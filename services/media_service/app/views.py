import hashlib
import hmac
import logging
import time
import uuid
import base64
 
from django.utils import timezone
from rest_framework.decorators import api_view, permission_classes, parser_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.parsers import MultiPartParser
from rest_framework.response import Response
from rest_framework import status
 
from .models import Room, Participant, IceServer, Recording, RecordingChunk, RoomInvite
from .tasks import assemble_recording_chunks
 
logger = logging.getLogger(__name__)
 
 
# ------------------------------------------------------------------ #
# Rooms                                                               #
# ------------------------------------------------------------------ #
 
@api_view(["POST"])
@permission_classes([IsAuthenticated])
def create_room(request):
    workspace_id = request.data.get("workspace_id")
    if not workspace_id:
        return Response({"detail": "workspace_id is required."}, status=status.HTTP_400_BAD_REQUEST)
 
    room = Room.objects.create(
        workspace_id=workspace_id,
        name=request.data.get("name", ""),
        room_type=request.data.get("room_type", "video"),
        created_by=request.user,
        max_participants=request.data.get("max_participants", 10),
    )
 
    # Creator becomes host participant
    Participant.objects.create(room=room, user=request.user, role="host")
 
    return Response({
        "room_id": str(room.id),
        "room_type": room.room_type,
        "name": room.name,
    }, status=status.HTTP_201_CREATED)
 
 
@api_view(["GET"])
@permission_classes([IsAuthenticated])
def get_room(request, room_id):
    try:
        room = Room.objects.get(id=room_id)
    except Room.DoesNotExist:
        return Response({"detail": "Room not found."}, status=status.HTTP_404_NOT_FOUND)
 
    participants = Participant.objects.filter(
        room=room, left_at__isnull=True
    ).select_related("user")
 
    return Response({
        "room_id": str(room.id),
        "name": room.name,
        "room_type": room.room_type,
        "is_active": room.is_active,
        "is_locked": room.is_locked,
        "max_participants": room.max_participants,
        "participant_count": participants.count(),
        "participants": [
            {
                "user_id": str(p.user_id),
                "username": str(p.user),
                "role": p.role,
                "is_muted": p.is_muted,
                "is_video_on": p.is_video_on,
                "is_screen_sharing": p.is_screen_sharing,
            }
            for p in participants
        ],
    })
 
 
@api_view(["POST"])
@permission_classes([IsAuthenticated])
def end_room(request, room_id):
    try:
        room = Room.objects.get(id=room_id)
    except Room.DoesNotExist:
        return Response({"detail": "Not found."}, status=status.HTTP_404_NOT_FOUND)
 
    # Only host or creator may end the room
    is_host = Participant.objects.filter(
        room=room, user=request.user, role__in=["host", "co_host"]
    ).exists()
    if not is_host and room.created_by != request.user:
        return Response({"detail": "Only the host can end the room."}, status=status.HTTP_403_FORBIDDEN)
 
    room.is_active = False
    room.ended_at = timezone.now()
    room.save(update_fields=["is_active", "ended_at"])
 
    return Response({"status": "ended"})
 
 
# ------------------------------------------------------------------ #
# ICE Servers (STUN/TURN)                                             #
# ------------------------------------------------------------------ #
 
@api_view(["GET"])
@permission_classes([IsAuthenticated])
def get_ice_servers(request):
    """
    Return STUN/TURN configs for RTCPeerConnection.
 
    For TURN servers with hmac_secret set, generate time-limited credentials
    using the coturn HMAC-SHA1 mechanism instead of returning static passwords.
    This is the production-safe approach — static TURN credentials can be
    extracted from the client and abused.
 
    Credential format:
      username = "<unix_timestamp>:<user_id>"
      password = base64(HMAC-SHA1(secret, username))
    """
    servers = IceServer.objects.filter(is_active=True)
    result = []
 
    for s in servers:
        if s.hmac_secret:
            ttl = s.credential_ttl
            timestamp = int(time.time()) + ttl
            username = f"{timestamp}:{request.user.id}"
            digest = hmac.new(
                s.hmac_secret.encode(),
                username.encode(),
                hashlib.sha1,
            ).digest()
            credential = base64.b64encode(digest).decode()
            result.append({
                "urls": s.url,
                "username": username,
                "credential": credential,
            })
        elif s.username:
            result.append({
                "urls": s.url,
                "username": s.username,
                "credential": s.credential,
            })
        else:
            result.append({"urls": s.url})
 
    return Response({"ice_servers": result})
 
 
# ------------------------------------------------------------------ #
# Recordings                                                          #
# ------------------------------------------------------------------ #
 
