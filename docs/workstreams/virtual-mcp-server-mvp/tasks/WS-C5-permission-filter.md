# Task: WS-C5 Implement Permission Filter

---

## Metadata

| Field | Value |
|-------|-------|
| **Status** | `ready` |
| **Design Doc** | [deepsecure-virtual-mcp-server-mvp.md](../../../design/internal/markdowns/deepsecure-virtual-mcp-server-mvp.md) |
| **Workstream** | WS-C: Auth & Permissions |
| **Dependencies** | C3 (JWT validation middleware) ✅, C4 (Tool→permission mapper) ✅ |
| **Blocked By** | None (C3, C4 complete) |
| **Assigned** | - |
| **Created** | February 5, 2026 |
| **Estimated Complexity** | `M` (2-4 hours) |
| **Batch** | 6 |
| **Target Worktree** | `vmcp-gateway` |

---

## Validation Mapping

| Validates | Reference |
|-----------|-----------|
| **Demo 2** | Filtered Visibility - 90%+ tool reduction |
| **Demo 4** | Permission Enforcement - Unauthorized blocked at gateway |
| **User Journey Step** | Step 7: Agent receives filtered tools/list |

---

## Pre-Conditions

Before starting this task, ensure:

- [x] C3 (JWT validation middleware) is complete - provides `request.state.agent_context` with `delegated_permissions`
- [x] C4 (Tool→permission mapper) is complete - provides `PermissionMapper.filter_tools()`
- [x] B6 (tools/list handler) is complete - returns aggregated tools
- [x] B8 (Tool aggregator) is complete - combines tools from backends

---

## Task Description

Implement a **permission filter middleware** that intercepts `tools/list` responses and filters them to only include tools the agent has permission to use based on their delegation.

### Context

This is **Step 7 of Sarah's journey**: Agent asks "What can I do?" and receives only delegated tools.

The permission filter sits in the response path and:
1. Intercepts `tools/list` responses from B6
2. Extracts `delegated_permissions` from `request.state.agent_context` (set by C3)
3. Uses `PermissionMapper.filter_tools()` (from C4) to filter tools
4. Returns only permitted tools to the agent

### Key Security Requirement

**Fail-closed behavior**: If permissions cannot be determined, return empty tool list (not all tools).

### Integration Point

```
Agent → Gateway
         │
         ├── JWTValidationMiddleware (C3) → sets request.state.agent_context
         │
         ├── tools/list handler (B6) → returns all aggregated tools
         │
         └── PermissionFilter (C5) → filters tools by delegation
                  │
                  └── Uses PermissionMapper.filter_tools() (C4)
```

---

## Files to Create/Modify

| File | Action | Description |
|------|--------|-------------|
| `deeptrail-gateway/app/middleware/permission_filter.py` | **CREATE** | Permission filter middleware |
| `deeptrail-gateway/app/mcp/handlers/tools_list.py` | **MODIFY** | Integrate permission filtering |
| `deeptrail-gateway/app/main.py` | **MODIFY** | Register middleware (if needed) |
| `deeptrail-gateway/tests/middleware/test_permission_filter.py` | **CREATE** | Unit tests |

---

## Implementation Details

### 1. PermissionFilterMiddleware

```python
"""
Permission Filter for tools/list responses.

Filters MCP tools/list responses to only include tools the agent
has delegated permission to use.

This is Step 7 of Sarah's journey: Agent sees only delegated tools.

Key Features:
- Intercepts tools/list responses
- Uses delegated_permissions from JWT (via AgentContext)
- Uses PermissionMapper to filter tools
- Fail-closed: returns empty list if permissions unavailable
- Logs filtering statistics for audit/debugging

Usage:
    # In tools/list handler
    filtered_tools = permission_filter.filter_response(
        tools=aggregated_tools,
        agent_context=request.state.agent_context
    )
"""

from app.middleware.jwt_validation import AgentContext
from app.mcp.permission_mapper import PermissionMapper

class PermissionFilter:
    """
    Filters tools by delegated permissions.
    
    Can be used as:
    1. Direct function call in handlers
    2. Middleware for response interception (optional)
    """
    
    @staticmethod
    def filter_tools(
        tools: list[dict],
        agent_context: AgentContext,
    ) -> list[dict]:
        """
        Filter tools by agent's delegated permissions.
        
        Args:
            tools: List of tool schemas from aggregator
            agent_context: Validated agent context with delegated_permissions
            
        Returns:
            Filtered list of tools agent can use
            
        Security:
            - Returns empty list if agent_context is None (fail-closed)
            - Uses PermissionMapper.filter_tools() for actual filtering
        """
        if agent_context is None:
            logger.warning("No agent context - returning empty tool list (fail-closed)")
            return []
        
        if not agent_context.delegated_permissions:
            logger.info("Agent %s has no delegated permissions", agent_context.agent_id)
            return []
        
        filtered = PermissionMapper.filter_tools(
            tools, 
            agent_context.delegated_permissions
        )
        
        # Calculate reduction for Demo 2 metric
        original_count = len(tools)
        filtered_count = len(filtered)
        reduction_pct = ((original_count - filtered_count) / original_count * 100) if original_count > 0 else 0
        
        logger.info(
            "Permission filter: %d/%d tools (%.1f%% reduction) for agent %s",
            filtered_count, original_count, reduction_pct, agent_context.agent_id
        )
        
        return filtered
    
    @staticmethod
    def get_permitted_backends(
        agent_context: AgentContext,
    ) -> set[str]:
        """
        Get set of backends the agent has any permission for.
        
        Useful for optimizing tool aggregation - only query 
        backends the agent can actually use.
        
        Args:
            agent_context: Validated agent context
            
        Returns:
            Set of backend IDs (e.g., {"notion", "slack"})
        """
        backends = set()
        for perm in agent_context.delegated_permissions:
            # Permission format: backend:resource:action
            parts = perm.split(":")
            if len(parts) >= 1:
                backends.add(parts[0])
        return backends
```

