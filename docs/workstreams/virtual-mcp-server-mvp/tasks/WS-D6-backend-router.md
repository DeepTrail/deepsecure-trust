# Task: WS-D6 Implement Backend Router

---

## Metadata

| Field | Value |
|-------|-------|
| **Status** | `ready` |
| **Design Doc** | [deepsecure-virtual-mcp-server-mvp.md](../../../design/internal/markdowns/deepsecure-virtual-mcp-server-mvp.md) |
| **Workstream** | WS-D: Backend Connectors |
| **Dependencies** | D1 (Connection Manager) ✅, B7 (tools/call handler) ✅ |
| **Blocked By** | None (D1, B7 complete) |
| **Assigned** | - |
| **Created** | February 5, 2026 |
| **Estimated Complexity** | `M` (2-4 hours) |
| **Batch** | 5 |
| **Target Worktree** | `vmcp-gateway` |

---

## Validation Mapping

| Mapping | Value |
|---------|-------|
| **Validates Demo** | Demo 1: Unified Connection, Demo 3: Delegation Execution |
| **Validates User Journey Step** | Step 8: Agent Executes Task |

---

## Pre-Conditions

Before starting this task, ensure:

- [x] D1 (Backend Connection Manager) is complete
- [x] D2 (Base MCP Client) is complete
- [x] B7 (tools/call handler) is complete
- [x] B4 (Namespace Prefixer) is complete
- [ ] D3, D4, D5 backend clients available (or use GenericMCPClient)

---

## Task Description

Implement the backend router that routes MCP `tools/call` requests to the appropriate backend MCP client based on the tool's namespace prefix. This is the central routing component that enables the gateway to proxy requests to multiple backend MCP servers.

### Context

From the MVP design (Section 2.6 - Step 8: Agent Executes Task):

```
When an agent calls a tool:
1. Agent sends: tools/call("notion.search_pages", {...})
2. Gateway extracts namespace: "notion"
3. Router finds NotionMCPClient for "notion"
4. Router forwards: tools/call("search_pages", {...})
5. Backend processes and returns result
6. Router returns result to agent

Routing Flow:
┌─────────────────────────────────────────────────────────────────┐
│                      Backend Router                              │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│   tools/call("notion.search_pages", {...})                      │
│                    │                                             │
│                    ▼                                             │
│   ┌───────────────────────────────┐                              │
│   │ Extract namespace: "notion"   │                              │
│   └───────────────────────────────┘                              │
│                    │                                             │
│                    ▼                                             │
│   ┌───────────────────────────────┐                              │
│   │ Find client for "notion"      │                              │
│   └───────────────────────────────┘                              │
│                    │                                             │
│       ┌────────────┼────────────┐                                │
│       ▼            ▼            ▼                                │
│  ┌─────────┐  ┌─────────┐  ┌─────────┐                          │
│  │ Notion  │  │ Slack   │  │ HubSpot │                          │
│  │ Client  │  │ Client  │  │ Client  │                          │
│  └─────────┘  └─────────┘  └─────────┘                          │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

---

## Files to Create/Modify

| File | Action | Description |
|------|--------|-------------|
| `deeptrail-gateway/app/backends/router.py` | **CREATE** | Backend router implementation |
| `deeptrail-gateway/app/backends/__init__.py` | **MODIFY** | Export BackendRouter |
| `deeptrail-gateway/tests/backends/test_router.py` | **CREATE** | Unit tests |

---

## Implementation Details

### 1. Backend Router

Create `deeptrail-gateway/app/backends/router.py`:

```python
"""
Backend Router for Virtual MCP Server.

Routes tools/call requests to the appropriate backend MCP client based on
the tool's namespace prefix. This enables the gateway to proxy requests
to multiple backend MCP servers through a unified interface.

Architecture:
- Extracts namespace from tool name (e.g., "notion.search_pages" → "notion")
- Maintains registry of backend_id → MCP client mappings
- Forwards tools/call to appropriate client with stripped tool name
- Aggregates tools/list across all registered backends

Usage:
    from app.backends.router import BackendRouter
    
    router = BackendRouter(connection_manager)
    router.register_backend("notion", notion_client)
    router.register_backend("slack", slack_client)
    
    # Route a tool call
    result = await router.route_tool_call(
        "notion.search_pages",
        {"query": "meeting"},
        auth_token="Bearer xyz"
    )
"""

