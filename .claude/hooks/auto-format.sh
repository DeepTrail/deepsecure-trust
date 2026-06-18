#!/usr/bin/env bash
# auto-format.sh — PostToolUse(Edit|Write): lint Python files after edit
# Claude Code sends JSON to stdin with tool_name, file_path, etc.
set -euo pipefail

INPUT=$(cat)

FILE_PATH=$(echo "$INPUT" | python3 -c "import sys,json; print(json.load(sys.stdin).get('tool_input',{}).get('file_path',''))" 2>/dev/null || echo "")

if [ -z "$FILE_PATH" ]; then
    exit 0
fi

case "$FILE_PATH" in
    *.py) ;;
    *) exit 0 ;;
esac

case "$FILE_PATH" in
    */migrations/versions/*|*/__pycache__/*) exit 0 ;;
esac

if command -v ruff &>/dev/null; then
    LINT_OUTPUT=$(ruff check "$FILE_PATH" 2>&1 || true)
    if [ -n "$LINT_OUTPUT" ]; then
        echo "[hook:auto-format] Lint issues in $FILE_PATH:" >&2
        echo "$LINT_OUTPUT" >&2
    fi
fi

exit 0
