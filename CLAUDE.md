# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

> **CHECK YOUR OWN WORK**: Before declaring any task complete, verify your changes actually work. Run lints after edits. Run tests before completion. Validate assumptions against the codebase, not design docs. See [CODE_STANDARDS.md](CODE_STANDARDS.md).

## Project Overview

DeepSecure is a security platform that provides Identity-as-Code for AI agents, enabling them to fetch their own ephemeral credentials programmatically instead of using static API keys. The project consists of a Python CLI/SDK and backend services that implement a dual-service gateway architecture.

## Quick Reference

| Topic | Reference |
|-------|-----------|
| Dev commands, env setup, build, debugging | [docs/DEVELOPMENT_COMMANDS.md](docs/DEVELOPMENT_COMMANDS.md) |
| Module structure, services, key patterns | [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) |
| Test organization, markers, backend deps | [docs/TESTING_GUIDE.md](docs/TESTING_GUIDE.md) |
| Full Agent JWT creation flow, detailed MCP examples | [docs/TOKEN_TYPES.md](docs/TOKEN_TYPES.md) |
| Engineering preferences, review process, verification | [CODE_STANDARDS.md](CODE_STANDARDS.md) |
| Developer workflow (E2E) | [docs/DEVELOPER_WORKFLOW.md](docs/DEVELOPER_WORKFLOW.md) |
| Task ticket template | [docs/workstreams/TASK_TICKET_TEMPLATE.md](docs/workstreams/TASK_TICKET_TEMPLATE.md) |
| Merge point guide | [docs/workstreams/MERGE_POINT_GUIDE.md](docs/workstreams/MERGE_POINT_GUIDE.md) |

## Development Workflow

### Making Changes
1. Core functionality → `deepsecure/_core/`
2. Public API → `deepsecure/client.py` or `deepsecure/`
3. CLI → `deepsecure/commands/`
4. Always run `make check-all` before committing

### Pre-Completion Checklist (MANDATORY)

```
□ ReadLints on all edited files - fix any errors I introduced
□ Code compiles/imports without errors
□ Relevant tests pass (or new tests added)
□ Acceptance criteria explicitly verified (re-read and check each one)
□ No obvious regressions to existing functionality
□ Changes match the design doc/spec (if applicable)
```

### Security Considerations
- Never commit secrets or private keys
- All crypto operations use `ed25519` signatures
- Agent private keys stored in OS keyring by default
- JWT tokens for service-to-service auth; split-key architecture

## Task Breakdown Workflow

When given a design document: identify architectural boundaries → map dependencies → group into parallel workstreams → order sequentially within each → output as tasks with acceptance criteria.

### Dependency Classification
- **PARALLEL**: Independent modules, separate services, isolated tests
- **SEQUENTIAL**: Schema → migrations → code, API contracts → implementations
- **BLOCKED**: Requires external input, design decision, or approval

### Common Workstream Patterns

**SDK Feature:** `WS-A: Core (_core/) → WS-B: Public API → WS-C: CLI (parallel with B) → WS-D: Tests → WS-E: Docs`

**Cross-Service:** `WS-A: Contracts → WS-B: Control (after A) → WS-C: Gateway (parallel with B) → WS-D: SDK → WS-E: E2E`

## Critical Rules (MANDATORY)

### Workstream Prerequisites

Never run `/run-batch` without the full PLAN phase. ALL 7 files must exist:
`BREAKDOWN.md`, `CODEBASE_ANALYSIS.md`, `MERGE_POINTS.md`, `BATCH_EXECUTION_PLAN.md`, `WORKSTREAM.md`, `STATUS.md`, `PIPELINE_STATE.md`

```bash
FEATURE="[feature-name]"
for f in BREAKDOWN CODEBASE_ANALYSIS MERGE_POINTS BATCH_EXECUTION_PLAN WORKSTREAM STATUS PIPELINE_STATE; do
  [ -f "docs/workstreams/${FEATURE}/${f}.md" ] && echo "✅ ${f}.md" || echo "❌ MISSING"
done
```

### Status Verification

Status files MUST stay consistent with completion reports. After every batch:
```bash
/verify-batch-completion [batch-id] [feature-name]
```
DO NOT proceed to next batch if verification fails.

### Codebase Exploration Before Breakdown

ALWAYS explore the codebase BEFORE creating task breakdowns. Design docs describe **intent**, not **current state**. Run `/explore-codebase` before `/breakdown-design`.

| Codebase State | Task Type |
|----------------|-----------|
| Doesn't exist | `Create` |
| Exists, format wrong | `Modify` |
| Exists, needs validation | `Verify` |
| Exists, fully correct | `Skip` |

### Merge Point Protocol

Sequential pre-merge gate — complete ALL steps in order:
1. **Batch Validation** — run every command in BATCH_EXECUTION_PLAN.md Validation section
2. **Container Deployment** — `docker compose build`, `up -d`, migrations
3. **Container Test Scenarios** — live `curl` tests from MERGE_POINTS.md
4. **Success Criteria** — check every box in MERGE_POINTS.md
5. **Merge Actions** — only NOW: `git commit`, `git push`, `git tag`

