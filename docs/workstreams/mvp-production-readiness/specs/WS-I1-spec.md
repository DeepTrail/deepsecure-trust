# Task Specification: WS-I1 Wire Gateway Audit Events to Control Plane

> **IMMUTABLE AFTER DESIGN APPROVAL**
>
> This specification defines what implementation MUST match exactly.
> Do not modify without updating the design doc first.
>
> **Source:** STATUS.md P1-4, MERGE_POINTS.md (Audit Persistence), INTEGRATION_VALIDATION_GUIDE.md Test Scenario 16

---

## Overview

| Field | Value |
|-------|-------|
| **Task ID** | WS-I1 |
| **Task Name** | Wire Gateway Audit Events to Control Plane |
| **Type** | Middleware Configuration |
| **Service** | deeptrail-gateway |
| **Complexity** | S (< 1 hour) |
| **Dependencies** | None (Control Plane endpoints already exist) |
| **Validates** | E2E Step 10 (Audit Trail), Test Scenario 16 returns populated events |

---

## Problem Statement

### Current State (MVP)

```
Gateway tools/call → AuditMiddleware → _log_event_locally() → logger.info(...)
                                      ↑ control_plane_url=None
                                      ↓
                              Never calls POST /api/v1/audit/events
                                      ↓
Control Plane GET /api/v1/audit/events → Returns [] (empty in-memory store)
```

**Root Cause:** `AuditMiddleware` is NOT configured with `control_plane_url` in Gateway startup.

### Desired State

```
Gateway tools/call → AuditMiddleware → POST /api/v1/audit/events → Control Plane
                                      ↑ control_plane_url=http://localhost:8000
                                      ↓
Control Plane GET /api/v1/audit/events → Returns [event1, event2, ...]
```

---

## Current State Analysis

**Existing Implementation:**
- `deeptrail-gateway/app/middleware/audit.py` (608 lines) - Full implementation
- `deeptrail-control/app/api/v1/endpoints/audit.py` - Endpoints exist
- `deeptrail-control/app/services/audit_logger_service.py` - Service exists

**What Exists:**
- `AuditMiddleware` class with `control_plane_url` parameter (line 160-163)
- `_send_event()` method that calls `POST /api/v1/audit/events` (line 352-360)
- `configure_audit_middleware()` function (line 527-554)
- Control Plane `POST /api/v1/audit/events` endpoint (audit.py:157-205)
- Control Plane `GET /api/v1/audit/events` endpoint (audit.py:208-277)

**What's Missing:**
- `configure_audit_middleware()` call in `deeptrail-gateway/app/main.py`
- `control_plane_url` parameter passed to configure function

---

## Component Specification

### Module: `AuditMiddleware` Configuration

| Field | Value |
|-------|-------|
| **Module** | `deeptrail-gateway/app/main.py` |
| **Type** | Startup Configuration |
| **Purpose** | Configure AuditMiddleware with Control Plane URL for event dispatch |

### Changes Required

**File:** `deeptrail-gateway/app/main.py`

```python
# Add import at top
from app.middleware.audit import configure_audit_middleware

# Add configuration after other middleware setup (around line 158)
# Configure audit middleware with Control Plane URL
configure_audit_middleware(
    control_plane_url=config.control_plane_url,
    timeout_seconds=5.0,
    enabled=True,
)
logger.info(f"Audit middleware configured with control plane URL: {config.control_plane_url}")
```

---

## API Contract: POST /api/v1/audit/events (called by Gateway)

### Endpoint Definition

| Field | Value |
|-------|-------|
| **Method** | `POST` |
| **Path** | `/api/v1/audit/events` |
| **Auth** | None (internal service-to-service) |
| **Content-Type** | `application/json` |

### Request Schema

```json
{
  "event_type": "string — mcp_tool_call | permission_denied | credential_error | tool_error | delegation_revoked",
  "agent_id": "string — agent identifier",
  "on_behalf_of": "string — user email",
  "tool": "string — namespaced tool name (e.g., notion.search_pages)",
  "timestamp": "string — ISO 8601 datetime",
  "arguments": "object | null — tool arguments (redacted)",
  "result_summary": "string | null — brief result summary",
  "error": "string | null — error message",
  "duration_ms": "int | null — execution duration",
  "delegation_id": "string | null — delegation ID",
  "session_id": "string | null — agent session ID",
  "organization_id": "string | null — organization ID",
  "extra_data": "object | null — additional metadata"
}
```

