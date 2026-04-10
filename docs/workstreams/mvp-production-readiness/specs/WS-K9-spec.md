# Task Specification: WS-K9 — Gateway Task Token JWT Support

> **Purpose**: Teach the Gateway's JWT middleware and MCP session management to
> recognise and correctly process Task Token JWTs (Layer 4), so that agents
> operating with a task-scoped token can initialize MCP sessions and execute
> tool calls through the Gateway with properly scoped permissions.

---

## Metadata

| Field | Value |
|-------|-------|
| **Task ID** | WS-K9 |
| **Workstream** | K — Task Token Hierarchy |
| **Phase** | P2 — Production Hardening |
| **Dependencies** | WS-K6 (Task Token model), WS-K7 (TaskService), WS-K8 (Task endpoints) |
| **Complexity** | M (1–3 hr) |
| **Service** | `deeptrail-gateway` |
| **Validates** | MP4 Container Test Scenario 5 (Task Token permission enforcement) |

---

## Problem Statement

Task Tokens (Layer 4) issued by the Control Plane use a different JWT claim
structure than Agent Session JWTs (Layer 3). The Gateway's JWT middleware and
MCP session management only understand Layer 3 tokens today:

### Layer 3 — Agent Session JWT (works)

```json
{
  "sub": "sdr-assistant-001",
  "owner": "sarah@acme.com",
  "delegated_permissions": ["notion:pages:search"],
  "delegation_id": "del-abc123",
  "session_id": "asess-xyz789",
  "iss": "deeptrail-control",
  "aud": "deeptrail-gateway"
}
```

### Layer 4 — Task Token JWT (broken)

```json
{
  "task_id": "task-379b49a5-...",
  "agent_id": "sdr-assistant-001",
  "scoped_permissions": [
    { "urn": "notion:pages:search", "constraints": {} }
  ],
  "token_type": "task_token",
  "deadline": null,
  "auto_revoke_on_complete": true,
  "iss": "deepsecure-control",
  "aud": "deepsecure-gateway"
}
```

### Three Root Causes

| # | Issue | Where | Effect |
|---|-------|-------|--------|
| 1 | **Issuer/audience mismatch** | `task_service.py` sets `iss: "deepsecure-control"` / `aud: "deepsecure-gateway"`, but Gateway expects `"deeptrail-control"` / `"deeptrail-gateway"` | Primary decode path fails → falls to legacy path |
| 2 | **Missing standard claims** | Task token has `agent_id` instead of `sub`, `scoped_permissions` instead of `delegated_permissions`, no `session_id` | `AgentContext.from_jwt_payload()` yields `agent_id=""`, `session_id=""`, `delegated_permissions=[]` |
| 3 | **Empty session key** | `mcp_endpoint()` maps `agent_session_id = agent_context.session_id` → `""` | Session created with key `""`, subsequent lookups may fail or collide |

### Observed Behaviour

1. `initialize` with task token: **succeeds** (session created with empty key)
2. `tools/call` with task token: **fails** — `"No agent session. Call initialize first."`
3. Even if session lookup worked, `delegated_permissions` would be `[]` so no tools would be allowed

---

## API Contracts

> **Note:** This task modifies internal middleware and session management, not
> API endpoints. The `/mcp` endpoint contract is unchanged — task tokens should
> be accepted anywhere agent JWTs are accepted today.

### Behavioural Contract

| Scenario | Token Type | Expected Behaviour |
|----------|-----------|-------------------|
| MCP initialize | Task Token | Session created, scoped tools listed |
| tools/list | Task Token | Only tools matching `scoped_permissions` returned |
| tools/call (permitted) | Task Token | Tool executed with credential injection |
| tools/call (denied) | Task Token | `-32001 Permission Denied` error |
| tools/call (expired task) | Task Token | `-32002 Session Invalid` or `401 token_expired` |

---

## Technical Design

### Change 1: Fix issuer/audience in Control Plane (task_service.py)

Align task token `iss`/`aud` with agent JWT conventions.

**File:** `deeptrail-control/app/services/task_service.py`

```python
# Before (inconsistent)
claims["iss"] = "deepsecure-control"
claims["aud"] = "deepsecure-gateway"

# After (consistent with agent JWTs)
claims["iss"] = "deeptrail-control"
claims["aud"] = "deeptrail-gateway"
```

This allows the Gateway's primary decode path (with issuer/audience validation)
to accept task tokens without falling to the legacy path.

