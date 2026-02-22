# Task Specification: WS-I2 Wire Backend Clients for Real API Calls

> **IMMUTABLE AFTER DESIGN APPROVAL**
>
> This specification defines what implementation MUST match exactly.
> Do not modify without updating the design doc first.
>
> **Source:** STATUS.md P1-3, INTEGRATION_VALIDATION_GUIDE.md Test Scenario 17

---

## Overview

| Field | Value |
|-------|-------|
| **Task ID** | WS-I2 |
| **Task Name** | Wire Backend Clients for Real API Calls |
| **Type** | Middleware Configuration / Adapter |
| **Service** | deeptrail-gateway |
| **Complexity** | M (1-3 hours) |
| **Dependencies** | WS-G2 (Notion), WS-G3 (Slack), WS-G4 (HubSpot), WS-H1 (Credential Injection) |
| **Validates** | E2E Step 8 (Execute Tool) with real API responses, Test Scenario 17 |

---

## Problem Statement

### Current State (MVP)

```
Gateway tools/call → _forward_to_backend() → backend_client=None?
                                             ↓ YES (always)
                                      _generate_mock_response()
                                             ↓
                                      "[Notion] Found 5 results..."
```

**Root Cause:** `backend_client=None` in `main.py` line 187, causing `_forward_to_backend()` to always take the mock path.

### Desired State

```
Gateway tools/call → _forward_to_backend() → backend_client=BackendClientAdapter
                                             ↓
                                      BackendRouter.route_tool_call()
                                             ↓
                                      NotionDirectClient.call_tool()
                                             ↓
                                      Real Notion API Response
```

---

## Current State Analysis

**Existing Implementation:**
- `deeptrail-gateway/app/backends/notion_client.py` - NotionDirectClient (23 tools)
- `deeptrail-gateway/app/backends/slack_client.py` - SlackDirectClient (7 tools)
- `deeptrail-gateway/app/backends/hubspot_client.py` - HubSpotDirectClient (9 tools)
- `deeptrail-gateway/app/backends/router.py` - BackendRouter with `route_tool_call()`

**What Exists:**
- All 3 backend clients fully implemented with real API calls (WS-G2, WS-G3, WS-G4)
- `BackendRouter` class to dispatch calls to correct client (line 263)
- Credential injection working via WS-H1/WS-H2

**What's Missing:**
- `BackendClientAdapter` class implementing interface expected by `tools_call.py`
- Configuration of adapter in `main.py` `configure_tools_call_handler()`

---

## Interface Mismatch Analysis

### Interface Expected by `tools_call.py` (line 659-667)

```python
_backend_client.call_tool(
    backend_id=backend_id,            # "notion"
    tool_name=tool_name,              # "notion.search_pages" (NAMESPACED)
    arguments=arguments,              # dict
    auth_headers=auth_headers,        # dict {"Authorization": "Bearer xxx"}
    mcp_session_id=mcp_session_id     # str
)
```

### Interface Provided by Backend Clients (e.g., NotionDirectClient)

```python
async def call_tool(
    self,
    tool_name: str,                   # "search_pages" (NOT namespaced)
    arguments: dict[str, Any],
    auth_token: str | None = None,    # str, NOT dict
) -> ToolResult:
```

### Interface Provided by BackendRouter.route_tool_call()

```python
async def route_tool_call(
    self,
    namespaced_tool: str,             # "notion.search_pages" (NAMESPACED)
    arguments: dict[str, Any],
    auth_token: str | None = None,    # str, NOT dict
) -> ToolResult:
```

### Solution: BackendClientAdapter

Create an adapter class that:
1. Implements the interface expected by `tools_call.py`
2. Extracts `auth_token` string from `auth_headers` dict
3. Delegates to `BackendRouter.route_tool_call()`
4. Converts `ToolResult` to dict format expected by MCP protocol

---

## Component Specification

### Class: `BackendClientAdapter`

| Field | Value |
|-------|-------|
| **Module** | `deeptrail-gateway/app/backends/adapter.py` |
| **Type** | Class |
| **Purpose** | Adapt backend router interface to tools_call.py expected interface |

### Class Definition