### Response Schema (Success - 200/201)

```json
{
  "event_id": "string — evt-<uuid>",
  "timestamp": "string — ISO 8601 datetime"
}
```

### Error Responses

| Status | Condition | Gateway Behavior |
|--------|-----------|------------------|
| 200/201/202 | Success | Log debug, continue |
| 4xx | Bad request | Log warning, log locally as fallback |
| 5xx | Server error | Log warning, log locally as fallback |
| Timeout | Network timeout | Log warning, log locally as fallback |

---

## Implementation Details

### Existing Code in AuditMiddleware (No Changes Needed)

The `_send_event()` method already handles the HTTP POST:

```python
# deeptrail-gateway/app/middleware/audit.py:334-385
async def _send_event(self, event: AuditEvent) -> bool:
    if not self.control_plane_url:
        # MVP mode: Log locally
        self._log_event_locally(event)
        return True

    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self.control_plane_url}/api/v1/audit/events",
                json=event.to_dict(),
                timeout=self.timeout_seconds,
            )

            if response.status_code in (200, 201, 202):
                logger.debug("Audit event sent: %s %s", event.event_type.value, event.tool)
                return True
            else:
                logger.warning("Audit send failed: %d for %s", response.status_code, event.tool)
                self._log_event_locally(event)  # Fallback
                return False

    except httpx.TimeoutException:
        logger.warning("Audit send timeout for %s", event.tool)
        self._log_event_locally(event)
        return False
    except Exception as e:
        logger.error("Audit send error: %s", type(e).__name__)
        self._log_event_locally(event)
        return False
```

### Required Change (main.py Only)

```python
# deeptrail-gateway/app/main.py

# Add to imports section (around line 20-40)
from app.middleware.audit import configure_audit_middleware

# Add after line 158 (after health_checker configuration)
# =============================================================================
# Audit Middleware Configuration
# =============================================================================

configure_audit_middleware(
    control_plane_url=config.control_plane_url,
    timeout_seconds=5.0,
    enabled=True,
)
logger.info(f"Audit middleware configured: control_plane_url={config.control_plane_url}")
```

---

## Error Handling Matrix

| Scenario | Gateway Behavior | User Impact |
|----------|------------------|-------------|
| Control Plane healthy | Audit sent async, tool continues | None |
| Control Plane timeout | Log locally, tool continues (fail-open) | Audit gap |
| Control Plane 5xx | Log locally, tool continues (fail-open) | Audit gap |
| Control Plane down | Log locally, tool continues (fail-open) | Audit gap |
| Invalid event format | Log warning, continue | Debug info only |

**Key Principle:** Audit is non-blocking and fail-open. Tool execution is never delayed or failed due to audit issues.

---

## File Location Rules

| Artifact | Correct Location | Notes |
|----------|------------------|-------|
| Configuration change | `deeptrail-gateway/app/main.py` | Add configure call |
| Audit middleware | `deeptrail-gateway/app/middleware/audit.py` | NO changes needed |
| Control Plane endpoint | `deeptrail-control/app/api/v1/endpoints/audit.py` | NO changes needed |
| Unit tests | `deeptrail-gateway/tests/middleware/test_audit.py` | Existing, may need integration test |
| Integration test | `tests/e2e/test_audit_integration.py` | NEW: verify E2E flow |

---

## Test Cases

### Unit Tests (Existing - Verify Pass)

| Test Case | File | Expected |
|-----------|------|----------|
| Log tool call (MVP mode) | `test_audit.py` | Event logged locally |
| Log permission denied | `test_audit.py` | Event logged locally |
| Redact sensitive data | `test_audit.py` | Passwords/tokens redacted |
| Summarize result | `test_audit.py` | Result truncated to 100 chars |

### Integration Tests (NEW)