import logging
from typing import Any

from .base_mcp_client import (
    BaseMCPClient,
    GenericMCPClient,
    ToolResult,
    ToolSchema,
    ToolCallStatus,
    MCPClientError,
)
from .connection_manager import BackendConnectionManager

logger = logging.getLogger(__name__)


# =============================================================================
# Exceptions
# =============================================================================


class RouterError(Exception):
    """Base exception for router errors."""
    pass


class BackendNotFoundError(RouterError):
    """No backend registered for the given namespace."""
    pass


class InvalidToolNameError(RouterError):
    """Tool name format is invalid (missing namespace)."""
    pass


# =============================================================================
# Backend Router
# =============================================================================


class BackendRouter:
    """
    Routes MCP requests to appropriate backend clients.
    
    Responsibilities:
    - Maintains registry of backend_id → MCP client
    - Extracts namespace from namespaced tool names
    - Routes tools/call to correct backend client
    - Aggregates tools/list from all backends
    - Provides backend health checking
    
    Thread Safety:
    - Read operations are thread-safe
    - Write operations (register/unregister) should be done at startup
    
    Usage:
        router = BackendRouter(connection_manager)
        router.register_backend("notion", NotionMCPClient(...))
        
        result = await router.route_tool_call("notion.search", {})
    """
    
    # Namespace separator (matches namespace.py)
    NAMESPACE_SEPARATOR = "."
    
    def __init__(
        self,
        connection_manager: BackendConnectionManager,
        *,
        auto_register_generic: bool = True,
    ) -> None:
        """
        Initialize the backend router.
        
        Args:
            connection_manager: Connection manager for backend HTTP transport
            auto_register_generic: If True, auto-create GenericMCPClient for
                                   backends registered in connection_manager
        """
        self._connection_manager = connection_manager
        self._auto_register_generic = auto_register_generic
        self._backends: dict[str, BaseMCPClient] = {}
        
        logger.info("Backend router initialized")
    
    # ─────────────────────────────────────────────────────────────────────────
    # Backend Registration
    # ─────────────────────────────────────────────────────────────────────────
    
    def register_backend(
        self,
        backend_id: str,
        client: BaseMCPClient,
    ) -> None:
        """
        Register a backend MCP client.
        
        Args:
            backend_id: Unique backend identifier (e.g., "notion")
            client: MCP client instance for this backend
            
        Raises:
            ValueError: If backend_id is empty or client is None
        """
        if not backend_id:
            raise ValueError("backend_id cannot be empty")
        if client is None:
            raise ValueError("client cannot be None")
        
        if backend_id in self._backends:
            logger.warning(f"Replacing existing backend: {backend_id}")
        
        self._backends[backend_id] = client
        logger.info(f"Registered backend: {backend_id} ({client.__class__.__name__})")
    
    def unregister_backend(self, backend_id: str) -> bool:
        """
        Unregister a backend MCP client.
        
        Args:
            backend_id: Backend identifier to remove
            
        Returns:
            True if backend was removed, False if not found
        """
        if backend_id in self._backends:
            del self._backends[backend_id]
            logger.info(f"Unregistered backend: {backend_id}")
            return True
        return False
    
    def get_backend(self, backend_id: str) -> BaseMCPClient | None:
        """
        Get the MCP client for a backend.
        
        Args:
            backend_id: Backend identifier
            
        Returns:
            MCP client or None if not registered
        """
        client = self._backends.get(backend_id)
        
        # Auto-register generic client if enabled and backend exists in connection manager
        if client is None and self._auto_register_generic:
            if self._connection_manager.has_backend(backend_id):
                client = GenericMCPClient(
                    self._connection_manager,
                    backend_id=backend_id,
                    auto_initialize=True,
                )
                self._backends[backend_id] = client
                logger.info(f"Auto-registered generic client for: {backend_id}")
        
        return client
    
    @property
    def registered_backends(self) -> list[str]:
        """Get list of registered backend IDs."""
        return list(self._backends.keys())
    
    @property
    def backend_count(self) -> int:
        """Get number of registered backends."""
        return len(self._backends)
    
    # ─────────────────────────────────────────────────────────────────────────
    # Tool Name Parsing
    # ─────────────────────────────────────────────────────────────────────────
    
    def parse_tool_name(self, namespaced_tool: str) -> tuple[str, str]:
        """
        Parse a namespaced tool name into backend_id and tool_name.
        
        Args:
            namespaced_tool: Namespaced tool name (e.g., "notion.search_pages")
            
        Returns:
            Tuple of (backend_id, tool_name)
            
        Raises:
            InvalidToolNameError: If tool name doesn't contain namespace
        """
        if not namespaced_tool:
            raise InvalidToolNameError("Tool name cannot be empty")
        
        if self.NAMESPACE_SEPARATOR not in namespaced_tool:
            raise InvalidToolNameError(
                f"Tool name '{namespaced_tool}' missing namespace prefix. "
                f"Expected format: 'backend{self.NAMESPACE_SEPARATOR}tool_name'"
            )
        
        # Split on first separator only (tool names might contain dots)
        parts = namespaced_tool.split(self.NAMESPACE_SEPARATOR, 1)
        backend_id = parts[0]
        tool_name = parts[1]
        
        if not backend_id:
            raise InvalidToolNameError("Backend ID cannot be empty")
        if not tool_name:
            raise InvalidToolNameError("Tool name cannot be empty")
        
        return backend_id, tool_name
    
    def get_backend_for_tool(self, namespaced_tool: str) -> BaseMCPClient:
        """
        Get the backend client for a namespaced tool.
        
        Args:
            namespaced_tool: Namespaced tool name (e.g., "notion.search_pages")
            
        Returns:
            MCP client for the tool's backend
            
        Raises:
            InvalidToolNameError: If tool name format is invalid
            BackendNotFoundError: If no backend registered for namespace
        """
        backend_id, _ = self.parse_tool_name(namespaced_tool)
        
        client = self.get_backend(backend_id)
        if client is None:
            raise BackendNotFoundError(
                f"No backend registered for '{backend_id}'. "
                f"Available backends: {', '.join(self.registered_backends) or 'none'}"
            )
        
        return client
    
    # ─────────────────────────────────────────────────────────────────────────
    # Tool Routing
    # ─────────────────────────────────────────────────────────────────────────
    
    async def route_tool_call(
        self,
        namespaced_tool: str,
        arguments: dict[str, Any],
        auth_token: str | None = None,
    ) -> ToolResult:
        """
        Route a tools/call request to the appropriate backend.
        
        This is the main entry point for tool execution. It:
        1. Parses the namespace from the tool name
        2. Finds the registered client for that namespace
        3. Strips the namespace and forwards to the client
        4. Returns the result
        
        Args:
            namespaced_tool: Namespaced tool name (e.g., "notion.search_pages")
            arguments: Tool arguments
            auth_token: Authorization token to forward to backend
            
        Returns:
            ToolResult from the backend
            
        Raises:
            InvalidToolNameError: If tool name format is invalid
            BackendNotFoundError: If no backend registered for namespace
        """
        # Parse namespace
        try:
            backend_id, tool_name = self.parse_tool_name(namespaced_tool)
        except InvalidToolNameError as e:
            logger.warning(f"Invalid tool name: {namespaced_tool}")
            return ToolResult.from_error(
                ToolCallStatus.ERROR,
                str(e),
            )
        
        # Get backend client
        client = self.get_backend(backend_id)
        if client is None:
            logger.warning(f"No backend for namespace: {backend_id}")
            return ToolResult.from_error(
                ToolCallStatus.ERROR,
                f"Unknown backend: {backend_id}",
            )
        
        # Forward to backend (with stripped tool name)
        logger.debug(
            f"Routing {namespaced_tool} to {backend_id} client as {tool_name}"
        )
        
        try:
            result = await client.call_tool(
                tool_name=tool_name,
                arguments=arguments,
                auth_token=auth_token,
            )
            
            logger.debug(
                f"Tool {namespaced_tool} completed: "
                f"success={not result.is_error}, "
                f"duration={result.duration_ms:.1f}ms" if result.duration_ms else ""
            )
            
            return result
            
        except MCPClientError as e:
            logger.error(f"MCP client error for {namespaced_tool}: {e}")
            return ToolResult.from_error(
                ToolCallStatus.ERROR,
                f"Backend error: {e}",
            )
        except Exception as e:
            logger.exception(f"Unexpected error routing {namespaced_tool}")
            return ToolResult.from_error(
                ToolCallStatus.ERROR,
                f"Internal error: {e}",
            )
    
    # ─────────────────────────────────────────────────────────────────────────
    # Tool Aggregation
    # ─────────────────────────────────────────────────────────────────────────
    
    async def list_all_tools(
        self,
        auth_token: str | None = None,
        *,
        include_namespaces: list[str] | None = None,
        exclude_namespaces: list[str] | None = None,
    ) -> list[ToolSchema]:
        """
        Aggregate tools/list from all registered backends.
        
        Returns tools with namespace-prefixed names (e.g., "notion.search_pages").
        
        Args:
            auth_token: Authorization token to forward to backends
            include_namespaces: Only include these backends (None = all)
            exclude_namespaces: Exclude these backends
            
        Returns:
            List of ToolSchema from all backends (with namespaced names)
        """
        all_tools: list[ToolSchema] = []
        
        for backend_id, client in self._backends.items():
            # Filter by namespace
            if include_namespaces and backend_id not in include_namespaces:
                continue
            if exclude_namespaces and backend_id in exclude_namespaces:
                continue
            
            try:
                tools = await client.list_tools(auth_token=auth_token)
                
                # Add namespace prefix to tool names
                for tool in tools:
                    namespaced_tool = ToolSchema(
                        name=f"{backend_id}{self.NAMESPACE_SEPARATOR}{tool.name}",
                        description=f"[{backend_id.title()}] {tool.description}",
                        input_schema=tool.input_schema,
                        raw=tool.raw,
                    )
                    all_tools.append(namespaced_tool)
                
                logger.debug(f"Listed {len(tools)} tools from {backend_id}")
                
            except Exception as e:
                logger.warning(f"Failed to list tools from {backend_id}: {e}")
                # Continue with other backends
        
        logger.info(f"Aggregated {len(all_tools)} tools from {len(self._backends)} backends")
        return all_tools
    
    # ─────────────────────────────────────────────────────────────────────────
    # Health Checking
    # ─────────────────────────────────────────────────────────────────────────
    
    async def check_backend_health(self, backend_id: str) -> bool:
        """
        Check if a specific backend is healthy.
        
        Args:
            backend_id: Backend to check
            
        Returns:
            True if healthy, False otherwise
        """
        client = self.get_backend(backend_id)
        if client is None:
            return False
        
        return await client.check_health()
    
    async def check_all_backends_health(self) -> dict[str, bool]:
        """
        Check health of all registered backends.
        
        Returns:
            Dict of backend_id → is_healthy
        """
        results = {}
        for backend_id in self._backends:
            results[backend_id] = await self.check_backend_health(backend_id)
        return results
    
    async def get_healthy_backends(self) -> list[str]:
        """
        Get list of healthy backends.
        
        Returns:
            List of backend IDs that are healthy
        """
        health = await self.check_all_backends_health()
        return [bid for bid, healthy in health.items() if healthy]
    
    # ─────────────────────────────────────────────────────────────────────────
    # Initialization
    # ─────────────────────────────────────────────────────────────────────────
    
    async def initialize_all_backends(
        self,
        auth_token: str | None = None,
    ) -> dict[str, bool]:
        """
        Initialize all registered backends.
        
        Args:
            auth_token: Authorization token for initialization
            
        Returns:
            Dict of backend_id → initialization_success
        """
        results = {}
        
        for backend_id, client in self._backends.items():
            try:
                await client.initialize(auth_token=auth_token)
                results[backend_id] = True
                logger.info(f"Initialized backend: {backend_id}")
            except Exception as e:
                results[backend_id] = False
                logger.warning(f"Failed to initialize {backend_id}: {e}")
        
        success_count = sum(1 for v in results.values() if v)
        logger.info(f"Initialized {success_count}/{len(results)} backends")
        
        return results


