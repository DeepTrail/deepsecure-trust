# Task: WS-D4 Implement Slack MCP Client

---

## Metadata

| Field | Value |
|-------|-------|
| **Status** | `ready` |
| **Design Doc** | [deepsecure-virtual-mcp-server-mvp.md](../../../design/internal/markdowns/deepsecure-virtual-mcp-server-mvp.md) |
| **Workstream** | WS-D: Backend Connectors |
| **Dependencies** | D2 (Base MCP Client) ✅ |
| **Blocked By** | None (D2 complete) |
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

- [x] D2 (Base MCP Client) is complete
- [x] D1 (Backend Connection Manager) is complete
- [x] `BaseMCPClient` class available in `app/backends/base_mcp_client.py`
- [x] `BackendConnectionManager` available for HTTP transport
- [ ] Slack API documentation reviewed for tool schemas

---

## Task Description

Implement the Slack MCP client that extends `BaseMCPClient` to provide Slack-specific tool operations. This enables the gateway to proxy MCP requests to a Slack MCP server backend.

### Context

From the MVP design (Section 2.6 - Step 8: Agent Executes Task):

```
Sarah's agent needs to access Slack tools:
- search_messages: Search messages across channels
- send_message: Send a message to a channel
- list_channels: List available channels

The Slack MCP client:
1. Extends BaseMCPClient with backend_id = "slack"
2. Provides Slack-specific argument validation
3. Transforms Slack API responses to standard MCP format
4. Handles Slack-specific error cases (rate limits, permissions)
```

### MVP Slack Tools

| Tool Name | Permission | Description |
|-----------|------------|-------------|
| `search_messages` | `slack:messages:search` | Search messages in workspace |
| `send_message` | `slack:messages:send` | Send message to a channel |
| `list_channels` | `slack:channels:list` | List accessible channels |
| `join_channel` | `slack:channels:join` | Join a channel |
| `post_reaction` | `slack:reactions:write` | Add reaction to a message |
| `list_users` | `slack:users:list` | List workspace users |

---

## Files to Create/Modify

| File | Action | Description |
|------|--------|-------------|
| `deeptrail-gateway/app/backends/slack_client.py` | **CREATE** | Slack MCP client implementation |
| `deeptrail-gateway/app/backends/__init__.py` | **MODIFY** | Export SlackMCPClient |
| `deeptrail-gateway/tests/backends/test_slack_client.py` | **CREATE** | Unit tests |

---

## Implementation Details

### 1. Slack MCP Client

Create `deeptrail-gateway/app/backends/slack_client.py`:

```python
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
    result = await client.call_tool(
        "search_messages",
        {"query": "meeting notes"},
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
    TOOL_SCHEMAS = {
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
        arguments = {"channel": channel, "text": text}
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
```

### 2. Update `__init__.py`

Add to `deeptrail-gateway/app/backends/__init__.py`:

```python
from .slack_client import (
    SlackMCPClient,
    SlackClientError,
    SlackRateLimitError,
    SlackChannelNotFoundError,
    SlackPermissionError,
    create_slack_client,
)

__all__ = [
    # ... existing exports ...
    # Slack client
    "SlackMCPClient",
    "SlackClientError",
    "SlackRateLimitError",
    "SlackChannelNotFoundError",
    "SlackPermissionError",
    "create_slack_client",
]
```

---

## Acceptance Criteria

### Implementation Criteria

- [ ] `SlackMCPClient` extends `BaseMCPClient`
- [ ] `backend_id` property returns `"slack"`
- [ ] Implements `validate_tool_arguments()` for Slack tools
- [ ] Implements `transform_tool_result()` for Slack responses

### Tool Support Criteria

- [ ] `search_messages` tool supported with query parameter
- [ ] `send_message` tool supported with channel and text
- [ ] `list_channels` tool supported with types filter
- [ ] `join_channel` tool supported
- [ ] `post_reaction` tool supported with emoji name
- [ ] `list_users` tool supported

### Validation Criteria

- [ ] Missing required arguments raise `ValueError`
- [ ] Invalid channel ID format logged (but allows names)
- [ ] Timestamp format validated (epoch.sequence)
- [ ] Reaction name normalized (colons removed)
- [ ] count/limit validated within ranges

