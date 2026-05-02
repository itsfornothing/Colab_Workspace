"""
Serializers for video call functionality
"""
from rest_framework import serializers
from django.contrib.auth import get_user_model
from .models import Room, RoomParticipant, CallHistory, CallParticipant

User = get_user_model()


class UserSerializer(serializers.ModelSerializer):
    """Serializer for user information"""
    full_name = serializers.SerializerMethodField()
    
    class Meta:
        model = User
        fields = ['id', 'username', 'full_name']
        read_only_fields = ['id', 'username', 'full_name']
    
    def get_full_name(self, obj):
        return getattr(obj, 'full_name', obj.username) or obj.username


class RoomParticipantSerializer(serializers.ModelSerializer):
    """Serializer for room participants"""
    user = UserSerializer(read_only=True)
    
    class Meta:
        model = RoomParticipant
        fields = [
            'id', 'user', 'joined_at', 'left_at',
            'is_muted', 'is_video_on', 'is_screen_sharing'
        ]
        read_only_fields = ['id', 'joined_at']


class RoomSerializer(serializers.ModelSerializer):
    """Serializer for video call rooms"""
    created_by = UserSerializer(read_only=True)
    participants = RoomParticipantSerializer(many=True, read_only=True)
    participant_count = serializers.IntegerField(read_only=True)
    is_full = serializers.BooleanField(read_only=True)
    
    class Meta:
        model = Room
        fields = [
            'id', 'workspace_id', 'name', 'created_by', 'is_active',
            'max_participants', 'created_at', 'ended_at',
            'participants', 'participant_count', 'is_full'
        ]
        read_only_fields = ['id', 'created_at', 'created_by']
    
    def validate_max_participants(self, value):
        """Validate max_participants is between 2 and 8"""
        if value < 2:
            raise serializers.ValidationError("Maximum participants must be at least 2")
        if value > 8:
            raise serializers.ValidationError("Maximum participants cannot exceed 8")
        return value


class CallParticipantSerializer(serializers.ModelSerializer):
    """Serializer for call history participants"""
    user = UserSerializer(read_only=True)
    
    class Meta:
        model = CallParticipant
        fields = ['id', 'user', 'joined_at', 'left_at', 'duration_seconds']
        read_only_fields = ['id', 'joined_at']


class CallHistorySerializer(serializers.ModelSerializer):
    """Serializer for call history records"""
    room = RoomSerializer(read_only=True)
    participants = CallParticipantSerializer(many=True, read_only=True)
    
    class Meta:
        model = CallHistory
        fields = [
            'id', 'room', 'started_at', 'ended_at',
            'duration_seconds', 'participant_count',
            'recording_url', 'participants'
        ]
        read_only_fields = ['id', 'started_at']
