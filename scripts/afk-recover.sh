#!/usr/bin/env bash
# afk-recover.sh — Crash recovery: restore corrupt progress, stash dirty tree, restart Docker
# Usage: afk-recover.sh <workstream-name>
set -euo pipefail

WORKSTREAM=${1:?"Usage: afk-recover.sh <workstream-name>"}
PROGRESS="docs/workstreams/$WORKSTREAM/ralph_progress.json"
RECOVERED=0

echo "Recovering AFK state for: $WORKSTREAM"

# 1. Stash dirty working tree
if [ -n "$(git status --short)" ]; then
    echo "  Stashing dirty tree..."
    git stash push -m "afk-recover: $(date +%Y%m%d_%H%M%S)"
    RECOVERED=$((RECOVERED + 1))
fi

# 2. Validate/restore JSON progress
if [ -f "$PROGRESS" ]; then
    if ! jq empty "$PROGRESS" 2>/dev/null; then
        echo "  Corrupt JSON — restoring from last commit..."
        git checkout HEAD -- "$PROGRESS" 2>/dev/null || {
            echo "  No committed version — resetting from template"
            cp .afk/ralph_progress_template.json "$PROGRESS"
        }
        RECOVERED=$((RECOVERED + 1))
    else
        echo "  Progress JSON is valid"
    fi
else
    echo "  No progress file found — nothing to recover"
fi

# 3. Reset circuit breaker if OPEN
if [ -f "$PROGRESS" ] && jq -e '.metadata.circuit_breaker == "OPEN"' "$PROGRESS" >/dev/null 2>&1; then
    echo "  Resetting circuit breaker from OPEN → CLOSED"
    python3 -c "
import json
with open('$PROGRESS') as f:
    d = json.load(f)
d['metadata']['circuit_breaker'] = 'CLOSED'
d['metadata']['circuit_breaker_counter'] = 0
with open('$PROGRESS', 'w') as f:
    json.dump(d, f, indent=4)
" 2>/dev/null
    RECOVERED=$((RECOVERED + 1))
fi

# 4. Restart Docker if needed
if command -v docker &>/dev/null; then
    if ! docker compose ps --services --filter status=running 2>/dev/null | grep -q deeptrail; then
        echo "  Restarting Docker services..."
        docker compose up -d deeptrail-control deeptrail-gateway 2>/dev/null || true
        RECOVERED=$((RECOVERED + 1))
    else
        echo "  Docker services running"
    fi
fi

echo ""
if [ "$RECOVERED" -gt 0 ]; then
    echo "Recovery complete ($RECOVERED actions taken)."
else
    echo "Nothing to recover — all clean."
fi
echo "Resume with: ./scripts/ralph.sh $WORKSTREAM"
