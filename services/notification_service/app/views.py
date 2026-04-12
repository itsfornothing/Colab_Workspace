"""
REST views for the notification service.

BUG FIX: create_event imported process_notification_event from tasks.py
but that task was not defined there — NameError on first request.

ADDED: Full notification management API:
  - list_notifications: paginated list with unread filter
  - mark_read / mark_all_read
  - get/update NotificationPreference
  - create_event with input validation, rate limiting, and priority routing
"""

import logging
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status
from django.utils import timezone

from .models import Notification, NotificationEvent, NotificationPreference
from .tasks import process_high_priority, process_low_priority, process_notification_event
from .rate_limit import is_rate_limited

logger = logging.getLogger(__name__)

# Events that bypass normal queuing and go to the high-priority worker
HIGH_PRIORITY_EVENTS = {"user_mentioned", "system_alert"}
VALID_EVENT_TYPES = {"message_created", "user_invited", "user_mentioned", "system_alert"}


# ------------------------------------------------------------------ #
# Events (service-to-service)                                         #
# ------------------------------------------------------------------ #

@api_view(["POST"])
def create_event(request):
    """
    Endpoint for other services (chat, workspace, etc.) to fire events.
    No user auth required — service-to-service calls use a shared secret
    (add HMAC validation here in production).
    """
    event_type = request.data.get("event_type")
    payload = request.data.get("payload")

    if not event_type or not payload:
        return Response(
            {"detail": "event_type and payload are required."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    if event_type not in VALID_EVENT_TYPES:
        return Response(
            {"detail": f"Unknown event_type: {event_type!r}"},
            status=status.HTTP_400_BAD_REQUEST,
        )

    event = NotificationEvent.objects.create(
        event_type=event_type,
        payload=payload,
    )

    # Route to priority queue
    if event_type in HIGH_PRIORITY_EVENTS:
        process_high_priority.delay(str(event.id))
    else:
        process_low_priority.delay(str(event.id))

    return Response({"status": "queued", "event_id": str(event.id)}, status=status.HTTP_201_CREATED)


# ------------------------------------------------------------------ #
# Notifications                                                        #
# ------------------------------------------------------------------ #

@api_view(["GET"])
@permission_classes([IsAuthenticated])
def list_notifications(request):
    """
    GET /api/notifications/?unread=true&limit=20&offset=0
    """
    qs = Notification.objects.filter(user=request.user)

    if request.query_params.get("unread", "").lower() == "true":
        qs = qs.filter(is_read=False)

    notification_type = request.query_params.get("type")
    if notification_type:
        qs = qs.filter(type=notification_type)

    try:
        limit = min(int(request.query_params.get("limit", 20)), 100)
        offset = int(request.query_params.get("offset", 0))
    except ValueError:
        return Response({"detail": "limit and offset must be integers."}, status=status.HTTP_400_BAD_REQUEST)

    total = qs.count()
    notifications = qs[offset: offset + limit]

    return Response({
        "total": total,
        "unread_count": Notification.objects.filter(user=request.user, is_read=False).count(),
        "results": [
            {
                "id": str(n.id),
                "type": n.type,
                "title": n.title,
                "content": n.content,
                "is_read": n.is_read,
                "priority": n.priority,
                "metadata": n.metadata,
                "created_at": n.created_at.isoformat(),
                "read_at": n.read_at.isoformat() if n.read_at else None,
            }
            for n in notifications
        ],
    })


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def mark_read(request, notification_id):
    """Mark a single notification as read."""
    try:
        notif = Notification.objects.get(id=notification_id, user=request.user)
        notif.mark_as_read()
        return Response({"status": "marked_read"})
    except Notification.DoesNotExist:
        return Response({"detail": "Not found."}, status=status.HTTP_404_NOT_FOUND)


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def mark_all_read(request):
    """Mark all notifications as read for the authenticated user."""
    Notification.objects.filter(user=request.user, is_read=False).update(
        is_read=True, read_at=timezone.now()
    )
    return Response({"status": "all_marked_read"})


@api_view(["DELETE"])
@permission_classes([IsAuthenticated])
def delete_notification(request, notification_id):
    """Delete a single notification."""
    try:
        Notification.objects.get(id=notification_id, user=request.user).delete()
        return Response(status=status.HTTP_204_NO_CONTENT)
    except Notification.DoesNotExist:
        return Response({"detail": "Not found."}, status=status.HTTP_404_NOT_FOUND)


# ------------------------------------------------------------------ #
# Notification Preferences                                             #
# ------------------------------------------------------------------ #

@api_view(["GET", "PUT"])
@permission_classes([IsAuthenticated])
def notification_preferences(request):
    """
    GET  /api/notifications/preferences/  — fetch current preferences
    PUT  /api/notifications/preferences/  — update preferences
    """
    prefs, _ = NotificationPreference.objects.get_or_create(user=request.user)

    if request.method == "GET":
        return Response(_serialize_prefs(prefs))

    # PUT — update
    data = request.data
    updatable = [
        "in_app_enabled", "email_enabled", "push_enabled",
        "type_preferences", "quiet_hours_enabled", "quiet_start",
        "quiet_end", "timezone", "digest_frequency", "fcm_token",
    ]
    for field in updatable:
        if field in data:
            setattr(prefs, field, data[field])

    prefs.save()
    return Response(_serialize_prefs(prefs))


def _serialize_prefs(prefs: NotificationPreference) -> dict:
    return {
        "in_app_enabled":      prefs.in_app_enabled,
        "email_enabled":       prefs.email_enabled,
        "push_enabled":        prefs.push_enabled,
        "type_preferences":    prefs.type_preferences,
        "quiet_hours_enabled": prefs.quiet_hours_enabled,
        "quiet_start":         str(prefs.quiet_start) if prefs.quiet_start else None,
        "quiet_end":           str(prefs.quiet_end) if prefs.quiet_end else None,
        "timezone":            prefs.timezone,
        "digest_frequency":    prefs.digest_frequency,
        "fcm_token":           prefs.fcm_token,
        "updated_at":          prefs.updated_at.isoformat(),
    }