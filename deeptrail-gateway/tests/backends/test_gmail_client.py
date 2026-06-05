"""Tests for ``GmailDirectClient`` (WS-D4).

Covers all 17 test cases from the WS-D4 task ticket:

1.  list_messages success
2.  list_messages with label_ids (repeated `labelIds` params)
3.  read_message success
4.  read_message format=metadata
5.  read_message missing id → ERROR
6.  search_messages success (`q` param set)
7.  list_labels success
8.  No auth token (all 4 methods → UNAUTHORIZED)
9.  HTTP 401
10. HTTP 404
11. HTTP 429 rate limit
12. Timeout (httpx.TimeoutException → TIMEOUT)
13. Connection error (httpx.ConnectError → ERROR)
14. call_tool dispatch (each tool routes to correct method)
15. call_tool unknown tool → ERROR
16. Config from settings (no explicit config)
17. Factory function (create_gmail_direct_client)
"""

from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from app.backends.base_mcp_client import ToolCallStatus
from app.backends.gmail_client import (
    GmailAPIConfig,
    GmailDirectClient,
    create_gmail_direct_client,
)


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def gmail_config():
    return GmailAPIConfig(
        base_url="https://gmail.googleapis.com/gmail/v1",
        timeout_seconds=30.0,
    )


@pytest.fixture
def gmail_client(gmail_config):
    return GmailDirectClient(config=gmail_config)


def _mock_response(status_code: int, body: dict | None = None, text: str | None = None):
    """Build a MagicMock that mimics ``httpx.Response``."""
    response = MagicMock(spec=httpx.Response)
    response.status_code = status_code
    response.json.return_value = body if body is not None else {}
    response.text = text if text is not None else ("" if body is None else str(body))
    return response


# =============================================================================
# Initialization / Config Tests
# =============================================================================


class TestInit:
    def test_init_with_explicit_config(self, gmail_config):
        client = GmailDirectClient(config=gmail_config)
        assert client.base_url == "https://gmail.googleapis.com/gmail/v1"
        assert client.timeout == 30.0

    def test_init_with_custom_config(self):
        config = GmailAPIConfig(
            base_url="http://mock-gmail:8080",
            timeout_seconds=60.0,
        )
        client = GmailDirectClient(config=config)
        assert client.base_url == "http://mock-gmail:8080"
        assert client.timeout == 60.0

    def test_init_loads_from_settings(self):
        """Test 16: when no config provided, loads from get_settings().gmail."""
        from app.core.config import reset_settings

        reset_settings()
        client = GmailDirectClient()
        assert client.base_url == "https://gmail.googleapis.com/gmail/v1"
        assert client.timeout == 30.0

    def test_factory_function(self, gmail_config):
        """Test 17: factory returns a GmailDirectClient."""
        client = create_gmail_direct_client(config=gmail_config)
        assert isinstance(client, GmailDirectClient)

    def test_factory_function_no_config(self):
        client = create_gmail_direct_client()
        assert isinstance(client, GmailDirectClient)


# =============================================================================
# Headers
# =============================================================================


class TestHeaders:
    def test_get_headers_uses_bearer_token(self, gmail_client):
        headers = gmail_client._get_headers("ya29.test_token")
        assert headers["Authorization"] == "Bearer ya29.test_token"
        assert headers["Accept"] == "application/json"


# =============================================================================
# list_messages (Tests 1, 2)
# =============================================================================


