"""
Event handlers — translate raw NotificationEvent records into Notification
rows and trigger the correct delivery pipeline.

BUG FIX (critical): Original handlers.py executed two lines at module level
outside any function:

    channel_layer = get_channel_layer()
    async_to_sync(channel_layer.group_send)(
        f"user_{Notification.user_id}",   ← Notification is a class, not an instance
        ...
    )

This runs on import and crashes immediately with:
  AttributeError: type object 'Notification' has no attribute 'user_id' (class attr, not instance)
  And even if it didn't crash, it fires a WebSocket push to nobody on every import.

All delivery logic now lives inside functions and is only called explicitly.

ADDED: deliver_notification() — central dispatcher that checks user preferences
       before routing to in-app / push / email channels.
ADDED: push_to_websocket() — sends real-time WebSocket update after DB write.
"""

import logging
from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync
from django.utils import timezone

from .models import Notification, NotificationDelivery, NotificationPreference
from .firebase import send_push
from .email_service import send_notification_email
from .rate_limit import is_rate_limited

logger = logging.getLogger(__name__)


# ------------------------------------------------------------------ #
# WebSocket delivery                                                   #
# ------------------------------------------------------------------ #

def push_to_websocket(notification: Notification) -> None:
    """Push a real-time notification to the user's WebSocket group."""
    channel_layer = get_channel_layer()
    if not channel_layer:
        logger.warning("No channel layer configured — skipping WebSocket push")
        return

    try:
        async_to_sync(channel_layer.group_send)(
            f"user_{notification.user_id}",
            {
                "type": "send_notification",
                "data": {
                    "id": str(notification.id),
                    "title": notification.title,
                    "content": notification.content,
                    "notification_type": notification.type,
                    "priority": notification.priority,
                    "created_at": notification.created_at.isoformat(),
                    "metadata": notification.metadata,
                },
            },
        )
        _record_delivery(notification, "in_app", "sent")
    except Exception:
        logger.exception("WebSocket push failed for notification %s", notification.id)
        _record_delivery(notification, "in_app", "failed")


# ------------------------------------------------------------------ #
# Central delivery dispatcher                                          #
# ------------------------------------------------------------------ #

def deliver_notification(notification: Notification) -> None:
    """
    Route a notification through all channels the user has enabled,
    respecting preferences, quiet hours, and rate limits.
    """
    try:
        prefs = NotificationPreference.objects.get(user_id=notification.user_id)
    except NotificationPreference.DoesNotExist:
        # No prefs record — use all channels with defaults
        prefs = None

    # Rate-limit guard (applies to all channels)
    if is_rate_limited(str(notification.user_id)):
        logger.info("Rate limited: skipping delivery for user %s", notification.user_id)
        return

    # Check per-type opt-in
    if prefs and not prefs.is_type_enabled(notification.type):
        logger.info(
            "User %s has disabled %s notifications", notification.user_id, notification.type
        )
        return

    in_quiet = prefs.is_in_quiet_hours() if prefs else False

    # In-app (WebSocket) — always delivered unless in quiet hours for low priority
    if not prefs or prefs.in_app_enabled:
        if not (in_quiet and notification.priority == "low"):
            push_to_websocket(notification)

    # Push (FCM)
    if (not prefs or prefs.push_enabled) and not in_quiet:
        fcm_token = prefs.fcm_token if prefs else None
        if fcm_token:
            _deliver_push(notification, fcm_token)

    # Email — skip if user is in digest mode (digest task handles it)
    digest_freq = prefs.digest_frequency if prefs else "none"
    email_enabled = not prefs or prefs.email_enabled
    if email_enabled and digest_freq == "none" and not in_quiet:
        user = notification.user
        email = getattr(user, "email", None)
        if email:
            _deliver_email(notification, email)


# ------------------------------------------------------------------ #
# Channel-specific delivery helpers                                    #
# ------------------------------------------------------------------ #

def _deliver_push(notification: Notification, fcm_token: str) -> None:
    try:
        send_push(fcm_token, notification.title, notification.content)
        _record_delivery(notification, "push", "sent")
    except Exception:
        logger.exception("FCM push failed for notification %s", notification.id)
        _record_delivery(notification, "push", "failed")


def _deliver_email(notification: Notification, email: str) -> None:
    try:
        send_notification_email(email, notification.title, notification.content)
        _record_delivery(notification, "email", "sent")
    except Exception:
        logger.exception("Email delivery failed for notification %s", notification.id)
        _record_delivery(notification, "email", "failed")


def _record_delivery(notification: Notification, channel: str, status: str) -> None:
    NotificationDelivery.objects.update_or_create(
        notification=notification,
        channel=channel,
        defaults={"status": status, "sent_at": timezone.now() if status == "sent" else None},
    )


# ------------------------------------------------------------------ #
# Event → Notification factories                                       #
# ------------------------------------------------------------------ #

def handle_message_event(event) -> Notification:
    data = event.payload
    notif = Notification.objects.create(
        user_id=data["receiver_id"],
        type="message",
        title="New Message",
        content=data["message"],
        priority="medium",
        metadata={
            "sender_id": data["sender_id"],
            "channel_id": data.get("channel_id"),
        },
    )
    deliver_notification(notif)
    return notif


def handle_invite_event(event) -> Notification:
    data = event.payload
    notif = Notification.objects.create(
        user_id=data["user_id"],
        type="invite",
        title="Workspace Invitation",
        content=f"You were invited to {data['workspace_name']}",
        priority="high",
        metadata=data,
    )
    deliver_notification(notif)
    return notif


def handle_mention_event(event) -> Notification:
    data = event.payload
    notif = Notification.objects.create(
        user_id=data["user_id"],
        type="mention",
        title="You were mentioned",
        content=data["message"],
        priority="high",
        metadata=data,
    )
    deliver_notification(notif)
    return notif


def handle_system_alert_event(event) -> Notification:
    data = event.payload
    notif = Notification.objects.create(
        user_id=data["user_id"],
        type="system",
        title=data.get("title", "System Alert"),
        content=data.get("message", ""),
        priority=data.get("priority", "medium"),
        metadata=data,
    )
    deliver_notification(notif)
    return notif


# ------------------------------------------------------------------ #
# Router                                                               #
# ------------------------------------------------------------------ #

EVENT_HANDLERS = {
    "message_created": handle_message_event,
    "user_invited":    handle_invite_event,
    "user_mentioned":  handle_mention_event,
    "system_alert":    handle_system_alert_event,
}


def dispatch_event(event) -> None:
    """Route a NotificationEvent to its handler by event_type."""
    handler = EVENT_HANDLERS.get(event.event_type)
    if handler:
        handler(event)
    else:
        logger.warning("No handler registered for event type: %s", event.event_type)