#!/usr/bin/env bash
# security-gate.sh — PreToolUse(Bash): block dangerous command patterns
# Claude Code sends JSON to stdin with tool_name, tool_input, etc.
# Return JSON: {"decision": "allow"} or {"decision": "block", "reason": "..."}
set -euo pipefail

INPUT=$(cat)

COMMAND=$(echo "$INPUT" | python3 -c "import sys,json; print(json.load(sys.stdin).get('tool_input',{}).get('command',''))" 2>/dev/null || echo "")

if [ -z "$COMMAND" ]; then
    echo '{"decision": "allow"}'
    exit 0
fi

# Block Python patterns that bypass file-level denylists
if echo "$COMMAND" | grep -qE 'shutil\.rmtree|os\.remove\(|subprocess\.run.*rm|eval\(|exec\(' 2>/dev/null; then
    cat <<EOF
{"decision": "block", "reason": "Blocked: command contains dangerous Python pattern (shutil.rmtree, os.remove, eval, exec)"}
EOF
    exit 0
fi

# Block pipe-to-bash patterns
if echo "$COMMAND" | grep -qE 'curl.*\|\s*(ba)?sh|wget.*\|\s*(ba)?sh' 2>/dev/null; then
    cat <<EOF
{"decision": "block", "reason": "Blocked: pipe-to-bash pattern detected. Download and inspect scripts before executing."}
EOF
    exit 0
fi

# Block force-push to protected branches
if echo "$COMMAND" | grep -qE 'git\s+push\s+.*--force.*\s+(main|dev|master)' 2>/dev/null; then
    cat <<EOF
{"decision": "block", "reason": "Blocked: force-push to protected branch (main/dev/master)."}
EOF
    exit 0
fi

# Block rm -rf on dangerous paths
if echo "$COMMAND" | grep -qE 'rm\s+-rf\s+(/|~|\$HOME|\.git\b)' 2>/dev/null; then
    cat <<EOF
{"decision": "block", "reason": "Blocked: dangerous rm -rf on protected path (/, ~, .git)."}
EOF
    exit 0
fi

echo '{"decision": "allow"}'
exit 0
