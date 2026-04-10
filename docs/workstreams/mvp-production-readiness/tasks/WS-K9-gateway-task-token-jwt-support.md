# Task: WS-K9 Gateway Task Token JWT Support

> **Status:** `ready`
> **Batch:** P2-B3
> **Worktree:** mvp-prod-gateway (primary), mvp-prod-control (iss/aud fix)

---

## Metadata

| Field | Value |
|-------|-------|
| **Task ID** | WS-K9 |
| **Workstream** | K (Task Token Hierarchy) |
| **Phase** | P2 (Production Hardening) |
| **Dependencies** | WS-K6 ✅, WS-K7 ✅, WS-K8 ✅ |
| **Complexity** | `M` (1–3 hr) |
| **Service** | `deeptrail-gateway` (primary), `deeptrail-control` (minor fix) |
| **Validates** | MP4 Container Test Scenario 5 (Task Token permission enforcement via Gateway) |

---

## Specification

> See full specification: [../specs/WS-K9-spec.md](../specs/WS-K9-spec.md)

### Key Contracts

This task modifies internal middleware, not API endpoints. The external `/mcp`
endpoint contract is unchanged — task tokens should be accepted wherever agent
JWTs are accepted.

**AgentContext extensions:**

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `token_type` | `str` | `"agent_session"` | `"agent_session"` or `"task_token"` |
| `task_id` | `str \| None` | `None` | Task ID from task token JWT |
| `scoped_permissions` | `list[dict] \| None` | `None` | Raw scoped permissions from JWT |

**JWT claim mapping for task tokens:**

| Task Token Claim | AgentContext Field | Mapping |
|-----------------|-------------------|---------|
| `agent_id` | `agent_id` | Direct |
| `task_id` | `session_id` | Used as MCP session key |
| `scoped_permissions[].urn` | `delegated_permissions` | Extract URN strings |
| `token_type` | `token_type` | Direct |
| (not present) | `owner` | `""` (empty; resolved via session lookup) |

---

## API Contracts

> **Note:** This task implements internal middleware changes, not API endpoints.
> The Gateway's `/mcp` endpoint (POST) is unchanged. Task tokens are accepted
> as `Authorization: Bearer <task_token>` headers on the same endpoint.
> See [WS-K8](./WS-K8-create-task-endpoints.md) for the Control Plane task
> token issuance endpoints.

---

## Pre-Conditions

- [x] WS-K6 (TaskToken Model) complete — defines the task token data model
- [x] WS-K7 (TaskService) complete — implements task token JWT issuance
- [x] WS-K8 (Task Endpoints) complete — REST API for task CRUD + token issuance
- [x] Gateway JWT middleware (`jwt_validation.py`) exists and handles Layer 3 JWTs
- [x] MCP session manager (`session_manager.py`) exists and manages agent sessions
- [x] MCP initialize handler (`initialize.py`) creates sessions from JWT context

---

## Task Description

### Objective

Enable the Gateway to accept Task Token JWTs (Layer 4) for MCP sessions, so
agents can operate with least-privilege, task-scoped permissions instead of
broad delegation JWTs.

### Background

Task tokens are issued by the Control Plane (WS-K8) and contain per-task scoped
permissions. They are narrower than agent delegation JWTs — granting access to
only the specific tools needed for a single task. However, the Gateway currently
only understands Layer 3 agent session JWTs. When a task token is presented:

1. The JWT middleware falls to the legacy decode path (wrong `iss`/`aud`)
2. `AgentContext` is populated with empty fields (`agent_id=""`, `session_id=""`,
   `delegated_permissions=[]`)
3. MCP sessions are created with an empty session key, causing lookup failures

This was discovered during MP4 Container Test Scenario 5.

### What to Implement

1. **Fix `iss`/`aud` in Control Plane** (`task_service.py`):
   - Change `"deepsecure-control"` → `"deeptrail-control"`
   - Change `"deepsecure-gateway"` → `"deeptrail-gateway"`
   - Update corresponding test expectations

2. **Extend `AgentContext`** (`jwt_validation.py`):
   - Add `token_type`, `task_id`, `scoped_permissions` fields
   - Add task-token branch in `from_jwt_payload()`:
     - Map `agent_id` → `agent_id` (instead of `sub`)
     - Map `task_id` → `session_id` (used as MCP session key)
     - Extract `scoped_permissions[].urn` → `delegated_permissions`

3. **Update required claims validation** (`jwt_validation.py`):
   - In `_validate_jwt_token()`, after decode, check `token_type`
   - Task tokens require: `agent_id`, `task_id`, `scoped_permissions`
   - Agent session JWTs require existing claims (unchanged)

