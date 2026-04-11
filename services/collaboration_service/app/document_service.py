"""
Document service — HTTP-layer CRUD for documents.

BUG FIX: update_document() used .count() to determine the next version
number. Under concurrent edits this produces duplicate version_number
values (two concurrent saves both read count=5, both try to insert
version_number=6 → IntegrityError). Fixed with select_for_update +
MAX aggregation inside the same transaction.

ADDED: Permission check before update so the HTTP endpoint respects the
       same access control as the WebSocket layer.
ADDED: get_document() and list_documents() for the REST views.
ADDED: archive_document() so documents aren't hard-deleted.
"""

import uuid
import logging
from django.db import transaction
from django.db.models import Max
from .models import Document, DocumentContent, DocumentVersion
from .permissions import has_permission

logger = logging.getLogger(__name__)


def create_document(user, workspace_id, title: str, content: str = "") -> Document:
    with transaction.atomic():
        doc = Document.objects.create(
            id=uuid.uuid4(),
            workspace_id=workspace_id,
            title=title,
            created_by=user,
        )

        DocumentContent.objects.create(
            document=doc,
            content=content,
            last_edited_by=user,
        )

        DocumentVersion.objects.create(
            document=doc,
            version_number=1,
            content_snapshot=content,
            edited_by=user,
        )

        # Grant the creator admin rights
        from .models import DocumentPermission
        DocumentPermission.objects.create(
            document=doc,
            user=user,
            permission="admin",
            granted_by=user,
        )

        logger.info("Document %s created by %s", doc.id, user)
        return doc


def update_document(user, document_id, new_content: str) -> DocumentContent:
    if not has_permission(user, document_id, "edit"):
        raise PermissionError(f"User {user} cannot edit document {document_id}")

    with transaction.atomic():
        content_obj = DocumentContent.objects.select_for_update().get(
            document_id=document_id
        )

        # BUG FIX: use MAX instead of COUNT to avoid duplicate version numbers
        # under concurrent writes.
        agg = DocumentVersion.objects.filter(
            document_id=document_id
        ).aggregate(max_ver=Max("version_number"))
        next_version = (agg["max_ver"] or 0) + 1

        DocumentVersion.objects.create(
            document_id=document_id,
            version_number=next_version,
            content_snapshot=new_content,
            edited_by=user,
        )

        content_obj.content = new_content
        content_obj.last_edited_by = user
        content_obj.save()

        return content_obj


def get_document(user, document_id) -> Document:
    if not has_permission(user, document_id, "view"):
        raise PermissionError(f"User {user} cannot view document {document_id}")
    return Document.objects.select_related("content").get(id=document_id)


def list_documents(user, workspace_id) -> list:
    """Return all non-archived documents in a workspace the user can view."""
    from .models import DocumentPermission
    permitted_ids = DocumentPermission.objects.filter(
        user=user
    ).values_list("document_id", flat=True)

    return Document.objects.filter(
        workspace_id=workspace_id,
        id__in=permitted_ids,
        is_archived=False,
    ).order_by("-updated_at")


def archive_document(user, document_id) -> None:
    if not has_permission(user, document_id, "admin"):
        raise PermissionError(f"User {user} cannot archive document {document_id}")
    Document.objects.filter(id=document_id).update(is_archived=True)


def restore_version(user, document_id, version_number: int) -> DocumentContent:
    """Roll back document content to a specific version snapshot."""
    if not has_permission(user, document_id, "admin"):
        raise PermissionError("Only admins can restore versions.")

    version = DocumentVersion.objects.get(
        document_id=document_id,
        version_number=version_number,
    )
    return update_document(user, document_id, version.content_snapshot)