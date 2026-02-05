# Task: WS-C4 Implement Tool→Permission Mapper

---

## Metadata

| Field | Value |
|-------|-------|
| **Status** | `ready` |
| **Design Doc** | [deepsecure-virtual-mcp-server-mvp.md](../../../design/internal/markdowns/deepsecure-virtual-mcp-server-mvp.md) |
| **Workstream** | WS-C: Auth & Permissions |
| **Dependencies** | B4 (Namespace Prefixer) ✅ |
| **Blocked By** | None (B4 complete) |
| **Assigned** | - |
| **Created** | February 5, 2026 |
| **Estimated Complexity** | `S` (1-2 hours) |
| **Batch** | 5 |
| **Target Worktree** | `vmcp-gateway` |

---

## Validation Mapping

| Mapping | Value |
|---------|-------|
| **Validates Demo** | Demo 2: Filtered Visibility, Demo 4: Permission Enforcement |
| **Validates User Journey Step** | Step 7: Agent Discovers Tools, Step 8: Agent Executes Task |

---

## Pre-Conditions

Before starting this task, ensure:

- [x] B4 (Namespace Prefixer) is complete
- [x] B6 (tools/list handler) is complete - uses permission filtering
- [x] B7 (tools/call handler) is complete - uses permission validation
- [x] Existing `permission_mapper.py` exists in gateway (verify/enhance)

---

## Task Description

Implement (or verify) the tool→permission mapper that translates MCP tool names to permission strings. This enables the gateway to filter `tools/list` responses and validate `tools/call` requests against the agent's delegated permissions.

### Context

From the MVP design (Section 2.6 - Steps 7 & 8):

```
Permission Mapping Convention:
- Tool name format: {backend}.{tool_name}
- Permission format: {backend}:{resource}:{action}

Examples:
- notion.search_pages → notion:pages:search
- slack.send_message → slack:messages:send
- hubspot.get_contact → hubspot:contacts:read

Step 7 (tools/list): Filter tools where agent has permission
Step 8 (tools/call): Validate permission before routing to backend
Step 9 (denied): Return error if permission not in delegation
```

### Current State

The `permission_mapper.py` file exists with:
- Static mapping for Notion, Slack, HubSpot tools
- `get_permission()` - Get permission for a tool
- `infer_permission()` - Infer permission from naming convention
- `is_tool_permitted()` - Check if tool is allowed
- `filter_tools()` - Filter tools by permissions

### Verification Required

This task involves **verifying and enhancing** the existing implementation:

1. **Verify mappings are complete** for MVP backends
2. **Add any missing tools** from D3/D4/D5 backend clients
3. **Ensure integration** with tools/list (B6) and tools/call (B7)
4. **Add comprehensive tests** if not present

---

## Files to Create/Modify

| File | Action | Description |
|------|--------|-------------|
| `deeptrail-gateway/app/mcp/permission_mapper.py` | **VERIFY/ENHANCE** | Ensure all MVP tools mapped |
| `deeptrail-gateway/tests/mcp/test_permission_mapper.py` | **CREATE** | Comprehensive tests |

---

## Implementation Details

### 1. Current Permission Mappings

The existing `PermissionMapper` class contains these mappings:

```python
TOOL_TO_PERMISSION: dict[str, str] = {
    # Notion tools
    "notion.search_pages": "notion:pages:search",
    "notion.read_page": "notion:pages:read",
    "notion.create_page": "notion:pages:create",
    "notion.update_page": "notion:pages:update",
    "notion.delete_page": "notion:pages:delete",
    "notion.list_databases": "notion:databases:list",
    "notion.query_database": "notion:databases:query",
    
    # Slack tools
    "slack.search_messages": "slack:messages:search",
    "slack.send_message": "slack:messages:send",
    "slack.list_channels": "slack:channels:list",
    "slack.join_channel": "slack:channels:join",
    "slack.post_reaction": "slack:reactions:write",
    "slack.list_users": "slack:users:list",
    
    # HubSpot tools
    "hubspot.get_contact": "hubspot:contacts:read",
    "hubspot.create_contact": "hubspot:contacts:create",
    "hubspot.update_contact": "hubspot:contacts:update",
    "hubspot.list_contacts": "hubspot:contacts:list",
    "hubspot.list_deals": "hubspot:deals:list",
    "hubspot.create_deal": "hubspot:deals:create",
    "hubspot.update_deal": "hubspot:deals:update",
}
```

### 2. Key Methods to Verify

