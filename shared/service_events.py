"""
shared/service_events.py
Concrete event handlers — what each service does when it receives
an event from the bus.

Start the appropriate subscriber in each service's AppConfig.ready():

    # services/chat-service/app/apps.py
    from django.apps import AppConfig

    class AppConfig(AppConfig):
        name = "app"
        def ready(self):
            from collab_shared.service_events import get_chat_service_subscriber
            get_chat_service_subscriber().start()

    # services/notification-service/app/apps.py
    class AppConfig(AppConfig):
        name = "app"
        def ready(self):
            from collab_shared.service_events import get_notification_service_subscriber
            get_notification_service_subscriber().start()
"""

import logging
from django.core.cache import cache

logger = logging.getLogger(__name__)


# ------------------------------------------------------------------ #
# Handlers — what CHAT SERVICE does when it receives events           #
# ------------------------------------------------------------------ #

def on_profile_updated(payload: dict) -> None:
    """
    Invalidate cached profile data so chat avatars update immediately.
    Triggered by: user.profile_updated
    """
    user_id = payload.get("user_id")
    if not user_id:
        return

    cache.delete(f"profile:{user_id}")
    cache.delete(f"public_profile:{user_id}")
    logger.info(
        "Profile cache invalidated for user %s (profile_updated event)",
        user_id,
    )


def on_user_deactivated(payload: dict) -> None:
    """
    Force-disconnect any open WebSocket connections when a user is
    deactivated. Triggered by: user.deactivated
    """
    user_id = payload.get("user_id")
    if not user_id:
        return

    from channels.layers import get_channel_layer
    from asgiref.sync import async_to_sync

    layer = get_channel_layer()
    try:
        async_to_sync(layer.group_send)(
            f"user_{user_id}",
            {
                "type":   "force_disconnect",
                "reason": "account_deactivated",
            },
        )
        logger.info("Force-disconnected user %s (deactivated)", user_id)
    except Exception:
        logger.exception(
            "Failed to force-disconnect user %s", user_id
        )


def on_workspace_member_removed(payload: dict) -> None:
    """
    Evict RBAC and workspace membership caches when a member is removed.
    Triggered by: workspace.member_removed
    """
    user_id      = payload.get("user_id")
    workspace_id = payload.get("workspace_id")

    if user_id and workspace_id:
        cache.delete(f"rbac:{user_id}:{workspace_id}")
        cache.delete(f"user_workspaces_{user_id}")
        logger.info(
            "RBAC cache cleared for user %s workspace %s",
            user_id, workspace_id,
        )


def on_workspace_role_changed(payload: dict) -> None:
    """
    Evict RBAC cache when a member's role changes.
    Triggered by: workspace.member_role_changed
    """
    user_id      = payload.get("user_id")
    workspace_id = payload.get("workspace_id")

    if user_id and workspace_id:
        cache.delete(f"rbac:{user_id}:{workspace_id}")
        logger.info(
            "RBAC cache cleared after role change for user %s workspace %s",
            user_id, workspace_id,
        )


# ------------------------------------------------------------------ #
# Handlers — what NOTIFICATION SERVICE does when it receives events   #
# ------------------------------------------------------------------ #

def on_notification_send(payload: dict) -> None:
    """
    Receive a cross-service notification request and dispatch it.
    Triggered by: notification.send
    Called by: chat_service, workspace_service, media_service

    Expected payload keys:
        user_id  (str)       — recipient
        title    (str)
        content  (str)
        type     (str)       — message | invite | mention | system
        priority (str)       — low | medium | high
    """
    try:
        from services.notification_service.app.models import NotificationEvent
        from services.notification_service.app.tasks import process_notification_event

        event = NotificationEvent.objects.create(
            event_type=payload.get("type", "system_alert"),
            payload=payload,
        )
        process_notification_event.delay(str(event.id))
        logger.info(
            "Notification event %s queued from event bus", event.id
        )
    except Exception:
        logger.exception(
            "Failed to enqueue notification from event bus: %s", payload
        )


# ------------------------------------------------------------------ #
# Handlers — what USER SERVICE does when it receives events           #
# ------------------------------------------------------------------ #

def on_workspace_created(payload: dict) -> None:
    """
    Log or react when a new workspace is created.
    Triggered by: workspace.created
    """
    logger.info(
        "New workspace created: %s by owner %s",
        payload.get("workspace_id"),
        payload.get("owner_id"),
    )


# ------------------------------------------------------------------ #
# Subscriber factory functions                                         #
# Call these in each service's AppConfig.ready()                      #
# ------------------------------------------------------------------ #

def get_chat_service_subscriber():
    """Returns the EventBusSubscriber for the chat service."""
    from event_bus import EventBusSubscriber
    return EventBusSubscriber(handlers={
        "user.profile_updated":           on_profile_updated,
        "user.deactivated":               on_user_deactivated,
        "workspace.member_removed":       on_workspace_member_removed,
        "workspace.member_role_changed":  on_workspace_role_changed,
    })


def get_workspace_service_subscriber():
    """Returns the EventBusSubscriber for the workspace service."""
    from event_bus import EventBusSubscriber
    return EventBusSubscriber(handlers={
        "user.profile_updated": on_profile_updated,
        "user.deactivated":     on_user_deactivated,
    })


def get_notification_service_subscriber():
    """Returns the EventBusSubscriber for the notification service."""
    from event_bus import EventBusSubscriber
    return EventBusSubscriber(handlers={
        "notification.send": on_notification_send,
    })


def get_user_service_subscriber():
    """Returns the EventBusSubscriber for the user service."""
    from event_bus import EventBusSubscriber
    return EventBusSubscriber(handlers={
        "workspace.created": on_workspace_created,
    })