from django.db import transaction
from .models import Workspace, Membership, Invitation, Notification
from django.core.mail import send_mail
from django.utils import timezone
from datetime import timedelta
from django.conf import settings
from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer

def create_workspace_service(user, name):
    with transaction.atomic():
        workspace = Workspace.objects.create(
            name=name,
            owner=user
        )

        Membership.objects.create(
            user=user,
            workspace=workspace,
            role="admin"
        )

    return workspace

def send_invitation_email(invitation):
    subject = f"Invitation to join {invitation.workspace.name}"
    invite_link = f"{settings.FRONTEND_URL}/invite/{invitation.token}"
    message = (
        f"You've been invited to join {invitation.workspace.name} as {invitation.role}.\n\n"
        f"Accept here: {invite_link}"
    )

    send_mail(
        subject,
        message,
        settings.DEFAULT_FROM_EMAIL,
        [invitation.email],
    )


def is_admin(user, workspace):
    return Membership.objects.filter(
        user=user,
        workspace=workspace,
        role="admin"
    ).exists()


def is_member(user, workspace):
    return Membership.objects.filter(
        user=user,
        workspace=workspace
    ).exists()


def invite_user_service(workspace, email, role, invited_by):
    invitation = Invitation.objects.create(
        workspace=workspace,
        email=email,
        role=role,
        invited_by=invited_by,
        expires_at=timezone.now() + timedelta(days=7)
    )

    send_invitation_email(invitation)
    return invitation


def accept_invitation_service(user, token):
    invitation = Invitation.objects.get(token=token)

    if not invitation.is_valid():
        raise ValueError("Invalid or expired invitation")

    membership, created = Membership.objects.get_or_create(
        user=user,
        workspace=invitation.workspace,
        defaults={"role": invitation.role},
    )

    invitation.status = "accepted"
    invitation.save()

    if created:
        notify_user(
            user,
            invitation.workspace,
            f"You have joined the workspace {invitation.workspace.name}.",
        )
        broadcast_workspace_notification(
            invitation.workspace,
            f"{user.email} has joined the workspace.",
        )

    return invitation.workspace


def persist_notification(user, workspace, message):
    Notification.objects.create(
        user=user,
        workspace=workspace,
        message=message,
    )


def notify_user(user, workspace, message):
    persist_notification(user, workspace, message)
    layer = get_channel_layer()
    async_to_sync(layer.group_send)(
        f"user_{user.id}",
        {
            "type": "notification_message",
            "message": message,
        },
    )


def broadcast_workspace_notification(workspace, message):
    layer = get_channel_layer()
    async_to_sync(layer.group_send)(
        f"workspace_{workspace.id}",
        {
            "type": "notification_message",
            "message": message,
        },
    )
