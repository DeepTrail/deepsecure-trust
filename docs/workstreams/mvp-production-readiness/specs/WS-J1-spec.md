# Task Specification: WS-J1 Add Verbose Data to Permission Denied MCP Errors

> **IMMUTABLE AFTER DESIGN APPROVAL**
>
> This specification defines what implementation MUST match exactly.
> Do not modify without updating the design doc first.
>
> **Source:** INTEGRATION_VALIDATION_GUIDE.md Test Scenario 15

---

## Overview

| Field | Value |
|-------|-------|
| **Task ID** | WS-J1 |
| **Task Name** | Add verbose data to permission denied MCP errors |
| **Type** | Bug Fix / Enhancement |
| **Service** | deeptrail-gateway |
| **Complexity** | S (< 1 hour) |
| **Dependencies** | None |
| **Validates** | Test Scenario 15 (MCP Tool Call Permission Denied) verbose response |

---

## Problem Statement

### Current Behavior

When an agent attempts to call a tool without the required permission, the MCP error response is missing the verbose `data` object:

```json
{
  "jsonrpc": "2.0",
  "id": 4,
  "error": {
    "code": -32001,
    "message": "Permission denied: notion:pages:create not delegated",
    "data": null
  }
}
```

### Expected Behavior

The error response should include helpful debugging information:

```json
{
  "jsonrpc": "2.0",
  "id": 4,
  "error": {
    "code": -32001,
    "message": "Permission denied: notion:pages:create not delegated",
    "data": {
      "tool": "notion.create_page",
      "required_permission": "notion:pages:create",
      "delegated_permissions": ["notion:pages:search", "notion:pages:read", "..."]
    }
  }
}
```

---

## Root Cause Analysis

### Location

**File:** `deeptrail-gateway/app/mcp/handlers/tools_call.py` (lines 420-423)

### Current Code

```python
raise MCPError(
    ToolsCallErrorCode.PERMISSION_DENIED,
    error_message
    # ← No 'data' parameter passed
)
```

### Evidence MCPError Supports `data`

**File:** `deeptrail-gateway/app/mcp/protocol.py` (lines 486-503)

```python
class MCPError(Exception):
    def __init__(
        self,
        code: int | JsonRpcErrorCode,
        message: str,
        data: Any = None  # ← Supported parameter
    ):
```

### Working Example (Constraint Violations)

**File:** `deeptrail-gateway/app/mcp/handlers/tools_call.py` (lines 454-462)

```python
raise MCPError(
    ToolsCallErrorCode.CONSTRAINT_VIOLATED,
    error_msg,
    data={
        "constraint": constraint_violation.constraint_name,
        "current": constraint_violation.current_value,
        "limit": constraint_violation.limit_value,
    }
)
```

---

## Component Specification

### Fix Location

| Field | Value |
|-------|-------|
| **Module** | `deeptrail-gateway/app/mcp/handlers/tools_call.py` |
| **Function** | `handle_tools_call()` |
| **Lines** | ~420-423 |

### Implementation Fix

```python
# In handle_tools_call() around line 420
# Replace the current MCPError raise with:

raise MCPError(
    ToolsCallErrorCode.PERMISSION_DENIED,
    error_message,
    data={
        "tool": tool_name,
        "required_permission": required_perm,
        "delegated_permissions": agent_context.delegated_permissions if agent_context else []
    }
)
```

### Variable Availability

All required variables are available at this point in the code flow:

| Variable | Source | Line |
|----------|--------|------|
| `tool_name` | `call_params.name` | Line 317 |
| `required_perm` | `validation_result.required_permission` | Line 398 |
| `agent_context` | Built from context dict | Lines 287-295 |
| `agent_context.delegated_permissions` | From `_context["delegated_permissions"]` | Line 294 |

---

## Documentation Fix

### Location

**File:** `docs/INTEGRATION_VALIDATION_GUIDE.md` (lines 1328-1341)

### Current Documentation (Incorrect)

```json
{
  "error": {
    "code": -32603,  ← INCORRECT (should be -32001)
    ...
  }
}
```

### Fixed Documentation

```json
{
  "jsonrpc": "2.0",
  "id": 4,
  "error": {
    "code": -32001,
    "message": "Permission denied: notion:pages:create not delegated",
    "data": {
      "tool": "notion.create_page",
      "required_permission": "notion:pages:create",
      "delegated_permissions": ["notion:pages:search", "notion:pages:read"]
    }
  }
}
```

