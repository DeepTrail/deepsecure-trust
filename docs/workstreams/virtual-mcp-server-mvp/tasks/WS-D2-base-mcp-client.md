# Task: WS-D2 Implement Base MCP Client

---

## Metadata

| Field | Value |
|-------|-------|
| **Status** | `ready` |
| **Design Doc** | [deepsecure-virtual-mcp-server-mvp.md](../../../design/internal/markdowns/deepsecure-virtual-mcp-server-mvp.md) |
| **Workstream** | WS-D: Backend Connectors |
| **Dependencies** | D1 (Backend Connection Manager) |
| **Blocked By** | None (D1 ticket created) |
| **Assigned** | - |
| **Created** | February 4, 2026 |
| **Estimated Complexity** | `M` (2-4 hours) |
| **Batch** | 4 |

---

## Validation Mapping

| Mapping | Value |
|---------|-------|
| **Validates Demo** | Demo 1: Unified Connection, Demo 3: Delegation Execution |
| **Validates User Journey Step** | Step 8: Agent Executes Task (Tool Execution) |

---

## Pre-Conditions

Before starting this task, ensure:

- [x] D1 (Backend Connection Manager) ticket created
- [x] B1 (MCP JSON-RPC 2.0 parser) is complete
- [ ] `deeptrail-gateway/app/backends/` package exists (from D1)
- [ ] BackendConnectionManager can be imported from `app.backends`
- [ ] MCPRequest/MCPResponse can be imported from `app.backends`

---

## Task Description

Implement the BaseMCPClient abstract base class that provides a common interface for communicating with backend MCP servers. This class handles the MCP protocol lifecycle (initialize, tools/list, tools/call) and provides extension points for backend-specific implementations (Notion, Slack, HubSpot).

### Context

From the MVP design (Section 2.9 - Step 8: Agent Executes Task):

```
Gateway forwards tools/call to backend:

5. FORWARD to backend Notion MCP Server:
   POST https://mcp.notion.com/tools/call
   Authorization: Bearer {sarah's-notion-oauth-token}
   {
     "method": "tools/call",
     "params": {
       "name": "search_pages",   // Stripped namespace (no "notion." prefix)
       "arguments": {"query": "competitor analysis", "limit": 5}
     }
   }

6. RECEIVE response from Notion:
   {
     "content": [
       {"type": "text", "text": "Found 3 pages: ..."}
     ]
   }
```

The base MCP client provides:
- **Standardized Interface**: Common API for all backend interactions
- **Protocol Handling**: MCP JSON-RPC request/response formatting
- **Credential Injection**: Auth header management per request
- **Error Normalization**: Consistent error handling across backends
- **Extensibility**: Hook methods for backend-specific logic

### Technical Notes

- Abstract base class using Python's `abc` module
- Uses `BackendConnectionManager` (D1) for actual HTTP requests
- Async methods for non-blocking I/O
- Supports both stateless requests and stateful sessions
- Tool name stripping (removes namespace prefix before forwarding)
- Response transformation (optional backend-specific processing)

---

## Files to Create/Modify

| File | Action | Description |
|------|--------|-------------|
| `deeptrail-gateway/app/backends/base_mcp_client.py` | **CREATE** | BaseMCPClient abstract class |
| `deeptrail-gateway/app/backends/__init__.py` | **MODIFY** | Export BaseMCPClient |
| `deeptrail-gateway/tests/backends/test_base_mcp_client.py` | **CREATE** | Unit tests |

---

## Implementation Details

### 1. Base MCP Client (`app/backends/base_mcp_client.py`)