### Change 2: Extend AgentContext for task tokens (jwt_validation.py)

Add task-token-aware fields and a secondary `from_jwt_payload` path.

**File:** `deeptrail-gateway/app/middleware/jwt_validation.py`

Add to `AgentContext`:

```python
@dataclass
class AgentContext:
    agent_id: str
    owner: str
    delegation_id: str
    session_id: str
    delegated_permissions: list[str] = field(default_factory=list)
    groups: list[str] = field(default_factory=list)
    party_type: str = "first_party"
    idp_issuer: str | None = None
    # --- New fields for task tokens ---
    token_type: str = "agent_session"   # "agent_session" | "task_token"
    task_id: str | None = None
    scoped_permissions: list[dict] | None = None  # raw scoped_permissions from JWT

    @classmethod
    def from_jwt_payload(cls, payload: dict[str, Any]) -> "AgentContext":
        token_type = payload.get("token_type", "agent_session")

        if token_type == "task_token":
            scoped = payload.get("scoped_permissions", [])
            perm_urns = [p["urn"] for p in scoped if isinstance(p, dict) and "urn" in p]
            return cls(
                agent_id=payload.get("agent_id", ""),
                owner="",  # task tokens don't carry owner
                delegation_id="",
                session_id=payload.get("task_id", ""),  # use task_id as session key
                delegated_permissions=perm_urns,
                token_type="task_token",
                task_id=payload.get("task_id"),
                scoped_permissions=scoped,
            )

        # Existing Layer 3 logic (unchanged)
        return cls(
            agent_id=payload.get("sub", ""),
            owner=payload.get("owner", ""),
            delegation_id=payload.get("delegation_id", ""),
            session_id=payload.get("session_id", ""),
            delegated_permissions=payload.get("delegated_permissions", []),
            groups=payload.get("groups", []),
            party_type=payload.get("party_type", "first_party"),
            idp_issuer=payload.get("idp_issuer"),
        )
```

### Change 3: Update required claims validation (jwt_validation.py)

The middleware's `_validate_required_claims` currently requires `sub`, `owner`,
`delegated_permissions`, `delegation_id`, `session_id`. Task tokens don't have
these. Add a task-token-specific validation path.

**File:** `deeptrail-gateway/app/middleware/jwt_validation.py`

In `_validate_jwt_token()`, after successful decode, check `token_type` before
validating required claims:

```python
# After successful decode with issuer/audience
token_type = payload.get("token_type")

if token_type == "task_token":
    # Task tokens have different required claims
    task_required = ["agent_id", "task_id", "scoped_permissions"]
    self._validate_required_claims(payload, task_required)
else:
    # Standard Layer 3 agent session
    self._validate_required_claims(payload, self.REQUIRED_CLAIMS)
```

### Change 4: Session key for task tokens (main.py)

The `mcp_endpoint` function maps `agent_context.session_id` to
`agent_session_id`. With Change 2, task tokens use `task_id` as the
`session_id`, so this mapping works automatically. No change needed in
`main.py` — the `AgentContext.session_id` field is already set to `task_id`
for task tokens.

### Change 5: Owner resolution for vault calls (tools_call.py)

The `tools_call` handler passes `agent_context.owner` to the credential
injector for vault token retrieval. Task tokens don't carry `owner`. The
handler should fall back to looking up the agent's owner from the session
or from the Control Plane.

**File:** `deeptrail-gateway/app/mcp/handlers/tools_call.py`

```python
# When building vault request, resolve owner:
user_id = agent_context.owner
if not user_id and agent_context.token_type == "task_token":
    # For task tokens, look up owner from the agent session
    # or from the task metadata via Control Plane API
    # MVP: use the agent_id to resolve owner from active sessions
    for sess in session_manager._sessions.values():
        if any(
            bs.parent_agent_session == agent_context.session_id
            for bs in sess.backend_sessions.values()
        ):
            user_id = sess.delegator
            break
```

**Note:** A cleaner approach for production would be to include `owner` in the
task token claims. This is noted as a follow-up recommendation.

---

## Files to Create/Modify