### 2. Integration with tools/list Handler

Modify `deeptrail-gateway/app/mcp/handlers/tools_list.py`:

```python
from app.middleware.permission_filter import PermissionFilter
from app.middleware.jwt_validation import AgentContext

async def handle_tools_list(
    request: Request,
    params: dict | None = None,
) -> dict:
    """
    Handle MCP tools/list request with permission filtering.
    
    Flow:
    1. Get agent context from request.state (set by JWT middleware)
    2. Aggregate tools from all backends (B8)
    3. Filter tools by delegated permissions (C5)
    4. Return filtered, namespaced tools
    """
    # Get agent context (fail-closed if missing)
    agent_context: AgentContext | None = getattr(
        request.state, "agent_context", None
    )
    
    if agent_context is None:
        logger.warning("No agent context for tools/list - returning empty")
        return {"tools": []}
    
    # Get permitted backends for optimization
    permitted_backends = PermissionFilter.get_permitted_backends(agent_context)
    
    # Aggregate tools only from permitted backends
    all_tools = await tool_aggregator.aggregate(
        backends=list(permitted_backends)
    )
    
    # Filter by specific permissions
    filtered_tools = PermissionFilter.filter_tools(
        tools=all_tools,
        agent_context=agent_context,
    )
    
    return {"tools": filtered_tools}
```

### 3. Key Behaviors

| Scenario | Behavior |
|----------|----------|
| No agent context | Return empty list (fail-closed) |
| Empty permissions | Return empty list |
| All tools permitted | Return all tools |
| Some tools permitted | Return only permitted tools |
| Unknown tool | Excluded (fail-closed via C4) |

---

## Acceptance Criteria

### Protocol Criteria
- [ ] `tools/list` returns only tools matching `delegated_permissions`
- [ ] Response format unchanged (just filtered)
- [ ] Empty permissions → empty tools list
- [ ] Tools maintain proper namespace prefixes

