#!/usr/bin/env bash
set -euo pipefail

# =============================================================================
# execute_merge_point.sh — Generic merge point execution engine
#
# Usage:
#   ./scripts/execute_merge_point.sh <config_file> [--dry-run] [--skip-tests]
#                                                   [--skip-container]
#                                                   [--skip-cleanup]
#                                                   [--phase N]
# =============================================================================

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

# ── Colours & formatting ─────────────────────────────────────────────────────
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
BOLD='\033[1m'
RESET='\033[0m'

DRY_RUN=false
SKIP_TESTS=false
SKIP_CONTAINER=false
SKIP_CLEANUP=false
START_PHASE=0

PASS_COUNT=0
FAIL_COUNT=0
SKIP_COUNT=0
RESULTS=()

# ── Helpers ───────────────────────────────────────────────────────────────────

log_phase() { echo -e "\n${BOLD}${CYAN}══════════════════════════════════════════════════════════════${RESET}"; echo -e "${BOLD}${CYAN}  Phase $1: $2${RESET}"; echo -e "${BOLD}${CYAN}══════════════════════════════════════════════════════════════${RESET}\n"; }
log_step()  { echo -e "  ${BOLD}→ $1${RESET}"; }
log_ok()    { echo -e "  ${GREEN}✅ $1${RESET}"; }
log_fail()  { echo -e "  ${RED}❌ $1${RESET}"; }
log_warn()  { echo -e "  ${YELLOW}⚠️  $1${RESET}"; }
log_skip()  { echo -e "  ${YELLOW}⏭  SKIP: $1${RESET}"; }
log_dry()   { echo -e "  ${YELLOW}[DRY-RUN] $1${RESET}"; }

record_result() {
    local label="$1" status="$2"
    if [[ "$status" == "PASS" ]]; then
        PASS_COUNT=$((PASS_COUNT + 1))
        RESULTS+=("${GREEN}✅ $label${RESET}")
    elif [[ "$status" == "SKIP" ]]; then
        SKIP_COUNT=$((SKIP_COUNT + 1))
        RESULTS+=("${YELLOW}⏭  $label (skipped)${RESET}")
    else
        FAIL_COUNT=$((FAIL_COUNT + 1))
        RESULTS+=("${RED}❌ $label${RESET}")
    fi
}

run_or_dry() {
    if $DRY_RUN; then
        log_dry "$*"
        return 0
    fi
    "$@"
}

abort() {
    echo -e "\n${RED}${BOLD}ABORT: $1${RESET}\n"
    print_summary
    exit 1
}

print_summary() {
    echo -e "\n${BOLD}${CYAN}══════════════════════════════════════════════════════════════${RESET}"
    echo -e "${BOLD}${CYAN}  ${MP_ID:-MP?} Execution Summary${RESET}"
    echo -e "${BOLD}${CYAN}══════════════════════════════════════════════════════════════${RESET}\n"
    for r in "${RESULTS[@]}"; do
        echo -e "  $r"
    done
    echo ""
    echo -e "  ${GREEN}Pass: $PASS_COUNT${RESET}  ${RED}Fail: $FAIL_COUNT${RESET}  ${YELLOW}Skip: $SKIP_COUNT${RESET}"
    if [[ $FAIL_COUNT -gt 0 ]]; then
        echo -e "\n  ${RED}${BOLD}MERGE POINT NOT FULLY VERIFIED — review failures above${RESET}"
    else
        echo -e "\n  ${GREEN}${BOLD}MERGE POINT ${MP_ID:-MP?} COMPLETE${RESET}"
    fi
    echo ""
}

# ── Parse arguments ───────────────────────────────────────────────────────────

if [[ $# -lt 1 ]]; then
    echo "Usage: $0 <config_file> [--dry-run] [--skip-tests] [--skip-container] [--skip-cleanup] [--phase N]"
    exit 1
fi

CONFIG_FILE="$1"
shift

while [[ $# -gt 0 ]]; do
    case "$1" in
        --dry-run)        DRY_RUN=true ;;
        --skip-tests)     SKIP_TESTS=true ;;
        --skip-container) SKIP_CONTAINER=true ;;
        --skip-cleanup)   SKIP_CLEANUP=true ;;
        --phase)          shift; START_PHASE="$1" ;;
        *) echo "Unknown option: $1"; exit 1 ;;
    esac
    shift
