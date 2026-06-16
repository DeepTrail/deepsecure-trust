"""
MCP Initialize Handler

This module implements the `initialize` method handler for the MCP protocol.
The initialize handler is the first message in the MCP protocol handshake -
it exchanges capabilities between client (agent) and server (gateway).

MCP Specification Reference:
https://spec.modelcontextprotocol.io/specification/basic/lifecycle/

Usage:
    from app.mcp.handlers import handle_initialize
    from app.mcp.protocol import MCPProtocolHandler
    
    handler = MCPProtocolHandler()
    handler.register_handler("initialize", handle_initialize)
"""

import logging
from typing import Any

from pydantic import BaseModel, Field, field_validator

from ..permission_mapper import PermissionMapper
from ..protocol import JsonRpcErrorCode, MCPError
from ..session_manager import MCPSessionManager

logger = logging.getLogger(__name__)

# Global session manager - will be set during app initialization
_session_manager: MCPSessionManager | None = None


def configure_initialize_handler(session_manager: MCPSessionManager) -> None:
    """Configure the initialize handler with required dependencies."""
    global _session_manager
    _session_manager = session_manager
    logger.info("initialize handler configured")


def get_session_manager() -> MCPSessionManager | None:
    """Get the configured session manager (can be None for MVP)."""
    return _session_manager

# =============================================================================
# Constants
# =============================================================================

# Supported MCP protocol versions
# https://spec.modelcontextprotocol.io/specification/basic/lifecycle/#version-negotiation
SUPPORTED_PROTOCOL_VERSIONS = ["2026-07-28", "2025-11-25", "2024-11-05", "2024-10-07"]

# Server metadata returned in initialize response
SERVER_INFO = {
    "name": "DeepTrail Virtual MCP Server",
    "version": "0.1.0",
}

# Server capabilities advertised to clients
# We support tools (the core MCP feature for Virtual MCP Server)
SERVER_CAPABILITIES = {
    "tools": {
        "listChanged": True,  # We can notify when tool list changes
    },
}


# =============================================================================
# Request/Response Models
# =============================================================================


class ClientInfo(BaseModel):
    """
    Information about the MCP client.
    
    Attributes:
        name: Human-readable name of the client
        version: Client version string
    """
    name: str = Field(..., description="Client name")
    version: str = Field(default="", description="Client version")
    
    @field_validator("name")
    @classmethod
    def validate_name_not_empty(cls, v: str) -> str:
        """Validate that name is not empty."""
        if not v or not v.strip():
            raise ValueError("clientInfo.name must not be empty")
        return v


class InitializeParams(BaseModel):
    """
    Parameters for the MCP initialize request.
    
    Attributes:
        protocolVersion: MCP protocol version requested by client
        capabilities: Client capabilities object
        clientInfo: Information about the client
    """
    protocolVersion: str = Field(..., alias="protocolVersion", description="Requested protocol version")
    capabilities: dict[str, Any] = Field(default_factory=dict, description="Client capabilities")
    clientInfo: ClientInfo = Field(..., alias="clientInfo", description="Client information")
    
    model_config = {"populate_by_name": True}
    
    @field_validator("protocolVersion")
    @classmethod
    def validate_protocol_version_format(cls, v: str) -> str:
        """Validate protocol version format (YYYY-MM-DD)."""
        if not v or not v.strip():
            raise ValueError("protocolVersion must not be empty")
        # Basic format validation (YYYY-MM-DD)
        parts = v.split("-")
        if len(parts) != 3:
            raise ValueError(f"Invalid protocolVersion format: {v} (expected YYYY-MM-DD)")
        return v


class InitializeResult(BaseModel):
    """
    Result for the MCP initialize response.
    
    Attributes:
        protocolVersion: The negotiated protocol version
        capabilities: Server capabilities
        serverInfo: Information about the server
    """
    protocolVersion: str = Field(..., description="Negotiated protocol version")
    capabilities: dict[str, Any] = Field(default_factory=dict, description="Server capabilities")
    serverInfo: dict[str, str] = Field(default_factory=dict, description="Server information")
    
    model_config = {"populate_by_name": True}


# =============================================================================
# Handler Implementation
# =============================================================================