| File | Action | Description |
|------|--------|-------------|
| `deeptrail-control/app/services/task_service.py` | **Modify** | Fix `iss`/`aud` to `deeptrail-control`/`deeptrail-gateway` |
| `deeptrail-gateway/app/middleware/jwt_validation.py` | **Modify** | Add `token_type`, `task_id`, `scoped_permissions` to `AgentContext`; add task-token claim validation path |
| `deeptrail-gateway/app/main.py` | **No change** | `agent_context.session_id` already maps correctly with Change 2 |
| `deeptrail-gateway/app/mcp/handlers/tools_call.py` | **Modify** | Handle missing `owner` for task token vault lookups |
| `deeptrail-gateway/tests/middleware/test_jwt_validation.py` | **Modify** | Add task token test cases |
| `deeptrail-gateway/tests/mcp/handlers/test_tools_call.py` | **Modify** | Add task-token scoped call tests |
| `deeptrail-control/tests/services/test_task_service.py` | **Modify** | Update expected `iss`/`aud` values |

---

## Test Endpoint Specification

> These are integration tests against the running containers, not unit tests.

| Test Case | Method | Endpoint | Auth | Expected |
|-----------|--------|----------|------|----------|
| Task token MCP initialize | POST | `/mcp` | `Bearer $TASK_TOKEN` | `{"result": {"serverInfo": ...}}` |
| Task token tools/list | POST | `/mcp` | `Bearer $TASK_TOKEN` | Only scoped tools listed |
| Task token tools/call (permitted) | POST | `/mcp` | `Bearer $TASK_TOKEN` | Tool executed |
| Task token tools/call (denied) | POST | `/mcp` | `Bearer $TASK_TOKEN` | `-32001` error |
| Task token expired | POST | `/mcp` | `Bearer $EXPIRED_TASK_TOKEN` | `401 token_expired` |
| Agent JWT still works | POST | `/mcp` | `Bearer $AGENT_JWT` | All existing behaviour preserved |

---

## Unit Test Cases

### jwt_validation.py

| Test | Description |
|------|-------------|
| `test_task_token_decoded_correctly` | Task token with `iss: deeptrail-control` is decoded via primary path |
| `test_task_token_agent_context_fields` | `AgentContext` has correct `token_type`, `task_id`, `agent_id`, `delegated_permissions` |
| `test_task_token_session_id_is_task_id` | `AgentContext.session_id` equals `task_id` |
| `test_task_token_scoped_permissions_mapped` | `scoped_permissions[].urn` mapped to `delegated_permissions[]` |
| `test_task_token_missing_required_claims` | Task token without `agent_id` raises 401 |
| `test_agent_jwt_unchanged` | Existing Layer 3 flow is unaffected |

### tools_call.py

| Test | Description |
|------|-------------|
| `test_task_token_tools_call_permitted` | Tool in `scoped_permissions` is executed |
| `test_task_token_tools_call_denied` | Tool NOT in `scoped_permissions` returns `-32001` |
| `test_task_token_owner_resolution` | Vault credential lookup resolves owner for task token |

### task_service.py (Control Plane)

| Test | Description |
|------|-------------|
| `test_task_token_iss_aud_consistent` | Issued token has `iss: deeptrail-control`, `aud: deeptrail-gateway` |

---

## Technical Requirements

### Framework-Specific Requirements

| Requirement | Pattern | Why |
|-------------|---------|-----|
| Async test fixtures | `@pytest_asyncio.fixture` | Async generators require pytest-asyncio |
| JWT mocking | Create tokens with `jose.jwt.encode()` | Must match Gateway's decode library |
| Gateway tests | Mock Control Plane responses | Gateway tests run without live Control Plane |

### Backward Compatibility

| Token Type | Before This Change | After This Change |
|-----------|-------------------|------------------|
| Agent Session JWT (Layer 3) | ✅ Works | ✅ Works (unchanged) |
| Legacy JWT (no iss/aud) | ✅ Works (fallback) | ✅ Works (fallback unchanged) |
| Task Token JWT (Layer 4) | ❌ Broken (empty session) | ✅ Works |

---

## Acceptance Criteria

- [ ] Task token JWTs are accepted by the Gateway's JWT middleware without falling to legacy path
- [ ] `AgentContext.from_jwt_payload()` correctly populates all fields from task token claims
- [ ] `AgentContext.session_id` is set to `task_id` for task tokens
- [ ] `AgentContext.delegated_permissions` contains URN strings from `scoped_permissions`
- [ ] MCP `initialize` with task token creates a session keyed by `task_id`
- [ ] MCP `tools/list` with task token returns only tools matching scoped permissions
- [ ] MCP `tools/call` with task token and permitted tool succeeds
- [ ] MCP `tools/call` with task token and non-permitted tool returns `-32001`
- [ ] Existing Agent JWT flow is completely unaffected (regression tests pass)
- [ ] Task token `iss`/`aud` aligned with agent JWT conventions in Control Plane
- [ ] All existing Gateway tests pass without modification