```python
"""
Base MCP Client

Abstract base class for backend MCP server clients. Provides standardized
interface for MCP protocol operations (initialize, tools/list, tools/call)
while allowing backend-specific customizations.

Architecture:
- BaseMCPClient defines the interface and common behavior
- Concrete clients (NotionMCPClient, SlackMCPClient) extend for specifics
- Uses BackendConnectionManager for actual HTTP transport

Usage:
    # Create concrete implementation
    class NotionMCPClient(BaseMCPClient):
        @property
        def backend_id(self) -> str:
            return "notion"
        
        def transform_tool_result(self, tool_name, result):
            # Notion-specific result processing
            return result
    
    # Use the client
    client = NotionMCPClient(connection_manager)
    tools = await client.list_tools(auth_token="Bearer xyz")
    result = await client.call_tool("search_pages", {"query": "test"}, auth_token="Bearer xyz")
"""

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Callable, TypeVar

from .connection_manager import (
    BackendConnectionManager,
    MCPRequest,
    MCPResponse,
    BackendError,
    BackendNotFoundError,
    BackendUnavailableError,
    BackendTimeoutError,
    BackendRequestError,
)

logger = logging.getLogger(__name__)

T = TypeVar("T")


# =============================================================================
# Enums and Constants
# =============================================================================


class MCPCapability(str, Enum):
    """MCP server capabilities."""
    TOOLS = "tools"
    RESOURCES = "resources"
    PROMPTS = "prompts"
    LOGGING = "logging"


class ToolCallStatus(str, Enum):
    """Status of a tool call."""
    SUCCESS = "success"
    ERROR = "error"
    TIMEOUT = "timeout"
    UNAUTHORIZED = "unauthorized"


# =============================================================================
# Data Classes
# =============================================================================


@dataclass
class ServerInfo:
    """
    Information about a backend MCP server.
    
    Populated from the initialize response.
    
    Attributes:
        name: Server name (e.g., "Notion MCP Server")
        version: Server version (e.g., "1.0.0")
        protocol_version: MCP protocol version (e.g., "2024-11-05")
        capabilities: List of supported capabilities
        raw: Raw server info dict from response
    """
    name: str
    version: str
    protocol_version: str = "2024-11-05"
    capabilities: list[MCPCapability] = field(default_factory=list)
    raw: dict[str, Any] = field(default_factory=dict)
    
    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ServerInfo":
        """Parse from initialize response serverInfo."""
        capabilities = []
        caps_data = data.get("capabilities", {})
        if caps_data.get("tools"):
            capabilities.append(MCPCapability.TOOLS)
        if caps_data.get("resources"):
            capabilities.append(MCPCapability.RESOURCES)
        if caps_data.get("prompts"):
            capabilities.append(MCPCapability.PROMPTS)
        if caps_data.get("logging"):
            capabilities.append(MCPCapability.LOGGING)
        
        return cls(
            name=data.get("name", "Unknown"),
            version=data.get("version", "0.0.0"),
            protocol_version=data.get("protocolVersion", "2024-11-05"),
            capabilities=capabilities,
            raw=data,
        )


@dataclass
class ToolSchema:
    """
    Schema for a single MCP tool.
    
    Attributes:
        name: Tool name (without namespace prefix)
        description: Human-readable description
        input_schema: JSON Schema for tool inputs
        raw: Raw tool dict from backend
    """
    name: str
    description: str
    input_schema: dict[str, Any] = field(default_factory=dict)
    raw: dict[str, Any] = field(default_factory=dict)
    
    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ToolSchema":
        """Parse from tools/list response item."""
        return cls(
            name=data.get("name", ""),
            description=data.get("description", ""),
            input_schema=data.get("inputSchema", {}),
            raw=data,
        )
    
    def to_dict(self) -> dict[str, Any]:
        """Convert to MCP tool format."""
        return {
            "name": self.name,
            "description": self.description,
            "inputSchema": self.input_schema,
        }


@dataclass
class ToolResult:
    """
    Result from a tools/call invocation.
    
    Attributes:
        status: Call status (success, error, etc.)
        content: Result content (list of content items)
        is_error: Whether the tool returned an error
        error_message: Error message if is_error
        raw: Raw response from backend
        duration_ms: Call duration in milliseconds
    """
    status: ToolCallStatus
    content: list[dict[str, Any]] = field(default_factory=list)
    is_error: bool = False
    error_message: str | None = None
    raw: dict[str, Any] = field(default_factory=dict)
    duration_ms: float | None = None
    
    @classmethod
    def from_response(cls, response: MCPResponse, duration_ms: float | None = None) -> "ToolResult":
        """Parse from MCP response."""
        if not response.is_success:
            error = response.error or {}
            return cls(
                status=ToolCallStatus.ERROR,
                is_error=True,
                error_message=error.get("message", "Unknown error"),
                raw=response.raw,
                duration_ms=duration_ms,
            )
        
        result = response.result or {}
        content = result.get("content", [])
        is_error = result.get("isError", False)
        
        return cls(
            status=ToolCallStatus.ERROR if is_error else ToolCallStatus.SUCCESS,
            content=content,
            is_error=is_error,
            error_message=content[0].get("text") if is_error and content else None,
            raw=response.raw,
            duration_ms=duration_ms,
        )
    
    @classmethod
    def from_error(cls, status: ToolCallStatus, message: str) -> "ToolResult":
        """Create error result."""
        return cls(
            status=status,
            is_error=True,
            error_message=message,
            content=[{"type": "text", "text": message}],
        )
    
    def get_text_content(self) -> str:
        """Extract text content from result."""
        texts = []
        for item in self.content:
            if item.get("type") == "text":
                texts.append(item.get("text", ""))
        return "\n".join(texts)


# =============================================================================
# Exceptions
# =============================================================================


class MCPClientError(Exception):
    """Base exception for MCP client errors."""
    pass


class MCPInitializeError(MCPClientError):
    """Failed to initialize MCP session with backend."""
    pass


class MCPToolNotFoundError(MCPClientError):
    """Requested tool not found on backend."""
    pass


class MCPToolCallError(MCPClientError):
    """Tool call failed."""
    pass


# =============================================================================
# Base MCP Client
# =============================================================================


class BaseMCPClient(ABC):
    """
    Abstract base class for backend MCP clients.
    
    Provides common interface for MCP protocol operations while allowing
    backend-specific customizations through abstract methods and hooks.
    
    Subclasses must implement:
    - backend_id: Property returning the backend identifier
    
    Subclasses may override:
    - transform_tool_result: Process tool results before returning
    - get_default_headers: Add backend-specific headers
    - validate_tool_arguments: Validate arguments before sending
    
    Usage:
        class NotionMCPClient(BaseMCPClient):
            @property
            def backend_id(self) -> str:
                return "notion"
        
        client = NotionMCPClient(connection_manager)
        await client.initialize(auth_token="Bearer xyz")
        tools = await client.list_tools(auth_token="Bearer xyz")
        result = await client.call_tool("search_pages", {...}, auth_token="Bearer xyz")
    """
    
    def __init__(
        self,
        connection_manager: BackendConnectionManager,
        *,
        auto_initialize: bool = False,
    ) -> None:
        """
        Initialize MCP client.
        
        Args:
            connection_manager: Backend connection manager for HTTP transport
            auto_initialize: If True, automatically initialize on first request
        """
        self._connection_manager = connection_manager
        self._auto_initialize = auto_initialize
        self._server_info: ServerInfo | None = None
        self._initialized = False
        self._tools_cache: list[ToolSchema] | None = None
    
    # ─────────────────────────────────────────────────────────────────
    # Abstract Properties
    # ─────────────────────────────────────────────────────────────────
    
    @property
    @abstractmethod
    def backend_id(self) -> str:
        """
        Return the backend identifier.
        
        This must match the backend_id registered with BackendConnectionManager.
        
        Returns:
            Backend identifier (e.g., "notion", "slack", "hubspot")
        """
        pass
    
    # ─────────────────────────────────────────────────────────────────
    # Properties
    # ─────────────────────────────────────────────────────────────────
    
    @property
    def is_initialized(self) -> bool:
        """Check if client has completed initialize handshake."""
        return self._initialized
    
    @property
    def server_info(self) -> ServerInfo | None:
        """Get server info from last initialize (or None if not initialized)."""
        return self._server_info
    
    @property
    def connection_manager(self) -> BackendConnectionManager:
        """Get the connection manager."""
        return self._connection_manager
    
    # ─────────────────────────────────────────────────────────────────
    # MCP Protocol Methods
    # ─────────────────────────────────────────────────────────────────
    
    async def initialize(
        self,
        auth_token: str | None = None,
        client_info: dict[str, Any] | None = None,
    ) -> ServerInfo:
        """
        Initialize MCP session with backend.
        
        Performs the MCP initialize handshake to establish capabilities
        and protocol version with the backend server.
        
        Args:
            auth_token: Authorization token (e.g., "Bearer xyz")
            client_info: Client information to send to backend
            
        Returns:
            ServerInfo from backend
            
        Raises:
            MCPInitializeError: If initialization fails
        """
        if client_info is None:
            client_info = {
                "name": "DeepTrail Gateway",
                "version": "1.0.0",
            }
        
        try:
            response = await self._connection_manager.send_initialize(
                backend_id=self.backend_id,
                client_info=client_info,
                auth_header=auth_token,
            )
            
            if not response.is_success:
                error_msg = response.error.get("message", "Unknown error") if response.error else "Unknown error"
                raise MCPInitializeError(f"Initialize failed: {error_msg}")
            
            result = response.result or {}
            server_info_data = result.get("serverInfo", result)
            
            self._server_info = ServerInfo.from_dict(server_info_data)
            self._initialized = True
            
            logger.info(
                f"Initialized MCP session with {self.backend_id}: "
                f"{self._server_info.name} v{self._server_info.version}"
            )
            
            return self._server_info
            
        except BackendError as e:
            raise MCPInitializeError(f"Initialize failed: {e}") from e
    
    async def list_tools(
        self,
        auth_token: str | None = None,
        *,
        use_cache: bool = True,
        force_refresh: bool = False,
    ) -> list[ToolSchema]:
        """
        List available tools from backend.
        
        Args:
            auth_token: Authorization token
            use_cache: Use cached tools if available
            force_refresh: Force refresh even if cached
            
        Returns:
            List of ToolSchema objects
            
        Raises:
            MCPClientError: If request fails
        """
        # Check cache
        if use_cache and not force_refresh and self._tools_cache is not None:
            return self._tools_cache
        
        # Auto-initialize if needed
        if self._auto_initialize and not self._initialized:
            await self.initialize(auth_token=auth_token)
        
        try:
            response = await self._connection_manager.send_tools_list(
                backend_id=self.backend_id,
                auth_header=auth_token,
            )
            
            if not response.is_success:
                error_msg = response.error.get("message", "Unknown error") if response.error else "Unknown error"
                raise MCPClientError(f"tools/list failed: {error_msg}")
            
            result = response.result or {}
            tools_data = result.get("tools", [])
            
            tools = [ToolSchema.from_dict(t) for t in tools_data]
            
            # Cache results
            if use_cache:
                self._tools_cache = tools
            
            logger.debug(f"Listed {len(tools)} tools from {self.backend_id}")
            
            return tools
            
        except BackendError as e:
            raise MCPClientError(f"tools/list failed: {e}") from e
    
    async def call_tool(
        self,
        tool_name: str,
        arguments: dict[str, Any],
        auth_token: str | None = None,
    ) -> ToolResult:
        """
        Execute a tool on the backend.
        
        Args:
            tool_name: Tool name (without namespace prefix)
            arguments: Tool arguments
            auth_token: Authorization token
            
        Returns:
            ToolResult with execution result
            
        Raises:
            MCPToolCallError: If tool call fails unexpectedly
        """
        # Validate arguments (hook for subclasses)
        validated_args = self.validate_tool_arguments(tool_name, arguments)
        
        # Auto-initialize if needed
        if self._auto_initialize and not self._initialized:
            await self.initialize(auth_token=auth_token)
        
        start_time = datetime.now(timezone.utc)
        
        try:
            response = await self._connection_manager.send_tools_call(
                backend_id=self.backend_id,
                tool_name=tool_name,
                arguments=validated_args,
                auth_header=auth_token,
            )
            
            duration_ms = (datetime.now(timezone.utc) - start_time).total_seconds() * 1000
            
            # Parse result
            result = ToolResult.from_response(response, duration_ms=duration_ms)
            
            # Transform result (hook for subclasses)
            result = self.transform_tool_result(tool_name, result)
            
            if result.is_error:
                logger.warning(
                    f"Tool {self.backend_id}.{tool_name} returned error: {result.error_message}"
                )
            else:
                logger.debug(
                    f"Tool {self.backend_id}.{tool_name} completed in {duration_ms:.1f}ms"
                )
            
            return result
            
        except BackendTimeoutError as e:
            duration_ms = (datetime.now(timezone.utc) - start_time).total_seconds() * 1000
            logger.warning(f"Tool {self.backend_id}.{tool_name} timed out after {duration_ms:.1f}ms")
            return ToolResult.from_error(ToolCallStatus.TIMEOUT, f"Tool call timed out: {e}")
            
        except BackendUnavailableError as e:
            logger.warning(f"Backend {self.backend_id} unavailable for tool {tool_name}")
            return ToolResult.from_error(ToolCallStatus.ERROR, f"Backend unavailable: {e}")
            
        except BackendError as e:
            raise MCPToolCallError(f"Tool call failed: {e}") from e
    
    async def call_tool_with_namespace(
        self,
        namespaced_tool: str,
        arguments: dict[str, Any],
        auth_token: str | None = None,
    ) -> ToolResult:
        """
        Execute a tool using its namespaced name.
        
        Strips the namespace prefix before forwarding to backend.
        
        Args:
            namespaced_tool: Namespaced tool name (e.g., "notion.search_pages")
            arguments: Tool arguments
            auth_token: Authorization token
            
        Returns:
            ToolResult with execution result
        """
        # Strip namespace prefix
        tool_name = self.strip_namespace(namespaced_tool)
        return await self.call_tool(tool_name, arguments, auth_token=auth_token)
    
    # ─────────────────────────────────────────────────────────────────
    # Namespace Handling
    # ─────────────────────────────────────────────────────────────────
    
    def strip_namespace(self, namespaced_tool: str) -> str:
        """
        Remove namespace prefix from tool name.
        
        Args:
            namespaced_tool: Namespaced name (e.g., "notion.search_pages")
            
        Returns:
            Tool name without prefix (e.g., "search_pages")
        """
        if "." in namespaced_tool:
            parts = namespaced_tool.split(".", 1)
            if parts[0] == self.backend_id:
                return parts[1]
        return namespaced_tool
    
    def add_namespace(self, tool_name: str) -> str:
        """
        Add namespace prefix to tool name.
        
        Args:
            tool_name: Tool name without prefix
            
        Returns:
            Namespaced name (e.g., "notion.search_pages")
        """
        if "." not in tool_name:
            return f"{self.backend_id}.{tool_name}"
        return tool_name
    
    # ─────────────────────────────────────────────────────────────────
    # Hook Methods (Override in Subclasses)
    # ─────────────────────────────────────────────────────────────────
    
    def validate_tool_arguments(
        self,
        tool_name: str,
        arguments: dict[str, Any],
    ) -> dict[str, Any]:
        """
        Validate and potentially transform tool arguments.
        
        Override in subclasses to add backend-specific validation.
        
        Args:
            tool_name: Tool being called
            arguments: Raw arguments from caller
            
        Returns:
            Validated/transformed arguments
            
        Raises:
            ValueError: If arguments are invalid
        """
        # Default: pass through unchanged
        return arguments
    
    def transform_tool_result(
        self,
        tool_name: str,
        result: ToolResult,
    ) -> ToolResult:
        """
        Transform tool result before returning to caller.
        
        Override in subclasses to add backend-specific result processing.
        
        Args:
            tool_name: Tool that was called
            result: Raw result from backend
            
        Returns:
            Transformed result
        """
        # Default: pass through unchanged
        return result
    
    def get_default_headers(self) -> dict[str, str]:
        """
        Get default headers to include in all requests.
        
        Override in subclasses to add backend-specific headers.
        
        Returns:
            Dict of header name → value
        """
        return {}
    
    # ─────────────────────────────────────────────────────────────────
    # Utility Methods
    # ─────────────────────────────────────────────────────────────────
    
    def clear_cache(self) -> None:
        """Clear cached tools list."""
        self._tools_cache = None
    
    def reset(self) -> None:
        """Reset client state (requires re-initialization)."""
        self._initialized = False
        self._server_info = None
        self._tools_cache = None
    
    async def check_health(self) -> bool:
        """
        Check if backend is healthy.
        
        Returns:
            True if backend is reachable and healthy
        """
        return await self._connection_manager.check_backend_health(self.backend_id)
    
    def __repr__(self) -> str:
        """String representation."""
        status = "initialized" if self._initialized else "not initialized"
        return f"<{self.__class__.__name__} backend={self.backend_id} {status}>"


# =============================================================================
# Concrete Implementation for Testing/MVP
# =============================================================================


class GenericMCPClient(BaseMCPClient):
    """
    Generic MCP client for backends without specific implementations.
    
    Use this for testing or for backends that don't need custom behavior.
    
    Usage:
        client = GenericMCPClient(connection_manager, backend_id="notion")
    """
    
    def __init__(
        self,
        connection_manager: BackendConnectionManager,
        backend_id: str,
        **kwargs,
    ) -> None:
        """
        Initialize generic client.
        
        Args:
            connection_manager: Backend connection manager
            backend_id: Backend identifier to use
            **kwargs: Additional arguments for BaseMCPClient
        """
        super().__init__(connection_manager, **kwargs)
        self._backend_id = backend_id
    
    @property
    def backend_id(self) -> str:
        """Return the configured backend ID."""
        return self._backend_id


# =============================================================================
# Factory Functions
# =============================================================================


def create_mcp_client(
    connection_manager: BackendConnectionManager,
    backend_id: str,
    **kwargs,
) -> BaseMCPClient:
    """
    Create an MCP client for the specified backend.
    
    For MVP, returns GenericMCPClient. In production, would return
    backend-specific clients (NotionMCPClient, SlackMCPClient, etc.)
    
    Args:
        connection_manager: Backend connection manager
        backend_id: Backend identifier
        **kwargs: Additional client options
        
    Returns:
        Configured MCP client
    """
    # MVP: Use generic client for all backends
    # Production: Return backend-specific clients
    return GenericMCPClient(
        connection_manager=connection_manager,
        backend_id=backend_id,
        **kwargs,
    )
```

