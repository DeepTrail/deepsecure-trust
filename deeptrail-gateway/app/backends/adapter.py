"""
Backend Client Adapter for Virtual MCP Server.

Bridges the interface between tools_call.py and backend clients (Notion, Slack, HubSpot).

The MCP handler expects:
    call_tool(backend_id, tool_name, arguments, auth_headers: dict, mcp_session_id)
    Returns: dict with {"content": [...], "isError": bool}

Backend clients provide:
    call_tool(tool_name, arguments, auth_token: str)
    Returns: ToolResult object

This adapter bridges that gap by:
1. Extracting auth_token from auth_headers dict
2. Routing to the correct backend client based on tool name namespace
3. Converting ToolResult to MCP response dict format

Usage:
    from app.backends.adapter import create_backend_adapter

    adapter = create_backend_adapter()
    result = await adapter.call_tool(
        backend_id="notion",
        tool_name="notion.search_pages",
        arguments={"query": "test"},
        auth_headers={"Authorization": "Bearer secret_xxx"},
        mcp_session_id="session-123"
    )
"""

import json
import logging
from typing import Any, Protocol

from .base_mcp_client import ToolResult

logger = logging.getLogger(__name__)


# =============================================================================
# Protocol for Backend Clients
# =============================================================================


class BackendClient(Protocol):
    """Protocol defining the interface for backend clients."""

    async def call_tool(
        self,
        tool_name: str,
        arguments: dict[str, Any],
        auth_token: str | None = None,
    ) -> ToolResult:
        """Execute a tool call."""
        ...


# =============================================================================
# Backend Client Adapter
# =============================================================================


