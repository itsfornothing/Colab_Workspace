import json
import logging
from channels.generic.websocket import AsyncWebsocketConsumer
from asgiref.sync import sync_to_async
from django.utils import timezone
 
logger = logging.getLogger(__name__)
 
 
class ChannelConsumer(AsyncWebsocketConsumer):
    """
    Per-channel WebSocket consumer (Slack-like channel chat).
    Users connect to a specific channel within a workspace.
    """
 
    async def connect(self):
        self.channel_id   = self.scope["url_route"]["kwargs"]["channel_id"]
        self.user         = self.scope.get("user")
 
        # BUG FIX 1+2: authentication guard
        if not self.user or not self.user.is_authenticated:
            await self.close(code=4001)
            return
 
        # BUG FIX 5: membership check
        is_member = await self._is_channel_member()
        if not is_member:
            await self.close(code=4003)
            return
 
        self.group_name = f"channel_{self.channel_id}"
        await self.channel_layer.group_add(self.group_name, self.channel_name)
        await self.accept()
 
        # Broadcast join presence
        await self.channel_layer.group_send(
            self.group_name,
            {
                "type":     "presence_event",
                "event":    "joined",
                "user_id":  str(self.user.id),
                "username": str(self.user),
                "sender_channel": self.channel_name,
            }
        )
 
    async def disconnect(self, close_code):
        if hasattr(self, "group_name"):
            await self.channel_layer.group_send(
                self.group_name,
                {
                    "type":     "presence_event",
                    "event":    "left",
                    "user_id":  str(self.user.id),
                    "username": str(self.user),
                }
            )
            await self.channel_layer.group_discard(self.group_name, self.channel_name)
 
    async def receive(self, text_data):
        try:
            data = json.loads(text_data)
        except (json.JSONDecodeError, ValueError):
            await self._send_error("Invalid JSON.")
            return
 
        msg_type = data.get("type")
 
        if msg_type == "message":
            await self._handle_message(data)
        elif msg_type == "typing":
            await self._handle_typing(data)
        elif msg_type == "edit":
            await self._handle_edit(data)
        elif msg_type == "delete":
            await self._handle_delete(data)
        elif msg_type == "reaction":
            await self._handle_reaction(data)
        elif msg_type == "mark_read":
            await self._handle_mark_read()
        elif msg_type == "heartbeat":
            await self.send(text_data=json.dumps({"type": "heartbeat_ack"}))
        else:
            await self._send_error(f"Unknown type: {msg_type!r}")
 
    # ---- incoming handlers ----
 
    async def _handle_message(self, data):
        content = str(data.get("content", "")).strip()
        if not content:
            return
 
        msg = await self._save_message(content, parent_id=data.get("parent_id"))
        await self.channel_layer.group_send(
            self.group_name,
            {
                "type":       "chat_message",
                "message_id": str(msg.id),
                "content":    msg.content,
                "user_id":    str(self.user.id),
                "username":   str(self.user),
                "created_at": msg.created_at.isoformat(),
                "parent_id":  str(msg.parent_id) if msg.parent_id else None,
            }
        )
 
    async def _handle_typing(self, data):
        await self.channel_layer.group_send(
            self.group_name,
            {
                "type":     "typing_event",
                "user_id":  str(self.user.id),
                "username": str(self.user),
                "sender_channel": self.channel_name,
            }
        )
 
    async def _handle_edit(self, data):
        message_id = data.get("message_id")
        content    = str(data.get("content", "")).strip()
        if not message_id or not content:
            return
 
        ok = await self._edit_message(message_id, content)
        if ok:
            await self.channel_layer.group_send(
                self.group_name,
                {
                    "type":       "message_edited",
                    "message_id": message_id,
                    "content":    content,
                    "user_id":    str(self.user.id),
                }
            )
 
    async def _handle_delete(self, data):
        message_id = data.get("message_id")
        if not message_id:
            return
 
        ok = await self._delete_message(message_id)
        if ok:
            await self.channel_layer.group_send(
                self.group_name,
                {"type": "message_deleted", "message_id": message_id}
            )
 
    async def _handle_reaction(self, data):
        message_id = data.get("message_id")
        emoji      = data.get("emoji", "").strip()
        if not message_id or not emoji:
            return
 
        added = await self._toggle_reaction(message_id, emoji)
        await self.channel_layer.group_send(
            self.group_name,
            {
                "type":       "reaction_event",
                "message_id": message_id,
                "emoji":      emoji,
                "user_id":    str(self.user.id),
                "added":      added,
            }
        )
 
    async def _handle_mark_read(self):
        await self._update_last_read()
 
    # ---- outgoing senders (channel-layer → WebSocket) ----
 
    async def chat_message(self, event):
        await self.send(text_data=json.dumps({
            "type":       "message",
            "message_id": event["message_id"],
            "content":    event["content"],
            "user_id":    event["user_id"],
            "username":   event["username"],
            "created_at": event["created_at"],
            "parent_id":  event.get("parent_id"),
        }))
 
    async def typing_event(self, event):
        if event.get("sender_channel") == self.channel_name:
            return
        await self.send(text_data=json.dumps({
            "type":     "typing",
            "user_id":  event["user_id"],
            "username": event["username"],
        }))
 
    async def message_edited(self, event):
        await self.send(text_data=json.dumps({
            "type":       "edit",
            "message_id": event["message_id"],
            "content":    event["content"],
        }))
 
    async def message_deleted(self, event):
        await self.send(text_data=json.dumps({
            "type":       "delete",
            "message_id": event["message_id"],
        }))
 
    async def reaction_event(self, event):
        await self.send(text_data=json.dumps({
            "type":       "reaction",
            "message_id": event["message_id"],
            "emoji":      event["emoji"],
            "user_id":    event["user_id"],
            "added":      event["added"],
        }))
 
    async def presence_event(self, event):
        if event.get("sender_channel") == self.channel_name:
            return
        await self.send(text_data=json.dumps({
            "type":     "presence",
            "event":    event["event"],
            "user_id":  event["user_id"],
            "username": event["username"],
        }))
 
    # notification_message handler — allows services.py to push to this group
    async def notification_message(self, event):
        await self.send(text_data=json.dumps({
            "type":    "notification",
            "message": event["message"],
        }))
 
    # ---- DB helpers ----
 
    @sync_to_async
    def _is_channel_member(self):
        from .models import ChannelMembership
        return ChannelMembership.objects.filter(
            user=self.user, channel_id=self.channel_id
        ).exists()
 
    @sync_to_async
    def _save_message(self, content, parent_id=None):
        from .models import Message, Channel
        ch = Channel.objects.get(id=self.channel_id)
        return Message.objects.create(
            channel_id=self.channel_id,
            workspace=ch.workspace,
            sender=self.user,
            content=content,
            parent_id=parent_id,
        )
 
    @sync_to_async
    def _edit_message(self, message_id, content):
        from .models import Message
        try:
            msg = Message.objects.get(id=message_id, sender=self.user, is_deleted=False)
            msg.content   = content
            msg.is_edited = True
            msg.save(update_fields=["content", "is_edited", "updated_at"])
            return True
        except Message.DoesNotExist:
            return False
 
    @sync_to_async
    def _delete_message(self, message_id):
        from .models import Message
        try:
            msg = Message.objects.get(id=message_id, sender=self.user)
            msg.is_deleted = True
            msg.save(update_fields=["is_deleted"])
            return True
        except Message.DoesNotExist:
            return False
 
    @sync_to_async
    def _toggle_reaction(self, message_id, emoji):
        from .models import MessageReaction
        obj, created = MessageReaction.objects.get_or_create(
            message_id=message_id, user=self.user, emoji=emoji
        )
        if not created:
            obj.delete()
        return created   # True = added, False = removed
 
    @sync_to_async
    def _update_last_read(self):
        from .models import ChannelMembership
        ChannelMembership.objects.filter(
            user=self.user, channel_id=self.channel_id
        ).update(last_read=timezone.now())
 
    async def _send_error(self, detail):
        await self.send(text_data=json.dumps({"type": "error", "detail": detail}))
 
 
