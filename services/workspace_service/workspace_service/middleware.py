from urllib.parse import parse_qs
from django.contrib.auth.models import AnonymousUser
 
 
# ------------------------------------------------------------------ #
# HTTP Workspace Context Middleware                                    #
# ------------------------------------------------------------------ #
 
class WorkspaceMiddleware:
    """
    Attaches request.workspace and request.membership from either:
      1. X-Workspace-ID request header (preferred for API clients)
      2. workspace_id URL kwarg (for URL-based views)
 
    Sets both to None if the workspace doesn't exist or user isn't a member.
    """
 
    def __init__(self, get_response):
        self.get_response = get_response
 
    def __call__(self, request):
        # Lazy import — avoids AppRegistryNotReady at startup
        from ..app.models import Workspace, Membership
 
        request.workspace  = None
        request.membership = None
 
        workspace_id = request.headers.get("X-Workspace-ID")
 
        if not workspace_id:
            # Try to extract from URL resolver kwargs
            resolver_match = getattr(request, "resolver_match", None)
            if resolver_match:
                workspace_id = resolver_match.kwargs.get("workspace_id")
 
        if workspace_id and getattr(request, "user", None) and request.user.is_authenticated:
            try:
                workspace  = Workspace.objects.select_related("owner").get(id=workspace_id)
                membership = Membership.objects.filter(
                    user=request.user, workspace=workspace
                ).first()
 
                if membership:
                    request.workspace  = workspace
                    request.membership = membership
 
            except (Workspace.DoesNotExist, Exception):
                pass
 
        return self.get_response(request)
 
 
# ------------------------------------------------------------------ #
# JWT Auth Middleware for WebSocket                                    #
# ------------------------------------------------------------------ #
 
from channels.db import database_sync_to_async
from rest_framework_simplejwt.tokens import UntypedToken
from rest_framework_simplejwt.exceptions import InvalidToken, TokenError
from jwt import decode as jwt_decode
from django.conf import settings
from django.core.cache import cache
 
 
@database_sync_to_async
def _get_user_from_token(token: str):
    from django.contrib.auth import get_user_model
    User = get_user_model()
    try:
        cached_id = cache.get(f"ws_session:{token}")
        if cached_id:
            return User.objects.get(id=cached_id)
 
        UntypedToken(token)
        decoded = jwt_decode(
            token,
            settings.SIMPLE_JWT["SIGNING_KEY"],
            algorithms=[settings.SIMPLE_JWT.get("ALGORITHM", "HS256")],
        )
        user_id = decoded.get("user_id")
        if not user_id:
            return AnonymousUser()
 
        user = User.objects.get(id=user_id)
        cache.set(f"ws_session:{token}", user.id, timeout=300)
        return user
    except (InvalidToken, TokenError, Exception):
        return AnonymousUser()
 
 
class JWTAuthMiddleware:
    """Authenticates WebSocket connections via ?token=<jwt> query param."""
 
    def __init__(self, inner):
        self.inner = inner
 
    async def __call__(self, scope, receive, send):
        if scope["type"] == "websocket":
            qs    = parse_qs(scope.get("query_string", b"").decode())
            token = qs.get("token", [None])[0]
            scope["user"] = (
                await _get_user_from_token(token) if token else AnonymousUser()
            )
        return await self.inner(scope, receive, send)