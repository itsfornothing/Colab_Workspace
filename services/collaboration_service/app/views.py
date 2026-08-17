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
        {
            "id": str(d.id),
            "title": d.title,
            "workspace_id": str(d.workspace_id),
            "last_edited_at": d.updated_at.isoformat(),
            "last_edited_by": (
                d.content.last_edited_by.get_full_name() or
                d.content.last_edited_by.username
                if hasattr(d, "content") and d.content and d.content.last_edited_by
                else None
            ),
        }
        for d in docs.select_related("content__last_edited_by")
    ])


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def get_document_view(request, document_id):
    try:
        doc = get_document(request.user, document_id)
        # doc.content is a OneToOne reverse relation — it may not exist
        # for documents created before DocumentContent was introduced.
        try:
            content_value = doc.content.content
        except Exception:
            content_value = ""
        return Response({
            "id": str(doc.id),
            "title": doc.title,
            "content": content_value,
            "updated_at": doc.updated_at,
        })
    except PermissionError as e:
        return Response({"detail": str(e)}, status=status.HTTP_403_FORBIDDEN)
    except Exception:
        return Response({"detail": "Not found."}, status=status.HTTP_404_NOT_FOUND)


@api_view(["PUT", "PATCH"])
@permission_classes([IsAuthenticated])
def update_document_view(request, document_id):
    content = request.data.get("content")
    title = request.data.get("title")

    if content is None and title is None:
        return Response(
            {"detail": "content or title is required."},
            status=status.HTTP_400_BAD_REQUEST,
        )
    try:
        from .models import Document
        doc = Document.objects.get(id=document_id)
        if title is not None:
            doc.title = title.strip()
            doc.save(update_fields=["title", "updated_at"])
        if content is not None:
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
    except Exception:
        logger.exception("archive_document failed for %s", document_id)
        return Response(
            {"detail": "Could not delete document."},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )


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


# ------------------------------------------------------------------ #
# Notification helper                                                 #
# ------------------------------------------------------------------ #

