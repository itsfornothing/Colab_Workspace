"""
Models for the notification service.

Changes / additions vs original:
  - Notification.mark_as_read(): fixed — used models.functions.Now() which
    requires an import from django.db.models.functions. Replaced with
    timezone.now() which is always available and works correctly.
  - NotificationPreference: NEW — per-user channel and type opt-in/out,
    quiet hours, and digest frequency.
  - DigestLog: NEW — tracks which digest emails have been sent so we never
    send duplicates on retry.
  - NotificationBatch: added batch_type field to distinguish real-time
    batches from digest batches.
  - All models: consistent UUID PKs, meaningful related_names.
"""

import uuid
from django.db import models
from django.conf import settings
from django.utils import timezone

User = settings.AUTH_USER_MODEL


class Notification(models.Model):
    NOTIFICATION_TYPES = [
        ("message", "Message"),
        ("invite", "Invite"),
        ("mention", "Mention"),
        ("system", "System"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name="notifications", db_index=True
    )
    type = models.CharField(max_length=20, choices=NOTIFICATION_TYPES)
    title = models.CharField(max_length=255)
    content = models.TextField()
    is_read = models.BooleanField(default=False, db_index=True)
    is_sent = models.BooleanField(default=False)
    priority = models.CharField(
        max_length=10,
        choices=[("low", "Low"), ("medium", "Medium"), ("high", "High")],
        default="medium",
    )
    metadata = models.JSONField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    read_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["user", "is_read"]),
            models.Index(fields=["user", "is_sent"]),
            models.Index(fields=["type"]),
        ]

    def mark_as_read(self):
        # BUG FIX: original used models.functions.Now() without importing it.
        # timezone.now() is simpler and always correct.
        if not self.is_read:
            self.is_read = True
            self.read_at = timezone.now()
            self.save(update_fields=["is_read", "read_at"])


class NotificationEvent(models.Model):
    EVENT_TYPES = [
        ("message_created", "Message Created"),
        ("user_invited", "User Invited"),
        ("user_mentioned", "User Mentioned"),
        ("system_alert", "System Alert"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    event_type = models.CharField(max_length=50, choices=EVENT_TYPES, db_index=True)
    payload = models.JSONField()
    processed = models.BooleanField(default=False, db_index=True)
    retry_count = models.PositiveIntegerField(default=0)
    status = models.CharField(
        max_length=20,
        choices=[
            ("pending", "Pending"),
            ("processing", "Processing"),
            ("completed", "Completed"),
            ("failed", "Failed"),
        ],
        default="pending",
    )
    error_message = models.TextField(null=True, blank=True)
    scheduled_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    processed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["event_type", "processed"]),
            models.Index(fields=["status"]),
        ]


class NotificationDelivery(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    notification = models.ForeignKey(
        Notification, on_delete=models.CASCADE, related_name="deliveries"
    )
    channel = models.CharField(
        max_length=20,
        choices=[("in_app", "In App"), ("email", "Email"), ("push", "Push")],
    )
    status = models.CharField(
        max_length=20,
        choices=[("pending", "Pending"), ("sent", "Sent"), ("failed", "Failed")],
        default="pending",
    )
    response = models.JSONField(null=True, blank=True)
    sent_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [models.Index(fields=["notification", "channel"])]


class NotificationBatch(models.Model):
    BATCH_TYPES = [("realtime", "Real-time"), ("digest", "Digest")]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="batches")
    notifications = models.ManyToManyField(Notification, related_name="batches")
    batch_type = models.CharField(max_length=20, choices=BATCH_TYPES, default="realtime")
    created_at = models.DateTimeField(auto_now_add=True)
    sent = models.BooleanField(default=False)
    sent_at = models.DateTimeField(null=True, blank=True)


class NotificationPreference(models.Model):
    """
    Per-user preferences controlling which channels and types are enabled,
    quiet hours, and digest frequency.
    """
    DIGEST_CHOICES = [
        ("none", "No digest"),
        ("daily", "Daily digest"),
        ("weekly", "Weekly digest"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.OneToOneField(
        User, on_delete=models.CASCADE, related_name="notification_preferences"
    )

    # Channel opt-ins
    in_app_enabled = models.BooleanField(default=True)
    email_enabled = models.BooleanField(default=True)
    push_enabled = models.BooleanField(default=True)

    # Per-type opt-ins (JSON: {"message": true, "invite": true, ...})
    type_preferences = models.JSONField(
        default=dict,
        help_text='e.g. {"message": true, "invite": true, "mention": true, "system": true}',
    )

    # Quiet hours — notifications are queued, not delivered
    quiet_hours_enabled = models.BooleanField(default=False)
    quiet_start = models.TimeField(null=True, blank=True, help_text="Local time, e.g. 22:00")
    quiet_end = models.TimeField(null=True, blank=True, help_text="Local time, e.g. 08:00")
    timezone = models.CharField(max_length=64, default="UTC")

    # Digest
    digest_frequency = models.CharField(
        max_length=10, choices=DIGEST_CHOICES, default="none"
    )
    # FCM token for push notifications
    fcm_token = models.TextField(null=True, blank=True)

    updated_at = models.DateTimeField(auto_now=True)

    def is_type_enabled(self, notification_type: str) -> bool:
        """Return True if this notification type is enabled (default: True)."""
        return self.type_preferences.get(notification_type, True)

    def is_in_quiet_hours(self) -> bool:
        """Return True if current time falls within the user's quiet window."""
        if not self.quiet_hours_enabled or not self.quiet_start or not self.quiet_end:
            return False
        import pytz
        from datetime import datetime
        tz = pytz.timezone(self.timezone)
        now_local = datetime.now(tz).time()
        start = self.quiet_start
        end = self.quiet_end
        if start <= end:
            return start <= now_local < end
        # Spans midnight
        return now_local >= start or now_local < end


class DigestLog(models.Model):
    """
    Tracks sent digest emails so Celery retries never send duplicates.
    """
    DIGEST_TYPES = [("daily", "Daily"), ("weekly", "Weekly")]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="digest_logs")
    digest_type = models.CharField(max_length=10, choices=DIGEST_TYPES)
    period_start = models.DateTimeField()
    period_end = models.DateTimeField()
    notifications_count = models.PositiveIntegerField(default=0)
    sent_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("user", "digest_type", "period_start")
        indexes = [models.Index(fields=["user", "digest_type", "period_start"])]