#!/usr/bin/env bash
set -euo pipefail

# Deploy a DeepSecure background agent to Cloud Run Jobs + Cloud Scheduler.
#
# Naming convention (tenant defaults to "deepsecure"):
#   AGENT_SLUG=debugging          → debugging-deepsecure-agent
#   JOB_NAME                      → debugging-deepsecure-agent-job
#   SCHEDULER_NAME                → trigger-debugging-deepsecure-agent
#
# Override any derived value by setting JOB_NAME, AGENT_ID, or SCHEDULER_NAME
# explicitly before invoking this script.

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

usage() {
  cat <<'EOF'
Usage: AGENT_SLUG=<slug> [options] ./infra/deploy-agent.sh

Required:
  AGENT_SLUG    Agent short name: debugging | engineering-audit | thunderbolt

Optional:
  TENANT_NAME   Tenant/company slug (default: deepsecure)
  SKIP_BUILD    1 = skip image build/push (default: 0)
  SCHEDULE      Cron expression (default: 0 */1 * * *)
  SERVICE_ACCOUNT  GCP SA email (default: <AGENT_SLUG>-sa@<project>.iam.gserviceaccount.com)

Derived names (override with env vars if needed):
  AGENT_ID      <slug>-<tenant>-agent
  JOB_NAME      <slug>-<tenant>-agent-job
  SCHEDULER_NAME trigger-<slug>-<tenant>-agent

Examples — deploy all 3 agents (build once, legacy GCP job names):
  AGENT_SLUG=debugging AGENT_ID=debugging-agent-sa JOB_NAME=gemini-deepsecure-agent SCHEDULER_NAME=trigger-gemini-agent ./infra/deploy-agent.sh
  AGENT_SLUG=engineering-audit AGENT_ID=engineering-audit-agent JOB_NAME=engineering-audit SCHEDULER_NAME=trigger-engineering-audit SKIP_BUILD=1 ./infra/deploy-agent.sh
  AGENT_SLUG=thunderbolt AGENT_ID=thunderbolt-agent JOB_NAME=thunderbolt-deepsecure-agent SCHEDULER_NAME=trigger-thunderbolt-agent SKIP_BUILD=1 ./infra/deploy-agent.sh

Target naming (after agent-naming migration):
  AGENT_SLUG=debugging          ./infra/deploy-agent.sh
  AGENT_SLUG=engineering-audit  SKIP_BUILD=1 ./infra/deploy-agent.sh
  AGENT_SLUG=thunderbolt        SKIP_BUILD=1 ./infra/deploy-agent.sh

Current production agents:
  Agent Name          AGENT_SLUG         AGENT_ID                           JOB_NAME                              SCHEDULER_NAME
  Debugging Agent     debugging          debugging-deepsecure-agent         debugging-deepsecure-agent-job        trigger-debugging-deepsecure-agent
  Engineering Audit   engineering-audit  engineering-audit-deepsecure-agent engineering-audit-deepsecure-agent-job trigger-engineering-audit-deepsecure-agent
  Thunderbolt         thunderbolt        thunderbolt-deepsecure-agent       thunderbolt-deepsecure-agent-job      trigger-thunderbolt-deepsecure-agent
EOF
}

if [[ "${1:-}" == "-h" || "${1:-}" == "--help" ]]; then
  usage
  exit 0
fi

PROJECT_ID="${GCP_PROJECT_ID:-deepsecure-saas}"
REGION="${GCP_REGION:-us-central1}"
REGISTRY="${REGION}-docker.pkg.dev/${PROJECT_ID}/deepsecure"
TAG="${IMAGE_TAG:-$(git -C "${REPO_ROOT}" rev-parse --short HEAD 2>/dev/null || echo latest)}"

AGENT_SLUG="${AGENT_SLUG:-}"
TENANT_NAME="${TENANT_NAME:-deepsecure}"
SKIP_BUILD="${SKIP_BUILD:-0}"
SCHEDULE="${SCHEDULE:-0 */1 * * *}"

if [[ -z "${AGENT_SLUG}" ]]; then
  echo "ERROR: AGENT_SLUG is required."
  echo ""
  usage
  exit 1
fi

AGENT_ID="${AGENT_ID:-${AGENT_SLUG}-${TENANT_NAME}-agent}"
JOB_NAME="${JOB_NAME:-${AGENT_SLUG}-${TENANT_NAME}-agent-job}"
SCHEDULER_NAME="${SCHEDULER_NAME:-trigger-${AGENT_SLUG}-${TENANT_NAME}-agent}"

