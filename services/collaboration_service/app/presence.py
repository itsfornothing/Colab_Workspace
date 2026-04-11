"""
Presence service — tracks which users are actively editing a document.

Uses Redis via Django's cache framework.

BUG FIX: The original get_active_users() called cache.keys() which is:
  1. Not supported by all Django cache backends (django-redis supports it,
     but the default LocMemCache does not — silent failure in tests/dev).
  2. A full Redis keyspace scan (KEYS command) — O(N) and dangerous in
     production with a large keyspace.

Replacement strategy: maintain a Redis Set per document containing the
active user IDs. Set membership operations are O(1) and atomic.
"""

from django.core.cache import cache

# How long (seconds) a presence entry lives without a heartbeat refresh.
# Slightly longer than the client heartbeat interval (30 s) so one missed
# ping doesn't flip the user offline.
PRESENCE_TTL = 90


def _set_key(doc_id) -> str:
    return f"doc_presence:{doc_id}"


def set_user_active(doc_id, user_id) -> None:
    """Add user to the document's active set and refresh the set TTL."""
    key = _set_key(doc_id)
    # sadd is atomic; we then reset the TTL on the whole set.
    cache.client.get_client().sadd(key, str(user_id))
    cache.client.get_client().expire(key, PRESENCE_TTL)


def remove_user_active(doc_id, user_id) -> None:
    """Remove user from the document's active set on disconnect."""
    key = _set_key(doc_id)
    cache.client.get_client().srem(key, str(user_id))


def get_active_users(doc_id) -> list:
    """Return list of user ID strings currently active on this document."""
    key = _set_key(doc_id)
    members = cache.client.get_client().smembers(key)
    # smembers returns bytes in most redis-py versions
    return [m.decode() if isinstance(m, bytes) else m for m in members]


def is_user_active(doc_id, user_id) -> bool:
    key = _set_key(doc_id)
    return cache.client.get_client().sismember(key, str(user_id))