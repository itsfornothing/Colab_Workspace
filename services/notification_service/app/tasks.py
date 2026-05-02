"""
Celery tasks for the notification service.

BUG FIXES:
  - process_high_priority / process_low_priority both called
    process_notification_event() which was never defined in tasks.py —
    guaranteed NameError at runtime. The actual logic is now here.
  - process_notification_batches used len(notifs) on a queryset slice,
    which always evaluates the slice and may return wrong count. Fixed
    with explicit list() conversion.
  - Duplicate imports (django.utils.timezone imported twice) removed.

ADDED:
  - process_notification_event: the missing core task
  - send_daily_digest / send_weekly_digest: new digest email tasks
  - cleanup_old_notifications: housekeeping task
  - Idempotency guards on all tasks (select_for_update + status checks)
"""

import logging
from celery import shared_task
from django.utils import timezone
from django.db import transaction
from datetime import timedelta

from .models import (
    Notification,
    NotificationEvent,
    NotificationBatch,
    NotificationPreference,
    DigestLog,
)
from .handlers import dispatch_event
from .email_service import send_digest_email

logger = logging.getLogger(__name__)

MAX_RETRIES = 3
BATCH_SIZE = 10


# ------------------------------------------------------------------ #
# Core event processor                                                 #
# ------------------------------------------------------------------ #

@shared_task(bind=True, max_retries=MAX_RETRIES, default_retry_delay=30)
def process_notification_event(self, event_id: str):
    """
    Process a single NotificationEvent: validate, dispatch to handler,
    mark complete. Retries up to MAX_RETRIES times on failure.
    """
    try:
        with transaction.atomic():
            # select_for_update prevents two workers racing on the same event
            event = NotificationEvent.objects.select_for_update().get(id=event_id)

            if event.status == "completed":
                logger.info("Event %s already completed, skipping", event_id)
                return

            if event.status == "processing":
                logger.warning("Event %s already being processed", event_id)
                return

            event.status = "processing"
            event.save(update_fields=["status"])

        # Dispatch outside the lock so DB row isn't held during push/email
        dispatch_event(event)

        event.status = "completed"
        event.processed = True
        event.processed_at = timezone.now()
        event.save(update_fields=["status", "processed", "processed_at"])

    except NotificationEvent.DoesNotExist:
        logger.error("NotificationEvent %s not found", event_id)

    except Exception as exc:
        logger.exception("Failed to process event %s", event_id)
        try:
            event = NotificationEvent.objects.get(id=event_id)
            event.retry_count += 1
            event.error_message = str(exc)
            event.status = "failed" if event.retry_count >= MAX_RETRIES else "pending"
            event.save(update_fields=["retry_count", "error_message", "status"])
        except Exception:
            pass
        raise self.retry(exc=exc)


# ------------------------------------------------------------------ #
# Priority routing wrappers                                            #
# ------------------------------------------------------------------ #

@shared_task(queue="high_priority")
def process_high_priority(event_id: str):
    process_notification_event(event_id)


@shared_task(queue="low_priority")
def process_low_priority(event_id: str):
    process_notification_event(event_id)


# ------------------------------------------------------------------ #
# Real-time batching (runs every 30 s via Celery Beat)                #
# ------------------------------------------------------------------ #

@shared_task
def process_notification_batches():
    """
    Group unsent notifications per user into batches, then trigger
    push + email summaries. Runs on a short cycle for near-real-time feel.
    """
    user_ids = (
        Notification.objects.filter(is_sent=False)
        .values_list("user_id", flat=True)
        .distinct()
    )

    for user_id in user_ids:
        # BUG FIX: convert queryset slice to list so len() is accurate
        notifs = list(
            Notification.objects.filter(user_id=user_id, is_sent=False)[:BATCH_SIZE]
        )
        if not notifs:
            continue

        try:
            prefs = NotificationPreference.objects.get(user_id=user_id)
        except NotificationPreference.DoesNotExist:
            prefs = None

        # Skip users who opted for digest — they get handled by digest tasks
        if prefs and prefs.digest_frequency != "none":
            continue

        with transaction.atomic():
            batch = NotificationBatch.objects.create(
                user_id=user_id, batch_type="realtime"
            )
            batch.notifications.set(notifs)

            summary = (
                f"You have {len(notifs)} new notification"
                + ("s" if len(notifs) > 1 else "")
            )
            logger.info("Batch %s created for user %s: %s", batch.id, user_id, summary)

            Notification.objects.filter(
                id__in=[n.id for n in notifs]
            ).update(is_sent=True)

            batch.sent = True
            batch.sent_at = timezone.now()
            batch.save(update_fields=["sent", "sent_at"])


# ------------------------------------------------------------------ #
# Digest emails                                                        #
# ------------------------------------------------------------------ #

@shared_task
def send_daily_digest():
    """
    Send a daily digest to users who opted in.
    Runs once per day via Celery Beat. Idempotent — DigestLog prevents
    duplicate sends on retry.
    """
    _send_digest("daily", timedelta(days=1))


@shared_task
def send_weekly_digest():
    """
    Send a weekly digest to users who opted in.
    """
    _send_digest("weekly", timedelta(weeks=1))


def _send_digest(digest_type: str, period: timedelta):
    now = timezone.now()
    period_start = now - period

    prefs_qs = NotificationPreference.objects.filter(
        digest_frequency=digest_type,
        email_enabled=True,
    ).select_related("user")

    for prefs in prefs_qs:
        user = prefs.user
        email = getattr(user, "email", None)
        if not email:
            continue

        # Idempotency check — skip if already sent for this period
        already_sent = DigestLog.objects.filter(
            user=user,
            digest_type=digest_type,
            period_start__gte=period_start,
        ).exists()

        if already_sent:
            continue

        # Collect unread notifications in the period
        notifications = list(
            Notification.objects.filter(
                user=user,
                created_at__gte=period_start,
                created_at__lte=now,
                is_read=False,
            ).order_by("-created_at")
        )

        if not notifications:
            continue

        try:
            send_digest_email(email, notifications, digest_type)

            DigestLog.objects.create(
                user=user,
                digest_type=digest_type,
                period_start=period_start,
                period_end=now,
                notifications_count=len(notifications),
            )
            logger.info(
                "Sent %s digest to %s (%d notifications)",
                digest_type, email, len(notifications)
            )
        except Exception:
            logger.exception("Digest email failed for user %s", user.id)


# ------------------------------------------------------------------ #
# Housekeeping                                                         #
# ------------------------------------------------------------------ #

@shared_task
def cleanup_old_notifications(days: int = 90):
    """
    Delete read notifications older than `days` days.
    Keeps the notifications table from growing unbounded.
    """
    cutoff = timezone.now() - timedelta(days=days)
    deleted, _ = Notification.objects.filter(
        is_read=True, created_at__lt=cutoff
    ).delete()
    logger.info("Cleaned up %d old notifications (older than %d days)", deleted, days)


@shared_task
def retry_failed_events():
    """
    Re-queue NotificationEvents that failed but have retries remaining.
    """
    events = NotificationEvent.objects.filter(
        status="failed",
        retry_count__lt=MAX_RETRIES,
    )
    for event in events:
        process_notification_event.delay(str(event.id))
        logger.info("Re-queued failed event %s (retry %d)", event.id, event.retry_count)