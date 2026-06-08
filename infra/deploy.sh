#!/usr/bin/env bash
set -euo pipefail

PROJECT_ID="${GCP_PROJECT_ID:-deepsecure-saas}"
REGION="${GCP_REGION:-us-central1}"
REGISTRY="${REGION}-docker.pkg.dev/${PROJECT_ID}/deepsecure"
TAG="${IMAGE_TAG:-latest}"

declare -A SERVICES=(
  ["deeptrail-control"]="deeptrail-control"
  ["deeptrail-gateway"]="deeptrail-gateway"
  ["frontend"]="frontend"
  ["keycloak"]="keycloak"
)

if [[ $# -eq 0 ]]; then
  echo "Usage: $0 <service1> [service2] ..."
  echo ""
  echo "Deploy Cloud Run services with the latest pushed image."
  echo ""
  echo "Available services: ${!SERVICES[*]}"
  echo ""
  echo "Examples:"
  echo "  $0 frontend deeptrail-control    # Deploy frontend + control plane"
  echo "  $0 frontend                      # Deploy frontend only"
  echo ""
  echo "Full pipeline:"
  echo "  ./build-and-push.sh frontend deeptrail-control"
  echo "  ./deploy.sh frontend deeptrail-control"
  echo "  ./migrate.sh"
  exit 1
fi

SELECTED=("$@")

echo "=== Deploying to Cloud Run ==="
echo "Project: ${PROJECT_ID}"
echo "Region:  ${REGION}"
echo "Tag:     ${TAG}"

for SERVICE_NAME in "${SELECTED[@]}"; do
  if [[ -z "${SERVICES[$SERVICE_NAME]+x}" ]]; then
    echo "ERROR: Unknown service '${SERVICE_NAME}'. Available: ${!SERVICES[*]}"
    exit 1
  fi

  IMAGE="${REGISTRY}/${SERVICE_NAME}:${TAG}"

  echo ""
  echo "--- Deploying ${SERVICE_NAME} ---"
  echo "Image: ${IMAGE}"

  gcloud run services update "${SERVICE_NAME}" \
    --region="${REGION}" \
    --project="${PROJECT_ID}" \
    --image="${IMAGE}"

  # Ensure traffic routes to the latest revision
  gcloud run services update-traffic "${SERVICE_NAME}" \
    --to-latest \
    --region="${REGION}" \
    --project="${PROJECT_ID}" 2>/dev/null || true

  echo "✅ ${SERVICE_NAME} deployed"
done

echo ""
echo "=== All services deployed ==="
echo "Verify at:"
for SERVICE_NAME in "${SELECTED[@]}"; do
  URL=$(gcloud run services describe "${SERVICE_NAME}" \
    --region="${REGION}" \
    --project="${PROJECT_ID}" \
    --format="value(status.url)" 2>/dev/null || echo "https://${SERVICE_NAME}-*.run.app")
  echo "  ${SERVICE_NAME}: ${URL}"
done
