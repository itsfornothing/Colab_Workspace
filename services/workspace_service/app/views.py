from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from django.shortcuts import get_object_or_404
from rest_framework.response import Response
from rest_framework import status
from .permissions import IsWorkspaceAdmin
from .models import Workspace, Invitation, Membership, Team, TeamMembership
from .services import (
    create_workspace_service,
    invite_user_service,
    accept_invitation_service,
    is_admin,
)
from .serializers import (
    WorkspaceSerializer,
    MembershipSerializer,
    TeamSerializer,
    TeamMembershipSerializer,
)
from django.core.cache import cache


def get_user_workspaces(user):
    cache_key = f"user_workspaces_{user.id}"
    data = cache.get(cache_key)

    if data is not None:
        return data

    workspaces = list(
        Workspace.objects.filter(
            members__user=user
        ).values("id", "name")
    )

    cache.set(cache_key, workspaces, timeout=300)
    return workspaces


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def create_workspace(request):
    name = request.data.get("name")

    if not name:
        return Response({"error": "Workspace name is required"}, status=400)

    workspace = create_workspace_service(request.user, name)

    serializer = WorkspaceSerializer(workspace)

    return Response({
        "message": "Workspace created successfully",
        "workspace": serializer.data
    }, status=status.HTTP_201_CREATED)


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def list_workspaces(request):
    workspaces = get_user_workspaces(request.user)
    return Response(workspaces)


@api_view(["GET", "DELETE"])
@permission_classes([IsAuthenticated])
def workspace_detail(request, workspace_id):
    workspace = get_object_or_404(Workspace, id=workspace_id)

    if not Membership.objects.filter(user=request.user, workspace=workspace).exists():
        return Response({"error": "Not a member"}, status=403)

    if request.method == "DELETE":
        if not is_admin(request.user, workspace):
            return Response({"error": "Only admins can delete workspaces"}, status=403)
        workspace.delete()
        return Response({"message": "Workspace deleted"})

    serializer = WorkspaceSerializer(workspace)
    return Response(serializer.data)


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def workspace_members(request, workspace_id):
    workspace = get_object_or_404(Workspace, id=workspace_id)

    if not Membership.objects.filter(user=request.user, workspace=workspace).exists():
        return Response({"error": "Not a member"}, status=403)

    memberships = Membership.objects.filter(workspace=workspace).select_related("user")
    serializer = MembershipSerializer(memberships, many=True)
    return Response(serializer.data)


@api_view(["PATCH", "DELETE"])
@permission_classes([IsAuthenticated])
def membership_detail(request, membership_id):
    membership = get_object_or_404(Membership, id=membership_id)

    if not is_admin(request.user, membership.workspace):
        return Response({"error": "Only admins can manage memberships"}, status=403)

    if request.method == "DELETE":
        membership.delete()
        return Response({"message": "Membership removed"})

    role = request.data.get("role")
    if not role:
        return Response({"error": "Role is required"}, status=400)

    membership.role = role
    membership.save()

    return Response(MembershipSerializer(membership).data)


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def invite_user(request):
    workspace_id = request.data.get("workspace_id")
    email = request.data.get("email")
    role = request.data.get("role", "member")

    if not email:
        return Response({"error": "Invitee email is required"}, status=400)

    workspace = request.workspace
    if workspace_id:
        if workspace and str(workspace.id) != str(workspace_id):
            return Response({"error": "Workspace header mismatch"}, status=403)
        try:
            workspace = Workspace.objects.get(id=workspace_id)
        except Workspace.DoesNotExist:
            return Response({"error": "Workspace not found"}, status=404)

    if not workspace:
        return Response({"error": "Workspace required"}, status=400)

    if not is_admin(request.user, workspace):
        return Response({"error": "Only admins can invite"}, status=403)

    invitation = invite_user_service(workspace, email, role, request.user)

    return Response({"message": "Invitation sent", "invitation_token": str(invitation.token)})


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def accept_invitation(request):
    token = request.data.get("token") or request.data.get("invitation_id")

    if not token:
        return Response({"error": "Invitation token is required"}, status=400)

    try:
        workspace = accept_invitation_service(request.user, token)
        return Response({"message": "Joined workspace", "workspace_id": str(workspace.id)})
    except Invitation.DoesNotExist:
        return Response({"error": "Invalid invitation token"}, status=404)
    except ValueError as exc:
        return Response({"error": str(exc)}, status=400)
    except Exception:
        return Response({"error": "Unable to accept invitation"}, status=400)


