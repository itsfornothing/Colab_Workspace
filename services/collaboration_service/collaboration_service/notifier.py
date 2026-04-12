import logging
import threading
import requests
from django.conf import settings
 
logger = logging.getLogger(__name__)
 
NOTIFICATION_SERVICE_URL = getattr(
    settings, "NOTIFICATION_SERVICE_URL", "http://notification-service/api"
)
 
 
def _post_event(payload: dict) -> None:
    try:
        resp = requests.post(
            f"{NOTIFICATION_SERVICE_URL}/events/",
            json=payload,
            timeout=3,
        )
        if not resp.ok:
            logger.warning(
                "Notification service returned %s: %s", resp.status_code, resp.text
            )
    except requests.RequestException:
        logger.exception("Failed to reach notification service")
 
 
def _fire(payload: dict) -> None:
    t = threading.Thread(target=_post_event, args=(payload,), daemon=True)
    t.start()
 
 
# ------------------------------------------------------------------ #
# Public helpers                                                       #
# ------------------------------------------------------------------ #
 
def notify_user_invited(user_id: str, email: str, workspace_name: str, workspace_id: str = None) -> None:
    _fire({
        "event_type": "user_invited",
        "payload": {
            "user_id":        user_id,
            "email":          email,
            "workspace_name": workspace_name,
            "workspace_id":   workspace_id,
        },
    })
 
 
def notify_system_alert(user_id: str, title: str, message: str, priority: str = "medium") -> None:
    _fire({
        "event_type": "system_alert",
        "payload": {
            "user_id":  user_id,
            "title":    title,
            "message":  message,
            "priority": priority,
        },
    })
 