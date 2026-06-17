#!/usr/bin/env bash
# P0 blocker: verify every Claude Code feature assumed by the AFK design doc.
# Exit 0 = all CRITICAL features pass. Exit 1 = at least one CRITICAL fails.
set -euo pipefail

PASS_COUNT=0
FAIL_COUNT=0
WARN_COUNT=0
CRITICAL_FAIL=0

pass() { echo "  PASS  $1"; PASS_COUNT=$((PASS_COUNT + 1)); }
fail() { echo "  FAIL  [CRITICAL] $1"; FAIL_COUNT=$((FAIL_COUNT + 1)); CRITICAL_FAIL=$((CRITICAL_FAIL + 1)); }
warn() { echo "  WARN  [OPTIONAL] $1"; WARN_COUNT=$((WARN_COUNT + 1)); }

echo "============================================"
echo "  AFK Feature Verification: Claude Code CLI"
echo "============================================"
echo ""

# ── 1. CLI availability ──────────────────────────────────────────────────────
echo "── CLI Basics ──"

if command -v claude &>/dev/null; then
    VERSION=$(claude --version 2>/dev/null || echo "unknown")
    pass "claude CLI found: $VERSION"
else
    fail "claude CLI not found in PATH"
    echo ""
    echo "RESULT: CRITICAL failure — Claude Code CLI is not installed."
    exit 1
fi

# ── 2. CRITICAL flags ────────────────────────────────────────────────────────
echo ""
echo "── CRITICAL Features (blocks AFK if missing) ──"

HELP_TEXT=$(claude --help 2>/dev/null || true)

if echo "$HELP_TEXT" | grep -qE '\-p,\s*--print|--print'; then
    pass "--print flag (non-interactive execution)"
else
    fail "--print flag missing — ralph.sh cannot execute"
fi

if echo "$HELP_TEXT" | grep -q '\-\-output-format'; then
    pass "--output-format flag (JSON output parsing)"
else
    fail "--output-format flag missing — ralph.sh cannot parse JSON output"
fi

if echo "$HELP_TEXT" | grep -q '\-\-max-budget-usd'; then
    pass "--max-budget-usd flag (cost ceiling per iteration)"
else
    fail "--max-budget-usd flag missing — no cost ceiling for AFK runs"
fi

if echo "$HELP_TEXT" | grep -q '\-\-system-prompt'; then
    pass "--system-prompt flag (custom system prompts)"
else
    fail "--system-prompt flag missing — cannot inject ralph-prompt context"
fi

if echo "$HELP_TEXT" | grep -qE '\-\-dangerously-skip-permissions|--allow-dangerously-skip-permissions'; then
    pass "--dangerously-skip-permissions flag (sandbox mode)"
else
    fail "--dangerously-skip-permissions flag missing — sandbox mode unavailable"
fi

if echo "$HELP_TEXT" | grep -qE '\-\-worktree|\-w,'; then
    pass "--worktree flag (agent isolation)"
else
    fail "--worktree flag missing — agent isolation unavailable"
fi

if echo "$HELP_TEXT" | grep -q '\-\-settings'; then
    pass "--settings flag (settings.local.json support)"
else
    fail "--settings flag missing — permission profile cannot be loaded"
fi

if echo "$HELP_TEXT" | grep -q '\-\-permission-mode'; then
    pass "--permission-mode flag (auto/ask/deny modes)"
else
    fail "--permission-mode flag missing — cannot set auto mode for AFK"
fi

# ── 3. Hooks support ─────────────────────────────────────────────────────────
echo ""
echo "── Hooks & Configuration ──"

if echo "$HELP_TEXT" | grep -qE '\-\-include-hook-events|hooks'; then
    pass "hooks support detected in CLI flags"
else
    warn "hooks not referenced in --help (may still work via hooks.json)"
fi

HOOKS_DIR="${HOME}/.claude"
if [ -d "$HOOKS_DIR" ] || [ -d ".claude" ]; then
    pass ".claude/ directory exists (hooks.json location)"
else
    warn ".claude/ directory not found — hooks may not be configured"
fi

if [ -f ".claude/settings.local.json" ]; then
    if python3 -c "import json; json.load(open('.claude/settings.local.json'))" 2>/dev/null; then
        pass "settings.local.json exists and is valid JSON"
    else
        fail "settings.local.json exists but is not valid JSON"
    fi
else
    warn "settings.local.json not found — will be created during WS-B8"
fi

# ── 4. Agent definitions ─────────────────────────────────────────────────────
echo ""
echo "── Agent & Skill Support ──"

if echo "$HELP_TEXT" | grep -q '\-\-agent'; then
    pass "--agent flag (agent definitions)"
else
    warn "--agent flag not found — agents may use directory convention only"
fi

