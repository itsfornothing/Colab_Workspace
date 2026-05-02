#!/usr/bin/env bash
# ============================================================
# entrypoint.prod.sh — collaboration-service
#
# Uses Daphne as the ASGI server. Daphne is the reference ASGI
# server for Django Channels and correctly handles the WebSocket
# upgrade handshake (HTTP → WS protocol switch).
#
# Gunicorn + UvicornWorker was tried previously but does NOT
# support WebSocket upgrades — Gunicorn's HTTP layer intercepts
# the Upgrade header before the uvicorn worker can process it,
# causing the client to see "connection was not upgraded to
# websocket" (the server returns a plain HTTP response instead
# of 101 Switching Protocols).
#
# The DB-readiness wait loop is kept to avoid migrate failing
# on a race with Postgres startup.
# ============================================================

set -euo pipefail

MODULE="${DJANGO_ASGI_MODULE:-collaboration_service.asgi:application}"
HOST="${BIND_HOST:-0.0.0.0}"
PORT="${BIND_PORT:-8000}"

echo "[entrypoint] Waiting for PostgreSQL at ${DATABASE_HOST}:${DATABASE_PORT}..."
for i in $(seq 1 30); do
    if python - <<'PYEOF'
import os, django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', os.environ.get('DJANGO_SETTINGS_MODULE', 'collaboration_service.settings'))
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

echo "[entrypoint] Running migrations..."
python manage.py migrate --noinput

echo "[entrypoint] Collecting static files..."
python manage.py collectstatic --noinput

echo "[entrypoint] Starting Daphne: ${MODULE} on ${HOST}:${PORT}"
exec daphne -b "${HOST}" -p "${PORT}" "${MODULE}"