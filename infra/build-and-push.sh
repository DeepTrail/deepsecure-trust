#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

PROJECT_ID="${GCP_PROJECT_ID:-deepsecure-saas}"
REGION="${GCP_REGION:-us-central1}"
REGISTRY="${REGION}-docker.pkg.dev/${PROJECT_ID}/deepsecure"
TAG="${IMAGE_TAG:-$(git -C "${REPO_ROOT}" rev-parse --short HEAD 2>/dev/null || echo latest)}"

echo "=== Building and pushing Docker images ==="
echo "Registry: ${REGISTRY}"
echo "Tag: ${TAG}"

# Configure Docker to authenticate with Artifact Registry
gcloud auth configure-docker "${REGION}-docker.pkg.dev" --quiet

# All available images and their build contexts (relative to repo root)
declare -A IMAGES=(
  ["deeptrail-control"]="deeptrail-control"
  ["deeptrail-gateway"]="deeptrail-gateway"
  ["frontend"]="frontend"
  ["keycloak"]="config/keycloak"
)

# If arguments provided, only build those images
if [[ $# -gt 0 ]]; then
  SELECTED=("$@")
else
  SELECTED=("${!IMAGES[@]}")
fi

for IMAGE_NAME in "${SELECTED[@]}"; do
  if [[ -z "${IMAGES[$IMAGE_NAME]+x}" ]]; then
    echo "ERROR: Unknown image '${IMAGE_NAME}'. Available: ${!IMAGES[*]}"
    exit 1
  fi

  BUILD_CONTEXT="${REPO_ROOT}/${IMAGES[$IMAGE_NAME]}"
  FULL_TAG="${REGISTRY}/${IMAGE_NAME}:${TAG}"
  LATEST_TAG="${REGISTRY}/${IMAGE_NAME}:latest"

  BUILD_OPTS=(--platform linux/amd64)
  if [[ "${NO_CACHE:-}" == "1" ]]; then
    BUILD_OPTS+=(--no-cache --pull)
  fi

  echo ""
  echo "--- Building ${IMAGE_NAME} from ${BUILD_CONTEXT}/ ---"
  if [[ "${NO_CACHE:-}" == "1" ]]; then
    echo "(no-cache build)"
  fi
  docker build "${BUILD_OPTS[@]}" -t "${FULL_TAG}" -t "${LATEST_TAG}" "${BUILD_CONTEXT}/"

  echo "--- Pushing ${IMAGE_NAME} ---"
  docker push "${FULL_TAG}"
  docker push "${LATEST_TAG}"
done

echo ""
echo "=== All images built and pushed ==="
echo "Images:"
for IMAGE_NAME in "${SELECTED[@]}"; do
  echo "  ${REGISTRY}/${IMAGE_NAME}:${TAG}"
done
