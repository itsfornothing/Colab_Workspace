import logging
import os
import uuid
import requests
from django.conf import settings
from django.contrib.auth import get_user_model
from django.db import models as db_models
from rest_framework.decorators import api_view, permission_classes, parser_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.parsers import MultiPartParser, FormParser, JSONParser
from rest_framework.response import Response
from rest_framework import status

from .models import Channel, ChannelMember, Message, DirectConversation, DirectMessage
from .search import search_messages
from . import audit_log

logger = logging.getLogger(__name__)
User = get_user_model()

USER_SERVICE_URL = getattr(settings, "USER_SERVICE_URL", "http://localhost:8000")
WORKSPACE_SERVICE_URL = getattr(settings, "WORKSPACE_SERVICE_URL", "http://localhost:8001")


# ─────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────

def _user_dict(u):
    return {
        "id": str(u.id),
        "username": u.username,
        "full_name": getattr(u, 'full_name', u.get_full_name() or u.username),
        "profile_picture": None,
    }


def _msg_dict(msg):
    return {
        "id": str(msg.id),
        "channel_id": str(msg.channel_id),
        "sender": _user_dict(msg.sender),
        "content": msg.content,
        "message_type": msg.message_type,
        "file_url": msg.file_url,
        "file_name": msg.file_name,
        "is_edited": msg.is_edited,
        "is_deleted": msg.is_deleted,
        "created_at": msg.created_at.isoformat(),
    }


def _dm_dict(dm):
    return {
        "id": str(dm.id),
        "conversation_id": str(dm.conversation_id),
        "sender": _user_dict(dm.sender),
        "content": dm.content,
        "message_type": dm.message_type,
        "file_url": dm.file_url,
        "file_name": dm.file_name,
        "is_edited": dm.is_edited,
        "is_deleted": dm.is_deleted,
        "created_at": dm.created_at.isoformat(),
    }


def _get_auth_header(request):
    return request.headers.get("Authorization", "")


def _get_client_ip(request):
    """Extract client IP from X-Forwarded-For or REMOTE_ADDR."""
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        return x_forwarded_for.split(',')[0].strip()
    return request.META.get('REMOTE_ADDR')


def _validate_workspace_membership(user, workspace_id, auth_header=""):
    """
    Check if a user belongs to a workspace by querying the workspace service.

    Returns a tuple (is_authorized, error_response):
      - (True, None)   — user is authorized (or service unavailable — fail open)
      - (False, Response) — user is explicitly denied (HTTP 403 from workspace service)
    """
    try:
        resp = requests.get(
            f"{WORKSPACE_SERVICE_URL}/api/workspaces/{workspace_id}/members/{user.id}/",
            headers={"Authorization": auth_header},
            timeout=3,
        )
        if resp.status_code == 200:
            return True, None
        if resp.status_code == 403:
            # Workspace service explicitly denied access
            return False, Response(
                {"error": "Access denied. You are not a member of this workspace."},
                status=status.HTTP_403_FORBIDDEN,
            )
        # Any other status (404, 5xx, etc.) — fail open to avoid breaking video calls
        # when workspace service is partially deployed or returns unexpected responses
        logger.warning(
            "Workspace membership check returned status %s for user=%s workspace=%s; allowing access",
            resp.status_code, user.id, workspace_id,
        )
        return True, None
    except Exception:
        # Workspace service unreachable — fail open to avoid breaking video calls
        logger.warning(
            "Workspace service unavailable; allowing access for user=%s workspace=%s",
            user.id, workspace_id,
        )
        return True, None


# ─────────────────────────────────────────────
# User search (proxies to user_service)
# ─────────────────────────────────────────────

