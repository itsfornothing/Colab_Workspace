"""
Email delivery helpers.

ADDED: send_digest_email() — renders a grouped digest of notifications
       as both plain text and HTML and sends via Django's email backend.
ADDED: HTML template string (inline, no separate template file needed).
"""

import logging
from django.core.mail import send_mail, EmailMultiAlternatives
from django.conf import settings

logger = logging.getLogger(__name__)


def send_notification_email(user_email: str, title: str, content: str) -> bool:
    """Send a single notification email. Returns True on success."""
    try:
        send_mail(
            subject=title,
            message=content,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[user_email],
            fail_silently=False,
        )
        return True
    except Exception:
        logger.exception("Failed to send notification email to %s", user_email)
        return False


def send_digest_email(user_email: str, notifications: list, digest_type: str) -> bool:
    """
    Send a digest email summarising a list of Notification objects.
    Sends both plain-text and HTML versions.
    Returns True on success.
    """
    count = len(notifications)
    subject = f"Your {digest_type} notification digest — {count} update{'s' if count != 1 else ''}"

    # ---- Plain text ----
    lines = [f"Hi,\n\nHere's your {digest_type} digest:\n"]
    for notif in notifications:
        lines.append(f"• [{notif.type.upper()}] {notif.title}")
        lines.append(f"  {notif.content[:200]}")
        lines.append(f"  {notif.created_at.strftime('%b %d %H:%M UTC')}\n")
    lines.append("Log in to view all notifications and mark them as read.")
    plain_text = "\n".join(lines)

    # ---- HTML ----
    rows_html = ""
    for notif in notifications:
        rows_html += f"""
        <tr>
          <td style="padding:8px;border-bottom:1px solid #eee;">
            <strong>[{notif.type.upper()}]</strong> {notif.title}<br>
            <span style="color:#555;font-size:13px;">{notif.content[:200]}</span><br>
            <small style="color:#999;">{notif.created_at.strftime('%b %d %H:%M UTC')}</small>
          </td>
        </tr>"""

    html_content = f"""
    <html><body style="font-family:sans-serif;max-width:600px;margin:auto;">
      <h2 style="color:#333;">Your {digest_type.capitalize()} Digest</h2>
      <p style="color:#666;">You have <strong>{count}</strong> unread notification{'s' if count != 1 else ''}.</p>
      <table width="100%" cellpadding="0" cellspacing="0" style="border-collapse:collapse;">
        {rows_html}
      </table>
      <p style="margin-top:24px;color:#999;font-size:12px;">
        You're receiving this because you subscribed to {digest_type} digests.
        <a href="#">Update preferences</a>
      </p>
    </body></html>
    """

    try:
        msg = EmailMultiAlternatives(
            subject=subject,
            body=plain_text,
            from_email=settings.DEFAULT_FROM_EMAIL,
            to=[user_email],
        )
        msg.attach_alternative(html_content, "text/html")
        msg.send()
        return True
    except Exception:
        logger.exception("Failed to send digest email to %s", user_email)
        return False