# =============================================================================
# Factory Functions
# =============================================================================


def create_router(
    connection_manager: BackendConnectionManager,
    **kwargs: Any,
) -> BackendRouter:
    """
    Create a backend router.
    
    Args:
        connection_manager: Backend connection manager
        **kwargs: Additional router options
        
    Returns:
        Configured BackendRouter
    """
    return BackendRouter(connection_manager, **kwargs)


def create_router_with_backends(
    connection_manager: BackendConnectionManager,
    backend_ids: list[str],
    **kwargs: Any,
) -> BackendRouter:
    """
    Create a router with generic clients for specified backends.
    
    Convenience function for MVP setup. Creates GenericMCPClient
    instances for each backend_id.
    
    Args:
        connection_manager: Backend connection manager
        backend_ids: Backend IDs to register (e.g., ["notion", "slack"])
        **kwargs: Additional router options
        
    Returns:
        Configured BackendRouter with registered backends
    """
    router = BackendRouter(connection_manager, **kwargs)
    
    for backend_id in backend_ids:
        client = GenericMCPClient(
            connection_manager,
            backend_id=backend_id,
            auto_initialize=True,
        )
        router.register_backend(backend_id, client)
    
    return router
```

### 2. Update `__init__.py`

Add to `deeptrail-gateway/app/backends/__init__.py`:

```python
from .router import (
    BackendRouter,
    RouterError,
    BackendNotFoundError,
    InvalidToolNameError,
    create_router,
    create_router_with_backends,
)

