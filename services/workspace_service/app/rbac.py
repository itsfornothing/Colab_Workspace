from django.core.cache import cache
 
# ------------------------------------------------------------------ #
# Permission matrix                                                   #
# ------------------------------------------------------------------ #
 
PERMISSIONS: dict[str, set] = {
    "owner": {
        # Workspace
        "workspace.view", "workspace.update", "workspace.delete",
        "workspace.transfer_ownership",
        # Members
        "member.list", "member.invite", "member.remove", "member.update_role",
        # Teams
        "team.create", "team.update", "team.delete",
        "team.add_member", "team.remove_member",
        # Channels
        "channel.create", "channel.update", "channel.delete",
        "channel.archive", "channel.add_member", "channel.remove_member",
        "channel.pin_message",
        # Messages
        "message.send", "message.edit_own", "message.delete_own",
        "message.delete_any",
        # Invitations
        "invitation.create", "invitation.revoke",
        # Admin
        "admin.manage_roles", "admin.view_audit_log",
    },
    "admin": {
        "workspace.view", "workspace.update",
        "member.list", "member.invite", "member.remove", "member.update_role",
        "team.create", "team.update", "team.delete",
        "team.add_member", "team.remove_member",
        "channel.create", "channel.update", "channel.delete",
        "channel.archive", "channel.add_member", "channel.remove_member",
        "channel.pin_message",
        "message.send", "message.edit_own", "message.delete_own",
        "message.delete_any",
        "invitation.create", "invitation.revoke",
        "admin.manage_roles", "admin.view_audit_log",
    },
    "member": {
        "workspace.view",
        "member.list",
        "team.create",           # members can create teams
        "team.add_member",
        "channel.create",        # members can create public channels
        "channel.add_member",
        "channel.pin_message",
        "message.send", "message.edit_own", "message.delete_own",
    },
    "guest": {
        "workspace.view",
        "member.list",
        "message.send",          # guests can send in channels they're added to
        "message.edit_own",
        "message.delete_own",
    },
}
 
# Role hierarchy for >= comparisons
HIERARCHY = {"owner": 4, "admin": 3, "member": 2, "guest": 1}
 
 
def has_permission(role: str, action: str) -> bool:
    """Return True if `role` is allowed to perform `action`."""
    return action in PERMISSIONS.get(role, set())
 
 
def role_gte(role: str, min_role: str) -> bool:
    """Return True if `role` is at least as powerful as `min_role`."""
    return HIERARCHY.get(role, 0) >= HIERARCHY.get(min_role, 999)
 
 
def get_permissions(role: str) -> set:
    """Return all permissions for a role."""
    return PERMISSIONS.get(role, set())
 
 
def check_workspace_permission(user_id, workspace_id: str, action: str) -> bool:
    """
    Check permission with Redis caching.
    Cache key: rbac:<user_id>:<workspace_id> → role string
    """
    cache_key = f"rbac:{user_id}:{workspace_id}"
    role = cache.get(cache_key)
 
    if role is None:
        from .models import Membership
        try:
            m = Membership.objects.get(user_id=user_id, workspace_id=workspace_id)
            role = m.role
        except Membership.DoesNotExist:
            role = ""
        cache.set(cache_key, role, timeout=300)
 
    return has_permission(role, action)
 
 
def invalidate_rbac_cache(user_id, workspace_id: str) -> None:
    """Call whenever a membership role changes."""
    cache.delete(f"rbac:{user_id}:{workspace_id}")