# Task: WS-B6 Implement tools/list Handler

---

## Metadata

| Field | Value |
|-------|-------|
| **Status** | `ready` |
| **Design Doc** | [deepsecure-virtual-mcp-server-mvp.md](../../../design/internal/markdowns/deepsecure-virtual-mcp-server-mvp.md) |
| **Workstream** | WS-B: Gateway MCP Core |
| **Dependencies** | B3 (MCP Session tracking), B5 (Tool schema cache) |
| **Blocked By** | None (B3, B5 are complete ✅) |
| **Assigned** | - |
| **Created** | January 30, 2026 |
| **Estimated Complexity** | `M` (2-4 hours) |
| **Batch** | 4 |

---

## Validation Mapping

| Mapping | Value |
|---------|-------|
| **Validates Demo** | Demo 1: Unified Connection, Demo 2: Filtered Visibility |
| **Validates User Journey Step** | Step 7: Agent Discovers Tools |

---

## Pre-Conditions

Before starting this task, ensure:

- [x] B3 (MCP Session tracking) is complete
- [x] B5 (Tool schema cache) is complete
- [ ] `deeptrail-gateway/` service structure exists
- [ ] MCP Session Manager can be imported
- [ ] Tool Schema Cache can be imported
- [ ] Namespace Prefixer (B4) can be imported

---

## Task Description

Implement the MCP `tools/list` request handler that returns aggregated, namespaced, and **filtered** tools to the agent. This is the core handler enabling Step 7 of Sarah's journey where the agent discovers only the tools it has been delegated access to.

### Context

From the MVP design (Section 2.8 - Step 7: Agent Discovers Tools):

```
Gateway Processing for tools/list:

1. AGGREGATE from backends (what backends offer):
   - Notion: search_pages, read_page, create_page, ...
   - Slack: search_messages, send_message, list_channels, ...

2. NAMESPACE PREFIX (avoid collisions):
   - search_pages → notion.search_pages
   - search_messages → slack.search_messages

3. FILTER by agent's delegated permissions:
   - notion.search_pages → notion:pages:search ✓ INCLUDE
   - notion.create_page → notion:pages:create ✗ NOT DELEGATED

4. RETURN filtered, namespaced tools to agent
```

**Key MVP Demonstration**: Agent sees 4 tools, not 20+. This is the core value prop.

### Response Format (MCP Protocol)

```json
{
  "jsonrpc": "2.0",
  "id": 2,
  "result": {
    "tools": [
      {
        "name": "notion.search_pages",
        "description": "[Notion] Search pages in workspace",
        "inputSchema": {
          "type": "object",
          "properties": {
            "query": {"type": "string", "description": "Search query"}
          },
          "required": ["query"]
        }
      },
      {
        "name": "slack.list_channels",
        "description": "[Slack] List available channels",
        "inputSchema": {
          "type": "object",
          "properties": {}
        }
      }
    ]
  }
}
```

### Technical Notes

- Handler receives parsed MCP request from protocol layer (B1)
- Must extract agent session from request context (JWT validated by middleware)
- Uses MCP Session Manager (B3) to get connected backend sessions
- Uses Tool Schema Cache (B5) to get backend tool schemas
- Uses Namespace Prefixer (B4) to apply `{backend}.{tool}` naming
- Must filter tools based on `delegated_permissions` from agent session
- Tool→Permission mapping required (e.g., `notion.search_pages` → `notion:pages:search`)

---

## Files to Create/Modify

| File | Action | Description |
|------|--------|-------------|
| `deeptrail-gateway/gateway/mcp/handlers/tools_list.py` | **CREATE** | tools/list request handler |
| `deeptrail-gateway/gateway/mcp/handlers/__init__.py` | **MODIFY** | Export handler |
| `deeptrail-gateway/gateway/mcp/permission_mapper.py` | **CREATE** | Tool→Permission mapping |
| `deeptrail-gateway/tests/mcp/handlers/test_tools_list.py` | **CREATE** | Unit tests |

---

## Implementation Details

### 1. Permission Mapper (`deeptrail-gateway/gateway/mcp/permission_mapper.py`)

