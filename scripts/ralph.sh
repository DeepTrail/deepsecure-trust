#!/usr/bin/env bash
# ralph.sh — Core AFK engine: fresh-context iteration loop
# Usage: ralph.sh <workstream-name> [max-iterations]
# Wraps claude --print in a loop with: dirty-tree guard, sentinel detection,
# JSON progress tracking, circuit breaker, and cost ceiling.
set -euo pipefail

WORKSTREAM=${1:?"Usage: ralph.sh <workstream-name> [max-iterations]"}
MAX_ITER=${2:-10}
PROMPT_FILE="docs/workstreams/$WORKSTREAM/ralph-prompt.md"
PROGRESS="docs/workstreams/$WORKSTREAM/ralph_progress.json"
BUDGET="${RALPH_MAX_BUDGET:-5.00}"
CB_THRESHOLD=3
CB_COUNTER=0

if [ ! -f "$PROMPT_FILE" ]; then
    echo "ERROR: Prompt file not found: $PROMPT_FILE" >&2
    exit 1
fi

# Initialize progress if it doesn't exist
if [ ! -f "$PROGRESS" ]; then
    cp .afk/ralph_progress_template.json "$PROGRESS"
    TIMESTAMP=$(date -u +%Y-%m-%dT%H:%M:%SZ)
    python3 -c "
import json, sys
with open('$PROGRESS') as f:
    d = json.load(f)
d['workstream'] = '$WORKSTREAM'
d['created'] = '$TIMESTAMP'
d['metadata']['max_iterations'] = $MAX_ITER
d['metadata']['max_budget_usd'] = float('$BUDGET')
with open('$PROGRESS', 'w') as f:
    json.dump(d, f, indent=4)
" 2>/dev/null || true
fi

PROMPT_CONTENT=$(cat "$PROMPT_FILE")

# Inject extracted reference docs into system prompt for full AFK coverage.
# CLAUDE.md is auto-loaded but these docs are not — without injection, the AFK
# agent would need to proactively Read them, which is unreliable.
REF_DOCS=""
for doc in docs/DEVELOPMENT_COMMANDS.md docs/ARCHITECTURE.md docs/TESTING_GUIDE.md CODE_STANDARDS.md; do
    [ -f "$doc" ] && REF_DOCS="${REF_DOCS}
$(cat "$doc")
"
done

if [ -n "$REF_DOCS" ]; then
    PROMPT_CONTENT="${PROMPT_CONTENT}

---
# Reference Documentation (auto-injected for AFK context)
${REF_DOCS}"
fi

echo "Ralph loop starting: $WORKSTREAM (max $MAX_ITER iterations, \$$BUDGET budget/iter)"
scripts/notify.sh "AFK Started" "Ralph loop: $WORKSTREAM ($MAX_ITER iterations)" info 2>/dev/null || true

for ((i=1; i<=MAX_ITER; i++)); do
    echo ""
    echo "═══ Iteration $i/$MAX_ITER ═══"
    ITER_START=$(date +%s)

    # Dirty-tree guard
    if [ -n "$(git status --short)" ]; then
        git stash push -m "ralph-guard: iteration $i $(date +%Y%m%d_%H%M%S)" 2>/dev/null || true
    fi

    # Capture progress before iteration
    PREV_DONE=$(jq '[.tasks[] | select(.passes==true)] | length' "$PROGRESS" 2>/dev/null || echo 0)

    # Execute one iteration with fresh context
    OUTPUT=$(claude --print \
        --output-format json \
        --system-prompt "$PROMPT_CONTENT" \
        --max-budget-usd "$BUDGET" \
        --permission-mode auto \
        < /dev/null 2>&1 | tee /dev/stderr) || true

    ITER_END=$(date +%s)
    ITER_DURATION=$((ITER_END - ITER_START))

    # Sentinel detection
    if echo "$OUTPUT" | grep -q "<promise>COMPLETE</promise>"; then
        echo ""
        echo "✅ Sentinel detected — workstream complete"
        python3 -c "
import json
with open('$PROGRESS') as f:
    d = json.load(f)
d['metadata']['total_iterations'] = $i
d['metadata']['last_iteration_at'] = '$(date -u +%Y-%m-%dT%H:%M:%SZ)'
with open('$PROGRESS', 'w') as f:
    json.dump(d, f, indent=4)
" 2>/dev/null || true
        scripts/notify.sh "AFK Complete" "Workstream $WORKSTREAM finished after $i iterations" success 2>/dev/null || true
        exit 0
    fi

    # Cost tracking
    COST=$(echo "$OUTPUT" | python3 -c "
import json, sys
try:
    data = json.load(sys.stdin)
    print(data.get('usage', {}).get('cost', 'unknown'))
except:
    print('unknown')
" 2>/dev/null || echo "unknown")
    echo "Iteration $i: cost=\$$COST duration=${ITER_DURATION}s at $(date -u +%Y-%m-%dT%H:%M:%SZ)" >> .afk/cost-log.txt

    # Update progress metadata
    python3 -c "
import json
with open('$PROGRESS') as f:
    d = json.load(f)
d['metadata']['total_iterations'] = $i
d['metadata']['last_iteration_at'] = '$(date -u +%Y-%m-%dT%H:%M:%SZ)'
with open('$PROGRESS', 'w') as f:
    json.dump(d, f, indent=4)
" 2>/dev/null || true

    # Circuit breaker — check if progress was made
    CURR_DONE=$(jq '[.tasks[] | select(.passes==true)] | length' "$PROGRESS" 2>/dev/null || echo 0)
    if [ "$CURR_DONE" -le "$PREV_DONE" ]; then
        CB_COUNTER=$((CB_COUNTER + 1))
        echo "⚠️  No progress (${CB_COUNTER}/${CB_THRESHOLD} toward circuit breaker)"
        if [ "$CB_COUNTER" -ge "$CB_THRESHOLD" ]; then
            python3 -c "
import json
with open('$PROGRESS') as f:
    d = json.load(f)
d['metadata']['circuit_breaker'] = 'OPEN'
with open('$PROGRESS', 'w') as f:
    json.dump(d, f, indent=4)
" 2>/dev/null || true
            scripts/notify.sh "AFK Stopped" "Circuit breaker OPEN for $WORKSTREAM after $i iterations" warning 2>/dev/null || true
            echo "❌ Circuit breaker OPEN — stopping"
            exit 2
        fi
    else
        CB_COUNTER=0
    fi
done

echo ""
echo "Max iterations ($MAX_ITER) reached"
scripts/notify.sh "AFK Paused" "Max iterations reached for $WORKSTREAM" info 2>/dev/null || true
exit 0
