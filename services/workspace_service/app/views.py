import logging
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.exceptions import PermissionDenied, ValidationError, NotFound
from rest_framework.response import Response
from rest_framework import status
from django.shortcuts import get_object_or_404
from django.core.cache import cache
 
from .permissions import IsWorkspaceAdmin
from .models import (
    Workspace, Invitation, Membership, Team, TeamMembership,
    Channel, ChannelMembership, Message, Notification, WorkspaceInviteLink,
)
from .services import (
    create_workspace_service, invite_user_service, accept_invitation_service,
    is_admin, create_channel_service, add_channel_member_service,
    remove_channel_member_service, archive_channel_service,
    update_membership_role_service, remove_member_service,
    create_invite_link_service, accept_invite_link_service,
)
from .serializers import (
    WorkspaceSerializer, MembershipSerializer, TeamSerializer,
    TeamMembershipSerializer, ChannelSerializer, MessageSerializer,
    NotificationSerializer, InvitationSerializer, WorkspaceInviteLinkSerializer,
)
from .rbac import check_workspace_permission
 
logger = logging.getLogger(__name__)
 
 
# ------------------------------------------------------------------ #
# Workspace CRUD                                                       #
# ------------------------------------------------------------------ #
 
@api_view(["POST"])
@permission_classes([IsAuthenticated])
def create_workspace(request):
    name = request.data.get("name", "").strip()
    if not name:
        raise ValidationError({"detail": "Workspace name is required."})
 
    workspace = create_workspace_service(
        request.user, name, request.data.get("description", "")
    )
    return Response(
        {"message": "Workspace created.", "workspace": WorkspaceSerializer(workspace).data},
        status=status.HTTP_201_CREATED,
    )
 
 
@api_view(["GET"])
@permission_classes([IsAuthenticated])
def list_workspaces(request):
    cache_key = f"user_workspaces_{request.user.id}"
    data = cache.get(cache_key)
    if data is None:
        qs = Workspace.objects.filter(members__user=request.user, is_active=True)
        data = WorkspaceSerializer(qs, many=True).data
        cache.set(cache_key, data, timeout=300)
    return Response(data)
 
 
@api_view(["GET", "PATCH", "DELETE"])
@permission_classes([IsAuthenticated])
def workspace_detail(request, workspace_id):
    workspace = get_object_or_404(Workspace, id=workspace_id)
 
    if not Membership.objects.filter(user=request.user, workspace=workspace).exists():
        raise PermissionDenied({"detail": "Not a member."})
 
    if request.method == "GET":
        return Response(WorkspaceSerializer(workspace).data)
 
    if request.method == "PATCH":
        if not is_admin(request.user, workspace):
            raise PermissionDenied({"detail": "Admins only."})
        for field in ("name", "description", "avatar_url", "slug"):
            if field in request.data:
                setattr(workspace, field, request.data[field])
        workspace.save()
        cache.delete(f"user_workspaces_{request.user.id}")
        return Response(WorkspaceSerializer(workspace).data)
 
    # DELETE
    if not is_admin(request.user, workspace):
        raise PermissionDenied({"detail": "Only admins can delete workspaces."})
    workspace.delete()
    cache.delete(f"user_workspaces_{request.user.id}")
    return Response({"message": "Workspace deleted."})
 
 
@api_view(["POST"])
@permission_classes([IsAuthenticated])
def switch_workspace(request):
    workspace_id = request.data.get("workspace_id")
    if not workspace_id:
        raise ValidationError({"detail": "workspace_id is required."})
 
    workspace = get_object_or_404(Workspace, id=workspace_id)
 
    if not Membership.objects.filter(user=request.user, workspace=workspace).exists():
        raise PermissionDenied({"detail": "Not a member."})
 
    cache.set(f"current_workspace:{request.user.id}", str(workspace.id), timeout=3600)
    return Response({"message": "Switched.", "workspace_id": str(workspace.id)})
 
 
# ------------------------------------------------------------------ #
# Members                                                             #
# ------------------------------------------------------------------ #
 
@api_view(["GET"])
@permission_classes([IsAuthenticated])
def workspace_members(request, workspace_id):
    workspace = get_object_or_404(Workspace, id=workspace_id)
    if not Membership.objects.filter(user=request.user, workspace=workspace).exists():
        raise PermissionDenied({"detail": "Not a member."})
 
    role_filter = request.query_params.get("role")
    qs = Membership.objects.filter(workspace=workspace).select_related("user")
    if role_filter:
        qs = qs.filter(role=role_filter)
 
    return Response(MembershipSerializer(qs, many=True).data)
 
 