```python
"""Tool to Permission mapping for Virtual MCP Server.

Maps MCP tool names to permission strings for filtering.

Convention:
- Tool name: {backend}.{operation}
- Permission: {backend}:{resource}:{action}

Examples:
- notion.search_pages → notion:pages:search
- slack.send_message → slack:messages:send
"""

from typing import Dict, Optional
import re


class PermissionMapper:
    """
    Maps tool names to permission strings.
    
    Used by tools/list to filter tools by delegated permissions,
    and by tools/call to validate permission before execution.
    """
    
    # Static mapping for MVP backends
    # Production: Load from configuration or database
    TOOL_TO_PERMISSION: Dict[str, str] = {
        # Notion tools
        "notion.search_pages": "notion:pages:search",
        "notion.read_page": "notion:pages:read",
        "notion.create_page": "notion:pages:create",
        "notion.update_page": "notion:pages:update",
        "notion.delete_page": "notion:pages:delete",
        
        # Slack tools
        "slack.search_messages": "slack:messages:search",
        "slack.send_message": "slack:messages:send",
        "slack.list_channels": "slack:channels:list",
        "slack.join_channel": "slack:channels:join",
        "slack.post_reaction": "slack:reactions:write",
        
        # HubSpot tools (Phase 2)
        "hubspot.get_contact": "hubspot:contacts:read",
        "hubspot.update_contact": "hubspot:contacts:update",
        "hubspot.list_deals": "hubspot:deals:list",
        "hubspot.create_deal": "hubspot:deals:create",
    }
    
    @classmethod
    def get_permission(cls, tool_name: str) -> Optional[str]:
        """
        Get the permission string required for a tool.
        
        Args:
            tool_name: Namespaced tool name (e.g., "notion.search_pages")
            
        Returns:
            Permission string (e.g., "notion:pages:search") or None if unknown
        """
        return cls.TOOL_TO_PERMISSION.get(tool_name)
    
    @classmethod
    def infer_permission(cls, tool_name: str) -> Optional[str]:
        """
        Infer permission from tool name if not in static mapping.
        
        Convention: {backend}.{action}_{resource} → {backend}:{resource}:{action}
        
        Args:
            tool_name: Namespaced tool name
            
        Returns:
            Inferred permission string or None
        """
        # First check static mapping
        if tool_name in cls.TOOL_TO_PERMISSION:
            return cls.TOOL_TO_PERMISSION[tool_name]
        
        # Try to infer
        # Pattern: backend.action_resource or backend.resource_action
        match = re.match(r'^([^.]+)\.([^_]+)_(.+)$', tool_name)
        if match:
            backend, action, resource = match.groups()
            return f"{backend}:{resource}:{action}"
        
        return None
    
    @classmethod
    def tool_requires_permission(
        cls,
        tool_name: str,
        delegated_permissions: list
    ) -> bool:
        """
        Check if tool is allowed by delegated permissions.
        
        Args:
            tool_name: Namespaced tool name
            delegated_permissions: List of permission strings agent has
            
        Returns:
            True if tool is permitted, False otherwise
        """
        required_permission = cls.get_permission(tool_name)
        
        if required_permission is None:
            # Unknown tool - deny by default (fail-closed)
            return False
        
        return required_permission in delegated_permissions
    
    @classmethod
    def filter_tools_by_permissions(
        cls,
        tools: list,
        delegated_permissions: list
    ) -> list:
        """
        Filter a list of tools to only those permitted.
        
        Args:
            tools: List of tool schemas (with 'name' field)
            delegated_permissions: List of permission strings
            
        Returns:
            Filtered list of permitted tools
        """
        return [
            tool for tool in tools
            if cls.tool_requires_permission(tool.get("name", ""), delegated_permissions)
        ]
```

### 2. Tools List Handler (`deeptrail-gateway/gateway/mcp/handlers/tools_list.py`)