@api_view(["GET"])
@permission_classes([IsAuthenticated])
def search_users(request):
    """GET /api/users/search/?q=name — proxy to user_service user search"""
    q = request.GET.get("q", "").strip()
    if len(q) < 1:
        return Response({"error": "q must be at least 1 character."}, status=400)

    try:
        resp = requests.get(
            f"{USER_SERVICE_URL}/api/users/",
            params={"q": q},
            headers={"Authorization": _get_auth_header(request)},
            timeout=5,
        )
        if resp.ok:
            return Response(resp.json())
        return Response([], status=200)
    except Exception:
        logger.exception("User search proxy failed")
        return Response([], status=200)


# ─────────────────────────────────────────────
# Channels
# ─────────────────────────────────────────────

@api_view(["GET", "POST"])
@permission_classes([IsAuthenticated])
def channels(request):
    """
    GET  /api/channels/        — list channels the user is a member of
    POST /api/channels/        — create a new channel
    """
    if request.method == "GET":
        member_channel_ids = ChannelMember.objects.filter(
            user=request.user
        ).values_list("channel_id", flat=True)
        chans = Channel.objects.filter(id__in=member_channel_ids).order_by("name")
        return Response([{
            "id": str(c.id),
            "name": c.name,
            "is_private": c.is_private,
            "description": c.description,
            "created_at": c.created_at.isoformat(),
            "member_count": c.members.count(),
        } for c in chans])

    # POST — create channel
    name = request.data.get("name", "").strip()
    is_private = request.data.get("is_private", False)
    description = request.data.get("description", "")

    if not name:
        return Response({"error": "name is required."}, status=400)

    if Channel.objects.filter(name__iexact=name).exists():
        return Response({"error": "A channel with that name already exists."}, status=400)

    channel = Channel.objects.create(
        name=name,
        is_private=is_private,
        description=description,
        created_by=request.user,
    )
    ChannelMember.objects.create(channel=channel, user=request.user)

    return Response({
        "id": str(channel.id),
        "name": channel.name,
        "is_private": channel.is_private,
        "description": channel.description,
        "created_at": channel.created_at.isoformat(),
        "member_count": 1,
    }, status=201)


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def discover_channels(request):
    """GET /api/channels/discover/?q=name — search public channels to join"""
    q = request.GET.get("q", "").strip()
    qs = Channel.objects.filter(is_private=False)
    if q:
        qs = qs.filter(name__icontains=q)
    qs = qs.order_by("name")[:30]

    joined_ids = set(ChannelMember.objects.filter(
        user=request.user
    ).values_list("channel_id", flat=True))

    return Response([{
        "id": str(c.id),
        "name": c.name,
        "description": c.description,
        "member_count": c.members.count(),
        "is_joined": c.id in joined_ids,
    } for c in qs])


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def join_channel(request, channel_id):
    """POST /api/channels/<id>/join/"""
    try:
        channel = Channel.objects.get(id=channel_id, is_private=False)
    except Channel.DoesNotExist:
        return Response({"error": "Channel not found."}, status=404)

    ChannelMember.objects.get_or_create(channel=channel, user=request.user)
    return Response({"message": "Joined."})


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def leave_channel(request, channel_id):
    """POST /api/channels/<id>/leave/"""
    ChannelMember.objects.filter(channel_id=channel_id, user=request.user).delete()
    return Response({"message": "Left."})


# ─────────────────────────────────────────────
# Channel Messages
# ─────────────────────────────────────────────

@api_view(["GET"])
@permission_classes([IsAuthenticated])
def channel_messages(request, channel_id):
    """GET /api/channels/<id>/messages/?before=<id>&limit=50"""
    if not ChannelMember.objects.filter(channel_id=channel_id, user=request.user).exists():
        return Response({"error": "Not a member."}, status=403)

    limit = min(int(request.GET.get("limit", 50)), 100)
    before = request.GET.get("before")

    qs = Message.objects.filter(channel_id=channel_id).select_related("sender")
    if before:
        try:
            pivot = Message.objects.get(id=before)
            qs = qs.filter(created_at__lt=pivot.created_at)
        except Message.DoesNotExist:
            pass

    msgs = list(qs.order_by("-created_at")[:limit])
    msgs.reverse()
    return Response([_msg_dict(m) for m in msgs])


