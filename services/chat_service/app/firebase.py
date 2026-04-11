import logging
import firebase_admin
from firebase_admin import credentials, messaging
from django.conf import settings

logger = logging.getLogger(__name__)

# Initialize only once (guard against re-import during dev reload)
if not firebase_admin._apps:
    cred = credentials.Certificate(settings.FIREBASE_CREDENTIALS_PATH)
    firebase_admin.initialize_app(cred)


def send_push(token: str, title: str, body: str) -> bool:
    """
    Send a push notification to a single FCM device token.
    Returns True on success, False on failure.
    """
    if not token:
        return False

    message = messaging.Message(
        notification=messaging.Notification(title=title, body=body),
        token=token,
    )

    try:
        messaging.send(message)
        return True
    except messaging.UnregisteredError:
        logger.warning("FCM token is no longer registered: %s", token[:20])
        return False
    except Exception:
        logger.exception("Failed to send push to token %s", token[:20])
        return False


def send_push_to_channel_members(channel_id, sender, body: str) -> None:
    """
    Send push notifications to all channel members who have an FCM token,
    excluding the sender themselves.

    Assumes your User model has an optional `fcm_token` field.
    Adjust the queryset if your token is stored elsewhere (e.g. a Profile model).
    """
    from django.contrib.auth import get_user_model
    from .models import ChannelMember

    User = get_user_model()

    members = (
        ChannelMember.objects
        .filter(channel_id=channel_id)
        .exclude(user=sender)
        .select_related("user")
    )

    title = f"New message from {sender}"

    for member in members:
        token = getattr(member.user, "fcm_token", None)
        if token:
            send_push(token, title, body)