#!/usr/bin/env bash
# ============================================================
# entrypoint.prod.sh — notification-service (WSGI)
# ============================================================

set -euo pipefail

echo "[entrypoint] Waiting for PostgreSQL at ${DATABASE_HOST}:${DATABASE_PORT}..."
for i in $(seq 1 30); do
    if python - <<'PYEOF'
import os, django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', os.environ.get('DJANGO_SETTINGS_MODULE', 'notification_service.settings'))
django.setup()
from django.db import connection
connection.ensure_connection()
print("DB ready")
PYEOF
    then
        break
    fi
    echo "[entrypoint] DB not ready yet ($i/30), retrying in 2s..."
    sleep 2
done

echo "[entrypoint] Collecting static files..."
python manage.py collectstatic --noinput
echo "[entrypoint] Running migrations..."
python manage.py migrate --noinput
echo "[entrypoint] Starting Gunicorn on 0.0.0.0:8000 (3 workers)"
exec python -m gunicorn --bind 0.0.0.0:8000 --workers 3 notification_service.wsgi:application
