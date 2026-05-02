#!/usr/bin/env bash
# ============================================================
# scripts/deploy-aws.sh
# Build, push to ECR, and deploy all services to AWS ECS Fargate
#
# Prerequisites:
#   - AWS CLI installed and configured  (aws configure)
#   - Docker installed
#   - ECR repositories already exist for each service
#   - ECS cluster and services already defined
#
# Usage:
#   ./scripts/deploy-aws.sh              # deploy all services
#   ./scripts/deploy-aws.sh user-service # deploy one service
# ============================================================

set -euo pipefail

# ── Config ───────────────────────────────────────────────────
AWS_REGION="${AWS_REGION:-us-east-1}"
ECS_CLUSTER="${ECS_CLUSTER:-app-cluster}"
IMAGE_TAG="${IMAGE_TAG:-$(git rev-parse --short HEAD)}"
AWS_ACCOUNT_ID="$(aws sts get-caller-identity --query Account --output text)"
ECR_BASE="${AWS_ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com"

ALL_SERVICES=(
  "user-service"
  "workspace-service"
  "chat-service"
  "collaboration-service"
  "notification-service"
  "media-service"
)

# If a specific service is passed, only deploy that one
if [[ $# -gt 0 ]]; then
  DEPLOY_SERVICES=("$1")
else
  DEPLOY_SERVICES=("${ALL_SERVICES[@]}")
fi

echo ""
echo "🚀  Deploying to AWS ECS"
echo "    Region  : ${AWS_REGION}"
echo "    Cluster : ${ECS_CLUSTER}"
echo "    Tag     : ${IMAGE_TAG}"
echo "    Services: ${DEPLOY_SERVICES[*]}"
echo ""

# ── Login to ECR ─────────────────────────────────────────────
echo "🔐  Logging in to ECR..."
aws ecr get-login-password --region "${AWS_REGION}" \
  | docker login --username AWS --password-stdin "${ECR_BASE}"

# ── Build → Tag → Push → Deploy ──────────────────────────────
for SERVICE in "${DEPLOY_SERVICES[@]}"; do

  # Derive source directory name (user-service → user_service)
  SRC_DIR="services/${SERVICE}"

  echo ""
  echo "────────────────────────────────────────"
  echo "📦  Building: ${SERVICE}"

  docker build \
    --platform linux/amd64 \
    --tag "${ECR_BASE}/${SERVICE}:${IMAGE_TAG}" \
    --tag "${ECR_BASE}/${SERVICE}:latest" \
    --file "${SRC_DIR}/Dockerfile" \
    "${SRC_DIR}"

  echo "⬆️   Pushing: ${SERVICE}:${IMAGE_TAG}"
  docker push "${ECR_BASE}/${SERVICE}:${IMAGE_TAG}"
  docker push "${ECR_BASE}/${SERVICE}:latest"

  echo "🔄  Triggering ECS rolling deployment: ${SERVICE}"
  aws ecs update-service \
    --cluster   "${ECS_CLUSTER}" \
    --service   "${SERVICE}" \
    --force-new-deployment \
    --region    "${AWS_REGION}" \
    --output    text \
    --query     "service.serviceName"

  echo "✅  ${SERVICE} deployment triggered"
done

# ── Wait for all services to stabilise ───────────────────────
echo ""
echo "⏳  Waiting for ECS services to stabilise..."

for SERVICE in "${DEPLOY_SERVICES[@]}"; do
  echo "    Waiting: ${SERVICE}..."
  aws ecs wait services-stable \
    --cluster  "${ECS_CLUSTER}" \
    --services "${SERVICE}" \
    --region   "${AWS_REGION}"
  echo "    ✅  ${SERVICE} stable"
done

echo ""
echo "🎉  All deployments complete — tag: ${IMAGE_TAG}"