"""
JWTAuthMiddleware — ASGI middleware that authenticates WebSocket connections.

The original asgi.py had NO authentication middleware on the WebSocket route,
meaning scope["user"] was never set — every consumer access to self.user
would raise KeyError or AttributeError.

Usage:
    ws://host/ws/docs/<document_id>/?token=<jwt>
"""

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
def get_user_from_token(token: str):
    try:
        # Fast path: local Django PK cached in Redis
        cached_pk = cache.get(f"ws_session:{token}")
        if cached_pk:
            return User.objects.get(pk=cached_pk)

        # Validate token signature and expiry (raises on failure)
        UntypedToken(token)

        decoded = jwt_decode(
            token,
            settings.SIMPLE_JWT["SIGNING_KEY"],
            algorithms=[settings.SIMPLE_JWT.get("ALGORITHM", "HS256")],
        )
        # user_id in the JWT is the UUID from user-service, stored as the
        # local shadow user's *username* (see RemoteUserJWTAuthentication).
        # We must NOT do User.objects.get(id=user_id) — that would try to
        # cast the UUID string to an integer PK and raise TypeError.
        user_id = str(decoded.get("user_id", ""))
        if not user_id:
            return AnonymousUser()

        user, _ = User.objects.get_or_create(
            username=user_id,
            defaults={
                "email": decoded.get("email", f"{user_id}@remote"),
                "is_active": True,
            },
        )
        cache.set(f"ws_session:{token}", user.pk, timeout=300)
        return user

    except (InvalidToken, TokenError, User.DoesNotExist, Exception):
        return AnonymousUser()


class JWTAuthMiddleware:
    def __init__(self, inner):
        self.inner = inner

    async def __call__(self, scope, receive, send):
        if scope["type"] == "websocket":
            qs = parse_qs(scope.get("query_string", b"").decode())
            token = qs.get("token", [None])[0]
            scope["user"] = (
                await get_user_from_token(token) if token else AnonymousUser()
            )
        return await self.inner(scope, receive, send)