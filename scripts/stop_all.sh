#!/bin/bash
echo "Stopping all Collab Workspace services..."
for name in user_service chat_service workspace_service notification_service collaboration_service media_service; do
  pid_file="/tmp/collab_${name}.pid"
  if [ -f "$pid_file" ]; then
    pid=$(cat "$pid_file")
    if kill -0 "$pid" 2>/dev/null; then
      kill "$pid"
      echo "  ✓ Stopped $name (PID $pid)"
    fi
    rm -f "$pid_file"
  fi
done
echo "Done."
