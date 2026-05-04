#!/usr/bin/env bash
# on-task-stop.sh — Notification + quality summary on task completion
#
# Runs when a Cursor agent task completes (stop event).
# Provides a macOS notification and logs a summary.
#
# Cursor sends JSON to stdin: { status: "completed"|"aborted"|"error", ... }

set -euo pipefail

INPUT=$(cat)

STATUS=$(echo "$INPUT" | python3 -c "import sys,json; print(json.load(sys.stdin).get('status','unknown'))" 2>/dev/null || echo "unknown")
CONVERSATION_ID=$(echo "$INPUT" | python3 -c "import sys,json; print(json.load(sys.stdin).get('conversation_id','')[:8])" 2>/dev/null || echo "")

TIMESTAMP=$(date '+%Y-%m-%d %H:%M:%S')

# Log to a session file for tracking
LOG_DIR="${HOME}/.cursor/logs/deepsecure"
mkdir -p "$LOG_DIR"
LOG_FILE="$LOG_DIR/task-completions.log"

case "$STATUS" in
  completed)
    TITLE="Task Complete"
    MSG="Agent task finished successfully"
    ICON="✅"
    ;;
  aborted)
    TITLE="Task Aborted"
    MSG="Agent task was cancelled"
    ICON="⚠️"
    ;;
  error)
    TITLE="Task Error"
    MSG="Agent task ended with an error"
    ICON="❌"
    ;;
  *)
    TITLE="Task Ended"
    MSG="Agent task ended (status: $STATUS)"
    ICON="ℹ️"
    ;;
esac

echo "$TIMESTAMP | $ICON $STATUS | session:$CONVERSATION_ID" >> "$LOG_FILE"

# macOS notification (non-blocking)
if command -v osascript &>/dev/null; then
  osascript -e "display notification \"$MSG\" with title \"DeepSecure\" subtitle \"$TITLE\" sound name \"Glass\"" 2>/dev/null &
fi

# Quick lint summary of recently modified Python files (last 5 minutes)
if [ "$STATUS" = "completed" ] && command -v ruff &>/dev/null; then
  RECENT_PY=$(find . -name "*.py" -newer /tmp/.cursor-task-marker -not -path '*/node_modules/*' -not -path '*/__pycache__/*' -not -path '*/migrations/*' 2>/dev/null | head -20)
  if [ -n "$RECENT_PY" ]; then
    LINT_COUNT=$(echo "$RECENT_PY" | xargs ruff check 2>/dev/null | wc -l || echo "0")
    LINT_COUNT=$(echo "$LINT_COUNT" | tr -d ' ')
    if [ "$LINT_COUNT" -gt 0 ] 2>/dev/null; then
      echo "$TIMESTAMP | ⚠️ $LINT_COUNT lint issues in recently modified files" >> "$LOG_FILE"
    fi
  fi
fi

# Touch marker file for next task timing
touch /tmp/.cursor-task-marker 2>/dev/null || true

exit 0