```python
class PermissionMapper:
    
    @classmethod
    def get_permission(cls, tool_name: str) -> str | None:
        """Get the permission string required for a tool."""
        return cls.TOOL_TO_PERMISSION.get(tool_name)
    
    @classmethod
    def infer_permission(cls, tool_name: str) -> str | None:
        """
        Infer permission from tool name if not in static mapping.
        Uses convention: {backend}.{action}_{resource} → {backend}:{resource}:{action}
        """
        # First check static mapping
        static = cls.get_permission(tool_name)
        if static:
            return static
        
        # Try to infer: backend.action_resource → backend:resource:action
        match = re.match(r"^([^.]+)\.([^_]+)_(.+)$", tool_name)
        if match:
            backend, action, resource = match.groups()
            return f"{backend}:{resource}:{action}"
        
        return None
    
    @classmethod
    def is_tool_permitted(
        cls,
        tool_name: str,
        delegated_permissions: list[str],
    ) -> bool:
        """
        Check if a tool is allowed by delegated permissions.
        Security: Unknown tools are denied by default (fail-closed).
        """
        required_permission = cls.get_permission(tool_name)
        
        if required_permission is None:
            # Unknown tool - deny by default (fail-closed)
            return False
        
        return required_permission in delegated_permissions
    
    @classmethod
    def filter_tools(
        cls,
        tools: list[dict[str, Any]],
        delegated_permissions: list[str],
    ) -> list[dict[str, Any]]:
        """Filter a list of tools to only those permitted."""
        return [
            tool for tool in tools
            if cls.is_tool_permitted(tool.get("name", ""), delegated_permissions)
        ]
```

### 3. Integration Points

Verify these files use `PermissionMapper`:

**`tools_list.py` (B6):**
```python
from app.mcp.permission_mapper import PermissionMapper

# In tools/list handler:
permitted_tools = PermissionMapper.filter_tools(
    all_tools,
    agent_context.delegated_permissions
)
```

**`tools_call.py` (B7):**
```python
from app.mcp.permission_mapper import PermissionMapper

# In tools/call handler:
if not PermissionMapper.is_tool_permitted(
    tool_name,
    agent_context.delegated_permissions
):
    raise PermissionDeniedError(
        tool=tool_name,
        required=PermissionMapper.get_permission(tool_name),
    )
```

---

## Acceptance Criteria

### Mapping Criteria

- [ ] `notion.search_pages` → `notion:pages:search`
- [ ] `notion.read_page` → `notion:pages:read`
- [ ] `slack.send_message` → `slack:messages:send`
- [ ] `slack.list_channels` → `slack:channels:list`
- [ ] `hubspot.get_contact` → `hubspot:contacts:read`
- [ ] `hubspot.list_deals` → `hubspot:deals:list`
- [ ] All MVP backend tools have mappings

### Behavior Criteria

- [ ] `get_permission()` returns correct permission string
- [ ] `get_permission()` returns `None` for unknown tools
- [ ] `is_tool_permitted()` returns `True` when permission in list
- [ ] `is_tool_permitted()` returns `False` when permission missing
- [ ] `is_tool_permitted()` returns `False` for unknown tools (fail-closed)
- [ ] `filter_tools()` returns only permitted tools
- [ ] `infer_permission()` handles convention: `{backend}.{action}_{resource}`

### Security Criteria

- [ ] Unknown tools denied by default (fail-closed)
- [ ] Permission checks logged for audit
- [ ] No information leakage about available permissions

### Integration Criteria

- [ ] `tools/list` handler (B6) uses `filter_tools()`
- [ ] `tools/call` handler (B7) uses `is_tool_permitted()`
- [ ] Works with `AgentContext.delegated_permissions` from JWT

### Test Criteria

- [ ] Test all static mappings
- [ ] Test `get_permission()` for known and unknown tools
- [ ] Test `is_tool_permitted()` positive and negative cases
- [ ] Test `filter_tools()` with various permission sets
- [ ] Test `infer_permission()` with convention
- [ ] Test fail-closed behavior for unknown tools
- [ ] All tests pass with `pytest tests/mcp/test_permission_mapper.py`

---

## Test Cases

Create `deeptrail-gateway/tests/mcp/test_permission_mapper.py`:

