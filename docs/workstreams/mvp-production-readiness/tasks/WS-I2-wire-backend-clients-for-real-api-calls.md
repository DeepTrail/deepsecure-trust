# Task: WS-I2 Wire Backend Clients for Real API Calls

> **Status:** `ready`
> **Batch:** P1-B4 (Integration)
> **Worktree:** mvp-prod-gateway

---

## Metadata

| Field | Value |
|-------|-------|
| **Task ID** | WS-I2 |
| **Workstream** | I (Integration Wiring) |
| **Phase** | P1 (Real Backend Integration) |
| **Dependencies** | WS-G2, WS-G3, WS-G4, WS-H1 |
| **Complexity** | `M` (1-3hr) |
| **Service** | deeptrail-gateway |
| **Validates** | E2E Step 8 (Execute Tool), Test Scenario 17 |

---

## Specification

> See full specification: [../specs/WS-I2-spec.md](../specs/WS-I2-spec.md)

### Key Contracts

**Interface Expected by `tools_call.py`:**
| Method | Arguments | Returns | Description |
|--------|-----------|---------|-------------|
| `call_tool` | `backend_id, tool_name, arguments, auth_headers: dict, mcp_session_id` | `dict` (MCP response) | Execute tool via backend router |

**Interface Provided by `BackendRouter`:**
| Method | Arguments | Returns | Description |
|--------|-----------|---------|-------------|
| `route_tool_call` | `namespaced_tool, arguments, auth_token: str` | `ToolResult` | Route to correct backend client |

**Adapter Pattern:**
```
tools_call.py → BackendClientAdapter → BackendRouter → NotionDirectClient
                ↓ Converts:
                - auth_headers dict → auth_token str
                - ToolResult → MCP response dict
```

---

## API Contracts

> **Note:** This task implements an internal adapter class, not API endpoints.
> The adapter bridges the interface between `tools_call.py` and `BackendRouter`.
> See WS-G2, WS-G3, WS-G4 for backend client implementations that make the actual API calls.

---

## Pre-Conditions

- [x] WS-G2 (Notion REST API) complete
- [x] WS-G3 (Slack REST API) complete
- [x] WS-G4 (HubSpot REST API) complete
- [x] WS-H1 (Credential Injection) complete
- [x] `BackendRouter` class exists in `app/backends/router.py`
- [x] `ToolResult` type exists in `app/backends/types.py`

---

## Task Description

### Objective

Create a `BackendClientAdapter` class that bridges the interface mismatch between `tools_call.py` and `BackendRouter`, enabling real API calls instead of mock responses.

### Background

Currently, `configure_tools_call_handler()` in `main.py` passes `backend_client=None`, causing `_forward_to_backend()` to always return mock responses like `"[Notion] Found 5 results..."`.

The backend clients (Notion, Slack, HubSpot) are fully implemented, but they have a different interface than what `tools_call.py` expects:
- `tools_call.py` passes `auth_headers: dict` (e.g., `{"Authorization": "Bearer xxx"}`)
- Backend clients expect `auth_token: str` (e.g., `"xxx"`)

An adapter class is needed to bridge this gap.

### What to Implement

1. **BackendClientAdapter class** (`app/backends/adapter.py`):
   - Constructor accepting `BackendRouter`
   - `call_tool()` method matching `tools_call.py` interface
   - `_extract_auth_token()` helper to extract Bearer token from headers dict
   - `_to_mcp_response()` helper to convert `ToolResult` to MCP format

2. **Factory function** (`create_backend_adapter()`):
   - Create `BackendRouter`
   - Register Notion, Slack, HubSpot clients
   - Return wrapped `BackendClientAdapter`

3. **Configuration in main.py**:
   - Import `create_backend_adapter`
   - Replace `backend_client=None` with `backend_client=create_backend_adapter()`

---

## Files to Create/Modify

| File | Action | Description |
|------|--------|-------------|
| `deeptrail-gateway/app/backends/adapter.py` | Create | BackendClientAdapter class and factory |
| `deeptrail-gateway/app/main.py` | Modify | Wire adapter into configure_tools_call_handler |
| `deeptrail-gateway/tests/backends/test_adapter.py` | Create | Unit tests for adapter |

---

## Acceptance Criteria