@api_view(["PATCH", "DELETE"])
@permission_classes([IsAuthenticated])
def membership_detail(request, membership_id):
    membership = get_object_or_404(Membership, id=membership_id)
 
    if not is_admin(request.user, membership.workspace):
        raise PermissionDenied({"detail": "Admins only."})
 
    if request.method == "DELETE":
        remove_member_service(request.user, membership)
        return Response({"message": "Membership removed."})
 
    role = request.data.get("role")
    if not role:
        raise ValidationError({"detail": "role is required."})
 
    VALID_ROLES = {"admin", "member", "guest"}
    if role not in VALID_ROLES:
        raise ValidationError({"detail": f"Role must be one of {VALID_ROLES}."})
 
    membership = update_membership_role_service(request.user, membership, role)
    return Response(MembershipSerializer(membership).data)
 
 
# ------------------------------------------------------------------ #
# Invitations                                                         #
# ------------------------------------------------------------------ #
 
@api_view(["POST"])
@permission_classes([IsAuthenticated])
def invite_user(request):
    email = request.data.get("email", "").strip()
    role  = request.data.get("role", "member")
    if not email:
        raise ValidationError({"detail": "email is required."})
 
    # Resolve workspace: prefer header context, fallback to body
    workspace = getattr(request, "workspace", None)
    if not workspace:
        workspace_id = request.data.get("workspace_id")
        if not workspace_id:
            raise ValidationError({"detail": "Workspace context required."})
        workspace = get_object_or_404(Workspace, id=workspace_id)
 
    if not is_admin(request.user, workspace):
        raise PermissionDenied({"detail": "Only admins can invite."})
 
    invitation = invite_user_service(workspace, email, role, request.user)
    return Response(
        {"message": "Invitation sent.", "invitation_token": invitation.token},
        status=status.HTTP_201_CREATED,
    )
 
 
@api_view(["POST"])
@permission_classes([IsAuthenticated])
def accept_invitation(request):
    token = request.data.get("token")
    if not token:
        raise ValidationError({"detail": "token is required."})
 
    try:
        workspace = accept_invitation_service(request.user, token)
        return Response({"message": "Joined workspace.", "workspace_id": str(workspace.id)})
    except ValueError as exc:
        raise ValidationError({"detail": str(exc)})
 
 
@api_view(["POST"])
@permission_classes([IsAuthenticated])
def create_invite_link(request, workspace_id):
    workspace = get_object_or_404(Workspace, id=workspace_id)
    if not is_admin(request.user, workspace):
        raise PermissionDenied({"detail": "Admins only."})
 
    link = create_invite_link_service(
        workspace=workspace,
        created_by=request.user,
        role=request.data.get("role", "member"),
        max_uses=request.data.get("max_uses"),
        expires_in_hours=int(request.data.get("expires_in_hours", 72)),
    )
    return Response(WorkspaceInviteLinkSerializer(link).data, status=status.HTTP_201_CREATED)
 
 
@api_view(["POST"])
@permission_classes([IsAuthenticated])
def accept_invite_link(request):
    token = request.data.get("token")
    if not token:
        raise ValidationError({"detail": "token is required."})
    try:
        workspace = accept_invite_link_service(request.user, token)
        return Response({"workspace_id": str(workspace.id)})
    except ValueError as exc:
        raise ValidationError({"detail": str(exc)})
 
 
# ------------------------------------------------------------------ #
# Teams                                                               #
# ------------------------------------------------------------------ #
 
@api_view(["POST"])
@permission_classes([IsAuthenticated, IsWorkspaceAdmin])
def create_team(request):
    name = request.data.get("name", "").strip()
    if not name:
        raise ValidationError({"detail": "Team name is required."})
 
    workspace = getattr(request, "workspace", None)
    if not workspace:
        workspace = get_object_or_404(Workspace, id=request.data.get("workspace_id"))
 
    team = Team.objects.create(
        name=name,
        workspace=workspace,
        description=request.data.get("description", ""),
        created_by=request.user,
    )
    TeamMembership.objects.create(team=team, user=request.user, role="lead")
    return Response(TeamSerializer(team).data, status=status.HTTP_201_CREATED)
 
 
@api_view(["GET"])
@permission_classes([IsAuthenticated])
def list_workspace_teams(request, workspace_id):
    workspace = get_object_or_404(Workspace, id=workspace_id)
    if not Membership.objects.filter(user=request.user, workspace=workspace).exists():
        raise PermissionDenied({"detail": "Not a member."})
 
    return Response(TeamSerializer(workspace.teams.all(), many=True).data)
 
 