```python
"""Tests for tool→permission mapper (C4)."""

import pytest
from app.mcp.permission_mapper import PermissionMapper


class TestGetPermission:
    """Tests for get_permission method."""
    
    def test_notion_search_pages(self):
        """Test Notion search_pages mapping."""
        assert PermissionMapper.get_permission("notion.search_pages") == "notion:pages:search"
    
    def test_notion_read_page(self):
        """Test Notion read_page mapping."""
        assert PermissionMapper.get_permission("notion.read_page") == "notion:pages:read"
    
    def test_slack_send_message(self):
        """Test Slack send_message mapping."""
        assert PermissionMapper.get_permission("slack.send_message") == "slack:messages:send"
    
    def test_slack_list_channels(self):
        """Test Slack list_channels mapping."""
        assert PermissionMapper.get_permission("slack.list_channels") == "slack:channels:list"
    
    def test_hubspot_get_contact(self):
        """Test HubSpot get_contact mapping."""
        assert PermissionMapper.get_permission("hubspot.get_contact") == "hubspot:contacts:read"
    
    def test_hubspot_list_deals(self):
        """Test HubSpot list_deals mapping."""
        assert PermissionMapper.get_permission("hubspot.list_deals") == "hubspot:deals:list"
    
    def test_unknown_tool(self):
        """Test unknown tool returns None."""
        assert PermissionMapper.get_permission("unknown.tool") is None
    
    def test_empty_string(self):
        """Test empty string returns None."""
        assert PermissionMapper.get_permission("") is None


class TestInferPermission:
    """Tests for infer_permission method."""
    
    def test_static_mapping_takes_precedence(self):
        """Test static mapping is preferred over inference."""
        # This has a static mapping
        result = PermissionMapper.infer_permission("notion.search_pages")
        assert result == "notion:pages:search"
    
    def test_infer_from_convention(self):
        """Test inference from naming convention."""
        # Not in static mapping, should infer
        result = PermissionMapper.infer_permission("github.list_repos")
        assert result == "github:repos:list"
    
    def test_infer_create_action(self):
        """Test inference for create action."""
        result = PermissionMapper.infer_permission("jira.create_issues")
        assert result == "jira:issues:create"
    
    def test_cannot_infer(self):
        """Test returns None when cannot infer."""
        result = PermissionMapper.infer_permission("invalid_format")
        assert result is None


class TestIsToolPermitted:
    """Tests for is_tool_permitted method."""
    
    def test_permitted_tool(self):
        """Test tool is permitted when permission in list."""
        permissions = ["notion:pages:search", "slack:channels:list"]
        assert PermissionMapper.is_tool_permitted("notion.search_pages", permissions) is True
    
    def test_not_permitted_tool(self):
        """Test tool is not permitted when permission missing."""
        permissions = ["notion:pages:search"]
        assert PermissionMapper.is_tool_permitted("notion.create_page", permissions) is False
    
    def test_unknown_tool_denied(self):
        """Test unknown tools are denied (fail-closed)."""
        permissions = ["notion:pages:search", "slack:messages:send"]
        assert PermissionMapper.is_tool_permitted("unknown.tool", permissions) is False
    
    def test_empty_permissions(self):
        """Test with empty permission list."""
        assert PermissionMapper.is_tool_permitted("notion.search_pages", []) is False
    
    def test_multiple_permissions(self):
        """Test with multiple permissions."""
        permissions = [
            "notion:pages:search",
            "notion:pages:read",
            "slack:messages:send",
        ]
        assert PermissionMapper.is_tool_permitted("notion.search_pages", permissions) is True
        assert PermissionMapper.is_tool_permitted("notion.read_page", permissions) is True
        assert PermissionMapper.is_tool_permitted("slack.send_message", permissions) is True
        assert PermissionMapper.is_tool_permitted("hubspot.get_contact", permissions) is False


class TestFilterTools:
    """Tests for filter_tools method."""
    
    def test_filter_basic(self):
        """Test basic filtering."""
        tools = [
            {"name": "notion.search_pages", "description": "Search"},
            {"name": "notion.create_page", "description": "Create"},
            {"name": "slack.send_message", "description": "Send"},
        ]
        permissions = ["notion:pages:search"]
        
        filtered = PermissionMapper.filter_tools(tools, permissions)
        
        assert len(filtered) == 1
        assert filtered[0]["name"] == "notion.search_pages"
    
    def test_filter_multiple_permitted(self):
        """Test filtering with multiple permitted tools."""
        tools = [
            {"name": "notion.search_pages"},
            {"name": "notion.read_page"},
            {"name": "slack.send_message"},
            {"name": "hubspot.get_contact"},
        ]
        permissions = ["notion:pages:search", "notion:pages:read", "slack:messages:send"]
        
        filtered = PermissionMapper.filter_tools(tools, permissions)
        
        assert len(filtered) == 3
        names = [t["name"] for t in filtered]
        assert "notion.search_pages" in names
        assert "notion.read_page" in names
        assert "slack.send_message" in names
        assert "hubspot.get_contact" not in names
    
    def test_filter_empty_permissions(self):
        """Test filtering with no permissions."""
        tools = [
            {"name": "notion.search_pages"},
            {"name": "slack.send_message"},
        ]
        
        filtered = PermissionMapper.filter_tools(tools, [])
        
        assert len(filtered) == 0
    
    def test_filter_empty_tools(self):
        """Test filtering with no tools."""
        permissions = ["notion:pages:search"]
        
        filtered = PermissionMapper.filter_tools([], permissions)
        
        assert len(filtered) == 0
    
    def test_filter_preserves_tool_structure(self):
        """Test that filtering preserves tool structure."""
        tools = [
            {
                "name": "notion.search_pages",
                "description": "Search pages in Notion",
                "inputSchema": {"type": "object", "properties": {"query": {"type": "string"}}},
            }
        ]
        permissions = ["notion:pages:search"]
        
        filtered = PermissionMapper.filter_tools(tools, permissions)
        
        assert len(filtered) == 1
        assert filtered[0]["description"] == "Search pages in Notion"
        assert filtered[0]["inputSchema"]["type"] == "object"


class TestHelperMethods:
    """Tests for helper methods."""
    
    def test_get_all_permissions(self):
        """Test getting all known permissions."""
        permissions = PermissionMapper.get_all_permissions()
        
        assert "notion:pages:search" in permissions
        assert "slack:messages:send" in permissions
        assert "hubspot:contacts:read" in permissions
    
    def test_get_all_tools(self):
        """Test getting all known tools."""
        tools = PermissionMapper.get_all_tools()
        
        assert "notion.search_pages" in tools
        assert "slack.send_message" in tools
        assert "hubspot.get_contact" in tools
    
    def test_get_backend_permissions(self):
        """Test getting permissions for a backend."""
        notion_perms = PermissionMapper.get_backend_permissions("notion")
        
        assert all(p.startswith("notion:") for p in notion_perms)
        assert "notion:pages:search" in notion_perms
    
    def test_get_backend_tools(self):
        """Test getting tools for a backend."""
        slack_tools = PermissionMapper.get_backend_tools("slack")
        
        assert all(t.startswith("slack.") for t in slack_tools)
        assert "slack.send_message" in slack_tools
    
    def test_get_all_tools_for_permission(self):
        """Test getting tools that require a permission."""
        tools = PermissionMapper.get_all_tools_for_permission("notion:pages:search")
        
        assert "notion.search_pages" in tools


class TestDynamicMapping:
    """Tests for dynamic mapping methods."""
    
    def test_add_mapping(self):
        """Test adding a new mapping."""
        PermissionMapper.add_mapping("test.custom_tool", "test:custom:action")
        
        assert PermissionMapper.get_permission("test.custom_tool") == "test:custom:action"
        
        # Cleanup
        PermissionMapper.remove_mapping("test.custom_tool")
    
    def test_remove_mapping(self):
        """Test removing a mapping."""
        PermissionMapper.add_mapping("test.remove_me", "test:remove:me")
        
        result = PermissionMapper.remove_mapping("test.remove_me")
        
        assert result is True
        assert PermissionMapper.get_permission("test.remove_me") is None
    
    def test_remove_nonexistent(self):
        """Test removing non-existent mapping."""
        result = PermissionMapper.remove_mapping("nonexistent.tool")
        
        assert result is False
```

