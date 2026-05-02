import logging
logger = logging.getLogger(__name__)


def _init_firebase():
    try:
        import firebase_admin
        from firebase_admin import credentials
        from django.conf import settings
        cred_path = getattr(settings, 'FIREBASE_CREDENTIALS_PATH', None)
        if cred_path and not firebase_admin._apps:
            cred = credentials.Certificate(cred_path)
            firebase_admin.initialize_app(cred)
        return True
    except (ImportError, Exception):
        return False


def send_push(token: str, title: str, body: str) -> bool:
    if not token or not _init_firebase():
        return False
    try:
        from firebase_admin import messaging
        message = messaging.Message(
            notification=messaging.Notification(title=title, body=body),
            token=token,
        )
        messaging.send(message)
        return True
    except Exception:
        logger.exception("Failed to send push to token %s", token[:20])
        return False


def send_push_to_channel_members(channel_id, sender, body: str) -> None:
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
