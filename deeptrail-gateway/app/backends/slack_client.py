"""
Slack MCP Client

Extends BaseMCPClient to provide Slack-specific tool operations.
Proxies MCP requests to a Slack MCP server backend.

MVP Tools:
- search_messages: Search messages in workspace
- send_message: Send message to a channel
- list_channels: List accessible channels
- join_channel: Join a channel
- post_reaction: Add reaction to a message
- list_users: List workspace users

Usage:
    from app.backends.slack_client import SlackMCPClient
    
    client = SlackMCPClient(connection_manager)
    await client.initialize(auth_token="Bearer xyz")
    
    # Search messages
    result = await client.search_messages(
        query="meeting notes",
        auth_token="Bearer xyz"
    )
"""

import logging
import re
from typing import Any

from .base_mcp_client import (
    BaseMCPClient,
    BackendConnectionManager,
    ToolResult,
    ToolCallStatus,
)

logger = logging.getLogger(__name__)


# =============================================================================
# Slack-Specific Types
# =============================================================================


class SlackChannelType:
    """Slack channel types."""
    PUBLIC = "public_channel"
    PRIVATE = "private_channel"
    MPIM = "mpim"
    IM = "im"


# =============================================================================
# Exceptions
# =============================================================================


class SlackClientError(Exception):
    """Slack-specific client error."""
    pass


class SlackRateLimitError(SlackClientError):
    """Slack API rate limit exceeded."""
    pass


class SlackChannelNotFoundError(SlackClientError):
    """Slack channel not found."""
    pass


class SlackPermissionError(SlackClientError):
    """Insufficient permissions for Slack operation."""
    pass


# =============================================================================
# Slack MCP Client
# =============================================================================


