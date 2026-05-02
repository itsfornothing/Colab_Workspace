from functools import wraps
from rest_framework.permissions import BasePermission
from rest_framework.exceptions import PermissionDenied, ValidationError, NotFound
from .models import Membership
from .rbac import check_workspace_permission, has_permission, invalidate_rbac_cache
 
 
# ------------------------------------------------------------------ #
# DRF Permission Classes                                              #
# ------------------------------------------------------------------ #
 
class IsWorkspaceMember(BasePermission):
    """Requires the user to be a member of request.workspace."""
    def has_permission(self, request, view):
        if not getattr(request, "workspace", None):
            return False
        return Membership.objects.filter(
            user=request.user, workspace=request.workspace
        ).exists()
 
 
class IsWorkspaceAdmin(BasePermission):
    """Requires admin or owner role in request.workspace."""
    def has_permission(self, request, view):
        workspace = getattr(request, "workspace", None)
        if not workspace:
            workspace_id = (
                request.data.get("workspace_id")
                or request.query_params.get("workspace_id")
            )
            if not workspace_id:
                return False
            from .models import Workspace
            try:
                workspace = Workspace.objects.get(id=workspace_id)
            except Workspace.DoesNotExist:
                return False
 
        return Membership.objects.filter(
            user=request.user,
            workspace=workspace,
            role__in=["admin", "owner"],
        ).exists()
 
 
class WorkspacePermission(BasePermission):
    """
    Action-based permission check against the RBAC matrix.
 
    Usage:
        class MyView(APIView):
            required_action = "channel.create"
            permission_classes = [IsAuthenticated, WorkspacePermission]
    """
    required_action = None
 
    def has_permission(self, request, view):
        action = getattr(view, "required_action", self.required_action)
        if not action:
            return True
 
        workspace = getattr(request, "workspace", None)
        if not workspace:
            return False
 
        return check_workspace_permission(request.user.id, str(workspace.id), action)
 
 
# ------------------------------------------------------------------ #
# Function-based view decorators                                      #
# ------------------------------------------------------------------ #
 
def require_workspace(view_func):
    """
    Raises ValidationError (400) if X-Workspace-ID header is missing or invalid.
    BUG FIX: now raises DRF exceptions instead of returning bare Response().
    """
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        if not getattr(request, "workspace", None):
            raise ValidationError({"detail": "A valid X-Workspace-ID header is required."})
        return view_func(request, *args, **kwargs)
    return wrapper
 
 
def require_role(*allowed_roles):
    """
    Decorator that checks the user's role in request.workspace against allowed_roles.
    Uses Redis-cached RBAC check.
 
    Usage:
        @require_role("admin", "owner")
        def my_view(request): ...
    """
    def decorator(view_func):
        @wraps(view_func)
        def wrapper(request, *args, **kwargs):
            workspace = getattr(request, "workspace", None)
            if not workspace:
                raise ValidationError({"detail": "Workspace context required."})
 
            membership = getattr(request, "membership", None)
            if not membership:
                raise PermissionDenied({"detail": "Not a member of this workspace."})
 
            if membership.role not in allowed_roles:
                raise PermissionDenied({
                    "detail": f"Requires one of roles: {', '.join(allowed_roles)}."
                })
            return view_func(request, *args, **kwargs)
        return wrapper
    return decorator
 
 
def require_action(action: str):
    """
    Decorator that checks a fine-grained RBAC action.
 
    Usage:
        @require_action("channel.create")
        def create_channel_view(request): ...
    """
    def decorator(view_func):
        @wraps(view_func)
        def wrapper(request, *args, **kwargs):
            workspace = getattr(request, "workspace", None)
            if not workspace:
                raise ValidationError({"detail": "Workspace context required."})
 
            allowed = check_workspace_permission(
                request.user.id, str(workspace.id), action
            )
            if not allowed:
                raise PermissionDenied({"detail": f"Action '{action}' not permitted."})
            return view_func(request, *args, **kwargs)
        return wrapper
    return decorator
 
 
def require_membership(view_func):
    """Raises PermissionDenied if the user is not a workspace member."""
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        workspace = getattr(request, "workspace", None)
        if not workspace:
            raise ValidationError({"detail": "Workspace context required."})
 
        if not Membership.objects.filter(
            user=request.user, workspace=workspace
        ).exists():
            raise PermissionDenied({"detail": "Not a member of this workspace."})
 
        return view_func(request, *args, **kwargs)
    return wrapper