@api_view(["POST"])
@permission_classes([IsAuthenticated])
@parser_classes([MultiPartParser, FormParser, JSONParser])
def upload_channel_file(request, channel_id):
    """POST /api/channels/<id>/upload/

    Accepts two modes:
    1. JSON body with a Cloudinary URL (preferred):
       { "cloudinary_url": "https://...", "file_name": "photo.jpg", "file_size": 1234 }
    2. Multipart file upload (legacy):
       file: <binary>
    """
    if not ChannelMember.objects.filter(channel_id=channel_id, user=request.user).exists():
        return Response({"error": "Not a member."}, status=403)

    # ── Mode 1: Cloudinary URL ────────────────────────────────────────
    cloudinary_url = request.data.get("cloudinary_url")
    if cloudinary_url:
        file_name = request.data.get("file_name") or cloudinary_url.split("/")[-1]
        try:
            file_size = int(request.data.get("file_size") or 0)
        except (TypeError, ValueError):
            file_size = 0
        return Response({
            "file_url": cloudinary_url,
            "file_name": file_name,
            "file_size": file_size,
        }, status=201)

    # ── Mode 2: Multipart file upload (legacy) ────────────────────────
    f = request.FILES.get("file")
    if not f:
        return Response({"error": "Provide either cloudinary_url or a multipart file."}, status=400)

    if f.size > 50 * 1024 * 1024:  # 50 MB limit
        return Response({"error": "File too large (max 50 MB)."}, status=400)

    ext = os.path.splitext(f.name)[1]
    filename = f"{uuid.uuid4().hex}{ext}"
    upload_dir = os.path.join(settings.MEDIA_ROOT, "chat_files")
    os.makedirs(upload_dir, exist_ok=True)
    filepath = os.path.join(upload_dir, filename)

    with open(filepath, "wb") as dest:
        for chunk in f.chunks():
            dest.write(chunk)

    file_url = f"{settings.MEDIA_URL}chat_files/{filename}"
    # Make it absolute for the app
    base = getattr(settings, "BASE_URL", "http://localhost:8002")
    absolute_url = f"{base}{file_url}"

    return Response({
        "file_url": absolute_url,
        "file_name": f.name,
        "file_size": f.size,
    }, status=201)


# ─────────────────────────────────────────────
# Direct Messages (DMs)
# ─────────────────────────────────────────────