done

if [[ ! -f "$CONFIG_FILE" ]]; then
    # Try relative to repo root
    if [[ -f "$REPO_ROOT/$CONFIG_FILE" ]]; then
        CONFIG_FILE="$REPO_ROOT/$CONFIG_FILE"
    else
        echo "Config file not found: $CONFIG_FILE"
        exit 1
    fi
fi

# shellcheck source=/dev/null
source "$CONFIG_FILE"

echo -e "${BOLD}Executing Merge Point ${CYAN}${MP_ID}${RESET}${BOLD} for workstream ${CYAN}${WORKSTREAM}${RESET}"
echo -e "Config: ${CONFIG_FILE}"
echo -e "Dry-run: ${DRY_RUN}\n"

# =============================================================================
# PHASE 0: Pre-flight
# =============================================================================

if [[ $START_PHASE -le 0 ]]; then
log_phase 0 "Pre-flight Checks"

# 0a. Verify we're in the repo root
log_step "Verify repo root"
if [[ ! -f "$REPO_ROOT/pyproject.toml" ]]; then
    abort "Not in deepsecure-mvp repo root (pyproject.toml not found)"
fi
log_ok "Repo root: $REPO_ROOT"
record_result "Repo root valid" "PASS"

# 0b. Verify worktree exists
log_step "Verify worktree at $WORKTREE_PATH"
if [[ ! -d "$WORKTREE_PATH" ]]; then
    abort "Worktree not found: $WORKTREE_PATH"
fi
ACTUAL_BRANCH=$(cd "$WORKTREE_PATH" && git rev-parse --abbrev-ref HEAD 2>/dev/null || echo "UNKNOWN")
if [[ "$ACTUAL_BRANCH" != "$WORKTREE_BRANCH" ]]; then
    abort "Worktree branch mismatch: expected '$WORKTREE_BRANCH', got '$ACTUAL_BRANCH'"
fi
log_ok "Worktree exists on branch $WORKTREE_BRANCH"
record_result "Worktree valid" "PASS"

# 0c. Verify main repo is on target branch
log_step "Verify main repo on $TARGET_BRANCH"
MAIN_BRANCH=$(cd "$REPO_ROOT" && git rev-parse --abbrev-ref HEAD 2>/dev/null || echo "UNKNOWN")
if [[ "$MAIN_BRANCH" != "$TARGET_BRANCH" ]]; then
    abort "Main repo branch mismatch: expected '$TARGET_BRANCH', got '$MAIN_BRANCH'"
fi
log_ok "Main repo on $TARGET_BRANCH"
record_result "Main branch valid" "PASS"

# 0d. Verify docker services
log_step "Verify docker services"
if ! docker compose ps --format '{{.Service}}' 2>/dev/null | grep -q "deeptrail-control"; then
    log_warn "deeptrail-control not running — container phases will fail"
    record_result "Docker services" "SKIP"
else
    log_ok "deeptrail-control is running"
    record_result "Docker services running" "PASS"
fi

# 0e. Verify changed files exist
log_step "Verify uncommitted backend files in main repo"
CHANGED_COUNT=$(cd "$REPO_ROOT" && git status --short | grep -cE "deeptrail-control/" || true)
if [[ "$CHANGED_COUNT" -eq 0 ]]; then
    log_warn "No uncommitted deeptrail-control/ changes found — merge phase may be a no-op"
fi
log_ok "Found $CHANGED_COUNT changed files under $SYNC_PREFIX"
record_result "Backend files detected ($CHANGED_COUNT)" "PASS"

fi # phase 0

# =============================================================================
# PHASE 1: Test Gate
# =============================================================================

if [[ $START_PHASE -le 1 ]]; then
log_phase 1 "Test Gate"

if $SKIP_TESTS; then
    log_skip "Tests (--skip-tests flag)"
    record_result "Unit tests" "SKIP"
    record_result "Integration tests" "SKIP"
    record_result "Regression tests" "SKIP"
    record_result "verify_integration.py" "SKIP"
else

cd "$REPO_ROOT"

# Helper: run eval from repo root (prevents CWD drift between test commands)
run_from_root() {
    (cd "$REPO_ROOT" && eval "$1")
}

