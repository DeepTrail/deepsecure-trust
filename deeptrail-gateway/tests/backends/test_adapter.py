"""
Tests for BackendClientAdapter.

Tests the adapter that bridges tools_call.py interface to backend clients.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock

from app.backends.adapter import (
    BackendClientAdapter,
    create_backend_adapter,
)
from app.backends.base_mcp_client import ToolResult, ToolCallStatus


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def adapter() -> BackendClientAdapter:
    """Create a fresh adapter instance."""
    return BackendClientAdapter()


@pytest.fixture
def mock_client() -> MagicMock:
    """Create a mock backend client."""
    client = MagicMock()
    client.call_tool = AsyncMock()
    return client


@pytest.fixture
def success_result() -> ToolResult:
    """Create a success ToolResult."""
    return ToolResult(
        status=ToolCallStatus.SUCCESS,
        content=[{"type": "text", "text": "Success result"}],
        is_error=False,
    )


@pytest.fixture
def error_result() -> ToolResult:
    """Create an error ToolResult."""
    return ToolResult(
        status=ToolCallStatus.ERROR,
        content=[{"type": "text", "text": "Error message"}],
        is_error=True,
        error_message="Something went wrong",
    )


# =============================================================================
# Auth Token Extraction Tests
# =============================================================================


class TestExtractAuthToken:
    """Tests for _extract_auth_token method."""

    def test_extract_bearer_token(self, adapter: BackendClientAdapter):
        """Should extract token from Bearer auth header."""
        headers = {"Authorization": "Bearer secret_token_123"}
        token = adapter._extract_auth_token(headers)
        assert token == "secret_token_123"

    def test_extract_token_without_bearer(self, adapter: BackendClientAdapter):
        """Should return full value if no Bearer prefix."""
        headers = {"Authorization": "api_key_xyz"}
        token = adapter._extract_auth_token(headers)
        assert token == "api_key_xyz"

    def test_empty_headers(self, adapter: BackendClientAdapter):
        """Should return None for empty headers dict."""
        token = adapter._extract_auth_token({})
        assert token is None

    def test_none_headers(self, adapter: BackendClientAdapter):
        """Should return None for None headers."""
        token = adapter._extract_auth_token(None)
        assert token is None

    def test_missing_authorization_header(self, adapter: BackendClientAdapter):
        """Should return None if Authorization header missing."""
        headers = {"Content-Type": "application/json"}
        token = adapter._extract_auth_token(headers)
        assert token is None

    def test_empty_authorization_value(self, adapter: BackendClientAdapter):
        """Should return None for empty Authorization value."""
        headers = {"Authorization": ""}
        token = adapter._extract_auth_token(headers)
        assert token is None


# =============================================================================
# Namespace Stripping Tests
# =============================================================================


class TestStripNamespace:
    """Tests for _strip_namespace method."""

    def test_strip_notion_namespace(self, adapter: BackendClientAdapter):
        """Should strip notion. prefix."""
        result = adapter._strip_namespace("notion.search_pages")
        assert result == "search_pages"

    def test_strip_slack_namespace(self, adapter: BackendClientAdapter):
        """Should strip slack. prefix."""
        result = adapter._strip_namespace("slack.post_message")
        assert result == "post_message"

    def test_no_namespace(self, adapter: BackendClientAdapter):
        """Should return unchanged if no namespace."""
        result = adapter._strip_namespace("search_pages")
        assert result == "search_pages"

    def test_multiple_dots(self, adapter: BackendClientAdapter):
        """Should only split on first dot."""
        result = adapter._strip_namespace("notion.database.query")
        assert result == "database.query"


# =============================================================================
# MCP Response Conversion Tests
# =============================================================================


class TestToMcpResponse:
    """Tests for _to_mcp_response method."""

    def test_success_with_content(
        self, adapter: BackendClientAdapter, success_result: ToolResult
    ):
        """Should convert success result with content."""
        response = adapter._to_mcp_response(success_result)
        assert response["isError"] is False
        assert response["content"] == [{"type": "text", "text": "Success result"}]

    def test_error_result(
        self, adapter: BackendClientAdapter, error_result: ToolResult
    ):
        """Should convert error result correctly."""
        response = adapter._to_mcp_response(error_result)
        assert response["isError"] is True
        assert response["content"][0]["type"] == "text"
        assert response["content"][0]["text"] == "Something went wrong"

    def test_error_without_message(self, adapter: BackendClientAdapter):
        """Should use default error message if none provided."""
        result = ToolResult(
            status=ToolCallStatus.ERROR,
            is_error=True,
            error_message=None,
        )
        response = adapter._to_mcp_response(result)
        assert response["isError"] is True
        assert response["content"][0]["text"] == "Unknown error"

    def test_success_with_raw_data(self, adapter: BackendClientAdapter):
        """Should serialize raw data if no content."""
        result = ToolResult(
            status=ToolCallStatus.SUCCESS,
            is_error=False,
            raw={"data": "test_value"},
        )
        response = adapter._to_mcp_response(result)
        assert response["isError"] is False
        assert "test_value" in response["content"][0]["text"]

    def test_empty_success(self, adapter: BackendClientAdapter):
        """Should handle empty success result."""
        result = ToolResult(
            status=ToolCallStatus.SUCCESS,
            is_error=False,
        )
        response = adapter._to_mcp_response(result)
        assert response["isError"] is False
        assert response["content"][0]["text"] == "Success"


# =============================================================================
# Client Registration Tests
# =============================================================================


class TestClientRegistration:
    """Tests for client registration."""

    def test_register_client(
        self, adapter: BackendClientAdapter, mock_client: MagicMock
    ):
        """Should register a client successfully."""
        adapter.register_client("notion", mock_client)
        assert "notion" in adapter.registered_backends

    def test_register_multiple_clients(
        self, adapter: BackendClientAdapter, mock_client: MagicMock
    ):
        """Should register multiple clients."""
        adapter.register_client("notion", mock_client)
        adapter.register_client("slack", mock_client)
        adapter.register_client("gdrive", mock_client)
        assert adapter.registered_backends == ["notion", "slack", "gdrive"]

    def test_register_empty_backend_id(
        self, adapter: BackendClientAdapter, mock_client: MagicMock
    ):
        """Should raise ValueError for empty backend_id."""
        with pytest.raises(ValueError, match="backend_id cannot be empty"):
            adapter.register_client("", mock_client)

    def test_register_none_client(self, adapter: BackendClientAdapter):
        """Should raise ValueError for None client."""
        with pytest.raises(ValueError, match="client cannot be None"):
            adapter.register_client("notion", None)


# =============================================================================
# Tool Call Routing Tests
# =============================================================================


class TestCallTool:
    """Tests for call_tool method."""

    @pytest.mark.asyncio
    async def test_routes_to_correct_backend(
        self,
        adapter: BackendClientAdapter,
        mock_client: MagicMock,
        success_result: ToolResult,
    ):
        """Should route to the registered backend client."""
        mock_client.call_tool.return_value = success_result
        adapter.register_client("notion", mock_client)

        result = await adapter.call_tool(
            backend_id="notion",
            tool_name="notion.search_pages",
            arguments={"query": "test"},
            auth_headers={"Authorization": "Bearer secret_123"},
            mcp_session_id="session-abc",
        )

        # Verify client was called correctly
        mock_client.call_tool.assert_called_once_with(
            tool_name="search_pages",  # Namespace stripped
            arguments={"query": "test"},
            auth_token="secret_123",  # Token extracted
        )
        assert result["isError"] is False

    @pytest.mark.asyncio
    async def test_unknown_backend(self, adapter: BackendClientAdapter):
        """Should return error for unknown backend."""
        result = await adapter.call_tool(
            backend_id="unknown",
            tool_name="unknown.some_tool",
            arguments={},
        )

        assert result["isError"] is True
        assert "Unknown backend" in result["content"][0]["text"]

    @pytest.mark.asyncio
    async def test_passes_none_token(
        self,
        adapter: BackendClientAdapter,
        mock_client: MagicMock,
        success_result: ToolResult,
    ):
        """Should pass None token when no auth headers."""
        mock_client.call_tool.return_value = success_result
        adapter.register_client("notion", mock_client)

        await adapter.call_tool(
            backend_id="notion",
            tool_name="notion.search_pages",
            arguments={},
            auth_headers=None,
        )

        mock_client.call_tool.assert_called_once()
        call_args = mock_client.call_tool.call_args
        assert call_args.kwargs["auth_token"] is None

    @pytest.mark.asyncio
    async def test_handles_client_exception(
        self,
        adapter: BackendClientAdapter,
        mock_client: MagicMock,
    ):
        """Should catch and convert client exceptions."""
        mock_client.call_tool.side_effect = RuntimeError("Connection failed")
        adapter.register_client("notion", mock_client)

        result = await adapter.call_tool(
            backend_id="notion",
            tool_name="notion.search_pages",
            arguments={},
        )

        assert result["isError"] is True
        assert "RuntimeError" in result["content"][0]["text"]

    @pytest.mark.asyncio
    async def test_returns_error_result(
        self,
        adapter: BackendClientAdapter,
        mock_client: MagicMock,
        error_result: ToolResult,
    ):
        """Should properly convert error ToolResult."""
        mock_client.call_tool.return_value = error_result
        adapter.register_client("notion", mock_client)

        result = await adapter.call_tool(
            backend_id="notion",
            tool_name="notion.search_pages",
            arguments={},
        )

        assert result["isError"] is True
        assert "Something went wrong" in result["content"][0]["text"]


# =============================================================================
# Factory Function Tests
# =============================================================================


class TestCreateBackendAdapter:
    """Tests for create_backend_adapter factory function."""

    def test_creates_adapter_with_backends(self):
        """Should create adapter with all backends registered."""
        adapter = create_backend_adapter()

        assert "notion" in adapter.registered_backends
        assert "slack" in adapter.registered_backends
        assert "gdrive" in adapter.registered_backends
        assert "gcalendar" in adapter.registered_backends
        assert "gmail" in adapter.registered_backends
        assert len(adapter.registered_backends) == 5

    def test_clients_are_correct_types(self):
        """Should register correct client types."""
        from app.backends.notion_client import NotionDirectClient
        from app.backends.slack_client import SlackDirectClient
        from app.backends.gdrive_client import GDriveDirectClient
        from app.backends.gcalendar_client import GCalendarDirectClient
        from app.backends.gmail_client import GmailDirectClient

        adapter = create_backend_adapter()

        assert isinstance(adapter._clients["notion"], NotionDirectClient)
        assert isinstance(adapter._clients["slack"], SlackDirectClient)
        assert isinstance(adapter._clients["gdrive"], GDriveDirectClient)
        assert isinstance(adapter._clients["gcalendar"], GCalendarDirectClient)
        assert isinstance(adapter._clients["gmail"], GmailDirectClient)


# =============================================================================
# Integration-style Tests
# =============================================================================


class TestAdapterIntegration:
    """Integration-style tests with real client instances."""

    @pytest.mark.asyncio
    async def test_notion_tool_routing(self):
        """Test routing to Notion client (without real API call)."""
        adapter = create_backend_adapter()

        # Mock the internal Notion client's call_tool method
        mock_result = ToolResult(
            status=ToolCallStatus.SUCCESS,
            content=[{"type": "text", "text": '{"results": []}'}],
            is_error=False,
        )
        adapter._clients["notion"].call_tool = AsyncMock(return_value=mock_result)

        result = await adapter.call_tool(
            backend_id="notion",
            tool_name="notion.search_pages",
            arguments={"query": "test"},
            auth_headers={"Authorization": "Bearer secret_xxx"},
            mcp_session_id="test-session",
        )

        assert result["isError"] is False
        adapter._clients["notion"].call_tool.assert_called_once_with(
            tool_name="search_pages",
            arguments={"query": "test"},
            auth_token="secret_xxx",
        )

    @pytest.mark.asyncio
    async def test_slack_tool_routing(self):
        """Test routing to Slack client (without real API call)."""
        adapter = create_backend_adapter()

        mock_result = ToolResult(
            status=ToolCallStatus.SUCCESS,
            content=[{"type": "text", "text": "Message sent"}],
            is_error=False,
        )
        adapter._clients["slack"].call_tool = AsyncMock(return_value=mock_result)

        result = await adapter.call_tool(
            backend_id="slack",
            tool_name="slack.post_message",
            arguments={"channel": "#general", "text": "Hello"},
            auth_headers={"Authorization": "Bearer xoxb-token"},
        )

        assert result["isError"] is False
        adapter._clients["slack"].call_tool.assert_called_once_with(
            tool_name="post_message",
            arguments={"channel": "#general", "text": "Hello"},
            auth_token="xoxb-token",
        )
