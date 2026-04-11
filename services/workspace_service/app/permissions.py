from rest_framework.permissions import BasePermission
from .models import Membership
from rest_framework.response import Response
from functools import wraps
from django.core.cache import cache



class IsWorkspaceAdmin(BasePermission):
    def has_permission(self, request, view):
        workspace_id = None

        if hasattr(request, "workspace") and request.workspace:
            workspace_id = str(request.workspace.id)
        else:
            workspace_id = request.data.get("workspace_id") or request.query_params.get("workspace_id")

        if not workspace_id:
            return False

        return Membership.objects.filter(
            user=request.user,
            workspace_id=workspace_id,
            role="admin"
        ).exists()
    

def require_workspace(view_func):
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        if not getattr(request, "workspace", None):
            return Response({"error": "Workspace required"}, status=400)
        return view_func(request, *args, **kwargs)
    return wrapper


def require_role(allowed_roles):
    def decorator(view_func):
        @wraps(view_func)
        def wrapper(request, *args, **kwargs):
            if not getattr(request, "membership", None):
                return Response({"error": "Not a member"}, status=403)

            if not getattr(request, "workspace", None):
                return Response({"error": "Workspace required"}, status=400)

            cache_key = f"perm_{request.user.id}_{request.workspace.id}"
            role = cache.get(cache_key)

            if role is None:
                role = request.membership.role
                cache.set(cache_key, role, timeout=300)

            if role not in allowed_roles:
                return Response({"error": "Permission denied"}, status=403)

            return view_func(request, *args, **kwargs)
        return wrapper
    return decorator


def require_membership(view_func):
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        if not getattr(request, "workspace", None):
            return Response({"error": "Workspace required"}, status=400)

        exists = Membership.objects.filter(
            user=request.user,
            workspace=request.workspace
        ).exists()

        if not exists:
            return Response({"error": "Not a member"}, status=403)

        return view_func(request, *args, **kwargs)
    return wrapper