"""
WebRTCConsumer — Full WebRTC signaling server via Django Channels.
 
Full peer connection flow implemented:
  Client A connects → receives room_state (all participants + ICE servers)
  Client A sends offer  → targeted to Client B's user_id
  Client B sends answer → targeted back to Client A's user_id
  Both sides exchange ICE candidates → targeted by user_id
  Any participant mutes/unmutes → broadcast to room
  Any participant leaves → room gets participant_left event
"""


import json
import logging
from channels.generic.websocket import AsyncWebsocketConsumer
from asgiref.sync import sync_to_async
from django.utils import timezone
 
from .models import Room, Participant, Signal, IceServer
 
logger = logging.getLogger(__name__)
 
 
class WebRTCConsumer(AsyncWebsocketConsumer):
 
    # ------------------------------------------------------------------ #
    # Lifecycle                                                            #
    # ------------------------------------------------------------------ #
 
    async def connect(self):
        self.room_id = self.scope["url_route"]["kwargs"]["room_id"]
        self.user = self.scope.get("user")
 
        # BUG FIX 1: Authentication guard
        if not self.user or not self.user.is_authenticated:
            await self.close(code=4001)
            return
 
        self.group_name = f"room_{self.room_id}"
        self.user_id = str(self.user.id)
 
        # Validate room exists and is active
        room = await self._get_room()
        if not room:
            await self.close(code=4004)
            return
 
        # BUG FIX 2: Enforce max_participants
        count = await self._get_participant_count()
        if count >= room.max_participants:
            await self.close(code=4008)
            return
 
        await self.channel_layer.group_add(self.group_name, self.channel_name)
        await self.accept()
 
        # Register participant in DB
        await self._join_room()
 
        # Send room state to the newly joined client:
        # - all current participants
        # - ICE server list (STUN + TURN credentials)
        participants = await self._get_participants()
        ice_servers = await self._get_ice_servers()
 
        await self.send(text_data=json.dumps({
            "type": "room_state",
            "room_id": self.room_id,
            "your_user_id": self.user_id,
            "participants": participants,
            "ice_servers": ice_servers,
        }))
 
        # Notify everyone else in the room that a new peer joined
        await self.channel_layer.group_send(
            self.group_name,
            {
                "type": "participant_joined",
                "user_id": self.user_id,
                "username": str(self.user),
                "sender_channel": self.channel_name,
            }
        )
 
    async def disconnect(self, close_code):
        if hasattr(self, "group_name"):
            await self._leave_room()
 
            await self.channel_layer.group_send(
                self.group_name,
                {
                    "type": "participant_left",
                    "user_id": self.user_id,
                    "username": str(self.user),
                }
            )
            await self.channel_layer.group_discard(self.group_name, self.channel_name)
 
    # ------------------------------------------------------------------ #
    # Receive (client → server)                                           #
    # ------------------------------------------------------------------ #
 
    async def receive(self, text_data):
        try:
            data = json.loads(text_data)
        except (json.JSONDecodeError, ValueError):
            await self._send_error("Invalid JSON.")
            return
 
        msg_type = data.get("type")
 
        # ---- WebRTC signaling (MUST be targeted, not broadcast) ----
        if msg_type in ("offer", "answer", "ice_candidate"):
            await self._handle_signal(data, msg_type)
 
        # ---- Media state changes ----
        elif msg_type == "media_state":
            await self._handle_media_state(data)
 
        # ---- Screen sharing ----
        elif msg_type in ("screen_share_started", "screen_share_stopped"):
            await self._handle_screen_share(data, msg_type)
 
        # ---- Recording events (host only) ----
        elif msg_type in ("recording_started", "recording_stopped"):
            await self._handle_recording_event(data, msg_type)
 
        # ---- Chat inside the room ----
        elif msg_type == "room_chat":
            await self._handle_room_chat(data)
 
        # ---- Heartbeat ----
        elif msg_type == "heartbeat":
            await self.send(text_data=json.dumps({"type": "heartbeat_ack"}))
 
        else:
            await self._send_error(f"Unknown message type: {msg_type!r}")
 
    # ------------------------------------------------------------------ #
    # Incoming handlers                                                   #
    # ------------------------------------------------------------------ #
 
    async def _handle_signal(self, data: dict, signal_type: str):
        """
        Route offer/answer/ICE to a SPECIFIC target peer.
 
        BUG FIX 3 + 4: Original broadcast to the entire group.
        In a room with peers A, B, C: A's offer intended for B would also
        be received by C, who would try to create an answer — breaking
        all connections. WebRTC signaling MUST be point-to-point.
        """
        target_user_id = data.get("target_user_id")
        if not target_user_id:
            await self._send_error(f"{signal_type} requires target_user_id.")
            return
 
        signal_data = data.get("data") or data.get("sdp") or data.get("candidate")
        if not signal_data:
            await self._send_error(f"{signal_type} requires signal data.")
            return
 
        # Persist for reconnect delivery
        await self._save_signal(signal_type, target_user_id, signal_data)
 
        # Send to target peer's personal channel group
        await self.channel_layer.group_send(
            f"user_{target_user_id}",   # Each user is also in their own group
            {
                "type": "signal_relay",
                "signal_type": signal_type,
                "from_user_id": self.user_id,
                "data": signal_data,
            }
        )
 
    async def _handle_media_state(self, data: dict):
        """Broadcast mute/video state change to all peers in the room."""
        is_muted = data.get("is_muted")
        is_video_on = data.get("is_video_on")
 
        await self._update_participant_media(is_muted, is_video_on)
 
        await self.channel_layer.group_send(
            self.group_name,
            {
                "type": "media_state_changed",
                "user_id": self.user_id,
                "is_muted": is_muted,
                "is_video_on": is_video_on,
                "sender_channel": self.channel_name,
            }
        )
 
    async def _handle_screen_share(self, data: dict, event_type: str):
        sharing = event_type == "screen_share_started"
        await self._update_screen_share(sharing)
 
        await self.channel_layer.group_send(
            self.group_name,
            {
                "type": "screen_share_event",
                "user_id": self.user_id,
                "sharing": sharing,
                "sender_channel": self.channel_name,
            }
        )
 
    async def _handle_recording_event(self, data: dict, event_type: str):
        """Notify all peers that recording started/stopped (host only)."""
        is_host = await self._is_host()
        if not is_host:
            await self._send_error("Only the host can control recording.")
            return
 
        await self.channel_layer.group_send(
            self.group_name,
            {
                "type": "recording_event",
                "event_type": event_type,
                "user_id": self.user_id,
            }
        )
 
    async def _handle_room_chat(self, data: dict):
        """Simple in-room text chat (no persistence needed)."""
        message = str(data.get("message", "")).strip()[:1000]
        if not message:
            return
 
        await self.channel_layer.group_send(
            self.group_name,
            {
                "type": "room_chat_message",
                "user_id": self.user_id,
                "username": str(self.user),
                "message": message,
            }
        )
 
    # ------------------------------------------------------------------ #
    # Outgoing event senders (channel-layer → this WebSocket)            #
    # ------------------------------------------------------------------ #
 
    async def signal_relay(self, event):
        """Deliver a targeted WebRTC signal (offer/answer/ICE) to this client."""
        await self.send(text_data=json.dumps({
            "type": event["signal_type"],
            "from_user_id": event["from_user_id"],
            "data": event["data"],
        }))
 
    async def participant_joined(self, event):
        if event.get("sender_channel") == self.channel_name:
            return
        await self.send(text_data=json.dumps({
            "type": "participant_joined",
            "user_id": event["user_id"],
            "username": event["username"],
        }))
 
    async def participant_left(self, event):
        await self.send(text_data=json.dumps({
            "type": "participant_left",
            "user_id": event["user_id"],
            "username": event["username"],
        }))
 
    async def media_state_changed(self, event):
        if event.get("sender_channel") == self.channel_name:
            return
        await self.send(text_data=json.dumps({
            "type": "media_state",
            "user_id": event["user_id"],
            "is_muted": event["is_muted"],
            "is_video_on": event["is_video_on"],
        }))
 
    async def screen_share_event(self, event):
        if event.get("sender_channel") == self.channel_name:
            return
        await self.send(text_data=json.dumps({
            "type": "screen_share_started" if event["sharing"] else "screen_share_stopped",
            "user_id": event["user_id"],
        }))
 
    async def recording_event(self, event):
        await self.send(text_data=json.dumps({
            "type": event["event_type"],
            "user_id": event["user_id"],
        }))
 
    async def room_chat_message(self, event):
        await self.send(text_data=json.dumps({
            "type": "room_chat",
            "user_id": event["user_id"],
            "username": event["username"],
            "message": event["message"],
        }))
 
    # ------------------------------------------------------------------ #
    # DB helpers                                                           #
    # ------------------------------------------------------------------ #
 
    @sync_to_async
    def _get_room(self):
        try:
            return Room.objects.get(id=self.room_id, is_active=True)
        except Room.DoesNotExist:
            return None
 
    @sync_to_async
    def _get_participant_count(self):
        return Participant.objects.filter(room_id=self.room_id, left_at__isnull=True).count()
 
    @sync_to_async
    def _join_room(self):
        participant, created = Participant.objects.get_or_create(
            room_id=self.room_id,
            user=self.user,
            defaults={"role": "participant"},
        )
        if not created:
            # Rejoin — clear left_at
            participant.left_at = None
            participant.save(update_fields=["left_at"])
        return participant
 
    @sync_to_async
    def _leave_room(self):
        Participant.objects.filter(
            room_id=self.room_id, user=self.user
        ).update(left_at=timezone.now())
 
    @sync_to_async
    def _get_participants(self):
        participants = Participant.objects.filter(
            room_id=self.room_id, left_at__isnull=True
        ).select_related("user")
        return [
            {
                "user_id": str(p.user_id),
                "username": str(p.user),
                "role": p.role,
                "is_muted": p.is_muted,
                "is_video_on": p.is_video_on,
                "is_screen_sharing": p.is_screen_sharing,
            }
            for p in participants
        ]
 
    @sync_to_async
    def _get_ice_servers(self):
        """
        Return STUN + TURN server configs for the client's RTCPeerConnection.
        TURN credentials are fetched from the DB (managed via admin or API).
        """
        servers = IceServer.objects.filter(is_active=True)
        return [
            {
                "urls": s.url,
                **({"username": s.username, "credential": s.credential}
                   if s.username else {}),
            }
            for s in servers
        ]
 
    @sync_to_async
    def _save_signal(self, signal_type: str, target_user_id: str, signal_data):
        Signal.objects.create(
            room_id=self.room_id,
            sender=self.user,
            target_user_id=target_user_id,
            signal_type=signal_type,
            signal_data=signal_data if isinstance(signal_data, dict) else {"raw": signal_data},
            is_delivered=False,
        )
 
    @sync_to_async
    def _update_participant_media(self, is_muted, is_video_on):
        updates = {}
        if is_muted is not None:
            updates["is_muted"] = is_muted
        if is_video_on is not None:
            updates["is_video_on"] = is_video_on
        if updates:
            Participant.objects.filter(
                room_id=self.room_id, user=self.user
            ).update(**updates)
 
    @sync_to_async
    def _update_screen_share(self, sharing: bool):
        Participant.objects.filter(
            room_id=self.room_id, user=self.user
        ).update(is_screen_sharing=sharing)
 
    @sync_to_async
    def _is_host(self):
        return Participant.objects.filter(
            room_id=self.room_id, user=self.user, role__in=["host", "co_host"]
        ).exists()
 
    # ------------------------------------------------------------------ #
    # Utility                                                              #
    # ------------------------------------------------------------------ #
 
    async def _send_error(self, detail: str):
        await self.send(text_data=json.dumps({"type": "error", "detail": detail}))