from channels.generic.websocket import AsyncWebsocketConsumer
from asgiref.sync import sync_to_async
import json
import logging

from .models import (
    Message,
    Channel,
    ChannelMember,
    MessageRead,
    PinnedMessage,
    MessageReaction,
    Room,
    RoomParticipant,
)
from .presence import set_user_online, set_user_offline
from .search import index_message, delete_message_doc
from .firebase import send_push_to_channel_members   # see firebase.py
from . import audit_log
from . import performance_monitor
import logging
import threading
import requests
from django.conf import settings
 
logger = logging.getLogger(__name__)
 
NOTIFICATION_SERVICE_URL = getattr(
    settings, "NOTIFICATION_SERVICE_URL", "http://notification-service/api"
)
 
 
def _post_event(payload: dict) -> None:
    """Fire-and-forget HTTP POST to the notification service."""
    try:
        resp = requests.post(
            f"{NOTIFICATION_SERVICE_URL}/events/",
            json=payload,
            timeout=3,
        )
        if not resp.ok:
            logger.warning(
                "Notification service returned %s: %s", resp.status_code, resp.text
            )
    except requests.RequestException:
        logger.exception("Failed to reach notification service")
 
 
def _fire(payload: dict) -> None:
    """Send in a daemon thread so callers are never blocked."""
    t = threading.Thread(target=_post_event, args=(payload,), daemon=True)
    t.start()
 
 
# ------------------------------------------------------------------ #
# Public helpers — call these from the chat service                   #
# ------------------------------------------------------------------ #
 
def notify_new_message(receiver_id: str, sender_id: str, message: str, channel_id: str = None) -> None:
    _fire({
        "event_type": "message_created",
        "payload": {
            "receiver_id": receiver_id,
            "sender_id":   sender_id,
            "message":     message[:500],   # truncate for safety
            "channel_id":  channel_id,
        },
    })
 
 
def notify_user_mentioned(user_id: str, mentioned_by: str, message: str, channel_id: str = None) -> None:
    _fire({
        "event_type": "user_mentioned",
        "payload": {
            "user_id":     user_id,
            "mentioned_by": mentioned_by,
            "message":     message[:500],
            "channel_id":  channel_id,
        },
    })



# How often the client should send a heartbeat ping (seconds)
PRESENCE_HEARTBEAT_INTERVAL = 30