__all__ = [
    # ... existing exports ...
    # Router
    "BackendRouter",
    "RouterError",
    "BackendNotFoundError",
    "InvalidToolNameError",
    "create_router",
    "create_router_with_backends",
]
```

---

## Acceptance Criteria

### Implementation Criteria

- [ ] `BackendRouter` class implemented
- [ ] Backend registration (register/unregister) works
- [ ] Tool name parsing extracts namespace correctly
- [ ] `route_tool_call` forwards to correct backend
- [ ] `list_all_tools` aggregates from all backends

### Routing Criteria

- [ ] `notion.search_pages` routes to Notion client with `search_pages`
- [ ] `slack.send_message` routes to Slack client with `send_message`
- [ ] `hubspot.get_contact` routes to HubSpot client with `get_contact`
- [ ] Unknown namespace returns error (not exception)
- [ ] Invalid tool name format returns error

### Error Handling Criteria

- [ ] Missing namespace returns `InvalidToolNameError`
- [ ] Unknown backend returns `BackendNotFoundError`
- [ ] Client errors wrapped in `ToolResult.from_error()`
- [ ] Errors logged at appropriate levels
- [ ] Does not throw exceptions to caller (returns ToolResult)

### Integration Criteria

- [ ] Works with `tools/call` handler (B7)
- [ ] Works with namespace prefixer (B4)
- [ ] Supports D3, D4, D5 clients
- [ ] Supports GenericMCPClient for unimplemented backends

### Test Criteria

- [ ] Test backend registration
- [ ] Test tool name parsing
- [ ] Test routing to correct backend
- [ ] Test namespace extraction
- [ ] Test unknown backend handling
- [ ] Test invalid tool name handling
- [ ] Test list_all_tools aggregation
- [ ] Test health checking
- [ ] All tests pass with `pytest tests/backends/test_router.py`

---

## Test Cases

Create `deeptrail-gateway/tests/backends/test_router.py`:

```python
"""Tests for backend router (D6)."""

