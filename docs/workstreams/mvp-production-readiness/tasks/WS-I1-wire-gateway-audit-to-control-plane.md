# Task: WS-I1 Wire Gateway Audit Events to Control Plane

> **Status:** `completed`
> **Completion Date:** February 21, 2026
> **Batch:** P2 (Audit Integration)
> **Worktree:** mvp-prod-gateway

---

## Metadata

| Field | Value |
|-------|-------|
| **Task ID** | WS-I1 |
| **Workstream** | I (Audit Integration) |
| **Phase** | P2 (Production Readiness) |
| **Dependencies** | None (Control Plane endpoints already exist) |
| **Complexity** | S (< 1 hr) |
| **Service** | deeptrail-gateway |
| **Validates** | E2E Step 10 (Audit Trail), Test Scenario 16 returns populated events |

---

## Specification

> See full specification: [../specs/WS-I1-spec.md](../specs/WS-I1-spec.md)

### Key Contracts

**Endpoint Called by AuditMiddleware:**

| Field | Value |
|-------|-------|
| **Method** | `POST` |
| **Path** | `/api/v1/audit/events` |
| **Auth** | None (internal service-to-service) |

**Request Body:**
```json
{
  "event_type": "mcp_tool_call | permission_denied | credential_error | tool_error",
  "agent_id": "string",
  "on_behalf_of": "string (user email)",
  "tool": "string (e.g., notion.search_pages)",
  "timestamp": "string (ISO 8601)",
  "arguments": "object | null (redacted)",
  "result_summary": "string | null",
  "error": "string | null",
  "duration_ms": "int | null",
  "delegation_id": "string | null",
  "session_id": "string | null"
}
```

**Response (Success 200/201):**
```json
{
  "event_id": "evt-<uuid>",
  "timestamp": "2026-02-21T10:30:00Z"
}
```

**Error Handling (Fail-Open):**

| Scenario | Gateway Behavior |
|----------|------------------|
| 200/201/202 | Log debug, continue |
| 4xx/5xx | Log warning, log locally as fallback |
| Timeout | Log warning, log locally as fallback |

---

## API Contracts

> **Note:** This task implements middleware configuration, not API endpoints.
> The AuditMiddleware calls the Control Plane audit API but does not expose any Gateway API endpoints.
> The Control Plane `POST /api/v1/audit/events` endpoint already exists (see `deeptrail-control/app/api/v1/endpoints/audit.py`).

---

## Pre-Conditions

- [x] `AuditMiddleware` class exists with `control_plane_url` parameter (`audit.py:160-163`)
- [x] `configure_audit_middleware()` function exists (`audit.py:527-554`)
- [x] `_send_event()` method implements HTTP POST (`audit.py:334-385`)
- [x] Control Plane `POST /api/v1/audit/events` endpoint exists (`audit.py:157-205`)
- [x] Control Plane `GET /api/v1/audit/events` endpoint exists (`audit.py:208-277`)
- [x] `config.control_plane_url` available in Gateway (`main.py`)

---

## Task Description

### Objective

Configure `AuditMiddleware` with `control_plane_url` so audit events are dispatched to the Control Plane instead of being logged locally.

### Background

Currently, the Gateway's `AuditMiddleware` is NOT configured with a `control_plane_url` at startup. This causes `_send_event()` to take the MVP path (line 347-350), logging events locally via `logger.info()` instead of POSTing them to the Control Plane. As a result, `GET /api/v1/audit/events` always returns an empty array. This task fixes the configuration gap - all the code already exists, it just needs to be wired up.

### What to Implement

1. **Add import** (`main.py`):
   - Add `from app.middleware.audit import configure_audit_middleware`

2. **Configure audit middleware at startup** (`main.py`):
   - Add `configure_audit_middleware()` call after other middleware configuration
   - Pass `control_plane_url=config.control_plane_url`
   - Pass `timeout_seconds=5.0`
   - Pass `enabled=True`
   - Add info log confirming configuration

---

## Files to Create/Modify

| File | Action | Description |
|------|--------|-------------|
| `deeptrail-gateway/app/main.py` | Modify | Add import and `configure_audit_middleware()` call |
| `deeptrail-gateway/tests/middleware/test_audit.py` | Verify | Ensure existing tests still pass |

