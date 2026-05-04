#!/usr/bin/env bash
# after-file-edit.sh — Quality gate: lint-on-save for Python files
#
# Runs after Cursor edits a file. Checks if it's a Python file and
# runs ruff on it to catch lint errors immediately. This implements
# the "Micro Verification" tier from CLAUDE.md: catch errors at the
# point of creation, not during review 20 minutes later.
#
# Cursor sends JSON to stdin with: file_path, edits, conversation_id, etc.
# This hook is informational-only (afterFileEdit cannot block).

set -euo pipefail

INPUT=$(cat)

FILE_PATH=$(echo "$INPUT" | python3 -c "import sys,json; print(json.load(sys.stdin).get('file_path',''))" 2>/dev/null || echo "")

if [ -z "$FILE_PATH" ]; then
  exit 0
fi

# Only lint Python files
case "$FILE_PATH" in
  *.py)
    ;;
  *)
    exit 0
    ;;
esac

# Skip test fixture files and generated files
case "$FILE_PATH" in
  */migrations/versions/*)
    exit 0
    ;;
  */__pycache__/*)
    exit 0
    ;;
esac

# Run ruff check (non-blocking, just log)
if command -v ruff &>/dev/null; then
  LINT_OUTPUT=$(ruff check "$FILE_PATH" 2>&1 || true)
  if [ -n "$LINT_OUTPUT" ]; then
    echo "[hook:after-file-edit] Lint issues in $FILE_PATH:" >&2
    echo "$LINT_OUTPUT" >&2
  fi
fi

exit 0