| Test Case | Method | Endpoint | Expected |
|-----------|--------|----------|----------|
| Audit event persisted | POST | `/api/v1/audit/events` | 200, event_id returned |
| Query events | GET | `/api/v1/audit/events?agent_id=X` | Events array populated |
| Tool call audit flow | POST | `/mcp` (tools/call) | Audit event in Control Plane |

### Manual Verification

```bash
# 1. Start services
docker compose up -d --build

# 2. Wait for initialization
sleep 20

# 3. Run a tool call (using full validation script)
./scripts/validate_integration.sh

# 4. Check audit events
USER_TOKEN=$(curl -s -X POST http://localhost:8000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"sarah@acme.com","password":"test_password"}' | jq -r '.token')

curl -s "http://localhost:8000/api/v1/audit/events?limit=10" \
  -H "Authorization: Bearer $USER_TOKEN" | jq .

# Expected: {"events": [...], "total": > 0, ...}

# 5. Verify Gateway logs show audit sent (not local)
docker compose logs deeptrail-gateway 2>&1 | grep -i "audit event sent"
```

---

## Contract Verification Checklist

Before marking implementation complete, verify:

- [ ] `configure_audit_middleware()` called in `main.py` with `control_plane_url`
- [ ] Gateway startup logs show "Audit middleware configured: control_plane_url=..."
- [ ] `POST /api/v1/audit/events` receives events from Gateway
- [ ] `GET /api/v1/audit/events` returns populated events array
- [ ] Test Scenario 16 (INTEGRATION_VALIDATION_GUIDE.md) passes
- [ ] Audit failures don't block tool execution (fail-open)
- [ ] Sensitive data (tokens, passwords) NOT appearing in audit events
- [ ] Gateway logs show "Audit event sent" (not "MVP mode: Log locally")
- [ ] Existing unit tests in `test_audit.py` still pass

---

## Expected Output After Implementation

### Before (Current MVP)

```bash
curl -s "http://localhost:8000/api/v1/audit/events?limit=10" \
  -H "Authorization: Bearer $USER_TOKEN" | jq .
```

```json
{
  "events": [],
  "total": 0,
  "limit": 10,
  "offset": 0
}
```

### After (With WS-I1)

```json
{
  "events": [
    {
      "id": "evt-abc123def456",
      "timestamp": "2026-02-21T10:30:00.000Z",
      "event_type": "mcp_tool_call",
      "agent_id": "sdr-assistant-001",
      "on_behalf_of": "sarah@acme.com",
      "tool": "notion.search_pages",
      "arguments": {"query": "competitor analysis"},
      "result_summary": "[Notion] Found 5 results...",
      "reason": null,
      "session_id": "asess-xyz789",
      "delegation_id": "del-abc123",
      "extra_data": null
    },
    {
      "id": "evt-def456ghi789",
      "timestamp": "2026-02-21T10:30:05.000Z",
      "event_type": "permission_denied",
      "agent_id": "sdr-assistant-001",
      "on_behalf_of": "sarah@acme.com",
      "tool": "notion.create_page",
      "arguments": null,
      "result_summary": null,
      "reason": "Permission denied: notion:pages:create required",
      "session_id": "asess-xyz789",
      "delegation_id": "del-abc123",
      "extra_data": {"required_permission": "notion:pages:create"}
    }
  ],
  "total": 2,
  "limit": 10,
  "offset": 0
}
```

---

## Docker Compose Verification

Ensure `control_plane_url` is set in Gateway environment:

```yaml
# docker-compose.yml - deeptrail-gateway service
environment:
  - CONTROL_PLANE_URL=http://deeptrail-control:8001
```

The Gateway's `config.control_plane_url` should resolve from this environment variable.

---

## References

- **Design Doc Section:** STATUS.md P1-4: Wire Gateway Audit Events to Control Plane DB
- **Related Specs:** None (standalone task)
- **Upstream Dependencies:** None (Control Plane endpoints already exist)
- **Downstream Dependents:** None
- **Test Scenario:** INTEGRATION_VALIDATION_GUIDE.md Section 19 (Test Scenario 16)
- **MERGE_POINTS.md:** Line 753 - "audit.py:348 - Local logging → Audit events in DB"