class TestListMessages:
    @pytest.mark.asyncio
    async def test_list_messages_success(self, gmail_client):
        """Test 1: 200 response with message id/threadId stubs.

        ``list_messages`` enriches results by fetching metadata for each
        message, so the mock will be called multiple times (1 list + N
        enrichment calls). We check ``call_args_list[0]`` for the
        initial list request.
        """
        mock_response = _mock_response(
            200,
            body={
                "messages": [
                    {"id": "m1", "threadId": "t1"},
                    {"id": "m2", "threadId": "t2"},
                ],
                "resultSizeEstimate": 2,
            },
        )

        with patch.object(httpx.AsyncClient, "get", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = mock_response

            result = await gmail_client.list_messages(auth_token="ya29.test")

            assert not result.is_error
            assert result.status == ToolCallStatus.SUCCESS
            assert len(result.raw["messages"]) == 2
            first_call = mock_get.call_args_list[0]
            assert (
                first_call.args[0]
                == "https://gmail.googleapis.com/gmail/v1/users/me/messages"
            )
            params = first_call.kwargs["params"]
            assert params["maxResults"] == 10
            assert "labelIds" not in params

    @pytest.mark.asyncio
    async def test_list_messages_with_label_ids(self, gmail_client):
        """Test 2: label_ids forwarded as `labelIds` (httpx repeats list values)."""
        mock_response = _mock_response(200, body={"messages": []})

        with patch.object(httpx.AsyncClient, "get", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = mock_response

            await gmail_client.list_messages(
                auth_token="ya29.test",
                label_ids=["INBOX", "UNREAD"],
                max_results=25,
            )

            params = mock_get.call_args.kwargs["params"]
            assert params["maxResults"] == 25
            # Forwarded as a list — httpx serialises lists into repeated query params.
            assert params["labelIds"] == ["INBOX", "UNREAD"]


# =============================================================================
# read_message (Tests 3, 4, 5)
# =============================================================================


class TestReadMessage:
    @pytest.mark.asyncio
    async def test_read_message_success(self, gmail_client):
        """Test 3: 200 response with full message; default format=full."""
        mock_response = _mock_response(
            200,
            body={
                "id": "m1",
                "threadId": "t1",
                "labelIds": ["INBOX"],
                "snippet": "Hello world",
                "payload": {"headers": [{"name": "From", "value": "a@x.com"}]},
            },
        )

        with patch.object(httpx.AsyncClient, "get", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = mock_response

            result = await gmail_client.read_message(
                message_id="m1", auth_token="ya29.test"
            )

            assert not result.is_error
            assert result.status == ToolCallStatus.SUCCESS
            assert result.raw["id"] == "m1"
            assert (
                mock_get.call_args.args[0]
                == "https://gmail.googleapis.com/gmail/v1/users/me/messages/m1"
            )
            assert mock_get.call_args.kwargs["params"] == {"format": "full"}

    @pytest.mark.asyncio
    async def test_read_message_format_metadata(self, gmail_client):
        """Test 4: format=metadata forwarded to API."""
        mock_response = _mock_response(200, body={"id": "m1", "threadId": "t1"})

        with patch.object(httpx.AsyncClient, "get", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = mock_response

            await gmail_client.read_message(
                message_id="m1", auth_token="ya29.test", format="metadata"
            )

            assert mock_get.call_args.kwargs["params"] == {"format": "metadata"}

    @pytest.mark.asyncio
    async def test_read_message_invalid_format_falls_back_to_full(self, gmail_client):
        """Invalid format values fall back to 'full' rather than failing or
        forwarding bad input to Gmail."""
        mock_response = _mock_response(200, body={"id": "m1"})

        with patch.object(httpx.AsyncClient, "get", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = mock_response

            await gmail_client.read_message(
                message_id="m1", auth_token="ya29.test", format="bogus"
            )

            assert mock_get.call_args.kwargs["params"] == {"format": "full"}

    @pytest.mark.asyncio
    async def test_read_message_missing_id_direct(self, gmail_client):
        """Test 5 (direct call): empty message_id → ERROR before HTTP."""
        result = await gmail_client.read_message(
            message_id="", auth_token="ya29.test"
        )
        assert result.is_error
        assert "message_id is required" in result.error_message

    @pytest.mark.asyncio
    async def test_read_message_missing_id_dispatch(self, gmail_client):
        """Test 5 (via dispatcher): call_tool('read_message', {}) → ERROR."""
        result = await gmail_client.call_tool(
            "read_message", {}, auth_token="ya29.test"
        )
        assert result.is_error
        assert "message_id is required" in result.error_message


# =============================================================================
# search_messages (Test 6)
# =============================================================================


class TestSearchMessages:
    @pytest.mark.asyncio
    async def test_search_messages_success(self, gmail_client):
        """Test 6: 200 response with q-based search.

        ``search_messages`` enriches results by fetching metadata for
        each message, so we check ``call_args_list[0]`` for the initial
        search request.
        """
        mock_response = _mock_response(
            200, body={"messages": [{"id": "m1", "threadId": "t1"}]}
        )

        with patch.object(httpx.AsyncClient, "get", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = mock_response

            result = await gmail_client.search_messages(
                query="from:alice subject:meeting newer_than:7d",
                auth_token="ya29.test",
                max_results=20,
            )

            assert not result.is_error
            first_call = mock_get.call_args_list[0]
            params = first_call.kwargs["params"]
            assert params["q"] == "from:alice subject:meeting newer_than:7d"
            assert params["maxResults"] == 20
            assert (
                first_call.args[0]
                == "https://gmail.googleapis.com/gmail/v1/users/me/messages"
            )


# =============================================================================
# list_labels (Test 7)
# =============================================================================


class TestListLabels:
    @pytest.mark.asyncio
    async def test_list_labels_success(self, gmail_client):
        """Test 7: 200 response with label list."""
        mock_response = _mock_response(
            200,
            body={
                "labels": [
                    {"id": "INBOX", "name": "INBOX", "type": "system"},
                    {"id": "STARRED", "name": "STARRED", "type": "system"},
                    {"id": "Label_1", "name": "Work", "type": "user"},
                ]
            },
        )

        with patch.object(httpx.AsyncClient, "get", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = mock_response

            result = await gmail_client.list_labels(auth_token="ya29.test")

            assert not result.is_error
            assert result.status == ToolCallStatus.SUCCESS
            assert len(result.raw["labels"]) == 3
            assert (
                mock_get.call_args.args[0]
                == "https://gmail.googleapis.com/gmail/v1/users/me/labels"
            )


# =============================================================================
# No auth token (Test 8)
# =============================================================================


class TestUnauthorized:
    @pytest.mark.asyncio
    async def test_list_messages_no_auth_token(self, gmail_client):
        result = await gmail_client.list_messages(auth_token=None)
        assert result.is_error
        assert result.status == ToolCallStatus.UNAUTHORIZED

    @pytest.mark.asyncio
    async def test_read_message_no_auth_token(self, gmail_client):
        result = await gmail_client.read_message(message_id="m1", auth_token=None)
        assert result.is_error
        assert result.status == ToolCallStatus.UNAUTHORIZED

    @pytest.mark.asyncio
    async def test_search_messages_no_auth_token(self, gmail_client):
        result = await gmail_client.search_messages(query="x", auth_token=None)
        assert result.is_error
        assert result.status == ToolCallStatus.UNAUTHORIZED

    @pytest.mark.asyncio
    async def test_list_labels_no_auth_token(self, gmail_client):
        result = await gmail_client.list_labels(auth_token=None)
        assert result.is_error
        assert result.status == ToolCallStatus.UNAUTHORIZED


# =============================================================================
# HTTP error responses (Tests 9, 10, 11)
# =============================================================================


class TestHTTPErrors:
    @pytest.mark.asyncio
    async def test_http_401_unauthorized(self, gmail_client):
        """Test 9: HTTP 401 → ToolResult(ERROR) with 'Unauthorized'."""
        mock_response = _mock_response(
            401,
            body={"error": {"code": 401, "message": "Invalid Credentials"}},
        )

        with patch.object(httpx.AsyncClient, "get", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = mock_response

            result = await gmail_client.list_labels(auth_token="bad_token")

            assert result.is_error
            assert result.status == ToolCallStatus.ERROR
            assert "Unauthorized" in result.error_message
            assert "Invalid Credentials" in result.error_message
            assert result.raw["status_code"] == 401

    @pytest.mark.asyncio
    async def test_http_404_not_found(self, gmail_client):
        """Test 10: HTTP 404 → ToolResult(ERROR) with 'Not found'."""
        mock_response = _mock_response(
            404, body={"error": {"code": 404, "message": "Requested entity was not found."}}
        )

        with patch.object(httpx.AsyncClient, "get", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = mock_response

            result = await gmail_client.read_message(
                message_id="nonexistent", auth_token="ya29.test"
            )

            assert result.is_error
            assert "Not found" in result.error_message

    @pytest.mark.asyncio
    async def test_http_429_rate_limit(self, gmail_client):
        """Test 11: HTTP 429 → ToolResult(ERROR) with 'Rate limit'."""
        mock_response = _mock_response(
            429,
            body={"error": {"code": 429, "message": "User-rate limit exceeded"}},
        )

        with patch.object(httpx.AsyncClient, "get", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = mock_response

            result = await gmail_client.list_messages(auth_token="ya29.test")

            assert result.is_error
            assert "Rate limit" in result.error_message

    @pytest.mark.asyncio
    async def test_http_500_server_error(self, gmail_client):
        """HTTP 5xx → generic Gmail API error message."""
        mock_response = _mock_response(
            500, body={"error": {"message": "Backend error"}}
        )

        with patch.object(httpx.AsyncClient, "get", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = mock_response

            result = await gmail_client.list_labels(auth_token="ya29.test")

            assert result.is_error
            assert "Gmail API error (500)" in result.error_message

    @pytest.mark.asyncio
    async def test_error_with_unparseable_body(self, gmail_client):
        """Error response with non-JSON body falls back to raw text (truncated)."""
        long_text = "a" * 1000
        mock_response = MagicMock(spec=httpx.Response)
        mock_response.status_code = 502
        mock_response.json.side_effect = ValueError("not json")
        mock_response.text = long_text

        with patch.object(httpx.AsyncClient, "get", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = mock_response

            result = await gmail_client.list_labels(auth_token="ya29.test")

            assert result.is_error
            assert len(result.raw["error"]) <= 500


# =============================================================================
# Network errors (Tests 12, 13)
# =============================================================================


class TestNetworkErrors:
    @pytest.mark.asyncio
    async def test_timeout(self, gmail_client):
        """Test 12: httpx.TimeoutException → ToolResult(TIMEOUT)."""
        with patch.object(httpx.AsyncClient, "get", new_callable=AsyncMock) as mock_get:
            mock_get.side_effect = httpx.TimeoutException("timed out")

            result = await gmail_client.list_messages(auth_token="ya29.test")

            assert result.is_error
            assert result.status == ToolCallStatus.TIMEOUT
            assert "timed out" in result.error_message.lower()

    @pytest.mark.asyncio
    async def test_connection_error(self, gmail_client):
        """Test 13: httpx.ConnectError → ToolResult(ERROR)."""
        with patch.object(httpx.AsyncClient, "get", new_callable=AsyncMock) as mock_get:
            mock_get.side_effect = httpx.ConnectError("connection refused")

            result = await gmail_client.read_message(
                message_id="m1", auth_token="ya29.test"
            )

            assert result.is_error
            assert result.status == ToolCallStatus.ERROR
            assert "Request failed" in result.error_message


# =============================================================================
# call_tool dispatcher (Tests 14, 15)
# =============================================================================


class TestCallToolDispatch:
    @pytest.mark.asyncio
    async def test_dispatch_list_messages(self, gmail_client):
        """Test 14a: call_tool('list_messages', ...) routes to list_messages."""
        with patch.object(
            gmail_client, "list_messages", new_callable=AsyncMock
        ) as mock_method:
            mock_method.return_value = MagicMock(is_error=False)

            await gmail_client.call_tool(
                "list_messages",
                {"max_results": 50, "label_ids": ["INBOX"]},
                auth_token="ya29.test",
            )

            mock_method.assert_awaited_once()
            kwargs = mock_method.await_args.kwargs
            assert kwargs["max_results"] == 50
            assert kwargs["label_ids"] == ["INBOX"]
            assert kwargs["auth_token"] == "ya29.test"

    @pytest.mark.asyncio
    async def test_dispatch_list_messages_camelcase(self, gmail_client):
        """Dispatcher tolerates camelCase `labelIds` and scalar value."""
        with patch.object(
            gmail_client, "list_messages", new_callable=AsyncMock
        ) as mock_method:
            mock_method.return_value = MagicMock(is_error=False)

            await gmail_client.call_tool(
                "list_messages",
                {"maxResults": 5, "labelIds": "STARRED"},
                auth_token="ya29.test",
            )

            kwargs = mock_method.await_args.kwargs
            assert kwargs["max_results"] == 5
            assert kwargs["label_ids"] == ["STARRED"]

    @pytest.mark.asyncio
    async def test_dispatch_read_message(self, gmail_client):
        """Test 14b: call_tool('read_message', ...) routes to read_message."""
        with patch.object(
            gmail_client, "read_message", new_callable=AsyncMock
        ) as mock_method:
            mock_method.return_value = MagicMock(is_error=False)

            await gmail_client.call_tool(
                "read_message",
                {"message_id": "m1", "format": "metadata"},
                auth_token="ya29.test",
            )

            mock_method.assert_awaited_once()
            kwargs = mock_method.await_args.kwargs
            assert kwargs["message_id"] == "m1"
            assert kwargs["format"] == "metadata"

    @pytest.mark.asyncio
    async def test_dispatch_read_message_camelcase_id(self, gmail_client):
        """Dispatcher accepts `messageId` and bare `id` keys."""
        with patch.object(
            gmail_client, "read_message", new_callable=AsyncMock
        ) as mock_method:
            mock_method.return_value = MagicMock(is_error=False)

            await gmail_client.call_tool(
                "read_message", {"messageId": "m2"}, auth_token="ya29.test"
            )
            assert mock_method.await_args.kwargs["message_id"] == "m2"

            await gmail_client.call_tool(
                "read_message", {"id": "m3"}, auth_token="ya29.test"
            )
            assert mock_method.await_args.kwargs["message_id"] == "m3"

    @pytest.mark.asyncio
    async def test_dispatch_search_messages(self, gmail_client):
        """Test 14c: call_tool('search_messages', ...) routes correctly."""
        with patch.object(
            gmail_client, "search_messages", new_callable=AsyncMock
        ) as mock_method:
            mock_method.return_value = MagicMock(is_error=False)

            await gmail_client.call_tool(
                "search_messages",
                {"query": "from:bob", "max_results": 5},
                auth_token="ya29.test",
            )

            mock_method.assert_awaited_once()
            kwargs = mock_method.await_args.kwargs
            assert kwargs["query"] == "from:bob"
            assert kwargs["max_results"] == 5

    @pytest.mark.asyncio
    async def test_dispatch_search_messages_missing_query(self, gmail_client):
        """call_tool('search_messages', {}) → ERROR (no query)."""
        result = await gmail_client.call_tool(
            "search_messages", {}, auth_token="ya29.test"
        )
        assert result.is_error
        assert "query is required" in result.error_message

    @pytest.mark.asyncio
    async def test_dispatch_list_labels(self, gmail_client):
        """Test 14d: call_tool('list_labels', ...) routes to list_labels."""
        with patch.object(
            gmail_client, "list_labels", new_callable=AsyncMock
        ) as mock_method:
            mock_method.return_value = MagicMock(is_error=False)

            await gmail_client.call_tool(
                "list_labels", {}, auth_token="ya29.test"
            )

            mock_method.assert_awaited_once()
            assert mock_method.await_args.kwargs["auth_token"] == "ya29.test"

    @pytest.mark.asyncio
    async def test_dispatch_unknown_tool(self, gmail_client):
        """Test 15: unknown tool → ToolResult(ERROR) with 'Unknown tool'."""
        result = await gmail_client.call_tool(
            "delete_universe", {}, auth_token="ya29.test"
        )
        assert result.is_error
        assert result.status == ToolCallStatus.ERROR
        assert "Unknown tool" in result.error_message


# =============================================================================
# Security: tokens and message content never logged
# =============================================================================


class TestSecurity:
    @pytest.mark.asyncio
    async def test_auth_token_not_in_logs(self, gmail_client, caplog):
        """Auth token must never appear in log output."""
        import logging

        caplog.set_level(logging.DEBUG, logger="app.backends.gmail_client")

        mock_response = _mock_response(200, body={"messages": []})
        with patch.object(httpx.AsyncClient, "get", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = mock_response
            await gmail_client.list_messages(
                auth_token="SUPER_SECRET_TOKEN_789"
            )

        for record in caplog.records:
            assert "SUPER_SECRET_TOKEN_789" not in record.getMessage()

    @pytest.mark.asyncio
    async def test_message_content_not_in_logs(self, gmail_client, caplog):
        """Message bodies must never appear in log output."""
        import logging

        caplog.set_level(logging.DEBUG, logger="app.backends.gmail_client")

        sensitive_snippet = "CONFIDENTIAL_BOARD_MEMO_CONTENTS"
        mock_response = _mock_response(
            200,
            body={
                "id": "m1",
                "threadId": "t1",
                "snippet": sensitive_snippet,
                "payload": {"body": {"data": "base64encodedsecret"}},
            },
        )

        with patch.object(httpx.AsyncClient, "get", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = mock_response
            await gmail_client.read_message(
                message_id="m1", auth_token="ya29.test"
            )

        for record in caplog.records:
            assert sensitive_snippet not in record.getMessage()
            assert "base64encodedsecret" not in record.getMessage()

    @pytest.mark.asyncio
    async def test_error_message_content_not_in_logs(self, gmail_client, caplog):
        """Error responses' Gmail messages can appear in error_message field
        (so callers can see the failure), but should NOT be logged at WARN
        beyond status code + tool name."""
        import logging

        caplog.set_level(logging.WARNING, logger="app.backends.gmail_client")

        secret_in_error = "SECRET_MESSAGE_ID_EXPOSED_IN_ERROR"
        mock_response = _mock_response(
            403,
            body={"error": {"code": 403, "message": secret_in_error}},
        )
        with patch.object(httpx.AsyncClient, "get", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = mock_response
            await gmail_client.read_message(
                message_id="m1", auth_token="ya29.test"
            )

        warn_records = [r for r in caplog.records if r.levelno == logging.WARNING]
        assert warn_records, "expected at least one WARNING record"
        for record in warn_records:
            assert secret_in_error not in record.getMessage()


# =============================================================================
# WS-D6 gap-fill tests — coverage matrix cells
# =============================================================================


class TestConfigFallback:
    def test_config_fallback_on_attribute_error(self):
        mock_settings = MagicMock()
        del mock_settings.gmail
        with patch("app.core.config.get_settings", return_value=mock_settings):
            client = GmailDirectClient()
        assert client.base_url == "https://gmail.googleapis.com/gmail/v1"
        assert client.timeout == 30.0


class TestTransformResponseEdgeCases:
    @pytest.mark.asyncio
    async def test_success_response_with_unparseable_json(self, gmail_client):
        """Use ``list_labels`` because it routes 200 responses through
        ``_transform_response`` which handles bad JSON gracefully.
        ``list_messages`` does NOT use ``_transform_response`` for
        success (it has custom enrichment logic)."""
        response = MagicMock(spec=httpx.Response)
        response.status_code = 200
        response.json.side_effect = ValueError("bad json")
        response.text = "not-json"

        with patch.object(httpx.AsyncClient, "get", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = response
            result = await gmail_client.list_labels(auth_token="tok")

        assert not result.is_error
        assert result.raw == {"raw_text": "not-json"}

    @pytest.mark.asyncio
    async def test_http_400_validation_error(self, gmail_client):
        response = _mock_response(
            400, body={"error": {"message": "Invalid query"}}
        )
        with patch.object(httpx.AsyncClient, "get", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = response
            result = await gmail_client.list_messages(auth_token="tok")

        assert result.is_error
        assert "Validation error" in result.error_message or "Invalid query" in result.error_message


class TestPerToolNetworkErrors:
    @pytest.mark.asyncio
    async def test_read_message_timeout(self, gmail_client):
        with patch.object(httpx.AsyncClient, "get", new_callable=AsyncMock) as mock_get:
            mock_get.side_effect = httpx.TimeoutException("timed out")
            result = await gmail_client.read_message(
                message_id="m1", auth_token="tok"
            )
        assert result.is_error
        assert result.status == ToolCallStatus.TIMEOUT

    @pytest.mark.asyncio
    async def test_search_messages_connection_error(self, gmail_client):
        with patch.object(httpx.AsyncClient, "get", new_callable=AsyncMock) as mock_get:
            mock_get.side_effect = httpx.ConnectError("refused")
            result = await gmail_client.search_messages(
                query="test", auth_token="tok"
            )
        assert result.is_error
        assert result.status == ToolCallStatus.ERROR

    @pytest.mark.asyncio
    async def test_list_labels_timeout(self, gmail_client):
        with patch.object(httpx.AsyncClient, "get", new_callable=AsyncMock) as mock_get:
            mock_get.side_effect = httpx.TimeoutException("timed out")
            result = await gmail_client.list_labels(auth_token="tok")
        assert result.is_error
        assert result.status == ToolCallStatus.TIMEOUT

    @pytest.mark.asyncio
    async def test_list_messages_connection_error(self, gmail_client):
        with patch.object(httpx.AsyncClient, "get", new_callable=AsyncMock) as mock_get:
            mock_get.side_effect = httpx.ConnectError("refused")
            result = await gmail_client.list_messages(auth_token="tok")
        assert result.is_error
        assert result.status == ToolCallStatus.ERROR
