"""
Firebase Cloud Messaging helper.

BUG FIX: Original code called firebase_admin.initialize_app() at module
level unconditionally. If the module is imported more than once (Django
dev server reload, test suite), it raises:
  ValueError: The default Firebase app already exists.

Fixed with the standard _apps guard.

ADDED: send_push_batch() for sending to multiple tokens efficiently.
ADDED: Proper error handling for UnregisteredError (stale tokens).
"""

import logging
import firebase_admin
from firebase_admin import credentials, messaging
from django.conf import settings

logger = logging.getLogger(__name__)

if not firebase_admin._apps:
    cred = credentials.Certificate(
        getattr(settings, "FIREBASE_CREDENTIALS_PATH", "firebase.json")
    )
    firebase_admin.initialize_app(cred)


def send_push(token: str, title: str, body: str, data: dict = None) -> bool:
    """
    Send a push notification to a single FCM token.
    Returns True on success, False on failure.
    """
    if not token:
        return False

    message = messaging.Message(
        notification=messaging.Notification(title=title, body=body),
        data={str(k): str(v) for k, v in (data or {}).items()},
        token=token,
    )

    try:
        messaging.send(message)
        return True
    except messaging.UnregisteredError:
        logger.warning("FCM token unregistered: %s…", token[:20])
        return False
    except messaging.SenderIdMismatchError:
        logger.error("FCM sender ID mismatch for token %s…", token[:20])
        return False
    except Exception:
        logger.exception("FCM send failed for token %s…", token[:20])
        return False


def send_push_batch(tokens: list, title: str, body: str, data: dict = None) -> dict:
    """
    Send the same notification to multiple FCM tokens using MulticastMessage.
    Returns {"success": n, "failure": n}.
    """
    if not tokens:
        return {"success": 0, "failure": 0}

    message = messaging.MulticastMessage(
        notification=messaging.Notification(title=title, body=body),
        data={str(k): str(v) for k, v in (data or {}).items()},
        tokens=tokens[:500],  # FCM limit per batch
    )

    try:
        response = messaging.send_each_for_multicast(message)
        return {
            "success": response.success_count,
            "failure": response.failure_count,
        }
    except Exception:
        logger.exception("FCM multicast failed")
        return {"success": 0, "failure": len(tokens)}