### 2. Update Package Init (`app/backends/__init__.py`)

Add to the existing `__init__.py` from D1:

```python
"""
Backend Connectors Package

Provides connection management and MCP clients for backend servers.

Main Components:
- BackendConnectionManager: Manages connections, pooling, health checks
- BaseMCPClient: Abstract base class for backend MCP clients
- GenericMCPClient: Generic client for testing/MVP

Usage:
    from app.backends import (
        BackendConnectionManager,
        BackendConfig,
        BaseMCPClient,
        GenericMCPClient,
        create_mcp_client,
    )
"""

from .connection_manager import (
    # Enums
    BackendStatus,
    RequestMethod,
    # Data Classes
    BackendConfig,
    BackendState,
    MCPRequest,
    MCPResponse,
    # Exceptions
    BackendError,
    BackendNotFoundError,
    BackendUnavailableError,
    BackendTimeoutError,
    BackendRequestError,
    # Manager
    BackendConnectionManager,
    # Factory
    create_default_manager,
)

from .base_mcp_client import (
    # Enums
    MCPCapability,
    ToolCallStatus,
    # Data Classes
    ServerInfo,
    ToolSchema,
    ToolResult,
    # Exceptions
    MCPClientError,
    MCPInitializeError,
    MCPToolNotFoundError,
    MCPToolCallError,
    # Base Class
    BaseMCPClient,
    # Generic Implementation
    GenericMCPClient,
    # Factory
    create_mcp_client,
)

__all__ = [
    # Connection Manager
    "BackendStatus",
    "RequestMethod",
    "BackendConfig",
    "BackendState",
    "MCPRequest",
    "MCPResponse",
    "BackendError",
    "BackendNotFoundError",
    "BackendUnavailableError",
    "BackendTimeoutError",
    "BackendRequestError",
    "BackendConnectionManager",
    "create_default_manager",
    # MCP Client
    "MCPCapability",
    "ToolCallStatus",
    "ServerInfo",
    "ToolSchema",
    "ToolResult",
    "MCPClientError",
    "MCPInitializeError",
    "MCPToolNotFoundError",
    "MCPToolCallError",
    "BaseMCPClient",
    "GenericMCPClient",
    "create_mcp_client",
]
```