```python
"""Adapter between tools_call.py interface and BackendRouter."""

from typing import Any
import logging

from .router import BackendRouter
from .types import ToolResult

logger = logging.getLogger(__name__)


class BackendClientAdapter:
    """
    Adapts BackendRouter to the interface expected by tools_call.py.

    tools_call.py expects:
        call_tool(backend_id, tool_name, arguments, auth_headers, mcp_session_id)

    BackendRouter provides:
        route_tool_call(namespaced_tool, arguments, auth_token)

    This adapter bridges the gap.
    """

    def __init__(self, router: BackendRouter):
        """
        Initialize adapter with a configured BackendRouter.

        Args:
            router: BackendRouter with registered backend clients
        """
        self._router = router

    async def call_tool(
        self,
        backend_id: str,
        tool_name: str,
        arguments: dict[str, Any],
        auth_headers: dict[str, str] | None = None,
        mcp_session_id: str | None = None,
    ) -> dict[str, Any]:
        """
        Execute a tool call via the backend router.

        Args:
            backend_id: Backend identifier (e.g., "notion") - IGNORED, extracted from tool_name
            tool_name: Namespaced tool name (e.g., "notion.search_pages")
            arguments: Tool arguments
            auth_headers: Dict of headers, expecting {"Authorization": "Bearer xxx"}
            mcp_session_id: MCP session ID (logged for debugging)

        Returns:
            MCP-formatted result dict with "content" and "isError" keys
        """
        # Extract auth token from headers
        auth_token = self._extract_auth_token(auth_headers)

        logger.debug(
            "BackendClientAdapter: routing %s (session=%s, has_token=%s)",
            tool_name,
            mcp_session_id,
            bool(auth_token),
        )

        # Route to backend via router (handles namespace parsing)
        result: ToolResult = await self._router.route_tool_call(
            namespaced_tool=tool_name,
            arguments=arguments,
            auth_token=auth_token,
        )

        # Convert ToolResult to MCP response format
        return self._to_mcp_response(result)

    def _extract_auth_token(self, auth_headers: dict[str, str] | None) -> str | None:
        """
        Extract Bearer token from auth headers dict.

        Args:
            auth_headers: Dict like {"Authorization": "Bearer xxx"}

        Returns:
            Token string without "Bearer " prefix, or None
        """
        if not auth_headers:
            return None

        auth_value = auth_headers.get("Authorization", "")
        if auth_value.startswith("Bearer "):
            return auth_value[7:]  # Remove "Bearer " prefix

        return auth_value if auth_value else None

    def _to_mcp_response(self, result: ToolResult) -> dict[str, Any]:
        """
        Convert ToolResult to MCP protocol response format.

        Args:
            result: ToolResult from backend client

        Returns:
            Dict with "content" list and "isError" boolean
        """
        if result.is_error:
            return {
                "content": [
                    {
                        "type": "text",
                        "text": result.error_message or "Unknown error",
                    }
                ],
                "isError": True,
            }

        return {
            "content": [
                {
                    "type": "text",
                    "text": result.to_json() if hasattr(result, 'to_json') else str(result.data),
                }
            ],
            "isError": False,
        }
```

---

## Factory Function

### Function: `create_backend_adapter`

```python
# Add to deeptrail-gateway/app/backends/adapter.py

def create_backend_adapter() -> BackendClientAdapter:
    """
    Create a fully configured BackendClientAdapter.

    Creates a BackendRouter with all registered backend clients
    (Notion, Slack, HubSpot) and wraps it in an adapter.

    Returns:
        BackendClientAdapter ready for use in tools_call handler
    """
    from .notion_client import NotionDirectClient
    from .slack_client import SlackDirectClient
    from .hubspot_client import HubSpotDirectClient

    # Create router
    router = BackendRouter()

    # Register all backend clients
    router.register_backend("notion", NotionDirectClient())
    router.register_backend("slack", SlackDirectClient())
    router.register_backend("hubspot", HubSpotDirectClient())

    logger.info(
        "BackendClientAdapter created with backends: %s",
        list(router._backends.keys()),
    )

    return BackendClientAdapter(router)
```

---

## Configuration Change

### File: `deeptrail-gateway/app/main.py`

```python
# Add import at top
from app.backends.adapter import create_backend_adapter

# Change line 185-189 from:
configure_tools_call_handler(
    session_manager=mcp_session_manager,
    backend_client=None,  # MVP: No backend forwarding yet
    audit_logger=None,  # MVP: Basic audit logging
)

# To:
# =============================================================================
# Backend Client Configuration
# =============================================================================
backend_client = create_backend_adapter()
logger.info("Backend client adapter configured for real API calls")

configure_tools_call_handler(
    session_manager=mcp_session_manager,
    backend_client=backend_client,  # Production: Real backend calls
    audit_logger=None,  # TODO: Wire audit logger
)
```

---

## ToolResult Response Handling

### ToolResult Structure (from `types.py`)

```python
@dataclass
class ToolResult:
    status: ToolCallStatus
    data: Any = None
    error_message: str | None = None

    @property
    def is_error(self) -> bool:
        return self.status != ToolCallStatus.SUCCESS

    def to_json(self) -> str:
        """Serialize data to JSON string."""
        import json
        return json.dumps(self.data) if self.data else ""
```

### MCP Response Format (expected by tools_call.py)

```python
{
    "content": [
        {
            "type": "text",
            "text": "JSON serialized result data"
        }
    ],
    "isError": False  # or True for errors
}
```

---

## Error Handling Matrix

