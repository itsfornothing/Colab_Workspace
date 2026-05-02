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