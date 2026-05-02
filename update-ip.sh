#!/bin/bash
# Run this whenever your IP changes: ./update-ip.sh
# This updates the IP in all configs AND re-applies all custom code fixes.

set -e

NEW_IP=$(ipconfig getifaddr en0)
if [ -z "$NEW_IP" ]; then
  echo "Could not detect IP. Are you connected to WiFi?"
  exit 1
fi

echo "New IP: $NEW_IP"

# ── 1. Update all service env files ──────────────────────────────────────────
for f in services/user_service/.env.local \
          services/workspace_service/.env.local \
          services/chat_service/.env.local \
          services/collaboration_service/.env.local \
          services/media_service/.env.local \
          services/notification_service/.env.local; do
  sed -i '' "s/10\.[0-9]*\.[0-9]*\.[0-9]*/$NEW_IP/g" "$f"
  echo "  Updated $f"
done

# ── 2. Update Flutter constants ───────────────────────────────────────────────
CONSTANTS="frontend/mobile/mobile_app/lib/core/constants.dart"
sed -i '' "s/10\.[0-9]*\.[0-9]*\.[0-9]*/$NEW_IP/g" "$CONSTANTS"
echo "  Updated $CONSTANTS"

# ── 3. Update DJANGO_ALLOWED_HOSTS in root docker-compose to include new IP ──
# Replace the entire ALLOWED_HOSTS line with the correct value
sed -i '' "s/DJANGO_ALLOWED_HOSTS: localhost,127\.0\.0\.1,[0-9.]*,collaboration-service/DJANGO_ALLOWED_HOSTS: localhost,127.0.0.1,$NEW_IP,collaboration-service/" docker-compose.yml
sed -i '' "s/DJANGO_ALLOWED_HOSTS: localhost,127\.0\.0\.1,[0-9.]*,chat-service/DJANGO_ALLOWED_HOSTS: localhost,127.0.0.1,$NEW_IP,chat-service/" docker-compose.yml
echo "  Updated docker-compose.yml ALLOWED_HOSTS"

# ── 4. Stop standalone collaboration service containers (port conflict) ───────
echo "Stopping standalone collaboration service if running..."
docker rm -f collaboration-service collaboration-redis 2>/dev/null || true

# ── 5. Rebuild and force-recreate all services to pick up new env ────────────
echo "Rebuilding and restarting services..."
docker compose build collaboration-service chat-service
docker compose up -d --force-recreate \
  user-service workspace-service collaboration-service \
  media-service notification-service chat-service

sleep 5

# ── 6. Re-apply authentication.py fix to ALL services ────────────────────────
echo "Re-applying authentication fixes..."
docker cp services/workspace_service/app/authentication.py    workspace-service:/app/app/authentication.py
docker cp services/collaboration_service/app/authentication.py collaboration-service:/app/app/authentication.py
docker cp services/media_service/app/authentication.py        media-service:/app/app/authentication.py
docker cp services/notification_service/app/authentication.py notification-service:/app/app/authentication.py

# ── 7. Re-apply custom views/urls/settings for all services ──────────────────
echo "Re-applying custom views/urls/settings..."
docker cp services/workspace_service/app/views.py workspace-service:/app/app/views.py
docker cp services/workspace_service/app/urls.py  workspace-service:/app/app/urls.py
docker cp services/workspace_service/workspace_service/settings.py workspace-service:/app/workspace_service/settings.py
docker cp services/collaboration_service/app/views.py collaboration-service:/app/app/views.py
docker cp services/collaboration_service/app/consumers.py collaboration-service:/app/app/consumers.py
docker cp services/collaboration_service/collaboration_service/settings.py collaboration-service:/app/collaboration_service/settings.py
docker cp services/chat_service/chat_service/settings.py chat-service:/app/chat_service/settings.py
docker cp services/media_service/media_service/settings.py media-service:/app/media_service/settings.py
docker cp services/notification_service/notification_service/settings.py notification-service:/app/notification_service/settings.py

# ── 8. Restart services that got new files ───────────────────────────────────
echo "Restarting services with updated files..."
docker restart workspace-service collaboration-service chat-service media-service notification-service

echo ""
echo "Done! Current IP: $NEW_IP"
echo "Now hot restart the Flutter app."