import logging
from django.db import transaction
from django.core.mail import send_mail
from django.utils import timezone
from datetime import timedelta
from django.conf import settings
from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
 
from .models import (
    Workspace, Membership, Invitation, WorkspaceInviteLink,
    Notification, Channel, ChannelMembership, Team, TeamMembership,
)
from .rbac import invalidate_rbac_cache
 
logger = logging.getLogger(__name__)
 
 
# ------------------------------------------------------------------ #
# Workspace                                                           #
# ------------------------------------------------------------------ #
 
def create_workspace_service(user, name: str, description: str = "") -> Workspace:
    with transaction.atomic():
        workspace = Workspace.objects.create(
            name=name, description=description, owner=user
        )
        Membership.objects.create(user=user, workspace=workspace, role="owner")
        # Auto-create a #general channel
        channel = Channel.objects.create(
            workspace=workspace,
            name="general",
            created_by=user,
        )
        ChannelMembership.objects.create(user=user, channel=channel)
 
    logger.info("Workspace %s created by %s", workspace.id, user)
    return workspace
 
 
def delete_workspace_service(user, workspace: Workspace) -> None:
    if workspace.owner != user:
        from rest_framework.exceptions import PermissionDenied
        raise PermissionDenied("Only the workspace owner can delete it.")
    workspace.delete()
    invalidate_rbac_cache(user.id, str(workspace.id))
 
 
# ------------------------------------------------------------------ #
# Invitations (email-based)                                           #
# ------------------------------------------------------------------ #
 
def send_invitation_email(invitation: Invitation) -> None:
    invite_link = f"{settings.FRONTEND_URL}/invite/{invitation.token}"
    subject = f"Invitation to join {invitation.workspace.name}"
    body = (
        f"You've been invited to join {invitation.workspace.name} as {invitation.role}.\n\n"
        f"Accept here: {invite_link}\n\n"
        f"This link expires in 7 days."
    )
    try:
        send_mail(subject, body, settings.DEFAULT_FROM_EMAIL, [invitation.email])
    except Exception:
        logger.exception("Failed to send invitation email to %s", invitation.email)
 
 
def invite_user_service(workspace: Workspace, email: str, role: str, invited_by) -> Invitation:
    invitation = Invitation.objects.create(
        workspace=workspace,
        email=email,
        role=role,
        invited_by=invited_by,
        expires_at=timezone.now() + timedelta(days=7),
    )
    send_invitation_email(invitation)
    return invitation
 
 
def accept_invitation_service(user, token: str) -> Workspace:
    """
    BUG FIX: select_for_update inside transaction prevents double-accept race.
    """
    with transaction.atomic():
        try:
            invitation = Invitation.objects.select_for_update().get(token=token)
        except Invitation.DoesNotExist:
            raise ValueError("Invalid invitation token.")
 
        if not invitation.is_valid():
            raise ValueError("This invitation has expired or already been used.")
 
        membership, created = Membership.objects.get_or_create(
            user=user,
            workspace=invitation.workspace,
            defaults={"role": invitation.role},
        )
 
        if not created and membership.role != invitation.role:
            # Update role if re-accepting a different-role invite
            membership.role = invitation.role
            membership.save(update_fields=["role"])
            invalidate_rbac_cache(user.id, str(invitation.workspace_id))
 
        invitation.status = "accepted"
        invitation.save(update_fields=["status"])
 
    if created:
        notify_user(user, invitation.workspace,
                    f"You have joined {invitation.workspace.name}.", "invite")
        broadcast_workspace_event(
            invitation.workspace,
            {"type": "member_joined", "user_id": str(user.id), "email": user.email},
        )
 
    return invitation.workspace
 
 
# ------------------------------------------------------------------ #
# Public invite links                                                  #
# ------------------------------------------------------------------ #
 
def create_invite_link_service(workspace: Workspace, created_by, role: str = "member",
                                max_uses: int = None, expires_in_hours: int = 72) -> WorkspaceInviteLink:
    return WorkspaceInviteLink.objects.create(
        workspace=workspace,
        created_by=created_by,
        role=role,
        max_uses=max_uses,
        expires_at=timezone.now() + timedelta(hours=expires_in_hours),
    )
 
 