```python
"""MCP tools/list request handler for Virtual MCP Server.

Handles the tools/list MCP method by:
1. Aggregating tools from all connected backends
2. Applying namespace prefixes
3. Filtering by agent's delegated permissions
4. Returning filtered tool list

This is the core handler demonstrating the "filtered visibility" value prop.
"""

from typing import Dict, Any, List, Optional
import logging

from gateway.mcp.session_manager import MCPSessionManager
from gateway.mcp.tool_cache import ToolSchemaCache
from gateway.mcp.namespace import NamespacePrefixer
from gateway.mcp.permission_mapper import PermissionMapper


logger = logging.getLogger(__name__)


class ToolsListHandler:
    """
    Handler for MCP tools/list requests.
    
    Demonstrates key Virtual MCP Server capabilities:
    - Unified view: Agent sees tools from multiple backends as one list
    - Namespacing: Tools prefixed with backend (notion.search_pages)
    - Filtering: Only delegated tools visible to agent
    
    Example flow:
    1. Agent calls tools/list
    2. Handler gets agent session from context
    3. For each connected backend:
       a. Fetch tools from cache (or backend if cache miss)
       b. Apply namespace prefix
    4. Filter aggregated tools by delegated_permissions
    5. Return filtered list
    """
    
    def __init__(
        self,
        session_manager: MCPSessionManager,
        tool_cache: ToolSchemaCache,
        namespace_prefixer: NamespacePrefixer,
        permission_mapper: Optional[PermissionMapper] = None
    ):
        """
        Initialize ToolsListHandler.
        
        Args:
            session_manager: For accessing MCP backend sessions
            tool_cache: For cached tool schemas
            namespace_prefixer: For applying {backend}.{tool} naming
            permission_mapper: For tool→permission mapping (default: PermissionMapper)
        """
        self.session_manager = session_manager
        self.tool_cache = tool_cache
        self.namespace_prefixer = namespace_prefixer
        self.permission_mapper = permission_mapper or PermissionMapper
    
    async def handle(
        self,
        request: Dict[str, Any],
        context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Handle MCP tools/list request.
        
        Args:
            request: Parsed MCP JSON-RPC request
            context: Request context containing:
                - agent_session: Validated AgentSession
                - mcp_sessions: Dict of backend MCP sessions
                
        Returns:
            MCP JSON-RPC response with filtered tools
        """
        request_id = request.get("id")
        agent_session = context.get("agent_session")
        
        if not agent_session:
            return self._error_response(
                request_id,
                -32600,
                "Invalid Request: No agent session"
            )
        
        # Get agent's delegated permissions
        delegated_permissions = agent_session.scoped_permissions or []
        
        logger.info(
            f"tools/list request from agent {agent_session.agent_id}, "
            f"permissions: {delegated_permissions}"
        )
        
        try:
            # Step 1: Aggregate tools from all backends
            aggregated_tools = await self._aggregate_tools(context)
            
            # Step 2: Filter by delegated permissions
            filtered_tools = self.permission_mapper.filter_tools_by_permissions(
                aggregated_tools,
                delegated_permissions
            )
            
            logger.info(
                f"Returning {len(filtered_tools)}/{len(aggregated_tools)} tools "
                f"to agent {agent_session.agent_id}"
            )
            
            # Step 3: Build response
            return self._success_response(request_id, filtered_tools)
            
        except Exception as e:
            logger.error(f"Error handling tools/list: {e}", exc_info=True)
            return self._error_response(
                request_id,
                -32603,
                f"Internal error: {str(e)}"
            )
    
    async def _aggregate_tools(self, context: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Aggregate tools from all connected backend MCP sessions.
        
        For each backend:
        1. Get cached tool schemas (or fetch if cache miss)
        2. Apply namespace prefix to each tool
        3. Optionally modify description to include backend name
        
        Args:
            context: Request context with mcp_sessions
            
        Returns:
            List of namespaced tool schemas
        """
        mcp_sessions = context.get("mcp_sessions", {})
        aggregated = []
        
        for backend_id, mcp_session in mcp_sessions.items():
            # Get tools from cache
            backend_tools = await self.tool_cache.get_tools(backend_id)
            
            if backend_tools is None:
                logger.warning(f"No tools cached for backend {backend_id}")
                continue
            
            # Apply namespace prefix to each tool
            for tool in backend_tools:
                namespaced_tool = self._namespace_tool(backend_id, tool)
                aggregated.append(namespaced_tool)
        
        return aggregated
    
    def _namespace_tool(
        self,
        backend_id: str,
        tool: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Apply namespace prefix to a tool schema.
        
        Args:
            backend_id: Backend identifier (e.g., "notion")
            tool: Original tool schema
            
        Returns:
            Tool schema with namespaced name and modified description
        """
        original_name = tool.get("name", "")
        namespaced_name = self.namespace_prefixer.prefix(backend_id, original_name)
        
        # Modify description to include backend context
        original_desc = tool.get("description", "")
        backend_label = backend_id.capitalize()
        enhanced_desc = f"[{backend_label}] {original_desc}"
        
        return {
            **tool,
            "name": namespaced_name,
            "description": enhanced_desc,
            "_original_name": original_name,  # Keep for routing
            "_backend": backend_id            # Keep for routing
        }
    
    def _success_response(
        self,
        request_id: Any,
        tools: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        Build successful MCP tools/list response.
        
        Args:
            request_id: Original request ID
            tools: List of filtered tool schemas
            
        Returns:
            MCP JSON-RPC response
        """
        # Remove internal fields before sending
        clean_tools = [
            {k: v for k, v in tool.items() if not k.startswith("_")}
            for tool in tools
        ]
        
        return {
            "jsonrpc": "2.0",
            "id": request_id,
            "result": {
                "tools": clean_tools
            }
        }
    
    def _error_response(
        self,
        request_id: Any,
        code: int,
        message: str
    ) -> Dict[str, Any]:
        """
        Build MCP error response.
        
        Args:
            request_id: Original request ID
            code: JSON-RPC error code
            message: Error message
            
        Returns:
            MCP JSON-RPC error response
        """
        return {
            "jsonrpc": "2.0",
            "id": request_id,
            "error": {
                "code": code,
                "message": message
            }
        }


# Factory function for handler registration
def create_tools_list_handler(
    session_manager: MCPSessionManager,
    tool_cache: ToolSchemaCache,
    namespace_prefixer: NamespacePrefixer
) -> ToolsListHandler:
    """
    Create a configured ToolsListHandler.
    
    Args:
        session_manager: MCP session manager instance
        tool_cache: Tool schema cache instance
        namespace_prefixer: Namespace prefixer instance
        
    Returns:
        Configured ToolsListHandler
    """
    return ToolsListHandler(
        session_manager=session_manager,
        tool_cache=tool_cache,
        namespace_prefixer=namespace_prefixer
    )
```

