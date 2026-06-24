#!/usr/bin/env bash
# hermes-manager.sh — Phase 3: Full lifecycle manager with DeepSecure delegation_tokens
# Usage: hermes-manager.sh <spec-file> [--dry-run] [--max-iterations N]
#
# Phase 3 authority: plan → decompose → spawn agents → review → merge.
# Gated by DeepSecure delegation_tokens — scoped, ephemeral, auditable.
# Token revocation stops all execution immediately.
set -euo pipefail

DRY_RUN=false
MAX_ITERATIONS=5
IDENTITY_FILE="${AFK_IDENTITY_FILE:-.afk/identity.json}"
LOG_FILE="${AFK_LOG_DIR:-.hermes}/manager.log"
AUDIT_FILE="${AFK_LOG_DIR:-.hermes}/manager-audit.json"
CONTROL_URL="${DEEPSECURE_CONTROL_URL:-http://localhost:8000}"

# Parse --help before requiring positional arg
for arg in "$@"; do
    case "$arg" in
        --help|-h)
            echo "Usage: hermes-manager.sh <spec-file> [--dry-run] [--max-iterations N]"
            echo ""
            echo "Phase 3 Hermes Manager: full lifecycle with DeepSecure delegation_tokens."
            echo ""
            echo "Arguments:"
            echo "  spec-file         Design doc or spec to implement"
            echo ""
            echo "Options:"
            echo "  --dry-run         Show plan without executing"
            echo "  --max-iterations  Max Ralph iterations per task (default: 5)"
            echo ""
            echo "Environment:"
            echo "  DEEPSECURE_AGENT_ID     Required — agent identifier"
            echo "  DEEPSECURE_CONTROL_URL  Control Plane URL (default: http://localhost:8000)"
            echo "  USER_TOKEN              Required for initial bootstrap"
            exit 0
            ;;
    esac
done

SPEC_FILE=${1:?"Usage: hermes-manager.sh <spec-file> [--dry-run] [--max-iterations N]"}
shift || true
while [ $# -gt 0 ]; do
    case "$1" in
        --dry-run) DRY_RUN=true; shift ;;
        --max-iterations) MAX_ITERATIONS="${2:?--max-iterations requires a value}"; shift 2 ;;
        *) echo "Unknown option: $1"; exit 1 ;;
    esac
done

log() {
    local msg="[$(date -u +%Y-%m-%dT%H:%M:%SZ)] [manager] $1"
    echo "$msg" | tee -a "$LOG_FILE"
}

notify() {
    scripts/notify.sh "$1" "$2" "${3:-info}" 2>/dev/null || true
}

audit_event() {
    local event_type="$1"
    local details="$2"

    python3 -c "
import json, os
from datetime import datetime, timezone

event = {
    'timestamp': datetime.now(timezone.utc).isoformat(),
    'event_type': '$event_type',
    'agent_id': '${DEEPSECURE_AGENT_ID:-unknown}',
    'spec_file': '$SPEC_FILE',
    'details': '''$details'''
}

audit_path = '$AUDIT_FILE'
try:
    with open(audit_path) as f:
        events = json.load(f)
except (FileNotFoundError, json.JSONDecodeError):
    events = []

events.append(event)

with open(audit_path, 'w') as f:
    json.dump(events, f, indent=2)
" 2>/dev/null || log "⚠️  Audit event logging failed"
}

check_identity() {
    if [ -z "${DEEPSECURE_AGENT_ID:-}" ]; then
        log "❌ DEEPSECURE_AGENT_ID not set — Phase 3 requires identity"
        echo ""
        echo "Phase 3 Manager requires DeepSecure delegation_tokens."
        echo "Set up identity first:"
        echo "  export DEEPSECURE_AGENT_ID=<agent-id>"
        echo "  export USER_TOKEN=<user-token>"
        echo "  scripts/afk-identity.sh"
        exit 1
    fi

    # Verify token via identity-check hook
    if ! .claude/hooks/identity-check.sh 2>/dev/null; then
        log "❌ Identity check failed — cannot proceed"
        audit_event "identity_check_failed" "Token verification failed before execution"
        exit 1
    fi

    log "✅ Identity verified: $DEEPSECURE_AGENT_ID"
}

validate_spec() {
    if [ ! -f "$SPEC_FILE" ]; then
        log "❌ Spec file not found: $SPEC_FILE"
        exit 1
    fi

    log "Spec file validated: $SPEC_FILE"
}

