# WS-B6 Completion Report: Implement tools/list handler

| Field | Value |
|-------|-------|
| **Task ID** | WS-B6 |
| **Task Name** | Implement tools/list handler |
| **Status** | ✅ Completed |
| **Started** | January 30, 2026 |
| **Completed** | January 30, 2026 |
| **Worktree** | vmcp-gateway |

---

## Summary

Implemented the MCP `tools/list` request handler that aggregates tools from multiple backends, applies namespace prefixes, and filters based on an agent's delegated permissions. This component is essential for:
- **Demo 1 (Unified Connection)**: Single connection to access tools from multiple backends
- **Demo 2 (Filtered Visibility)**: Agents only see tools they're permitted to use

---

## Files Created

| File | Lines | Description |
|------|-------|-------------|
| `deeptrail-gateway/app/mcp/permission_mapper.py` | 252 | Tool-to-permission mapping with static registry for MVP backends |
| `deeptrail-gateway/app/mcp/handlers/tools_list.py` | 378 | The `tools/list` handler with Pydantic models and filtering logic |
| `deeptrail-gateway/tests/mcp/test_permission_mapper.py` | 198 | 31 unit tests for PermissionMapper |
| `deeptrail-gateway/tests/mcp/handlers/test_tools_list.py` | 560 | 23 unit tests for tools_list handler |

## Files Modified

| File | Changes | Description |
|------|---------|-------------|
| `deeptrail-gateway/app/mcp/handlers/__init__.py` | +14 | Export tools_list handler components |
| `deeptrail-gateway/app/mcp/__init__.py` | +5 | Export PermissionMapper |

---

## Implementation Details

### PermissionMapper

A static class that provides tool-to-permission mapping:

```python
class PermissionMapper:
    # Static mapping for MVP backends
    TOOL_TO_PERMISSION = {
        "notion.search_pages": "notion:pages:search",
        "notion.read_page": "notion:pages:read",
        "slack.send_message": "slack:messages:send",
        # ... 20+ mappings for Notion, Slack, HubSpot
    }
    
    @classmethod
    def get_permission(cls, tool_name: str) -> str | None
    
    @classmethod
    def infer_permission(cls, tool_name: str) -> str | None
    
    @classmethod
    def is_tool_permitted(cls, tool_name: str, delegated_permissions: list[str]) -> bool
    
    @classmethod
    def filter_tools(cls, tools: list[dict], delegated_permissions: list[str]) -> list[dict]
```

**Key Features:**
- Explicit mapping takes precedence over inference
- Inference supports `{backend}.{action}_{resource}` → `{backend}:{resource}:{action}` pattern
- Unknown tools are denied (fail-closed)
- Supports wildcard permissions (`notion:*`, `*:*`)

### tools/list Handler

Async handler that returns filtered tool schemas:

```python
async def handle_tools_list(params: dict[str, Any]) -> dict[str, Any]:
    """
    1. Extract agent_session_id and delegated_permissions from context
    2. Get allowed tools from session (pre-computed at initialization)
    3. Build tool schemas with namespace prefixes
    4. Apply permission filtering (defense in depth)
    5. Return JSON-RPC compliant response
    """
```

**Response Format:**
```json
{
  "tools": [
    {
      "name": "notion.search_pages",
      "description": "[Notion] Search for pages by title or content",
      "inputSchema": {
        "type": "object",
        "properties": { "query": { "type": "string" } },
        "required": ["query"]
      }
    }
  ]
}
```

### Dependency Integration

| Dependency | Usage |
|------------|-------|
| `MCPSessionManager` (B3) | Retrieve agent session and pre-computed `allowed_tools` |
| `ToolCache` (B5) | Fetch cached tool schemas without redundant network calls |
| `namespace` utils (B4) | Apply `{backend}.` prefix and `[{Backend}]` description prefix |

---

## Test Coverage

### PermissionMapper Tests (31 tests)

| Category | Tests | Coverage |
|----------|-------|----------|
| `get_permission` | 5 | Exact lookup, missing tool, backend-scoped |
| `infer_permission` | 5 | Pattern inference, failures |
| `is_tool_permitted` | 6 | Exact match, inference, wildcards, denied |
| `filter_tools` | 5 | Multiple tools, empty lists, partial permissions |
| Backend queries | 4 | Get tools/permissions by backend ID |
| Dynamic mapping | 4 | add_mapping, remove_mapping |
| Edge cases | 2 | Empty inputs, case sensitivity |

### tools_list Handler Tests (23 tests)

| Category | Tests | Coverage |
|----------|-------|----------|
| Core functionality | 6 | Successful list, empty tools, single tool |
| Permission filtering | 4 | Subset permissions, no permissions, wildcard |
| Namespace prefixing | 3 | Tool names, descriptions, multiple backends |
| Integration | 3 | MCPSessionManager, ToolCache, cross-component |
| Error handling | 4 | Missing session, configuration errors, graceful degradation |
| Edge cases | 3 | Empty cache, consistency, minimal schema |

---

## Quality Verification

```bash
# Linting
$ ruff check deeptrail-gateway/app/mcp/
All checks passed!

# Tests
$ pytest deeptrail-gateway/tests/mcp/ -v
========================= 308 passed in 6.47s =========================
```

---

## Acceptance Criteria Status

| Criterion | Status |
|-----------|--------|
| ✅ Handler fetches tools from all connected backend sessions |
| ✅ Tools from multiple backends combined into single list |
| ✅ Cache miss logs warning but doesn't fail request |
| ✅ All tool names prefixed with `{backend}.` |
| ✅ Tool descriptions enhanced with `[{Backend}]` prefix |
| ✅ Only tools matching delegated permissions returned |
| ✅ Unknown tools denied (fail-closed) |
| ✅ Response follows MCP JSON-RPC format |
| ✅ All unit tests pass (54 new tests) |

---

## Tasks Unblocked

| Task ID | Task Name | Status |
|---------|-----------|--------|
| **B8** | Implement tool aggregator | **Now Ready** (B5 ✅, B6 ✅) |

---

## Next Recommended Tasks

1. **WS-B7**: Implement tools/call handler (ready, B3 ✅, B4 ✅)
2. **WS-B8**: Implement tool aggregator (ready, B5 ✅, B6 ✅)

Both B7 and B8 can be executed in parallel.