### 3. Update `__init__.py`

```python
# Add to deeptrail-gateway/gateway/mcp/handlers/__init__.py
from .tools_list import ToolsListHandler, create_tools_list_handler

__all__ = [
    # ... existing exports ...
    "ToolsListHandler",
    "create_tools_list_handler",
]
```

```python
# Add to deeptrail-gateway/gateway/mcp/__init__.py
from .permission_mapper import PermissionMapper

__all__ = [
    # ... existing exports ...
    "PermissionMapper",
]
```

---

## Acceptance Criteria

### Aggregation Criteria

- [ ] Handler fetches tools from all connected backend sessions
- [ ] Tools from multiple backends are combined into single list
- [ ] Cache miss for a backend logs warning but doesn't fail request
- [ ] Empty backend (no tools) is handled gracefully

### Namespace Criteria

- [ ] All tool names prefixed with `{backend}.` (e.g., `notion.search_pages`)
- [ ] Tool descriptions enhanced with `[{Backend}]` prefix
- [ ] Original name preserved in `_original_name` for routing
- [ ] Backend ID preserved in `_backend` for routing

### Filtering Criteria

- [ ] Only tools matching delegated permissions are returned
- [ ] Tool→Permission mapping works for all MVP tools
- [ ] Unknown tools are denied (fail-closed)
- [ ] Empty permissions list returns empty tools list

### Permission Mapping Criteria

- [ ] `PermissionMapper.get_permission()` returns correct permission
- [ ] `PermissionMapper.tool_requires_permission()` validates correctly
- [ ] `PermissionMapper.filter_tools_by_permissions()` filters list
- [ ] All MVP tools have mappings (Notion, Slack, HubSpot)

### Protocol Criteria

- [ ] Response follows MCP JSON-RPC format
- [ ] `result.tools` is an array of tool objects
- [ ] Each tool has `name`, `description`, `inputSchema`
- [ ] Internal fields (`_original_name`, `_backend`) stripped from response
- [ ] Error responses use correct JSON-RPC error format