extract_workstream() {
    # Extract workstream name from spec file path or content
    local workstream
    workstream=$(python3 -c "
import sys, os, re

spec_path = '$SPEC_FILE'
basename = os.path.basename(spec_path).replace('.md', '').replace('.plan', '')

# Try to extract from docs/workstreams/<name>/ path
parts = spec_path.split('/')
for i, part in enumerate(parts):
    if part == 'workstreams' and i + 1 < len(parts):
        print(parts[i + 1])
        sys.exit(0)

# Try to read workstream name from file content
try:
    with open(spec_path) as f:
        content = f.read(2000)
    match = re.search(r'workstream[:\s]+([a-z0-9-]+)', content, re.IGNORECASE)
    if match:
        print(match.group(1))
        sys.exit(0)
except:
    pass

# Fall back to filename
print(basename)
" 2>/dev/null || basename "$SPEC_FILE" .md)

    echo "$workstream"
}

plan_phase() {
    log "=== Phase: PLAN ==="
    audit_event "plan_start" "Beginning planning phase for $SPEC_FILE"

    local workstream
    workstream=$(extract_workstream)
    log "Workstream: $workstream"

    if [ "$DRY_RUN" = true ]; then
        log "[DRY RUN] Would run: /run-plan $workstream $SPEC_FILE"
        echo ""
        echo "=== DRY RUN: Plan Phase ==="
        echo "  Workstream: $workstream"
        echo "  Spec:       $SPEC_FILE"
        echo "  Command:    /run-plan $workstream $SPEC_FILE"
        echo ""
        audit_event "plan_dry_run" "Would plan $workstream from $SPEC_FILE"
        return 0
    fi

    # Re-verify identity before long-running operation
    check_identity

    log "Planning $workstream from $SPEC_FILE"
    claude --print \
        --permission-mode auto \
        --max-budget-usd 3 \
        --system-prompt "You are planning a workstream. Run: /run-plan $workstream $SPEC_FILE" \
        < /dev/null 2>&1 | tee -a "$LOG_FILE" || {
        log "❌ Plan phase failed"
        audit_event "plan_failed" "Claude Code planning returned error"
        return 1
    }

    audit_event "plan_complete" "Planning phase completed for $workstream"
    log "✅ Plan phase complete"
}

execute_phase() {
    log "=== Phase: EXECUTE ==="

    local workstream
    workstream=$(extract_workstream)

    # Find batch execution plan
    local bep="docs/workstreams/$workstream/BATCH_EXECUTION_PLAN.md"
    if [ ! -f "$bep" ]; then
        log "❌ No batch execution plan found: $bep"
        log "   Run plan phase first"
        return 1
    fi

    # Extract batch list from Quick Reference table
    local batches
    batches=$(grep -oE 'P[0-9]+-B[0-9]+' "$bep" | sort -u 2>/dev/null || echo "")

    if [ -z "$batches" ]; then
        log "❌ No batches found in $bep"
        return 1
    fi

    local batch_count
    batch_count=$(echo "$batches" | wc -l | tr -d ' ')
    log "Found $batch_count batches to execute"

    local completed=0
    for batch in $batches; do
        log "--- Batch: $batch ---"
        audit_event "batch_start" "Starting $batch for $workstream"

        # Re-verify identity before each batch
        if ! .claude/hooks/identity-check.sh 2>/dev/null; then
            log "❌ Identity check failed before $batch — token may be revoked"
            audit_event "batch_blocked" "$batch blocked by identity check failure"
            notify "Hermes Manager" "BLOCKED: $batch — token revoked or expired" error
            return 1
        fi

        if [ "$DRY_RUN" = true ]; then
            log "[DRY RUN] Would execute: /run-batch $batch $workstream"
            completed=$((completed + 1))
            continue
        fi

        claude --print \
            --permission-mode auto \
            --max-budget-usd 5 \
            --system-prompt "Execute batch. Run: /run-batch $batch $workstream" \
            < /dev/null 2>&1 | tee -a "$LOG_FILE" || {
            log "❌ Batch $batch failed"
            audit_event "batch_failed" "$batch execution failed"
            notify "Hermes Manager" "FAILED: $batch — manual review needed" error
            return 1
        }

        completed=$((completed + 1))
        audit_event "batch_complete" "$batch completed ($completed/$batch_count)"
        log "✅ Batch $batch complete ($completed/$batch_count)"
    done

    audit_event "execute_complete" "All $batch_count batches completed"
    log "✅ Execute phase complete ($completed/$batch_count batches)"
}

review_phase() {
    log "=== Phase: REVIEW ==="

    local workstream
    workstream=$(extract_workstream)

    # Re-verify identity
    check_identity

    if [ "$DRY_RUN" = true ]; then
        log "[DRY RUN] Would run adversarial review"
        echo ""
        echo "=== DRY RUN: Review Phase ==="
        echo "  Would run: adversarial-review.js on current branch"
        echo ""
        audit_event "review_dry_run" "Would review $workstream"
        return 0
    fi

    audit_event "review_start" "Starting adversarial review"

    # Use adversarial review workflow if available
    if [ -f ".claude/workflows/adversarial-review.js" ]; then
        log "Running adversarial review workflow"
        claude --print \
            --permission-mode auto \
            --max-budget-usd 2 \
            --system-prompt "Review recent changes for $workstream. Check for: security issues, test gaps, code quality. Be thorough." \
            < /dev/null 2>&1 | tee -a "$LOG_FILE" || {
            log "⚠️  Review had issues (non-blocking)"
        }
    else
        log "⚠️  adversarial-review.js not found — skipping automated review"
    fi

    audit_event "review_complete" "Review phase completed"
    log "✅ Review phase complete"
}

merge_phase() {
    log "=== Phase: MERGE ==="

    local workstream
    workstream=$(extract_workstream)

    # Final identity check
    check_identity

    if [ "$DRY_RUN" = true ]; then
        log "[DRY RUN] Would commit and push changes"
        echo ""
        echo "=== DRY RUN: Merge Phase ==="
        echo "  Would: git add, commit, push, create PR"
        echo ""
        audit_event "merge_dry_run" "Would merge $workstream"
        return 0
    fi

    audit_event "merge_start" "Starting merge phase"

    # Check for uncommitted changes
    if [ -z "$(git status --short)" ]; then
        log "No changes to merge"
        audit_event "merge_skip" "No uncommitted changes"
        return 0
    fi

    local branch
    branch=$(git branch --show-current)
    log "Merging on branch: $branch"

    git add -A
    git commit -m "Hermes Manager: $workstream implementation complete

Automated by hermes-manager.sh (Phase 3)
Agent: ${DEEPSECURE_AGENT_ID:-unknown}
Spec: $SPEC_FILE

Co-Authored-By: Hermes Manager <hermes@deepsecure.ai>" || {
        log "⚠️  Nothing to commit"
        return 0
    }

    git push origin "$branch" 2>&1 | tee -a "$LOG_FILE" || {
        log "❌ Push failed"
        audit_event "merge_push_failed" "git push to $branch failed"
        return 1
    }

    audit_event "merge_complete" "Changes pushed to $branch"
    log "✅ Merge phase complete"
}