class ChatConsumer(AsyncWebsocketConsumer):

    # ====================== LIFECYCLE ======================

    async def connect(self):
        self.channel_id = self.scope["url_route"]["kwargs"]["channel_id"]
        self.room_group_name = f"channel_{self.channel_id}"
        user = self.scope["user"]

        if not user.is_authenticated:
            await self.close()
            return

        is_member = await self.is_member(user, self.channel_id)
        if not is_member:
            await self.close()
            return

        await self.channel_layer.group_add(self.room_group_name, self.channel_name)
        # Join user's personal group for direct messages (call invitations, etc.)
        self.user_group_name = f"user_{user.id}"
        await self.channel_layer.group_add(self.user_group_name, self.channel_name)
        # Join room groups for any active rooms the user is participating in
        self.active_room_groups = []
        active_room_ids = await self.get_user_active_room_ids(user)
        for room_id in active_room_ids:
            room_group = f"room_{room_id}"
            await self.channel_layer.group_add(room_group, self.channel_name)
            self.active_room_groups.append(room_group)
        await sync_to_async(set_user_online)(user.id)
        await self.accept()

        # Track WebSocket connection for performance monitoring (Requirements 11.2, 11.4)
        performance_monitor.record_websocket_connected()

        # Tell the client how often to send heartbeats
        await self.send(text_data=json.dumps({
            "type": "connected",
            "heartbeat_interval": PRESENCE_HEARTBEAT_INTERVAL,
        }))

    async def disconnect(self, close_code):
        user = self.scope["user"]
        if user.is_authenticated:
            await sync_to_async(set_user_offline)(user.id)

        # Track WebSocket disconnection for performance monitoring (Requirements 11.2, 11.4)
        performance_monitor.record_websocket_disconnected()

        await self.channel_layer.group_discard(self.room_group_name, self.channel_name)
        # Leave user's personal group
        if hasattr(self, 'user_group_name'):
            await self.channel_layer.group_discard(self.user_group_name, self.channel_name)
        # Leave active room groups
        for room_group in getattr(self, 'active_room_groups', []):
            await self.channel_layer.group_discard(room_group, self.channel_name)

    # ====================== RECEIVE ======================

    async def receive(self, text_data):
        try:
            data = json.loads(text_data)
        except (json.JSONDecodeError, ValueError):
            await self._send_error("Invalid JSON payload.")
            return

        event_type = data.get("type")
        user = self.scope["user"]

        if not user.is_authenticated:
            await self._send_error("Unauthenticated.")
            return

        handlers = {
            "message":          self._handle_message,
            "typing":           self._handle_typing,
            "reaction":         self._handle_reaction,
            "file":             self._handle_file,
            "pin":              self._handle_pin,
            "read":             self._handle_read,
            "edit":             self._handle_edit,
            "delete":           self._handle_delete,
            "heartbeat":        self._handle_heartbeat,
            "webrtc_offer":     self._handle_webrtc_offer,
            "webrtc_answer":    self._handle_webrtc_answer,
            "webrtc_ice":       self._handle_webrtc_ice,
            "call_invite":      self._handle_call_invite,
            "call_accept":      self._handle_call_accept,
            "call_decline":     self._handle_call_decline,
            "call_end":         self._handle_call_end,
            "participant_state": self._handle_participant_state,
        }

        handler = handlers.get(event_type)
        if handler:
            await handler(user, data)
        else:
            await self._send_error(f"Unknown event type: {event_type}")

    # ====================== EVENT HANDLERS (incoming) ======================

    async def _handle_message(self, user, data):
        message_text = data.get("message", "").strip()
        if not message_text:
            await self._send_error("Message content cannot be empty.")
            return

        msg_obj = await self.save_message(user, self.channel_id, message_text)

        await self.channel_layer.group_send(
            self.room_group_name,
            {
                "type": "chat_message",
                "message": message_text,
                "user": str(user),
                "message_id": str(msg_obj.id),
            }
        )

        # Fire push notifications asynchronously (non-blocking)
        try:
            await sync_to_async(send_push_to_channel_members)(
                channel_id=self.channel_id,
                sender=user,
                body=message_text[:200],
            )
        except Exception:
            logger.exception("Push notification failed for channel %s", self.channel_id)

    async def _handle_typing(self, user, data):
        await self.channel_layer.group_send(
            self.room_group_name,
            {"type": "typing_event", "user": str(user)}
        )

    async def _handle_reaction(self, user, data):
        message_id = data.get("message_id")
        emoji = data.get("emoji", "").strip()

        if not message_id or not emoji:
            await self._send_error("reaction requires message_id and emoji.")
            return

        await self.save_reaction(user, message_id, emoji)

        await self.channel_layer.group_send(
            self.room_group_name,
            {
                "type": "reaction_event",
                "message_id": message_id,
                "emoji": emoji,
                "user": str(user),
            }
        )

    async def _handle_file(self, user, data):
        file_url = data.get("file_url", "").strip()
        if not file_url:
            await self._send_error("file requires file_url.")
            return

        msg_obj = await self.save_file_message(user, self.channel_id, file_url)

        await self.channel_layer.group_send(
            self.room_group_name,
            {
                "type": "file_message",
                "file_url": file_url,
                "user": str(user),
                "message_id": str(msg_obj.id),
            }
        )

    async def _handle_pin(self, user, data):
        message_id = data.get("message_id")
        if not message_id:
            await self._send_error("pin requires message_id.")
            return

        await self.pin_message(user, message_id)

        await self.channel_layer.group_send(
            self.room_group_name,
            {"type": "pin_event", "message_id": message_id}
        )

    async def _handle_read(self, user, data):
        message_id = data.get("message_id")
        if not message_id:
            await self._send_error("read requires message_id.")
            return

        await self.mark_as_read(user, message_id)

        await self.channel_layer.group_send(
            self.room_group_name,
            {
                "type": "read_event",
                "message_id": message_id,
                "user": str(user),
            }
        )

    async def _handle_edit(self, user, data):
        message_id = data.get("message_id")
        content = data.get("content", "").strip()

        if not message_id or not content:
            await self._send_error("edit requires message_id and content.")
            return

        success = await self.edit_message(user, message_id, content)
        if not success:
            await self._send_error("Edit failed. You may not own this message.")
            return

        await self.channel_layer.group_send(
            self.room_group_name,
            {
                "type": "edit_event",
                "message_id": message_id,
                "content": content,
            }
        )

    async def _handle_delete(self, user, data):
        message_id = data.get("message_id")
        if not message_id:
            await self._send_error("delete requires message_id.")
            return

        success = await self.delete_message(user, message_id)
        if not success:
            await self._send_error("Delete failed. You may not own this message.")
            return

        await self.channel_layer.group_send(
            self.room_group_name,
            {"type": "delete_event", "message_id": message_id}
        )

    async def _handle_heartbeat(self, user, data):
        """Client sends periodic pings to keep presence alive."""
        await sync_to_async(set_user_online)(user.id)
        await self.send(text_data=json.dumps({"type": "heartbeat_ack"}))

    # ====================== VIDEO CALL SIGNALING HELPERS ======================

    async def _check_signaling_rate_limit(self, user, event_type):
        """Check rate limit for signaling messages. Returns True if allowed."""
        from .rate_limiter import SignalingRateLimiter
        is_allowed, remaining = await sync_to_async(SignalingRateLimiter.check_rate_limit)(
            str(user.id), event_type
        )
        if not is_allowed:
            await self.send(text_data=json.dumps({
                "type": "error",
                "detail": "Rate limit exceeded. Please slow down.",
                "code": "RATE_LIMIT_EXCEEDED"
            }))
            return False
        return True

    async def _sanitize_signaling_data(self, data):
        """Sanitize signaling data. Returns sanitized dict or None on error."""
        from .rate_limiter import sanitize_signaling_data
        try:
            return sanitize_signaling_data(data)
        except ValueError as e:
            await self.send(text_data=json.dumps({
                "type": "error",
                "detail": f"Invalid signaling data: {str(e)}",
                "code": "INVALID_DATA"
            }))
            return None

    # ====================== VIDEO CALL SIGNALING HANDLERS ======================

    async def _handle_call_invite(self, user, data):
        """Send call invitation to specified users."""
        # Rate limit check
        if not await self._check_signaling_rate_limit(user, "call_invite"):
            return

        room_id = data.get("room_id")
        invited_user_ids = data.get("invited_user_ids", [])
        
        if not room_id:
            await self._send_error("call_invite requires room_id.")
            return
        
        if not invited_user_ids or not isinstance(invited_user_ids, list):
            await self._send_error("call_invite requires invited_user_ids as a list.")
            return
        
        # Verify room exists and user is authorized
        room = await self.get_room(room_id)
        if not room:
            await self._send_error("Room not found.")
            return
        
        # Check if room is full
        if await self.is_room_full(room_id):
            await self._send_error("Room is at maximum capacity.")
            return
        
        # Send invitation to each invited user
        for invited_user_id in invited_user_ids:
            await self.channel_layer.group_send(
                f"user_{invited_user_id}",
                {
                    "type": "call_invitation",
                    "room_id": str(room_id),
                    "caller_id": str(user.id),
                    "caller_name": user.get_full_name(),
                }
            )
        
        # Audit log: call invited
        try:
            audit_log.log_call_invited(user.id, room_id, invited_user_ids)
        except Exception:
            pass
    
    async def _handle_call_accept(self, user, data):
        """Handle call acceptance and notify caller."""
        # Rate limit check
        if not await self._check_signaling_rate_limit(user, "call_accept"):
            return

        room_id = data.get("room_id")
        caller_id = data.get("caller_id")
        
        if not room_id or not caller_id:
            await self._send_error("call_accept requires room_id and caller_id.")
            return
        
        # Verify room exists and check capacity
        room = await self.get_room(room_id)
        if not room:
            await self._send_error("Room not found.")
            return
        
        if await self.is_room_full(room_id):
            await self._send_error("Room is at maximum capacity.")
            return
        
        # Notify the caller
        await self.channel_layer.group_send(
            f"user_{caller_id}",
            {
                "type": "call_accepted",
                "room_id": str(room_id),
                "accepter_id": str(user.id),
                "accepter_name": user.get_full_name(),
            }
        )
        
        # Broadcast to room that user is joining
        await self.channel_layer.group_send(
            f"room_{room_id}",
            {
                "type": "user_joined_call",
                "room_id": str(room_id),
                "user_id": str(user.id),
                "user_name": user.get_full_name(),
            }
        )
    
    async def _handle_call_decline(self, user, data):
        """Handle call decline and notify caller."""
        # Rate limit check
        if not await self._check_signaling_rate_limit(user, "call_decline"):
            return

        room_id = data.get("room_id")
        caller_id = data.get("caller_id")
        
        if not room_id or not caller_id:
            await self._send_error("call_decline requires room_id and caller_id.")
            return
        
        # Notify the caller
        await self.channel_layer.group_send(
            f"user_{caller_id}",
            {
                "type": "call_declined",
                "room_id": str(room_id),
                "decliner_id": str(user.id),
                "decliner_name": user.get_full_name(),
            }
        )
    
    async def _handle_call_end(self, user, data):
        """Handle call termination and broadcast to all participants."""
        # Rate limit check
        if not await self._check_signaling_rate_limit(user, "call_end"):
            return

        room_id = data.get("room_id")
        
        if not room_id:
            await self._send_error("call_end requires room_id.")
            return
        
        # Verify room exists
        room = await self.get_room(room_id)
        if not room:
            await self._send_error("Room not found.")
            return
        
        # Broadcast call end to all participants in the room
        await self.channel_layer.group_send(
            f"room_{room_id}",
            {
                "type": "call_ended",
                "room_id": str(room_id),
                "ended_by": str(user.id),
            }
        )
        
        # Audit log: call ended
        try:
            audit_log.log_call_ended(user.id, room_id)
        except Exception:
            pass
    
    async def _handle_webrtc_offer(self, user, data):
        """Relay WebRTC offer to target peer."""
        # Rate limit check
        if not await self._check_signaling_rate_limit(user, "webrtc_offer"):
            return

        room_id = data.get("room_id")
        to_user_id = data.get("to_user_id")
        sdp = data.get("sdp")

        if not room_id or not to_user_id or not sdp:
            await self._send_error("webrtc_offer requires room_id, to_user_id, and sdp.")
            return

        # Validate from_user_id if provided (prevent spoofing)
        if "from_user_id" in data and str(data["from_user_id"]) != str(user.id):
            await self._send_error("from_user_id does not match authenticated user.")
            return

        # Sanitize signaling data
        sanitized = await self._sanitize_signaling_data({
            'sdp': sdp,
            'room_id': room_id,
            'to_user_id': to_user_id,
        })
        if sanitized is None:
            return

        # Use sanitized values
        sdp = sanitized.get('sdp', sdp)
        room_id = sanitized.get('room_id', room_id)
        to_user_id = sanitized.get('to_user_id', to_user_id)

        # Validate room membership
        is_member = await self.is_room_member(user, room_id)
        if not is_member:
            await self._send_error("You are not a member of this room.")
            return

        # Validate target user is also a member
        target_is_member = await self.is_room_member_by_id(to_user_id, room_id)
        if not target_is_member:
            await self._send_error("Target user is not a member of this room.")
            return

        # Relay offer to target user — measure signaling latency (Requirement 11.2)
        with performance_monitor.measure_signaling_latency():
            await self.channel_layer.group_send(
                f"user_{to_user_id}",
                {
                    "type": "webrtc_offer_relay",
                    "room_id": str(room_id),
                    "from_user_id": str(user.id),
                    "to_user_id": str(to_user_id),
                    "sdp": sdp,
                }
            )
    
    async def _handle_webrtc_answer(self, user, data):
        """Relay WebRTC answer to initiator."""
        # Rate limit check
        if not await self._check_signaling_rate_limit(user, "webrtc_answer"):
            return

        room_id = data.get("room_id")
        to_user_id = data.get("to_user_id")
        sdp = data.get("sdp")

        if not room_id or not to_user_id or not sdp:
            await self._send_error("webrtc_answer requires room_id, to_user_id, and sdp.")
            return

        # Validate from_user_id if provided (prevent spoofing)
        if "from_user_id" in data and str(data["from_user_id"]) != str(user.id):
            await self._send_error("from_user_id does not match authenticated user.")
            return

        # Sanitize signaling data
        sanitized = await self._sanitize_signaling_data({
            'sdp': sdp,
            'room_id': room_id,
            'to_user_id': to_user_id,
        })
        if sanitized is None:
            return

        # Use sanitized values
        sdp = sanitized.get('sdp', sdp)
        room_id = sanitized.get('room_id', room_id)
        to_user_id = sanitized.get('to_user_id', to_user_id)

        # Validate room membership
        is_member = await self.is_room_member(user, room_id)
        if not is_member:
            await self._send_error("You are not a member of this room.")
            return

        # Validate target user is also a member
        target_is_member = await self.is_room_member_by_id(to_user_id, room_id)
        if not target_is_member:
            await self._send_error("Target user is not a member of this room.")
            return

        # Relay answer to initiator — measure signaling latency (Requirement 11.2)
        with performance_monitor.measure_signaling_latency():
            await self.channel_layer.group_send(
                f"user_{to_user_id}",
                {
                    "type": "webrtc_answer_relay",
                    "room_id": str(room_id),
                    "from_user_id": str(user.id),
                    "to_user_id": str(to_user_id),
                    "sdp": sdp,
                }
            )
    
    async def _handle_webrtc_ice(self, user, data):
        """Relay ICE candidate to target peer."""
        # Rate limit check
        if not await self._check_signaling_rate_limit(user, "webrtc_ice"):
            return

        room_id = data.get("room_id")
        to_user_id = data.get("to_user_id")
        candidate = data.get("candidate")

        if not room_id or not to_user_id or not candidate:
            await self._send_error("webrtc_ice requires room_id, to_user_id, and candidate.")
            return

        # Validate from_user_id if provided (prevent spoofing)
        if "from_user_id" in data and str(data["from_user_id"]) != str(user.id):
            await self._send_error("from_user_id does not match authenticated user.")
            return

        # Sanitize signaling data
        sanitized = await self._sanitize_signaling_data({
            'candidate': candidate,
            'room_id': room_id,
            'to_user_id': to_user_id,
        })
        if sanitized is None:
            return

        # Use sanitized values
        candidate = sanitized.get('candidate', candidate)
        room_id = sanitized.get('room_id', room_id)
        to_user_id = sanitized.get('to_user_id', to_user_id)

        # Validate room membership
        is_member = await self.is_room_member(user, room_id)
        if not is_member:
            await self._send_error("You are not a member of this room.")
            return

        # Validate target user is also a member
        target_is_member = await self.is_room_member_by_id(to_user_id, room_id)
        if not target_is_member:
            await self._send_error("Target user is not a member of this room.")
            return

        # Relay ICE candidate to target user — measure signaling latency (Requirement 11.2)
        with performance_monitor.measure_signaling_latency():
            await self.channel_layer.group_send(
                f"user_{to_user_id}",
                {
                    "type": "webrtc_ice_relay",
                    "room_id": str(room_id),
                    "from_user_id": str(user.id),
                    "to_user_id": str(to_user_id),
                    "candidate": candidate,
                }
            )
    
    async def _handle_participant_state(self, user, data):
        """Update and broadcast participant state (muted, video off, screen sharing)."""
        # Rate limit check
        if not await self._check_signaling_rate_limit(user, "participant_state"):
            return

        room_id = data.get("room_id")
        is_muted = data.get("is_muted")
        is_video_on = data.get("is_video_on")
        is_screen_sharing = data.get("is_screen_sharing")
        
        if not room_id:
            await self._send_error("participant_state requires room_id.")
            return
        
        # Validate room membership
        is_member = await self.is_room_member(user, room_id)
        if not is_member:
            await self._send_error("You are not a member of this room.")
            return
        
        # Update participant state in database
        await self.update_participant_state(
            user, room_id, is_muted, is_video_on, is_screen_sharing
        )
        
        # Audit log: participant state changed
        try:
            audit_log.log_participant_state_changed(user.id, room_id, is_muted, is_video_on, is_screen_sharing)
        except Exception:
            pass

        # Broadcast state update to all participants in the room
        await self.channel_layer.group_send(
            f"room_{room_id}",
            {
                "type": "participant_state_update",
                "room_id": str(room_id),
                "user_id": str(user.id),
                "is_muted": is_muted,
                "is_video_on": is_video_on,
                "is_screen_sharing": is_screen_sharing,
            }
        )

    # ====================== OUTGOING EVENT SENDERS ======================

    async def chat_message(self, event):
        await self.send(text_data=json.dumps({
            "type": "message",
            "message": event["message"],
            "user": event["user"],
            "message_id": event.get("message_id"),
        }))

    async def typing_event(self, event):
        await self.send(text_data=json.dumps({
            "type": "typing",
            "user": event["user"],
        }))

    async def reaction_event(self, event):
        await self.send(text_data=json.dumps({
            "type": "reaction",
            "message_id": event["message_id"],
            "emoji": event["emoji"],
            "user": event["user"],
        }))

    async def file_message(self, event):
        await self.send(text_data=json.dumps({
            "type": "file",
            "file_url": event["file_url"],
            "user": event["user"],
            "message_id": event.get("message_id"),
        }))

    async def pin_event(self, event):
        await self.send(text_data=json.dumps({
            "type": "pin",
            "message_id": event["message_id"],
        }))

    async def read_event(self, event):
        await self.send(text_data=json.dumps({
            "type": "read",
            "message_id": event["message_id"],
            "user": event["user"],
        }))

    async def edit_event(self, event):
        await self.send(text_data=json.dumps({
            "type": "edit",
            "message_id": event["message_id"],
            "content": event["content"],
        }))

    async def delete_event(self, event):
        await self.send(text_data=json.dumps({
            "type": "delete",
            "message_id": event["message_id"],
        }))

    # ====================== VIDEO CALL EVENT RELAYS ======================

    async def call_invitation(self, event):
        """Relay call invitation to invited user."""
        await self.send(text_data=json.dumps({
            "type": "call_invite",
            "room_id": event["room_id"],
            "caller_id": event["caller_id"],
            "caller_name": event["caller_name"],
        }))
    
    async def call_accepted(self, event):
        """Relay call acceptance to caller."""
        await self.send(text_data=json.dumps({
            "type": "call_accept",
            "room_id": event["room_id"],
            "accepter_id": event["accepter_id"],
            "accepter_name": event["accepter_name"],
        }))
    
    async def call_declined(self, event):
        """Relay call decline to caller."""
        await self.send(text_data=json.dumps({
            "type": "call_decline",
            "room_id": event["room_id"],
            "decliner_id": event["decliner_id"],
            "decliner_name": event["decliner_name"],
        }))
    
    async def call_ended(self, event):
        """Relay call end to all participants."""
        await self.send(text_data=json.dumps({
            "type": "call_end",
            "room_id": event["room_id"],
            "ended_by": event["ended_by"],
        }))
    
    async def user_joined_call(self, event):
        """Notify room that a user joined the call."""
        await self.send(text_data=json.dumps({
            "type": "user_joined",
            "room_id": event["room_id"],
            "user_id": event["user_id"],
            "user_name": event["user_name"],
        }))
    
    async def webrtc_offer_relay(self, event):
        """Relay WebRTC offer to target peer."""
        await self.send(text_data=json.dumps({
            "type": "webrtc_offer",
            "room_id": event["room_id"],
            "from_user_id": event["from_user_id"],
            "to_user_id": event["to_user_id"],
            "sdp": event["sdp"],
        }))
    
    async def webrtc_answer_relay(self, event):
        """Relay WebRTC answer to initiator."""
        await self.send(text_data=json.dumps({
            "type": "webrtc_answer",
            "room_id": event["room_id"],
            "from_user_id": event["from_user_id"],
            "to_user_id": event["to_user_id"],
            "sdp": event["sdp"],
        }))
    
    async def webrtc_ice_relay(self, event):
        """Relay ICE candidate to target peer."""
        await self.send(text_data=json.dumps({
            "type": "webrtc_ice",
            "room_id": event["room_id"],
            "from_user_id": event["from_user_id"],
            "to_user_id": event["to_user_id"],
            "candidate": event["candidate"],
        }))
    
    async def participant_state_update(self, event):
        """Broadcast participant state update to room."""
        await self.send(text_data=json.dumps({
            "type": "participant_state",
            "room_id": event["room_id"],
            "user_id": event["user_id"],
            "is_muted": event["is_muted"],
            "is_video_on": event["is_video_on"],
            "is_screen_sharing": event["is_screen_sharing"],
        }))

    async def webrtc_event(self, event):
        """Legacy WebRTC event handler (deprecated, kept for backward compatibility)."""
        await self.send(text_data=json.dumps(event["data"]))

    # ====================== DB HELPERS ======================

    @sync_to_async
    def save_message(self, user, channel_id, content):
        channel = Channel.objects.get(id=channel_id)
        msg = Message.objects.create(
            channel=channel,
            sender=user,
            content=content,
            message_type="text",
        )
        try:
            index_message(msg)
        except Exception:
            logger.exception("Elasticsearch indexing failed for message %s", msg.id)
        return msg

    @sync_to_async
    def save_file_message(self, user, channel_id, file_url):
        channel = Channel.objects.get(id=channel_id)
        msg = Message.objects.create(
            channel=channel,
            sender=user,
            content="",
            file_url=file_url,
            message_type="file",
        )
        return msg

    @sync_to_async
    def save_reaction(self, user, message_id, emoji):
        message = Message.objects.get(id=message_id)
        # Toggle: remove if already reacted with same emoji, otherwise add
        reaction, created = MessageReaction.objects.get_or_create(
            message=message,
            user=user,
            emoji=emoji,
        )
        if not created:
            reaction.delete()

    @sync_to_async
    def is_member(self, user, channel_id):
        return ChannelMember.objects.filter(
            user=user,
            channel_id=channel_id,
        ).exists()

    @sync_to_async
    def mark_as_read(self, user, message_id):
        message = Message.objects.get(id=message_id)
        MessageRead.objects.get_or_create(user=user, message=message)

    @sync_to_async
    def edit_message(self, user, message_id, content):
        try:
            msg = Message.objects.get(id=message_id, sender=user, is_deleted=False)
            msg.content = content
            msg.is_edited = True
            msg.save()
            try:
                index_message(msg)
            except Exception:
                logger.exception("Elasticsearch re-index failed for message %s", msg.id)
            return True
        except Message.DoesNotExist:
            return False

    @sync_to_async
    def delete_message(self, user, message_id):
        try:
            msg = Message.objects.get(id=message_id, sender=user)
            msg.is_deleted = True
            msg.save()
            try:
                delete_message_doc(message_id)
            except Exception:
                logger.exception("Elasticsearch delete failed for message %s", message_id)
            return True
        except Message.DoesNotExist:
            return False

    @sync_to_async
    def pin_message(self, user, message_id):
        # Any authenticated channel member may pin
        msg = Message.objects.get(id=message_id)
        PinnedMessage.objects.get_or_create(
            message=msg,
            channel=msg.channel,
            defaults={"pinned_by": user},
        )

    # ====================== VIDEO CALL DB HELPERS ======================

    @sync_to_async
    def get_room(self, room_id):
        """Get room by ID."""
        from .models import Room
        try:
            return Room.objects.get(id=room_id)
        except Room.DoesNotExist:
            return None
    
    @sync_to_async
    def get_user_active_room_ids(self, user):
        """Get list of room IDs where user is an active participant."""
        from .models import RoomParticipant
        return list(
            RoomParticipant.objects.filter(
                user=user,
                left_at__isnull=True,
                room__is_active=True
            ).values_list('room_id', flat=True)
        )
    
    @sync_to_async
    def is_room_full(self, room_id):
        """Check if room is at maximum capacity."""
        from .models import Room
        try:
            room = Room.objects.get(id=room_id)
            return room.is_full
        except Room.DoesNotExist:
            return False
    
    @sync_to_async
    def is_room_member(self, user, room_id):
        """Check if user is a member of the room."""
        from .models import RoomParticipant
        return RoomParticipant.objects.filter(
            room_id=room_id,
            user=user,
            left_at__isnull=True
        ).exists()
    
    @sync_to_async
    def is_room_member_by_id(self, user_id, room_id):
        """Check if user (by ID) is a member of the room."""
        from .models import RoomParticipant
        return RoomParticipant.objects.filter(
            room_id=room_id,
            user_id=user_id,
            left_at__isnull=True
        ).exists()
    
    @sync_to_async
    def update_participant_state(self, user, room_id, is_muted, is_video_on, is_screen_sharing):
        """Update participant state in the database."""
        from .models import RoomParticipant
        try:
            participant = RoomParticipant.objects.get(
                room_id=room_id,
                user=user,
                left_at__isnull=True
            )
            if is_muted is not None:
                participant.is_muted = is_muted
            if is_video_on is not None:
                participant.is_video_on = is_video_on
            if is_screen_sharing is not None:
                participant.is_screen_sharing = is_screen_sharing
            participant.save()
            return True
        except RoomParticipant.DoesNotExist:
            return False

    # ====================== UTILITIES ======================

    async def _send_error(self, detail: str):
        await self.send(text_data=json.dumps({"type": "error", "detail": detail}))


