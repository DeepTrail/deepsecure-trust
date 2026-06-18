#!/usr/bin/env bash
# deploy-afk-cloud.sh — Deploy AFK cloud container to GCP Cloud Run Jobs or AWS ECS
# Usage: deploy-afk-cloud.sh <platform> [options]
#
# Platforms:
#   gcp     — Deploy as GCP Cloud Run Job
#   aws     — Deploy as AWS ECS Fargate task
#   build   — Build and push container image only
#
# Options:
#   --workstream <name>    Workstream to run (required for gcp/aws)
#   --branch <name>        Git branch (default: current branch)
#   --max-iterations <n>   Max ralph iterations (default: 10)
#   --dry-run              Show commands without executing
set -euo pipefail

PLATFORM="${1:?"Usage: deploy-afk-cloud.sh <gcp|aws|build> [options]"}"
shift

# Defaults
WORKSTREAM=""
BRANCH=$(git branch --show-current 2>/dev/null || echo "dev")
MAX_ITER=10
DRY_RUN=false
IMAGE_NAME="afk-cloud"
GCP_PROJECT="${GCP_PROJECT:-}"
GCP_REGION="${GCP_REGION:-us-central1}"
AWS_REGION="${AWS_REGION:-us-east-1}"

# Parse options
while [ $# -gt 0 ]; do
    case "$1" in
        --workstream) WORKSTREAM="$2"; shift 2 ;;
        --branch) BRANCH="$2"; shift 2 ;;
        --max-iterations) MAX_ITER="$2"; shift 2 ;;
        --dry-run) DRY_RUN=true; shift ;;
        *) echo "Unknown option: $1" >&2; exit 1 ;;
    esac
done

log() {
    echo "[deploy] $1"
}

run_cmd() {
    if [ "$DRY_RUN" = true ]; then
        echo "[DRY RUN] $*"
    else
        "$@"
    fi
}

# ── Build & Push ─────────────────────────────────────────────────────────────
build_and_push() {
    log "Building cloud image..."
    run_cmd docker build -f Dockerfile.afk-cloud -t "$IMAGE_NAME" .

    case "$PLATFORM" in
        gcp)
            REGISTRY="gcr.io/${GCP_PROJECT}/${IMAGE_NAME}"
            log "Tagging for GCR: $REGISTRY"
            run_cmd docker tag "$IMAGE_NAME" "$REGISTRY"
            run_cmd docker push "$REGISTRY"
            ;;
        aws)
            ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text 2>/dev/null || echo "UNKNOWN")
            REGISTRY="${ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com/${IMAGE_NAME}"
            log "Tagging for ECR: $REGISTRY"
            run_cmd aws ecr get-login-password --region "$AWS_REGION" | docker login --username AWS --password-stdin "${ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com"
            run_cmd docker tag "$IMAGE_NAME" "$REGISTRY"
            run_cmd docker push "$REGISTRY"
            ;;
    esac
}

# ── GCP Cloud Run Job ────────────────────────────────────────────────────────
deploy_gcp() {
    [ -z "$WORKSTREAM" ] && { echo "ERROR: --workstream required" >&2; exit 1; }
    [ -z "$GCP_PROJECT" ] && { echo "ERROR: GCP_PROJECT env var required" >&2; exit 1; }

    build_and_push

    JOB_NAME="afk-${WORKSTREAM}"
    REGISTRY="gcr.io/${GCP_PROJECT}/${IMAGE_NAME}"

    log "Deploying Cloud Run Job: $JOB_NAME"
    run_cmd gcloud run jobs create "$JOB_NAME" \
        --image "$REGISTRY" \
        --region "$GCP_REGION" \
        --task-timeout 3600s \
        --max-retries 0 \
        --memory 2Gi \
        --cpu 2 \
        --set-env-vars "AFK_REPO_URL=$(git remote get-url origin),AFK_BRANCH=$BRANCH,AFK_WORKSTREAM=$WORKSTREAM,AFK_MAX_ITERATIONS=$MAX_ITER" \
        --set-secrets "ANTHROPIC_API_KEY=anthropic-api-key:latest" \
        --project "$GCP_PROJECT" \
        2>/dev/null || \
    run_cmd gcloud run jobs update "$JOB_NAME" \
        --image "$REGISTRY" \
        --region "$GCP_REGION" \
        --set-env-vars "AFK_REPO_URL=$(git remote get-url origin),AFK_BRANCH=$BRANCH,AFK_WORKSTREAM=$WORKSTREAM,AFK_MAX_ITERATIONS=$MAX_ITER" \
        --project "$GCP_PROJECT"

    log "Job deployed. Execute with:"
    log "  gcloud run jobs execute $JOB_NAME --region $GCP_REGION --project $GCP_PROJECT"
}

# ── AWS ECS ──────────────────────────────────────────────────────────────────
deploy_aws() {
    [ -z "$WORKSTREAM" ] && { echo "ERROR: --workstream required" >&2; exit 1; }

    build_and_push

    TASK_FAMILY="afk-${WORKSTREAM}"

    log "Registering ECS task definition: $TASK_FAMILY"
    run_cmd aws ecs register-task-definition \
        --cli-input-json "file://infra/afk-ecs-task.json" \
        --region "$AWS_REGION"

    log "Task registered. Run with:"
    log "  aws ecs run-task --task-definition $TASK_FAMILY --launch-type FARGATE --region $AWS_REGION"
}

# ── Main ─────────────────────────────────────────────────────────────────────
case "$PLATFORM" in
    gcp)   deploy_gcp ;;
    aws)   deploy_aws ;;
    build) build_and_push ;;
    *)     echo "Unknown platform: $PLATFORM (use gcp, aws, or build)" >&2; exit 1 ;;
esac

log "Done."
