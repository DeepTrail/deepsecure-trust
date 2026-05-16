#!/usr/bin/env bash
set -euo pipefail

PROJECT_ID="${GCP_PROJECT_ID:-deepsecure-saas}"
REGION="${GCP_REGION:-us-central1}"
INSTANCE_NAME="${CLOUD_SQL_INSTANCE:-deepsecure-db}"
REGISTRY="${REGION}-docker.pkg.dev/${PROJECT_ID}/deepsecure"
CONNECTION_NAME="${PROJECT_ID}:${REGION}:${INSTANCE_NAME}"

MODE="${1:-job}"

case "$MODE" in
  job)
    echo "=== Running migrations via Cloud Run Job ==="

    DB_PASSWORD=$(gcloud secrets versions access latest --secret="db-password" --project="${PROJECT_ID}")
    DATABASE_URL="postgresql://deepsecure_user:${DB_PASSWORD}@/deeptrail_controldb?host=/cloudsql/${CONNECTION_NAME}"

    JOB_ARGS=(
      --image="${REGISTRY}/deeptrail-control:latest"
      --region="${REGION}"
      --project="${PROJECT_ID}"
      --set-cloudsql-instances="${CONNECTION_NAME}"
      --service-account="deepsecure-runner@${PROJECT_ID}.iam.gserviceaccount.com"
      --set-env-vars="DATABASE_URL=${DATABASE_URL},CLOUD_RUN=true"
      --command="alembic"
      --args="upgrade,head"
      --max-retries=0
      --task-timeout=300s
    )

    if gcloud run jobs describe alembic-migrate --region="${REGION}" --project="${PROJECT_ID}" &>/dev/null; then
      echo "Updating existing migration job with latest image..."
      gcloud run jobs update alembic-migrate "${JOB_ARGS[@]}"
    else
      echo "Creating migration job..."
      gcloud run jobs create alembic-migrate "${JOB_ARGS[@]}"
    fi

    echo "Executing migration job..."
    gcloud run jobs execute alembic-migrate \
      --region="${REGION}" \
      --project="${PROJECT_ID}" \
      --wait

    echo "=== Migration complete ==="
    ;;

  local)
    echo "=== Running migrations locally via cloud-sql-proxy ==="
    echo "Starting cloud-sql-proxy..."

    cloud-sql-proxy "${CONNECTION_NAME}" --port=5433 &
    PROXY_PID=$!
    sleep 3

    DB_PASSWORD=$(gcloud secrets versions access latest --secret="db-password" --project="${PROJECT_ID}")
    export DATABASE_URL="postgresql://deepsecure_user:${DB_PASSWORD}@localhost:5433/deeptrail_controldb"

    echo "Running alembic upgrade head..."
    cd deeptrail-control
    alembic upgrade head
    cd ..

    echo "Stopping cloud-sql-proxy..."
    kill $PROXY_PID 2>/dev/null || true

    echo "=== Migration complete ==="
    ;;

  *)
    echo "Usage: $0 [job|local]"
    echo "  job   - Run via Cloud Run Job (default, recommended)"
    echo "  local - Run locally via cloud-sql-proxy"
    exit 1
    ;;
esac