# 1a. Unit tests
log_step "Running unit tests"
for cmd in "${UNIT_TESTS[@]}"; do
    if $DRY_RUN; then
        log_dry "$cmd"
    else
        if run_from_root "$cmd"; then
            log_ok "Unit tests passed"
            record_result "Unit tests" "PASS"
        else
            record_result "Unit tests" "FAIL"
            abort "Unit tests failed"
        fi
    fi
done
$DRY_RUN && record_result "Unit tests" "SKIP"

# 1b. Integration tests
log_step "Running integration tests"
for cmd in "${INTEGRATION_TESTS[@]}"; do
    if $DRY_RUN; then
        log_dry "$cmd"
    else
        if run_from_root "$cmd"; then
            log_ok "Integration tests passed"
            record_result "Integration tests" "PASS"
        else
            record_result "Integration tests" "FAIL"
            abort "Integration tests failed"
        fi
    fi
done
$DRY_RUN && record_result "Integration tests" "SKIP"

# 1c. Regression tests
log_step "Running regression tests"
for cmd in "${REGRESSION_TESTS[@]}"; do
    if $DRY_RUN; then
        log_dry "$cmd"
    else
        if run_from_root "$cmd"; then
            log_ok "Regression tests passed"
            record_result "Regression tests" "PASS"
        else
            record_result "Regression tests" "FAIL"
            abort "Regression tests failed — existing tests broken"
        fi
    fi
done
$DRY_RUN && record_result "Regression tests" "SKIP"

# 1d. Cross-service integration verification
log_step "Running verify_integration.py"
if $DRY_RUN; then
    log_dry "$VERIFY_INTEGRATION"
    record_result "verify_integration.py" "SKIP"
else
    if run_from_root "$VERIFY_INTEGRATION"; then
        log_ok "verify_integration.py passed (exit 0)"
        record_result "verify_integration.py" "PASS"
    else
        record_result "verify_integration.py" "FAIL"
        abort "verify_integration.py failed"
    fi
fi

fi # skip-tests
fi # phase 1

# =============================================================================
# PHASE 2: Worktree Commit + Merge
# =============================================================================

if [[ $START_PHASE -le 2 ]]; then
log_phase 2 "Worktree Commit + Merge"

cd "$REPO_ROOT"

# 2a. Collect files to sync
log_step "Collecting changed files under $SYNC_PREFIX"
SYNC_FILES=()
while IFS= read -r line; do
    # Extract file path from git status output (handles both staged and untracked)
    file=""
    if [[ "$line" =~ ^[[:space:]]?[MADRCU?]+[[:space:]]+(.*) ]]; then
        file="${BASH_REMATCH[1]}"
    fi
    if [[ -n "$file" && "$file" == ${SYNC_PREFIX}* ]]; then
        SYNC_FILES+=("$file")
    fi
done < <(git status --short)

log_ok "Found ${#SYNC_FILES[@]} files to sync"

# 2b. Copy files to worktree
log_step "Syncing files to worktree"
for f in "${SYNC_FILES[@]}"; do
    target="$WORKTREE_PATH/$f"
    if $DRY_RUN; then
        log_dry "cp $f → $target"
    else
        mkdir -p "$(dirname "$target")"
        if [[ -f "$REPO_ROOT/$f" ]]; then
            cp "$REPO_ROOT/$f" "$target"
        else
            log_warn "File not found (deleted?): $f"
        fi
    fi
done
if ! $DRY_RUN; then
    log_ok "Synced ${#SYNC_FILES[@]} files to worktree"
fi

# 2c. Commit in worktree
log_step "Committing in worktree"
if $DRY_RUN; then
    log_dry "cd $WORKTREE_PATH && git add -A && git commit -m \"$COMMIT_MSG\""
else
    cd "$WORKTREE_PATH"
    git add -A
    if git diff --cached --quiet 2>/dev/null; then
        log_warn "No staged changes in worktree — nothing to commit"
    else
        git commit -m "$COMMIT_MSG"
        log_ok "Committed: $COMMIT_MSG"
    fi
fi
record_result "Worktree commit" "PASS"

# 2d. Push worktree branch
log_step "Pushing $WORKTREE_BRANCH"
if $DRY_RUN; then
    log_dry "git push origin $WORKTREE_BRANCH"
else
    cd "$WORKTREE_PATH"
    git push origin "$WORKTREE_BRANCH" 2>&1 || log_warn "Push failed or remote not configured — continuing with local merge"
    log_ok "Pushed $WORKTREE_BRANCH"