### Integration Criteria

- [ ] Handler uses MCPSessionManager from B3
- [ ] Handler uses ToolSchemaCache from B5
- [ ] Handler uses NamespacePrefixer from B4
- [ ] Handler exported from `handlers/__init__.py`
- [ ] All tests pass

---

## Test Cases

Create `deeptrail-gateway/tests/mcp/handlers/test_tools_list.py`:

```python
"""Tests for tools/list handler."""

import pytest
from unittest.mock import MagicMock, AsyncMock
from gateway.mcp.handlers.tools_list import ToolsListHandler
from gateway.mcp.permission_mapper import PermissionMapper


@pytest.fixture
def mock_session_manager():
    return MagicMock()


@pytest.fixture
def mock_tool_cache():
    cache = MagicMock()
    cache.get_tools = AsyncMock()
    return cache


@pytest.fixture
def mock_namespace_prefixer():
    prefixer = MagicMock()
    prefixer.prefix = lambda backend, name: f"{backend}.{name}"
    return prefixer


@pytest.fixture
def mock_agent_session():
    session = MagicMock()
    session.agent_id = "agent-sdr-001"
    session.scoped_permissions = [
        "notion:pages:search",
        "notion:pages:read",
        "slack:channels:list"
    ]
    return session


@pytest.fixture
def handler(mock_session_manager, mock_tool_cache, mock_namespace_prefixer):
    return ToolsListHandler(
        session_manager=mock_session_manager,
        tool_cache=mock_tool_cache,
        namespace_prefixer=mock_namespace_prefixer
    )


class TestToolsListHandler:
    """Test tools/list handler."""
    
    @pytest.mark.asyncio
    async def test_returns_filtered_tools(
        self, handler, mock_tool_cache, mock_agent_session
    ):
        """Test that only permitted tools are returned."""
        # Setup: Mock backend tools
        mock_tool_cache.get_tools.side_effect = [
            # Notion backend
            [
                {"name": "search_pages", "description": "Search pages"},
                {"name": "create_page", "description": "Create page"},  # NOT permitted
            ],
            # Slack backend
            [
                {"name": "list_channels", "description": "List channels"},
                {"name": "send_message", "description": "Send message"},  # NOT permitted
            ]
        ]
        
        context = {
            "agent_session": mock_agent_session,
            "mcp_sessions": {"notion": {}, "slack": {}}
        }
        
        request = {"jsonrpc": "2.0", "id": 1, "method": "tools/list"}
        
        # Execute
        response = await handler.handle(request, context)
        
        # Verify
        assert response["jsonrpc"] == "2.0"
        assert response["id"] == 1
        assert "error" not in response
        
        tools = response["result"]["tools"]
        tool_names = [t["name"] for t in tools]
        
        # Should include permitted tools
        assert "notion.search_pages" in tool_names
        assert "slack.list_channels" in tool_names
        
        # Should NOT include unpermitted tools
        assert "notion.create_page" not in tool_names
        assert "slack.send_message" not in tool_names
    
    @pytest.mark.asyncio
    async def test_namespaces_tools(
        self, handler, mock_tool_cache, mock_agent_session
    ):
        """Test that tools are namespaced with backend prefix."""
        mock_tool_cache.get_tools.return_value = [
            {"name": "search_pages", "description": "Search"}
        ]
        
        # Grant permission
        mock_agent_session.scoped_permissions = ["notion:pages:search"]
        
        context = {
            "agent_session": mock_agent_session,
            "mcp_sessions": {"notion": {}}
        }
        
        request = {"jsonrpc": "2.0", "id": 1, "method": "tools/list"}
        response = await handler.handle(request, context)
        
        tools = response["result"]["tools"]
        assert tools[0]["name"] == "notion.search_pages"
        assert "[Notion]" in tools[0]["description"]
    
    @pytest.mark.asyncio
    async def test_empty_permissions_returns_empty_list(
        self, handler, mock_tool_cache, mock_agent_session
    ):
        """Test that no permissions = no tools."""
        mock_tool_cache.get_tools.return_value = [
            {"name": "search_pages", "description": "Search"}
        ]
        
        mock_agent_session.scoped_permissions = []
        
        context = {
            "agent_session": mock_agent_session,
            "mcp_sessions": {"notion": {}}
        }
        
        request = {"jsonrpc": "2.0", "id": 1, "method": "tools/list"}
        response = await handler.handle(request, context)
        
        assert response["result"]["tools"] == []
    
    @pytest.mark.asyncio
    async def test_no_agent_session_returns_error(self, handler):
        """Test error when no agent session in context."""
        request = {"jsonrpc": "2.0", "id": 1, "method": "tools/list"}
        response = await handler.handle(request, {})
        
        assert "error" in response
        assert response["error"]["code"] == -32600
    
    @pytest.mark.asyncio
    async def test_internal_fields_stripped(
        self, handler, mock_tool_cache, mock_agent_session
    ):
        """Test that _original_name and _backend are not in response."""
        mock_tool_cache.get_tools.return_value = [
            {"name": "search_pages", "description": "Search"}
        ]
        mock_agent_session.scoped_permissions = ["notion:pages:search"]
        
        context = {
            "agent_session": mock_agent_session,
            "mcp_sessions": {"notion": {}}
        }
        
        request = {"jsonrpc": "2.0", "id": 1, "method": "tools/list"}
        response = await handler.handle(request, context)
        
        tool = response["result"]["tools"][0]
        assert "_original_name" not in tool
        assert "_backend" not in tool


class TestPermissionMapper:
    """Test permission mapper."""
    
    def test_get_permission_known_tool(self):
        """Test getting permission for known tool."""
        perm = PermissionMapper.get_permission("notion.search_pages")
        assert perm == "notion:pages:search"
    
    def test_get_permission_unknown_tool(self):
        """Test getting permission for unknown tool."""
        perm = PermissionMapper.get_permission("unknown.tool")
        assert perm is None
    
    def test_tool_requires_permission_granted(self):
        """Test permission check when granted."""
        permissions = ["notion:pages:search", "slack:channels:list"]
        assert PermissionMapper.tool_requires_permission(
            "notion.search_pages", permissions
        ) is True
    
    def test_tool_requires_permission_denied(self):
        """Test permission check when not granted."""
        permissions = ["notion:pages:search"]
        assert PermissionMapper.tool_requires_permission(
            "notion.create_page", permissions
        ) is False
    
    def test_filter_tools_by_permissions(self):
        """Test filtering tool list."""
        tools = [
            {"name": "notion.search_pages"},
            {"name": "notion.create_page"},
            {"name": "slack.list_channels"},
        ]
        permissions = ["notion:pages:search", "slack:channels:list"]
        
        filtered = PermissionMapper.filter_tools_by_permissions(tools, permissions)
        
        names = [t["name"] for t in filtered]
        assert "notion.search_pages" in names
        assert "slack.list_channels" in names
        assert "notion.create_page" not in names
```

