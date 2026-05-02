import logging
from django.core.cache import cache
from django.utils import timezone
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.response import Response
from rest_framework import status
from django.shortcuts import get_object_or_404
from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
 
from .models import UserProfile
from .serializers import UserProfileSerializer, PublicUserProfileSerializer
 
logger    = logging.getLogger(__name__)
CACHE_TTL = 60 * 60   # 1 hour
 
 
@api_view(["GET"])
@permission_classes([IsAuthenticated])
def get_profile(request):
    cache_key = f"profile:{request.user.id}"
    data      = cache.get(cache_key)
 
    if not data:
        profile    = request.user.profile
        serializer = UserProfileSerializer(profile)
        data       = serializer.data
        cache.set(cache_key, data, CACHE_TTL)
 
    return Response(data)
 
 
@api_view(["PATCH"])
@permission_classes([IsAuthenticated])
def update_profile(request):
    profile = request.user.profile
 
    # BUG FIX: use "in request.data" not truthiness check
    updatable = ["profile_picture", "job_title", "bio", "timezone", "locale"]
    changed   = False
    for field in updatable:
        if field in request.data:
            setattr(profile, field, request.data[field])
            changed = True
 
    if not changed:
        return Response({"error": "No fields to update."}, status=400)
 
    profile.save()
 
    # Invalidate both private and public caches
    cache.delete(f"profile:{request.user.id}")
    cache.delete(f"public_profile:{request.user.id}")
 
    # Broadcast real-time profile update to any open WebSocket connections
    # (chat service uses profile_picture and job_title for message rendering)
    try:
        layer = get_channel_layer()
        async_to_sync(layer.group_send)(
            f"user_{request.user.id}",
            {
                "type": "profile_updated",
                "user_id":         str(request.user.id),
                "profile_picture": profile.profile_picture,
                "job_title":       profile.job_title,
            },
        )
    except Exception:
        logger.warning("Real-time profile broadcast failed for user %s", request.user.id)
 
    return Response(UserProfileSerializer(profile).data)
 
 
@api_view(["POST"])
@permission_classes([IsAuthenticated])
def update_fcm_token(request):
    """Update the Firebase Cloud Messaging token for push notifications."""
    token = request.data.get("fcm_token", "").strip()
    if not token:
        return Response({"error": "fcm_token required."}, status=400)
 
    profile           = request.user.profile
    profile.fcm_token = token
    profile.save(update_fields=["fcm_token"])
    cache.delete(f"profile:{request.user.id}")
    return Response({"message": "FCM token updated."})
 
 
@api_view(["POST"])
@permission_classes([IsAuthenticated])
def update_presence(request):
    """Set online/away/dnd/offline status."""
    valid_statuses = {"online", "away", "dnd", "offline"}
    new_status     = request.data.get("status", "").lower()
 
    if new_status not in valid_statuses:
        return Response({"error": f"status must be one of {valid_statuses}."}, status=400)
 
    profile               = request.user.profile
    profile.online_status = new_status
    profile.last_seen     = timezone.now()
    profile.save(update_fields=["online_status", "last_seen"])
    cache.delete(f"public_profile:{request.user.id}")
    return Response({"status": new_status})
 
 
@api_view(["GET"])
@permission_classes([AllowAny])
def public_profile_view(request, user_id):
    cache_key = f"public_profile:{user_id}"
    data      = cache.get(cache_key)
 
    if not data:
        profile    = get_object_or_404(UserProfile, user_id=user_id)
        serializer = PublicUserProfileSerializer(profile)
        data       = serializer.data
        cache.set(cache_key, data, CACHE_TTL)
 
    return Response(data)
 
 
@api_view(["GET"])
@permission_classes([IsAuthenticated])
def list_users(request):
    """
    Search users by username, email, or full_name.
    """
    from django.db import models as db_models
    from django.contrib.auth import get_user_model
    User = get_user_model()

    q = request.query_params.get("q", "").strip()
    if not q or len(q) < 2:
        return Response({"error": "q must be at least 2 characters."}, status=400)

    users = User.objects.filter(
        is_active=True
    ).filter(
        db_models.Q(username__icontains=q) |
        db_models.Q(email__icontains=q) |
        db_models.Q(full_name__icontains=q)
    ).select_related("profile")[:20]

    return Response([
        {
            "id":              str(u.id),
            "username":        u.username,
            "full_name":       u.full_name,
            "email":           u.email,
            "profile_picture": u.profile.profile_picture if hasattr(u, "profile") else None,
        }
        for u in users
    ])