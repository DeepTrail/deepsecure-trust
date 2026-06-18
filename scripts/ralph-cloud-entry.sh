#!/usr/bin/env bash
# ralph-cloud-entry.sh — Cloud container entry point for AFK execution
# Clones the repo, checks out the target branch, and delegates to ralph.sh.
#
# Required environment variables:
#   ANTHROPIC_API_KEY  — Claude API key
#   AFK_REPO_URL       — Git clone URL (SSH or HTTPS)
#   AFK_BRANCH         — Branch to check out
#   AFK_WORKSTREAM     — Workstream name for ralph.sh
#
# Optional:
#   AFK_MAX_ITERATIONS — Max ralph iterations (default: 10)
#   AFK_MAX_BUDGET     — Max budget per iteration in USD (default: 5.00)
#   AFK_CLOUD_ENV      — Cloud environment label (default: auto-detected)
#   AFK_SSH_KEY        — Base64-encoded SSH private key for git clone
set -euo pipefail

REPO_URL="${AFK_REPO_URL:?"AFK_REPO_URL is required"}"
BRANCH="${AFK_BRANCH:?"AFK_BRANCH is required"}"
WORKSTREAM="${AFK_WORKSTREAM:?"AFK_WORKSTREAM is required"}"
MAX_ITER="${AFK_MAX_ITERATIONS:-10}"

: "${ANTHROPIC_API_KEY:?"ANTHROPIC_API_KEY is required"}"

# Auto-detect cloud environment
if [ -z "${AFK_CLOUD_ENV:-}" ]; then
    if [ -n "${K_SERVICE:-}" ]; then
        export AFK_CLOUD_ENV="gcp-cloud-run"
    elif [ -n "${ECS_CONTAINER_METADATA_URI:-}" ]; then
        export AFK_CLOUD_ENV="aws-ecs"
    else
        export AFK_CLOUD_ENV="cloud-generic"
    fi
fi

log() {
    echo "[$(date -u +%Y-%m-%dT%H:%M:%SZ)] [cloud-entry] $1"
}

log "Starting AFK cloud execution"
log "  Repo: $REPO_URL"
log "  Branch: $BRANCH"
log "  Workstream: $WORKSTREAM"
log "  Max iterations: $MAX_ITER"
log "  Cloud env: $AFK_CLOUD_ENV"

# Set up SSH key if provided (base64-encoded)
if [ -n "${AFK_SSH_KEY:-}" ]; then
    mkdir -p ~/.ssh
    echo "$AFK_SSH_KEY" | base64 -d > ~/.ssh/id_ed25519
    chmod 600 ~/.ssh/id_ed25519
    log "SSH key configured"
fi

# Clone repository
WORK_DIR="/tmp/afk-repo"
log "Cloning repository..."
git clone --depth 50 --branch "$BRANCH" "$REPO_URL" "$WORK_DIR"
cd "$WORK_DIR"

log "Checked out branch: $(git branch --show-current)"
log "HEAD: $(git log --oneline -1)"

# Export budget for ralph.sh
export RALPH_MAX_BUDGET="${AFK_MAX_BUDGET:-5.00}"

# Run ralph.sh
log "Delegating to ralph.sh..."
EXIT_CODE=0
bash scripts/ralph.sh "$WORKSTREAM" "$MAX_ITER" || EXIT_CODE=$?

# Push results back
if [ "$EXIT_CODE" -eq 0 ]; then
    log "Ralph completed successfully"
    if git diff --quiet && git diff --cached --quiet; then
        log "No changes to push"
    else
        git add -A
        git commit -m "AFK cloud run: $WORKSTREAM ($(date -u +%Y-%m-%dT%H:%M:%SZ))"
        git push origin "$BRANCH"
        log "Results pushed to $BRANCH"
    fi
else
    log "Ralph exited with code $EXIT_CODE"
fi

# Send notification
bash scripts/notify.sh "AFK Cloud Complete" \
    "Workstream: $WORKSTREAM, Exit: $EXIT_CODE, Env: $AFK_CLOUD_ENV" \
    "$([ $EXIT_CODE -eq 0 ] && echo success || echo error)" 2>/dev/null || true

log "Cloud entry point finished (exit $EXIT_CODE)"
exit $EXIT_CODE