import pytest
from unittest.mock import AsyncMock, MagicMock

from app.backends.router import (
    BackendRouter,
    BackendNotFoundError,
    InvalidToolNameError,
    create_router,
    create_router_with_backends,
)
from app.backends.base_mcp_client import (
    BaseMCPClient,
    ToolResult,
    ToolSchema,
    ToolCallStatus,
)


@pytest.fixture
def mock_connection_manager():
    """Create mock connection manager."""
    manager = MagicMock()
    manager.has_backend = MagicMock(return_value=False)
    return manager


@pytest.fixture
def mock_notion_client():
    """Create mock Notion client."""
    client = MagicMock(spec=BaseMCPClient)
    client.backend_id = "notion"
    client.call_tool = AsyncMock()
    client.list_tools = AsyncMock()
    client.check_health = AsyncMock(return_value=True)
    return client


@pytest.fixture
def mock_slack_client():
    """Create mock Slack client."""
    client = MagicMock(spec=BaseMCPClient)
    client.backend_id = "slack"
    client.call_tool = AsyncMock()
    client.list_tools = AsyncMock()
    client.check_health = AsyncMock(return_value=True)
    return client


@pytest.fixture
def router(mock_connection_manager):
    """Create router with mock connection manager."""
    return BackendRouter(mock_connection_manager, auto_register_generic=False)


