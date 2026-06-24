#!/usr/bin/env bash
# afk-once.sh — Single Ralph iteration for manual stepping
# Usage: afk-once.sh <workstream-name>
# Run this repeatedly before trusting the full ralph.sh loop.
set -euo pipefail

WORKSTREAM=${1:?"Usage: afk-once.sh <workstream-name>"}
PROMPT_FILE="docs/workstreams/$WORKSTREAM/ralph-prompt.md"
BUDGET="${RALPH_MAX_BUDGET:-5.00}"

if [ ! -f "$PROMPT_FILE" ]; then
    echo "ERROR: Prompt file not found: $PROMPT_FILE" >&2
    echo "Create it first, or check the workstream name." >&2
    exit 1
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

claude --print \
    --output-format json \
    --system-prompt "$PROMPT_CONTENT" \
    --max-budget-usd "$BUDGET" \
    --permission-mode auto \
    < /dev/null