---

## Post-Conditions

After completing this task:

- [ ] ToolsListHandler is available for import
- [ ] PermissionMapper is available for import
- [ ] Agents can call tools/list and receive filtered tools
- [ ] B8 (Tool Aggregator) is unblocked
- [ ] Demo 1 (Unified Connection) can be demonstrated
- [ ] Demo 2 (Filtered Visibility) can be demonstrated
- [ ] All unit tests pass

---

## References

- **Design Doc Section**: 2.8 Step 7: Agent Discovers Tools
- **MCP Protocol**: [tools/list method](https://modelcontextprotocol.io/specification)
- **Related Tasks**:
  - [WS-B3: MCP Session Tracking](./WS-B3-mcp-session-tracking.md)
  - [WS-B4: Namespace Prefixer](./WS-B4-namespace-prefixer.md)
  - [WS-B5: Tool Schema Cache](./WS-B5-tool-schema-cache.md)
- **Downstream Tasks**:
  - [WS-B8: Tool Aggregator](./WS-B8-tool-aggregator.md)
  - [WS-C5: Permission Filter](./WS-C5-permission-filter.md)

---

## Notes

- The `_original_name` and `_backend` fields are internal metadata for routing in tools/call
- Permission mapping is static for MVP; production should load from configuration
- Fail-closed: Unknown tools are denied by default
- This handler is the core demonstration of the "filtered visibility" value proposition