@api_view(["POST"])
@permission_classes([IsAuthenticated, IsWorkspaceAdmin])
def create_team(request):
    name = request.data.get("name")
    workspace = request.workspace
    workspace_id = request.data.get("workspace_id")

    if not name:
        return Response({"error": "Team name is required"}, status=400)

    if workspace_id and workspace and str(workspace.id) != str(workspace_id):
        return Response({"error": "Workspace header mismatch"}, status=403)

    if not workspace:
        try:
            workspace = Workspace.objects.get(id=workspace_id)
        except Workspace.DoesNotExist:
            return Response({"error": "Workspace not found"}, status=404)

    team = Team.objects.create(
        name=name,
        workspace=workspace
    )

    return Response({"message": "Team created", "team_id": str(team.id)})


@api_view(["POST"])
@permission_classes([IsAuthenticated, IsWorkspaceAdmin])
def add_team_member(request):
    team_id = request.data.get("team_id")
    user_id = request.data.get("user_id")

    if not team_id or not user_id:
        return Response({"error": "team_id and user_id are required"}, status=400)

    try:
        team = Team.objects.get(id=team_id)
    except Team.DoesNotExist:
        return Response({"error": "Team not found"}, status=404)

    if request.workspace and team.workspace_id != request.workspace.id:
        return Response({"error": "Workspace mismatch"}, status=403)

    if not Membership.objects.filter(user_id=user_id, workspace=team.workspace).exists():
        return Response({"error": "User is not a member of the workspace"}, status=400)

    TeamMembership.objects.get_or_create(
        team=team,
        user_id=user_id,
    )

    return Response({"message": "User added to team"})


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def list_workspace_teams(request, workspace_id):
    workspace = get_object_or_404(Workspace, id=workspace_id)

    if not Membership.objects.filter(user=request.user, workspace=workspace).exists():
        return Response({"error": "Not a member"}, status=403)

    teams = Team.objects.filter(workspace=workspace)
    serializer = TeamSerializer(teams, many=True)
    return Response(serializer.data)


@api_view(["GET", "POST"])
@permission_classes([IsAuthenticated])
def team_members(request):
    if request.method == "GET":
        team_id = request.query_params.get("team_id")
        if not team_id:
            return Response({"error": "team_id is required"}, status=400)

        team = get_object_or_404(Team, id=team_id)

        if not Membership.objects.filter(user=request.user, workspace=team.workspace).exists():
            return Response({"error": "Not a member of the team workspace"}, status=403)

        memberships = TeamMembership.objects.filter(team=team).select_related("user")
        serializer = TeamMembershipSerializer(memberships, many=True)
        return Response(serializer.data)

    team_id = request.data.get("team_id")
    user_id = request.data.get("user_id")

    if not team_id or not user_id:
        return Response({"error": "team_id and user_id are required"}, status=400)

    team = get_object_or_404(Team, id=team_id)

    if request.workspace and team.workspace_id != request.workspace.id:
        return Response({"error": "Workspace mismatch"}, status=403)

    if not Membership.objects.filter(user_id=user_id, workspace=team.workspace).exists():
        return Response({"error": "User is not a member of the workspace"}, status=400)

    membership, created = TeamMembership.objects.get_or_create(
        team=team,
        user_id=user_id,
    )

    return Response({"message": "User added to team", "created": created})


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def switch_workspace(request):
    workspace_id = request.data.get("workspace_id")

    if not workspace_id:
        return Response({"error": "workspace_id is required"}, status=400)

    try:
        workspace = Workspace.objects.get(id=workspace_id)
    except Workspace.DoesNotExist:
        return Response({"error": "Workspace not found"}, status=404)

    if not Membership.objects.filter(user=request.user, workspace=workspace).exists():
        return Response({"error": "Not a member of this workspace"}, status=403)

    cache.set(f"current_workspace:{request.user.id}", str(workspace.id), timeout=3600)

    return Response({"message": "Switched to workspace", "workspace_id": str(workspace.id)})