def _fire_notification(user_id: str, title: str, message: str, metadata: dict = None):
    """
    POST a system_alert event to the notification service.
    Runs in a background thread so it never blocks the HTTP response.
    Failures are logged but do not affect the caller.
    """
    import threading
    import urllib.request
    import json as _json
    from django.conf import settings as _settings

    notification_url = getattr(
        _settings,
        "NOTIFICATION_SERVICE_URL",
        "http://notification_service:8005",
    )
    endpoint = f"{notification_url}/api/events/"

    payload = _json.dumps({
        "event_type": "system_alert",
        "payload": {
            "user_id": str(user_id),
            "title": title,
            "message": message,
            **(metadata or {}),
        },
    }).encode()

    def _post():
        try:
            parsed = urllib.request.urlparse(endpoint)
            if parsed.scheme not in ("http", "https"):
                logger.warning("Blocked notification request to non-HTTP URL: %s", endpoint)
                return
            req = urllib.request.Request(
                endpoint,
                data=payload,
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            urllib.request.urlopen(req, timeout=5)  # nosec B310
        except Exception:
            logger.warning("Could not reach notification service at %s", endpoint)

    threading.Thread(target=_post, daemon=True).start()


# ------------------------------------------------------------------ #
# Tasks                                                               #
# ------------------------------------------------------------------ #

@api_view(["GET", "POST"])
@permission_classes([IsAuthenticated])
def tasks_view(request):
    """
    GET  /api/tasks/?workspace_id=<uuid>  — list tasks
    POST /api/tasks/                       — create task
    """
    from .models import Task

    if request.method == "GET":
        workspace_id = request.query_params.get("workspace_id")
        if not workspace_id:
            return Response({"detail": "workspace_id required."}, status=400)
        qs = Task.objects.filter(workspace_id=workspace_id)
        status_filter = request.query_params.get("status")
        if status_filter:
            qs = qs.filter(status=status_filter)
        return Response([_task_dict(t) for t in qs])

    # POST
    workspace_id = request.data.get("workspace_id")
    title = request.data.get("title", "").strip()
    if not workspace_id or not title:
        return Response({"detail": "workspace_id and title required."}, status=400)

    due_date = request.data.get("due_date")
    task = Task.objects.create(
        workspace_id=workspace_id,
        title=title,
        description=request.data.get("description", ""),
        status=request.data.get("status", "todo"),
        priority=request.data.get("priority", "medium"),
        assignee_id=request.data.get("assignee_id"),
        due_date=due_date,
        created_by=request.user,
    )

    # Notify the creator that the task was created
    due_info = f" (due {due_date})" if due_date else ""
    _fire_notification(
        user_id=str(request.user.id),
        title="Task Created",
        message=f'Your task "{title}"{due_info} has been created.',
        metadata={"task_id": str(task.id), "priority": task.priority},
    )

    return Response(_task_dict(task), status=201)


@api_view(["GET", "PATCH", "DELETE"])
@permission_classes([IsAuthenticated])
def task_detail_view(request, task_id):
    from .models import Task
    try:
        task = Task.objects.get(id=task_id)
    except Task.DoesNotExist:
        return Response({"detail": "Not found."}, status=404)

    if request.method == "GET":
        return Response(_task_dict(task))

    if request.method == "DELETE":
        task.delete()
        return Response(status=204)

    # PATCH
    for field in ("title", "description", "status", "priority", "assignee_id", "due_date"):
        if field in request.data:
            setattr(task, field, request.data[field])
    task.save()
    return Response(_task_dict(task))


def _task_dict(task):
    return {
        "id": str(task.id),
        "workspace_id": str(task.workspace_id),
        "title": task.title,
        "description": task.description,
        "status": task.status,
        "priority": task.priority,
        "assignee_id": str(task.assignee_id) if task.assignee_id else None,
        "created_by": str(task.created_by_id) if task.created_by_id else None,
        "due_date": task.due_date.isoformat() if hasattr(task.due_date, 'isoformat') else (str(task.due_date) if task.due_date else None),
        "created_at": task.created_at.isoformat(),
        "updated_at": task.updated_at.isoformat(),
    }


# ------------------------------------------------------------------ #
# Workspace Files                                                      #
# ------------------------------------------------------------------ #

@api_view(["GET"])
@permission_classes([IsAuthenticated])
def files_view(request):
    """GET /api/files/?workspace_id=<uuid>&q=<search>"""
    from .models import WorkspaceFile
    workspace_id = request.query_params.get("workspace_id")
    if not workspace_id:
        return Response({"detail": "workspace_id required."}, status=400)

    qs = WorkspaceFile.objects.filter(workspace_id=workspace_id)
    q = request.query_params.get("q", "").strip()
    if q:
        qs = qs.filter(name__icontains=q)

    return Response([_file_dict(f) for f in qs])


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def upload_file_view(request):
    """POST /api/files/upload/

    Accepts two modes:
    1. JSON body with a Cloudinary URL (preferred):
       { "workspace_id": "...", "file_url": "...", "name": "...",
         "file_size": 1234, "mime_type": "image/png" }
    2. Multipart file upload (legacy):
       form fields: workspace_id; file: <binary>
    """
    import os, uuid as _uuid
    from django.conf import settings as django_settings
    from .models import WorkspaceFile

    workspace_id = request.data.get("workspace_id")
    if not workspace_id:
        return Response({"detail": "workspace_id required."}, status=400)

    # ── Mode 1: Cloudinary URL supplied directly ──────────────────────
    file_url = request.data.get("file_url")
    if file_url:
        name = request.data.get("name") or file_url.split("/")[-1]
        try:
            file_size = int(request.data.get("file_size") or 0)
        except (TypeError, ValueError):
            file_size = 0
        mime_type = request.data.get("mime_type") or "application/octet-stream"

        wf = WorkspaceFile.objects.create(
            workspace_id=workspace_id,
            name=name,
            file_url=file_url,
            file_size=file_size,
            mime_type=mime_type,
            uploaded_by=request.user,
        )
        return Response(_file_dict(wf), status=201)

    # ── Mode 2: Multipart file upload (legacy) ────────────────────────
    f = request.FILES.get("file")
    if not f:
        return Response({"detail": "Provide either file_url or a multipart file."}, status=400)

    if f.size > 100 * 1024 * 1024:
        return Response({"detail": "File too large (max 100 MB)."}, status=400)

    ext = os.path.splitext(f.name)[1]
    filename = f"{_uuid.uuid4().hex}{ext}"
    upload_dir = os.path.join(django_settings.MEDIA_ROOT, "workspace_files")
    os.makedirs(upload_dir, exist_ok=True)
    filepath = os.path.join(upload_dir, filename)

    with open(filepath, "wb") as dest:
        for chunk in f.chunks():
            dest.write(chunk)

    base = getattr(django_settings, "BASE_URL", "http://localhost:8005")
    stored_url = f"{base}/media/workspace_files/{filename}"

    wf = WorkspaceFile.objects.create(
        workspace_id=workspace_id,
        name=f.name,
        file_url=stored_url,
        file_size=f.size,
        mime_type=f.content_type or "",
        uploaded_by=request.user,
    )
    return Response(_file_dict(wf), status=201)


@api_view(["DELETE"])
@permission_classes([IsAuthenticated])
def delete_file_view(request, file_id):
    from .models import WorkspaceFile
    try:
        wf = WorkspaceFile.objects.get(id=file_id)
        wf.delete()
        return Response(status=204)
    except WorkspaceFile.DoesNotExist:
        return Response({"detail": "Not found."}, status=404)


def _file_dict(f):
    return {
        "id": str(f.id),
        "workspace_id": str(f.workspace_id),
        "name": f.name,
        "file_url": f.file_url,
        "file_size": f.file_size,
        "mime_type": f.mime_type,
        "uploaded_by": str(f.uploaded_by_id) if f.uploaded_by_id else None,
        "created_at": f.created_at.isoformat(),
    }


# ------------------------------------------------------------------ #
# Document versions list                                               #
# ------------------------------------------------------------------ #

@api_view(["GET"])
@permission_classes([IsAuthenticated])
def document_versions_view(request, document_id):
    """GET /api/documents/<id>/versions/"""
    from .models import DocumentVersion
    from .permissions import has_permission
    if not has_permission(request.user, document_id, "view"):
        return Response({"detail": "Forbidden."}, status=403)
    versions = DocumentVersion.objects.filter(document_id=document_id).order_by("-version_number")
    return Response([{
        "version_number": v.version_number,
        "edited_by": str(v.edited_by_id) if v.edited_by_id else None,
        "created_at": v.created_at.isoformat(),
    } for v in versions])
