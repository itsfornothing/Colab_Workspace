from rest_framework import serializers
from .models import UserProfile


class UserProfileSerializer(serializers.ModelSerializer):
    # Expose the auth User fields Flutter needs
    user_id   = serializers.UUIDField(source="user.id",        read_only=True)
    email     = serializers.CharField(source="user.email",     read_only=True)
    username  = serializers.CharField(source="user.username",  read_only=True)
    full_name = serializers.CharField(source="user.full_name", read_only=True)

    class Meta:
        model  = UserProfile
        fields = [
            "user_id", "id", "email", "username", "full_name",
            "profile_picture", "job_title", "bio",
            "online_status", "last_seen",
            "timezone", "locale",
            "created_at", "updated_at",
        ]
        read_only_fields = ["user_id", "id", "email", "username", "full_name", "created_at", "updated_at"]


class PublicUserProfileSerializer(serializers.ModelSerializer):
    """Used by chat avatars and public workspace member lists."""
    username = serializers.CharField(source="user.username", read_only=True)
    user_id  = serializers.UUIDField(source="user.id", read_only=True)

    class Meta:
        model  = UserProfile
        fields = [
            "user_id", "username",
            "profile_picture", "job_title", "bio",
            "online_status", "last_seen",
        ]