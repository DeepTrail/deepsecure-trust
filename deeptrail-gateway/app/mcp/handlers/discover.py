"""
MCP server/discover handler (MCP 2026-07-28).

Returns server metadata and capabilities without requiring an active session.
This endpoint enables MCP clients to discover the server's supported protocol
versions, capabilities, and auth requirements before calling initialize.
"""

import logging
from typing import Any

from .initialize import SUPPORTED_PROTOCOL_VERSIONS, SERVER_INFO, SERVER_CAPABILITIES

logger = logging.getLogger(__name__)


async def handle_discover(params: dict[str, Any]) -> dict[str, Any]:
    """
    Handle server/discover request.

    Returns server metadata including:
    - Supported protocol versions
    - Server identity
    - Capabilities
    - Protected Resource Metadata URL (for OAuth discovery)
    """
    context = params.pop("_context", {})
    agent_id = context.get("agent_id", "anonymous")

    logger.info("server/discover from agent %s", agent_id)

    return {
        "protocolVersions": SUPPORTED_PROTOCOL_VERSIONS,
        "serverInfo": SERVER_INFO,
        "capabilities": SERVER_CAPABILITIES,
    }
