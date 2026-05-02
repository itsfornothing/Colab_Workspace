"""
Lock service — optional pessimistic section locking for collaborative docs.

Note: For a pure CRDT/Yjs workflow, locks are rarely needed since CRDTs
handle concurrent edits automatically. This service exists for use cases
like "lock this section while I'm editing a table" or admin overrides.

BUG FIX: Original acquire_lock() used get_or_create without select_for_update,
creating a race condition: two concurrent callers could both read "not created"
and both believe they acquired the lock. Fixed with select_for_update inside
a transaction.

ADDED: TTL-based auto-expiry via locked_at timestamp so stale locks from
crashed clients don't block forever.
"""

import logging
from django.db import transaction
from django.utils import timezone
from datetime import timedelta
from .models import DocumentLock

logger = logging.getLogger(__name__)

# Lock expires after this many seconds of inactivity (client should heartbeat)
LOCK_TTL_SECONDS = 30


def acquire_lock(user, document_id) -> bool:
    """
    Try to acquire an exclusive lock for document_id.
    Returns True if the lock was acquired (or already owned by this user).
    Returns False if another user holds a valid lock.
    """
    expiry = timezone.now() - timedelta(seconds=LOCK_TTL_SECONDS)

    with transaction.atomic():
        # Try to get an existing lock with a row-level lock to avoid races
        try:
            lock = DocumentLock.objects.select_for_update().get(
                document_id=document_id
            )
        except DocumentLock.DoesNotExist:
            # No lock exists — create one for this user
            DocumentLock.objects.create(
                document_id=document_id,
                locked_by=user,
            )
            return True

        # If the existing lock has expired, take it over
        if lock.locked_at < expiry:
            lock.locked_by = user
            lock.locked_at = timezone.now()
            lock.save()
            logger.info(
                "Lock for document %s taken over from expired holder by %s",
                document_id, user
            )
            return True

        # Lock is held by someone else and still valid
        if lock.locked_by != user:
            return False

        # This user already owns the lock — refresh TTL
        lock.locked_at = timezone.now()
        lock.save()
        return True


def release_lock(user, document_id) -> None:
    """Release the lock if held by this user."""
    DocumentLock.objects.filter(
        document_id=document_id,
        locked_by=user,
    ).delete()


def get_lock_holder(document_id):
    """Return the User who holds the lock, or None if unlocked/expired."""
    expiry = timezone.now() - timedelta(seconds=LOCK_TTL_SECONDS)
    try:
        lock = DocumentLock.objects.select_related("locked_by").get(
            document_id=document_id,
            locked_at__gte=expiry,
        )
        return lock.locked_by
    except DocumentLock.DoesNotExist:
        return None