---

## Acceptance Criteria

### Functional Criteria

- [x] `configure_audit_middleware(control_plane_url=...)` called at Gateway startup
- [x] Gateway logs show "Audit middleware configured: control_plane_url=http://..."
- [x] Audit events dispatched to `POST /api/v1/audit/events`
- [ ] `GET /api/v1/audit/events` returns populated events after tool calls (requires E2E verification)
- [ ] Test Scenario 16 (INTEGRATION_VALIDATION_GUIDE.md) returns non-empty events (requires E2E verification)

### Security Criteria

- [x] Sensitive data (tokens, passwords) NOT appearing in audit events (existing redaction preserved)
- [x] Audit failures don't block tool execution (fail-open behavior preserved)
- [x] No token values in log messages

### Integration Criteria

- [x] Gateway logs show "Audit event sent" (not "MVP mode: Log locally")
- [x] All existing tests in `test_audit.py` pass unchanged (40/40 passed)
- [x] MVP mock path still works when `control_plane_url=None` (for development)

---

## Test Cases

| Test Case | Module | Expected Result | Notes |
|-----------|--------|-----------------|-------|
| MVP mode unchanged | `_send_event` | Local logging | `control_plane_url=None` |
| Production mode sends | `_send_event` | HTTP POST to Control Plane | `control_plane_url` set |
| Tool call audited | E2E | Event in `GET /audit/events` | After `tools/call` |
| Permission denied audited | E2E | Event in `GET /audit/events` | After denied tool |
| Timeout fallback | `_send_event` | Local logging | Control Plane timeout |
| Redaction preserved | `_redact_sensitive` | Passwords replaced with `[REDACTED]` | Existing behavior |

---

## Post-Conditions

After this task is complete:
- [ ] Test Scenario 16 (Audit Events Query) returns populated events
- [ ] Sarah can review agent audit trail via dashboard
- [ ] Audit events persisted for compliance/debugging
- [ ] E2E Step 10 fully functional

---

## Validation

### Unit Tests
```bash
cd deeptrail-gateway
pytest tests/middleware/test_audit.py -v
```

### Manual Verification
```bash
# 1. Start services
cd /Users/imaxxs/repositories/deepsecure-mvp
docker compose up -d --build

# 2. Wait for initialization
sleep 20

# 3. Run complete validation
./scripts/validate_integration.sh

# 4. Check Gateway logs for "Audit event sent" (not "Log locally")
docker compose logs deeptrail-gateway 2>&1 | grep -i "audit"
# Expected: "Audit event sent" or "Audit middleware configured"
# NOT: "MVP mode: Log locally"

# 5. Query audit events from Control Plane
USER_TOKEN=$(curl -s -X POST http://localhost:8000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"sarah@acme.com","password":"test_password"}' | jq -r '.token')

curl -s "http://localhost:8000/api/v1/audit/events?limit=10" \
  -H "Authorization: Bearer $USER_TOKEN" | jq .

# Expected: {"events": [...], "total": > 0, ...}
# NOT: {"events": [], "total": 0, ...}
```

---

## References

- **Specification:** [../specs/WS-I1-spec.md](../specs/WS-I1-spec.md)
- **Design Doc:** `STATUS.md` P1-4: Wire Gateway audit events to Control Plane DB
- **Upstream:** None (Control Plane endpoints already exist)
- **Downstream:** None
- **Related Code:**
  - `deeptrail-gateway/app/middleware/audit.py` (AuditMiddleware, configure function)
  - `deeptrail-gateway/app/main.py` (startup configuration)
  - `deeptrail-control/app/api/v1/endpoints/audit.py` (target endpoints)
  - `docs/INTEGRATION_VALIDATION_GUIDE.md` Section 19 (Test Scenario 16)

---

## Execution

```bash
# Run in mvp-prod-gateway worktree:
cd /Users/imaxxs/repositories/mvp-prod-gateway
/execute-task WS-I1 mvp-production-readiness

# Complete this task:
/complete-task WS-I1 mvp-production-readiness
```