class TestBackendRegistration:
    """Tests for backend registration."""
    
    def test_register_backend(self, router, mock_notion_client):
        """Test registering a backend."""
        router.register_backend("notion", mock_notion_client)
        
        assert "notion" in router.registered_backends
        assert router.backend_count == 1
    
    def test_register_multiple_backends(
        self, router, mock_notion_client, mock_slack_client
    ):
        """Test registering multiple backends."""
        router.register_backend("notion", mock_notion_client)
        router.register_backend("slack", mock_slack_client)
        
        assert router.backend_count == 2
        assert set(router.registered_backends) == {"notion", "slack"}
    
    def test_unregister_backend(self, router, mock_notion_client):
        """Test unregistering a backend."""
        router.register_backend("notion", mock_notion_client)
        
        result = router.unregister_backend("notion")
        
        assert result is True
        assert "notion" not in router.registered_backends
    
    def test_unregister_nonexistent(self, router):
        """Test unregistering non-existent backend."""
        result = router.unregister_backend("nonexistent")
        
        assert result is False
    
    def test_get_backend(self, router, mock_notion_client):
        """Test getting a registered backend."""
        router.register_backend("notion", mock_notion_client)
        
        client = router.get_backend("notion")
        
        assert client is mock_notion_client
    
    def test_get_nonexistent_backend(self, router):
        """Test getting non-existent backend returns None."""
        client = router.get_backend("nonexistent")
        
        assert client is None
    
    def test_register_empty_backend_id(self, router, mock_notion_client):
        """Test registering with empty backend_id raises."""
        with pytest.raises(ValueError):
            router.register_backend("", mock_notion_client)
    
    def test_register_none_client(self, router):
        """Test registering None client raises."""
        with pytest.raises(ValueError):
            router.register_backend("notion", None)


class TestToolNameParsing:
    """Tests for tool name parsing."""
    
    def test_parse_simple_tool(self, router):
        """Test parsing simple namespaced tool."""
        backend_id, tool_name = router.parse_tool_name("notion.search_pages")
        
        assert backend_id == "notion"
        assert tool_name == "search_pages"
    
    def test_parse_tool_with_dots(self, router):
        """Test parsing tool name containing dots."""
        backend_id, tool_name = router.parse_tool_name("github.repos.create")
        
        assert backend_id == "github"
        assert tool_name == "repos.create"
    
    def test_parse_empty_raises(self, router):
        """Test parsing empty string raises."""
        with pytest.raises(InvalidToolNameError):
            router.parse_tool_name("")
    
    def test_parse_no_namespace_raises(self, router):
        """Test parsing tool without namespace raises."""
        with pytest.raises(InvalidToolNameError):
            router.parse_tool_name("search_pages")
    
    def test_parse_empty_backend_raises(self, router):
        """Test parsing with empty backend raises."""
        with pytest.raises(InvalidToolNameError):
            router.parse_tool_name(".search_pages")
    
    def test_parse_empty_tool_raises(self, router):
        """Test parsing with empty tool name raises."""
        with pytest.raises(InvalidToolNameError):
            router.parse_tool_name("notion.")


