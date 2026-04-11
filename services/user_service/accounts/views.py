from django.core.cache import cache
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from django.shortcuts import get_object_or_404
from .models import UserProfile
from .serializers import UserProfileSerializer, PublicUserProfileSerializer


CACHE_TTL = 60 * 60  # 1 hour


# GET PROFILE
@api_view(["GET"])
@permission_classes([IsAuthenticated])
def get_profile(request):
    cache_key = f"profile:{request.user.id}"
    data = cache.get(cache_key)

    if not data:
        profile = request.user.profile
        serializer = UserProfileSerializer(profile)
        data = serializer.data
        cache.set(cache_key, data, CACHE_TTL)

    return Response(data)


# UPDATE PROFILE (Cloudinary URL comes here)
@api_view(["PATCH"])
@permission_classes([IsAuthenticated])
def update_profile(request):
    profile = request.user.profile

    profile.profile_picture = request.data.get(
        "profile_picture", profile.profile_picture
    )
    profile.job_title = request.data.get(
        "job_title", profile.job_title
    )
    profile.bio = request.data.get(
        "bio", profile.bio
    )

    profile.save()

    cache.delete(f"profile:{request.user.id}")
    cache.delete(f"public_profile:{request.user.id}")

    return Response({
        "message": "Profile updated successfully",
        "profile_picture": profile.profile_picture,
        "job_title": profile.job_title,
        "bio": profile.bio,
    })


@api_view(["GET"])
@permission_classes([AllowAny])
def public_profile_view(request, user_id):
    cache_key = f"public_profile:{user_id}"
    data = cache.get(cache_key)

    if not data:
        profile = get_object_or_404(UserProfile, user_id=user_id)
        serializer = PublicUserProfileSerializer(profile)
        data = serializer.data
        cache.set(cache_key, data, CACHE_TTL)

    return Response(data)