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
SUPPORTED_PROTOCOL_VERSIONS = ["2024-11-05", "2024-10-07"]

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
    Handle MCP initialize request.
    
    This is the first message in the MCP protocol handshake. The client sends
    its capabilities and protocol version, and we respond with ours.
    
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
    if init_params.protocolVersion not in SUPPORTED_PROTOCOL_VERSIONS:
        logger.info(
            f"Unsupported protocol version requested: {init_params.protocolVersion}. "
            f"Supported: {SUPPORTED_PROTOCOL_VERSIONS}"
        )
        raise MCPError(
            JsonRpcErrorCode.INVALID_PARAMS,
            f"Unsupported protocol version: {init_params.protocolVersion}. "
            f"Supported versions: {', '.join(SUPPORTED_PROTOCOL_VERSIONS)}"
        )
    
    # Log the connection
    logger.info(
        f"MCP initialize: client={init_params.clientInfo.name} "
        f"version={init_params.clientInfo.version} "
        f"protocol={init_params.protocolVersion}"
    )
    
    # Create agent session if session manager is configured and we have agent context
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
            # Create tools from permissions (e.g., notion:pages:search -> search_pages)
            notion_tools = []
            for perm in notion_perms:
                parts = perm.split(":")
                if len(parts) >= 3:
                    # Map permission to tool name (e.g., pages:search -> search_pages)
                    tool_name = f"{parts[2]}_{parts[1]}" if len(parts) == 3 else parts[2]
                    notion_tools.append(tool_name)
            
            connected_services.append({
                "service_id": "notion",
                "oauth_token_ref": f"vault://notion-oauth-{agent_session_id}",
                "available_tools": notion_tools or ["search_pages", "get_page"],
            })
        
        # Check for slack permissions
        slack_perms = [p for p in delegated_permissions if p.startswith("slack:")]
        if slack_perms:
            slack_tools = []
            for perm in slack_perms:
                parts = perm.split(":")
                if len(parts) >= 3:
                    tool_name = f"{parts[2]}_{parts[1]}" if len(parts) == 3 else parts[2]
                    slack_tools.append(tool_name)
            
            connected_services.append({
                "service_id": "slack",
                "oauth_token_ref": f"vault://slack-oauth-{agent_session_id}",
                "available_tools": slack_tools or ["send_message"],
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
        protocolVersion=init_params.protocolVersion,
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