| Scenario | Adapter Behavior | MCP Response |
|----------|------------------|--------------|
| Success | `ToolResult.status=SUCCESS` | `{"content": [...], "isError": False}` |
| Backend error | `ToolResult.status=ERROR` | `{"content": [{"type":"text","text":"error"}], "isError": True}` |
| Backend not found | Router returns error ToolResult | `{"content": [...], "isError": True}` |
| Invalid tool name | Router returns error ToolResult | `{"content": [...], "isError": True}` |
| No auth token | Pass `None` to backend | Backend may return 401 error |
| API timeout | Backend client handles | `{"content": [...], "isError": True}` |

---

## File Location Rules

| Artifact | Correct Location | Notes |
|----------|------------------|-------|
| Adapter class | `deeptrail-gateway/app/backends/adapter.py` | NEW file |
| Configuration | `deeptrail-gateway/app/main.py` | Modify existing |
| Unit tests | `deeptrail-gateway/tests/backends/test_adapter.py` | NEW file |
| Integration tests | `tests/e2e/test_backend_integration.py` | NEW file (optional) |

---

## Test Cases

### Unit Tests (NEW)

| Test Case | Method | Expected |
|-----------|--------|----------|
| Extract Bearer token from headers | `_extract_auth_token({"Authorization": "Bearer xxx"})` | `"xxx"` |
| Handle missing Authorization header | `_extract_auth_token({})` | `None` |
| Handle None headers | `_extract_auth_token(None)` | `None` |
| Convert success ToolResult | `_to_mcp_response(success_result)` | `{"content": [...], "isError": False}` |
| Convert error ToolResult | `_to_mcp_response(error_result)` | `{"content": [...], "isError": True}` |
| Route to correct backend | `call_tool("notion", "notion.search_pages", ...)` | Calls NotionDirectClient |
| Route with auth token | `call_tool(..., auth_headers={"Authorization": "Bearer xxx"})` | Token passed to backend |

### Integration Tests (Manual Verification)

```bash
# 1. Start services
docker compose up -d --build

# 2. Wait for initialization
sleep 20

# 3. Run validation script
./scripts/validate_integration.sh

# 4. Check for real API response (not mock)
# Look for actual Notion API response, not "[Notion] Found 5 results..."
docker compose logs deeptrail-gateway 2>&1 | grep -i "BackendClientAdapter"
```

---

## Contract Verification Checklist

Before marking implementation complete, verify:

- [ ] `BackendClientAdapter` class exists in `app/backends/adapter.py`
- [ ] `create_backend_adapter()` factory function exists
- [ ] `main.py` calls `create_backend_adapter()` and passes to `configure_tools_call_handler`
- [ ] `main.py` no longer has `backend_client=None`
- [ ] Adapter extracts auth token from headers correctly
- [ ] Adapter converts ToolResult to MCP response format
- [ ] All existing tools_call tests still pass
- [ ] Test Scenario 17 returns real API response (not mock)
- [ ] Gateway logs show "BackendClientAdapter" routing messages
- [ ] No token values appear in log messages

---

## Expected Output After Implementation

### Before (Current MVP)

```bash
curl -s -X POST http://localhost:8002/mcp \
  -H "Authorization: Bearer $AGENT_JWT" \
  -H "Content-Type: application/json" \
  -d '{
    "jsonrpc": "2.0",
    "method": "tools/call",
    "id": 1,
    "params": {"name": "notion.search_pages", "arguments": {"query": "test"}}
  }'
```

```json
{
  "jsonrpc": "2.0",
  "id": 1,
  "result": {
    "content": [
      {
        "type": "text",
        "text": "[Notion] Found 5 results for 'test'"
      }
    ],
    "isError": false
  }
}
```

### After (With WS-I2)

```json
{
  "jsonrpc": "2.0",
  "id": 1,
  "result": {
    "content": [
      {
        "type": "text",
        "text": "{\"results\": [{\"id\": \"page-123\", \"title\": \"Test Page\", ...}], \"has_more\": false}"
      }
    ],
    "isError": false
  }
}
```

---

## Fallback Behavior

If backend API calls fail, the system should NOT fall back to mock responses. Instead:

1. Return proper error response with `isError: true`
2. Log the error for debugging
3. Audit event recorded with error details

This ensures transparency - agents receive real API errors, not fake success responses.

---

## References

- **Design Doc Section:** STATUS.md P1-3: Tool calls return mock strings
- **Related Specs:** [WS-G2-spec.md](./WS-G2-spec.md), [WS-G3-spec.md](./WS-G3-spec.md), [WS-G4-spec.md](./WS-G4-spec.md), [WS-H1-spec.md](./WS-H1-spec.md)
- **Upstream Dependencies:** WS-G2, WS-G3, WS-G4 (backend clients), WS-H1/H2 (credential injection)
- **Downstream Dependents:** None (final integration piece)
- **Test Scenario:** INTEGRATION_VALIDATION_GUIDE.md Section 20 (Test Scenario 17)
- **Code Reference:** `tools_call.py` lines 659-693