@api_view(["GET", "POST", "DELETE"])
@permission_classes([IsAuthenticated])
def team_members(request):
    if request.method == "GET":
        team_id = request.query_params.get("team_id")
        if not team_id:
            raise ValidationError({"detail": "team_id is required."})
        team = get_object_or_404(Team, id=team_id)
        if not Membership.objects.filter(user=request.user, workspace=team.workspace).exists():
            raise PermissionDenied({"detail": "Not a member."})
        return Response(TeamMembershipSerializer(
            TeamMembership.objects.filter(team=team).select_related("user"), many=True
        ).data)
 
    team_id = request.data.get("team_id")
    user_id = request.data.get("user_id")
    if not team_id or not user_id:
        raise ValidationError({"detail": "team_id and user_id are required."})
 
    team = get_object_or_404(Team, id=team_id)
 
    if not is_admin(request.user, team.workspace):
        raise PermissionDenied({"detail": "Admins only."})
 
    if not Membership.objects.filter(user_id=user_id, workspace=team.workspace).exists():
        raise ValidationError({"detail": "User is not a workspace member."})
 
    if request.method == "DELETE":
        TeamMembership.objects.filter(team=team, user_id=user_id).delete()
        return Response({"message": "Removed from team."})
 
    membership, created = TeamMembership.objects.get_or_create(
        team=team, user_id=user_id, defaults={"role": "member"}
    )
    return Response({"created": created}, status=status.HTTP_201_CREATED if created else status.HTTP_200_OK)
 
 
# ------------------------------------------------------------------ #
# Channels                                                            #
# ------------------------------------------------------------------ #
 
@api_view(["GET", "POST"])
@permission_classes([IsAuthenticated])
def workspace_channels(request, workspace_id):
    workspace = get_object_or_404(Workspace, id=workspace_id)
    if not Membership.objects.filter(user=request.user, workspace=workspace).exists():
        raise PermissionDenied({"detail": "Not a member."})
 
    if request.method == "GET":
        qs = Channel.objects.filter(workspace=workspace, is_archived=False)
        # Guests/private: only show channels they're a member of
        membership = Membership.objects.get(user=request.user, workspace=workspace)
        if membership.role == "guest":
            qs = qs.filter(memberships__user=request.user)
        return Response(ChannelSerializer(qs, many=True).data)
 
    # POST — create channel
    if not check_workspace_permission(request.user.id, str(workspace_id), "channel.create"):
        raise PermissionDenied({"detail": "Cannot create channel."})
 
    name = request.data.get("name", "").strip()
    if not name:
        raise ValidationError({"detail": "Channel name is required."})
 
    channel = create_channel_service(
        workspace=workspace,
        name=name,
        created_by=request.user,
        is_private=request.data.get("is_private", False),
        topic=request.data.get("topic", ""),
    )
    return Response(ChannelSerializer(channel).data, status=status.HTTP_201_CREATED)
 
 
@api_view(["GET", "PATCH", "DELETE"])
@permission_classes([IsAuthenticated])
def channel_detail(request, channel_id):
    channel = get_object_or_404(Channel, id=channel_id)
    if not ChannelMembership.objects.filter(user=request.user, channel=channel).exists():
        raise PermissionDenied({"detail": "Not a channel member."})
 
    if request.method == "GET":
        return Response(ChannelSerializer(channel).data)
 
    if not is_admin(request.user, channel.workspace):
        raise PermissionDenied({"detail": "Admins only."})
 
    if request.method == "DELETE":
        archive_channel_service(channel, request.user)
        return Response({"message": "Channel archived."})
 
    for field in ("name", "topic", "description"):
        if field in request.data:
            setattr(channel, field, request.data[field])
    channel.save()
    return Response(ChannelSerializer(channel).data)
 
 
@api_view(["GET"])
@permission_classes([IsAuthenticated])
def channel_messages(request, channel_id):
    channel = get_object_or_404(Channel, id=channel_id)
    if not ChannelMembership.objects.filter(user=request.user, channel=channel).exists():
        raise PermissionDenied({"detail": "Not a channel member."})
 
    try:
        limit  = min(int(request.query_params.get("limit", 50)), 200)
        before = request.query_params.get("before")   # cursor-based pagination
    except ValueError:
        raise ValidationError({"detail": "limit must be an integer."})
 
    qs = Message.objects.filter(
        channel=channel, is_deleted=False, parent__isnull=True
    ).prefetch_related("reactions", "replies").order_by("-created_at")
 
    if before:
        qs = qs.filter(created_at__lt=before)
 
    messages = list(qs[:limit])
    return Response({
        "results":  MessageSerializer(reversed(messages), many=True).data,
        "has_more": qs.count() > limit,
    })
 
 
# ------------------------------------------------------------------ #
# Notifications                                                       #
# ------------------------------------------------------------------ #
 
@api_view(["GET"])
@permission_classes([IsAuthenticated])
def list_notifications(request):
    qs = Notification.objects.filter(user=request.user)
    workspace = getattr(request, "workspace", None)
    if workspace:
        qs = qs.filter(workspace=workspace)
 
    if request.query_params.get("unread") == "true":
        qs = qs.filter(is_read=False)
 
    return Response(NotificationSerializer(qs[:50], many=True).data)
 
 
@api_view(["POST"])
@permission_classes([IsAuthenticated])
def mark_notifications_read(request):
    workspace = getattr(request, "workspace", None)
    qs = Notification.objects.filter(user=request.user, is_read=False)
    if workspace:
        qs = qs.filter(workspace=workspace)
    qs.update(is_read=True)
    return Response({"status": "marked_read"})