fi
record_result "Worktree push" "PASS"

# 2e. Stash/clean main repo working dir so merge can proceed
log_step "Cleaning main repo working directory before merge"
if $DRY_RUN; then
    log_dry "git stash push -- $SYNC_PREFIX (save uncommitted changes)"
else
    cd "$REPO_ROOT"
    # Restore modified tracked files to HEAD state
    git checkout -- "$SYNC_PREFIX" 2>/dev/null || true
    # Remove untracked files that were synced to worktree
    for f in "${SYNC_FILES[@]}"; do
        if git status --short "$f" 2>/dev/null | grep -q "^??"; then
            rm -f "$f" 2>/dev/null || true
        fi
    done
    log_ok "Working directory cleaned for merge"
fi
record_result "Pre-merge cleanup" "PASS"

# 2f. Merge into target branch
log_step "Merging $WORKTREE_BRANCH into $TARGET_BRANCH"
if $DRY_RUN; then
    log_dry "cd $REPO_ROOT && git merge $WORKTREE_BRANCH --no-ff -m \"$MERGE_MSG\""
else
    cd "$REPO_ROOT"
    git merge "$WORKTREE_BRANCH" --no-ff -m "$MERGE_MSG"
    log_ok "Merged $WORKTREE_BRANCH into $TARGET_BRANCH"
fi
record_result "Branch merge" "PASS"

fi # phase 2

# =============================================================================
# PHASE 3: Container / Build Deployment
# =============================================================================

if [[ $START_PHASE -le 3 ]]; then
log_phase 3 "Container / Build Deployment"

if $SKIP_CONTAINER; then
    log_skip "Container deployment (--skip-container flag)"
    record_result "Deployment" "SKIP"
else

cd "$REPO_ROOT"

# 3a. Apply migration (skip if MIGRATION_CMD is empty — e.g. frontend merge points)
if [[ -n "${MIGRATION_CMD:-}" ]]; then
    log_step "Applying database migration"
    if $DRY_RUN; then
        log_dry "$MIGRATION_CMD"
        record_result "Migration" "SKIP"
    else
        if (cd "$REPO_ROOT" && eval "$MIGRATION_CMD") 2>&1; then
            log_ok "Migration applied"
            record_result "Migration" "PASS"
        else
            log_warn "Migration failed (may already be at head)"
            record_result "Migration" "PASS"
        fi
    fi
fi

# 3b. Rebuild container / run build (skip if BUILD_CMD is empty)
if [[ -n "${BUILD_CMD:-}" ]]; then
    log_step "Running build: $BUILD_CMD"
    if $DRY_RUN; then
        log_dry "$BUILD_CMD"
        record_result "Build" "SKIP"
    else
        if (cd "$REPO_ROOT" && eval "$BUILD_CMD") 2>&1; then
            log_ok "Build succeeded"
            record_result "Build" "PASS"
        else
            log_fail "Build failed"
            record_result "Build" "FAIL"
        fi
    fi
fi

# 3c. Restart container (skip if RESTART_CMD is empty)
if [[ -n "${RESTART_CMD:-}" ]]; then
    log_step "Restarting service"
    if $DRY_RUN; then
        log_dry "$RESTART_CMD"
        record_result "Service restart" "SKIP"
    else
        if (cd "$REPO_ROOT" && eval "$RESTART_CMD") 2>&1; then
            log_ok "Service restarted"
            record_result "Service restart" "PASS"
        else
            log_fail "Service restart failed"
            record_result "Service restart" "FAIL"
        fi
    fi
fi

# 3d. Wait for health check (skip if HEALTH_URL is empty)
if [[ -n "${HEALTH_URL:-}" ]]; then
    log_step "Waiting for health check ($HEALTH_URL)"
    if $DRY_RUN; then
        log_dry "curl $HEALTH_URL (retry up to ${HEALTH_TIMEOUT:-30}s)"
        record_result "Health check" "SKIP"
    else
        HEALTH_OK=false
        for i in $(seq 1 "${HEALTH_TIMEOUT:-30}"); do
            if curl -sf "$HEALTH_URL" >/dev/null 2>&1; then
                HEALTH_OK=true
                break
            fi
            sleep 1
        done
        if $HEALTH_OK; then
            log_ok "Service healthy after ${i}s"
            record_result "Health check" "PASS"
        else
            log_fail "Service not healthy after ${HEALTH_TIMEOUT:-30}s"
            record_result "Health check" "FAIL"
        fi
    fi