---

## Acceptance Criteria

### Abstract Interface Criteria

- [ ] `BaseMCPClient` is abstract and cannot be instantiated directly
- [ ] `backend_id` property is abstract and must be implemented
- [ ] Subclasses can override `validate_tool_arguments`
- [ ] Subclasses can override `transform_tool_result`
- [ ] Subclasses can override `get_default_headers`

### Initialize Criteria

- [ ] `initialize()` sends MCP initialize request to backend
- [ ] Server info parsed and stored from response
- [ ] `is_initialized` property reflects state
- [ ] `server_info` property returns parsed ServerInfo
- [ ] `MCPInitializeError` raised on failure

### List Tools Criteria

- [ ] `list_tools()` fetches tools from backend
- [ ] Tools parsed into `ToolSchema` objects
- [ ] Results cached when `use_cache=True`
- [ ] Cache bypassed when `force_refresh=True`
- [ ] Auto-initialize if `auto_initialize=True` and not initialized

### Call Tool Criteria

- [ ] `call_tool()` sends tools/call to backend
- [ ] Tool name passed without namespace prefix
- [ ] Arguments validated via `validate_tool_arguments` hook
- [ ] Result transformed via `transform_tool_result` hook
- [ ] `ToolResult` captures success/error status
- [ ] Duration tracked in milliseconds
- [ ] Timeout returns `ToolCallStatus.TIMEOUT`

