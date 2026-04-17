from rest_framework import serializers
from .models import (
    Workspace, Membership, Invitation, WorkspaceInviteLink,
    Team, TeamMembership, Channel, ChannelMembership,
    Message, MessageReaction, Notification,
)
 
 
class WorkspaceSerializer(serializers.ModelSerializer):
    owner_id     = serializers.UUIDField(source="owner.id", read_only=True)
    owner_email  = serializers.CharField(source="owner.email", read_only=True)
    member_count = serializers.SerializerMethodField()
 
    class Meta:
        model  = Workspace
        fields = [
            "id", "name", "slug", "description", "avatar_url",
            "owner_id", "owner_email", "member_count", "is_active", "created_at",
        ]
        read_only_fields = ["id", "owner_id", "owner_email", "member_count", "created_at"]
 
    def get_member_count(self, obj):
        return obj.members.count()
 
 
class MembershipSerializer(serializers.ModelSerializer):
    user_id  = serializers.UUIDField(source="user.id", read_only=True)
    email    = serializers.CharField(source="user.email", read_only=True)
    username = serializers.CharField(source="user.username", read_only=True)
 
    class Meta:
        model  = Membership
        fields = ["id", "user_id", "email", "username", "role", "joined_at"]
        read_only_fields = ["id", "user_id", "email", "username", "joined_at"]
 
 
class TeamSerializer(serializers.ModelSerializer):
    workspace_id = serializers.UUIDField(source="workspace.id", read_only=True)
    member_count = serializers.SerializerMethodField()
 
    class Meta:
        model  = Team
        fields = ["id", "name", "description", "workspace_id", "member_count", "created_at"]
        read_only_fields = ["id", "workspace_id", "member_count", "created_at"]
 
    def get_member_count(self, obj):
        return obj.memberships.count()
 
 
class TeamMembershipSerializer(serializers.ModelSerializer):
    user_id  = serializers.UUIDField(source="user.id", read_only=True)
    email    = serializers.CharField(source="user.email", read_only=True)
    team_id  = serializers.UUIDField(source="team.id", read_only=True)
 
    class Meta:
        model  = TeamMembership
        fields = ["id", "team_id", "user_id", "email", "role"]
        read_only_fields = ["id", "team_id", "user_id", "email"]
 
 
class ChannelSerializer(serializers.ModelSerializer):
    workspace_id = serializers.UUIDField(source="workspace.id", read_only=True)
    member_count = serializers.SerializerMethodField()
 
    class Meta:
        model  = Channel
        fields = [
            "id", "name", "topic", "description", "workspace_id",
            "is_private", "is_archived", "member_count", "created_at",
        ]
        read_only_fields = ["id", "workspace_id", "member_count", "created_at"]
 
    def get_member_count(self, obj):
        return obj.memberships.count()
 
 
class MessageReactionSerializer(serializers.ModelSerializer):
    user_id = serializers.UUIDField(source="user.id", read_only=True)
 
    class Meta:
        model  = MessageReaction
        fields = ["id", "emoji", "user_id"]
 
 
class MessageSerializer(serializers.ModelSerializer):
    sender_id   = serializers.UUIDField(source="sender.id", read_only=True)
    sender_name = serializers.CharField(source="sender.username", read_only=True)
    reactions   = MessageReactionSerializer(many=True, read_only=True)
    reply_count = serializers.SerializerMethodField()
 
    class Meta:
        model  = Message
        fields = [
            "id", "channel", "sender_id", "sender_name", "content",
            "is_edited", "is_deleted", "parent", "reply_count",
            "reactions", "created_at", "updated_at",
        ]
        read_only_fields = [
            "id", "sender_id", "sender_name", "is_edited",
            "reply_count", "reactions", "created_at", "updated_at",
        ]
 
    def get_reply_count(self, obj):
        return obj.replies.count()
 
 
class NotificationSerializer(serializers.ModelSerializer):
    class Meta:
        model  = Notification
        fields = ["id", "type", "message", "metadata", "is_read", "created_at"]
        read_only_fields = ["id", "type", "message", "metadata", "created_at"]
 
 
class InvitationSerializer(serializers.ModelSerializer):
    class Meta:
        model  = Invitation
        fields = ["id", "email", "role", "status", "expires_at", "created_at"]
        read_only_fields = ["id", "status", "created_at"]
 
 
class WorkspaceInviteLinkSerializer(serializers.ModelSerializer):
    invite_url = serializers.SerializerMethodField()
 
    class Meta:
        model  = WorkspaceInviteLink
        fields = [
            "id", "token", "invite_url", "role", "max_uses",
            "use_count", "expires_at", "is_active", "created_at",
        ]
        read_only_fields = ["id", "token", "invite_url", "use_count", "created_at"]
 
    def get_invite_url(self, obj):
        from django.conf import settings
        return f"{settings.FRONTEND_URL}/join/{obj.token}"