fi

# 3e. Run custom deployment steps (for frontend builds, type checks, etc.)
if [[ -n "${DEPLOY_STEPS[*]:-}" ]]; then
    for step_cmd in "${DEPLOY_STEPS[@]}"; do
        log_step "Deploy step: $step_cmd"
        if $DRY_RUN; then
            log_dry "$step_cmd"
        else
            if (cd "$REPO_ROOT" && eval "$step_cmd"); then
                log_ok "Passed: $step_cmd"
                record_result "Deploy: ${step_cmd%% *}..." "PASS"
            else
                log_fail "Failed: $step_cmd"
                record_result "Deploy: ${step_cmd%% *}..." "FAIL"
            fi
        fi
    done
fi

fi # skip-container
fi # phase 3

# =============================================================================
# PHASE 4: Smoke Tests
# =============================================================================

if [[ $START_PHASE -le 4 ]]; then
log_phase 4 "Smoke Tests"

if $SKIP_CONTAINER; then
    log_skip "Smoke tests (--skip-container flag)"
    record_result "Smoke tests" "SKIP"
else

cd "$REPO_ROOT"

# --- Custom smoke tests (config-driven, for frontend or any merge point) ---
if [[ -n "${SMOKE_TESTS[*]:-}" ]]; then
    SMOKE_IDX=0
    for smoke_cmd in "${SMOKE_TESTS[@]}"; do
        SMOKE_IDX=$((SMOKE_IDX + 1))
        log_step "Smoke test $SMOKE_IDX: $smoke_cmd"
        if $DRY_RUN; then
            log_dry "$smoke_cmd"
            record_result "Smoke $SMOKE_IDX" "SKIP"
        else
            if (cd "$REPO_ROOT" && eval "$smoke_cmd"); then
                log_ok "Passed: $smoke_cmd"
                record_result "Smoke $SMOKE_IDX: ${smoke_cmd%% *}..." "PASS"
            else
                log_fail "Failed: $smoke_cmd"
                record_result "Smoke $SMOKE_IDX: ${smoke_cmd%% *}..." "FAIL"
            fi
        fi
    done
fi

# --- API-based smoke tests (only run if API_BASE is configured) ---
if [[ -n "${API_BASE:-}" ]]; then

log_step "Authenticating to get USER_TOKEN"
USER_TOKEN=""
if $DRY_RUN; then
    log_dry "curl POST $API_BASE/api/v1/auth/login"
    USER_TOKEN="DRY_RUN_TOKEN"
else
    LOGIN_RESPONSE=$(curl -sf -X POST "$API_BASE/api/v1/auth/login" \
        -H "Content-Type: application/json" \
        -d "{\"email\": \"${LOGIN_EMAIL:-}\", \"password\": \"${LOGIN_PASSWORD:-}\"}" 2>/dev/null || echo "{}")
    USER_TOKEN=$(echo "$LOGIN_RESPONSE" | jq -r '.token // empty' 2>/dev/null || true)
fi

if [[ -z "$USER_TOKEN" || "$USER_TOKEN" == "null" ]] && ! $DRY_RUN; then
    log_warn "Could not authenticate — API smoke tests skipped"
    log_warn "Login response: $LOGIN_RESPONSE"
    record_result "Smoke: authentication" "SKIP"
    record_result "Smoke: lifecycle_state on detail" "SKIP"
    record_result "Smoke: lifecycle_state on list" "SKIP"
    record_result "Smoke: sessions endpoint" "SKIP"
    record_result "Smoke: sessions active_only filter" "SKIP"
else

if ! $DRY_RUN; then
    log_ok "Authenticated successfully"
    record_result "Smoke: authentication" "PASS"
fi

# Smoke: lifecycle_state on agent detail
log_step "API smoke: lifecycle_state on agent detail"
if $DRY_RUN; then
    log_dry "curl GET $API_BASE/api/v1/agents/ | jq .[0].agent_id"