### Security Criteria
- [ ] **Fail-closed**: No agent context → empty list, not all tools
- [ ] Unknown tools are excluded (handled by C4's PermissionMapper)
- [ ] No information leakage about excluded tools
- [ ] Filtering logged for audit trail

### Integration Criteria
- [ ] Uses `AgentContext` from C3 (jwt_validation.py)
- [ ] Uses `PermissionMapper.filter_tools()` from C4
- [ ] Works with B6 tools/list handler
- [ ] Works with B8 tool aggregator

### Demo 2 Metric
- [ ] Can demonstrate 90%+ tool reduction when agent has limited delegation
  - Example: 20 total tools → 2 delegated = 90% reduction

---

## Test Cases

### Unit Tests (`test_permission_filter.py`)

```python
import pytest
from app.middleware.permission_filter import PermissionFilter
from app.middleware.jwt_validation import AgentContext

class TestPermissionFilter:
    """Tests for C5: Permission Filter"""
    
    @pytest.fixture
    def sample_tools(self):
        return [
            {"name": "notion.search_pages", "description": "Search Notion pages"},
            {"name": "notion.create_page", "description": "Create Notion page"},
            {"name": "slack.send_message", "description": "Send Slack message"},
            {"name": "slack.list_channels", "description": "List Slack channels"},
            {"name": "hubspot.get_contact", "description": "Get HubSpot contact"},
        ]
    
    @pytest.fixture
    def agent_with_limited_perms(self):
        return AgentContext(
            agent_id="agent-123",
            owner="sarah@example.com",
            delegation_id="del-456",
            session_id="sess-789",
            delegated_permissions=[
                "notion:pages:search",
                "slack:messages:send",
            ],
        )
    
    def test_filter_returns_only_permitted_tools(
        self, sample_tools, agent_with_limited_perms
    ):
        """C5: Should filter to only permitted tools"""
        filtered = PermissionFilter.filter_tools(
            tools=sample_tools,
            agent_context=agent_with_limited_perms,
        )
        
        names = [t["name"] for t in filtered]
        assert "notion.search_pages" in names
        assert "slack.send_message" in names
        assert "notion.create_page" not in names
        assert "slack.list_channels" not in names
        assert "hubspot.get_contact" not in names
    
    def test_filter_with_no_permissions_returns_empty(self, sample_tools):
        """C5: Empty permissions should return empty list"""
        agent = AgentContext(
            agent_id="agent-123",
            owner="sarah@example.com",
            delegation_id="del-456",
            session_id="sess-789",
            delegated_permissions=[],
        )
        
        filtered = PermissionFilter.filter_tools(
            tools=sample_tools,
            agent_context=agent,
        )
        
        assert filtered == []
    
    def test_filter_with_none_context_returns_empty(self, sample_tools):
        """C5 Fail-closed: None context should return empty list"""
        filtered = PermissionFilter.filter_tools(
            tools=sample_tools,
            agent_context=None,
        )
        
        assert filtered == []
    
    def test_filter_reduction_calculation(
        self, sample_tools, agent_with_limited_perms
    ):
        """C5 Demo 2: Should achieve significant reduction"""
        filtered = PermissionFilter.filter_tools(
            tools=sample_tools,
            agent_context=agent_with_limited_perms,
        )
        
        original = len(sample_tools)  # 5
        after = len(filtered)  # 2
        reduction = (original - after) / original * 100
        
        assert reduction >= 50  # At least 50% reduction for this test
    
    def test_get_permitted_backends(self, agent_with_limited_perms):
        """C5: Should extract backend IDs from permissions"""
        backends = PermissionFilter.get_permitted_backends(
            agent_with_limited_perms
        )
        
        assert "notion" in backends
        assert "slack" in backends
        assert "hubspot" not in backends
    
    def test_filter_preserves_tool_schema(
        self, sample_tools, agent_with_limited_perms
    ):
        """C5: Filtered tools should preserve full schema"""
        filtered = PermissionFilter.filter_tools(
            tools=sample_tools,
            agent_context=agent_with_limited_perms,
        )
        
        for tool in filtered:
            assert "name" in tool
            assert "description" in tool
```

### Integration Tests

```python
@pytest.mark.integration
async def test_tools_list_returns_filtered_tools(
    gateway_client, authenticated_agent_headers
):
    """C5 Integration: tools/list should return only permitted tools"""
    response = await gateway_client.post(
        "/mcp",
        json={
            "jsonrpc": "2.0",
            "method": "tools/list",
            "id": 1,
        },
        headers=authenticated_agent_headers,  # JWT with limited perms
    )
    
    assert response.status_code == 200
    result = response.json()
    tools = result["result"]["tools"]
    
    # Verify only permitted tools returned
    for tool in tools:
        # Each tool should require a permission the agent has
        # (specific assertions depend on test JWT permissions)
        pass

@pytest.mark.integration
async def test_tools_list_without_auth_returns_empty(gateway_client):
    """C5 Fail-closed: No auth should return empty tools list"""
    response = await gateway_client.post(
        "/mcp",
        json={
            "jsonrpc": "2.0",
            "method": "tools/list",
            "id": 1,
        },
        # No Authorization header
    )
    
    # Should either return 401 (from C3) or empty tools
    assert response.status_code in [200, 401]
    if response.status_code == 200:
        result = response.json()
        assert result["result"]["tools"] == []
```

---

## Post-Conditions

After completing this task:

1. `tools/list` returns only tools the agent has permission for
2. Tool reduction is measurable (for Demo 2)
3. Filtering is logged for audit trail
4. C6 (delegation validator) can build on this for tools/call

---

## Unblocks

| Task | Name | Notes |
|------|------|-------|
| **F3** | Demo 2: Filtered Visibility | Requires C5 to show 90%+ reduction |

---

## References

- **Design Doc**: Section "Step 7: Agent asks 'What can I do?'"
- **C3 Implementation**: `deeptrail-gateway/app/middleware/jwt_validation.py`
- **C4 Implementation**: `deeptrail-gateway/app/mcp/permission_mapper.py`
- **B6 Handler**: `deeptrail-gateway/app/mcp/handlers/tools_list.py`
- **B8 Aggregator**: `deeptrail-gateway/app/mcp/aggregator.py`

---

## Notes

- The permission filter should be efficient as it runs on every tools/list request
- Consider caching permitted tool list per session if performance becomes an issue
- The 90%+ reduction metric for Demo 2 assumes agent has limited delegation (e.g., 2-3 permissions out of 20+ available tools)
