from rest_framework import serializers
from .models import Workspace, Membership, Team, TeamMembership


class WorkspaceSerializer(serializers.ModelSerializer):
    owner_id = serializers.UUIDField(source="owner.id", read_only=True)
    owner_email = serializers.CharField(source="owner.email", read_only=True)

    class Meta:
        model = Workspace
        fields = ["id", "name", "owner_id", "owner_email", "created_at"]
        read_only_fields = ["id", "owner_id", "owner_email", "created_at"]


class MembershipSerializer(serializers.ModelSerializer):
    user_id = serializers.UUIDField(source="user.id", read_only=True)
    email = serializers.CharField(source="user.email", read_only=True)

    class Meta:
        model = Membership
        fields = ["id", "user_id", "email", "role", "joined_at"]
        read_only_fields = ["id", "user_id", "email", "joined_at"]


class TeamSerializer(serializers.ModelSerializer):
    workspace_id = serializers.UUIDField(source="workspace.id", read_only=True)

    class Meta:
        model = Team
        fields = ["id", "name", "workspace_id", "created_at"]
        read_only_fields = ["id", "workspace_id", "created_at"]


class TeamMembershipSerializer(serializers.ModelSerializer):
    user_id = serializers.UUIDField(source="user.id", read_only=True)
    team_id = serializers.UUIDField(source="team.id", read_only=True)

    class Meta:
        model = TeamMembership
        fields = ["id", "team_id", "user_id"]
        read_only_fields = ["id", "team_id", "user_id"]