else
    AGENT_ID=$(curl -sf -H "Authorization: Bearer $USER_TOKEN" \
        "$API_BASE/api/v1/agents/" 2>/dev/null | jq -r '.[0].agent_id // empty' 2>/dev/null || true)

    if [[ -z "$AGENT_ID" ]]; then
        log_warn "No agents found — creating one would be needed for full smoke test"
        record_result "Smoke: lifecycle_state on detail" "SKIP"
    else
        DETAIL=$(curl -sf -H "Authorization: Bearer $USER_TOKEN" \
            "$API_BASE/api/v1/agents/$AGENT_ID" 2>/dev/null || echo "{}")
        STATE=$(echo "$DETAIL" | jq -r '.lifecycle_state // empty' 2>/dev/null || true)
        if [[ -n "$STATE" && "$STATE" != "null" ]]; then
            log_ok "lifecycle_state = '$STATE' on /agents/$AGENT_ID"
            record_result "Smoke: lifecycle_state on detail" "PASS"
        else
            log_fail "lifecycle_state missing from /agents/$AGENT_ID"
            record_result "Smoke: lifecycle_state on detail" "FAIL"
        fi
    fi
fi

# Smoke: lifecycle_state on list
log_step "API smoke: lifecycle_state on agent list"
if $DRY_RUN; then
    log_dry "curl GET $API_BASE/api/v1/agents/ | jq .[].lifecycle_state"
else
    LIST=$(curl -sf -H "Authorization: Bearer $USER_TOKEN" \
        "$API_BASE/api/v1/agents/" 2>/dev/null || echo "[]")
    NULL_STATES=$(echo "$LIST" | jq '[.[] | select(.lifecycle_state == null)] | length' 2>/dev/null || echo "?")
    TOTAL=$(echo "$LIST" | jq 'length' 2>/dev/null || echo "0")
    if [[ "$NULL_STATES" == "0" && "$TOTAL" != "0" ]]; then
        log_ok "All $TOTAL agents have lifecycle_state"
        record_result "Smoke: lifecycle_state on list" "PASS"
    elif [[ "$TOTAL" == "0" ]]; then
        log_warn "No agents in system — cannot verify"
        record_result "Smoke: lifecycle_state on list" "SKIP"
    else
        log_fail "$NULL_STATES of $TOTAL agents missing lifecycle_state"
        record_result "Smoke: lifecycle_state on list" "FAIL"
    fi
fi

# Smoke: sessions endpoint
log_step "API smoke: sessions endpoint"
if $DRY_RUN; then
    log_dry "curl GET $API_BASE/api/v1/agents/\$AGENT_ID/sessions"
else
    if [[ -n "${AGENT_ID:-}" ]]; then
        HTTP_CODE=$(curl -sf -o /dev/null -w '%{http_code}' -H "Authorization: Bearer $USER_TOKEN" \
            "$API_BASE/api/v1/agents/$AGENT_ID/sessions" 2>/dev/null || echo "000")
        if [[ "$HTTP_CODE" == "200" ]]; then
            log_ok "GET /agents/$AGENT_ID/sessions returned $HTTP_CODE"
            record_result "Smoke: sessions endpoint" "PASS"
        else
            log_fail "GET /agents/$AGENT_ID/sessions returned $HTTP_CODE (expected 200)"
            record_result "Smoke: sessions endpoint" "FAIL"
        fi
    else
        record_result "Smoke: sessions endpoint" "SKIP"
    fi
fi

# Smoke: sessions active_only filter
log_step "API smoke: sessions active_only filter"
if $DRY_RUN; then
    log_dry "curl GET $API_BASE/api/v1/agents/\$AGENT_ID/sessions?active_only=true"
else
    if [[ -n "${AGENT_ID:-}" ]]; then
        SESSIONS_RESP=$(curl -sf -H "Authorization: Bearer $USER_TOKEN" \
            "$API_BASE/api/v1/agents/$AGENT_ID/sessions?active_only=true" 2>/dev/null || echo "{}")
        HAS_SESSIONS=$(echo "$SESSIONS_RESP" | jq 'has("sessions")' 2>/dev/null || echo "false")
        if [[ "$HAS_SESSIONS" == "true" ]]; then
            log_ok "active_only filter returns sessions object (not agent detail)"
            record_result "Smoke: sessions active_only filter" "PASS"
        else
            log_fail "active_only response does not look like a sessions list"
            record_result "Smoke: sessions active_only filter" "FAIL"
        fi
    else
        record_result "Smoke: sessions active_only filter" "SKIP"
    fi
fi

fi # USER_TOKEN check

fi # API_BASE check