@api_view(["POST"])
@permission_classes([IsAuthenticated])
@parser_classes([MultiPartParser])
def upload_recording_chunk(request, room_id):
    """
    Chunked upload endpoint. The client sends one chunk at a time.
    Body: multipart with `file`, `chunk_index`, `recording_id` (optional on first chunk).
    """
    chunk_file = request.FILES.get("file")
    chunk_index = request.data.get("chunk_index")
    recording_id = request.data.get("recording_id")
 
    if not chunk_file or chunk_index is None:
        return Response(
            {"detail": "file and chunk_index are required."},
            status=status.HTTP_400_BAD_REQUEST,
        )
 
    # Get or create the Recording record on first chunk
    if recording_id:
        try:
            recording = Recording.objects.get(id=recording_id, room_id=room_id)
        except Recording.DoesNotExist:
            return Response({"detail": "Recording not found."}, status=status.HTTP_404_NOT_FOUND)
    else:
        recording = Recording.objects.create(
            room_id=room_id,
            recorded_by=request.user,
            started_at=timezone.now(),
            status="recording",
        )
 
    # Upload to cloud storage and store URL
    # For now we store locally — replace with S3/Cloudinary in production
    import os
    from django.conf import settings as django_settings
    upload_dir = os.path.join(django_settings.MEDIA_ROOT, "recording_chunks", str(recording.id))
    os.makedirs(upload_dir, exist_ok=True)
    chunk_path = os.path.join(upload_dir, f"chunk_{chunk_index}")
    with open(chunk_path, "wb") as f:
        for part in chunk_file.chunks():
            f.write(part)
 
    chunk_url = f"/media/recording_chunks/{recording.id}/chunk_{chunk_index}"
    RecordingChunk.objects.update_or_create(
        recording=recording,
        chunk_index=int(chunk_index),
        defaults={"file_url": chunk_url, "size": chunk_file.size},
    )
 
    return Response({
        "recording_id": str(recording.id),
        "chunk_index": chunk_index,
        "status": "chunk_received",
    })
 
 
@api_view(["POST"])
@permission_classes([IsAuthenticated])
def finalize_recording(request, recording_id):
    """
    Called by client after all chunks are uploaded.
    Triggers the assembly Celery task.
    """
    try:
        recording = Recording.objects.get(id=recording_id, recorded_by=request.user)
    except Recording.DoesNotExist:
        return Response({"detail": "Not found."}, status=status.HTTP_404_NOT_FOUND)
 
    recording.ended_at = timezone.now()
    recording.status = "processing"
    recording.save(update_fields=["ended_at", "status"])
 
    assemble_recording_chunks.delay(str(recording.id))
 
    return Response({"status": "processing", "recording_id": str(recording.id)})
 
 
@api_view(["GET"])
@permission_classes([IsAuthenticated])
def list_recordings(request, room_id):
    recordings = Recording.objects.filter(room_id=room_id).order_by("-created_at")
    return Response([
        {
            "id": str(r.id),
            "status": r.status,
            "file_url": r.file_url,
            "file_size": r.file_size,
            "started_at": r.started_at.isoformat() if r.started_at else None,
            "ended_at": r.ended_at.isoformat() if r.ended_at else None,
        }
        for r in recordings
    ])
 
 
# ------------------------------------------------------------------ #
# Room Invites                                                         #
# ------------------------------------------------------------------ #
 
@api_view(["POST"])
@permission_classes([IsAuthenticated])
def create_invite(request, room_id):
    """Generate an invite token for a room."""
    try:
        room = Room.objects.get(id=room_id, is_active=True)
    except Room.DoesNotExist:
        return Response({"detail": "Room not found."}, status=status.HTTP_404_NOT_FOUND)
 
    is_host = Participant.objects.filter(
        room=room, user=request.user, role__in=["host", "co_host"]
    ).exists()
    if not is_host:
        return Response({"detail": "Only hosts can create invites."}, status=status.HTTP_403_FORBIDDEN)
 
    from datetime import timedelta
    token = uuid.uuid4().hex
    expires_in_hours = int(request.data.get("expires_in_hours", 24))
    invite = RoomInvite.objects.create(
        room=room,
        created_by=request.user,
        token=token,
        max_uses=int(request.data.get("max_uses", 1)),
        expires_at=timezone.now() + timedelta(hours=expires_in_hours),
    )
 
    return Response({
        "invite_token": invite.token,
        "expires_at": invite.expires_at.isoformat(),
        "max_uses": invite.max_uses,
    }, status=status.HTTP_201_CREATED)
 
 
@api_view(["POST"])
@permission_classes([IsAuthenticated])
def join_via_invite(request):
    """Accept an invite token and add user as participant."""
    token = request.data.get("token")
    if not token:
        return Response({"detail": "token is required."}, status=status.HTTP_400_BAD_REQUEST)
 
    try:
        invite = RoomInvite.objects.select_related("room").get(token=token)
    except RoomInvite.DoesNotExist:
        return Response({"detail": "Invalid invite token."}, status=status.HTTP_404_NOT_FOUND)
 
    if not invite.is_valid():
        return Response({"detail": "Invite has expired or reached its use limit."}, status=status.HTTP_410_GONE)
 
    invite.use_count += 1
    invite.save(update_fields=["use_count"])
 
    Participant.objects.get_or_create(
        room=invite.room,
        user=request.user,
        defaults={"role": "participant"},
    )
 
    return Response({"room_id": str(invite.room_id)})