@api_view(["GET"])
@permission_classes([IsAuthenticated])
def dm_conversations(request):
    """GET /api/dm/ — list all DM conversations for the current user"""
    convs = DirectConversation.objects.filter(
        db_models.Q(user1=request.user) | db_models.Q(user2=request.user)
    ).select_related("user1", "user2").order_by("-updated_at")

    result = []
    for conv in convs:
        other = conv.user2 if conv.user1 == request.user else conv.user1
        last_msg = conv.dm_messages.order_by("-created_at").first()
        result.append({
            "id": str(conv.id),
            "other_user": _user_dict(other),
            "last_message": last_msg.content if last_msg and not last_msg.is_deleted else None,
            "last_message_time": last_msg.created_at.isoformat() if last_msg else None,
            "updated_at": conv.updated_at.isoformat(),
        })
    return Response(result)


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def start_dm(request):
    """POST /api/dm/start/ — get or create a DM conversation with another user"""
    other_id = request.data.get("user_id")
    if not other_id:
        return Response({"error": "user_id required."}, status=400)

    try:
        other = User.objects.get(id=other_id)
    except User.DoesNotExist:
        # Try to create a stub user record if they exist in user_service
        try:
            resp = requests.get(
                f"{USER_SERVICE_URL}/api/users/{other_id}/public/",
                headers={"Authorization": _get_auth_header(request)},
                timeout=5,
            )
            if resp.ok:
                data = resp.json()
                other, _ = User.objects.get_or_create(
                    id=other_id,
                    defaults={"username": data.get("username", other_id[:8])},
                )
            else:
                return Response({"error": "User not found."}, status=404)
        except Exception:
            return Response({"error": "User not found."}, status=404)

    if other == request.user:
        return Response({"error": "Cannot DM yourself."}, status=400)

    u1, u2 = sorted([request.user, other], key=lambda u: str(u.id))
    conv, _ = DirectConversation.objects.get_or_create(user1=u1, user2=u2)

    other_data = {
        "id": str(other.id),
        "username": other.username,
        "full_name": getattr(other, 'full_name', other.username),
        "profile_picture": None,
    }

    return Response({
        "id": str(conv.id),
        "other_user": other_data,
    }, status=200)


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def dm_messages(request, conv_id):
    """GET /api/dm/<conv_id>/messages/?before=<id>&limit=50"""
    try:
        conv = DirectConversation.objects.get(
            id=conv_id,
        )
    except DirectConversation.DoesNotExist:
        return Response({"error": "Conversation not found."}, status=404)

    if conv.user1 != request.user and conv.user2 != request.user:
        return Response({"error": "Forbidden."}, status=403)

    limit = min(int(request.GET.get("limit", 50)), 100)
    before = request.GET.get("before")

    qs = DirectMessage.objects.filter(conversation=conv).select_related("sender")
    if before:
        try:
            pivot = DirectMessage.objects.get(id=before)
            qs = qs.filter(created_at__lt=pivot.created_at)
        except DirectMessage.DoesNotExist:
            pass

    msgs = list(qs.order_by("-created_at")[:limit])
    msgs.reverse()
    return Response([_dm_dict(m) for m in msgs])


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def send_dm(request, conv_id):
    """POST /api/dm/<conv_id>/send/"""
    try:
        conv = DirectConversation.objects.get(id=conv_id)
    except DirectConversation.DoesNotExist:
        return Response({"error": "Conversation not found."}, status=404)

    if conv.user1 != request.user and conv.user2 != request.user:
        return Response({"error": "Forbidden."}, status=403)

    content = request.data.get("content", "").strip()
    if not content:
        return Response({"error": "content required."}, status=400)

    msg = DirectMessage.objects.create(
        conversation=conv,
        sender=request.user,
        content=content,
    )
    from django.utils import timezone
    conv.updated_at = timezone.now()
    conv.save(update_fields=["updated_at"])

    return Response(_dm_dict(msg), status=201)


@api_view(["POST"])
@permission_classes([IsAuthenticated])
@parser_classes([MultiPartParser, FormParser])
def upload_dm_file(request, conv_id):
    """POST /api/dm/<conv_id>/upload/"""
    try:
        conv = DirectConversation.objects.get(id=conv_id)
    except DirectConversation.DoesNotExist:
        return Response({"error": "Conversation not found."}, status=404)

    if conv.user1 != request.user and conv.user2 != request.user:
        return Response({"error": "Forbidden."}, status=403)

    f = request.FILES.get("file")
    if not f:
        return Response({"error": "No file provided."}, status=400)

    if f.size > 50 * 1024 * 1024:
        return Response({"error": "File too large (max 50 MB)."}, status=400)

    ext = os.path.splitext(f.name)[1]
    filename = f"{uuid.uuid4().hex}{ext}"
    upload_dir = os.path.join(settings.MEDIA_ROOT, "dm_files")
    os.makedirs(upload_dir, exist_ok=True)
    filepath = os.path.join(upload_dir, filename)

    with open(filepath, "wb") as dest:
        for chunk in f.chunks():
            dest.write(chunk)

    file_url = f"{settings.MEDIA_URL}dm_files/{filename}"
    base = getattr(settings, "BASE_URL", "http://localhost:8002")
    absolute_url = f"{base}{file_url}"

    msg = DirectMessage.objects.create(
        conversation=conv,
        sender=request.user,
        content="",
        message_type="file",
        file_url=absolute_url,
        file_name=f.name,
    )
    from django.utils import timezone
    conv.updated_at = timezone.now()
    conv.save(update_fields=["updated_at"])

    return Response({
        "message": _dm_dict(msg),
        "file_url": absolute_url,
        "file_name": f.name,
    }, status=201)