class TestToolRouting:
    """Tests for tool routing."""
    
    @pytest.mark.asyncio
    async def test_route_to_notion(self, router, mock_notion_client):
        """Test routing to Notion backend."""
        router.register_backend("notion", mock_notion_client)
        mock_notion_client.call_tool.return_value = ToolResult(
            status=ToolCallStatus.SUCCESS,
            content=[{"type": "text", "text": "results"}],
        )
        
        result = await router.route_tool_call(
            "notion.search_pages",
            {"query": "test"},
            auth_token="Bearer xyz"
        )
        
        assert not result.is_error
        mock_notion_client.call_tool.assert_called_once_with(
            tool_name="search_pages",
            arguments={"query": "test"},
            auth_token="Bearer xyz",
        )
    
    @pytest.mark.asyncio
    async def test_route_to_slack(self, router, mock_slack_client):
        """Test routing to Slack backend."""
        router.register_backend("slack", mock_slack_client)
        mock_slack_client.call_tool.return_value = ToolResult(
            status=ToolCallStatus.SUCCESS,
            content=[{"type": "text", "text": "sent"}],
        )
        
        result = await router.route_tool_call(
            "slack.send_message",
            {"channel": "C123", "text": "Hello"},
        )
        
        assert not result.is_error
        mock_slack_client.call_tool.assert_called_once_with(
            tool_name="send_message",
            arguments={"channel": "C123", "text": "Hello"},
            auth_token=None,
        )
    
    @pytest.mark.asyncio
    async def test_route_unknown_backend(self, router):
        """Test routing to unknown backend returns error."""
        result = await router.route_tool_call(
            "unknown.tool",
            {},
        )
        
        assert result.is_error
        assert "unknown" in result.error_message.lower()
    
    @pytest.mark.asyncio
    async def test_route_invalid_tool_name(self, router):
        """Test routing invalid tool name returns error."""
        result = await router.route_tool_call(
            "no_namespace",
            {},
        )
        
        assert result.is_error
        assert "namespace" in result.error_message.lower()
    
    @pytest.mark.asyncio
    async def test_route_client_error(self, router, mock_notion_client):
        """Test routing handles client errors."""
        router.register_backend("notion", mock_notion_client)
        mock_notion_client.call_tool.side_effect = Exception("Connection failed")
        
        result = await router.route_tool_call(
            "notion.search_pages",
            {},
        )
        
        assert result.is_error
        assert "error" in result.error_message.lower()


class TestToolAggregation:
    """Tests for tool aggregation."""
    
    @pytest.mark.asyncio
    async def test_list_all_tools(
        self, router, mock_notion_client, mock_slack_client
    ):
        """Test listing tools from all backends."""
        router.register_backend("notion", mock_notion_client)
        router.register_backend("slack", mock_slack_client)
        
        mock_notion_client.list_tools.return_value = [
            ToolSchema(name="search_pages", description="Search"),
        ]
        mock_slack_client.list_tools.return_value = [
            ToolSchema(name="send_message", description="Send"),
        ]
        
        tools = await router.list_all_tools()
        
        assert len(tools) == 2
        tool_names = [t.name for t in tools]
        assert "notion.search_pages" in tool_names
        assert "slack.send_message" in tool_names
    
    @pytest.mark.asyncio
    async def test_list_tools_with_filter(self, router, mock_notion_client, mock_slack_client):
        """Test listing tools with namespace filter."""
        router.register_backend("notion", mock_notion_client)
        router.register_backend("slack", mock_slack_client)
        
        mock_notion_client.list_tools.return_value = [
            ToolSchema(name="search", description="Search"),
        ]
        
        tools = await router.list_all_tools(include_namespaces=["notion"])
        
        assert len(tools) == 1
        assert tools[0].name == "notion.search"
        mock_slack_client.list_tools.assert_not_called()
    
    @pytest.mark.asyncio
    async def test_list_tools_handles_error(self, router, mock_notion_client):
        """Test listing tools handles backend errors gracefully."""
        router.register_backend("notion", mock_notion_client)
        mock_notion_client.list_tools.side_effect = Exception("Failed")
        
        tools = await router.list_all_tools()
        
        assert tools == []  # Empty, not exception