4. **Handle missing `owner` for vault calls** (`tools_call.py`):
   - Task tokens don't carry `owner` claim
   - Fall back to resolving owner from active sessions or agent metadata

---

## Files to Create/Modify

| File | Action | Description |
|------|--------|-------------|
| `deeptrail-control/app/services/task_service.py` | **Modify** | Fix `iss`/`aud` to `deeptrail-control`/`deeptrail-gateway` |
| `deeptrail-gateway/app/middleware/jwt_validation.py` | **Modify** | Add `token_type`, `task_id`, `scoped_permissions` to `AgentContext`; add task-token claim validation path |
| `deeptrail-gateway/app/mcp/handlers/tools_call.py` | **Modify** | Handle missing `owner` for task token vault lookups |
| `deeptrail-gateway/tests/middleware/test_jwt_validation.py` | **Modify** | Add task token test cases (6 tests) |
| `deeptrail-gateway/tests/mcp/handlers/test_tools_call.py` | **Modify** | Add task-token scoped call tests (3 tests) |
| `deeptrail-control/tests/services/test_task_service.py` | **Modify** | Update expected `iss`/`aud` values |

---

## Acceptance Criteria

### Functional Criteria
- [ ] Task token JWTs are decoded via the primary path (not legacy fallback)
- [ ] `AgentContext.from_jwt_payload()` returns correct fields for task tokens:
  - `agent_id` = task token's `agent_id` claim
  - `session_id` = task token's `task_id` claim
  - `delegated_permissions` = list of URN strings from `scoped_permissions`
  - `token_type` = `"task_token"`
  - `task_id` = task token's `task_id` claim
- [ ] MCP `initialize` with task token creates session keyed by `task_id`
- [ ] MCP `tools/list` with task token returns only tools matching scoped permissions
- [ ] MCP `tools/call` with permitted tool succeeds
- [ ] MCP `tools/call` with non-permitted tool returns `-32001 Permission Denied`

### Security Criteria
- [ ] Task tokens without required claims (`agent_id`, `task_id`, `scoped_permissions`) are rejected with 401
- [ ] Expired task tokens are rejected with 401
- [ ] Invalid task token signatures are rejected

### Integration Criteria
- [ ] Existing Agent JWT (Layer 3) flow is completely unaffected
- [ ] Legacy JWT fallback path is unaffected
- [ ] All existing Gateway tests pass without modification
- [ ] Task token `iss`/`aud` aligned with agent JWT conventions

### Contract Verification
- [ ] `AgentContext` dataclass has `token_type`, `task_id`, `scoped_permissions` fields
- [ ] `_validate_jwt_token()` branches on `token_type` for required claims
- [ ] `task_service.py` uses `iss: "deeptrail-control"`, `aud: "deeptrail-gateway"`

---

## Test Cases

| Test Case | Method | Endpoint/Module | Expected Status | Notes |
|-----------|--------|-----------------|-----------------|-------|
| Task token decoded via primary path | — | `jwt_validation._validate_jwt_token` | Success | Not legacy fallback |
| AgentContext fields from task token | — | `jwt_validation.AgentContext.from_jwt_payload` | Correct fields | All 6 fields verified |
| session_id equals task_id | — | `jwt_validation.AgentContext.from_jwt_payload` | Match | Key for session lookup |
| scoped_permissions mapped to delegated | — | `jwt_validation.AgentContext.from_jwt_payload` | URNs extracted | `[{"urn":"x"}]` → `["x"]` |
| Missing required claims rejected | — | `jwt_validation._validate_jwt_token` | 401 | `agent_id` absent |
| Agent JWT unchanged | — | `jwt_validation._validate_jwt_token` | Success | Regression test |
| Task token MCP initialize | POST | `/mcp` (initialize) | Session created | Keyed by `task_id` |
| Task token tools/call permitted | POST | `/mcp` (tools/call) | Tool executed | In scoped_permissions |
| Task token tools/call denied | POST | `/mcp` (tools/call) | `-32001` error | Not in scoped_permissions |
| Task token owner resolution | — | `tools_call._forward_to_backend` | Owner resolved | For vault lookup |
| Task token iss/aud consistent | — | `task_service.TaskService._issue_task_token` | `deeptrail-*` | Not `deepsecure-*` |

---

## Post-Conditions

After this task is complete:
- [ ] MP4 Container Test Scenario 5 (Task Token permission enforcement) passes end-to-end
- [ ] Task tokens are a fully functional auth mechanism for the Gateway
- [ ] Agents can use least-privilege, task-scoped tokens for MCP tool execution
- [ ] All P2 production hardening features are fully integrated

