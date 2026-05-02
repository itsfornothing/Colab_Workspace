from django.core.cache import cache

# Presence TTL: slightly longer than the client heartbeat interval (30s)
# so a single missed ping doesn't flip the user offline.
ONLINE_TTL = 90  # seconds


def set_user_online(user_id: int) -> None:
    """Mark user as online (or refresh their TTL)."""
    cache.set(f"user_online_{user_id}", True, timeout=ONLINE_TTL)


def set_user_offline(user_id: int) -> None:
    """Explicitly mark user as offline (called on WebSocket disconnect)."""
    cache.delete(f"user_online_{user_id}")


def is_user_online(user_id: int) -> bool:
    """Return True if the user has an active presence record in Redis."""
    return cache.get(f"user_online_{user_id}") is not None


def get_online_users(user_ids: list[int]) -> list[int]:
    """
    Bulk-check presence for a list of user IDs.
    Returns only those who are currently online.
    Efficient: uses a single Redis pipeline via cache.get_many.
    """
    keys = {uid: f"user_online_{uid}" for uid in user_ids}
    found = cache.get_many(list(keys.values()))
    return [uid for uid, key in keys.items() if key in found]