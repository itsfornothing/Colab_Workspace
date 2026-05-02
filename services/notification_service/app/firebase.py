"""Firebase Cloud Messaging helper — lazy import so firebase_admin is optional."""
import logging
logger = logging.getLogger(__name__)


def _init():
    try:
        import firebase_admin
        from firebase_admin import credentials
        from django.conf import settings
        cred_path = getattr(settings, "FIREBASE_CREDENTIALS_PATH", None)
        if cred_path and not firebase_admin._apps:
            cred = credentials.Certificate(cred_path)
            firebase_admin.initialize_app(cred)
        return True
    except (ImportError, Exception):
        return False


def send_push(token: str, title: str, body: str, data: dict = None) -> bool:
    if not token or not _init():
        return False
    try:
        from firebase_admin import messaging
        message = messaging.Message(
            notification=messaging.Notification(title=title, body=body),
            data={str(k): str(v) for k, v in (data or {}).items()},
            token=token,
        )
        messaging.send(message)
        return True
    except Exception:
        logger.exception("FCM send failed for token %s…", token[:20])
        return False


def send_push_batch(tokens: list, title: str, body: str, data: dict = None) -> dict:
    if not tokens or not _init():
        return {"success": 0, "failure": 0}
    try:
        from firebase_admin import messaging
        message = messaging.MulticastMessage(
            notification=messaging.Notification(title=title, body=body),
            data={str(k): str(v) for k, v in (data or {}).items()},
            tokens=tokens[:500],
        )
        response = messaging.send_each_for_multicast(message)
        return {"success": response.success_count, "failure": response.failure_count}
    except Exception:
        logger.exception("FCM multicast failed")
        return {"success": 0, "failure": len(tokens)}
