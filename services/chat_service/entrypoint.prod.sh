#!/usr/bin/env bash
# ============================================================
# entrypoint.prod.sh — chat-service
# Uses Gunicorn + UvicornWorker for reliable ASGI/WebSocket support.
# ============================================================

set -euo pipefail

MODULE="${DJANGO_ASGI_MODULE:-chat_service.asgi:application}"
WORKERS="${GUNICORN_WORKERS:-4}"
HOST="${BIND_HOST:-0.0.0.0}"
PORT="${BIND_PORT:-8000}"

echo "[entrypoint] Waiting for PostgreSQL at ${DATABASE_HOST}:${DATABASE_PORT}..."
for i in $(seq 1 30); do
    python -c "
import os, django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', os.environ.get('DJANGO_SETTINGS_MODULE', 'chat_service.settings'))
django.setup()
from django.db import connection
connection.ensure_connection()
print('DB ready')
" && break
    echo "[entrypoint] DB not ready yet ($i/30), retrying in 2s..."
    sleep 2
done

echo "[entrypoint] Running migrations..."
python manage.py migrate --noinput

echo "[entrypoint] Collecting static files..."
python manage.py collectstatic --noinput

echo "[entrypoint] Starting: ${MODULE} on ${HOST}:${PORT} (${WORKERS} workers)"
exec gunicorn "${MODULE}" \
    --worker-class uvicorn.workers.UvicornWorker \
    --workers "${WORKERS}" \
    --bind "${HOST}:${PORT}" \
    --access-logfile - \
    --error-logfile - \
    --log-level info \
    --timeout 120 \
    --graceful-timeout 30 \
    --keep-alive 5