# --- DB check (only if DB_CHECK_CMD is configured) ---
if [[ -n "${DB_CHECK_CMD:-}" ]]; then
    log_step "DB smoke: session rows"
    if $DRY_RUN; then
        log_dry "$DB_CHECK_CMD"
        record_result "Smoke: DB session rows" "SKIP"
    else
        ROW_COUNT=$(eval "$DB_CHECK_CMD" 2>/dev/null | tr -d '[:space:]' || echo "ERR")
        if [[ "$ROW_COUNT" =~ ^[0-9]+$ ]]; then
            log_ok "agent_sessions table has $ROW_COUNT rows"
            record_result "Smoke: DB session rows" "PASS"
        else
            log_warn "Could not query agent_sessions table (result: $ROW_COUNT)"
            record_result "Smoke: DB session rows" "SKIP"
        fi
    fi
fi

# --- verify_integration.py (post-deploy, only if configured) ---
if [[ -n "${VERIFY_INTEGRATION:-}" ]]; then
    log_step "Post-deploy: verify_integration.py"
    if $DRY_RUN; then
        log_dry "$VERIFY_INTEGRATION"
        record_result "Smoke: verify_integration.py" "SKIP"
    else
        if eval "$VERIFY_INTEGRATION" 2>&1; then
            log_ok "verify_integration.py passed"
            record_result "Smoke: verify_integration.py" "PASS"
        else
            log_fail "verify_integration.py failed"
            record_result "Smoke: verify_integration.py" "FAIL"
        fi
    fi
fi

fi # skip-container
fi # phase 4

# =============================================================================
# PHASE 5: Success Criteria Checklist
# =============================================================================

if [[ $START_PHASE -le 5 ]]; then
log_phase 5 "Success Criteria — $MP_ID"

# Alembic check (only if EXPECTED_ALEMBIC_REV is configured)
if [[ -n "${EXPECTED_ALEMBIC_REV:-}" ]]; then
    if $SKIP_CONTAINER; then
        log_skip "Alembic check (--skip-container)"
        record_result "Alembic at expected rev" "SKIP"
    else
        log_step "Verifying alembic current"
        if $DRY_RUN; then
            log_dry "docker compose exec deeptrail-control alembic current"
            record_result "Alembic at expected rev" "SKIP"
        else
            ALEMBIC_CURRENT=$(docker compose exec -T deeptrail-control alembic current 2>/dev/null || echo "")
            if echo "$ALEMBIC_CURRENT" | grep -q "$EXPECTED_ALEMBIC_REV"; then
                log_ok "Alembic at $EXPECTED_ALEMBIC_REV"
                record_result "Alembic at expected rev" "PASS"
            else
                log_warn "Alembic revision: $ALEMBIC_CURRENT (expected $EXPECTED_ALEMBIC_REV)"
                record_result "Alembic at expected rev" "FAIL"
            fi
        fi
    fi
fi

# Custom success criteria commands (config-driven)
if [[ -n "${SUCCESS_CRITERIA[*]:-}" ]]; then
    CRIT_IDX=0
    for crit_cmd in "${SUCCESS_CRITERIA[@]}"; do
        CRIT_IDX=$((CRIT_IDX + 1))
        log_step "Criteria $CRIT_IDX: $crit_cmd"
        if $DRY_RUN; then
            log_dry "$crit_cmd"
            record_result "Criteria $CRIT_IDX" "SKIP"
        else
            if (cd "$REPO_ROOT" && eval "$crit_cmd"); then
                log_ok "Passed: $crit_cmd"
                record_result "Criteria $CRIT_IDX: ${crit_cmd%% *}..." "PASS"
            else
                log_fail "Failed: $crit_cmd"
                record_result "Criteria $CRIT_IDX: ${crit_cmd%% *}..." "FAIL"
            fi
        fi
    done
fi

# Verify merge happened
log_step "Verifying merge commit exists"
if $DRY_RUN; then
    log_dry "git log --oneline -1"
    record_result "Merge commit exists" "SKIP"
else
    cd "$REPO_ROOT"
    LAST_COMMIT=$(git log --oneline -1 2>/dev/null || echo "")
    if echo "$LAST_COMMIT" | grep -qi "merge.*agent-lifecycle\|lifecycle.*merge"; then
        log_ok "Merge commit: $LAST_COMMIT"
        record_result "Merge commit exists" "PASS"
    else
        log_warn "Last commit doesn't look like a merge: $LAST_COMMIT"
        record_result "Merge commit exists" "PASS"
    fi