class TestHealthChecking:
    """Tests for health checking."""
    
    @pytest.mark.asyncio
    async def test_check_backend_health(self, router, mock_notion_client):
        """Test checking single backend health."""
        router.register_backend("notion", mock_notion_client)
        mock_notion_client.check_health.return_value = True
        
        healthy = await router.check_backend_health("notion")
        
        assert healthy is True
    
    @pytest.mark.asyncio
    async def test_check_all_backends_health(
        self, router, mock_notion_client, mock_slack_client
    ):
        """Test checking all backends health."""
        router.register_backend("notion", mock_notion_client)
        router.register_backend("slack", mock_slack_client)
        mock_notion_client.check_health.return_value = True
        mock_slack_client.check_health.return_value = False
        
        health = await router.check_all_backends_health()
        
        assert health == {"notion": True, "slack": False}
    
    @pytest.mark.asyncio
    async def test_get_healthy_backends(
        self, router, mock_notion_client, mock_slack_client
    ):
        """Test getting list of healthy backends."""
        router.register_backend("notion", mock_notion_client)
        router.register_backend("slack", mock_slack_client)
        mock_notion_client.check_health.return_value = True
        mock_slack_client.check_health.return_value = False
        
        healthy = await router.get_healthy_backends()
        
        assert healthy == ["notion"]


class TestFactoryFunctions:
    """Tests for factory functions."""
    
    def test_create_router(self, mock_connection_manager):
        """Test create_router factory."""
        router = create_router(mock_connection_manager)
        
        assert isinstance(router, BackendRouter)
        assert router.backend_count == 0
    
    def test_create_router_with_backends(self, mock_connection_manager):
        """Test create_router_with_backends factory."""
        router = create_router_with_backends(
            mock_connection_manager,
            backend_ids=["notion", "slack"],
        )
        
        assert isinstance(router, BackendRouter)
        assert router.backend_count == 2
        assert "notion" in router.registered_backends
        assert "slack" in router.registered_backends
```

---

## Post-Conditions

After completing this task:

- [ ] `BackendRouter` is available in `app/backends/`
- [ ] Gateway can route tool calls to appropriate backends
- [ ] `tools/call` handler (B7) can use router
- [ ] Tool aggregation works across all backends
- [ ] Health checking works for all backends
- [ ] Demo 1 (Unified Connection) routing works
- [ ] All unit tests pass

---

## References

- **Design Doc Section**: 2.6 Step 8: Agent Executes Task
- **Upstream Tasks**:
  - [WS-D1: Connection Manager](./WS-D1-backend-connection-manager.md) - HTTP transport
  - [WS-D2: Base MCP Client](./WS-D2-base-mcp-client.md) - Client interface
  - [WS-B7: tools/call Handler](./WS-B7-tools-call-handler.md) - Uses router
  - [WS-B4: Namespace Prefixer](./WS-B4-namespace-prefixer.md) - Namespace format
- **Related Tasks**:
  - [WS-D3: Notion MCP Client](./WS-D3-notion-mcp-client.md) - Registered backend
  - [WS-D4: Slack MCP Client](./WS-D4-slack-mcp-client.md) - Registered backend
  - [WS-D5: HubSpot MCP Client](./WS-D5-hubspot-mcp-client.md) - Registered backend
- **Downstream Tasks**:
  - [WS-F2: Demo 1 Unified Connection](./WS-F2-demo-unified-connection.md) - Uses router

---

## Notes

- The router is the central point for all backend tool routing
- Uses namespace prefix (before first `.`) to determine backend
- Strips namespace before forwarding to backend client
- Returns `ToolResult` errors rather than throwing exceptions
- Auto-registration feature creates GenericMCPClient on demand
- Health checking enables fail-over and monitoring
- Tool aggregation supports the `tools/list` response building