### Error Handling Criteria

- [ ] Rate limit errors (ratelimited) transformed
- [ ] Channel not found errors transformed
- [ ] Permission errors (missing_scope) transformed
- [ ] Auth errors (not_authed) transformed
- [ ] Errors logged at appropriate levels

### Test Criteria

- [ ] Test `backend_id` property
- [ ] Test argument validation for each tool
- [ ] Test channel ID validation
- [ ] Test timestamp validation
- [ ] Test reaction name normalization
- [ ] Test error transformation for rate limits
- [ ] Test error transformation for permissions
- [ ] Test convenience methods
- [ ] All tests pass with `pytest tests/backends/test_slack_client.py`

---

## Test Cases

Create `deeptrail-gateway/tests/backends/test_slack_client.py`:

```python
"""Tests for Slack MCP client (D4)."""

import pytest
from unittest.mock import AsyncMock, MagicMock

from app.backends.slack_client import (
    SlackMCPClient,
    SlackClientError,
    create_slack_client,
)
from app.backends.base_mcp_client import ToolResult, ToolCallStatus


@pytest.fixture
def mock_connection_manager():
    """Create mock connection manager."""
    manager = MagicMock()
    manager.send_initialize = AsyncMock()
    manager.send_tools_list = AsyncMock()
    manager.send_tools_call = AsyncMock()
    manager.check_backend_health = AsyncMock(return_value=True)
    return manager


@pytest.fixture
def slack_client(mock_connection_manager):
    """Create Slack client with mock connection manager."""
    return SlackMCPClient(mock_connection_manager)


class TestSlackMCPClient:
    """Tests for SlackMCPClient."""
    
    def test_backend_id(self, slack_client):
        """Test backend_id is 'slack'."""
        assert slack_client.backend_id == "slack"
    
    def test_repr(self, slack_client):
        """Test string representation."""
        assert "SlackMCPClient" in repr(slack_client)
        assert "slack" in repr(slack_client)


class TestArgumentValidation:
    """Tests for argument validation."""
    
    def test_search_messages_requires_query(self, slack_client):
        """Test search_messages requires query."""
        with pytest.raises(ValueError) as exc:
            slack_client.validate_tool_arguments("search_messages", {})
        assert "query" in str(exc.value)
    
    def test_search_messages_with_query(self, slack_client):
        """Test search_messages with valid query."""
        args = {"query": "meeting notes", "count": 50}
        result = slack_client.validate_tool_arguments("search_messages", args)
        assert result["query"] == "meeting notes"
        assert result["count"] == 50
    
    def test_send_message_requires_channel_and_text(self, slack_client):
        """Test send_message requires channel and text."""
        with pytest.raises(ValueError) as exc:
            slack_client.validate_tool_arguments("send_message", {"channel": "C123"})
        assert "text" in str(exc.value)
    
    def test_send_message_valid(self, slack_client):
        """Test send_message with valid args."""
        args = {"channel": "C12345678", "text": "Hello world"}
        result = slack_client.validate_tool_arguments("send_message", args)
        assert result["channel"] == "C12345678"
        assert result["text"] == "Hello world"
    
    def test_list_channels_no_required_args(self, slack_client):
        """Test list_channels has no required args."""
        result = slack_client.validate_tool_arguments("list_channels", {})
        assert result == {}
    
    def test_post_reaction_requires_all(self, slack_client):
        """Test post_reaction requires channel, timestamp, name."""
        with pytest.raises(ValueError):
            slack_client.validate_tool_arguments("post_reaction", {"channel": "C123"})
    
    def test_count_validation(self, slack_client):
        """Test count must be 1-100."""
        with pytest.raises(ValueError) as exc:
            slack_client.validate_tool_arguments("search_messages", {"query": "test", "count": 101})
        assert "count" in str(exc.value)
    
    def test_limit_validation(self, slack_client):
        """Test limit must be 1-1000."""
        with pytest.raises(ValueError) as exc:
            slack_client.validate_tool_arguments("list_channels", {"limit": 1001})
        assert "limit" in str(exc.value)


class TestChannelIDValidation:
    """Tests for channel ID validation."""
    
    def test_valid_public_channel(self, slack_client):
        """Test valid public channel ID."""
        result = slack_client._validate_channel_id("C12345678")
        assert result == "C12345678"
    
    def test_valid_dm_channel(self, slack_client):
        """Test valid DM channel ID."""
        result = slack_client._validate_channel_id("D12345678")
        assert result == "D12345678"
    
    def test_valid_private_channel(self, slack_client):
        """Test valid private channel ID."""
        result = slack_client._validate_channel_id("G12345678")
        assert result == "G12345678"
    
    def test_channel_name_passthrough(self, slack_client):
        """Test channel name passes through."""
        result = slack_client._validate_channel_id("general")
        assert result == "general"
    
    def test_empty_channel(self, slack_client):
        """Test empty channel rejected."""
        with pytest.raises(ValueError):
            slack_client._validate_channel_id("")


class TestTimestampValidation:
    """Tests for timestamp validation."""
    
    def test_valid_timestamp(self, slack_client):
        """Test valid timestamp format."""
        result = slack_client._validate_timestamp("1234567890.123456")
        assert result == "1234567890.123456"
    
    def test_invalid_timestamp_no_dot(self, slack_client):
        """Test timestamp without dot rejected."""
        with pytest.raises(ValueError):
            slack_client._validate_timestamp("1234567890")
    
    def test_invalid_timestamp_format(self, slack_client):
        """Test invalid format rejected."""
        with pytest.raises(ValueError):
            slack_client._validate_timestamp("abc.def")
    
    def test_empty_timestamp(self, slack_client):
        """Test empty timestamp rejected."""
        with pytest.raises(ValueError):
            slack_client._validate_timestamp("")


class TestReactionNameValidation:
    """Tests for reaction name validation."""
    
    def test_plain_name(self, slack_client):
        """Test plain reaction name."""
        result = slack_client._validate_reaction_name("thumbsup")
        assert result == "thumbsup"
    
    def test_name_with_colons(self, slack_client):
        """Test reaction name with colons stripped."""
        result = slack_client._validate_reaction_name(":thumbsup:")
        assert result == "thumbsup"
    
    def test_empty_name(self, slack_client):
        """Test empty name rejected."""
        with pytest.raises(ValueError):
            slack_client._validate_reaction_name("")
    
    def test_only_colons(self, slack_client):
        """Test only colons rejected."""
        with pytest.raises(ValueError):
            slack_client._validate_reaction_name("::")


class TestResultTransformation:
    """Tests for result transformation."""
    
    def test_transform_rate_limit_error(self, slack_client):
        """Test rate limit error transformation."""
        error_result = ToolResult(
            status=ToolCallStatus.ERROR,
            is_error=True,
            error_message="ratelimited",
            content=[{"type": "text", "text": "Error"}],
        )
        
        result = slack_client.transform_tool_result("search_messages", error_result)
        
        assert result.is_error
        assert "rate limit" in result.error_message.lower()
    
    def test_transform_channel_not_found(self, slack_client):
        """Test channel not found error transformation."""
        error_result = ToolResult(
            status=ToolCallStatus.ERROR,
            is_error=True,
            error_message="channel_not_found",
            content=[{"type": "text", "text": "Error"}],
        )
        
        result = slack_client.transform_tool_result("send_message", error_result)
        
        assert result.is_error
        assert "not found" in result.error_message.lower()
    
    def test_transform_permission_error(self, slack_client):
        """Test permission error transformation."""
        error_result = ToolResult(
            status=ToolCallStatus.ERROR,
            is_error=True,
            error_message="missing_scope",
            content=[{"type": "text", "text": "Error"}],
        )
        
        result = slack_client.transform_tool_result("send_message", error_result)
        
        assert result.is_error
        assert "permission" in result.error_message.lower()
    
    def test_transform_auth_error(self, slack_client):
        """Test auth error transformation."""
        error_result = ToolResult(
            status=ToolCallStatus.ERROR,
            is_error=True,
            error_message="not_authed",
            content=[{"type": "text", "text": "Error"}],
        )
        
        result = slack_client.transform_tool_result("list_channels", error_result)
        
        assert result.is_error
        assert result.status == ToolCallStatus.UNAUTHORIZED
    
    def test_successful_result_unchanged(self, slack_client):
        """Test successful results pass through."""
        success_result = ToolResult(
            status=ToolCallStatus.SUCCESS,
            is_error=False,
            content=[{"type": "text", "text": "Messages found"}],
        )
        
        result = slack_client.transform_tool_result("search_messages", success_result)
        
        assert not result.is_error
        assert result.content == success_result.content


class TestConvenienceMethods:
    """Tests for convenience methods."""
    
    @pytest.mark.asyncio
    async def test_search_messages(self, slack_client, mock_connection_manager):
        """Test search_messages convenience method."""
        mock_response = MagicMock()
        mock_response.is_success = True
        mock_response.result = {"content": [{"type": "text", "text": "results"}]}
        mock_response.error = None
        mock_response.raw = {}
        mock_connection_manager.send_tools_call.return_value = mock_response
        
        result = await slack_client.search_messages(
            query="test",
            count=10,
            auth_token="Bearer xyz"
        )
        
        mock_connection_manager.send_tools_call.assert_called_once()
        call_args = mock_connection_manager.send_tools_call.call_args
        assert call_args.kwargs["tool_name"] == "search_messages"
        assert call_args.kwargs["arguments"]["query"] == "test"
    
    @pytest.mark.asyncio
    async def test_send_message(self, slack_client, mock_connection_manager):
        """Test send_message convenience method."""
        mock_response = MagicMock()
        mock_response.is_success = True
        mock_response.result = {"content": [{"type": "text", "text": "sent"}]}
        mock_response.error = None
        mock_response.raw = {}
        mock_connection_manager.send_tools_call.return_value = mock_response
        
        result = await slack_client.send_message(
            channel="C12345678",
            text="Hello",
            auth_token="Bearer xyz"
        )
        
        call_args = mock_connection_manager.send_tools_call.call_args
        assert call_args.kwargs["tool_name"] == "send_message"
        assert call_args.kwargs["arguments"]["channel"] == "C12345678"
        assert call_args.kwargs["arguments"]["text"] == "Hello"


class TestFactoryFunction:
    """Tests for factory function."""
    
    def test_create_slack_client(self, mock_connection_manager):
        """Test create_slack_client factory."""
        client = create_slack_client(mock_connection_manager)
        
        assert isinstance(client, SlackMCPClient)
        assert client.backend_id == "slack"
```

