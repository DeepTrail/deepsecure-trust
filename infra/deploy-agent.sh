#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

# ── Required ────────────────────────────────────────────────────────
AGENT_SLUG="${AGENT_SLUG:?Set AGENT_SLUG (e.g. debugging, engineering-audit, thunderbolt)}"

# ── Derived naming (override any component via env) ─────────────────
PROJECT_ID="${GCP_PROJECT_ID:-deepsecure-saas}"
REGION="${GCP_REGION:-us-central1}"
REGISTRY="${REGION}-docker.pkg.dev/${PROJECT_ID}/deepsecure"
TAG="${IMAGE_TAG:-$(git -C "${REPO_ROOT}" rev-parse --short HEAD 2>/dev/null || echo latest)}"

AGENT_ID="${AGENT_ID:-${AGENT_SLUG}-deepsecure-agent}"
JOB_NAME="${JOB_NAME:-${AGENT_SLUG}-deepsecure-agent-job}"
SCHEDULER_NAME="${SCHEDULER_NAME:-trigger-${AGENT_SLUG}-deepsecure-agent}"
SA_EMAIL="${SA_EMAIL:-${AGENT_SLUG}-sa@${PROJECT_ID}.iam.gserviceaccount.com}"
CONTROL_URL="${CONTROL_URL:-https://app.deepsecure.one}"
GATEWAY_URL="${GATEWAY_URL:-https://app.deepsecure.one/mcp}"
SCHEDULE="${SCHEDULE:-0 */1 * * *}"
IMAGE_NAME="${IMAGE_NAME:-gemini-agent-sdk}"

echo "=== Deploying DeepSecure Agent to Cloud Run Jobs ==="
echo "Slug:      ${AGENT_SLUG}"
echo "Project:   ${PROJECT_ID}"
echo "Region:    ${REGION}"
echo "Job:       ${JOB_NAME}"
echo "Agent ID:  ${AGENT_ID}"
echo "SA:        ${SA_EMAIL}"
echo "Schedule:  ${SCHEDULE}"
echo ""

# ── Step 1: Build and push agent image ──────────────────────────────
IMAGE="${REGISTRY}/${IMAGE_NAME}:${TAG}"
LATEST="${REGISTRY}/${IMAGE_NAME}:latest"

if [ "${SKIP_BUILD:-}" != "1" ]; then
  echo "--- Building ${IMAGE_NAME} image ---"
  gcloud auth configure-docker "${REGION}-docker.pkg.dev" --quiet

  docker buildx build --platform linux/amd64 \
    -t "${IMAGE}" \
    -t "${LATEST}" \
    -f "${REPO_ROOT}/agents/gemini/Dockerfile.sdk" \
    "${REPO_ROOT}"

  echo "--- Pushing ${IMAGE_NAME} image ---"
  docker push "${IMAGE}"
  docker push "${LATEST}"
  echo "✅ Image pushed: ${IMAGE}"
else
  echo "--- SKIP_BUILD=1 — reusing existing image ---"
fi
echo ""

# ── Step 2: Create or update Cloud Run Job ──────────────────────────
echo "--- Creating/updating Cloud Run Job: ${JOB_NAME} ---"

LLM_PROVIDERS="${LLM_PROVIDERS:-gemini,claude,codex}"

# Use ^||^ as the kv-pair delimiter so commas inside values (e.g. LLM_PROVIDERS) are preserved.
ENV_VARS="^||^DEEPSECURE_CONTROL_URL=${CONTROL_URL}"
ENV_VARS+="||DEEPSECURE_GATEWAY_URL=${GATEWAY_URL}"
ENV_VARS+="||AGENT_ID=${AGENT_ID}"
ENV_VARS+="||GEMINI_CLI_TRUST_WORKSPACE=true"
ENV_VARS+="||GEMINI_MODEL=gemini-2.5-flash"
ENV_VARS+="||PROMPT_TIMEOUT_SECONDS=300"
ENV_VARS+="||LLM_PROVIDERS=${LLM_PROVIDERS}"

