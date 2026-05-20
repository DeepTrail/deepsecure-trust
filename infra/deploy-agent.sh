#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

PROJECT_ID="${GCP_PROJECT_ID:-deepsecure-saas}"
REGION="${GCP_REGION:-us-central1}"
REGISTRY="${REGION}-docker.pkg.dev/${PROJECT_ID}/deepsecure"
TAG="${IMAGE_TAG:-$(git -C "${REPO_ROOT}" rev-parse --short HEAD 2>/dev/null || echo latest)}"

JOB_NAME="gemini-deepsecure-agent"
SCHEDULER_NAME="trigger-gemini-agent"
AGENT_ID="${AGENT_ID:-debugging-agent-sa}"
SA_EMAIL="${AGENT_ID}@${PROJECT_ID}.iam.gserviceaccount.com"
CONTROL_URL="https://app.deepsecure.one"
GATEWAY_URL="https://app.deepsecure.one/mcp"
SCHEDULE="${SCHEDULE:-0 */6 * * *}"

echo "=== Deploying Gemini Agent to Cloud Run Jobs ==="
echo "Project:   ${PROJECT_ID}"
echo "Region:    ${REGION}"
echo "Job:       ${JOB_NAME}"
echo "Agent ID:  ${AGENT_ID}"
echo "SA:        ${SA_EMAIL}"
echo "Schedule:  ${SCHEDULE}"
echo ""

# Step 1: Build and push agent image
IMAGE="${REGISTRY}/gemini-agent:${TAG}"
LATEST="${REGISTRY}/gemini-agent:latest"

echo "--- Building gemini-agent image ---"
gcloud auth configure-docker "${REGION}-docker.pkg.dev" --quiet

docker build --platform linux/amd64 \
  -t "${IMAGE}" \
  -t "${LATEST}" \
  "${REPO_ROOT}/agents/gemini/"

echo "--- Pushing gemini-agent image ---"
docker push "${IMAGE}"
docker push "${LATEST}"
echo "✅ Image pushed: ${IMAGE}"
echo ""

# Step 2: Create or update Cloud Run Job
echo "--- Creating/updating Cloud Run Job: ${JOB_NAME} ---"

if gcloud run jobs describe "${JOB_NAME}" --region="${REGION}" --project="${PROJECT_ID}" &>/dev/null; then
  echo "Job exists — updating..."
  gcloud run jobs update "${JOB_NAME}" \
    --region="${REGION}" \
    --project="${PROJECT_ID}" \
    --image="${LATEST}" \
    --set-secrets="GEMINI_API_KEY=gemini-api-key:latest" \
    --set-env-vars="DEEPSECURE_CONTROL_URL=${CONTROL_URL},DEEPSECURE_GATEWAY_URL=${GATEWAY_URL},AGENT_ID=${AGENT_ID},AGENT_MAX_ITERATIONS=6,AGENT_INTERVAL_SECONDS=60,GEMINI_CLI_TRUST_WORKSPACE=true,GEMINI_MODEL=gemini-2.5-flash" \
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
    --set-secrets="GEMINI_API_KEY=gemini-api-key:latest" \
    --set-env-vars="DEEPSECURE_CONTROL_URL=${CONTROL_URL},DEEPSECURE_GATEWAY_URL=${GATEWAY_URL},AGENT_ID=${AGENT_ID},AGENT_MAX_ITERATIONS=6,AGENT_INTERVAL_SECONDS=60,GEMINI_CLI_TRUST_WORKSPACE=true,GEMINI_MODEL=gemini-2.5-flash" \
    --service-account="${SA_EMAIL}" \
    --task-timeout=1800 \
    --max-retries=1 \
    --memory=1Gi \
    --cpu=1
fi

echo "✅ Cloud Run Job ready: ${JOB_NAME}"
echo ""

# Step 3: Create or update Cloud Scheduler
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
    --description="Triggers gemini-deepsecure-agent every 6 hours to keep agent 'active'"
fi

echo "✅ Cloud Scheduler ready: ${SCHEDULER_NAME}"
echo ""

# Step 4: Summary
echo "=== Deployment Complete ==="
echo ""
echo "Cloud Run Job:     ${JOB_NAME}"
echo "Cloud Scheduler:   ${SCHEDULER_NAME} (${SCHEDULE})"
echo "Image:             ${IMAGE}"
echo ""
echo "Manual trigger:"
echo "  gcloud run jobs execute ${JOB_NAME} --region=${REGION} --project=${PROJECT_ID}"
echo ""
echo "View executions:"
echo "  gcloud run jobs executions list --job=${JOB_NAME} --region=${REGION} --project=${PROJECT_ID}"
echo ""
echo "View scheduler:"
echo "  gcloud scheduler jobs describe ${SCHEDULER_NAME} --location=${REGION} --project=${PROJECT_ID}"