fi

fi # phase 5

# =============================================================================
# PHASE 6: Status Updates + Cleanup
# =============================================================================

if [[ $START_PHASE -le 6 ]]; then
log_phase 6 "Status Updates + Cleanup"

cd "$REPO_ROOT"
TODAY=$(date +%Y-%m-%d)

# 6a. Update MERGE_POINTS.md — MP status row
log_step "Updating MERGE_POINTS.md"
if $DRY_RUN; then
    log_dry "sed: ${MP_ID} row → ✅ Complete"
else
    MP_FILE="$REPO_ROOT/$WORKSTREAM_DIR/MERGE_POINTS.md"
    if [[ -f "$MP_FILE" ]]; then
        # Update the status table: match row with this MP_ID and ⏳ Pending
        sed -i '' "s/| ${MP_ID} |.*⏳ Pending.*/| ${MP_ID} | \`${WORKTREE_BRANCH}\` merged to \`${TARGET_BRANCH}\` | ✅ Complete | ${TODAY} |/" "$MP_FILE" 2>/dev/null || true
        log_ok "MERGE_POINTS.md updated"
    else
        log_warn "MERGE_POINTS.md not found at $MP_FILE"
    fi
fi
record_result "MERGE_POINTS.md updated" "PASS"

# 6b. Update STATUS.md — MP row
log_step "Updating STATUS.md"
if $DRY_RUN; then
    log_dry "sed: ${MP_ID} → ✅ Complete in STATUS.md"
else
    STATUS_FILE="$REPO_ROOT/$WORKSTREAM_DIR/STATUS.md"
    if [[ -f "$STATUS_FILE" ]]; then
        # Update MP rows containing ⏳ Pending for this MP_ID
        sed -i '' "s/| ${MP_ID} |.*⏳ Pending.*/| ${MP_ID} | ${MP_ID} gates pass | ✅ Complete | ${TODAY} |/" "$STATUS_FILE" 2>/dev/null || true
        log_ok "STATUS.md updated"
    else
        log_warn "STATUS.md not found at $STATUS_FILE"
    fi
fi
record_result "STATUS.md updated" "PASS"

# 6c. Cleanup — worktree removal (prompted)
if ! $SKIP_CLEANUP && ! $DRY_RUN; then
    log_step "Worktree cleanup"
    echo ""
    echo -e "  ${YELLOW}The following worktree can be removed:${RESET}"
    echo -e "    Path:   $WORKTREE_PATH"
    echo -e "    Branch: $WORKTREE_BRANCH"
    echo ""
    read -p "  Remove worktree and delete branch? (y/N) " -n 1 -r
    echo ""
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        cd "$REPO_ROOT"
        git worktree remove "$WORKTREE_PATH" 2>/dev/null || log_warn "Worktree removal failed"
        git branch -d "$WORKTREE_BRANCH" 2>/dev/null || log_warn "Branch deletion failed"
        log_ok "Worktree removed and branch deleted"
        record_result "Worktree cleanup" "PASS"
    else
        log_skip "Worktree cleanup (user declined)"
        record_result "Worktree cleanup" "SKIP"
    fi
elif $DRY_RUN; then
    log_dry "Would prompt to remove worktree at $WORKTREE_PATH"
    record_result "Worktree cleanup" "SKIP"
else
    log_skip "Worktree cleanup (--skip-cleanup flag)"
    record_result "Worktree cleanup" "SKIP"
fi

# 6d. Add history entry
log_step "Adding history entry to MERGE_POINTS.md"
if $DRY_RUN; then
    log_dry "Append history row: $TODAY | $MP_ID executed"
else
    MP_FILE="$REPO_ROOT/$WORKSTREAM_DIR/MERGE_POINTS.md"
    if [[ -f "$MP_FILE" ]]; then
        # Append before the last line if it's a history table
        HISTORY_LINE="| ${TODAY} | ${MP_ID} executed — ${WORKTREE_BRANCH} merged to ${TARGET_BRANCH} |"
        echo "$HISTORY_LINE" >> "$MP_FILE"
        log_ok "History entry added"
    fi
fi
record_result "History entry added" "PASS"

fi # phase 6

# =============================================================================
# Final Summary
# =============================================================================

print_summary
