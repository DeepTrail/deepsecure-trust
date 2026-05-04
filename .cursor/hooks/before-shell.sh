#!/usr/bin/env bash
# before-shell.sh — Safety gate: block dangerous commands
#
# Runs before Cursor executes a shell command. Blocks dangerous
# operations that could cause data loss or security issues.
#
# Cursor sends JSON to stdin with: command, cwd, conversation_id, etc.
# Return JSON to stdout to allow/deny:
#   { "continue": true/false, "permission": "allow|deny", "userMessage": "...", "agentMessage": "..." }

set -euo pipefail

INPUT=$(cat)

COMMAND=$(echo "$INPUT" | python3 -c "import sys,json; print(json.load(sys.stdin).get('command',''))" 2>/dev/null || echo "")

if [ -z "$COMMAND" ]; then
  echo '{"continue": true, "permission": "allow"}'
  exit 0
fi

# ──────────────────────────────────────────────────
# BLOCK: Force-push to main/dev branches
# ──────────────────────────────────────────────────
if echo "$COMMAND" | grep -qE 'git\s+push\s+.*--force.*\s+(main|dev|master)' 2>/dev/null; then
  cat <<EOF
{
  "continue": false,
  "permission": "deny",
  "userMessage": "Blocked: force-push to protected branch (main/dev/master) is not allowed.",
  "agentMessage": "Force-pushing to main/dev/master is forbidden. Push to a feature branch instead."
}
EOF
  exit 0
fi

# ──────────────────────────────────────────────────
# BLOCK: rm -rf on dangerous paths
# ──────────────────────────────────────────────────
if echo "$COMMAND" | grep -qE 'rm\s+-rf\s+(/|~|\$HOME|\.git\b)' 2>/dev/null; then
  cat <<EOF
{
  "continue": false,
  "permission": "deny",
  "userMessage": "Blocked: dangerous rm -rf on a protected path.",
  "agentMessage": "Cannot rm -rf root, home, or .git directories. Be more specific about what to remove."
}
EOF
  exit 0
fi

# ──────────────────────────────────────────────────
# BLOCK: git commit --no-verify (skip hooks)
# ──────────────────────────────────────────────────
if echo "$COMMAND" | grep -qE 'git\s+commit\s+.*--no-verify' 2>/dev/null; then
  cat <<EOF
{
  "continue": false,
  "permission": "deny",
  "userMessage": "Blocked: --no-verify skips pre-commit hooks. Remove it and commit normally.",
  "agentMessage": "Do not use --no-verify. Pre-commit hooks exist for quality control. Commit without this flag."
}
EOF
  exit 0
fi

# ──────────────────────────────────────────────────
# BLOCK: git reset --hard on main/dev
# ──────────────────────────────────────────────────
if echo "$COMMAND" | grep -qE 'git\s+reset\s+--hard' 2>/dev/null; then
  BRANCH=$(git branch --show-current 2>/dev/null || echo "unknown")
  if [ "$BRANCH" = "main" ] || [ "$BRANCH" = "dev" ] || [ "$BRANCH" = "master" ]; then
    cat <<EOF
{
  "continue": false,
  "permission": "deny",
  "userMessage": "Blocked: git reset --hard on protected branch ($BRANCH).",
  "agentMessage": "Cannot hard reset on main/dev/master. Switch to a feature branch first."
}
EOF
    exit 0
  fi
fi

# ──────────────────────────────────────────────────
# WARN: pip install without version pinning (non-blocking)
# ──────────────────────────────────────────────────
if echo "$COMMAND" | grep -qE 'pip\s+install\s+(?!-r)(?!--requirement)' 2>/dev/null; then
  if ! echo "$COMMAND" | grep -qE '==' 2>/dev/null; then
    cat <<EOF
{
  "continue": true,
  "permission": "allow",
  "agentMessage": "Note: prefer pinned versions (package==version) for reproducibility."
}
EOF
    exit 0
  fi
fi

# ──────────────────────────────────────────────────
# DEFAULT: Allow everything else
# ──────────────────────────────────────────────────
echo '{"continue": true, "permission": "allow"}'
exit 0
