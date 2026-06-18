#!/usr/bin/env bash
# session-context.sh — SessionStart(startup): inject git context at session start
# Provides branch, status, recent commits, and active PRs so the agent
# has immediate situational awareness.
set -euo pipefail

echo "## Session Context"
echo ""

BRANCH=$(git branch --show-current 2>/dev/null || echo "unknown")
echo "**Branch:** \`$BRANCH\`"

DIRTY_COUNT=$(git status --short 2>/dev/null | wc -l | tr -d ' ')
echo "**Working tree:** $DIRTY_COUNT changed files"

echo ""
echo "**Recent commits (last 5):**"
git log --oneline -5 2>/dev/null || echo "(no commits)"

echo ""
OPEN_PRS=$(gh pr list --state open --limit 3 --json number,title 2>/dev/null || echo "[]")
if [ "$OPEN_PRS" != "[]" ] && [ -n "$OPEN_PRS" ]; then
    echo "**Open PRs:**"
    echo "$OPEN_PRS" | python3 -c "
import json, sys
prs = json.load(sys.stdin)
for pr in prs:
    print(f\"  - #{pr['number']}: {pr['title']}\")
" 2>/dev/null || true
fi

exit 0
