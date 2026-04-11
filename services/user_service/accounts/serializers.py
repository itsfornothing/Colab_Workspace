from rest_framework import serializers
from .models import UserProfile


class UserProfileSerializer(serializers.ModelSerializer):
    email = serializers.CharField(source="user.email", read_only=True)

    class Meta:
        model = UserProfile
        fields = [
            "id",
            "email",
            "profile_picture",
            "job_title",
            "bio",
            "created_at",
        ]


class PublicUserProfileSerializer(serializers.ModelSerializer):
    username = serializers.CharField(source="user.username", read_only=True)

    class Meta:
        model = UserProfile
        fields = [
            "username",
            "profile_picture",
            "job_title",
            "bio",
        ]