### Namespace Handling Criteria

- [ ] `strip_namespace("notion.search_pages")` returns `"search_pages"`
- [ ] `add_namespace("search_pages")` returns `"notion.search_pages"`
- [ ] `call_tool_with_namespace()` strips prefix before forwarding

### Generic Client Criteria

- [ ] `GenericMCPClient` accepts `backend_id` as constructor argument
- [ ] `create_mcp_client()` factory returns configured client
- [ ] Generic client works for any registered backend

### Test Criteria

- [ ] Test initialize success and failure
- [ ] Test list_tools with caching
- [ ] Test call_tool success and error cases
- [ ] Test namespace stripping and adding
- [ ] Test hook method overrides in subclass
- [ ] Test auto-initialize behavior
- [ ] All tests pass with `pytest tests/backends/test_base_mcp_client.py`

---

## Test Cases

Create `deeptrail-gateway/tests/backends/test_base_mcp_client.py`:

```python
"""Tests for Base MCP Client."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime, timezone

from app.backends.base_mcp_client import (
    BaseMCPClient,
    GenericMCPClient,
    ServerInfo,
    ToolSchema,
    ToolResult,
    ToolCallStatus,
    MCPCapability,
    MCPInitializeError,
    MCPClientError,
    create_mcp_client,
)
from app.backends.connection_manager import (
    BackendConnectionManager,
    MCPResponse,
    BackendTimeoutError,
    BackendUnavailableError,
)


@pytest.fixture
def mock_connection_manager():
    """Create mock connection manager."""
    manager = MagicMock(spec=BackendConnectionManager)
    return manager


@pytest.fixture
def generic_client(mock_connection_manager):
    """Create generic MCP client for testing."""
    return GenericMCPClient(
        connection_manager=mock_connection_manager,
        backend_id="notion",
    )


class TestServerInfo:
    """Tests for ServerInfo data class."""
    
    def test_from_dict_basic(self):
        """Test parsing basic server info."""
        data = {
            "name": "Test Server",
            "version": "1.0.0",
            "protocolVersion": "2024-11-05",
        }
        
        info = ServerInfo.from_dict(data)
        
        assert info.name == "Test Server"
        assert info.version == "1.0.0"
        assert info.protocol_version == "2024-11-05"
    
    def test_from_dict_with_capabilities(self):
        """Test parsing server info with capabilities."""
        data = {
            "name": "Full Server",
            "version": "2.0.0",
            "capabilities": {
                "tools": {},
                "resources": {},
            },
        }
        
        info = ServerInfo.from_dict(data)
        
        assert MCPCapability.TOOLS in info.capabilities
        assert MCPCapability.RESOURCES in info.capabilities
        assert MCPCapability.PROMPTS not in info.capabilities


class TestToolSchema:
    """Tests for ToolSchema data class."""
    
    def test_from_dict(self):
        """Test parsing tool schema."""
        data = {
            "name": "search_pages",
            "description": "Search for pages",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "query": {"type": "string"},
                },
            },
        }
        
        tool = ToolSchema.from_dict(data)
        
        assert tool.name == "search_pages"
        assert tool.description == "Search for pages"
        assert tool.input_schema["type"] == "object"
    
    def test_to_dict(self):
        """Test converting tool to dict."""
        tool = ToolSchema(
            name="read_page",
            description="Read a page",
            input_schema={"type": "object"},
        )
        
        result = tool.to_dict()
        
        assert result["name"] == "read_page"
        assert result["description"] == "Read a page"
        assert result["inputSchema"]["type"] == "object"


class TestToolResult:
    """Tests for ToolResult data class."""
    
    def test_from_response_success(self):
        """Test parsing successful response."""
        response = MCPResponse(
            result={
                "content": [{"type": "text", "text": "Found 3 pages"}],
            },
        )
        
        result = ToolResult.from_response(response, duration_ms=100)
        
        assert result.status == ToolCallStatus.SUCCESS
        assert not result.is_error
        assert result.duration_ms == 100
        assert "Found 3 pages" in result.get_text_content()
    
    def test_from_response_error(self):
        """Test parsing error response."""
        response = MCPResponse(
            error={"code": -32000, "message": "Something went wrong"},
        )
        
        result = ToolResult.from_response(response)
        
        assert result.status == ToolCallStatus.ERROR
        assert result.is_error
        assert result.error_message == "Something went wrong"
    
    def test_from_response_tool_error(self):
        """Test parsing tool that returned isError=true."""
        response = MCPResponse(
            result={
                "content": [{"type": "text", "text": "Page not found"}],
                "isError": True,
            },
        )
        
        result = ToolResult.from_response(response)
        
        assert result.status == ToolCallStatus.ERROR
        assert result.is_error
        assert result.error_message == "Page not found"


class TestBaseMCPClientAbstract:
    """Tests for abstract base class."""
    
    def test_cannot_instantiate_directly(self, mock_connection_manager):
        """Test that BaseMCPClient cannot be instantiated."""
        with pytest.raises(TypeError):
            BaseMCPClient(mock_connection_manager)


class TestGenericMCPClient:
    """Tests for GenericMCPClient."""
    
    def test_backend_id(self, generic_client):
        """Test backend_id property."""
        assert generic_client.backend_id == "notion"
    
    def test_initial_state(self, generic_client):
        """Test initial client state."""
        assert not generic_client.is_initialized
        assert generic_client.server_info is None
    
    @pytest.mark.asyncio
    async def test_initialize_success(self, generic_client, mock_connection_manager):
        """Test successful initialization."""
        mock_connection_manager.send_initialize = AsyncMock(
            return_value=MCPResponse(
                result={
                    "serverInfo": {
                        "name": "Notion MCP Server",
                        "version": "1.0.0",
                    },
                },
            )
        )
        
        info = await generic_client.initialize(auth_token="Bearer xyz")
        
        assert generic_client.is_initialized
        assert info.name == "Notion MCP Server"
        assert generic_client.server_info == info
    
    @pytest.mark.asyncio
    async def test_initialize_failure(self, generic_client, mock_connection_manager):
        """Test initialization failure."""
        mock_connection_manager.send_initialize = AsyncMock(
            return_value=MCPResponse(
                error={"code": -32000, "message": "Auth failed"},
            )
        )
        
        with pytest.raises(MCPInitializeError):
            await generic_client.initialize()
    
    @pytest.mark.asyncio
    async def test_list_tools(self, generic_client, mock_connection_manager):
        """Test listing tools."""
        mock_connection_manager.send_tools_list = AsyncMock(
            return_value=MCPResponse(
                result={
                    "tools": [
                        {"name": "search_pages", "description": "Search"},
                        {"name": "read_page", "description": "Read"},
                    ],
                },
            )
        )
        
        tools = await generic_client.list_tools(auth_token="Bearer xyz")
        
        assert len(tools) == 2
        assert tools[0].name == "search_pages"
        assert tools[1].name == "read_page"
    
    @pytest.mark.asyncio
    async def test_list_tools_caching(self, generic_client, mock_connection_manager):
        """Test that tools are cached."""
        mock_connection_manager.send_tools_list = AsyncMock(
            return_value=MCPResponse(
                result={"tools": [{"name": "tool1", "description": ""}]},
            )
        )
        
        # First call
        await generic_client.list_tools()
        # Second call should use cache
        await generic_client.list_tools()
        
        # Only one request made
        assert mock_connection_manager.send_tools_list.call_count == 1
    
    @pytest.mark.asyncio
    async def test_list_tools_force_refresh(self, generic_client, mock_connection_manager):
        """Test force refresh bypasses cache."""
        mock_connection_manager.send_tools_list = AsyncMock(
            return_value=MCPResponse(
                result={"tools": []},
            )
        )
        
        await generic_client.list_tools()
        await generic_client.list_tools(force_refresh=True)
        
        assert mock_connection_manager.send_tools_list.call_count == 2
    
    @pytest.mark.asyncio
    async def test_call_tool_success(self, generic_client, mock_connection_manager):
        """Test successful tool call."""
        mock_connection_manager.send_tools_call = AsyncMock(
            return_value=MCPResponse(
                result={
                    "content": [{"type": "text", "text": "Result"}],
                },
            )
        )
        
        result = await generic_client.call_tool(
            "search_pages",
            {"query": "test"},
            auth_token="Bearer xyz",
        )
        
        assert result.status == ToolCallStatus.SUCCESS
        assert not result.is_error
        assert result.duration_ms is not None
        
        # Verify call was made with correct params
        mock_connection_manager.send_tools_call.assert_called_once_with(
            backend_id="notion",
            tool_name="search_pages",
            arguments={"query": "test"},
            auth_header="Bearer xyz",
        )
    
    @pytest.mark.asyncio
    async def test_call_tool_timeout(self, generic_client, mock_connection_manager):
        """Test tool call timeout."""
        mock_connection_manager.send_tools_call = AsyncMock(
            side_effect=BackendTimeoutError("Timeout")
        )
        
        result = await generic_client.call_tool("search_pages", {})
        
        assert result.status == ToolCallStatus.TIMEOUT
        assert result.is_error
    
    @pytest.mark.asyncio
    async def test_call_tool_backend_unavailable(self, generic_client, mock_connection_manager):
        """Test tool call when backend unavailable."""
        mock_connection_manager.send_tools_call = AsyncMock(
            side_effect=BackendUnavailableError("Unavailable")
        )
        
        result = await generic_client.call_tool("search_pages", {})
        
        assert result.status == ToolCallStatus.ERROR
        assert result.is_error
        assert "unavailable" in result.error_message.lower()


class TestNamespaceHandling:
    """Tests for namespace handling."""
    
    def test_strip_namespace(self, generic_client):
        """Test stripping namespace prefix."""
        assert generic_client.strip_namespace("notion.search_pages") == "search_pages"
        assert generic_client.strip_namespace("notion.read_page") == "read_page"
    
    def test_strip_namespace_different_backend(self, generic_client):
        """Test stripping namespace for different backend keeps it."""
        # Different backend prefix should not be stripped
        assert generic_client.strip_namespace("slack.send_message") == "slack.send_message"
    
    def test_strip_namespace_no_prefix(self, generic_client):
        """Test stripping when no prefix present."""
        assert generic_client.strip_namespace("search_pages") == "search_pages"
    
    def test_add_namespace(self, generic_client):
        """Test adding namespace prefix."""
        assert generic_client.add_namespace("search_pages") == "notion.search_pages"
    
    def test_add_namespace_already_prefixed(self, generic_client):
        """Test adding namespace when already prefixed."""
        assert generic_client.add_namespace("notion.search_pages") == "notion.search_pages"
    
    @pytest.mark.asyncio
    async def test_call_tool_with_namespace(self, generic_client, mock_connection_manager):
        """Test calling tool with namespaced name."""
        mock_connection_manager.send_tools_call = AsyncMock(
            return_value=MCPResponse(result={"content": []})
        )
        
        await generic_client.call_tool_with_namespace(
            "notion.search_pages",
            {"query": "test"},
        )
        
        # Should strip prefix before sending
        mock_connection_manager.send_tools_call.assert_called_once()
        call_args = mock_connection_manager.send_tools_call.call_args
        assert call_args.kwargs["tool_name"] == "search_pages"


class TestSubclassHooks:
    """Tests for subclass hook methods."""
    
    @pytest.mark.asyncio
    async def test_validate_tool_arguments_hook(self, mock_connection_manager):
        """Test argument validation hook."""
        class ValidatingClient(GenericMCPClient):
            def validate_tool_arguments(self, tool_name, arguments):
                if "required_field" not in arguments:
                    raise ValueError("required_field is required")
                return arguments
        
        client = ValidatingClient(mock_connection_manager, "test")
        
        with pytest.raises(ValueError, match="required_field"):
            await client.call_tool("some_tool", {})
    
    @pytest.mark.asyncio
    async def test_transform_tool_result_hook(self, mock_connection_manager):
        """Test result transformation hook."""
        class TransformingClient(GenericMCPClient):
            def transform_tool_result(self, tool_name, result):
                # Add metadata to result
                result.raw["transformed"] = True
                return result
        
        mock_connection_manager.send_tools_call = AsyncMock(
            return_value=MCPResponse(result={"content": []})
        )
        
        client = TransformingClient(mock_connection_manager, "test")
        result = await client.call_tool("some_tool", {})
        
        assert result.raw.get("transformed") is True


class TestAutoInitialize:
    """Tests for auto-initialize behavior."""
    
    @pytest.mark.asyncio
    async def test_auto_initialize_on_list_tools(self, mock_connection_manager):
        """Test auto-initialize when listing tools."""
        client = GenericMCPClient(
            mock_connection_manager,
            "notion",
            auto_initialize=True,
        )
        
        mock_connection_manager.send_initialize = AsyncMock(
            return_value=MCPResponse(result={"serverInfo": {"name": "Test", "version": "1"}})
        )
        mock_connection_manager.send_tools_list = AsyncMock(
            return_value=MCPResponse(result={"tools": []})
        )
        
        await client.list_tools()
        
        # Should have initialized first
        mock_connection_manager.send_initialize.assert_called_once()
        mock_connection_manager.send_tools_list.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_no_auto_initialize_by_default(self, mock_connection_manager):
        """Test no auto-initialize by default."""
        client = GenericMCPClient(mock_connection_manager, "notion")
        
        mock_connection_manager.send_tools_list = AsyncMock(
            return_value=MCPResponse(result={"tools": []})
        )
        
        await client.list_tools()
        
        # Should NOT have initialized
        mock_connection_manager.send_initialize.assert_not_called()


class TestFactoryFunction:
    """Tests for create_mcp_client factory."""
    
    def test_create_mcp_client(self, mock_connection_manager):
        """Test factory creates client."""
        client = create_mcp_client(mock_connection_manager, "notion")
        
        assert isinstance(client, BaseMCPClient)
        assert client.backend_id == "notion"
    
    def test_create_mcp_client_with_options(self, mock_connection_manager):
        """Test factory passes options."""
        client = create_mcp_client(
            mock_connection_manager,
            "slack",
            auto_initialize=True,
        )
        
        assert client._auto_initialize is True
```

