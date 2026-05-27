#!/usr/bin/env bash
set -euo pipefail

# =============================================================================
# DeepSecure Agent Provisioning Script
#
# Creates GCP infrastructure for a new DeepSecure agent:
#   - Service Account with required IAM roles
#   - Cloud Run Job (using gemini-agent container)
#   - Cloud Scheduler (cron trigger)
#
# Prerequisites:
#   1. Register the agent in the DeepSecure UI with "GCP Workload Identity"
#      and SA email: <agent-name>-sa@deepsecure-saas.iam.gserviceaccount.com
#   2. Create a delegation in the UI (select services + permissions, set TTL)
#   3. Run this script
#   4. Agent becomes Active on first successful scheduler run
#
# Usage:
#   ./scripts/provision-agent.sh <agent-name> [schedule]
#
# Examples:
#   ./scripts/provision-agent.sh sales-lead-gen
#   ./scripts/provision-agent.sh research-bot "0 */4 * * *"
#   ./scripts/provision-agent.sh daily-reporter "0 9 * * *"
# =============================================================================

PROJECT="deepsecure-saas"
REGION="us-central1"
IMAGE="us-central1-docker.pkg.dev/${PROJECT}/deepsecure/gemini-agent:latest"
CONTROL_URL="https://app.deepsecure.one"
GATEWAY_URL="https://app.deepsecure.one/mcp"

# --- Parse arguments ---
if [[ $# -lt 1 ]]; then
  echo "Usage: $0 <agent-name> [schedule]"
  echo ""
  echo "  agent-name   Short name for the agent (e.g., sales-lead-gen)"
  echo "  schedule     Cron schedule (default: every 2 hours = \"0 */2 * * *\")"
  echo ""
  echo "Examples:"
  echo "  $0 sales-lead-gen"
  echo "  $0 research-bot \"*/15 * * * *\""
  exit 1
fi

AGENT_NAME="$1"
SCHEDULE="${2:-0 */2 * * *}"

# --- Derived values ---
SA_NAME="${AGENT_NAME}-sa"
SA_EMAIL="${SA_NAME}@${PROJECT}.iam.gserviceaccount.com"
JOB_NAME="${AGENT_NAME}-deepsecure-agent"
SCHEDULER_NAME="trigger-${AGENT_NAME}"
JOB_URI="https://${REGION}-run.googleapis.com/apis/run.googleapis.com/v1/namespaces/${PROJECT}/jobs/${JOB_NAME}:run"

# --- Display plan ---
echo "============================================="
echo " DeepSecure Agent Provisioning"
echo "============================================="
echo ""
echo " Agent Name:     ${AGENT_NAME}"
echo " Service Account: ${SA_EMAIL}"
echo " Cloud Run Job:  ${JOB_NAME}"
echo " Scheduler:      ${SCHEDULER_NAME}"
echo " Schedule:       ${SCHEDULE}"
echo " Region:         ${REGION}"
echo " Image:          ${IMAGE}"
echo ""
echo "============================================="
echo ""

read -p "Proceed? (y/N) " -n 1 -r
echo ""
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
  echo "Aborted."
  exit 0
fi

echo ""

# --- Step 1: Create Service Account ---
echo "[1/6] Creating service account ${SA_NAME}..."
gcloud iam service-accounts create "${SA_NAME}" \
  --display-name="${AGENT_NAME}" \
  --project="${PROJECT}" 2>&1 || {
    echo "  ⚠️  SA may already exist, continuing..."
  }

# GCP eventual consistency — wait for SA to propagate
echo "  Waiting for IAM propagation..."
sleep 10

# --- Step 2: Grant SA permission to generate OIDC tokens ---
echo "[2/6] Granting serviceAccountTokenCreator..."
gcloud iam service-accounts add-iam-policy-binding "${SA_EMAIL}" \
  --project="${PROJECT}" \
  --member="serviceAccount:${SA_EMAIL}" \
  --role="roles/iam.serviceAccountTokenCreator" \
  --quiet

# --- Step 3: Grant Secret Manager access ---
echo "[3/6] Granting secretmanager.secretAccessor..."
gcloud projects add-iam-policy-binding "${PROJECT}" \
  --member="serviceAccount:${SA_EMAIL}" \
  --role="roles/secretmanager.secretAccessor" \
  --quiet

# --- Step 4: Grant Cloud Run developer ---
echo "[4/6] Granting run.developer..."
gcloud projects add-iam-policy-binding "${PROJECT}" \
  --member="serviceAccount:${SA_EMAIL}" \
  --role="roles/run.developer" \
  --quiet

# --- Step 5: Create Cloud Run Job ---
echo "[5/6] Creating Cloud Run Job ${JOB_NAME}..."
gcloud run jobs create "${JOB_NAME}" \
  --image="${IMAGE}" \
  --region="${REGION}" \
  --project="${PROJECT}" \
  --service-account="${SA_EMAIL}" \
  --set-secrets="GEMINI_API_KEY=gemini-api-key:latest" \
  --set-env-vars="AGENT_ID=${AGENT_NAME},DEEPSECURE_CONTROL_URL=${CONTROL_URL},DEEPSECURE_GATEWAY_URL=${GATEWAY_URL},AGENT_MAX_ITERATIONS=6,AGENT_INTERVAL_SECONDS=60,GEMINI_CLI_TRUST_WORKSPACE=true,GEMINI_MODEL=gemini-2.5-flash" \
  --task-timeout=1800 \
  --max-retries=1 \
  --memory=1Gi \
  --cpu=1

# Grant run.invoker on the job (must exist first)
echo "  Granting run.invoker on job..."
gcloud run jobs add-iam-policy-binding "${JOB_NAME}" \
  --region="${REGION}" \
  --project="${PROJECT}" \
  --member="serviceAccount:${SA_EMAIL}" \
  --role="roles/run.invoker"

# --- Step 6: Create Cloud Scheduler ---
echo "[6/6] Creating Cloud Scheduler ${SCHEDULER_NAME}..."
gcloud scheduler jobs create http "${SCHEDULER_NAME}" \
  --location="${REGION}" \
  --project="${PROJECT}" \
  --schedule="${SCHEDULE}" \
  --uri="${JOB_URI}" \
  --http-method=POST \
  --oauth-service-account-email="${SA_EMAIL}" \
  --oauth-token-scope="https://www.googleapis.com/auth/cloud-platform"

# --- Done ---
echo ""
echo "============================================="
echo " ✅ Agent provisioned successfully!"
echo "============================================="
echo ""
echo " SA Email:  ${SA_EMAIL}"
echo " Job:       ${JOB_NAME}"
echo " Scheduler: ${SCHEDULER_NAME} (${SCHEDULE})"
echo ""
echo " Next steps:"
echo "   1. Verify agent is registered in UI with selector:"
echo "      ${SA_EMAIL}"
echo "   2. Ensure delegation exists with desired permissions"
echo "   3. Force first run:  gcloud scheduler jobs run ${SCHEDULER_NAME} --location=${REGION} --project=${PROJECT}"
echo "   4. Check logs:       gcloud logging read 'resource.type=\"cloud_run_job\" AND resource.labels.job_name=\"${JOB_NAME}\"' --project=${PROJECT} --limit=20 --format='value(timestamp,textPayload)' --freshness=15m"
echo ""