def accept_invite_link_service(user, token: str) -> Workspace:
    with transaction.atomic():
        try:
            link = WorkspaceInviteLink.objects.select_for_update().get(token=token)
        except WorkspaceInviteLink.DoesNotExist:
            raise ValueError("Invalid invite link.")
 
        if not link.is_valid():
            raise ValueError("This invite link has expired or reached its use limit.")
 
        membership, created = Membership.objects.get_or_create(
            user=user,
            workspace=link.workspace,
            defaults={"role": link.role},
        )
        link.use_count += 1
        link.save(update_fields=["use_count"])
 
    if created:
        broadcast_workspace_event(
            link.workspace,
            {"type": "member_joined", "user_id": str(user.id), "email": user.email},
        )
    return link.workspace
 
 
# ------------------------------------------------------------------ #
# Membership management                                               #
# ------------------------------------------------------------------ #
 
def update_membership_role_service(admin_user, membership: Membership, new_role: str) -> Membership:
    """
    BUG FIX ADDED: invalidate RBAC cache after role change so the
    5-minute cached role doesn't linger.
    """
    old_role = membership.role
    membership.role = new_role
    membership.save(update_fields=["role", "updated_at"])
    invalidate_rbac_cache(membership.user_id, str(membership.workspace_id))
 
    notify_user(
        membership.user,
        membership.workspace,
        f"Your role in {membership.workspace.name} changed from {old_role} to {new_role}.",
        "role",
    )
    return membership
 
 
def remove_member_service(admin_user, membership: Membership) -> None:
    workspace = membership.workspace
    user      = membership.user
    membership.delete()
    invalidate_rbac_cache(user.id, str(workspace.id))
    broadcast_workspace_event(
        workspace,
        {"type": "member_removed", "user_id": str(user.id)},
    )
 
 
# ------------------------------------------------------------------ #
# Channels                                                            #
# ------------------------------------------------------------------ #
 
def create_channel_service(workspace: Workspace, name: str, created_by,
                            is_private: bool = False, topic: str = "") -> Channel:
    with transaction.atomic():
        channel = Channel.objects.create(
            workspace=workspace,
            name=name,
            is_private=is_private,
            topic=topic,
            created_by=created_by,
        )
        ChannelMembership.objects.create(user=created_by, channel=channel)
 
    broadcast_workspace_event(
        workspace,
        {"type": "channel_created", "channel_id": str(channel.id), "name": channel.name},
    )
    return channel
 
 
def archive_channel_service(channel: Channel, archived_by) -> None:
    channel.is_archived = True
    channel.save(update_fields=["is_archived"])
 
 
def add_channel_member_service(channel: Channel, user) -> ChannelMembership:
    membership, _ = ChannelMembership.objects.get_or_create(user=user, channel=channel)
    return membership
 
 
def remove_channel_member_service(channel: Channel, user) -> None:
    ChannelMembership.objects.filter(user=user, channel=channel).delete()
 
 
# ------------------------------------------------------------------ #
# Notifications & WebSocket push                                      #
# ------------------------------------------------------------------ #
 
def persist_notification(user, workspace: Workspace, message: str,
                          notification_type: str = "system", metadata: dict = None) -> Notification:
    return Notification.objects.create(
        user=user,
        workspace=workspace,
        type=notification_type,
        message=message,
        metadata=metadata,
    )
 
 
def notify_user(user, workspace: Workspace, message: str,
                notification_type: str = "system", metadata: dict = None) -> None:
    persist_notification(user, workspace, message, notification_type, metadata)
    layer = get_channel_layer()
    try:
        async_to_sync(layer.group_send)(
            f"user_{user.id}",
            {"type": "notification_message", "message": message, "meta": metadata},
        )
    except Exception:
        logger.exception("WebSocket push failed for user %s", user.id)
 
 
def broadcast_workspace_notification(workspace: Workspace, message: str) -> None:
    layer = get_channel_layer()
    try:
        async_to_sync(layer.group_send)(
            f"workspace_{workspace.id}",
            {"type": "notification_message", "message": message},
        )
    except Exception:
        logger.exception("Workspace broadcast failed for %s", workspace.id)
 
 
def broadcast_workspace_event(workspace: Workspace, data: dict) -> None:
    layer = get_channel_layer()
    try:
        async_to_sync(layer.group_send)(
            f"workspace_{workspace.id}",
            {"type": "workspace_event", "data": data},
        )
    except Exception:
        logger.exception("Workspace event broadcast failed for %s", workspace.id)
 
 
# ------------------------------------------------------------------ #
# Admin helpers                                                       #
# ------------------------------------------------------------------ #
 
def is_admin(user, workspace: Workspace) -> bool:
    return Membership.objects.filter(
        user=user, workspace=workspace, role__in=["admin", "owner"]
    ).exists()
 
 
def is_member(user, workspace: Workspace) -> bool:
    return Membership.objects.filter(user=user, workspace=workspace).exists()