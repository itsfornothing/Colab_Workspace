"""
Custom JWT authentication that auto-creates ChatUser records
when a valid token from user_service is presented.
"""
from django.contrib.auth import get_user_model
from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework_simplejwt.exceptions import InvalidToken

User = get_user_model()


class ChatJWTAuthentication(JWTAuthentication):
    def get_user(self, validated_token):
        try:
            user_id = validated_token.get("user_id")
            if not user_id:
                raise InvalidToken("No user_id in token")

            user, _ = User.objects.get_or_create(
                id=user_id,
                defaults={"username": f"user_{str(user_id)[:8]}"},
            )
            return user
        except Exception as e:
            raise InvalidToken(str(e))
