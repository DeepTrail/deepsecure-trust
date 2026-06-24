#!/usr/bin/env bash
# permission-notify.sh — Notification(permission_prompt): alert developer of permission blocks
# During AFK runs, permission prompts block execution. This hook sends a
# notification so the developer can approve/deny remotely.
set -euo pipefail

INPUT=$(cat)

TOOL=$(echo "$INPUT" | python3 -c "import sys,json; print(json.load(sys.stdin).get('tool_name','unknown'))" 2>/dev/null || echo "unknown")

if [ -x "scripts/notify.sh" ]; then
    scripts/notify.sh "Permission Needed" "AFK blocked on: $TOOL — approve via Claude App or terminal" warning 2>/dev/null || true
fi

exit 0
