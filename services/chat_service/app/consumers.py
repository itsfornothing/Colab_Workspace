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
)
from .presence import set_user_online, set_user_offline
from .search import index_message, delete_message_doc
from .firebase import send_push_to_channel_members   # see firebase.py

logger = logging.getLogger(__name__)

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
        await sync_to_async(set_user_online)(user.id)
        await self.accept()

        # Tell the client how often to send heartbeats
        await self.send(text_data=json.dumps({
            "type": "connected",
            "heartbeat_interval": PRESENCE_HEARTBEAT_INTERVAL,
        }))

    async def disconnect(self, close_code):
        user = self.scope["user"]
        if user.is_authenticated:
            await sync_to_async(set_user_offline)(user.id)

        await self.channel_layer.group_discard(self.room_group_name, self.channel_name)

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
            "message":      self._handle_message,
            "typing":       self._handle_typing,
            "reaction":     self._handle_reaction,
            "file":         self._handle_file,
            "pin":          self._handle_pin,
            "read":         self._handle_read,
            "edit":         self._handle_edit,
            "delete":       self._handle_delete,
            "heartbeat":    self._handle_heartbeat,
            "webrtc_offer": self._handle_webrtc,
            "webrtc_answer":self._handle_webrtc,
            "webrtc_ice":   self._handle_webrtc,
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

    async def _handle_webrtc(self, user, data):
        await self.channel_layer.group_send(
            self.room_group_name,
            {"type": "webrtc_event", "data": data}
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

    async def webrtc_event(self, event):
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

    # ====================== UTILITIES ======================

    async def _send_error(self, detail: str):
        await self.send(text_data=json.dumps({"type": "error", "detail": detail}))