---

## File Location Rules

| Artifact | Correct Location |
|----------|------------------|
| Implementation fix | `deeptrail-gateway/app/mcp/handlers/tools_call.py` |
| Documentation fix | `docs/INTEGRATION_VALIDATION_GUIDE.md` |
| Unit test updates | `deeptrail-gateway/tests/mcp/handlers/test_tools_call.py` |

---

## Test Cases

| Test Case | Method | Expected | Notes |
|-----------|--------|----------|-------|
| Permission denied includes data | `handle_tools_call_standalone()` | MCPError has `data` dict | Verify all 3 fields present |
| Data contains tool name | Exception assertion | `data["tool"]` equals request tool name | Exact match |
| Data contains required permission | Exception assertion | `data["required_permission"]` populated | From validator |
| Data contains delegated list | Exception assertion | `data["delegated_permissions"]` is list | May be empty list |
| No agent context | Edge case | `delegated_permissions` is empty list | Graceful fallback |

### Test Code Example

```python
@pytest.mark.asyncio
async def test_permission_denied_includes_verbose_data(
    self, session_manager, agent_session
):
    """Test that permission denied error includes verbose data object."""
    params = {
        "name": "notion.create_page",
        "arguments": {"title": "Test"},
        "_context": {
            "agent_session_id": "agent-sdr-001",
            "delegated_permissions": ["notion:pages:search"],
        },
    }

    with pytest.raises(MCPError) as exc_info:
        await handle_tools_call_standalone(params, session_manager)

    # Verify error code
    assert exc_info.value.code == ToolsCallErrorCode.PERMISSION_DENIED

    # Verify data object is present
    assert exc_info.value.data is not None

    # Verify data contents
    data = exc_info.value.data
    assert data["tool"] == "notion.create_page"
    assert data["required_permission"] == "notion:pages:create"
    assert data["delegated_permissions"] == ["notion:pages:search"]
```

---

## Contract Verification Checklist

Before marking implementation complete, verify:

- [ ] `MCPError` for PERMISSION_DENIED includes `data` parameter
- [ ] `data["tool"]` contains namespaced tool name (e.g., "notion.create_page")
- [ ] `data["required_permission"]` contains the missing permission
- [ ] `data["delegated_permissions"]` contains agent's delegated permissions list
- [ ] Graceful fallback to empty list when no agent_context
- [ ] Existing permission denied tests still pass
- [ ] New test verifying data object contents passes
- [ ] Documentation updated with correct error code (-32001)
- [ ] No sensitive data (tokens) appears in data object

---

## Validation Commands

### Unit Tests

```bash
cd deeptrail-gateway
pytest tests/mcp/handlers/test_tools_call.py -v -k "permission"
```

### Manual Verification

```bash
# Ensure services are running
docker compose up -d

# Run the integration validation (Test Scenario 15)
# After completing scenarios 1-14, run:

DENIED_RESULT=$(curl -s -X POST http://localhost:8002/mcp \
  -H "Authorization: Bearer $AGENT_JWT" \
  -H "Content-Type: application/json" \
  -d '{
    "jsonrpc": "2.0",
    "method": "tools/call",
    "id": 4,
    "params": {
      "name": "notion.create_page",
      "arguments": {"title": "Test"}
    }
  }')

# Verify data object present
echo "$DENIED_RESULT" | jq '.error.data'

# Expected output (not null):
# {
#   "tool": "notion.create_page",
#   "required_permission": "notion:pages:create",
#   "delegated_permissions": ["notion:pages:search", "notion:pages:read", ...]
# }
```

---

## Security Considerations

| Aspect | Status | Notes |
|--------|--------|-------|
| Token exposure | Safe | No tokens in data object |
| Permission enumeration | Acceptable | Agent already knows its own permissions from JWT |
| Debug information | Helpful | Aids legitimate debugging without security risk |

---

## References

- **Issue Source:** Test Scenario 15 validation failure in INTEGRATION_VALIDATION_GUIDE.md
- **Related Code:** `MCPError` class in `protocol.py`, constraint violation handling
- **MCP Spec:** JSON-RPC 2.0 error data field is standard
- **Upstream Dependencies:** None
- **Downstream Dependents:** Test Scenario 15 validation, E2E integration tests
