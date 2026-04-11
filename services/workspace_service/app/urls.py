from django.urls import path
from .views import (
    create_workspace,
    list_workspaces,
    workspace_detail,
    invite_user,
    accept_invitation,
    create_team,
    add_team_member,
    switch_workspace,
    workspace_members,
    membership_detail,
    list_workspace_teams,
    team_members,
)

urlpatterns = [
    path('workspaces/', create_workspace),
    path('workspaces/list/', list_workspaces),
    path('workspaces/<uuid:workspace_id>/', workspace_detail),
    path('workspaces/<uuid:workspace_id>/members/', workspace_members),
    path('workspaces/<uuid:workspace_id>/teams/', list_workspace_teams),
    path('workspaces/switch/', switch_workspace),
    path('invitations/', invite_user),
    path('invitations/accept/', accept_invitation),
    path('memberships/<uuid:membership_id>/', membership_detail),
    path('teams/', create_team),
    path('team-members/', team_members),
]