# ─────────────────────────────────────────────
# Message search
# ─────────────────────────────────────────────

@api_view(["GET"])
@permission_classes([IsAuthenticated])
def search_view(request):
    query = request.GET.get("q", "").strip()
    channel_id = request.GET.get("channel_id", "").strip()

    if not query:
        return Response({"detail": "Query parameter 'q' is required."}, status=400)
    if not channel_id:
        return Response({"detail": "Query parameter 'channel_id' is required."}, status=400)

    try:
        results = search_messages(query, channel_id)
        return Response(results)
    except Exception:
        logger.exception("Search failed for query=%r channel=%r", query, channel_id)
        return Response({"detail": "Search service temporarily unavailable."}, status=503)


# ─────────────────────────────────────────────
# Video Call Rooms
# ─────────────────────────────────────────────

@api_view(["GET", "POST"])
@permission_classes([IsAuthenticated])
def rooms(request):
    """
    GET  /api/rooms/?workspace_id=<uuid>  — list active rooms
    POST /api/rooms/                       — create a room
    """
    from .models import Room, RoomParticipant
    from .serializers import RoomSerializer

    if request.method == "GET":
        workspace_id = request.GET.get("workspace_id")
        # Only list active rooms
        qs = Room.objects.filter(is_active=True).select_related('created_by').prefetch_related('participants__user')
        if workspace_id:
            qs = qs.filter(workspace_id=workspace_id)
        qs = qs.order_by("-created_at")[:20]
        
        serializer = RoomSerializer(qs, many=True)
        return Response(serializer.data)

    # POST — create room
    serializer = RoomSerializer(data=request.data)
    if not serializer.is_valid():
        return Response(serializer.errors, status=400)
    
    room = serializer.save(created_by=request.user, is_active=True)
    # Auto-join creator
    RoomParticipant.objects.create(room=room, user=request.user)
    
    # Audit log: call created
    try:
        audit_log.log_call_created(request.user.id, room.id, room.workspace_id, _get_client_ip(request))
    except Exception:
        pass

    # Return with participants included
    response_serializer = RoomSerializer(room)
    return Response(response_serializer.data, status=201)


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def room_detail(request, room_id):
    """GET /api/rooms/<id>/ — get room details"""
    from .models import Room, RoomParticipant
    from .serializers import RoomSerializer
    
    try:
        room = Room.objects.select_related('created_by').prefetch_related('participants__user').get(id=room_id)
    except Room.DoesNotExist:
        return Response({"error": "Room not found."}, status=404)
    
    # Validate workspace membership if room has workspace_id
    if room.workspace_id:
        is_authorized, error_response = _validate_workspace_membership(
            request.user, room.workspace_id, _get_auth_header(request)
        )
        if not is_authorized:
            return error_response
    
    serializer = RoomSerializer(room)
    return Response(serializer.data)


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def join_room(request, room_id):
    """POST /api/rooms/<id>/join/ — join a room with capacity check"""
    from .models import Room, RoomParticipant
    from .serializers import RoomSerializer
    
    try:
        room = Room.objects.select_related('created_by').prefetch_related('participants__user').get(id=room_id)
    except Room.DoesNotExist:
        return Response({"error": "Room not found."}, status=404)
    
    if not room.is_active:
        return Response({"error": "Room is not active."}, status=400)
    
    # Validate workspace membership if room has workspace_id
    if room.workspace_id:
        is_authorized, error_response = _validate_workspace_membership(
            request.user, room.workspace_id, _get_auth_header(request)
        )
        if not is_authorized:
            return error_response
    
    # Check if room is full
    if room.is_full:
        return Response({"error": "Room is at maximum capacity (8 participants)."}, status=400)
    
    # Check if user is already in the room (and hasn't left)
    existing = RoomParticipant.objects.filter(room=room, user=request.user, left_at__isnull=True).first()
    if existing:
        return Response({"error": "Already in this room."}, status=400)
    
    # Join the room
    RoomParticipant.objects.create(room=room, user=request.user)
    
    # Audit log: call joined
    try:
        audit_log.log_call_joined(request.user.id, room.id, room.workspace_id, _get_client_ip(request))
    except Exception:
        pass

    # Return updated room details
    serializer = RoomSerializer(room)
    return Response(serializer.data)


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def leave_room(request, room_id):
    """POST /api/rooms/<id>/leave/ — leave room and update timestamps"""
    from django.utils import timezone
    from .models import Room, RoomParticipant
    from .serializers import RoomSerializer
    
    try:
        room = Room.objects.get(id=room_id)
    except Room.DoesNotExist:
        return Response({"error": "Room not found."}, status=404)
    
    # Find active participant record
    participant = RoomParticipant.objects.filter(
        room=room, user=request.user, left_at__isnull=True
    ).first()
    
    if not participant:
        return Response({"error": "Not in this room."}, status=400)
    
    # Update left_at timestamp
    participant.left_at = timezone.now()
    participant.save(update_fields=['left_at'])
    
    # Audit log: call left
    try:
        audit_log.log_call_left(request.user.id, room.id, room.workspace_id, _get_client_ip(request))
    except Exception:
        pass

    # Check if room should be ended (no active participants)
    active_count = RoomParticipant.objects.filter(room=room, left_at__isnull=True).count()
    if active_count == 0 and room.is_active:
        room.is_active = False
        room.ended_at = timezone.now()
        room.save(update_fields=['is_active', 'ended_at'])

        # Create CallHistory record with duration and participant details (Requirement 6.1)
        from .models import CallHistory, CallParticipant
        try:
            duration_seconds = int((room.ended_at - room.created_at).total_seconds())
            all_participants = RoomParticipant.objects.filter(room=room).select_related('user')
            call_history = CallHistory.objects.create(
                room=room,
                ended_at=room.ended_at,
                duration_seconds=max(0, duration_seconds),
                participant_count=all_participants.count(),
            )
            for rp in all_participants:
                left = rp.left_at or room.ended_at
                joined = rp.joined_at
                participant_duration = max(0, int((left - joined).total_seconds()))
                CallParticipant.objects.create(
                    call_history=call_history,
                    user=rp.user,
                    joined_at=joined,
                    left_at=left,
                    duration_seconds=participant_duration,
                )
        except Exception:
            logger.exception("Failed to create CallHistory for room %s", room.id)

        # Audit log: call ended
        try:
            audit_log.log_call_ended(request.user.id, room.id, room.workspace_id)
        except Exception:
            pass
    
    serializer = RoomSerializer(room)
    return Response(serializer.data)


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def invite_to_room(request, room_id):
    """POST /api/rooms/<id>/invite/ — send invitations to users"""
    from .models import Room
    
    try:
        room = Room.objects.get(id=room_id)
    except Room.DoesNotExist:
        return Response({"error": "Room not found."}, status=404)
    
    if not room.is_active:
        return Response({"error": "Room is not active."}, status=400)
    
    # Verify the requester is in the room
    from .models import RoomParticipant
    if not RoomParticipant.objects.filter(room=room, user=request.user, left_at__isnull=True).exists():
        return Response({"error": "You must be in the room to invite others."}, status=403)
    
    user_ids = request.data.get("user_ids", [])
    if not user_ids or not isinstance(user_ids, list):
        return Response({"error": "user_ids must be a non-empty list."}, status=400)
    
    # Validate that users exist
    invited_users = User.objects.filter(id__in=user_ids)
    if invited_users.count() != len(user_ids):
        return Response({"error": "Some user IDs are invalid."}, status=400)
    
    # Check workspace authorization if workspace_id is set
    if room.workspace_id:
        is_authorized, error_response = _validate_workspace_membership(
            request.user, room.workspace_id, _get_auth_header(request)
        )
        if not is_authorized:
            return error_response
    
    # Return success - actual invitation delivery happens via WebSocket in ChatConsumer
    # Audit log: call invited
    try:
        audit_log.log_call_invited(request.user.id, room.id, [str(u.id) for u in invited_users], room.workspace_id, _get_client_ip(request))
    except Exception:
        pass

    return Response({
        "message": "Invitations will be sent.",
        "room_id": str(room.id),
        "invited_user_ids": [str(u.id) for u in invited_users]
    })


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def room_participants(request, room_id):
    """GET /api/rooms/<id>/participants/ — list room participants"""
    from .models import Room, RoomParticipant
    from .serializers import RoomParticipantSerializer
    
    try:
        room = Room.objects.get(id=room_id)
    except Room.DoesNotExist:
        return Response({"error": "Room not found."}, status=404)
    
    # Validate workspace membership if room has workspace_id
    if room.workspace_id:
        is_authorized, error_response = _validate_workspace_membership(
            request.user, room.workspace_id, _get_auth_header(request)
        )
        if not is_authorized:
            return error_response
    
    # Get all participants (including those who left)
    participants = RoomParticipant.objects.filter(room=room).select_related('user').order_by('joined_at')
    
    serializer = RoomParticipantSerializer(participants, many=True)
    return Response(serializer.data)


