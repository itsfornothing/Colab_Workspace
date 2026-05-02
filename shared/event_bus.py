"""
shared/event_bus.py
Redis Pub/Sub event bus for service-to-service communication.

Instead of direct HTTP calls between services (tight coupling),
services publish events to Redis channels and other services subscribe.

Pattern:
  Publisher  →  redis.publish("user.profile_updated", json_payload)
  Subscriber →  listens on that channel and reacts

Full Event Catalogue
--------------------
user.registered              {user_id, email}
user.profile_updated         {user_id, profile_picture, job_title}
user.deactivated             {user_id}

workspace.created            {workspace_id, owner_id, name}
workspace.member_joined      {workspace_id, user_id, role}
workspace.member_removed     {workspace_id, user_id}
workspace.member_role_changed{workspace_id, user_id, old_role, new_role}

chat.message_created         {channel_id, sender_id, message, workspace_id}
chat.message_deleted         {channel_id, message_id}

notification.send            {user_id, title, content, type, priority}

Usage — publishing (call from any Django view, signal, or service function):
    from collab_shared.event_bus import publish_event
    publish_event("user.profile_updated", {"user_id": str(user.id), ...})

Usage — subscribing (start in AppConfig.ready() as a daemon thread):
    from collab_shared.event_bus import EventBusSubscriber
    sub = EventBusSubscriber(handlers={
        "user.profile_updated": handle_profile_update,
    })
    sub.start()
"""

import json
import logging
import threading
from typing import Callable, Dict

import redis
from django.conf import settings

logger = logging.getLogger(__name__)

# Uses Redis DB 4 — separate from cache (1), channels (3), celery (0/2)
_REDIS_URL = getattr(settings, "REDIS_EVENT_BUS_URL", "redis://redis:6379/4")

HandlerMap = Dict[str, Callable[[dict], None]]


def _get_client() -> redis.Redis:
    return redis.Redis.from_url(_REDIS_URL, decode_responses=True)


# ------------------------------------------------------------------ #
# Publishing                                                           #
# ------------------------------------------------------------------ #

def publish_event(event_type: str, payload: dict) -> None:
    """
    Publish an event to all subscribers.
    Fire-and-forget — does NOT wait for consumers to finish.
    Safe to call from synchronous Django views and Celery tasks.
    """
    client = _get_client()
    message = json.dumps({"type": event_type, "payload": payload})
    try:
        client.publish(event_type, message)
        logger.debug("Published event %s: %s", event_type, payload)
    except Exception:
        logger.exception("Failed to publish event %s", event_type)
    finally:
        client.close()


# ------------------------------------------------------------------ #
# Subscribing                                                          #
# ------------------------------------------------------------------ #

class EventBusSubscriber:
    """
    Subscribes to Redis pub/sub channels and dispatches
    incoming events to registered handler functions.

    Runs in its own daemon thread — does not block the main process.

    Example:
        sub = EventBusSubscriber(handlers={
            "user.profile_updated": on_profile_updated,
            "workspace.member_removed": on_member_removed,
        })
        sub.start()   # non-blocking, runs in background
    """

    def __init__(self, handlers: HandlerMap, channels: list = None):
        self.handlers = handlers
        # Subscribe to every key in handlers unless explicit list given
        self.channels = channels or list(handlers.keys())
        self._thread  = None
        self._stop    = threading.Event()

    def start(self) -> None:
        """Start the subscriber loop in a background daemon thread."""
        self._thread = threading.Thread(
            target=self._run,
            daemon=True,
            name=f"EventBus-{'-'.join(self.channels[:2])}",
        )
        self._thread.start()
        logger.info(
            "EventBusSubscriber started on channels: %s", self.channels
        )

    def stop(self) -> None:
        self._stop.set()

    def _run(self) -> None:
        client = _get_client()
        pubsub = client.pubsub()
        pubsub.subscribe(*self.channels)

        for raw_message in pubsub.listen():
            if self._stop.is_set():
                break

            if raw_message["type"] != "message":
                continue

            try:
                data       = json.loads(raw_message["data"])
                event_type = data.get("type", raw_message["channel"])
                handler    = self.handlers.get(event_type)

                if handler:
                    handler(data.get("payload", {}))
                else:
                    logger.debug(
                        "No handler for event type: %s", event_type
                    )
            except Exception:
                logger.exception(
                    "Error handling event from channel %s",
                    raw_message.get("channel"),
                )

        pubsub.close()
        client.close()


# ------------------------------------------------------------------ #
# Django management command mixin                                      #
# ------------------------------------------------------------------ #

class EventConsumerCommand:
    """
    Mixin for Django management commands that run an event subscriber.

    Usage:
        from django.core.management.base import BaseCommand
        from collab_shared.event_bus import EventConsumerCommand

        class Command(EventConsumerCommand, BaseCommand):
            HANDLERS = {
                "user.profile_updated": handle_profile_update,
            }
            help = "Listen for user profile update events"
    """
    HANDLERS: HandlerMap = {}

    def handle(self, *args, **options):
        logger.info(
            "%s starting event bus subscriber...",
            self.__class__.__name__,
        )
        sub = EventBusSubscriber(handlers=self.HANDLERS)
        sub.start()
        sub._thread.join()   # block the management command until killed