### Functional Criteria
- [ ] `BackendClientAdapter` class exists in `app/backends/adapter.py`
- [ ] `create_backend_adapter()` factory function exists
- [ ] `main.py` creates adapter and passes to `configure_tools_call_handler`
- [ ] `main.py` no longer has `backend_client=None`
- [ ] Adapter extracts Bearer token from `auth_headers` dict correctly
- [ ] Adapter converts `ToolResult` to MCP response format
- [ ] Tool calls return real API responses (not mock)

### Security Criteria
- [ ] No token values appear in log messages
- [ ] Auth token extracted without modification (no accidental truncation)

### Integration Criteria
- [ ] All existing `tools_call` tests still pass
- [ ] Test Scenario 17 (INTEGRATION_VALIDATION_GUIDE.md) returns real API response
- [ ] Gateway logs show "BackendClientAdapter" routing messages

### Contract Verification
- [ ] Adapter `call_tool()` signature matches `tools_call.py` line 661-667
- [ ] Factory registers all 3 backends: notion, slack, hubspot
- [ ] MCP response format: `{"content": [...], "isError": bool}`

---

## Test Cases

| Test Case | Method | Endpoint/Module | Expected Status | Notes |
|-----------|--------|-----------------|-----------------|-------|
| Extract Bearer token | Unit | `_extract_auth_token({"Authorization": "Bearer xxx"})` | Returns `"xxx"` | |
| Handle missing header | Unit | `_extract_auth_token({})` | Returns `None` | |
| Handle None headers | Unit | `_extract_auth_token(None)` | Returns `None` | |
| Convert success result | Unit | `_to_mcp_response(success_result)` | `{"isError": False}` | |
| Convert error result | Unit | `_to_mcp_response(error_result)` | `{"isError": True}` | |
| Route to Notion | Integration | `call_tool("notion", "notion.search_pages", ...)` | Calls NotionDirectClient | |
| Route with auth | Integration | `call_tool(..., auth_headers={...})` | Token passed to backend | |

---

## Post-Conditions

After this task is complete:
- [ ] Test Scenario 17 returns real Notion/Slack/HubSpot API responses
- [ ] E2E Step 8 (Execute Tool) works with real APIs
- [ ] Mock response code path is no longer taken (unless backend_client=None for testing)
- [ ] All P1 backend integration tasks complete

---

## Validation

### Unit Tests
```bash
cd deeptrail-gateway
pytest tests/backends/test_adapter.py -v
```

### Manual Verification
```bash
# 1. Start services
docker compose up -d --build
sleep 20

# 2. Verify gateway startup logs show adapter configured
docker compose logs deeptrail-gateway 2>&1 | grep -i "BackendClientAdapter\|backend client"

# 3. Run tool call via MCP (requires Agent JWT - see validate_integration.sh)
# Expected: Real API response, NOT "[Notion] Found 5 results..."

# 4. Check Test Scenario 17 passes
./scripts/validate_integration.sh 2>&1 | grep -A5 "Scenario 17"
```

---

## References

- **Specification:** [../specs/WS-I2-spec.md](../specs/WS-I2-spec.md)
- **Design Doc:** STATUS.md P1-3 (Tool calls return mock strings)
- **Upstream:**
  - WS-G2 (Notion REST API) - ✅ Complete
  - WS-G3 (Slack REST API) - ✅ Complete
  - WS-G4 (HubSpot REST API) - ✅ Complete
  - WS-H1 (Credential Injection) - ✅ Complete
- **Downstream:** None (final integration piece)
- **Related Code:**
  - `deeptrail-gateway/app/mcp/handlers/tools_call.py` (lines 659-693)
  - `deeptrail-gateway/app/backends/router.py`
  - `deeptrail-gateway/app/backends/notion_client.py`
  - `deeptrail-gateway/app/backends/slack_client.py`
  - `deeptrail-gateway/app/backends/hubspot_client.py`
  - `deeptrail-gateway/app/main.py` (lines 185-189)

---

## Execution

```bash
# Run in mvp-prod-gateway worktree:
cd /Users/imaxxs/repositories/mvp-prod-gateway
/execute-task WS-I2 mvp-production-readiness

# Complete this task:
/complete-task WS-I2 mvp-production-readiness
```