@api_view(["PATCH"])
@permission_classes([IsAuthenticated])
def update_participant_state(request, room_id, user_id):
    """PATCH /api/rooms/<id>/participants/<user_id>/ — update participant state"""
    from .models import Room, RoomParticipant
    from .serializers import RoomParticipantSerializer
    
    try:
        room = Room.objects.get(id=room_id)
    except Room.DoesNotExist:
        return Response({"error": "Room not found."}, status=404)
    
    # Only allow users to update their own state
    if str(request.user.id) != str(user_id):
        return Response({"error": "You can only update your own participant state."}, status=403)
    
    # Validate workspace membership if room has workspace_id
    if room.workspace_id:
        is_authorized, error_response = _validate_workspace_membership(
            request.user, room.workspace_id, _get_auth_header(request)
        )
        if not is_authorized:
            return error_response
    
    # Find active participant record
    participant = RoomParticipant.objects.filter(
        room=room, user=request.user, left_at__isnull=True
    ).first()
    
    if not participant:
        return Response({"error": "Not an active participant in this room."}, status=400)
    
    # Update allowed fields
    allowed_fields = ['is_muted', 'is_video_on', 'is_screen_sharing']
    updated = False
    
    for field in allowed_fields:
        if field in request.data:
            setattr(participant, field, request.data[field])
            updated = True
    
    if updated:
        participant.save(update_fields=allowed_fields)
    
    # Audit log: participant state changed
    try:
        audit_log.log_participant_state_changed(
            request.user.id,
            room.id,
            is_muted=request.data.get('is_muted'),
            is_video_on=request.data.get('is_video_on'),
            is_screen_sharing=request.data.get('is_screen_sharing'),
        )
    except Exception:
        pass

    serializer = RoomParticipantSerializer(participant)
    return Response(serializer.data)


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def call_history(request):
    """GET /api/call-history/ — get user's call history with filtering"""
    from datetime import timedelta
    from django.utils import timezone
    from .models import CallHistory, CallParticipant
    from .serializers import CallHistorySerializer
    
    # Implement 90-day retention query
    retention_days = 90
    cutoff_date = timezone.now() - timedelta(days=retention_days)
    
    # Get calls where the user was a participant
    user_call_ids = CallParticipant.objects.filter(
        user=request.user
    ).values_list('call_history_id', flat=True)
    
    # Filter by retention period
    qs = CallHistory.objects.filter(
        id__in=user_call_ids,
        started_at__gte=cutoff_date
    ).select_related('room__created_by').prefetch_related('participants__user').order_by('-started_at')
    
    # Optional filtering by workspace
    workspace_id = request.GET.get('workspace_id')
    if workspace_id:
        qs = qs.filter(room__workspace_id=workspace_id)
    
    # Pagination
    limit = min(int(request.GET.get('limit', 50)), 100)
    qs = qs[:limit]
    
    serializer = CallHistorySerializer(qs, many=True)
    return Response(serializer.data)


