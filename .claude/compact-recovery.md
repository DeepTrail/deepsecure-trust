## Critical Rules (re-injected after compaction)

### Token Types
- **User Token:** `POST /api/v1/auth/login` → `.token` (NOT `.access_token`)
- **Agent JWT:** Ed25519 challenge-response → `.access_token`
- **Internal API Token:** From `docker-compose.yml` env var, used with `X-User-ID` header

### MCP Gateway Protocol
1. `initialize` FIRST (establishes session)
2. `tools/list` (optional)
3. `tools/call` (requires active session — "Session not found" means you skipped step 1)

### Async Test Fixtures
Use `@pytest_asyncio.fixture`, NOT `@pytest.fixture` for async fixtures.

### Merge Point Protocol (Sequential Gate)
1. Batch Validation → 2. Container Deployment → 3. Container Tests → 4. Success Criteria → 5. Merge Actions

### Self-Verification
- After every edit: ReadLints → fix errors → verify imports
- Before completion: re-read acceptance criteria → run tests → check regressions
- Never say "done" without running tests

### File Paths
- Backend: `[service]/app/` prefix (not `[service]/models/`)
- Tests: `[service]/tests/` or `tests/` (root) for cross-service
- Demos: `demos/` (root) for cross-service
