#!/usr/bin/env bash
# ============================================================
# scripts/deploy-digitalocean.sh
# Deploy to DigitalOcean — two modes:
#
#   --droplet  Deploy via Docker Compose on a single Droplet (SSH)
#   --app      Deploy via DigitalOcean App Platform (managed)
#
# Usage:
#   ./scripts/deploy-digitalocean.sh --droplet --host 1.2.3.4
#   ./scripts/deploy-digitalocean.sh --app
# ============================================================

set -euo pipefail

MODE="${1:-}"
IMAGE_TAG="$(git rev-parse --short HEAD)"
DO_REGISTRY="${DO_REGISTRY:-registry.digitalocean.com/your-registry}"

ALL_SERVICES=(
  "user-service"
  "workspace-service"
  "chat-service"
  "collaboration-service"
  "notification-service"
  "media-service"
)

# ============================================================
# MODE: Droplet — SSH + Docker Compose
# ============================================================
if [[ "${MODE}" == "--droplet" ]]; then

  DO_HOST="${3:-}"
  if [[ -z "${DO_HOST}" ]]; then
    echo "Usage: $0 --droplet --host <droplet-ip>"
    exit 1
  fi

  echo ""
  echo "🚀  Deploying to Droplet: ${DO_HOST}"
  echo "    Tag: ${IMAGE_TAG}"
  echo ""

  # Login to DigitalOcean Container Registry
  echo "🔐  Logging in to DO Container Registry..."
  doctl registry login

  # Build and push each service image
  for SERVICE in "${ALL_SERVICES[@]}"; do
    SRC_DIR="services/${SERVICE}"
    echo "📦  Building: ${SERVICE}"

    docker build \
      --platform linux/amd64 \
      --tag "${DO_REGISTRY}/${SERVICE}:${IMAGE_TAG}" \
      --tag "${DO_REGISTRY}/${SERVICE}:latest" \
      --file "${SRC_DIR}/Dockerfile" \
      "${SRC_DIR}"

    echo "⬆️   Pushing: ${SERVICE}"
    docker push "${DO_REGISTRY}/${SERVICE}:${IMAGE_TAG}"
    docker push "${DO_REGISTRY}/${SERVICE}:latest"
  done

  # Copy compose file and env to the Droplet, then pull + restart
  echo ""
  echo "📡  Copying files to Droplet..."
  scp infrastructure/docker-compose.yml "root@${DO_HOST}:/app/docker-compose.yml"
  scp .env                               "root@${DO_HOST}:/app/.env"

  echo "🔄  Pulling images and restarting services on Droplet..."
  ssh "root@${DO_HOST}" bash <<REMOTE
set -e
cd /app
export IMAGE_TAG="${IMAGE_TAG}"
doctl registry login
docker compose pull
docker compose up -d --remove-orphans
docker image prune -f
echo "✅  Deployment complete on Droplet ${DO_HOST}"
REMOTE

# ============================================================
# MODE: App Platform — doctl managed deployment
# ============================================================
elif [[ "${MODE}" == "--app" ]]; then

  echo ""
  echo "🚀  Deploying to DigitalOcean App Platform..."

  if ! command -v doctl &>/dev/null; then
    echo "❌  doctl not found."
    echo "    Install: https://docs.digitalocean.com/reference/doctl/how-to/install/"
    exit 1
  fi

  # Check for existing app
  APP_ID="$(doctl apps list --format ID --no-header 2>/dev/null | head -1)"

  if [[ -z "${APP_ID}" ]]; then
    echo "📝  No existing app found — creating from spec..."
    doctl apps create --spec .do/app.yaml
    echo "✅  App Platform app created"
  else
    echo "🔄  Updating existing app: ${APP_ID}"
    doctl apps update "${APP_ID}" --spec .do/app.yaml
    doctl apps create-deployment "${APP_ID}" --force-rebuild
    echo "✅  App Platform deployment triggered for app: ${APP_ID}"
  fi

# ============================================================
# No mode provided
# ============================================================
else
  echo ""
  echo "Usage:"
  echo "  $0 --droplet --host <droplet-ip>   Deploy via Docker Compose on a Droplet"
  echo "  $0 --app                           Deploy to App Platform via doctl"
  echo ""
  exit 1
fi