---

## Validation

### Unit Tests

```bash
# Gateway middleware tests (task token handling)
cd deeptrail-gateway
pytest tests/middleware/test_jwt_validation.py -v -k "task_token"

# Gateway MCP handler tests (scoped calls)
pytest tests/mcp/handlers/test_tools_call.py -v -k "task_token"

# Control Plane task service (iss/aud fix)
cd deeptrail-control
pytest tests/services/test_task_service.py -v -k "iss"

# Full regression (all existing tests)
cd deeptrail-gateway && pytest tests/ -v
cd deeptrail-control && pytest tests/services/test_task_service.py -v
```

### Manual Verification

```bash
# 1. Start full stack
cd /Users/imaxxs/repositories/deepsecure-mvp
docker compose up -d --build
sleep 10

# 2. Login + setup agent + delegation + agent JWT + MCP init
# (See INTEGRATION_VALIDATION_GUIDE.md Steps 1-8)

# 3. Create task + activate + get token
TASK_ID=$(curl -s -X POST "http://localhost:8000/api/v1/tasks/" \
  -H "Authorization: Bearer $AGENT_JWT" \
  -H "Content-Type: application/json" \
  -d '{"name":"test","requested_permissions":[{"permission_urn":"notion:pages:search"}]}' \
  | jq -r '.task_id')
curl -s -X POST "http://localhost:8000/api/v1/tasks/$TASK_ID/activate" \
  -H "Authorization: Bearer $AGENT_JWT"
TASK_TOKEN=$(curl -s -X POST "http://localhost:8000/api/v1/tasks/$TASK_ID/token" \
  -H "Authorization: Bearer $AGENT_JWT" | jq -r '.task_token')
# Expected: non-null JWT

# 4. MCP initialize with task token
curl -s -X POST http://localhost:8002/mcp \
  -H "Authorization: Bearer $TASK_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc":"2.0","method":"initialize","id":1,"params":{"protocolVersion":"2024-11-05","capabilities":{},"clientInfo":{"name":"task-test","version":"1.0"}}}'
# Expected: {"jsonrpc":"2.0","id":1,"result":{"serverInfo":{...}}}

# 5. Permitted tool call
curl -s -X POST http://localhost:8002/mcp \
  -H "Authorization: Bearer $TASK_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc":"2.0","method":"tools/call","id":2,"params":{"name":"notion.search_pages","arguments":{"query":"test"}}}'
# Expected: {"jsonrpc":"2.0","id":2,"result":{...}}

# 6. Denied tool call
curl -s -X POST http://localhost:8002/mcp \
  -H "Authorization: Bearer $TASK_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc":"2.0","method":"tools/call","id":3,"params":{"name":"slack.send_message","arguments":{"channel":"general","text":"test"}}}'
# Expected: {"jsonrpc":"2.0","id":3,"error":{"code":-32001,"message":"Permission denied..."}}
```

---

## References

- **Specification:** [../specs/WS-K9-spec.md](../specs/WS-K9-spec.md)
- **Upstream:** WS-K6 (TaskToken model) ✅, WS-K7 (TaskService) ✅, WS-K8 (Task endpoints) ✅
- **Downstream:** None (completes the task token integration path)
- **Validates:** MP4 Container Test Scenario 5
- **Related Code:**
  - `deeptrail-gateway/app/middleware/jwt_validation.py` — JWT decode + AgentContext
  - `deeptrail-gateway/app/mcp/session_manager.py` — MCP session storage
  - `deeptrail-gateway/app/mcp/handlers/initialize.py` — Session creation from context
  - `deeptrail-gateway/app/mcp/handlers/tools_call.py` — Tool execution + vault calls
  - `deeptrail-gateway/app/main.py` — MCP endpoint context building
  - `deeptrail-control/app/services/task_service.py` — Task token JWT issuance

---

## Execution

```bash
# Primary work in mvp-prod-gateway worktree:
cd /Users/imaxxs/repositories/mvp-prod-gateway
/execute-task WS-K9 mvp-production-readiness

# Complete this task:
/complete-task WS-K9 mvp-production-readiness

# Also apply iss/aud fix in mvp-prod-control:
cd /Users/imaxxs/repositories/mvp-prod-control
# Modify deeptrail-control/app/services/task_service.py (2-line change)
# Update deeptrail-control/tests/services/test_task_service.py (expected values)

# Sync status:
cd /Users/imaxxs/repositories/deepsecure-mvp
/sync-worktree-status mvp-production-readiness
```
