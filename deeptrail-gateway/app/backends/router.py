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
            if self._connection_manager.is_backend_registered(backend_id):
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
            
        Note:
            Does not throw exceptions - returns ToolResult.from_error() on failure
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
            
            if result.duration_ms:
                logger.debug(
                    f"Tool {namespaced_tool} completed: "
                    f"success={not result.is_error}, "
                    f"duration={result.duration_ms:.1f}ms"
                )
            else:
                logger.debug(
                    f"Tool {namespaced_tool} completed: success={not result.is_error}"
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
                        description=f"[{backend_id.title()}] {tool.description}" if tool.description else f"[{backend_id.title()}]",
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
