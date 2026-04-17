from django.urls import path
from .views import (
    create_workspace, list_workspaces, workspace_detail,
    workspace_members, membership_detail,
    invite_user, accept_invitation,
    create_invite_link, accept_invite_link,
    create_team, list_workspace_teams, team_members,
    workspace_channels, channel_detail, channel_messages,
    switch_workspace,
    list_notifications, mark_notifications_read,
)

urlpatterns = [
    # Workspaces
    path("workspaces/",                              create_workspace),         # POST
    path("workspaces/list/",                         list_workspaces),          # GET
    path("workspaces/switch/",                       switch_workspace),         # POST
    path("workspaces/<uuid:workspace_id>/",          workspace_detail),         # GET, PATCH, DELETE
    path("workspaces/<uuid:workspace_id>/members/",  workspace_members),        # GET
    path("workspaces/<uuid:workspace_id>/teams/",    list_workspace_teams),     # GET
    path("workspaces/<uuid:workspace_id>/channels/", workspace_channels),       # GET, POST
    path("workspaces/<uuid:workspace_id>/invites/",  create_invite_link),       # POST

    # Members
    path("memberships/<uuid:membership_id>/",        membership_detail),        # PATCH, DELETE

    # Invitations
    path("invitations/",                             invite_user),              # POST
    path("invitations/accept/",                      accept_invitation),        # POST
    path("invitations/join/",                        accept_invite_link),       # POST

    # Teams
    path("teams/",                                   create_team),              # POST
    path("team-members/",                            team_members),             # GET, POST, DELETE

    # Channels
    path("channels/<uuid:channel_id>/",              channel_detail),           # GET, PATCH, DELETE
    path("channels/<uuid:channel_id>/messages/",     channel_messages),         # GET

    # Notifications
    path("notifications/",                           list_notifications),       # GET
    path("notifications/mark-read/",                 mark_notifications_read),  # POST
]