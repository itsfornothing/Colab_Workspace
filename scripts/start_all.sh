#!/bin/bash
# Start all backend services locally for development
# Each service runs on a different port via Daphne (ASGI)
#
# Ports:
#   user_service         → 8001
#   chat_service         → 8002
#   workspace_service    → 8003
#   notification_service → 8004
#   collaboration_service→ 8005
#   media_service        → 8006

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
ROOT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
VENV="$ROOT_DIR/.venv/bin"
SERVICES_DIR="$ROOT_DIR/services"

echo "Starting all Collab Workspace services..."
echo "Root: $ROOT_DIR"
echo ""

start_service() {
  local name=$1
  local dir=$2
  local port=$3
  local settings_module=$4
  local asgi_module=$5

  echo "▶ Starting $name on port $port..."
  (
    cd "$dir"
    DJANGO_SETTINGS_MODULE="$settings_module" \
    "$VENV/daphne" -b 0.0.0.0 -p "$port" "${asgi_module}:application" \
      > "/tmp/collab_${name}.log" 2>&1 &
    echo $! > "/tmp/collab_${name}.pid"
    echo "  PID: $! | Log: /tmp/collab_${name}.log"
  )
}

start_service "user_service"          "$SERVICES_DIR/user_service"          8001 "user_service.settings"          "user_service.asgi"
start_service "chat_service"          "$SERVICES_DIR/chat_service"          8002 "chat_service.settings"          "chat_service.asgi"
start_service "workspace_service"     "$SERVICES_DIR/workspace_service"     8003 "workspace_service.settings"     "workspace_service.asgi"
start_service "notification_service"  "$SERVICES_DIR/notification_service"  8004 "notification_service.settings"  "notification_service.asgi"
start_service "collaboration_service" "$SERVICES_DIR/collaboration_service" 8005 "collaboration_service.settings" "collaboration_service.asgi"
start_service "media_service"         "$SERVICES_DIR/media_service"         8006 "media_service.settings"         "media_service.asgi"

echo ""
echo "All services started. Waiting 4s for startup..."
sleep 4
echo ""
echo "Service status:"
for name in user_service chat_service workspace_service notification_service collaboration_service media_service; do
  pid_file="/tmp/collab_${name}.pid"
  if [ -f "$pid_file" ]; then
    pid=$(cat "$pid_file")
    if kill -0 "$pid" 2>/dev/null; then
      echo "  ✓ $name (PID $pid)"
    else
      echo "  ✗ $name FAILED — check /tmp/collab_${name}.log"
    fi
  fi
done

echo ""
echo "Endpoints:"
echo "  user_service         → http://localhost:8001"
echo "  chat_service         → http://localhost:8002"
echo "  workspace_service    → http://localhost:8003"
echo "  notification_service → http://localhost:8004"
echo "  collaboration_service→ http://localhost:8005"
echo "  media_service        → http://localhost:8006"
echo ""
echo "To stop all services: bash $SCRIPT_DIR/stop_all.sh"