---

## Post-Conditions

After completing this task:

- [ ] All MVP backend tools have permission mappings
- [ ] `tools/list` (B6) filters tools by permissions
- [ ] `tools/call` (B7) validates permissions before execution
- [ ] Unknown tools are denied by default (fail-closed)
- [ ] C5 (Permission Filter) can use mapper for filtering
- [ ] C6 (Delegation Validator) can use mapper for validation
- [ ] All unit tests pass

---

## References

- **Design Doc Section**: 2.6 Steps 7-9 (Tool Discovery, Execution, Denial)
- **Related Tasks**:
  - [WS-B4: Namespace Prefixer](./WS-B4-namespace-prefixer.md) - Provides namespaced tool names
  - [WS-B6: Tools List Handler](./WS-B6-tools-list-handler.md) - Uses filter_tools()
  - [WS-B7: Tools Call Handler](./WS-B7-tools-call-handler.md) - Uses is_tool_permitted()
- **Downstream Tasks**:
  - [WS-C5: Permission Filter](./WS-C5-permission-filter.md) - Middleware using mapper
  - [WS-C6: Delegation Validator](./WS-C6-delegation-validator.md) - Validates permissions
- **Existing Code**:
  - `deeptrail-gateway/app/mcp/permission_mapper.py` - Current implementation

---

## Notes

- This task is mostly **verification** as the implementation already exists
- The existing implementation follows fail-closed security (unknown tools denied)
- `infer_permission()` provides fallback for tools not in static mapping
- In production, mappings could be loaded from configuration or database
- Permission format `{backend}:{resource}:{action}` aligns with industry standards
- The mapper is designed to be extended when new backends are added (D3, D4, D5)
