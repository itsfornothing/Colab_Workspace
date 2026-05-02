"""
Audit logging for video call security events.

Provides structured logging for call creation, join, leave, and participant
state change events for security review.

Requirements: 10.7
"""
import logging
import json
from datetime import datetime, timezone

# Dedicated audit logger — configure in settings to write to a separate handler
audit_logger = logging.getLogger('chat_service.audit')


def log_call_created(user_id, room_id, workspace_id=None, ip_address=None):
    """Log when a call room is created."""
    try:
        audit_logger.info(json.dumps({
            "event": "call_created",
            "user_id": str(user_id),
            "room_id": str(room_id),
            "workspace_id": str(workspace_id) if workspace_id else None,
            "ip_address": ip_address,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }))
    except Exception:
        pass


def log_call_joined(user_id, room_id, workspace_id=None, ip_address=None):
    """Log when a user joins a call room."""
    try:
        audit_logger.info(json.dumps({
            "event": "call_joined",
            "user_id": str(user_id),
            "room_id": str(room_id),
            "workspace_id": str(workspace_id) if workspace_id else None,
            "ip_address": ip_address,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }))
    except Exception:
        pass


def log_call_left(user_id, room_id, workspace_id=None, ip_address=None):
    """Log when a user leaves a call room."""
    try:
        audit_logger.info(json.dumps({
            "event": "call_left",
            "user_id": str(user_id),
            "room_id": str(room_id),
            "workspace_id": str(workspace_id) if workspace_id else None,
            "ip_address": ip_address,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }))
    except Exception:
        pass


def log_call_ended(user_id, room_id, workspace_id=None):
    """Log when a call room is ended (all participants left)."""
    try:
        audit_logger.info(json.dumps({
            "event": "call_ended",
            "ended_by_user_id": str(user_id),
            "room_id": str(room_id),
            "workspace_id": str(workspace_id) if workspace_id else None,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }))
    except Exception:
        pass


def log_call_invited(inviter_id, room_id, invited_user_ids, workspace_id=None, ip_address=None):
    """Log when users are invited to a call."""
    try:
        audit_logger.info(json.dumps({
            "event": "call_invited",
            "inviter_id": str(inviter_id),
            "room_id": str(room_id),
            "invited_user_ids": [str(uid) for uid in invited_user_ids],
            "workspace_id": str(workspace_id) if workspace_id else None,
            "ip_address": ip_address,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }))
    except Exception:
        pass


def log_participant_state_changed(user_id, room_id, is_muted=None, is_video_on=None, is_screen_sharing=None):
    """Log when a participant changes their audio/video/screen-share state."""
    try:
        audit_logger.info(json.dumps({
            "event": "participant_state_changed",
            "user_id": str(user_id),
            "room_id": str(room_id),
            "is_muted": is_muted,
            "is_video_on": is_video_on,
            "is_screen_sharing": is_screen_sharing,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }))
    except Exception:
        pass


def log_unauthorized_access(user_id, room_id, action, reason=None, ip_address=None):
    """Log unauthorized access attempts for security review."""
    try:
        audit_logger.warning(json.dumps({
            "event": "unauthorized_access",
            "user_id": str(user_id) if user_id else None,
            "room_id": str(room_id) if room_id else None,
            "action": action,
            "reason": reason,
            "ip_address": ip_address,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }))
    except Exception:
        pass