class SlackMCPClient(BaseMCPClient):
    """
    MCP client for Slack backend.
    
    Provides Slack-specific:
    - Argument validation for Slack tools
    - Result transformation for Slack responses
    - Error handling for Slack API errors
    
    Attributes:
        backend_id: Always "slack"
    """
    
    # Channel ID pattern: C/D/G followed by alphanumeric
    CHANNEL_ID_PATTERN = re.compile(r"^[CDG][A-Z0-9]{8,}$")
    
    # User ID pattern: U/W followed by alphanumeric
    USER_ID_PATTERN = re.compile(r"^[UW][A-Z0-9]{8,}$")
    
    # Message timestamp pattern: epoch.sequence
    TIMESTAMP_PATTERN = re.compile(r"^\d+\.\d+$")
    
    # Tool-specific argument schemas for validation
    TOOL_SCHEMAS: dict[str, dict[str, list[str]]] = {
        "search_messages": {
            "required": ["query"],
            "optional": ["sort", "sort_dir", "count", "page"],
        },
        "send_message": {
            "required": ["channel", "text"],
            "optional": ["thread_ts", "blocks", "attachments", "unfurl_links", "unfurl_media"],
        },
        "list_channels": {
            "required": [],
            "optional": ["types", "limit", "cursor", "exclude_archived"],
        },
        "join_channel": {
            "required": ["channel"],
            "optional": [],
        },
        "post_reaction": {
            "required": ["channel", "timestamp", "name"],
            "optional": [],
        },
        "list_users": {
            "required": [],
            "optional": ["limit", "cursor", "include_locale"],
        },
    }
    
    @property
    def backend_id(self) -> str:
        """Return the Slack backend identifier."""
        return "slack"
    
    # ─────────────────────────────────────────────────────────────────────────
    # Argument Validation
    # ─────────────────────────────────────────────────────────────────────────
    
    def validate_tool_arguments(
        self,
        tool_name: str,
        arguments: dict[str, Any],
    ) -> dict[str, Any]:
        """
        Validate and transform Slack tool arguments.
        
        Args:
            tool_name: Slack tool name
            arguments: Raw arguments
            
        Returns:
            Validated arguments
            
        Raises:
            ValueError: If required arguments missing or invalid
        """
        schema = self.TOOL_SCHEMAS.get(tool_name)
        
        if schema is None:
            # Unknown tool - pass through to backend
            logger.warning(f"No schema for Slack tool: {tool_name}")
            return arguments
        
        # Check required arguments
        missing = [
            arg for arg in schema["required"]
            if arg not in arguments or arguments[arg] is None
        ]
        
        if missing:
            raise ValueError(
                f"Missing required arguments for {tool_name}: {', '.join(missing)}"
            )
        
        # Validate specific arguments
        validated = dict(arguments)
        
        # Validate channel ID format
        if "channel" in validated:
            validated["channel"] = self._validate_channel_id(validated["channel"])
        
        # Validate timestamp format
        if "timestamp" in validated:
            validated["timestamp"] = self._validate_timestamp(validated["timestamp"])
        
        if "thread_ts" in validated and validated["thread_ts"]:
            validated["thread_ts"] = self._validate_timestamp(validated["thread_ts"])
        
        # Validate count/limit ranges
        if "count" in validated:
            count = validated["count"]
            if not isinstance(count, int) or count < 1 or count > 100:
                raise ValueError("count must be integer between 1 and 100")
        
        if "limit" in validated:
            limit = validated["limit"]
            if not isinstance(limit, int) or limit < 1 or limit > 1000:
                raise ValueError("limit must be integer between 1 and 1000")
        
        # Validate reaction name (emoji name without colons)
        if "name" in validated and tool_name == "post_reaction":
            validated["name"] = self._validate_reaction_name(validated["name"])
        
        return validated
    
    def _validate_channel_id(self, channel: str) -> str:
        """
        Validate Slack channel ID format.
        
        Slack channel IDs start with:
        - C: Public channel
        - D: DM
        - G: Private channel or group DM
        
        Args:
            channel: Channel ID or name
            
        Returns:
            Validated channel ID
            
        Raises:
            ValueError: If format is invalid
        """
        if not channel:
            raise ValueError("Channel ID cannot be empty")
        
        # If it looks like a channel ID, validate format
        if channel[0] in "CDG" and len(channel) > 8:
            if not self.CHANNEL_ID_PATTERN.match(channel):
                raise ValueError(f"Invalid channel ID format: {channel}")
        # Otherwise assume it's a channel name (let backend resolve)
        
        return channel
    
    def _validate_timestamp(self, timestamp: str) -> str:
        """
        Validate Slack message timestamp format.
        
        Format: epoch.sequence (e.g., "1234567890.123456")
        
        Args:
            timestamp: Message timestamp
            
        Returns:
            Validated timestamp
            
        Raises:
            ValueError: If format is invalid
        """
        if not timestamp:
            raise ValueError("Timestamp cannot be empty")
        
        if not self.TIMESTAMP_PATTERN.match(timestamp):
            raise ValueError(
                f"Invalid timestamp format: {timestamp}. "
                "Expected format: epoch.sequence (e.g., 1234567890.123456)"
            )
        
        return timestamp
    
    def _validate_reaction_name(self, name: str) -> str:
        """
        Validate and normalize reaction (emoji) name.
        
        Removes surrounding colons if present.
        
        Args:
            name: Reaction name (e.g., "thumbsup" or ":thumbsup:")
            
        Returns:
            Normalized reaction name without colons
        """
        if not name:
            raise ValueError("Reaction name cannot be empty")
        
        # Remove surrounding colons if present
        normalized = name.strip(":")
        
        if not normalized:
            raise ValueError("Reaction name cannot be empty after removing colons")
        
        return normalized
    
    # ─────────────────────────────────────────────────────────────────────────
    # Result Transformation
    # ─────────────────────────────────────────────────────────────────────────
    
    def transform_tool_result(
        self,
        tool_name: str,
        result: ToolResult,
    ) -> ToolResult:
        """
        Transform Slack tool results.
        
        Handles:
        - Rate limit errors (ratelimited)
        - Channel not found errors
        - Permission errors (missing_scope, not_in_channel)
        - Extracting useful content from responses
        
        Args:
            tool_name: Tool that was called
            result: Raw result from backend
            
        Returns:
            Transformed result
        """
        # Check for Slack-specific errors in the result
        if result.is_error:
            result = self._transform_error(tool_name, result)
        
        return result
    
    def _transform_error(self, tool_name: str, result: ToolResult) -> ToolResult:
        """Transform Slack error responses."""
        error_msg = result.error_message or ""
        error_lower = error_msg.lower()
        
        # Detect rate limiting
        if "ratelimited" in error_lower or "rate_limited" in error_lower:
            logger.warning(f"Slack rate limit hit for {tool_name}")
            return ToolResult(
                status=ToolCallStatus.ERROR,
                is_error=True,
                error_message="Slack rate limit exceeded. Please wait before retrying.",
                content=[{"type": "text", "text": "Rate limit exceeded"}],
                raw=result.raw,
                duration_ms=result.duration_ms,
            )
        
        # Detect channel not found
        if "channel_not_found" in error_lower:
            return ToolResult(
                status=ToolCallStatus.ERROR,
                is_error=True,
                error_message="Slack channel not found or not accessible",
                content=[{"type": "text", "text": "Channel not found"}],
                raw=result.raw,
                duration_ms=result.duration_ms,
            )
        
        # Detect permission errors
        if any(err in error_lower for err in ["missing_scope", "not_in_channel", "channel_not_member"]):
            return ToolResult(
                status=ToolCallStatus.ERROR,
                is_error=True,
                error_message=f"Insufficient permissions for Slack operation: {error_msg}",
                content=[{"type": "text", "text": f"Permission denied: {error_msg}"}],
                raw=result.raw,
                duration_ms=result.duration_ms,
            )
        
        # Detect not authed
        if "not_authed" in error_lower or "invalid_auth" in error_lower:
            return ToolResult(
                status=ToolCallStatus.UNAUTHORIZED,
                is_error=True,
                error_message="Slack authentication failed",
                content=[{"type": "text", "text": "Authentication failed"}],
                raw=result.raw,
                duration_ms=result.duration_ms,
            )
        
        # Detect message not found (for reactions)
        if "message_not_found" in error_lower:
            return ToolResult(
                status=ToolCallStatus.ERROR,
                is_error=True,
                error_message="Slack message not found",
                content=[{"type": "text", "text": "Message not found"}],
                raw=result.raw,
                duration_ms=result.duration_ms,
            )
        
        return result
    
    # ─────────────────────────────────────────────────────────────────────────
    # Convenience Methods
    # ─────────────────────────────────────────────────────────────────────────
    
    async def search_messages(
        self,
        query: str,
        count: int = 20,
        sort: str = "timestamp",
        auth_token: str | None = None,
    ) -> ToolResult:
        """
        Search for messages in the Slack workspace.
        
        Args:
            query: Search query string
            count: Number of results (1-100)
            sort: Sort order ("timestamp" or "score")
            auth_token: Authorization token
            
        Returns:
            ToolResult with search results
        """
        return await self.call_tool(
            "search_messages",
            {"query": query, "count": count, "sort": sort},
            auth_token=auth_token,
        )
    
    async def send_message(
        self,
        channel: str,
        text: str,
        thread_ts: str | None = None,
        auth_token: str | None = None,
    ) -> ToolResult:
        """
        Send a message to a Slack channel.
        
        Args:
            channel: Channel ID or name
            text: Message text
            thread_ts: Thread timestamp for replies
            auth_token: Authorization token
            
        Returns:
            ToolResult with sent message info
        """
        arguments: dict[str, Any] = {"channel": channel, "text": text}
        if thread_ts:
            arguments["thread_ts"] = thread_ts
        
        return await self.call_tool("send_message", arguments, auth_token=auth_token)
    
    async def list_channels(
        self,
        types: str = "public_channel,private_channel",
        limit: int = 100,
        exclude_archived: bool = True,
        auth_token: str | None = None,
    ) -> ToolResult:
        """
        List accessible channels in the workspace.
        
        Args:
            types: Channel types to include (comma-separated)
            limit: Maximum channels to return
            exclude_archived: Whether to exclude archived channels
            auth_token: Authorization token
            
        Returns:
            ToolResult with channel list
        """
        return await self.call_tool(
            "list_channels",
            {
                "types": types,
                "limit": limit,
                "exclude_archived": exclude_archived,
            },
            auth_token=auth_token,
        )
    
    async def join_channel(
        self,
        channel: str,
        auth_token: str | None = None,
    ) -> ToolResult:
        """
        Join a Slack channel.
        
        Args:
            channel: Channel ID
            auth_token: Authorization token
            
        Returns:
            ToolResult with join result
        """
        return await self.call_tool(
            "join_channel",
            {"channel": channel},
            auth_token=auth_token,
        )
    
    async def post_reaction(
        self,
        channel: str,
        timestamp: str,
        name: str,
        auth_token: str | None = None,
    ) -> ToolResult:
        """
        Add a reaction to a message.
        
        Args:
            channel: Channel containing the message
            timestamp: Message timestamp
            name: Reaction emoji name (without colons)
            auth_token: Authorization token
            
        Returns:
            ToolResult with reaction result
        """
        return await self.call_tool(
            "post_reaction",
            {"channel": channel, "timestamp": timestamp, "name": name},
            auth_token=auth_token,
        )
    
    async def list_users(
        self,
        limit: int = 100,
        auth_token: str | None = None,
    ) -> ToolResult:
        """
        List users in the workspace.
        
        Args:
            limit: Maximum users to return
            auth_token: Authorization token
            
        Returns:
            ToolResult with user list
        """
        return await self.call_tool(
            "list_users",
            {"limit": limit},
            auth_token=auth_token,
        )


# =============================================================================
# Factory Function
# =============================================================================


def create_slack_client(
    connection_manager: BackendConnectionManager,
    **kwargs: Any,
) -> SlackMCPClient:
    """
    Create a Slack MCP client.
    
    Args:
        connection_manager: Backend connection manager
        **kwargs: Additional client options
        
    Returns:
        Configured SlackMCPClient
    """
    return SlackMCPClient(connection_manager, **kwargs)
