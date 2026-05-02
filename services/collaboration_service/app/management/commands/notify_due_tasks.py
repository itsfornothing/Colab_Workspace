"""
Management command: notify_due_tasks

Fires a "Task Due Today" system_alert notification for every incomplete task
whose due_date is today (or already past) and hasn't been notified yet.

Run this on a schedule — e.g. once per day at 08:00 via cron or Celery Beat:

    python manage.py notify_due_tasks

Cron example (runs every day at 08:00):
    0 8 * * * /app/venv/bin/python /app/manage.py notify_due_tasks

The command is idempotent: the `due_date_notified` flag on each Task ensures
the notification is sent exactly once per task, even if the command is run
multiple times in the same day.
"""

import logging
import threading
import urllib.request
import json
from datetime import date

from django.core.management.base import BaseCommand
from django.conf import settings

from app.models import Task

logger = logging.getLogger(__name__)


def _fire_notification(user_id: str, title: str, message: str, metadata: dict = None):
    """POST a system_alert event to the notification service (synchronous here)."""
    notification_url = getattr(
        settings,
        "NOTIFICATION_SERVICE_URL",
        "http://notification_service:8005",
    )
    endpoint = f"{notification_url}/api/events/"

    payload = json.dumps({
        "event_type": "system_alert",
        "payload": {
            "user_id": str(user_id),
            "title": title,
            "message": message,
            **(metadata or {}),
        },
    }).encode()

    try:
        req = urllib.request.Request(
            endpoint,
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        urllib.request.urlopen(req, timeout=5)
        logger.info("Sent due-date notification to user %s for task %s", user_id, metadata.get("task_id"))
    except Exception as exc:
        logger.warning("Could not reach notification service: %s", exc)


class Command(BaseCommand):
    help = "Send notifications for tasks whose due date has been reached."

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Print tasks that would be notified without actually sending.",
        )

    def handle(self, *args, **options):
        dry_run = options["dry_run"]
        today = date.today()

        # Find all incomplete tasks that are due today or overdue and not yet notified
        due_tasks = Task.objects.filter(
            due_date__lte=today,
            due_date_notified=False,
            created_by__isnull=False,
        ).exclude(status="done").select_related("created_by")

        count = due_tasks.count()
        self.stdout.write(f"Found {count} task(s) to notify.")

        notified = 0
        for task in due_tasks:
            user_id = str(task.created_by_id)
            is_overdue = task.due_date < today
            title = "Task Overdue" if is_overdue else "Task Due Today"
            due_label = task.due_date.isoformat()

            if is_overdue:
                message = f'Your task "{task.title}" was due on {due_label} and is still incomplete.'
            else:
                message = f'Your task "{task.title}" is due today ({due_label}).'

            if dry_run:
                self.stdout.write(f"  [DRY RUN] Would notify user {user_id}: {message}")
                continue

            _fire_notification(
                user_id=user_id,
                title=title,
                message=message,
                metadata={
                    "task_id": str(task.id),
                    "priority": task.priority,
                    "due_date": due_label,
                },
            )

            # Mark as notified so we don't send again
            task.due_date_notified = True
            task.save(update_fields=["due_date_notified"])
            notified += 1

        if not dry_run:
            self.stdout.write(self.style.SUCCESS(f"Notified {notified} task(s)."))
