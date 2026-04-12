"""
NotificationConsumer — WebSocket consumer for real-time notifications.

BUG FIX: Original consumer had no authentication — anyone who knew a
user_id could subscribe to that user's notification stream. Fixed by:
  1. Requiring JWTAuthMiddleware (see middleware.py / asgi.py)
  2. Verifying scope["user"].id matches the requested user_id

ADDED:
  - Send unread count on connect so the client can badge immediately
  - mark_read event: client can mark a notification read via WebSocket
  - rate limiting on incoming messages
"""

import json
import logging
from channels.generic.websocket import AsyncWebsocketConsumer
from asgiref.sync import sync_to_async

from .models import Notification
from .rate_limit import is_rate_limited

logger = logging.getLogger(__name__)


class NotificationConsumer(AsyncWebsocketConsumer):

    async def connect(self):
        self.requested_user_id = self.scope["url_route"]["kwargs"]["user_id"]
        user = self.scope.get("user")

        # Authentication + authorisation guard
        if not user or not user.is_authenticated:
            await self.close(code=4001)
            return

        # Users may only subscribe to their own notification stream
        if str(user.id) != str(self.requested_user_id):
            await self.close(code=4003)
            return

        self.user_id = str(user.id)
        self.group_name = f"user_{self.user_id}"

        await self.channel_layer.group_add(self.group_name, self.channel_name)
        await self.accept()

        # Send unread count immediately on connect
        unread_count = await self._get_unread_count()
        await self.send(text_data=json.dumps({
            "type": "unread_count",
            "count": unread_count,
        }))

    async def disconnect(self, close_code):
        if hasattr(self, "group_name"):
            await self.channel_layer.group_discard(self.group_name, self.channel_name)

    async def receive(self, text_data):
        try:
            data = json.loads(text_data)
        except (json.JSONDecodeError, ValueError):
            await self._send_error("Invalid JSON.")
            return

        user = self.scope.get("user")
        if not user or not user.is_authenticated:
            await self.close(code=4001)
            return

        # Rate-limit incoming messages (e.g. rapid mark-read spam)
        if is_rate_limited(self.user_id, limit=20, window=60):
            await self._send_error("Too many requests.")
            return

        event_type = data.get("type")

        if event_type == "mark_read":
            notification_id = data.get("notification_id")
            if notification_id:
                await self._mark_notification_read(notification_id)
            else:
                # Mark all read
                await self._mark_all_read()

        elif event_type == "heartbeat":
            await self.send(text_data=json.dumps({"type": "heartbeat_ack"}))

        else:
            await self._send_error(f"Unknown event type: {event_type!r}")

    # ------------------------------------------------------------------ #
    # Outgoing (channel-layer → client)                                   #
    # ------------------------------------------------------------------ #

    async def send_notification(self, event):
        """Receive from channel layer and forward to WebSocket client."""
        await self.send(text_data=json.dumps(event["data"]))

    # ------------------------------------------------------------------ #
    # DB helpers                                                           #
    # ------------------------------------------------------------------ #

    @sync_to_async
    def _get_unread_count(self) -> int:
        return Notification.objects.filter(
            user_id=self.user_id, is_read=False
        ).count()

    @sync_to_async
    def _mark_notification_read(self, notification_id: str) -> None:
        try:
            notif = Notification.objects.get(id=notification_id, user_id=self.user_id)
            notif.mark_as_read()
        except Notification.DoesNotExist:
            pass

    @sync_to_async
    def _mark_all_read(self) -> None:
        from django.utils import timezone
        Notification.objects.filter(
            user_id=self.user_id, is_read=False
        ).update(is_read=True, read_at=timezone.now())

    async def _send_error(self, detail: str) -> None:
        await self.send(text_data=json.dumps({"type": "error", "detail": detail}))