---

## Validation

### Unit Tests

```bash
# Gateway middleware tests
cd deeptrail-gateway
pytest tests/middleware/test_jwt_validation.py -v -k "task_token"

# Gateway MCP handler tests
pytest tests/mcp/handlers/test_tools_call.py -v -k "task_token"

# Control Plane task service tests (iss/aud fix)
cd deeptrail-control
pytest tests/services/test_task_service.py -v -k "iss"
```

### Container Integration Test

```bash
# Prerequisites: full stack running, agent registered with delegation

# 1. Create and activate a task
TASK_ID=$(curl -s -X POST "http://localhost:8000/api/v1/tasks/" \
  -H "Authorization: Bearer $AGENT_JWT" \
  -H "Content-Type: application/json" \
  -d '{"name":"test","requested_permissions":[{"permission_urn":"notion:pages:search"}]}' \
  | jq -r '.task_id')
curl -s -X POST "http://localhost:8000/api/v1/tasks/$TASK_ID/activate" \
  -H "Authorization: Bearer $AGENT_JWT"

# 2. Get task token
TASK_TOKEN=$(curl -s -X POST "http://localhost:8000/api/v1/tasks/$TASK_ID/token" \
  -H "Authorization: Bearer $AGENT_JWT" | jq -r '.task_token')

# 3. MCP initialize with task token
curl -s -X POST http://localhost:8002/mcp \
  -H "Authorization: Bearer $TASK_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc":"2.0","method":"initialize","id":1,"params":{"protocolVersion":"2024-11-05","capabilities":{},"clientInfo":{"name":"task-test","version":"1.0"}}}'
# Expected: {"jsonrpc":"2.0","id":1,"result":{...}}

# 4. tools/call with permitted tool
curl -s -X POST http://localhost:8002/mcp \
  -H "Authorization: Bearer $TASK_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc":"2.0","method":"tools/call","id":2,"params":{"name":"notion.search_pages","arguments":{"query":"test"}}}'
# Expected: {"jsonrpc":"2.0","id":2,"result":{...}}

# 5. tools/call with denied tool
curl -s -X POST http://localhost:8002/mcp \
  -H "Authorization: Bearer $TASK_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc":"2.0","method":"tools/call","id":3,"params":{"name":"slack.send_message","arguments":{"channel":"general","text":"test"}}}'
# Expected: {"jsonrpc":"2.0","id":3,"error":{"code":-32001,"message":"Permission denied..."}}
```

---

## Post-Conditions

- MP4 Container Test Scenario 5 (Task Token permission enforcement) passes end-to-end
- Task tokens become a fully functional authentication mechanism for the Gateway
- Agents can operate with least-privilege, task-scoped tokens instead of broad delegation JWTs

---

## Follow-Up Recommendations

| Item | Priority | Description |
|------|----------|-------------|
| Include `owner` in task token claims | High | Avoids the vault owner resolution workaround; add `owner` to `TaskService._issue_task_token()` |
| Task token usage tracking | Medium | Increment `usage_count` on the `TaskToken` model when the Gateway processes a `tools/call` |
| Task token revocation check | Medium | Gateway checks with Control Plane whether task token is still active before executing |
| Constraint enforcement | Low | Honour `constraints` in `scoped_permissions` (e.g., `max_usage`, field restrictions) |

---

## References

- [WS-K6 Spec](./WS-K6-spec.md) — Task Token model definition
- [WS-K7 Spec](./WS-K7-spec.md) — TaskService and token issuance
- [WS-K8 Spec](./WS-K8-spec.md) — Task REST endpoints
- [MERGE_POINTS.md](../MERGE_POINTS.md) — MP4 Container Test Scenarios
- Gateway JWT middleware: `deeptrail-gateway/app/middleware/jwt_validation.py`
- MCP session manager: `deeptrail-gateway/app/mcp/session_manager.py`
- MCP initialize handler: `deeptrail-gateway/app/mcp/handlers/initialize.py`
- Task token issuance: `deeptrail-control/app/services/task_service.py`
