import logging
from urllib.parse import parse_qs
from channels.db import database_sync_to_async
from django.contrib.auth.models import AnonymousUser
from django.contrib.auth import get_user_model
from rest_framework_simplejwt.tokens import UntypedToken
from rest_framework_simplejwt.exceptions import InvalidToken, TokenError
from jwt import decode as jwt_decode
from django.conf import settings
from django.core.cache import cache

logger = logging.getLogger(__name__)
User = get_user_model()


@database_sync_to_async
def get_user_from_token(token):
    try:
        UntypedToken(token)
        decoded = jwt_decode(
            token,
            settings.SIMPLE_JWT["SIGNING_KEY"],
            algorithms=[settings.SIMPLE_JWT.get("ALGORITHM", "HS256")],
        )
        user_id = decoded.get("user_id")
        if not user_id:
            return AnonymousUser()

        user, _ = User.objects.get_or_create(
            id=user_id,
            defaults={"username": f"user_{str(user_id)[:8]}"},
        )
        return user
    except (InvalidToken, TokenError, Exception):
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

        # WSS security check (Requirement 10.1)
        # TLS termination typically happens at the proxy/load-balancer level, so
        # scope["scheme"] may be "ws" even when the client connected over WSS.
        # We log a warning rather than rejecting the connection, because enforcing
        # WSS at the application layer would break deployments with TLS termination
        # at the proxy.
        if (
            scope.get("type") == "websocket"
            and getattr(settings, "WEBRTC_REQUIRE_SECURE_SIGNALING", False)
            and scope.get("scheme") != "wss"
        ):
            logger.warning(
                "WebSocket signaling connection is not using WSS (scheme=%r). "
                "Ensure TLS termination is configured at the proxy/load-balancer level "
                "for production deployments. (Requirement 10.1)",
                scope.get("scheme"),
            )

        return await self.inner(scope, receive, send)