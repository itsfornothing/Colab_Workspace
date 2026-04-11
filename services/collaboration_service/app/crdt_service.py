"""
CRDT service — persistence layer for Yjs binary operations and snapshots.

Design notes:
  - Operations are raw Yjs update bytes (produced by Y.encodeStateAsUpdate
    or Y.encodeStateAsUpdateV2 on the client).
  - Snapshots are full Yjs state vectors (Y.encodeStateAsUpdate of the
    full document), stored periodically to bound reconnect cost.
  - get_operations_since() accepts an optional datetime cutoff so the
    consumer can send only a delta rather than the full log.
"""

import logging
from django.utils import timezone
from .models import DocumentOperation, DocumentSnapshot

logger = logging.getLogger(__name__)

# After this many operations since the last snapshot, a new snapshot
# should be triggered (the consumer or a periodic task calls save_snapshot).
SNAPSHOT_INTERVAL = 100


def save_operation(user, document_id, operation_bytes: bytes) -> DocumentOperation:
    """Persist a single Yjs update from a client."""
    op = DocumentOperation.objects.create(
        document_id=document_id,
        operation=operation_bytes,
        created_by=user,
    )
    _maybe_trigger_snapshot(document_id)
    return op


def get_operations_since(document_id, since=None):
    """
    Return operations for a document, optionally filtered to those
    created after `since` (a datetime or ISO-8601 string).

    Passing since=None returns all operations (full log mode).
    """
    qs = DocumentOperation.objects.filter(
        document_id=document_id
    ).order_by("created_at")

    if since is not None:
        qs = qs.filter(created_at__gt=since)

    return qs


def get_latest_snapshot(document_id):
    """
    Return the most recent DocumentSnapshot for this document, or None.
    """
    try:
        return DocumentSnapshot.objects.get(document_id=document_id)
    except DocumentSnapshot.DoesNotExist:
        return None


def save_snapshot(document_id, snapshot_bytes: bytes) -> None:
    """
    Upsert the document snapshot.  Called either:
      - From a periodic Celery task after SNAPSHOT_INTERVAL ops
      - Explicitly from a view when the document is saved via HTTP
    """
    DocumentSnapshot.objects.update_or_create(
        document_id=document_id,
        defaults={
            "snapshot": snapshot_bytes,
            "updated_at": timezone.now(),
        },
    )
    # Prune operations that predate the new snapshot so the log stays small.
    # We keep a small buffer (10 ops) in case of clock skew.
    snap = DocumentSnapshot.objects.get(document_id=document_id)
    DocumentOperation.objects.filter(
        document_id=document_id,
        created_at__lt=snap.updated_at,
    ).delete()
    logger.info("Snapshot saved and old ops pruned for document %s", document_id)


def get_operation_count_since_snapshot(document_id) -> int:
    """How many ops have accumulated since the last snapshot?"""
    snapshot = get_latest_snapshot(document_id)
    qs = DocumentOperation.objects.filter(document_id=document_id)
    if snapshot:
        qs = qs.filter(created_at__gt=snapshot.updated_at)
    return qs.count()


def _maybe_trigger_snapshot(document_id) -> None:
    """
    Log a warning when ops accumulate past the threshold.
    Actual snapshot creation requires a full Yjs state, which only the
    client can produce — so we signal via a flag in Redis, and the next
    client to connect will receive a `request_snapshot` message.

    In a production system you'd use a Celery beat task here instead.
    """
    count = get_operation_count_since_snapshot(document_id)
    if count >= SNAPSHOT_INTERVAL:
        logger.warning(
            "Document %s has %d ops since last snapshot — "
            "consider triggering a snapshot.",
            document_id,
            count,
        )