async def handle_initialize(params: dict[str, Any]) -> dict[str, Any]:
    """
    Handle MCP initialize request (B7: optional for MCP 2026-07-28).
    
    For 2025-11-25 clients this is the first message in the MCP handshake.
    For 2026-07-28 clients this is optional — tools/list and tools/call work
    without it because JWT claims provide all necessary context.
    
    Args:
        params: Initialize request parameters containing:
            - protocolVersion: Requested protocol version (e.g., "2024-11-05")
            - capabilities: Client capabilities object
            - clientInfo: Client identification (name, version)
    
    Returns:
        Initialize result containing:
            - protocolVersion: Negotiated version
            - capabilities: Server capabilities (tools support)
            - serverInfo: Server identification
    
    Raises:
        MCPError: If protocol version is unsupported or required params missing
    
    Example:
        >>> await handle_initialize({
        ...     "protocolVersion": "2024-11-05",
        ...     "capabilities": {},
        ...     "clientInfo": {"name": "TestAgent", "version": "1.0.0"}
        ... })
        {
            "protocolVersion": "2024-11-05",
            "capabilities": {"tools": {"listChanged": True}},
            "serverInfo": {"name": "DeepTrail Virtual MCP Server", "version": "0.1.0"}
        }
    """
    # Extract context before removing (passed by MCPProtocolHandler)
    context = params.pop("_context", {})
    
    # Remove any other internal params
    params = {k: v for k, v in params.items() if not k.startswith("_")}
    
    # Validate and parse params
    try:
        init_params = InitializeParams(**params)
    except Exception as e:
        logger.warning(f"Invalid initialize params: {e}")
        raise MCPError(
            JsonRpcErrorCode.INVALID_PARAMS,
            f"Invalid initialize parameters: {_sanitize_error(e)}"
        )
    
    # Validate protocol version is supported
    # Per MCP spec: server SHOULD negotiate down to its latest supported version
    # rather than rejecting the request outright
    negotiated_version = init_params.protocolVersion
    if init_params.protocolVersion not in SUPPORTED_PROTOCOL_VERSIONS:
        negotiated_version = SUPPORTED_PROTOCOL_VERSIONS[0]  # latest supported
        logger.info(
            f"Protocol version negotiation: client requested {init_params.protocolVersion}, "
            f"server responding with {negotiated_version}"
        )
    
    # Log the connection
    logger.info(
        f"MCP initialize: client={init_params.clientInfo.name} "
        f"version={init_params.clientInfo.version} "
        f"protocol={init_params.protocolVersion}"
    )
    
    # B6: Session creation is an optional optimization — JWT is the source of truth.
    # Handlers (tools/list, tools/call) work without sessions via stateless paths.
    agent_session_id = context.get("agent_session_id")
    delegated_permissions = context.get("delegated_permissions", [])
    delegator = context.get("delegator", "")
    
    session_manager = get_session_manager()
    if session_manager and agent_session_id:
        # Create mock backend sessions based on permissions
        # For MVP, we create backend sessions for notion and slack if permissions exist
        connected_services = []
        
        # Check for notion permissions
        notion_perms = [p for p in delegated_permissions if p.startswith("notion:")]
        if notion_perms:
            # Use Permission Mapper to get correct tool names
            notion_tools = []
            for perm in notion_perms:
                # Get all tools that require this permission
                tools = PermissionMapper.get_all_tools_for_permission(perm)
                for tool in tools:
                    # Extract tool name without namespace (e.g., "notion.search_pages" → "search_pages")
                    if "." in tool:
                        _, tool_name = tool.split(".", 1)
                        notion_tools.append(tool_name)
            
            # Remove duplicates while preserving order
            notion_tools = list(dict.fromkeys(notion_tools))
            
            if notion_tools:
                connected_services.append({
                    "service_id": "notion",
                    "oauth_token_ref": f"vault://notion-oauth-{agent_session_id}",
                    "available_tools": notion_tools,
                })
        
        # Check for slack permissions
        slack_perms = [p for p in delegated_permissions if p.startswith("slack:")]
        if slack_perms:
            # Use Permission Mapper to get correct tool names
            slack_tools = []
            for perm in slack_perms:
                tools = PermissionMapper.get_all_tools_for_permission(perm)
                for tool in tools:
                    if "." in tool:
                        _, tool_name = tool.split(".", 1)
                        slack_tools.append(tool_name)
            
            slack_tools = list(dict.fromkeys(slack_tools))
            
            if slack_tools:
                connected_services.append({
                    "service_id": "slack",
                    "oauth_token_ref": f"vault://slack-oauth-{agent_session_id}",
                    "available_tools": slack_tools,
                })
        
        # Check for gdrive permissions (WS-D5)
        gdrive_perms = [p for p in delegated_permissions if p.startswith("gdrive:")]
        if gdrive_perms:
            gdrive_tools = []
            for perm in gdrive_perms:
                tools = PermissionMapper.get_all_tools_for_permission(perm)
                for tool in tools:
                    if "." in tool:
                        _, tool_name = tool.split(".", 1)
                        gdrive_tools.append(tool_name)

            gdrive_tools = list(dict.fromkeys(gdrive_tools))

            if gdrive_tools:
                connected_services.append({
                    "service_id": "gdrive",
                    "oauth_token_ref": f"vault://gdrive-oauth-{agent_session_id}",
                    "available_tools": gdrive_tools,
                })

        # Check for gcalendar permissions (WS-D5)
        gcalendar_perms = [p for p in delegated_permissions if p.startswith("gcalendar:")]
        if gcalendar_perms:
            gcalendar_tools = []
            for perm in gcalendar_perms:
                tools = PermissionMapper.get_all_tools_for_permission(perm)
                for tool in tools:
                    if "." in tool:
                        _, tool_name = tool.split(".", 1)
                        gcalendar_tools.append(tool_name)

            gcalendar_tools = list(dict.fromkeys(gcalendar_tools))

            if gcalendar_tools:
                connected_services.append({
                    "service_id": "gcalendar",
                    "oauth_token_ref": f"vault://gcalendar-oauth-{agent_session_id}",
                    "available_tools": gcalendar_tools,
                })

        # Check for gmail permissions (WS-D5)
        gmail_perms = [p for p in delegated_permissions if p.startswith("gmail:")]
        if gmail_perms:
            gmail_tools = []
            for perm in gmail_perms:
                tools = PermissionMapper.get_all_tools_for_permission(perm)
                for tool in tools:
                    if "." in tool:
                        _, tool_name = tool.split(".", 1)
                        gmail_tools.append(tool_name)

            gmail_tools = list(dict.fromkeys(gmail_tools))

            if gmail_tools:
                connected_services.append({
                    "service_id": "gmail",
                    "oauth_token_ref": f"vault://gmail-oauth-{agent_session_id}",
                    "available_tools": gmail_tools,
                })

        # Check for github permissions
        github_perms = [p for p in delegated_permissions if p.startswith("github:")]
        if github_perms:
            github_tools = []
            for perm in github_perms:
                tools = PermissionMapper.get_all_tools_for_permission(perm)
                for tool in tools:
                    if "." in tool:
                        _, tool_name = tool.split(".", 1)
                        github_tools.append(tool_name)

            github_tools = list(dict.fromkeys(github_tools))

            if github_tools:
                connected_services.append({
                    "service_id": "github",
                    "oauth_token_ref": f"vault://github-oauth-{agent_session_id}",
                    "available_tools": github_tools,
                })

        # Create the agent session
        try:
            session_manager.create_agent_session(
                agent_session_id=agent_session_id,
                delegator=delegator,
                delegated_permissions=delegated_permissions,
                connected_services=connected_services,
            )
            logger.info(
                f"Created agent session: {agent_session_id} for {delegator} "
                f"with {len(connected_services)} backend(s)"
            )
        except Exception as e:
            logger.warning(f"Failed to create agent session: {e}")
    
    # Build response
    result = InitializeResult(
        protocolVersion=negotiated_version,
        capabilities=SERVER_CAPABILITIES,
        serverInfo=SERVER_INFO,
    )
    
    return result.model_dump(by_alias=True)


def _sanitize_error(error: Exception) -> str:
    """
    Sanitize error message to avoid exposing internal details.
    
    Args:
        error: The exception to sanitize
        
    Returns:
        Safe error message string
    """
    # Get the first line of the error message
    message = str(error).split("\n")[0]
    # Limit length
    if len(message) > 200:
        message = message[:200] + "..."
    return message
