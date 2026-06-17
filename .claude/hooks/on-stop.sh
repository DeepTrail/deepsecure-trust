#!/usr/bin/env bash
# on-stop.sh — Stop event: notification + remaining task check
# Runs when Claude Code session ends. Checks for remaining tasks and
# outputs a continuation nudge if work is incomplete.
set -euo pipefail

INPUT=$(cat)

STATUS=$(echo "$INPUT" | python3 -c "import sys,json; print(json.load(sys.stdin).get('stop_hook_active','true'))" 2>/dev/null || echo "true")
TIMESTAMP=$(date '+%Y-%m-%d %H:%M:%S')

LOG_DIR="${HOME}/.claude/logs/deepsecure"
mkdir -p "$LOG_DIR"
LOG_FILE="$LOG_DIR/session-completions.log"

echo "$TIMESTAMP | Session ended" >> "$LOG_FILE"

if command -v osascript &>/dev/null; then
    osascript -e 'display notification "Session ended" with title "DeepSecure AFK" sound name "Glass"' 2>/dev/null &
fi

FEATURE_DIR=$(find docs/workstreams -maxdepth 1 -type d 2>/dev/null | tail -1)
if [ -n "$FEATURE_DIR" ] && [ -f "$FEATURE_DIR/STATUS.md" ]; then
    REMAINING=$(grep -c "Ready\|In Progress\|Blocked" "$FEATURE_DIR/STATUS.md" 2>/dev/null || echo "0")
    COMPLETED=$(grep -c "Complete" "$FEATURE_DIR/STATUS.md" 2>/dev/null || echo "0")
    if [ "$REMAINING" -gt 0 ] 2>/dev/null; then
        echo ""
        echo "📋 Remaining tasks: $REMAINING (completed: $COMPLETED)"
        echo "   Resume with: /run-batch <next-batch> <feature-name>"
    fi
fi

exit 0