# Map slugs to existing GCP service account short names (not always <slug>-sa).
case "${AGENT_SLUG}" in
  debugging)         DEFAULT_SA="debugging-agent-sa" ;;
  engineering-audit) DEFAULT_SA="engineering-audit-sa" ;;
  thunderbolt)       DEFAULT_SA="thunderbolt-agent-sa" ;;
  *)                 DEFAULT_SA="${AGENT_SLUG}-sa" ;;
esac
SA_EMAIL="${SERVICE_ACCOUNT:-${DEFAULT_SA}@${PROJECT_ID}.iam.gserviceaccount.com}"

SECRETS="GEMINI_API_KEY=gemini-api-key:latest"
SECRETS+=",ANTHROPIC_API_KEY=anthropic-api-key:latest"
SECRETS+=",OPENAI_API_KEY=openai-api-key:latest"

CONTROL_URL="https://app.deepsecure.one"
GATEWAY_URL="https://app.deepsecure.one/mcp"

echo "=== Deploying Agent to Cloud Run Jobs ==="
echo "Project:        ${PROJECT_ID}"
echo "Region:         ${REGION}"
echo "Agent Slug:     ${AGENT_SLUG}"
echo "Tenant:         ${TENANT_NAME}"
echo "Job:            ${JOB_NAME}"
echo "Agent ID:       ${AGENT_ID}"
echo "Scheduler:      ${SCHEDULER_NAME}"
echo "Service Account ${SA_EMAIL}"
echo "Schedule:       ${SCHEDULE}"
echo ""

IMAGE="${REGISTRY}/gemini-agent-sdk:${TAG}"
LATEST="${REGISTRY}/gemini-agent-sdk:latest"

if [[ "${SKIP_BUILD}" != "1" ]]; then
  echo "--- Building gemini-agent-sdk image (from Dockerfile.sdk) ---"
  gcloud auth configure-docker "${REGION}-docker.pkg.dev" --quiet

  docker buildx build --platform linux/amd64 \
    -f "${REPO_ROOT}/agents/gemini/Dockerfile.sdk" \
    -t "${IMAGE}" \
    -t "${LATEST}" \
    "${REPO_ROOT}"

  echo "--- Pushing gemini-agent-sdk image ---"
  docker push "${IMAGE}"
  docker push "${LATEST}"
  echo "✅ Image pushed: ${IMAGE}"
  echo ""
else
  echo "--- Skipping build (SKIP_BUILD=1) ---"
  echo ""
fi

# Use ; delimiter because LLM_PROVIDERS contains commas (gcloud --set-env-vars syntax).
ENV_VARS="^;^DEEPSECURE_CONTROL_URL=${CONTROL_URL}"
ENV_VARS+=";DEEPSECURE_GATEWAY_URL=${GATEWAY_URL}"
ENV_VARS+=";AGENT_ID=${AGENT_ID}"
ENV_VARS+=";AGENT_MAX_ROUNDS=3"
ENV_VARS+=";AGENT_PROMPTS_PER_DELEGATION=2"
ENV_VARS+=";AGENT_INTERVAL_SECONDS=60"
ENV_VARS+=";GEMINI_CLI_TRUST_WORKSPACE=true"
ENV_VARS+=";GEMINI_MODEL=gemini-2.5-flash"
ENV_VARS+=";PROMPT_TIMEOUT_SECONDS=300"
ENV_VARS+=";LLM_PROVIDERS=gemini,claude,codex"

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
    --description="Triggers ${JOB_NAME} (${AGENT_ID}) on schedule '${SCHEDULE}'"

fi

echo "✅ Cloud Scheduler ready: ${SCHEDULER_NAME}"
echo ""

# ── Step 4: Summary ─────────────────────────────────────────────────
echo "=== Deployment Complete ==="
echo ""
echo "Cloud Run Job:     ${JOB_NAME}"
echo "Agent ID:          ${AGENT_ID}"
echo "Cloud Scheduler:   ${SCHEDULER_NAME} (${SCHEDULE})"
echo "Service Account:   ${SA_EMAIL}"
echo "Image:             ${LATEST}"
echo ""
echo "Manual trigger:"
echo "  gcloud run jobs execute ${JOB_NAME} --region=${REGION} --project=${PROJECT_ID}"
echo ""
echo "View executions:"
echo "  gcloud run jobs executions list --job=${JOB_NAME} --region=${REGION} --project=${PROJECT_ID}"
echo ""
echo "View scheduler:"
echo "  gcloud scheduler jobs describe ${SCHEDULER_NAME} --location=${REGION} --project=${PROJECT_ID}"