# ------------------------------------------------------------------ #
# Workspace-level notification consumer                               #
# ------------------------------------------------------------------ #
 
class NotificationConsumer(AsyncWebsocketConsumer):
    """
    Receives workspace/system notifications for the authenticated user.
    BUG FIX: original accessed self.scope["user"].id without auth check.
    """
 
    async def connect(self):
        user = self.scope.get("user")
 
        if not user or not user.is_authenticated:
            await self.close(code=4001)
            return
 
        self.user_id    = str(user.id)
        self.group_name = f"user_{self.user_id}"
 
        await self.channel_layer.group_add(self.group_name, self.channel_name)
        await self.accept()
 
        # Send unread count on connect
        count = await self._get_unread_count()
        await self.send(text_data=json.dumps({"type": "unread_count", "count": count}))
 
    async def disconnect(self, close_code):
        if hasattr(self, "group_name"):
            await self.channel_layer.group_discard(self.group_name, self.channel_name)
 
    async def receive(self, text_data):
        try:
            data = json.loads(text_data)
        except (json.JSONDecodeError, ValueError):
            return
 
        if data.get("type") == "mark_read":
            await self._mark_all_read()
        elif data.get("type") == "heartbeat":
            await self.send(text_data=json.dumps({"type": "heartbeat_ack"}))
 
    async def notification_message(self, event):
        await self.send(text_data=json.dumps({
            "type":    "notification",
            "message": event["message"],
            "meta":    event.get("meta"),
        }))
 
    @sync_to_async
    def _get_unread_count(self):
        from .models import Notification
        return Notification.objects.filter(user_id=self.user_id, is_read=False).count()
 
    @sync_to_async
    def _mark_all_read(self):
        from .models import Notification
        Notification.objects.filter(user_id=self.user_id, is_read=False).update(is_read=True)
 
 
# ------------------------------------------------------------------ #
# Workspace-wide broadcast consumer (for member join/role change)    #
# ------------------------------------------------------------------ #
 
class WorkspaceConsumer(AsyncWebsocketConsumer):
    """
    Workspace-level WebSocket for real-time member/role/channel events.
    Does NOT handle chat — use ChannelConsumer for that.
    """
 
    async def connect(self):
        self.workspace_id = self.scope["url_route"]["kwargs"]["workspace_id"]
        user              = self.scope.get("user")
 
        if not user or not user.is_authenticated:
            await self.close(code=4001)
            return
 
        is_member = await self._is_member()
        if not is_member:
            await self.close(code=4003)
            return
 
        self.group_name = f"workspace_{self.workspace_id}"
        await self.channel_layer.group_add(self.group_name, self.channel_name)
        await self.accept()
 
    async def disconnect(self, close_code):
        if hasattr(self, "group_name"):
            await self.channel_layer.group_discard(self.group_name, self.channel_name)
 
    async def notification_message(self, event):
        await self.send(text_data=json.dumps({
            "type":    "notification",
            "message": event["message"],
        }))
 
    async def workspace_event(self, event):
        await self.send(text_data=json.dumps(event["data"]))
 
    @sync_to_async
    def _is_member(self):
        from .models import Membership
        return Membership.objects.filter(
            user=self.scope["user"], workspace_id=self.workspace_id
        ).exists()