if [ -d ".claude/agents" ]; then
    AGENT_COUNT=$(ls .claude/agents/*.md 2>/dev/null | wc -l | tr -d ' ')
    pass ".claude/agents/ directory exists ($AGENT_COUNT agents)"
else
    warn ".claude/agents/ not found — will be created during WS-D"
fi

if [ -d ".claude/commands" ]; then
    SKILL_COUNT=$(ls .claude/commands/*.md 2>/dev/null | wc -l | tr -d ' ')
    pass ".claude/commands/ directory exists ($SKILL_COUNT skills)"
else
    warn ".claude/commands/ not found — will be created during WS-C"
fi

# ── 5. OPTIONAL flags ────────────────────────────────────────────────────────
echo ""
echo "── OPTIONAL Features (workarounds available) ──"

if echo "$HELP_TEXT" | grep -q '\-\-prompt-file'; then
    pass "--prompt-file flag"
else
    warn "--prompt-file flag not found — ALTERNATIVE: pipe via stdin or use --system-prompt"
fi

if echo "$HELP_TEXT" | grep -qE '\-\-max-turns'; then
    pass "--max-turns flag"
else
    warn "--max-turns flag not found — ALTERNATIVE: use --max-budget-usd as ceiling"
fi

if echo "$HELP_TEXT" | grep -q '\-\-bare'; then
    pass "--bare flag (minimal mode)"
else
    warn "--bare flag not found — ALTERNATIVE: use explicit flag combinations"
fi

if echo "$HELP_TEXT" | grep -q '\-\-resume'; then
    pass "--resume flag (session resumption)"
else
    warn "--resume flag not found — ALTERNATIVE: use --continue"
fi

if echo "$HELP_TEXT" | grep -q '\-\-name'; then
    pass "--name flag (session naming)"
else
    warn "--name flag not found"
fi

# ── 6. Advanced features ─────────────────────────────────────────────────────
echo ""
echo "── Advanced Features ──"

if echo "$HELP_TEXT" | grep -q '\-\-model'; then
    pass "--model flag (model selection)"
else
    warn "--model flag not found"
fi

if echo "$HELP_TEXT" | grep -q '\-\-mcp-config'; then
    pass "--mcp-config flag (MCP server configuration)"
else
    warn "--mcp-config flag not found"
fi

if echo "$HELP_TEXT" | grep -q '\-\-remote-control'; then
    pass "--remote-control flag (Agent View / Remote Control)"
else
    warn "--remote-control flag not found — Agent View may not be available"
fi

if echo "$HELP_TEXT" | grep -q '\-\-continue'; then
    pass "--continue flag (session continuation)"
else
    warn "--continue flag not found"
fi

if echo "$HELP_TEXT" | grep -q '\-\-allowed-tools'; then
    pass "--allowed-tools flag (tool allowlist)"
else
    warn "--allowed-tools flag not found"
fi

if echo "$HELP_TEXT" | grep -q '\-\-disallowed-tools'; then
    pass "--disallowed-tools flag (tool denylist)"
else
    warn "--disallowed-tools flag not found"
fi

# ── 7. Design doc assumption reconciliation ──────────────────────────────────
echo ""
echo "── Design Doc Assumptions ──"

ALTERNATIVES=""

if ! echo "$HELP_TEXT" | grep -q '\-\-prompt-file'; then
    ALTERNATIVES+="  --prompt-file → Use: claude --print --system-prompt \"\$(cat ralph-prompt.md)\" < /dev/null\n"
fi

if ! echo "$HELP_TEXT" | grep -qE '\-\-max-turns'; then
    ALTERNATIVES+="  --max-turns   → Use: --max-budget-usd as the iteration ceiling\n"
fi

if [ -n "$ALTERNATIVES" ]; then
    echo "  Documented alternatives for missing optional features:"
    echo -e "$ALTERNATIVES"
fi

# ── Summary ───────────────────────────────────────────────────────────────────
echo ""
echo "============================================"
echo "  RESULTS"
echo "============================================"
echo "  PASS: $PASS_COUNT"
echo "  FAIL: $FAIL_COUNT (critical)"
echo "  WARN: $WARN_COUNT (optional, workarounds exist)"
echo "  Claude Code: $(claude --version 2>/dev/null || echo 'unknown')"
echo "============================================"

if [ "$CRITICAL_FAIL" -gt 0 ]; then
    echo ""
    echo "  ❌ CRITICAL FAILURES DETECTED"
    echo "  AFK workstream is BLOCKED until these are resolved."
    echo "  Check Claude Code version and update if needed."
    exit 1
else
    echo ""
    echo "  ✅ ALL CRITICAL FEATURES VERIFIED"
    echo "  AFK workstream may proceed."
    if [ "$WARN_COUNT" -gt 0 ]; then
        echo "  $WARN_COUNT optional features missing — alternatives documented above."
    fi
    exit 0
fi
