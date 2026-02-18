"""Tests for Slack MCP client (WS-D4) and Slack Direct client (WS-G3)."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

import httpx

from app.backends.slack_client import (
    SlackMCPClient,
    SlackDirectClient,
    SlackAPIConfig,
    SlackClientError,
    SlackRateLimitError,
    SlackChannelNotFoundError,
    SlackPermissionError,
    SlackChannelType,
    create_slack_client,
    create_slack_direct_client,
)
from app.backends.base_mcp_client import ToolResult, ToolCallStatus


# =============================================================================
# Fixtures
# =============================================================================


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


# =============================================================================
# Basic Properties Tests
# =============================================================================


class TestSlackMCPClient:
    """Tests for SlackMCPClient basic properties."""
    
    def test_backend_id(self, slack_client):
        """Test backend_id is 'slack'."""
        assert slack_client.backend_id == "slack"
    
    def test_repr(self, slack_client):
        """Test string representation."""
        repr_str = repr(slack_client)
        assert "SlackMCPClient" in repr_str
        assert "slack" in repr_str
    
    def test_is_not_initialized_by_default(self, slack_client):
        """Test client is not initialized by default."""
        assert not slack_client.is_initialized
    
    def test_server_info_is_none_before_initialize(self, slack_client):
        """Test server_info is None before initialize."""
        assert slack_client.server_info is None


# =============================================================================
# Argument Validation Tests
# =============================================================================


class TestArgumentValidation:
    """Tests for argument validation."""
    
    # ─────────────────────────────────────────────────────────────────────────
    # search_messages
    # ─────────────────────────────────────────────────────────────────────────
    
    def test_search_messages_requires_query(self, slack_client):
        """Test search_messages requires query."""
        with pytest.raises(ValueError) as exc:
            slack_client.validate_tool_arguments("search_messages", {})
        assert "query" in str(exc.value)
    
    def test_search_messages_with_none_query(self, slack_client):
        """Test search_messages rejects None query."""
        with pytest.raises(ValueError) as exc:
            slack_client.validate_tool_arguments("search_messages", {"query": None})
        assert "query" in str(exc.value)
    
    def test_search_messages_with_query(self, slack_client):
        """Test search_messages with valid query."""
        args = {"query": "meeting notes", "count": 50}
        result = slack_client.validate_tool_arguments("search_messages", args)
        assert result["query"] == "meeting notes"
        assert result["count"] == 50
    
    def test_search_messages_all_optional_args(self, slack_client):
        """Test search_messages with all optional args."""
        args = {
            "query": "project update",
            "sort": "timestamp",
            "sort_dir": "desc",
            "count": 25,
            "page": 2,
        }
        result = slack_client.validate_tool_arguments("search_messages", args)
        assert result["query"] == "project update"
        assert result["sort"] == "timestamp"
        assert result["count"] == 25
    
    # ─────────────────────────────────────────────────────────────────────────
    # send_message
    # ─────────────────────────────────────────────────────────────────────────
    
    def test_send_message_requires_channel_and_text(self, slack_client):
        """Test send_message requires channel and text."""
        with pytest.raises(ValueError) as exc:
            slack_client.validate_tool_arguments("send_message", {"channel": "C123"})
        assert "text" in str(exc.value)
    
    def test_send_message_requires_text_with_channel(self, slack_client):
        """Test send_message requires text when channel is given."""
        with pytest.raises(ValueError) as exc:
            slack_client.validate_tool_arguments(
                "send_message", {"channel": "C12345678"}
            )
        assert "text" in str(exc.value)
    
    def test_send_message_with_all_required(self, slack_client):
        """Test send_message with all required args."""
        args = {"channel": "C12345678", "text": "Hello world"}
        result = slack_client.validate_tool_arguments("send_message", args)
        assert result["channel"] == "C12345678"
        assert result["text"] == "Hello world"
    
    def test_send_message_with_thread_ts(self, slack_client):
        """Test send_message with thread_ts."""
        args = {
            "channel": "C12345678",
            "text": "Reply in thread",
            "thread_ts": "1234567890.123456",
        }
        result = slack_client.validate_tool_arguments("send_message", args)
        assert result["thread_ts"] == "1234567890.123456"
    
    def test_send_message_with_optional_args(self, slack_client):
        """Test send_message with optional args."""
        args = {
            "channel": "C12345678",
            "text": "Message with blocks",
            "blocks": [{"type": "section", "text": {"type": "plain_text", "text": "Block"}}],
            "unfurl_links": False,
            "unfurl_media": True,
        }
        result = slack_client.validate_tool_arguments("send_message", args)
        assert result["blocks"] == args["blocks"]
        assert result["unfurl_links"] is False
    
    # ─────────────────────────────────────────────────────────────────────────
    # list_channels
    # ─────────────────────────────────────────────────────────────────────────
    
    def test_list_channels_no_required_args(self, slack_client):
        """Test list_channels has no required args."""
        result = slack_client.validate_tool_arguments("list_channels", {})
        assert result == {}
    
    def test_list_channels_with_types(self, slack_client):
        """Test list_channels with types filter."""
        args = {"types": "public_channel,private_channel", "limit": 200}
        result = slack_client.validate_tool_arguments("list_channels", args)
        assert result["types"] == "public_channel,private_channel"
        assert result["limit"] == 200
    
    def test_list_channels_with_all_options(self, slack_client):
        """Test list_channels with all optional args."""
        args = {
            "types": "public_channel",
            "limit": 500,
            "cursor": "abc123xyz",
            "exclude_archived": True,
        }
        result = slack_client.validate_tool_arguments("list_channels", args)
        assert result["exclude_archived"] is True
        assert result["cursor"] == "abc123xyz"
    
    # ─────────────────────────────────────────────────────────────────────────
    # join_channel
    # ─────────────────────────────────────────────────────────────────────────
    
    def test_join_channel_requires_channel(self, slack_client):
        """Test join_channel requires channel."""
        with pytest.raises(ValueError) as exc:
            slack_client.validate_tool_arguments("join_channel", {})
        assert "channel" in str(exc.value)
    
    def test_join_channel_with_channel(self, slack_client):
        """Test join_channel with channel ID."""
        args = {"channel": "C12345678"}
        result = slack_client.validate_tool_arguments("join_channel", args)
        assert result["channel"] == "C12345678"
    
    # ─────────────────────────────────────────────────────────────────────────
    # post_reaction
    # ─────────────────────────────────────────────────────────────────────────
    
    def test_post_reaction_requires_all(self, slack_client):
        """Test post_reaction requires channel, timestamp, name."""
        with pytest.raises(ValueError):
            slack_client.validate_tool_arguments("post_reaction", {"channel": "C123"})
    
    def test_post_reaction_requires_name(self, slack_client):
        """Test post_reaction requires name."""
        with pytest.raises(ValueError) as exc:
            slack_client.validate_tool_arguments(
                "post_reaction",
                {"channel": "C12345678", "timestamp": "1234567890.123456"}
            )
        assert "name" in str(exc.value)
    
    def test_post_reaction_with_all_required(self, slack_client):
        """Test post_reaction with all required args."""
        args = {
            "channel": "C12345678",
            "timestamp": "1234567890.123456",
            "name": "thumbsup",
        }
        result = slack_client.validate_tool_arguments("post_reaction", args)
        assert result["name"] == "thumbsup"
        assert result["timestamp"] == "1234567890.123456"
    
    # ─────────────────────────────────────────────────────────────────────────
    # list_users
    # ─────────────────────────────────────────────────────────────────────────
    
    def test_list_users_no_required_args(self, slack_client):
        """Test list_users has no required args."""
        result = slack_client.validate_tool_arguments("list_users", {})
        assert result == {}
    
    def test_list_users_with_limit(self, slack_client):
        """Test list_users with limit."""
        args = {"limit": 500}
        result = slack_client.validate_tool_arguments("list_users", args)
        assert result["limit"] == 500
    
    def test_list_users_with_all_options(self, slack_client):
        """Test list_users with all optional args."""
        args = {
            "limit": 200,
            "cursor": "cursor123",
            "include_locale": True,
        }
        result = slack_client.validate_tool_arguments("list_users", args)
        assert result["include_locale"] is True
    
    # ─────────────────────────────────────────────────────────────────────────
    # count/limit validation
    # ─────────────────────────────────────────────────────────────────────────
    
    def test_count_validation_above_100(self, slack_client):
        """Test count must be <= 100."""
        with pytest.raises(ValueError) as exc:
            slack_client.validate_tool_arguments(
                "search_messages", {"query": "test", "count": 101}
            )
        assert "count" in str(exc.value)
    
    def test_count_zero_invalid(self, slack_client):
        """Test count 0 is invalid."""
        with pytest.raises(ValueError):
            slack_client.validate_tool_arguments(
                "search_messages", {"query": "test", "count": 0}
            )
    
    def test_count_negative_invalid(self, slack_client):
        """Test negative count is invalid."""
        with pytest.raises(ValueError):
            slack_client.validate_tool_arguments(
                "search_messages", {"query": "test", "count": -1}
            )
    
    def test_count_not_integer_invalid(self, slack_client):
        """Test non-integer count is invalid."""
        with pytest.raises(ValueError):
            slack_client.validate_tool_arguments(
                "search_messages", {"query": "test", "count": "50"}
            )
    
    def test_count_boundary_1(self, slack_client):
        """Test count = 1 is valid."""
        result = slack_client.validate_tool_arguments(
            "search_messages", {"query": "test", "count": 1}
        )
        assert result["count"] == 1
    
    def test_count_boundary_100(self, slack_client):
        """Test count = 100 is valid."""
        result = slack_client.validate_tool_arguments(
            "search_messages", {"query": "test", "count": 100}
        )
        assert result["count"] == 100
    
    def test_limit_validation_above_1000(self, slack_client):
        """Test limit must be <= 1000."""
        with pytest.raises(ValueError) as exc:
            slack_client.validate_tool_arguments(
                "list_channels", {"limit": 1001}
            )
        assert "limit" in str(exc.value)
    
    def test_limit_boundary_1000(self, slack_client):
        """Test limit = 1000 is valid."""
        result = slack_client.validate_tool_arguments(
            "list_channels", {"limit": 1000}
        )
        assert result["limit"] == 1000
    
    # ─────────────────────────────────────────────────────────────────────────
    # Unknown tool handling
    # ─────────────────────────────────────────────────────────────────────────
    
    def test_unknown_tool_passthrough(self, slack_client):
        """Test unknown tools pass through."""
        args = {"foo": "bar", "baz": 123}
        result = slack_client.validate_tool_arguments("unknown_tool", args)
        assert result == args


# =============================================================================
# Channel ID Validation Tests
# =============================================================================


class TestChannelIDValidation:
    """Tests for channel ID validation."""
    
    def test_valid_public_channel(self, slack_client):
        """Test valid public channel ID."""
        result = slack_client._validate_channel_id("C12345678")
        assert result == "C12345678"
    
    def test_valid_public_channel_longer(self, slack_client):
        """Test valid public channel ID with longer format."""
        result = slack_client._validate_channel_id("C1234567890")
        assert result == "C1234567890"
    
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
    
    def test_channel_name_with_hash(self, slack_client):
        """Test channel name with hash prefix passes through."""
        result = slack_client._validate_channel_id("#general")
        assert result == "#general"
    
    def test_empty_channel(self, slack_client):
        """Test empty channel rejected."""
        with pytest.raises(ValueError) as exc:
            slack_client._validate_channel_id("")
        assert "cannot be empty" in str(exc.value)
    
    def test_invalid_channel_id_format(self, slack_client):
        """Test invalid channel ID format rejected."""
        # Starts with C but has lowercase letters which is invalid
        with pytest.raises(ValueError) as exc:
            slack_client._validate_channel_id("C12345abc")
        assert "Invalid channel ID" in str(exc.value)


# =============================================================================
# Timestamp Validation Tests
# =============================================================================


class TestTimestampValidation:
    """Tests for timestamp validation."""
    
    def test_valid_timestamp(self, slack_client):
        """Test valid timestamp format."""
        result = slack_client._validate_timestamp("1234567890.123456")
        assert result == "1234567890.123456"
    
    def test_valid_timestamp_short_sequence(self, slack_client):
        """Test valid timestamp with short sequence."""
        result = slack_client._validate_timestamp("1234567890.1")
        assert result == "1234567890.1"
    
    def test_valid_timestamp_long_sequence(self, slack_client):
        """Test valid timestamp with long sequence."""
        result = slack_client._validate_timestamp("1234567890.123456789")
        assert result == "1234567890.123456789"
    
    def test_invalid_timestamp_no_dot(self, slack_client):
        """Test timestamp without dot rejected."""
        with pytest.raises(ValueError) as exc:
            slack_client._validate_timestamp("1234567890")
        assert "Invalid timestamp format" in str(exc.value)
    
    def test_invalid_timestamp_format(self, slack_client):
        """Test invalid format rejected."""
        with pytest.raises(ValueError):
            slack_client._validate_timestamp("abc.def")
    
    def test_invalid_timestamp_letters_in_epoch(self, slack_client):
        """Test letters in epoch rejected."""
        with pytest.raises(ValueError):
            slack_client._validate_timestamp("123abc.123456")
    
    def test_empty_timestamp(self, slack_client):
        """Test empty timestamp rejected."""
        with pytest.raises(ValueError) as exc:
            slack_client._validate_timestamp("")
        assert "cannot be empty" in str(exc.value)
    
    def test_timestamp_only_dot(self, slack_client):
        """Test only dot rejected."""
        with pytest.raises(ValueError):
            slack_client._validate_timestamp(".")


# =============================================================================
# Reaction Name Validation Tests
# =============================================================================


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
    
    def test_name_with_leading_colon(self, slack_client):
        """Test reaction name with leading colon only."""
        result = slack_client._validate_reaction_name(":thumbsup")
        assert result == "thumbsup"
    
    def test_name_with_trailing_colon(self, slack_client):
        """Test reaction name with trailing colon only."""
        result = slack_client._validate_reaction_name("thumbsup:")
        assert result == "thumbsup"
    
    def test_name_with_underscores(self, slack_client):
        """Test reaction name with underscores."""
        result = slack_client._validate_reaction_name(":slightly_smiling_face:")
        assert result == "slightly_smiling_face"
    
    def test_name_with_numbers(self, slack_client):
        """Test reaction name with numbers."""
        result = slack_client._validate_reaction_name(":100:")
        assert result == "100"
    
    def test_empty_name(self, slack_client):
        """Test empty name rejected."""
        with pytest.raises(ValueError) as exc:
            slack_client._validate_reaction_name("")
        assert "cannot be empty" in str(exc.value)
    
    def test_only_colons(self, slack_client):
        """Test only colons rejected."""
        with pytest.raises(ValueError) as exc:
            slack_client._validate_reaction_name("::")
        assert "cannot be empty after removing colons" in str(exc.value)
    
    def test_single_colon(self, slack_client):
        """Test single colon rejected."""
        with pytest.raises(ValueError):
            slack_client._validate_reaction_name(":")


# =============================================================================
# Result Transformation Tests
# =============================================================================


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
    
    def test_transform_rate_limit_error_underscore(self, slack_client):
        """Test rate_limited error transformation."""
        error_result = ToolResult(
            status=ToolCallStatus.ERROR,
            is_error=True,
            error_message="rate_limited",
            content=[{"type": "text", "text": "Error"}],
        )
        
        result = slack_client.transform_tool_result("send_message", error_result)
        
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
    
    def test_transform_missing_scope_error(self, slack_client):
        """Test missing_scope error transformation."""
        error_result = ToolResult(
            status=ToolCallStatus.ERROR,
            is_error=True,
            error_message="missing_scope",
            content=[{"type": "text", "text": "Error"}],
        )
        
        result = slack_client.transform_tool_result("send_message", error_result)
        
        assert result.is_error
        assert "permission" in result.error_message.lower()
    
    def test_transform_not_in_channel_error(self, slack_client):
        """Test not_in_channel error transformation."""
        error_result = ToolResult(
            status=ToolCallStatus.ERROR,
            is_error=True,
            error_message="not_in_channel",
            content=[{"type": "text", "text": "Error"}],
        )
        
        result = slack_client.transform_tool_result("send_message", error_result)
        
        assert result.is_error
        assert "permission" in result.error_message.lower()
    
    def test_transform_channel_not_member_error(self, slack_client):
        """Test channel_not_member error transformation."""
        error_result = ToolResult(
            status=ToolCallStatus.ERROR,
            is_error=True,
            error_message="channel_not_member",
            content=[{"type": "text", "text": "Error"}],
        )
        
        result = slack_client.transform_tool_result("list_channels", error_result)
        
        assert result.is_error
        assert "permission" in result.error_message.lower()
    
    def test_transform_not_authed_error(self, slack_client):
        """Test not_authed error transformation."""
        error_result = ToolResult(
            status=ToolCallStatus.ERROR,
            is_error=True,
            error_message="not_authed",
            content=[{"type": "text", "text": "Error"}],
        )
        
        result = slack_client.transform_tool_result("list_channels", error_result)
        
        assert result.is_error
        assert result.status == ToolCallStatus.UNAUTHORIZED
        assert "authentication" in result.error_message.lower()
    
    def test_transform_invalid_auth_error(self, slack_client):
        """Test invalid_auth error transformation."""
        error_result = ToolResult(
            status=ToolCallStatus.ERROR,
            is_error=True,
            error_message="invalid_auth",
            content=[{"type": "text", "text": "Error"}],
        )
        
        result = slack_client.transform_tool_result("send_message", error_result)
        
        assert result.is_error
        assert result.status == ToolCallStatus.UNAUTHORIZED
    
    def test_transform_message_not_found_error(self, slack_client):
        """Test message_not_found error transformation."""
        error_result = ToolResult(
            status=ToolCallStatus.ERROR,
            is_error=True,
            error_message="message_not_found",
            content=[{"type": "text", "text": "Error"}],
        )
        
        result = slack_client.transform_tool_result("post_reaction", error_result)
        
        assert result.is_error
        assert "message not found" in result.error_message.lower()
    
    def test_transform_generic_error_unchanged(self, slack_client):
        """Test generic errors pass through unchanged."""
        error_result = ToolResult(
            status=ToolCallStatus.ERROR,
            is_error=True,
            error_message="some_other_error",
            content=[{"type": "text", "text": "Error"}],
        )
        
        result = slack_client.transform_tool_result("send_message", error_result)
        
        assert result.is_error
        assert result.error_message == "some_other_error"
    
    def test_transform_none_error_message(self, slack_client):
        """Test handling of None error message."""
        error_result = ToolResult(
            status=ToolCallStatus.ERROR,
            is_error=True,
            error_message=None,
            content=[{"type": "text", "text": "Error"}],
        )
        
        result = slack_client.transform_tool_result("send_message", error_result)
        
        assert result.is_error
    
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
    
    def test_preserves_raw_and_duration(self, slack_client):
        """Test transformation preserves raw and duration_ms."""
        error_result = ToolResult(
            status=ToolCallStatus.ERROR,
            is_error=True,
            error_message="ratelimited",
            content=[{"type": "text", "text": "Error"}],
            raw={"original": "data"},
            duration_ms=150.5,
        )
        
        result = slack_client.transform_tool_result("search_messages", error_result)
        
        assert result.raw == {"original": "data"}
        assert result.duration_ms == 150.5


# =============================================================================
# Convenience Methods Tests
# =============================================================================


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
        
        await slack_client.search_messages(
            query="test",
            count=10,
            auth_token="Bearer xyz"
        )
        
        mock_connection_manager.send_tools_call.assert_called_once()
        call_args = mock_connection_manager.send_tools_call.call_args
        assert call_args.kwargs["tool_name"] == "search_messages"
        assert call_args.kwargs["arguments"]["query"] == "test"
        assert call_args.kwargs["arguments"]["count"] == 10
    
    @pytest.mark.asyncio
    async def test_search_messages_defaults(self, slack_client, mock_connection_manager):
        """Test search_messages with default args."""
        mock_response = MagicMock()
        mock_response.is_success = True
        mock_response.result = {"content": [{"type": "text", "text": "results"}]}
        mock_response.error = None
        mock_response.raw = {}
        mock_connection_manager.send_tools_call.return_value = mock_response
        
        await slack_client.search_messages(query="test")
        
        call_args = mock_connection_manager.send_tools_call.call_args
        assert call_args.kwargs["arguments"]["count"] == 20  # Default
        assert call_args.kwargs["arguments"]["sort"] == "timestamp"  # Default
    
    @pytest.mark.asyncio
    async def test_send_message(self, slack_client, mock_connection_manager):
        """Test send_message convenience method."""
        mock_response = MagicMock()
        mock_response.is_success = True
        mock_response.result = {"content": [{"type": "text", "text": "sent"}]}
        mock_response.error = None
        mock_response.raw = {}
        mock_connection_manager.send_tools_call.return_value = mock_response
        
        await slack_client.send_message(
            channel="C12345678",
            text="Hello",
            auth_token="Bearer xyz"
        )
        
        call_args = mock_connection_manager.send_tools_call.call_args
        assert call_args.kwargs["tool_name"] == "send_message"
        assert call_args.kwargs["arguments"]["channel"] == "C12345678"
        assert call_args.kwargs["arguments"]["text"] == "Hello"
    
    @pytest.mark.asyncio
    async def test_send_message_with_thread(self, slack_client, mock_connection_manager):
        """Test send_message with thread_ts."""
        mock_response = MagicMock()
        mock_response.is_success = True
        mock_response.result = {"content": [{"type": "text", "text": "sent"}]}
        mock_response.error = None
        mock_response.raw = {}
        mock_connection_manager.send_tools_call.return_value = mock_response
        
        await slack_client.send_message(
            channel="C12345678",
            text="Reply",
            thread_ts="1234567890.123456",
            auth_token="Bearer xyz"
        )
        
        call_args = mock_connection_manager.send_tools_call.call_args
        assert call_args.kwargs["arguments"]["thread_ts"] == "1234567890.123456"
    
    @pytest.mark.asyncio
    async def test_send_message_no_thread(self, slack_client, mock_connection_manager):
        """Test send_message without thread_ts."""
        mock_response = MagicMock()
        mock_response.is_success = True
        mock_response.result = {"content": [{"type": "text", "text": "sent"}]}
        mock_response.error = None
        mock_response.raw = {}
        mock_connection_manager.send_tools_call.return_value = mock_response
        
        await slack_client.send_message(
            channel="C12345678",
            text="Hello"
        )
        
        call_args = mock_connection_manager.send_tools_call.call_args
        assert "thread_ts" not in call_args.kwargs["arguments"]
    
    @pytest.mark.asyncio
    async def test_list_channels(self, slack_client, mock_connection_manager):
        """Test list_channels convenience method."""
        mock_response = MagicMock()
        mock_response.is_success = True
        mock_response.result = {"content": [{"type": "text", "text": "channels"}]}
        mock_response.error = None
        mock_response.raw = {}
        mock_connection_manager.send_tools_call.return_value = mock_response
        
        await slack_client.list_channels(
            types="public_channel",
            limit=50,
            exclude_archived=False,
            auth_token="Bearer xyz"
        )
        
        call_args = mock_connection_manager.send_tools_call.call_args
        assert call_args.kwargs["tool_name"] == "list_channels"
        assert call_args.kwargs["arguments"]["types"] == "public_channel"
        assert call_args.kwargs["arguments"]["limit"] == 50
        assert call_args.kwargs["arguments"]["exclude_archived"] is False
    
    @pytest.mark.asyncio
    async def test_join_channel(self, slack_client, mock_connection_manager):
        """Test join_channel convenience method."""
        mock_response = MagicMock()
        mock_response.is_success = True
        mock_response.result = {"content": [{"type": "text", "text": "joined"}]}
        mock_response.error = None
        mock_response.raw = {}
        mock_connection_manager.send_tools_call.return_value = mock_response
        
        await slack_client.join_channel(
            channel="C12345678",
            auth_token="Bearer xyz"
        )
        
        call_args = mock_connection_manager.send_tools_call.call_args
        assert call_args.kwargs["tool_name"] == "join_channel"
        assert call_args.kwargs["arguments"]["channel"] == "C12345678"
    
    @pytest.mark.asyncio
    async def test_post_reaction(self, slack_client, mock_connection_manager):
        """Test post_reaction convenience method."""
        mock_response = MagicMock()
        mock_response.is_success = True
        mock_response.result = {"content": [{"type": "text", "text": "reacted"}]}
        mock_response.error = None
        mock_response.raw = {}
        mock_connection_manager.send_tools_call.return_value = mock_response
        
        await slack_client.post_reaction(
            channel="C12345678",
            timestamp="1234567890.123456",
            name="thumbsup",
            auth_token="Bearer xyz"
        )
        
        call_args = mock_connection_manager.send_tools_call.call_args
        assert call_args.kwargs["tool_name"] == "post_reaction"
        assert call_args.kwargs["arguments"]["name"] == "thumbsup"
        assert call_args.kwargs["arguments"]["timestamp"] == "1234567890.123456"
    
    @pytest.mark.asyncio
    async def test_list_users(self, slack_client, mock_connection_manager):
        """Test list_users convenience method."""
        mock_response = MagicMock()
        mock_response.is_success = True
        mock_response.result = {"content": [{"type": "text", "text": "users"}]}
        mock_response.error = None
        mock_response.raw = {}
        mock_connection_manager.send_tools_call.return_value = mock_response
        
        await slack_client.list_users(
            limit=200,
            auth_token="Bearer xyz"
        )
        
        call_args = mock_connection_manager.send_tools_call.call_args
        assert call_args.kwargs["tool_name"] == "list_users"
        assert call_args.kwargs["arguments"]["limit"] == 200


# =============================================================================
# Factory Function Tests
# =============================================================================


class TestFactoryFunction:
    """Tests for factory function."""
    
    def test_create_slack_client(self, mock_connection_manager):
        """Test create_slack_client factory."""
        client = create_slack_client(mock_connection_manager)
        
        assert isinstance(client, SlackMCPClient)
        assert client.backend_id == "slack"
    
    def test_create_slack_client_with_options(self, mock_connection_manager):
        """Test create_slack_client with additional options."""
        client = create_slack_client(
            mock_connection_manager,
            auto_initialize=True
        )
        
        assert isinstance(client, SlackMCPClient)


# =============================================================================
# Type Constants Tests
# =============================================================================


class TestTypeConstants:
    """Tests for type constant classes."""
    
    def test_slack_channel_types(self):
        """Test SlackChannelType constants."""
        assert SlackChannelType.PUBLIC == "public_channel"
        assert SlackChannelType.PRIVATE == "private_channel"
        assert SlackChannelType.MPIM == "mpim"
        assert SlackChannelType.IM == "im"


# =============================================================================
# Exception Classes Tests
# =============================================================================


class TestExceptionClasses:
    """Tests for exception classes."""
    
    def test_slack_client_error(self):
        """Test SlackClientError base exception."""
        error = SlackClientError("Test error")
        assert str(error) == "Test error"
        assert isinstance(error, Exception)
    
    def test_slack_rate_limit_error(self):
        """Test SlackRateLimitError inheritance."""
        error = SlackRateLimitError("Rate limit exceeded")
        assert isinstance(error, SlackClientError)
        assert str(error) == "Rate limit exceeded"
    
    def test_slack_channel_not_found_error(self):
        """Test SlackChannelNotFoundError inheritance."""
        error = SlackChannelNotFoundError("Channel not found")
        assert isinstance(error, SlackClientError)
        assert str(error) == "Channel not found"
    
    def test_slack_permission_error(self):
        """Test SlackPermissionError inheritance."""
        error = SlackPermissionError("Permission denied")
        assert isinstance(error, SlackClientError)
        assert str(error) == "Permission denied"


# =============================================================================
# SlackDirectClient Tests (WS-G3)
# =============================================================================


class TestSlackDirectClient:
    """Tests for SlackDirectClient direct REST API calls."""

    @pytest.fixture
    def slack_config(self):
        """Create test configuration."""
        return SlackAPIConfig(
            base_url="https://slack.com/api",
            timeout_seconds=10.0,
        )

    @pytest.fixture
    def direct_client(self, slack_config):
        """Create SlackDirectClient with test config."""
        return SlackDirectClient(config=slack_config)

    # ─────────────────────────────────────────────────────────────────────────
    # Basic Tests
    # ─────────────────────────────────────────────────────────────────────────

    def test_init_with_config(self, slack_config):
        """Test initialization with explicit config."""
        client = SlackDirectClient(config=slack_config)
        assert client.base_url == "https://slack.com/api"
        assert client.timeout == 10.0

    def test_init_with_defaults(self):
        """Test initialization with default config."""
        config = SlackAPIConfig()
        client = SlackDirectClient(config=config)
        assert client.base_url == "https://slack.com/api"
        assert client.timeout == 30.0

    def test_get_headers(self, direct_client):
        """Test header generation."""
        headers = direct_client._get_headers("xoxb-test-token")
        assert headers["Authorization"] == "Bearer xoxb-test-token"
        assert headers["Content-Type"] == "application/json"

    # ─────────────────────────────────────────────────────────────────────────
    # send_message Tests
    # ─────────────────────────────────────────────────────────────────────────

    @pytest.mark.asyncio
    async def test_send_message_success(self, direct_client):
        """Test send_message with successful response."""
        mock_response = httpx.Response(
            200,
            json={
                "ok": True,
                "channel": "C12345678",
                "ts": "1234567890.123456",
                "message": {"text": "Hello, World!"},
            },
        )

        with patch.object(
            httpx.AsyncClient, "post", new_callable=AsyncMock
        ) as mock_post:
            mock_post.return_value = mock_response

            result = await direct_client.send_message(
                channel="C12345678",
                text="Hello, World!",
                auth_token="xoxb-test",
            )

            assert result.status == ToolCallStatus.SUCCESS
            assert not result.is_error
            assert result.raw["ok"] is True
            assert result.raw["channel"] == "C12345678"

    @pytest.mark.asyncio
    async def test_send_message_with_thread(self, direct_client):
        """Test send_message with thread_ts."""
        mock_response = httpx.Response(
            200,
            json={"ok": True, "channel": "C12345678", "ts": "1234567890.123457"},
        )

        with patch.object(
            httpx.AsyncClient, "post", new_callable=AsyncMock
        ) as mock_post:
            mock_post.return_value = mock_response

            result = await direct_client.send_message(
                channel="C12345678",
                text="Reply in thread",
                thread_ts="1234567890.123456",
                auth_token="xoxb-test",
            )

            assert result.status == ToolCallStatus.SUCCESS
            # Verify thread_ts was passed in payload
            call_kwargs = mock_post.call_args.kwargs
            assert "json" in call_kwargs
            assert call_kwargs["json"]["thread_ts"] == "1234567890.123456"

    @pytest.mark.asyncio
    async def test_send_message_channel_not_found(self, direct_client):
        """Test send_message with channel_not_found error."""
        mock_response = httpx.Response(
            200,
            json={"ok": False, "error": "channel_not_found"},
        )

        with patch.object(
            httpx.AsyncClient, "post", new_callable=AsyncMock
        ) as mock_post:
            mock_post.return_value = mock_response

            result = await direct_client.send_message(
                channel="C_INVALID",
                text="Hello",
                auth_token="xoxb-test",
            )

            assert result.status == ToolCallStatus.ERROR
            assert result.is_error
            assert "not found" in result.error_message.lower()

    @pytest.mark.asyncio
    async def test_send_message_no_token(self, direct_client):
        """Test send_message without auth token."""
        result = await direct_client.send_message(
            channel="C12345678",
            text="Hello",
            auth_token=None,
        )

        assert result.status == ToolCallStatus.UNAUTHORIZED
        assert result.is_error

    # ─────────────────────────────────────────────────────────────────────────
    # list_channels Tests
    # ─────────────────────────────────────────────────────────────────────────

    @pytest.mark.asyncio
    async def test_list_channels_success(self, direct_client):
        """Test list_channels with successful response."""
        mock_response = httpx.Response(
            200,
            json={
                "ok": True,
                "channels": [
                    {"id": "C12345678", "name": "general"},
                    {"id": "C87654321", "name": "random"},
                ],
            },
        )

        with patch.object(
            httpx.AsyncClient, "get", new_callable=AsyncMock
        ) as mock_get:
            mock_get.return_value = mock_response

            result = await direct_client.list_channels(
                auth_token="xoxb-test",
            )

            assert result.status == ToolCallStatus.SUCCESS
            assert result.raw["ok"] is True
            assert len(result.raw["channels"]) == 2

    @pytest.mark.asyncio
    async def test_list_channels_with_pagination(self, direct_client):
        """Test list_channels with pagination cursor."""
        mock_response = httpx.Response(
            200,
            json={
                "ok": True,
                "channels": [{"id": "C12345678", "name": "general"}],
                "response_metadata": {"next_cursor": "abc123"},
            },
        )

        with patch.object(
            httpx.AsyncClient, "get", new_callable=AsyncMock
        ) as mock_get:
            mock_get.return_value = mock_response

            result = await direct_client.list_channels(
                cursor="prev_cursor",
                auth_token="xoxb-test",
            )

            assert result.status == ToolCallStatus.SUCCESS
            # Verify cursor was passed
            call_kwargs = mock_get.call_args.kwargs
            assert "params" in call_kwargs
            assert call_kwargs["params"]["cursor"] == "prev_cursor"

    # ─────────────────────────────────────────────────────────────────────────
    # search_messages Tests
    # ─────────────────────────────────────────────────────────────────────────

    @pytest.mark.asyncio
    async def test_search_messages_success(self, direct_client):
        """Test search_messages with successful response."""
        mock_response = httpx.Response(
            200,
            json={
                "ok": True,
                "messages": {
                    "total": 2,
                    "matches": [
                        {"text": "meeting notes from yesterday"},
                        {"text": "meeting notes from last week"},
                    ],
                },
            },
        )

        with patch.object(
            httpx.AsyncClient, "get", new_callable=AsyncMock
        ) as mock_get:
            mock_get.return_value = mock_response

            result = await direct_client.search_messages(
                query="meeting notes",
                auth_token="xoxp-test",
            )

            assert result.status == ToolCallStatus.SUCCESS
            assert result.raw["messages"]["total"] == 2

    @pytest.mark.asyncio
    async def test_search_messages_with_options(self, direct_client):
        """Test search_messages with sort options."""
        mock_response = httpx.Response(
            200,
            json={"ok": True, "messages": {"total": 0, "matches": []}},
        )

        with patch.object(
            httpx.AsyncClient, "get", new_callable=AsyncMock
        ) as mock_get:
            mock_get.return_value = mock_response

            result = await direct_client.search_messages(
                query="project",
                count=50,
                sort="timestamp",
                sort_dir="asc",
                auth_token="xoxp-test",
            )

            assert result.status == ToolCallStatus.SUCCESS
            call_kwargs = mock_get.call_args.kwargs
            assert call_kwargs["params"]["count"] == 50
            assert call_kwargs["params"]["sort"] == "timestamp"
            assert call_kwargs["params"]["sort_dir"] == "asc"

    # ─────────────────────────────────────────────────────────────────────────
    # join_channel Tests
    # ─────────────────────────────────────────────────────────────────────────

    @pytest.mark.asyncio
    async def test_join_channel_success(self, direct_client):
        """Test join_channel with successful response."""
        mock_response = httpx.Response(
            200,
            json={
                "ok": True,
                "channel": {"id": "C12345678", "name": "general"},
            },
        )

        with patch.object(
            httpx.AsyncClient, "post", new_callable=AsyncMock
        ) as mock_post:
            mock_post.return_value = mock_response

            result = await direct_client.join_channel(
                channel="C12345678",
                auth_token="xoxb-test",
            )

            assert result.status == ToolCallStatus.SUCCESS
            assert result.raw["channel"]["id"] == "C12345678"

    @pytest.mark.asyncio
    async def test_join_channel_not_found(self, direct_client):
        """Test join_channel with channel not found."""
        mock_response = httpx.Response(
            200,
            json={"ok": False, "error": "channel_not_found"},
        )

        with patch.object(
            httpx.AsyncClient, "post", new_callable=AsyncMock
        ) as mock_post:
            mock_post.return_value = mock_response

            result = await direct_client.join_channel(
                channel="C_INVALID",
                auth_token="xoxb-test",
            )

            assert result.is_error
            assert "not found" in result.error_message.lower()

    # ─────────────────────────────────────────────────────────────────────────
    # post_reaction Tests
    # ─────────────────────────────────────────────────────────────────────────

    @pytest.mark.asyncio
    async def test_post_reaction_success(self, direct_client):
        """Test post_reaction with successful response."""
        mock_response = httpx.Response(
            200,
            json={"ok": True},
        )

        with patch.object(
            httpx.AsyncClient, "post", new_callable=AsyncMock
        ) as mock_post:
            mock_post.return_value = mock_response

            result = await direct_client.post_reaction(
                channel="C12345678",
                timestamp="1234567890.123456",
                name="thumbsup",
                auth_token="xoxb-test",
            )

            assert result.status == ToolCallStatus.SUCCESS

    @pytest.mark.asyncio
    async def test_post_reaction_normalizes_name(self, direct_client):
        """Test post_reaction strips colons from emoji name."""
        mock_response = httpx.Response(200, json={"ok": True})

        with patch.object(
            httpx.AsyncClient, "post", new_callable=AsyncMock
        ) as mock_post:
            mock_post.return_value = mock_response

            await direct_client.post_reaction(
                channel="C12345678",
                timestamp="1234567890.123456",
                name=":thumbsup:",  # With colons
                auth_token="xoxb-test",
            )

            call_kwargs = mock_post.call_args.kwargs
            assert call_kwargs["json"]["name"] == "thumbsup"  # Colons stripped

    @pytest.mark.asyncio
    async def test_post_reaction_message_not_found(self, direct_client):
        """Test post_reaction with message not found."""
        mock_response = httpx.Response(
            200,
            json={"ok": False, "error": "message_not_found"},
        )

        with patch.object(
            httpx.AsyncClient, "post", new_callable=AsyncMock
        ) as mock_post:
            mock_post.return_value = mock_response

            result = await direct_client.post_reaction(
                channel="C12345678",
                timestamp="0000000000.000000",
                name="thumbsup",
                auth_token="xoxb-test",
            )

            assert result.is_error
            assert "message not found" in result.error_message.lower()

    # ─────────────────────────────────────────────────────────────────────────
    # list_users Tests
    # ─────────────────────────────────────────────────────────────────────────

    @pytest.mark.asyncio
    async def test_list_users_success(self, direct_client):
        """Test list_users with successful response."""
        mock_response = httpx.Response(
            200,
            json={
                "ok": True,
                "members": [
                    {"id": "U12345678", "name": "alice"},
                    {"id": "U87654321", "name": "bob"},
                ],
            },
        )

        with patch.object(
            httpx.AsyncClient, "get", new_callable=AsyncMock
        ) as mock_get:
            mock_get.return_value = mock_response

            result = await direct_client.list_users(
                auth_token="xoxb-test",
            )

            assert result.status == ToolCallStatus.SUCCESS
            assert len(result.raw["members"]) == 2

    @pytest.mark.asyncio
    async def test_list_users_with_pagination(self, direct_client):
        """Test list_users with pagination."""
        mock_response = httpx.Response(
            200,
            json={
                "ok": True,
                "members": [{"id": "U12345678", "name": "alice"}],
                "response_metadata": {"next_cursor": "xyz789"},
            },
        )

        with patch.object(
            httpx.AsyncClient, "get", new_callable=AsyncMock
        ) as mock_get:
            mock_get.return_value = mock_response

            result = await direct_client.list_users(
                limit=200,
                cursor="prev_cursor",
                auth_token="xoxb-test",
            )

            assert result.status == ToolCallStatus.SUCCESS
            call_kwargs = mock_get.call_args.kwargs
            assert call_kwargs["params"]["limit"] == 200
            assert call_kwargs["params"]["cursor"] == "prev_cursor"

    # ─────────────────────────────────────────────────────────────────────────
    # get_channel_history Tests
    # ─────────────────────────────────────────────────────────────────────────

    @pytest.mark.asyncio
    async def test_get_channel_history_success(self, direct_client):
        """Test get_channel_history with successful response."""
        mock_response = httpx.Response(
            200,
            json={
                "ok": True,
                "messages": [
                    {"type": "message", "text": "Hello", "ts": "1234567890.123456"},
                    {"type": "message", "text": "World", "ts": "1234567890.123457"},
                ],
                "has_more": False,
            },
        )

        with patch.object(
            httpx.AsyncClient, "get", new_callable=AsyncMock
        ) as mock_get:
            mock_get.return_value = mock_response

            result = await direct_client.get_channel_history(
                channel="C12345678",
                auth_token="xoxb-test",
            )

            assert result.status == ToolCallStatus.SUCCESS
            assert len(result.raw["messages"]) == 2

    @pytest.mark.asyncio
    async def test_get_channel_history_with_time_range(self, direct_client):
        """Test get_channel_history with time range parameters."""
        mock_response = httpx.Response(
            200,
            json={"ok": True, "messages": [], "has_more": False},
        )

        with patch.object(
            httpx.AsyncClient, "get", new_callable=AsyncMock
        ) as mock_get:
            mock_get.return_value = mock_response

            result = await direct_client.get_channel_history(
                channel="C12345678",
                oldest="1234567890.000000",
                latest="1234567899.000000",
                auth_token="xoxb-test",
            )

            assert result.status == ToolCallStatus.SUCCESS
            call_kwargs = mock_get.call_args.kwargs
            assert call_kwargs["params"]["oldest"] == "1234567890.000000"
            assert call_kwargs["params"]["latest"] == "1234567899.000000"

    @pytest.mark.asyncio
    async def test_get_channel_history_channel_not_found(self, direct_client):
        """Test get_channel_history with channel not found."""
        mock_response = httpx.Response(
            200,
            json={"ok": False, "error": "channel_not_found"},
        )

        with patch.object(
            httpx.AsyncClient, "get", new_callable=AsyncMock
        ) as mock_get:
            mock_get.return_value = mock_response

            result = await direct_client.get_channel_history(
                channel="C_INVALID",
                auth_token="xoxb-test",
            )

            assert result.is_error
            assert "not found" in result.error_message.lower()

    # ─────────────────────────────────────────────────────────────────────────
    # Error Handling Tests
    # ─────────────────────────────────────────────────────────────────────────

    @pytest.mark.asyncio
    async def test_rate_limited_error(self, direct_client):
        """Test rate limited error handling."""
        mock_response = httpx.Response(
            200,
            json={"ok": False, "error": "ratelimited"},
        )

        with patch.object(
            httpx.AsyncClient, "get", new_callable=AsyncMock
        ) as mock_get:
            mock_get.return_value = mock_response

            result = await direct_client.list_channels(auth_token="xoxb-test")

            assert result.is_error
            assert "rate limit" in result.error_message.lower()

    @pytest.mark.asyncio
    async def test_invalid_auth_error(self, direct_client):
        """Test invalid auth error handling."""
        mock_response = httpx.Response(
            200,
            json={"ok": False, "error": "invalid_auth"},
        )

        with patch.object(
            httpx.AsyncClient, "get", new_callable=AsyncMock
        ) as mock_get:
            mock_get.return_value = mock_response

            result = await direct_client.list_channels(auth_token="invalid")

            assert result.is_error
            assert result.status == ToolCallStatus.UNAUTHORIZED

    @pytest.mark.asyncio
    async def test_missing_scope_error(self, direct_client):
        """Test missing scope error handling."""
        mock_response = httpx.Response(
            200,
            json={"ok": False, "error": "missing_scope"},
        )

        with patch.object(
            httpx.AsyncClient, "get", new_callable=AsyncMock
        ) as mock_get:
            mock_get.return_value = mock_response

            result = await direct_client.list_channels(auth_token="xoxb-test")

            assert result.is_error
            assert "scope" in result.error_message.lower()

    @pytest.mark.asyncio
    async def test_timeout_error(self, direct_client):
        """Test timeout error handling."""
        with patch.object(
            httpx.AsyncClient, "get", new_callable=AsyncMock
        ) as mock_get:
            mock_get.side_effect = httpx.TimeoutException("Request timed out")

            result = await direct_client.list_channels(auth_token="xoxb-test")

            assert result.is_error
            assert result.status == ToolCallStatus.TIMEOUT

    @pytest.mark.asyncio
    async def test_request_error(self, direct_client):
        """Test request error handling."""
        with patch.object(
            httpx.AsyncClient, "get", new_callable=AsyncMock
        ) as mock_get:
            mock_get.side_effect = httpx.RequestError("Connection failed")

            result = await direct_client.list_channels(auth_token="xoxb-test")

            assert result.is_error
            assert result.status == ToolCallStatus.ERROR

    @pytest.mark.asyncio
    async def test_http_error_response(self, direct_client):
        """Test HTTP error response (non-200)."""
        mock_response = httpx.Response(
            500,
            json={"error": "internal_error"},
        )

        with patch.object(
            httpx.AsyncClient, "get", new_callable=AsyncMock
        ) as mock_get:
            mock_get.return_value = mock_response

            result = await direct_client.list_channels(auth_token="xoxb-test")

            assert result.is_error
            assert "500" in result.error_message

    # ─────────────────────────────────────────────────────────────────────────
    # call_tool Tests
    # ─────────────────────────────────────────────────────────────────────────

    @pytest.mark.asyncio
    async def test_call_tool_dispatch(self, direct_client):
        """Test call_tool dispatches to correct method."""
        mock_response = httpx.Response(
            200,
            json={"ok": True, "channels": []},
        )

        with patch.object(
            httpx.AsyncClient, "get", new_callable=AsyncMock
        ) as mock_get:
            mock_get.return_value = mock_response

            result = await direct_client.call_tool(
                "list_channels",
                {},
                auth_token="xoxb-test",
            )

            assert result.status == ToolCallStatus.SUCCESS

    @pytest.mark.asyncio
    async def test_call_tool_unknown_tool(self, direct_client):
        """Test call_tool with unknown tool name."""
        result = await direct_client.call_tool(
            "unknown_tool",
            {},
            auth_token="xoxb-test",
        )

        assert result.is_error
        assert "Unknown tool" in result.error_message

    @pytest.mark.asyncio
    async def test_call_tool_missing_required_arg(self, direct_client):
        """Test call_tool with missing required argument."""
        result = await direct_client.call_tool(
            "send_message",
            {"channel": "C12345678"},  # Missing text
            auth_token="xoxb-test",
        )

        assert result.is_error
        assert "text is required" in result.error_message


# =============================================================================
# SlackDirectClient Factory Tests
# =============================================================================


class TestSlackDirectClientFactory:
    """Tests for SlackDirectClient factory function."""

    def test_create_slack_direct_client(self):
        """Test create_slack_direct_client factory."""
        config = SlackAPIConfig(base_url="https://test.slack.com/api")
        client = create_slack_direct_client(config)

        assert isinstance(client, SlackDirectClient)
        assert client.base_url == "https://test.slack.com/api"

    def test_create_slack_direct_client_defaults(self):
        """Test create_slack_direct_client with default config."""
        config = SlackAPIConfig()
        client = create_slack_direct_client(config)

        assert isinstance(client, SlackDirectClient)
        assert client.base_url == "https://slack.com/api"
