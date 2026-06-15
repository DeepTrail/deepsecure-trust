"""
Backend Connectors Package

Provides connection management, MCP clients, and routing for backend servers.

Main Components:
- BackendConnectionManager: Manages connections, pooling, health checks
- BackendRouter: Routes tool calls to appropriate backend clients
- BaseMCPClient: Abstract base class for backend MCP clients
- GenericMCPClient: Generic client for testing/MVP
- NotionMCPClient: Notion-specific MCP client
- SlackMCPClient: Slack-specific MCP client
- GDriveDirectClient: Google Drive direct REST API client (WS-D2)
- GCalendarDirectClient: Google Calendar direct REST API client (WS-D3)
- GmailDirectClient: Gmail direct REST API client (WS-D4)
- BackendConfig: Configuration for a backend server
- MCPRequest/MCPResponse: Request/response wrappers

Usage:
    from app.backends import (
        BackendConnectionManager,
        BackendRouter,
        BackendConfig,
        BaseMCPClient,
        GenericMCPClient,
        NotionMCPClient,
        SlackMCPClient,
        GDriveDirectClient,
        GCalendarDirectClient,
        GmailDirectClient,
        create_mcp_client,
        create_router,
        create_notion_client,
        create_slack_client,
        create_gdrive_direct_client,
        create_gcalendar_direct_client,
        create_gmail_direct_client,
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

from .notion_client import (
    # Type Constants
    NotionPageType,
    NotionPropertyType,
    # Exceptions
    NotionClientError,
    NotionRateLimitError,
    NotionObjectNotFoundError,
    NotionValidationError,
    # Client
    NotionMCPClient,
    # Factory
    create_notion_client,
)

from .slack_client import (
    # Type Constants
    SlackChannelType,
    # Exceptions
    SlackClientError,
    SlackRateLimitError,
    SlackChannelNotFoundError,
    SlackPermissionError,
    # Client
    SlackMCPClient,
    # Factory
    create_slack_client,
)

from .gdrive_client import (
    GDriveDirectClient,
    GDriveAPIConfig,
    create_gdrive_direct_client,
)

from .gcalendar_client import (
    GCalendarDirectClient,
    GCalendarAPIConfig,
    create_gcalendar_direct_client,
)

from .gmail_client import (
    GmailDirectClient,
    GmailAPIConfig,
    create_gmail_direct_client,
)

from .router import (
    # Router
    BackendRouter,
    # Exceptions
    RouterError,
    InvalidToolNameError,
    # Factory
    create_router,
    create_router_with_backends,
)

__all__ = [
    # Connection Manager Enums
    "BackendStatus",
    "RequestMethod",
    # Connection Manager Data Classes
    "BackendConfig",
    "BackendState",
    "MCPRequest",
    "MCPResponse",
    # Connection Manager Exceptions
    "BackendError",
    "BackendNotFoundError",
    "BackendUnavailableError",
    "BackendTimeoutError",
    "BackendRequestError",
    # Connection Manager
    "BackendConnectionManager",
    "create_default_manager",
    # MCP Client Enums
    "MCPCapability",
    "ToolCallStatus",
    # MCP Client Data Classes
    "ServerInfo",
    "ToolSchema",
    "ToolResult",
    # MCP Client Exceptions
    "MCPClientError",
    "MCPInitializeError",
    "MCPToolNotFoundError",
    "MCPToolCallError",
    # MCP Client Classes
    "BaseMCPClient",
    "GenericMCPClient",
    "create_mcp_client",
    # Notion Client
    "NotionPageType",
    "NotionPropertyType",
    "NotionClientError",
    "NotionRateLimitError",
    "NotionObjectNotFoundError",
    "NotionValidationError",
    "NotionMCPClient",
    "create_notion_client",
    # Slack Client
    "SlackChannelType",
    "SlackClientError",
    "SlackRateLimitError",
    "SlackChannelNotFoundError",
    "SlackPermissionError",
    "SlackMCPClient",
    "create_slack_client",
    # Google Drive Client (WS-D2)
    "GDriveDirectClient",
    "GDriveAPIConfig",
    "create_gdrive_direct_client",
    # Google Calendar Client (WS-D3)
    "GCalendarDirectClient",
    "GCalendarAPIConfig",
    "create_gcalendar_direct_client",
    # Gmail Client (WS-D4)
    "GmailDirectClient",
    "GmailAPIConfig",
    "create_gmail_direct_client",
    # Router
    "BackendRouter",
    "RouterError",
    "InvalidToolNameError",
    "create_router",
    "create_router_with_backends",
]