def _validate_ice_servers(ice_servers):
    """
    Validate ICE server configuration (Requirement 10.1).

    Rules:
    - Each server must have a ``urls`` field (string or list of strings).
    - URLs must start with ``stun:``, ``stuns:``, ``turn:``, or ``turns:``.
    - TURN servers must have ``username`` and ``credential`` fields.

    Returns:
        (is_valid, error_message) — is_valid is True when the config is valid.
    """
    valid_schemes = ("stun:", "stuns:", "turn:", "turns:")

    if not isinstance(ice_servers, list) or len(ice_servers) == 0:
        return False, "ICE servers must be a non-empty list"

    for idx, server in enumerate(ice_servers):
        if not isinstance(server, dict):
            return False, f"ICE server at index {idx} must be a dict"

        urls = server.get("urls")
        if urls is None:
            return False, f"ICE server at index {idx} is missing required 'urls' field"

        # Normalise to list
        if isinstance(urls, str):
            url_list = [urls]
        elif isinstance(urls, list):
            url_list = urls
        else:
            return False, f"ICE server at index {idx}: 'urls' must be a string or list of strings"

        for url in url_list:
            if not isinstance(url, str) or not url:
                return False, f"ICE server at index {idx}: invalid URL value {url!r}"

            if not any(url.startswith(scheme) for scheme in valid_schemes):
                return (
                    False,
                    f"ICE server at index {idx}: URL {url!r} must start with one of "
                    f"{valid_schemes}",
                )

            # TURN servers require credentials
            if url.startswith(("turn:", "turns:")):
                if not server.get("username") or not server.get("credential"):
                    return (
                        False,
                        f"ICE server at index {idx}: TURN server {url!r} requires "
                        f"'username' and 'credential' fields",
                    )

    return True, None


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def ice_servers(request):
    """GET /api/ice-servers/ — return STUN/TURN config (Requirement 10.1)"""
    configured_servers = list(getattr(settings, "WEBRTC_ICE_SERVERS", [
        {"urls": "stun:stun.l.google.com:19302"},
        {"urls": "stun:stun1.l.google.com:19302"},
    ]))

    # Optionally include TURN server if configured with a non-empty URL
    turn_config = getattr(settings, "WEBRTC_TURN_SERVER", None)
    if turn_config and turn_config.get("urls"):
        configured_servers.append(turn_config)

    # Validate configuration — log a warning on failure but still return servers
    # so that a misconfiguration doesn't break active calls.
    is_valid, error_message = _validate_ice_servers(configured_servers)
    if not is_valid:
        logger.warning(
            "ICE server configuration validation failed: %s. "
            "Returning servers anyway to avoid breaking calls. (Requirement 10.1)",
            error_message,
        )

    return Response({"iceServers": configured_servers})


# ─────────────────────────────────────────────
# Performance Monitoring (Requirements 11.1, 11.2, 11.4)
# ─────────────────────────────────────────────

@api_view(["GET"])
@permission_classes([IsAuthenticated])
def performance_metrics(request):
    """
    GET /api/metrics/ — return current performance metrics snapshot.

    Returns:
      - active_calls: number of currently active call rooms
      - websocket_connections: number of open WebSocket connections
      - signaling_latency: latency statistics over the rolling sample window
        (count, avg_ms, min_ms, max_ms, p95_ms, p99_ms)

    Requirements: 11.1, 11.2, 11.4
    """
    from . import performance_monitor as pm

    snapshot = pm.get_metrics_snapshot()
    return Response(snapshot)