if gcloud run jobs describe "${JOB_NAME}" --region="${REGION}" --project="${PROJECT_ID}" &>/dev/null; then
  echo "Job exists — updating..."
  gcloud run jobs update "${JOB_NAME}" \
    --region="${REGION}" \
    --project="${PROJECT_ID}" \
    --image="${LATEST}" \
    --set-secrets="GEMINI_API_KEY=gemini-api-key:latest,ANTHROPIC_API_KEY=anthropic-api-key:latest,OPENAI_API_KEY=openai-api-key:latest" \
    --set-env-vars="${ENV_VARS}" \
    --service-account="${SA_EMAIL}" \
    --task-timeout=1800 \
    --max-retries=1 \
    --memory=1Gi \
    --cpu=1
else
  echo "Job does not exist — creating..."
  gcloud run jobs create "${JOB_NAME}" \
    --region="${REGION}" \
    --project="${PROJECT_ID}" \
    --image="${LATEST}" \
    --set-secrets="GEMINI_API_KEY=gemini-api-key:latest,ANTHROPIC_API_KEY=anthropic-api-key:latest,OPENAI_API_KEY=openai-api-key:latest" \
    --set-env-vars="${ENV_VARS}" \
    --service-account="${SA_EMAIL}" \
    --task-timeout=1800 \
    --max-retries=1 \
    --memory=1Gi \
    --cpu=1
fi

echo "✅ Cloud Run Job ready: ${JOB_NAME}"
echo ""

# ── Step 3: Create or update Cloud Scheduler ────────────────────────
echo "--- Creating/updating Cloud Scheduler: ${SCHEDULER_NAME} ---"

SCHEDULER_SA="${SA_EMAIL}"
JOB_URI="https://${REGION}-run.googleapis.com/apis/run.googleapis.com/v1/namespaces/${PROJECT_ID}/jobs/${JOB_NAME}:run"

if gcloud scheduler jobs describe "${SCHEDULER_NAME}" --location="${REGION}" --project="${PROJECT_ID}" &>/dev/null; then
  echo "Scheduler exists — updating..."
  gcloud scheduler jobs update http "${SCHEDULER_NAME}" \
    --location="${REGION}" \
    --project="${PROJECT_ID}" \
    --schedule="${SCHEDULE}" \
    --uri="${JOB_URI}" \
    --http-method=POST \
    --oauth-service-account-email="${SCHEDULER_SA}" \
    --oauth-token-scope="https://www.googleapis.com/auth/cloud-platform"
else
  echo "Scheduler does not exist — creating..."
  gcloud scheduler jobs create http "${SCHEDULER_NAME}" \
    --location="${REGION}" \
    --project="${PROJECT_ID}" \
    --schedule="${SCHEDULE}" \
    --uri="${JOB_URI}" \
    --http-method=POST \
    --oauth-service-account-email="${SCHEDULER_SA}" \
    --oauth-token-scope="https://www.googleapis.com/auth/cloud-platform" \
    --time-zone="America/Los_Angeles" \
    --description="Triggers ${AGENT_ID} on schedule '${SCHEDULE}'"
fi

echo "✅ Cloud Scheduler ready: ${SCHEDULER_NAME}"
echo ""

# ── Step 4: Summary ─────────────────────────────────────────────────
echo "=== Deployment Complete ==="
echo ""
echo "Cloud Run Job:     ${JOB_NAME}"
echo "Cloud Scheduler:   ${SCHEDULER_NAME} (${SCHEDULE})"
echo "Image:             ${IMAGE}"
echo "Agent ID:          ${AGENT_ID}"
echo ""
echo "Manual trigger:"
echo "  gcloud run jobs execute ${JOB_NAME} --region=${REGION} --project=${PROJECT_ID}"
echo ""
echo "View executions:"
echo "  gcloud run jobs executions list --job=${JOB_NAME} --region=${REGION} --project=${PROJECT_ID}"
echo ""
echo "View scheduler:"
echo "  gcloud scheduler jobs describe ${SCHEDULER_NAME} --location=${REGION} --project=${PROJECT_ID}"
