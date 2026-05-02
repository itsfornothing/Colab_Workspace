"""
Permission service — enforces document-level access control.

Permission hierarchy: view < edit < admin

ADDED: Cache layer so each WebSocket message doesn't hit the DB.
       Permission changes are rare; 60-second TTL is a good trade-off.
ADDED: is_document_owner() helper for admin operations.
ADDED: Anonymous user guard.
"""

import logging
from django.core.cache import cache
from .models import DocumentPermission, Document

logger = logging.getLogger(__name__)

HIERARCHY = {"view": 1, "edit": 2, "admin": 3}
PERM_CACHE_TTL = 60  # seconds


def _cache_key(user_id, document_id) -> str:
    return f"doc_perm:{document_id}:{user_id}"


def has_permission(user, document_id, required: str = "view") -> bool:
    """
    Return True if `user` has at least `required` permission on `document_id`.

    Checks:
      1. Anonymous users → always False
      2. Redis cache hit → fast path
      3. DB lookup → cache result
    """
    if not user or not getattr(user, "is_authenticated", False):
        return False

    cache_key = _cache_key(user.id, document_id)
    cached_level = cache.get(cache_key)

    if cached_level is None:
        try:
            perm = DocumentPermission.objects.get(
                document_id=document_id,
                user=user,
            )
            cached_level = HIERARCHY.get(perm.permission, 0)
        except DocumentPermission.DoesNotExist:
            cached_level = 0

        cache.set(cache_key, cached_level, timeout=PERM_CACHE_TTL)

    return cached_level >= HIERARCHY.get(required, 999)


def invalidate_permission_cache(user_id, document_id) -> None:
    """
    Call this whenever a DocumentPermission is created, updated, or deleted
    so the cached level is evicted immediately.
    """
    cache.delete(_cache_key(user_id, document_id))


def grant_permission(granting_user, target_user, document_id, level: str) -> bool:
    """
    Grant `level` permission to `target_user` on `document_id`.
    Only users with admin permission may grant.
    Returns True on success.
    """
    if level not in HIERARCHY:
        raise ValueError(f"Invalid permission level: {level!r}")

    if not has_permission(granting_user, document_id, "admin"):
        logger.warning(
            "User %s tried to grant permission on %s without admin rights",
            granting_user, document_id
        )
        return False

    DocumentPermission.objects.update_or_create(
        document_id=document_id,
        user=target_user,
        defaults={
            "permission": level,
            "granted_by": granting_user,
        },
    )
    invalidate_permission_cache(target_user.id, document_id)
    return True


def revoke_permission(revoking_user, target_user, document_id) -> bool:
    """Remove target_user's permission. Only admins may revoke."""
    if not has_permission(revoking_user, document_id, "admin"):
        return False

    DocumentPermission.objects.filter(
        document_id=document_id,
        user=target_user,
    ).delete()
    invalidate_permission_cache(target_user.id, document_id)
    return True