# ── Main Lifecycle ────────────────────────────────────────────────────────────

mkdir -p "$(dirname "$LOG_FILE")" 2>/dev/null || true
mkdir -p "$(dirname "$AUDIT_FILE")" 2>/dev/null || true

log "╔══════════════════════════════════════════════════════════╗"
log "║  Hermes Manager — Phase 3: Full Lifecycle               ║"
log "╚══════════════════════════════════════════════════════════╝"
log ""
log "Spec:           $SPEC_FILE"
log "Dry run:        $DRY_RUN"
log "Max iterations: $MAX_ITERATIONS"
log "Agent:          ${DEEPSECURE_AGENT_ID:-not set}"
log ""

notify "Hermes Manager" "Starting Phase 3 lifecycle for $(basename "$SPEC_FILE")" info
audit_event "lifecycle_start" "Manager starting with spec $SPEC_FILE (dry_run=$DRY_RUN)"

# Pre-flight: verify identity
check_identity
validate_spec

# Execute lifecycle phases
LIFECYCLE_START=$(date +%s)
FAILED=false

for phase in plan execute review merge; do
    log ""
    if ! ${phase}_phase; then
        log "❌ Lifecycle failed at phase: $phase"
        audit_event "lifecycle_failed" "Failed at $phase phase"
        notify "Hermes Manager" "FAILED at $phase phase for $(basename "$SPEC_FILE")" error
        FAILED=true
        break
    fi

    # Re-verify identity between phases
    if [ "$phase" != "merge" ]; then
        if ! .claude/hooks/identity-check.sh 2>/dev/null; then
            log "❌ Identity revoked between phases — stopping"
            audit_event "lifecycle_revoked" "Token revoked after $phase phase"
            notify "Hermes Manager" "Token REVOKED — stopping after $phase" error
            FAILED=true
            break
        fi
    fi
done

LIFECYCLE_END=$(date +%s)
DURATION=$((LIFECYCLE_END - LIFECYCLE_START))

if [ "$FAILED" = true ]; then
    log ""
    log "❌ Lifecycle FAILED (${DURATION}s elapsed)"
    audit_event "lifecycle_end" "Failed after ${DURATION}s"
    exit 1
else
    log ""
    log "✅ Lifecycle COMPLETE (${DURATION}s elapsed)"
    audit_event "lifecycle_end" "Completed successfully in ${DURATION}s"
    notify "Hermes Manager" "Lifecycle complete for $(basename "$SPEC_FILE") (${DURATION}s)" success
    echo ""
    echo "✅ Hermes Manager lifecycle complete"
    echo "   Spec:     $SPEC_FILE"
    echo "   Duration: ${DURATION}s"
    echo "   Agent:    ${DEEPSECURE_AGENT_ID:-unknown}"
    echo "   Audit:    $AUDIT_FILE"
    exit 0
fi