Tags MUST include feature branch: `{base-tag}-$(git branch --show-current)`

### Test Suite Health

ALL tests must pass before a batch is declared complete — not just workstream tests. Pre-existing failures must be fixed if encountered.

### Documentation Consistency

| File | Updated When |
|------|--------------|
| `reports/WS-{ID}-completion.md` | Task completed |
| `STATUS.md` | After each task |
| `WORKSTREAM.md` | After each task |
| `BATCH_EXECUTION_PLAN.md` | After each batch |
| `MERGE_POINTS.md` | After batch triggers MP |

## Task Ticket Structure

All tickets MUST include 12 sections: Metadata, Specification, API Contracts, Pre-Conditions, Task Description, Files to Create/Modify, Acceptance Criteria, Test Cases, Post-Conditions, Validation, References, Execution.

API Contracts section is **MANDATORY** — even for non-API tasks (use the "internal module" note format).

Templates: `docs/workstreams/TASK_TICKET_TEMPLATE.md`, `docs/workstreams/TASK_SPEC_TEMPLATE.md`

## Backend Conventions

| Design Doc Pattern | Actual Pattern |
|--------------------|----------------|
| `[service]/models/` | `[service]/app/models/` |
| `[service]/services/` | `[service]/app/services/` |
| `[service]/api/[domain]/` | `[service]/app/api/v1/endpoints/` |

Services: `*_service.py` suffix. Validation: `*_validation.py`. Constraints: active verbs (`*_checker.py`).

## Token Types & API Validation (CRITICAL)

Different endpoints require different authentication tokens. Using the wrong token type causes 401 errors.

| Token Type | How to Obtain | Used For | Header Format |
|------------|---------------|----------|---------------|
| **User Token** | `POST /api/v1/auth/login` → `.token` | User-facing endpoints, service connection | `Authorization: Bearer $USER_TOKEN` |
| **Agent JWT** | Ed25519 challenge-response flow | Agent-to-Control APIs, vault token retrieval | `Authorization: Bearer $AGENT_JWT` |
| **Internal API Token** | From `docker-compose.yml` env var | Gateway-to-Control internal APIs | `Authorization: Bearer gateway-internal-secret-token` |

**Common Mistakes:**

| Mistake | Error | Fix |
|---------|-------|-----|
| Using User Token for vault token retrieval | `401 "missing user identity"` | Use Agent JWT (has `owner` claim) |
| Using User Token for vault token refresh | `401 "Invalid internal token"` | Use Internal API Token + `X-User-ID` header |
| Using `.access_token` for login response | Returns `null` | Use `.token` - login returns `token` field |

### MCP Gateway Protocol (CRITICAL)

The Gateway requires `initialize` before any `tools/call`. Skipping returns: `"Session not found. Call initialize first."`

**Required sequence:** `initialize` → `tools/list` (optional) → `tools/call`

```bash
# Step 1: Initialize MCP session
curl -s -X POST http://localhost:8002/mcp \
  -H "Authorization: Bearer $AGENT_JWT" \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc":"2.0","method":"initialize","id":1,"params":{"protocolVersion":"2024-11-05","capabilities":{},"clientInfo":{"name":"test-agent","version":"1.0.0"}}}'

# Step 2: Now tools/call works
curl -s -X POST http://localhost:8002/mcp \
  -H "Authorization: Bearer $AGENT_JWT" \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc":"2.0","method":"tools/call","id":2,"params":{"name":"notion.search_pages","arguments":{"query":"test"}}}'
```

### Async Test Fixtures

Use `@pytest_asyncio.fixture` for async fixtures, NOT `@pytest.fixture`. Wrong fixture decorator causes `AttributeError: 'async_generator' object has no attribute 'post'`.

### API Contract Verification

Always verify implementation endpoints match design doc specs exactly.

```bash
# Check implemented endpoints
grep -r "@router\.\(get\|post\|put\|delete\)" [file] | grep -o '"/api/v1[^"]*"'
```

For the full Agent JWT creation flow (6-step Ed25519 challenge-response), see [docs/TOKEN_TYPES.md](docs/TOKEN_TYPES.md).

## Lessons Learned Changelog

| Date | Lesson | Section |
|------|--------|---------|
| Feb 2026 | Design docs describe intent, not current state — reduced over-scoping 60% | Codebase Exploration |
| Feb 2026 | `@pytest_asyncio.fixture` required for async (not `@pytest.fixture`) | [TOKEN_TYPES.md](docs/TOKEN_TYPES.md) |
| Feb 2026 | Login returns `.token` not `.access_token` | [TOKEN_TYPES.md](docs/TOKEN_TYPES.md) |
| Feb 2026 | MCP Gateway requires `initialize` before `tools/call` | [TOKEN_TYPES.md](docs/TOKEN_TYPES.md) |
| May 2026 | Workstreams created manually bypass pre-flight — added 7-file check | Workstream Prerequisites |
| May 2026 | Merge Actions before Container Tests = unvalidated tags | Merge Point Protocol |
| May 2026 | 151 pre-existing test failures skipped as "not mine" — wrong | Test Suite Health |
| May 2026 | Bare MP tags collide across workstreams — added branch suffix | Merge Point Protocol |