# ──────────────────────────────────────────────────────────────────────────────
# CallConsumer — lightweight consumer for global call signaling
#
# Connects the authenticated user to their personal group (user_{user_id}) so
# that call invitations, acceptances, declines, and end notifications are
# delivered even when no chat channel WebSocket is open.
#
# URL: /ws/calls/
# ──────────────────────────────────────────────────────────────────────────────

class CallConsumer(AsyncWebsocketConsumer):
    """
    Dedicated WebSocket consumer for call signaling.

    Each authenticated user connects here once (from WorkspaceShell) and joins
    their personal group ``user_{user_id}``.  The ChatConsumer already sends
    call-related events to that group, so this consumer simply relays them to
    the browser.

    It also accepts outgoing call signaling messages (call_invite, call_accept,
    call_decline, call_end) so the frontend can use a single WebSocket for all
    call lifecycle management without needing an open chat channel.
    """

    async def connect(self):
        user = self.scope["user"]
        if not user.is_authenticated:
            await self.close(code=4001)
            return

        self.user_group_name = f"user_{user.id}"
        await self.channel_layer.group_add(self.user_group_name, self.channel_name)
        await self.accept()

        await self.send(text_data=json.dumps({
            "type": "connected",
            "message": "Call signaling channel ready",
        }))

    async def disconnect(self, close_code):
        if hasattr(self, "user_group_name"):
            await self.channel_layer.group_discard(self.user_group_name, self.channel_name)

    async def receive(self, text_data):
        try:
            data = json.loads(text_data)
        except (json.JSONDecodeError, ValueError):
            await self._send_error("Invalid JSON payload.")
            return

        user = self.scope["user"]
        if not user.is_authenticated:
            await self._send_error("Unauthenticated.")
            return

        event_type = data.get("type")

        handlers = {
            "call_invite":  self._handle_call_invite,
            "call_accept":  self._handle_call_accept,
            "call_decline": self._handle_call_decline,
            "call_end":     self._handle_call_end,
            "heartbeat":    self._handle_heartbeat,
        }

        handler = handlers.get(event_type)
        if handler:
            await handler(user, data)
        else:
            await self._send_error(f"Unknown event type: {event_type}")

    # ── Outgoing call signaling ──────────────────────────────────────────

    async def _handle_call_invite(self, user, data):
        """Send call invitation to specified users."""
        room_id = data.get("room_id")
        invited_user_ids = data.get("invited_user_ids", [])

        if not room_id:
            await self._send_error("call_invite requires room_id.")
            return

        if not invited_user_ids or not isinstance(invited_user_ids, list):
            await self._send_error("call_invite requires invited_user_ids as a list.")
            return

        for invited_user_id in invited_user_ids:
            await self.channel_layer.group_send(
                f"user_{invited_user_id}",
                {
                    "type": "call_invitation",
                    "room_id": str(room_id),
                    "caller_id": str(user.id),
                    "caller_name": user.get_full_name(),
                    "caller_avatar": None,
                },
            )

        try:
            audit_log.log_call_invited(user.id, room_id, invited_user_ids)
        except Exception:
            pass

    async def _handle_call_accept(self, user, data):
        """Handle call acceptance and notify caller."""
        room_id = data.get("room_id")
        caller_id = data.get("caller_id")

        if not room_id or not caller_id:
            await self._send_error("call_accept requires room_id and caller_id.")
            return

        await self.channel_layer.group_send(
            f"user_{caller_id}",
            {
                "type": "call_accepted",
                "room_id": str(room_id),
                "accepter_id": str(user.id),
                "accepter_name": user.get_full_name(),
            },
        )

    async def _handle_call_decline(self, user, data):
        """Handle call decline and notify caller."""
        room_id = data.get("room_id")
        caller_id = data.get("caller_id")

        if not room_id or not caller_id:
            await self._send_error("call_decline requires room_id and caller_id.")
            return

        await self.channel_layer.group_send(
            f"user_{caller_id}",
            {
                "type": "call_declined",
                "room_id": str(room_id),
                "decliner_id": str(user.id),
                "decliner_name": user.get_full_name(),
            },
        )

    async def _handle_call_end(self, user, data):
        """Handle call termination and broadcast to all participants."""
        room_id = data.get("room_id")

        if not room_id:
            await self._send_error("call_end requires room_id.")
            return

        await self.channel_layer.group_send(
            f"room_{room_id}",
            {
                "type": "call_ended",
                "room_id": str(room_id),
                "ended_by": str(user.id),
            },
        )

        try:
            audit_log.log_call_ended(user.id, room_id)
        except Exception:
            pass

    async def _handle_heartbeat(self, user, data):
        await self.send(text_data=json.dumps({"type": "heartbeat_ack"}))

    # ── Incoming group event relays ──────────────────────────────────────

    async def call_invitation(self, event):
        """Relay call invitation to this user."""
        await self.send(text_data=json.dumps({
            "type": "call_invite",
            "room_id": event["room_id"],
            "caller_id": event["caller_id"],
            "caller_name": event["caller_name"],
            "caller_avatar": event.get("caller_avatar"),
        }))

    async def call_accepted(self, event):
        """Relay call acceptance to caller."""
        await self.send(text_data=json.dumps({
            "type": "call_accept",
            "room_id": event["room_id"],
            "accepter_id": event["accepter_id"],
            "accepter_name": event["accepter_name"],
        }))

    async def call_declined(self, event):
        """Relay call decline to caller."""
        await self.send(text_data=json.dumps({
            "type": "call_decline",
            "room_id": event["room_id"],
            "decliner_id": event["decliner_id"],
            "decliner_name": event["decliner_name"],
        }))

    async def call_ended(self, event):
        """Relay call end to this user."""
        await self.send(text_data=json.dumps({
            "type": "call_end",
            "room_id": event["room_id"],
            "ended_by": event["ended_by"],
        }))

    async def _send_error(self, detail: str):
        await self.send(text_data=json.dumps({"type": "error", "detail": detail}))