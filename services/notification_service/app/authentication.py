"""
Custom JWT authentication for workspace-service.

The workspace-service does not own user accounts — those live in user-service.
When a valid JWT arrives, we auto-create/get a local Django auth.User record
using the UUID from the token's `user_id` claim as the username.
This lets all FK relationships (Workspace.owner, Membership.user, etc.) work
without requiring a separate user database.
"""
from django.contrib.auth.models import User
from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework_simplejwt.exceptions import InvalidToken, TokenError


class RemoteUserJWTAuthentication(JWTAuthentication):
    """
    Validates the JWT signature/expiry normally, then resolves (or creates)
    a local Django User whose username == the UUID from the token's user_id claim.
    """

    def get_user(self, validated_token):
        try:
            user_id = str(validated_token.get("user_id", ""))
            if not user_id:
                raise InvalidToken("Token contained no recognizable user identification")

            # Use the UUID as username; create the local shadow user if needed
            user, _ = User.objects.get_or_create(
                username=user_id,
                defaults={
                    "email": validated_token.get("email", f"{user_id}@remote"),
                    "is_active": True,
                },
            )
            return user
        except Exception as exc:
            raise InvalidToken(f"Token user resolution failed: {exc}") from exc