---

## Post-Conditions

After completing this task:

- [ ] `SlackMCPClient` is available in `app/backends/`
- [ ] Gateway can proxy MCP requests to Slack backend
- [ ] Slack tool arguments are validated before sending
- [ ] Slack errors are transformed to user-friendly messages
- [ ] D6 (Backend Router) can route to Slack client
- [ ] Demo 1 (Unified Connection) can include Slack tools
- [ ] All unit tests pass

---

## References

- **Design Doc Section**: 2.6 Step 8: Agent Executes Task
- **Upstream Tasks**:
  - [WS-D2: Base MCP Client](./WS-D2-base-mcp-client.md) - Provides base class
  - [WS-D1: Connection Manager](./WS-D1-backend-connection-manager.md) - HTTP transport
- **Parallel Tasks**:
  - [WS-D3: Notion MCP Client](./WS-D3-notion-mcp-client.md) - Similar implementation
  - [WS-D5: HubSpot MCP Client](./WS-D5-hubspot-mcp-client.md) - Similar implementation
- **Downstream Tasks**:
  - [WS-D6: Backend Router](./WS-D6-backend-router.md) - Routes to this client
  - [WS-F2: Demo 1 Unified Connection](./WS-F2-demo-unified-connection.md) - Uses Slack
- **External References**:
  - [Slack Web API Reference](https://api.slack.com/methods)

---

## Notes

- Channel IDs have different prefixes: C (public), D (DM), G (private/group)
- Message timestamps use epoch.sequence format (e.g., "1234567890.123456")
- Reaction names should not include surrounding colons
- Rate limiting is aggressive in Slack - handle gracefully with retry hints
- Permission errors often indicate missing OAuth scopes
- The MCP server backend handles actual Slack API authentication