---

## Post-Conditions

After completing this task:

- [ ] `BaseMCPClient` provides abstract interface for all backend clients
- [ ] `GenericMCPClient` works for any registered backend
- [ ] MCP protocol operations (initialize, tools/list, tools/call) work
- [ ] Namespace stripping removes backend prefix before forwarding
- [ ] D3, D4, D5 can extend BaseMCPClient for specific backends
- [ ] D6 (Backend Router) can use clients to route calls
- [ ] All unit tests pass

---

## References

- **Design Doc Section**: 2.9 Step 8: Agent Executes Task
- **MCP Protocol**: JSON-RPC 2.0 over HTTP
- **Related Components**: 
  - [WS-D1: Backend Connection Manager](./WS-D1-backend-connection-manager.md) - HTTP transport
  - [WS-B1: MCP Protocol Parser](./WS-B1-mcp-protocol-parser.md) - JSON-RPC parsing
- **Downstream Tasks**:
  - [WS-D3: Notion MCP Client](./WS-D3-notion-client.md) - Extends BaseMCPClient
  - [WS-D4: Slack MCP Client](./WS-D4-slack-client.md) - Extends BaseMCPClient
  - [WS-D5: HubSpot MCP Client](./WS-D5-hubspot-client.md) - Extends BaseMCPClient
  - [WS-D6: Backend Router](./WS-D6-backend-router.md) - Uses clients

---

## Notes

- Uses Python's `abc` module for abstract base class pattern
- `GenericMCPClient` provides working implementation for MVP
- Hook methods allow backend-specific behavior without modifying base class
- Auto-initialize feature is opt-in for convenience
- Tool caching reduces redundant backend calls
- Namespace stripping ensures tools called with original names on backend
- Duration tracking enables performance monitoring
- For production, consider adding:
  - Request/response logging
  - Metrics collection (latency histograms)
  - Rate limiting per backend
  - Response validation against tool schema
