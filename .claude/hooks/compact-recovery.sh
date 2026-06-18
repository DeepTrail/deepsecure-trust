#!/usr/bin/env bash
# compact-recovery.sh — SessionStart(compact): re-inject critical rules after compaction
# Without this, the agent loses: token types, MCP protocol, async fixture rules,
# security boundaries, and merge point protocol.
set -euo pipefail

RECOVERY_FILE=".claude/compact-recovery.md"

if [ -f "$RECOVERY_FILE" ]; then
    cat "$RECOVERY_FILE"
else
    cat <<'RULES'
## Critical Rules (re-injected after compaction)

### Token Types
- User Token: `POST /api/v1/auth/login` → `.token` (NOT `.access_token`)
- Agent JWT: Ed25519 challenge-response → `.access_token`
- Internal API Token: From docker-compose.yml env var

### MCP Gateway Protocol
1. `initialize` FIRST (establishes session)
2. `tools/list` (optional)
3. `tools/call` (requires active session)

### Async Test Fixtures
Use `@pytest_asyncio.fixture`, NOT `@pytest.fixture` for async fixtures.

### Merge Point Protocol
Validation → Container Deployment → Container Tests → Success Criteria → Merge Actions
(Sequential pre-merge gate — never skip steps)

### Self-Verification
After every edit: ReadLints → fix errors → verify imports.
Before completion: re-read acceptance criteria → run tests → check regressions.
RULES
fi

exit 0