class BackendClientAdapter:
    """
    Adapts backend clients to the interface expected by tools_call.py.

    tools_call.py expects:
        call_tool(backend_id, tool_name, arguments, auth_headers: dict, mcp_session_id)

    Backend clients provide:
        call_tool(tool_name: str, arguments: dict, auth_token: str)

    This adapter bridges the gap by:
    - Extracting auth_token from auth_headers dict
    - Routing to correct backend by parsing namespace from tool_name
    - Converting ToolResult to MCP response dict

    Thread Safety:
        Read operations are thread-safe. Registration should be done at startup.
    """

    NAMESPACE_SEPARATOR = "."

    def __init__(self) -> None:
        """Initialize the adapter with empty client registry."""
        self._clients: dict[str, BackendClient] = {}
        self._connection_manager = None
        logger.info("BackendClientAdapter initialized")

    def set_connection_manager(self, connection_manager: "BackendConnectionManager") -> None:
        """Set the connection manager for dynamic MCP backend fallback."""
        from .connection_manager import BackendConnectionManager
        self._connection_manager = connection_manager

    def register_client(self, backend_id: str, client: BackendClient) -> None:
        """
        Register a backend client.

        Args:
            backend_id: Unique backend identifier (e.g., "notion", "slack")
            client: Backend client instance

        Raises:
            ValueError: If backend_id is empty or client is None
        """
        if not backend_id:
            raise ValueError("backend_id cannot be empty")
        if client is None:
            raise ValueError("client cannot be None")

        if backend_id in self._clients:
            logger.warning(f"Replacing existing client: {backend_id}")

        self._clients[backend_id] = client
        logger.info(f"Registered backend client: {backend_id}")

    def unregister_client(self, backend_id: str) -> None:
        """Remove a backend client from the registry."""
        if backend_id in self._clients:
            del self._clients[backend_id]
            logger.info("Unregistered backend client: %s", backend_id)

    @property
    def registered_backends(self) -> list[str]:
        """Get list of registered backend IDs."""
        return list(self._clients.keys())

    async def call_tool(
        self,
        backend_id: str,
        tool_name: str,
        arguments: dict[str, Any],
        auth_headers: dict[str, str] | None = None,
        mcp_session_id: str | None = None,
    ) -> dict[str, Any]:
        """
        Execute a tool call via the appropriate backend client.

        This method:
        1. Extracts auth_token from auth_headers
        2. Parses the namespace from tool_name to get the stripped name
        3. Routes to the registered client for backend_id
        4. Converts ToolResult to MCP response format

        Args:
            backend_id: Backend identifier (e.g., "notion")
            tool_name: Namespaced tool name (e.g., "notion.search_pages")
            arguments: Tool arguments
            auth_headers: Dict of headers, expecting {"Authorization": "Bearer xxx"}
            mcp_session_id: MCP session ID (logged for debugging)

        Returns:
            MCP-formatted result dict with "content" and "isError" keys
        """
        # Extract auth token from headers
        auth_token = self._extract_auth_token(auth_headers)

        # Parse namespace from tool name to get stripped name
        stripped_tool_name = self._strip_namespace(tool_name)

        logger.debug(
            "BackendClientAdapter routing: %s -> %s (session=%s, has_token=%s)",
            tool_name,
            backend_id,
            mcp_session_id,
            bool(auth_token),
        )

        # Get client for this backend (DirectClient or dynamic MCP fallback)
        client = self._clients.get(backend_id)
        if client is None and self._connection_manager is not None:
            if self._connection_manager.is_backend_registered(backend_id):
                from .base_mcp_client import GenericMCPClient

                client = GenericMCPClient(
                    self._connection_manager,
                    backend_id=backend_id,
                    auto_initialize=True,
                )
                self._clients[backend_id] = client
                logger.info("Auto-registered GenericMCPClient for dynamic backend: %s", backend_id)
        if client is None:
            logger.error("No client registered for backend: %s", backend_id)
            return self._error_response(f"Unknown backend: {backend_id}")

        # Call the backend client
        try:
            result: ToolResult = await client.call_tool(
                tool_name=stripped_tool_name,
                arguments=arguments,
                auth_token=auth_token,
            )

            logger.debug(
                "BackendClientAdapter result: %s success=%s",
                tool_name,
                not result.is_error,
            )

            return self._to_mcp_response(result)

        except Exception as e:
            logger.exception("BackendClientAdapter error for %s: %s", tool_name, e)
            return self._error_response(f"Backend error: {type(e).__name__}: {e}")

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

        # Return as-is if no Bearer prefix (could be API key)
        return auth_value if auth_value else None

    def _strip_namespace(self, namespaced_tool: str) -> str:
        """
        Strip namespace prefix from tool name.

        Args:
            namespaced_tool: Tool name like "notion.search_pages"

        Returns:
            Stripped name like "search_pages"
        """
        if self.NAMESPACE_SEPARATOR in namespaced_tool:
            _, tool_name = namespaced_tool.split(self.NAMESPACE_SEPARATOR, 1)
            return tool_name
        return namespaced_tool

    def _to_mcp_response(self, result: ToolResult) -> dict[str, Any]:
        """
        Convert ToolResult to MCP protocol response format.

        The MCP protocol expects:
        {
            "content": [{"type": "text", "text": "..."}],
            "isError": false
        }

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

        # Use existing content if available
        if result.content:
            return {
                "content": result.content,
                "isError": False,
            }

        # Fallback: serialize raw data
        if result.raw:
            try:
                text = json.dumps(result.raw, indent=2)
            except (TypeError, ValueError):
                text = str(result.raw)
            return {
                "content": [{"type": "text", "text": text}],
                "isError": False,
            }

        # Empty success
        return {
            "content": [{"type": "text", "text": "Success"}],
            "isError": False,
        }

    def _error_response(self, message: str) -> dict[str, Any]:
        """Create an error response dict."""
        return {
            "content": [{"type": "text", "text": message}],
            "isError": True,
        }


# =============================================================================
# Factory Function
# =============================================================================


def create_backend_adapter(*, include_builtin: bool | None = None) -> BackendClientAdapter:
    """
    Create a BackendClientAdapter.

    When ``include_builtin`` is True (default in ``hybrid`` registry mode), registers
    the six built-in DirectClients. In ``dynamic_only`` mode, starts with an empty
    adapter so the DynamicBackendLoader owns all registrations.

    Returns:
        BackendClientAdapter ready for use in tools_call handler
    """
    from app.core.config import get_settings

    adapter = BackendClientAdapter()

    if include_builtin is None:
        include_builtin = get_settings().registry_mode != "dynamic_only"

    if include_builtin:
        from .notion_client import NotionDirectClient
        from .slack_client import SlackDirectClient
        from .hubspot_client import HubSpotDirectClient
        from .gdrive_client import GDriveDirectClient
        from .gcalendar_client import GCalendarDirectClient
        from .gmail_client import GmailDirectClient

        adapter.register_client("notion", NotionDirectClient())
        adapter.register_client("slack", SlackDirectClient())
        adapter.register_client("hubspot", HubSpotDirectClient())
        adapter.register_client("gdrive", GDriveDirectClient())
        adapter.register_client("gcalendar", GCalendarDirectClient())
        adapter.register_client("gmail", GmailDirectClient())

    logger.info(
        "BackendClientAdapter created with backends: %s (include_builtin=%s)",
        adapter.registered_backends,
        include_builtin,
    )

    return adapter
