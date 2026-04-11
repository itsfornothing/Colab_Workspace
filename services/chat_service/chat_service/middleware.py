from urllib.parse import parse_qs
from channels.db import database_sync_to_async
from django.contrib.auth.models import AnonymousUser
from django.contrib.auth import get_user_model
from rest_framework_simplejwt.tokens import UntypedToken
from rest_framework_simplejwt.exceptions import InvalidToken, TokenError
from jwt import decode as jwt_decode
from django.conf import settings
from django.core.cache import cache

User = get_user_model()


@database_sync_to_async
def get_user_from_token(token):
    """
    Validate JWT token and return the corresponding User object.
    Returns AnonymousUser on any failure.
    """
    try:
        # Check Redis cache first
        cached_user_id = cache.get(f"session:{token}")
        if cached_user_id:
            return User.objects.get(id=cached_user_id)

        # Validate token signature/expiry
        UntypedToken(token)

        # Decode to get user_id
        decoded = jwt_decode(
            token,
            settings.SIMPLE_JWT["SIGNING_KEY"],
            algorithms=[settings.SIMPLE_JWT.get("ALGORITHM", "HS256")],
        )
        user_id = decoded.get("user_id")
        if not user_id:
            return AnonymousUser()

        user = User.objects.get(id=user_id)

        # Cache for 5 minutes to reduce DB hits
        cache.set(f"session:{token}", user.id, timeout=300)
        return user

    except (InvalidToken, TokenError, User.DoesNotExist, Exception):
        return AnonymousUser()


class JWTAuthMiddleware:
    """
    ASGI middleware that authenticates WebSocket connections via a JWT token
    passed as a query parameter: ws://host/ws/chat/123/?token=<jwt>
    """

    def __init__(self, inner):
        self.inner = inner

    async def __call__(self, scope, receive, send):
        query_string = scope.get("query_string", b"").decode()
        params = parse_qs(query_string)
        token = params.get("token", [None])[0]

        if token:
            scope["user"] = await get_user_from_token(token)
        else:
            scope["user"] = AnonymousUser()

        return await self.inner(scope, receive, send)