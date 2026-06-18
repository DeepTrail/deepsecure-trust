#!/usr/bin/env bash
# hermes-invoker.sh — Phase 2: Trigger Ralph loop and review output
# Usage: hermes-invoker.sh <workstream-name> [--dry-run]
#
# Invoker role: starts Ralph loop iterations, reviews JSON progress after
# each run, decides whether to continue, escalate, or stop.
# No direct code authority — delegates all execution to Claude Code via Ralph.
set -euo pipefail

WORKSTREAM=${1:?"Usage: hermes-invoker.sh <workstream-name> [--dry-run]"}
DRY_RUN=false
[ "${2:-}" = "--dry-run" ] && DRY_RUN=true

CONFIG_FILE=".hermes/config.yaml"
RALPH_SCRIPT="scripts/ralph.sh"
PROGRESS_FILE="docs/workstreams/$WORKSTREAM/ralph_progress.json"
LOG_FILE=".hermes/invoker.log"

log() {
    local msg="[$(date -u +%Y-%m-%dT%H:%M:%SZ)] [invoker] $1"
    echo "$msg" | tee -a "$LOG_FILE"
}

notify() {
    scripts/notify.sh "$1" "$2" "${3:-info}" 2>/dev/null || true
}

if [ ! -f "$CONFIG_FILE" ]; then
    echo "❌ Config not found: $CONFIG_FILE"
    echo "Run: scripts/hermes-setup.sh"
    exit 1
fi

if [ ! -f "$RALPH_SCRIPT" ]; then
    echo "❌ Ralph script not found: $RALPH_SCRIPT"
    exit 1
fi

get_progress() {
    if [ ! -f "$PROGRESS_FILE" ]; then
        echo '{"tasks":[],"metadata":{}}'
        return
    fi
    cat "$PROGRESS_FILE"
}

analyze_progress() {
    local progress="$1"

    python3 -c "
import json, sys

try:
    data = json.loads('''$progress''')
except json.JSONDecodeError:
    print('DECISION:escalate:Cannot parse progress JSON')
    sys.exit(0)

meta = data.get('metadata', {})
tasks = data.get('tasks', [])
completed = sum(1 for t in tasks if t.get('passes') or t.get('status') == 'completed')
total = len(tasks)
cb = meta.get('circuit_breaker', 'CLOSED')
iters = meta.get('total_iterations', 0)

# Decision logic
if cb == 'OPEN':
    print(f'DECISION:escalate:Circuit breaker OPEN after {iters} iterations ({completed}/{total} tasks)')
elif total > 0 and completed == total:
    print(f'DECISION:complete:All {total} tasks completed in {iters} iterations')
elif iters >= 10 and completed < total:
    print(f'DECISION:escalate:Max iterations ({iters}) reached with {total - completed} tasks remaining')
elif completed > 0:
    print(f'DECISION:continue:Progress ({completed}/{total} tasks) after {iters} iterations')
else:
    print(f'DECISION:continue:No tasks completed yet after {iters} iterations')
" 2>/dev/null || echo "DECISION:escalate:Analysis failed"
}

log "=== Invoker starting: $WORKSTREAM ==="
notify "Hermes Invoker" "Starting Ralph for $WORKSTREAM" info

# Capture pre-run state
PRE_PROGRESS=$(get_progress)
PRE_COMPLETED=$(echo "$PRE_PROGRESS" | python3 -c "
import json, sys
try:
    data = json.load(sys.stdin)
    print(sum(1 for t in data.get('tasks', []) if t.get('passes') or t.get('status') == 'completed'))
except:
    print(0)
" 2>/dev/null || echo "0")

log "Pre-run state: $PRE_COMPLETED tasks completed"

# Execute Ralph
if [ "$DRY_RUN" = true ]; then
    log "[DRY RUN] Would execute: $RALPH_SCRIPT $WORKSTREAM"
    echo "DRY RUN — skipping Ralph execution"
else
    log "Executing: $RALPH_SCRIPT $WORKSTREAM"
    "$RALPH_SCRIPT" "$WORKSTREAM" 2>&1 | tee -a "$LOG_FILE" || true
fi

# Analyze post-run progress
POST_PROGRESS=$(get_progress)
DECISION_LINE=$(analyze_progress "$POST_PROGRESS")
DECISION=$(echo "$DECISION_LINE" | cut -d: -f2)
REASON=$(echo "$DECISION_LINE" | cut -d: -f3-)

log "Decision: $DECISION — $REASON"

POST_COMPLETED=$(echo "$POST_PROGRESS" | python3 -c "
import json, sys
try:
    data = json.load(sys.stdin)
    print(sum(1 for t in data.get('tasks', []) if t.get('passes') or t.get('status') == 'completed'))
except:
    print(0)
" 2>/dev/null || echo "0")

DELTA=$((POST_COMPLETED - PRE_COMPLETED))
log "Progress delta: +$DELTA tasks ($PRE_COMPLETED → $POST_COMPLETED)"

# Store learning in observer memory
python3 -c "
import sqlite3, os
db_path = '.hermes/memory.db'
if not os.path.exists(db_path):
    import sys; sys.exit(0)
conn = sqlite3.connect(db_path)
conn.execute('''CREATE TABLE IF NOT EXISTS learnings (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id TEXT NOT NULL,
    content TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
)''')
conn.execute('INSERT INTO learnings (session_id, content) VALUES (?, ?)',
    ('invoker-$(date +%Y%m%d_%H%M%S)', 'Workstream: $WORKSTREAM, Decision: $DECISION, Delta: +$DELTA tasks, Reason: $REASON'))
conn.commit()
conn.close()
" 2>/dev/null || true

# Act on decision
case "$DECISION" in
    complete)
        log "✅ Workstream complete"
        notify "Hermes Invoker" "Workstream $WORKSTREAM complete ($REASON)" success
        echo ""
        echo "✅ $REASON"
        exit 0
        ;;
    continue)
        log "↻ Continuing (tasks progressing)"
        notify "Hermes Invoker" "$WORKSTREAM: $REASON — will continue next cycle" info
        echo ""
        echo "↻ $REASON"
        exit 0
        ;;
    escalate)
        log "⚠️  Escalating to developer"
        notify "Hermes Invoker" "ESCALATION: $WORKSTREAM — $REASON" warning
        echo ""
        echo "⚠️  ESCALATION: $REASON"
        echo "Manual intervention needed for: $WORKSTREAM"
        exit 2
        ;;
    *)
        log "❓ Unknown decision: $DECISION"
        exit 1
        ;;
esac
