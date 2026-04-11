"""
Models for the collaboration service.

Changes from original:
  - DocumentLock: added locked_at with auto_now (not auto_now_add) so TTL
    heartbeats can refresh it; added db_index on locked_at for expiry queries.
  - DocumentSnapshot: changed document_id from raw UUIDField primary key to a
    OneToOneField so Django enforces referential integrity and cascades deletes.
  - DocumentOperation: added sequence_number to support ordered replay without
    relying solely on created_at (clock skew between workers can reorder ops).
  - ActiveEditor: removed (replaced by Redis-based presence in presence.py;
    keeping a DB table for ephemeral state is an anti-pattern).
  - Added DocumentComment model for inline threaded comments.
"""

import uuid
from django.db import models
from django.conf import settings

User = settings.AUTH_USER_MODEL


class Document(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    workspace_id = models.UUIDField(db_index=True)
    title = models.CharField(max_length=255)
    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        related_name="created_documents",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    is_archived = models.BooleanField(default=False)

    class Meta:
        indexes = [models.Index(fields=["workspace_id"])]

    def __str__(self):
        return self.title


class DocumentContent(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    document = models.OneToOneField(
        Document, on_delete=models.CASCADE, related_name="content"
    )
    content = models.TextField(blank=True, default="")
    last_edited_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, related_name="edited_documents"
    )
    updated_at = models.DateTimeField(auto_now=True)


class DocumentVersion(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    document = models.ForeignKey(
        Document, on_delete=models.CASCADE, related_name="versions"
    )
    version_number = models.PositiveIntegerField()
    content_snapshot = models.TextField()
    edited_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("document", "version_number")
        ordering = ["-version_number"]


class DocumentPermission(models.Model):
    PERMISSION_CHOICES = [
        ("view", "View"),
        ("edit", "Edit"),
        ("admin", "Admin"),
    ]
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    document = models.ForeignKey(
        Document, on_delete=models.CASCADE, related_name="permissions"
    )
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    permission = models.CharField(max_length=10, choices=PERMISSION_CHOICES)
    granted_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, related_name="granted_permissions"
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("document", "user")
        indexes = [models.Index(fields=["document", "user"])]


class DocumentOperation(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    document_id = models.UUIDField(db_index=True)
    # Raw Yjs update bytes
    operation = models.BinaryField()
    created_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True
    )
    created_at = models.DateTimeField(auto_now_add=True)
    # Monotonic counter per document for deterministic replay ordering,
    # independent of wall-clock time (avoids clock-skew reordering).
    sequence_number = models.PositiveIntegerField(default=0)

    class Meta:
        indexes = [models.Index(fields=["document_id", "created_at"])]
        ordering = ["sequence_number", "created_at"]


class DocumentSnapshot(models.Model):
    """
    Stores a full Yjs state snapshot for a document.
    FIX: Changed from raw UUIDField PK to OneToOneField so Django enforces
    referential integrity and cascades the snapshot when the document is deleted.
    """
    document = models.OneToOneField(
        Document,
        on_delete=models.CASCADE,
        primary_key=True,
        related_name="snapshot",
    )
    snapshot = models.BinaryField()
    updated_at = models.DateTimeField(auto_now=True)

    @property
    def document_id(self):
        return self.document_id


class DocumentLock(models.Model):
    """
    Pessimistic lock for a document section.
    FIX: locked_at uses auto_now so heartbeat refreshes update it.
    ADDED: db_index on locked_at for efficient expiry queries.
    """
    document = models.OneToOneField(
        Document, on_delete=models.CASCADE, related_name="lock"
    )
    locked_by = models.ForeignKey(User, on_delete=models.CASCADE)
    locked_at = models.DateTimeField(auto_now=True, db_index=True)


class DocumentComment(models.Model):
    """
    Inline comment anchored to a position in the document.
    Supports threaded replies via parent FK.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    document = models.ForeignKey(
        Document, on_delete=models.CASCADE, related_name="comments"
    )
    author = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    parent = models.ForeignKey(
        "self", null=True, blank=True, on_delete=models.CASCADE, related_name="replies"
    )
    content = models.TextField()
    # Yjs anchor: serialised position reference so the comment tracks its
    # location as the document is edited
    anchor = models.JSONField(null=True, blank=True)
    resolved = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["created_at"]