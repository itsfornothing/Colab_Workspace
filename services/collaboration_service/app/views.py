"""
REST views for the collaboration service.

ADDED: Input validation, permission enforcement, proper error responses.
ADDED: get_document_view, list_documents_view, archive_document_view,
       restore_version_view, grant_permission_view for a complete API.
"""

import logging
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status

from .document_service import (
    create_document,
    update_document,
    get_document,
    list_documents,
    archive_document,
    restore_version,
)
from .permissions import grant_permission, revoke_permission
from .crdt_service import save_snapshot
from .lock_service import acquire_lock, release_lock, get_lock_holder

logger = logging.getLogger(__name__)


# ------------------------------------------------------------------ #
# Documents                                                           #
# ------------------------------------------------------------------ #

@api_view(["POST"])
@permission_classes([IsAuthenticated])
def create_document_view(request):
    workspace_id = request.data.get("workspace_id")
    title = request.data.get("title", "").strip()

    if not workspace_id or not title:
        return Response(
            {"detail": "workspace_id and title are required."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    try:
        doc = create_document(
            request.user,
            workspace_id,
            title,
            request.data.get("content", ""),
        )
        return Response({"document_id": str(doc.id)}, status=status.HTTP_201_CREATED)
    except Exception:
        logger.exception("create_document failed")
        return Response(
            {"detail": "Could not create document."},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def list_documents_view(request):
    workspace_id = request.query_params.get("workspace_id")
    if not workspace_id:
        return Response(
            {"detail": "workspace_id query param is required."},
            status=status.HTTP_400_BAD_REQUEST,
        )
    docs = list_documents(request.user, workspace_id)
    return Response([
        {"id": str(d.id), "title": d.title, "updated_at": d.updated_at}
        for d in docs
    ])


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def get_document_view(request, document_id):
    try:
        doc = get_document(request.user, document_id)
        return Response({
            "id": str(doc.id),
            "title": doc.title,
            "content": doc.content.content,
            "updated_at": doc.updated_at,
        })
    except PermissionError as e:
        return Response({"detail": str(e)}, status=status.HTTP_403_FORBIDDEN)
    except Exception:
        return Response({"detail": "Not found."}, status=status.HTTP_404_NOT_FOUND)


@api_view(["PUT"])
@permission_classes([IsAuthenticated])
def update_document_view(request, document_id):
    content = request.data.get("content")
    if content is None:
        return Response(
            {"detail": "content is required."},
            status=status.HTTP_400_BAD_REQUEST,
        )
    try:
        update_document(request.user, document_id, content)
        return Response({"status": "updated"})
    except PermissionError as e:
        return Response({"detail": str(e)}, status=status.HTTP_403_FORBIDDEN)
    except Exception:
        logger.exception("update_document failed for %s", document_id)
        return Response(
            {"detail": "Update failed."},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def archive_document_view(request, document_id):
    try:
        archive_document(request.user, document_id)
        return Response({"status": "archived"})
    except PermissionError as e:
        return Response({"detail": str(e)}, status=status.HTTP_403_FORBIDDEN)


# ------------------------------------------------------------------ #
# Versioning                                                          #
# ------------------------------------------------------------------ #

@api_view(["POST"])
@permission_classes([IsAuthenticated])
def restore_version_view(request, document_id):
    version_number = request.data.get("version_number")
    if not version_number:
        return Response(
            {"detail": "version_number is required."},
            status=status.HTTP_400_BAD_REQUEST,
        )
    try:
        restore_version(request.user, document_id, int(version_number))
        return Response({"status": "restored"})
    except PermissionError as e:
        return Response({"detail": str(e)}, status=status.HTTP_403_FORBIDDEN)


# ------------------------------------------------------------------ #
# Permissions                                                         #
# ------------------------------------------------------------------ #

@api_view(["POST"])
@permission_classes([IsAuthenticated])
def grant_permission_view(request, document_id):
    from django.contrib.auth import get_user_model
    User = get_user_model()

    target_user_id = request.data.get("user_id")
    level = request.data.get("permission")

    if not target_user_id or not level:
        return Response(
            {"detail": "user_id and permission are required."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    try:
        target_user = User.objects.get(id=target_user_id)
    except User.DoesNotExist:
        return Response({"detail": "User not found."}, status=status.HTTP_404_NOT_FOUND)

    success = grant_permission(request.user, target_user, document_id, level)
    if not success:
        return Response(
            {"detail": "You do not have admin rights on this document."},
            status=status.HTTP_403_FORBIDDEN,
        )
    return Response({"status": "granted"})


@api_view(["DELETE"])
@permission_classes([IsAuthenticated])
def revoke_permission_view(request, document_id):
    from django.contrib.auth import get_user_model
    User = get_user_model()

    target_user_id = request.data.get("user_id")
    if not target_user_id:
        return Response(
            {"detail": "user_id is required."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    try:
        target_user = User.objects.get(id=target_user_id)
    except User.DoesNotExist:
        return Response({"detail": "User not found."}, status=status.HTTP_404_NOT_FOUND)

    success = revoke_permission(request.user, target_user, document_id)
    if not success:
        return Response({"detail": "Forbidden."}, status=status.HTTP_403_FORBIDDEN)
    return Response({"status": "revoked"})


# ------------------------------------------------------------------ #
# Snapshots (called by client after snapshotting locally)            #
# ------------------------------------------------------------------ #

@api_view(["POST"])
@permission_classes([IsAuthenticated])
def save_snapshot_view(request, document_id):
    """
    The Yjs client calls this after producing a snapshot locally.
    Body: { "snapshot": "<base64-encoded Yjs state>" }
    """
    import base64
    from .permissions import has_permission

    if not has_permission(request.user, document_id, "edit"):
        return Response({"detail": "Forbidden."}, status=status.HTTP_403_FORBIDDEN)

    snapshot_b64 = request.data.get("snapshot")
    if not snapshot_b64:
        return Response({"detail": "snapshot is required."}, status=status.HTTP_400_BAD_REQUEST)

    try:
        snapshot_bytes = base64.b64decode(snapshot_b64)
        save_snapshot(document_id, snapshot_bytes)
        return Response({"status": "snapshot saved"})
    except Exception:
        logger.exception("save_snapshot failed for %s", document_id)
        return Response({"detail": "Failed."}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


# ------------------------------------------------------------------ #
# Locks                                                               #
# ------------------------------------------------------------------ #

@api_view(["POST"])
@permission_classes([IsAuthenticated])
def acquire_lock_view(request, document_id):
    acquired = acquire_lock(request.user, document_id)
    if acquired:
        return Response({"status": "acquired"})
    holder = get_lock_holder(document_id)
    return Response(
        {"detail": "Document is locked.", "locked_by": str(holder)},
        status=status.HTTP_409_CONFLICT,
    )


@api_view(["DELETE"])
@permission_classes([IsAuthenticated])
def release_lock_view(request, document_id):
    release_lock(request.user, document_id)
    return Response({"status": "released"})