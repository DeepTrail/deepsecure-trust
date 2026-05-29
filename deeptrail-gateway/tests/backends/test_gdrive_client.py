"""Tests for ``GDriveDirectClient`` (WS-D2).

Covers all 17 test cases from the WS-D2 task ticket:

1.  search_files success
2.  search_files empty results
3.  read_file success
4.  list_files success
5.  get_file_metadata success
6.  No auth token (all methods → UNAUTHORIZED)
7.  HTTP 401 unauthorized
8.  HTTP 403 forbidden
9.  HTTP 404 not found
10. HTTP 429 rate limit
11. Timeout (httpx.TimeoutException → TIMEOUT)
12. Connection error (httpx.ConnectError → ERROR)
13. call_tool dispatch (each tool routes to correct method)
14. call_tool unknown tool → ERROR
15. Config from settings (no explicit config)
16. Config explicit (custom GDriveAPIConfig)
17. Factory function (create_gdrive_direct_client)
"""

from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from app.backends.base_mcp_client import ToolCallStatus
from app.backends.gdrive_client import (
    GDriveAPIConfig,
    GDriveDirectClient,
    create_gdrive_direct_client,
)


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def gdrive_config():
    """Standard test configuration."""
    return GDriveAPIConfig(
        base_url="https://www.googleapis.com/drive/v3",
        timeout_seconds=30.0,
    )


@pytest.fixture
def gdrive_client(gdrive_config):
    """Client built from the standard test configuration."""
    return GDriveDirectClient(config=gdrive_config)


def _mock_response(status_code: int, body: dict | None = None, text: str | None = None):
    """Build a MagicMock that mimics ``httpx.Response``."""
    response = MagicMock(spec=httpx.Response)
    response.status_code = status_code
    response.json.return_value = body if body is not None else {}
    response.text = text if text is not None else (
        "" if body is None else str(body)
    )
    return response


# =============================================================================
# Initialization / Config Tests
# =============================================================================


class TestInit:
    """Tests for client initialization and configuration loading."""

    def test_init_with_explicit_config(self, gdrive_config):
        """Test 16: explicit GDriveAPIConfig is used."""
        client = GDriveDirectClient(config=gdrive_config)
        assert client.base_url == "https://www.googleapis.com/drive/v3"
        assert client.timeout == 30.0

    def test_init_with_custom_config(self):
        """Test 16 (variant): custom base_url + timeout are honored."""
        config = GDriveAPIConfig(
            base_url="http://mock-gdrive:8080",
            timeout_seconds=60.0,
        )
        client = GDriveDirectClient(config=config)
        assert client.base_url == "http://mock-gdrive:8080"
        assert client.timeout == 60.0

    def test_init_loads_from_settings(self):
        """Test 15: when no config provided, loads from get_settings().gdrive."""
        from app.core.config import reset_settings

        reset_settings()
        client = GDriveDirectClient()
        assert client.base_url == "https://www.googleapis.com/drive/v3"
        assert client.timeout == 30.0

    def test_factory_function(self, gdrive_config):
        """Test 17: factory returns a GDriveDirectClient."""
        client = create_gdrive_direct_client(config=gdrive_config)
        assert isinstance(client, GDriveDirectClient)

    def test_factory_function_no_config(self):
        """Test 17 (variant): factory works without arguments."""
        client = create_gdrive_direct_client()
        assert isinstance(client, GDriveDirectClient)


# =============================================================================
# Headers
# =============================================================================


class TestHeaders:
    def test_get_headers_uses_bearer_token(self, gdrive_client):
        headers = gdrive_client._get_headers("ya29.test_token")
        assert headers["Authorization"] == "Bearer ya29.test_token"
        assert headers["Accept"] == "application/json"


# =============================================================================
# search_files
# =============================================================================


class TestSearchFiles:
    @pytest.mark.asyncio
    async def test_search_files_success(self, gdrive_client):
        """Test 1: 200 response with files."""
        mock_response = _mock_response(
            200,
            body={
                "files": [
                    {"id": "file-1", "name": "Budget.xlsx"},
                    {"id": "file-2", "name": "Notes.docx"},
                ]
            },
        )

        with patch.object(httpx.AsyncClient, "get", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = mock_response

            result = await gdrive_client.search_files(
                query="name contains 'budget'", auth_token="ya29.test"
            )

            assert not result.is_error
            assert result.status == ToolCallStatus.SUCCESS
            assert "Budget.xlsx" in str(result.raw)
            mock_get.assert_called_once()
            # Verify URL + params
            call_args = mock_get.call_args
            assert call_args.args[0] == "https://www.googleapis.com/drive/v3/files"
            assert call_args.kwargs["params"]["q"] == "name contains 'budget'"
            assert call_args.kwargs["params"]["pageSize"] == 10

    @pytest.mark.asyncio
    async def test_search_files_empty(self, gdrive_client):
        """Test 2: 200 response with no files."""
        mock_response = _mock_response(200, body={"files": []})

        with patch.object(httpx.AsyncClient, "get", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = mock_response

            result = await gdrive_client.search_files(
                query="nonexistent", auth_token="ya29.test"
            )

            assert not result.is_error
            assert result.status == ToolCallStatus.SUCCESS
            assert result.raw == {"files": []}

    @pytest.mark.asyncio
    async def test_search_files_max_results_param(self, gdrive_client):
        """search_files passes max_results as pageSize."""
        mock_response = _mock_response(200, body={"files": []})

        with patch.object(httpx.AsyncClient, "get", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = mock_response

            await gdrive_client.search_files(
                query="x", auth_token="ya29.test", max_results=50
            )

            assert mock_get.call_args.kwargs["params"]["pageSize"] == 50


# =============================================================================
# read_file
# =============================================================================


class TestReadFile:
    @pytest.mark.asyncio
    async def test_read_file_success(self, gdrive_client):
        """Test 3: 200 response with file metadata."""
        mock_response = _mock_response(
            200,
            body={
                "id": "abc123",
                "name": "Budget.xlsx",
                "mimeType": "application/vnd.google-apps.spreadsheet",
            },
        )

        with patch.object(httpx.AsyncClient, "get", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = mock_response

            result = await gdrive_client.read_file(
                file_id="abc123", auth_token="ya29.test"
            )

            assert not result.is_error
            assert result.status == ToolCallStatus.SUCCESS
            assert result.raw["id"] == "abc123"
            mock_get.assert_called_once()
            assert (
                mock_get.call_args.args[0]
                == "https://www.googleapis.com/drive/v3/files/abc123"
            )

    @pytest.mark.asyncio
    async def test_read_file_missing_file_id(self, gdrive_client):
        """Empty file_id returns ERROR before making any HTTP call."""
        result = await gdrive_client.read_file(file_id="", auth_token="ya29.test")
        assert result.is_error
        assert "file_id is required" in result.error_message


# =============================================================================
# list_files
# =============================================================================


class TestListFiles:
    @pytest.mark.asyncio
    async def test_list_files_success(self, gdrive_client):
        """Test 4: 200 response with default ordering."""
        mock_response = _mock_response(
            200,
            body={
                "files": [
                    {"id": "f1", "name": "Recent.docx"},
                    {"id": "f2", "name": "Older.docx"},
                ]
            },
        )

        with patch.object(httpx.AsyncClient, "get", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = mock_response

            result = await gdrive_client.list_files(auth_token="ya29.test")

            assert not result.is_error
            assert result.status == ToolCallStatus.SUCCESS
            params = mock_get.call_args.kwargs["params"]
            assert params["pageSize"] == 20
            assert params["orderBy"] == "modifiedTime desc"

    @pytest.mark.asyncio
    async def test_list_files_custom_ordering(self, gdrive_client):
        """Custom page_size + order_by are forwarded."""
        mock_response = _mock_response(200, body={"files": []})

        with patch.object(httpx.AsyncClient, "get", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = mock_response

            await gdrive_client.list_files(
                auth_token="ya29.test",
                page_size=100,
                order_by="name",
            )

            params = mock_get.call_args.kwargs["params"]
            assert params["pageSize"] == 100
            assert params["orderBy"] == "name"


# =============================================================================
# get_file_metadata
# =============================================================================


class TestGetFileMetadata:
    @pytest.mark.asyncio
    async def test_get_file_metadata_success(self, gdrive_client):
        """Test 5: 200 response with full metadata; fields=* requested."""
        mock_response = _mock_response(
            200,
            body={
                "id": "abc123",
                "name": "Budget.xlsx",
                "owners": [{"emailAddress": "u@x.com"}],
                "modifiedTime": "2026-04-18T00:00:00Z",
            },
        )

        with patch.object(httpx.AsyncClient, "get", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = mock_response

            result = await gdrive_client.get_file_metadata(
                file_id="abc123", auth_token="ya29.test"
            )

            assert not result.is_error
            assert result.status == ToolCallStatus.SUCCESS
            assert result.raw["modifiedTime"] == "2026-04-18T00:00:00Z"
            assert mock_get.call_args.kwargs["params"] == {"fields": "*"}

    @pytest.mark.asyncio
    async def test_get_file_metadata_missing_file_id(self, gdrive_client):
        result = await gdrive_client.get_file_metadata(
            file_id="", auth_token="ya29.test"
        )
        assert result.is_error
        assert "file_id is required" in result.error_message


# =============================================================================
# No auth token (Test 6)
# =============================================================================


class TestUnauthorized:
    @pytest.mark.asyncio
    async def test_search_files_no_auth_token(self, gdrive_client):
        result = await gdrive_client.search_files(query="x", auth_token=None)
        assert result.is_error
        assert result.status == ToolCallStatus.UNAUTHORIZED

    @pytest.mark.asyncio
    async def test_read_file_no_auth_token(self, gdrive_client):
        result = await gdrive_client.read_file(file_id="abc", auth_token=None)
        assert result.is_error
        assert result.status == ToolCallStatus.UNAUTHORIZED

    @pytest.mark.asyncio
    async def test_list_files_no_auth_token(self, gdrive_client):
        result = await gdrive_client.list_files(auth_token=None)
        assert result.is_error
        assert result.status == ToolCallStatus.UNAUTHORIZED

    @pytest.mark.asyncio
    async def test_get_file_metadata_no_auth_token(self, gdrive_client):
        result = await gdrive_client.get_file_metadata(
            file_id="abc", auth_token=None
        )
        assert result.is_error
        assert result.status == ToolCallStatus.UNAUTHORIZED


# =============================================================================
# HTTP error responses (Tests 7-10)
# =============================================================================


class TestHTTPErrors:
    @pytest.mark.asyncio
    async def test_http_401_unauthorized(self, gdrive_client):
        """Test 7: HTTP 401 → ToolResult(ERROR) with 'Unauthorized'."""
        mock_response = _mock_response(
            401,
            body={"error": {"code": 401, "message": "Invalid Credentials"}},
        )

        with patch.object(httpx.AsyncClient, "get", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = mock_response

            result = await gdrive_client.search_files(
                query="x", auth_token="bad_token"
            )

            assert result.is_error
            assert result.status == ToolCallStatus.ERROR
            assert "Unauthorized" in result.error_message
            assert "Invalid Credentials" in result.error_message
            assert result.raw["status_code"] == 401

    @pytest.mark.asyncio
    async def test_http_403_forbidden(self, gdrive_client):
        """Test 8: HTTP 403 → ToolResult(ERROR) with 'Forbidden'."""
        mock_response = _mock_response(
            403,
            body={
                "error": {
                    "code": 403,
                    "message": "The user does not have sufficient permissions",
                }
            },
        )

        with patch.object(httpx.AsyncClient, "get", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = mock_response

            result = await gdrive_client.read_file(
                file_id="abc", auth_token="ya29.test"
            )

            assert result.is_error
            assert result.status == ToolCallStatus.ERROR
            assert "Forbidden" in result.error_message

    @pytest.mark.asyncio
    async def test_http_404_not_found(self, gdrive_client):
        """Test 9: HTTP 404 → ToolResult(ERROR) with 'Not found'."""
        mock_response = _mock_response(
            404, body={"error": {"code": 404, "message": "File not found: abc"}}
        )

        with patch.object(httpx.AsyncClient, "get", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = mock_response

            result = await gdrive_client.read_file(
                file_id="abc", auth_token="ya29.test"
            )

            assert result.is_error
            assert "Not found" in result.error_message

    @pytest.mark.asyncio
    async def test_http_429_rate_limit(self, gdrive_client):
        """Test 10: HTTP 429 → ToolResult(ERROR) with 'Rate limit'."""
        mock_response = _mock_response(
            429,
            body={"error": {"code": 429, "message": "Quota exceeded"}},
        )

        with patch.object(httpx.AsyncClient, "get", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = mock_response

            result = await gdrive_client.list_files(auth_token="ya29.test")

            assert result.is_error
            assert "Rate limit" in result.error_message

    @pytest.mark.asyncio
    async def test_http_500_server_error(self, gdrive_client):
        """HTTP 5xx → generic Google Drive API error."""
        mock_response = _mock_response(
            500, body={"error": {"message": "Internal error"}}
        )

        with patch.object(httpx.AsyncClient, "get", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = mock_response

            result = await gdrive_client.list_files(auth_token="ya29.test")

            assert result.is_error
            assert "Google Drive API error (500)" in result.error_message

    @pytest.mark.asyncio
    async def test_error_with_unparseable_body(self, gdrive_client):
        """Error response with non-JSON body falls back to raw text (truncated)."""
        long_text = "a" * 1000
        mock_response = MagicMock(spec=httpx.Response)
        mock_response.status_code = 502
        mock_response.json.side_effect = ValueError("not json")
        mock_response.text = long_text

        with patch.object(httpx.AsyncClient, "get", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = mock_response

            result = await gdrive_client.list_files(auth_token="ya29.test")

            assert result.is_error
            # Truncated to 500 chars — confirm the message shows truncation effect.
            assert len(result.raw["error"]) <= 500


# =============================================================================
# Network errors (Tests 11-12)
# =============================================================================


class TestNetworkErrors:
    @pytest.mark.asyncio
    async def test_timeout(self, gdrive_client):
        """Test 11: httpx.TimeoutException → ToolResult(TIMEOUT)."""
        with patch.object(httpx.AsyncClient, "get", new_callable=AsyncMock) as mock_get:
            mock_get.side_effect = httpx.TimeoutException("timed out")

            result = await gdrive_client.search_files(
                query="x", auth_token="ya29.test"
            )

            assert result.is_error
            assert result.status == ToolCallStatus.TIMEOUT
            assert "timed out" in result.error_message.lower()

    @pytest.mark.asyncio
    async def test_connection_error(self, gdrive_client):
        """Test 12: httpx.ConnectError → ToolResult(ERROR)."""
        with patch.object(httpx.AsyncClient, "get", new_callable=AsyncMock) as mock_get:
            mock_get.side_effect = httpx.ConnectError("connection refused")

            result = await gdrive_client.read_file(
                file_id="abc", auth_token="ya29.test"
            )

            assert result.is_error
            assert result.status == ToolCallStatus.ERROR
            assert "Request failed" in result.error_message


# =============================================================================
# call_tool dispatcher (Tests 13-14)
# =============================================================================


class TestCallToolDispatch:
    @pytest.mark.asyncio
    async def test_dispatch_search_files(self, gdrive_client):
        """Test 13a: call_tool('search_files', ...) routes to search_files.

        The dispatcher wraps plain-text queries (without Drive operators)
        into ``fullText contains '...'`` syntax automatically.
        """
        with patch.object(
            gdrive_client, "search_files", new_callable=AsyncMock
        ) as mock_method:
            mock_method.return_value = MagicMock(is_error=False)

            await gdrive_client.call_tool(
                "search_files", {"query": "test"}, auth_token="ya29.test"
            )

            mock_method.assert_awaited_once()
            assert mock_method.await_args.kwargs["query"] == "fullText contains 'test'"
            assert mock_method.await_args.kwargs["auth_token"] == "ya29.test"

    @pytest.mark.asyncio
    async def test_dispatch_read_file(self, gdrive_client):
        """Test 13b: call_tool('read_file', ...) routes to read_file."""
        with patch.object(
            gdrive_client, "read_file", new_callable=AsyncMock
        ) as mock_method:
            mock_method.return_value = MagicMock(is_error=False)

            await gdrive_client.call_tool(
                "read_file", {"file_id": "abc"}, auth_token="ya29.test"
            )

            mock_method.assert_awaited_once()
            assert mock_method.await_args.kwargs["file_id"] == "abc"

    @pytest.mark.asyncio
    async def test_dispatch_list_files(self, gdrive_client):
        """Test 13c: call_tool('list_files', ...) routes to list_files."""
        with patch.object(
            gdrive_client, "list_files", new_callable=AsyncMock
        ) as mock_method:
            mock_method.return_value = MagicMock(is_error=False)

            await gdrive_client.call_tool(
                "list_files",
                {"page_size": 50, "order_by": "name"},
                auth_token="ya29.test",
            )

            mock_method.assert_awaited_once()
            assert mock_method.await_args.kwargs["page_size"] == 50
            assert mock_method.await_args.kwargs["order_by"] == "name"

    @pytest.mark.asyncio
    async def test_dispatch_get_file_metadata(self, gdrive_client):
        """Test 13d: call_tool('get_file_metadata', ...) routes correctly."""
        with patch.object(
            gdrive_client, "get_file_metadata", new_callable=AsyncMock
        ) as mock_method:
            mock_method.return_value = MagicMock(is_error=False)

            await gdrive_client.call_tool(
                "get_file_metadata",
                {"file_id": "abc123"},
                auth_token="ya29.test",
            )

            mock_method.assert_awaited_once()
            assert mock_method.await_args.kwargs["file_id"] == "abc123"

    @pytest.mark.asyncio
    async def test_dispatch_camelcase_aliases(self, gdrive_client):
        """call_tool accepts both snake_case and camelCase argument keys."""
        with patch.object(
            gdrive_client, "read_file", new_callable=AsyncMock
        ) as mock_method:
            mock_method.return_value = MagicMock(is_error=False)

            await gdrive_client.call_tool(
                "read_file", {"fileId": "abc"}, auth_token="ya29.test"
            )

            mock_method.assert_awaited_once()
            assert mock_method.await_args.kwargs["file_id"] == "abc"

    @pytest.mark.asyncio
    async def test_dispatch_read_file_missing_id(self, gdrive_client):
        """call_tool('read_file', {}) → ERROR (no file_id)."""
        result = await gdrive_client.call_tool(
            "read_file", {}, auth_token="ya29.test"
        )
        assert result.is_error
        assert "file_id is required" in result.error_message

    @pytest.mark.asyncio
    async def test_dispatch_unknown_tool(self, gdrive_client):
        """Test 14: unknown tool → ToolResult(ERROR) with 'Unknown tool'."""
        result = await gdrive_client.call_tool(
            "delete_universe", {}, auth_token="ya29.test"
        )
        assert result.is_error
        assert result.status == ToolCallStatus.ERROR
        assert "Unknown tool" in result.error_message


# =============================================================================
# Auth token never logged (Security)
# =============================================================================


class TestSecurity:
    @pytest.mark.asyncio
    async def test_auth_token_not_in_logs(self, gdrive_client, caplog):
        """Auth token must never appear in log output."""
        import logging

        caplog.set_level(logging.DEBUG, logger="app.backends.gdrive_client")

        mock_response = _mock_response(200, body={"files": []})
        with patch.object(httpx.AsyncClient, "get", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = mock_response
            await gdrive_client.search_files(
                query="x", auth_token="SUPER_SECRET_TOKEN_123"
            )

        for record in caplog.records:
            assert "SUPER_SECRET_TOKEN_123" not in record.getMessage()


# =============================================================================
# WS-D6 gap-fill tests — coverage matrix cells
# =============================================================================


class TestConfigFallback:
    """Config fallback when settings import fails."""

    def test_config_fallback_on_attribute_error(self):
        """When get_settings().gdrive raises AttributeError, fallback to defaults."""
        mock_settings = MagicMock()
        del mock_settings.gdrive  # Accessing .gdrive will raise AttributeError
        with patch("app.core.config.get_settings", return_value=mock_settings):
            client = GDriveDirectClient()
        assert client.base_url == "https://www.googleapis.com/drive/v3"
        assert client.timeout == 30.0


class TestTransformResponseEdgeCases:
    """Edge cases in _transform_response that aren't hit by happy-path tests."""

    @pytest.mark.asyncio
    async def test_success_response_with_unparseable_json(self, gdrive_client):
        """When 200 response body isn't valid JSON, result should still succeed."""
        response = MagicMock(spec=httpx.Response)
        response.status_code = 200
        response.json.side_effect = ValueError("bad json")
        response.text = "not-json"

        with patch.object(httpx.AsyncClient, "get", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = response
            result = await gdrive_client.search_files(query="x", auth_token="tok")

        assert not result.is_error
        assert result.raw == {"raw_text": "not-json"}

    @pytest.mark.asyncio
    async def test_http_400_validation_error(self, gdrive_client):
        """HTTP 400 should return a validation error message."""
        response = _mock_response(
            400, body={"error": {"message": "Invalid query"}}
        )
        with patch.object(httpx.AsyncClient, "get", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = response
            result = await gdrive_client.search_files(query="x", auth_token="tok")

        assert result.is_error
        assert "Validation error" in result.error_message or "Invalid query" in result.error_message


class TestPerToolNetworkErrors:
    """Timeout/connection errors for tools other than search_files (gap-fill)."""

    @pytest.mark.asyncio
    async def test_list_files_timeout(self, gdrive_client):
        with patch.object(httpx.AsyncClient, "get", new_callable=AsyncMock) as mock_get:
            mock_get.side_effect = httpx.TimeoutException("timed out")
            result = await gdrive_client.list_files(auth_token="tok")
        assert result.is_error
        assert result.status == ToolCallStatus.TIMEOUT

    @pytest.mark.asyncio
    async def test_get_file_metadata_connection_error(self, gdrive_client):
        with patch.object(httpx.AsyncClient, "get", new_callable=AsyncMock) as mock_get:
            mock_get.side_effect = httpx.ConnectError("refused")
            result = await gdrive_client.get_file_metadata(
                file_id="f1", auth_token="tok"
            )
        assert result.is_error
        assert result.status == ToolCallStatus.ERROR

    @pytest.mark.asyncio
    async def test_read_file_timeout(self, gdrive_client):
        with patch.object(httpx.AsyncClient, "get", new_callable=AsyncMock) as mock_get:
            mock_get.side_effect = httpx.TimeoutException("timed out")
            result = await gdrive_client.read_file(file_id="f1", auth_token="tok")
        assert result.is_error
        assert result.status == ToolCallStatus.TIMEOUT

    @pytest.mark.asyncio
    async def test_get_file_metadata_timeout(self, gdrive_client):
        with patch.object(httpx.AsyncClient, "get", new_callable=AsyncMock) as mock_get:
            mock_get.side_effect = httpx.TimeoutException("timed out")
            result = await gdrive_client.get_file_metadata(
                file_id="f1", auth_token="tok"
            )
        assert result.is_error
        assert result.status == ToolCallStatus.TIMEOUT


class TestDispatcherMissingParams:
    """Gap: missing file_id in _call_get_file_metadata via call_tool."""

    @pytest.mark.asyncio
    async def test_dispatch_get_file_metadata_missing_id(self, gdrive_client):
        result = await gdrive_client.call_tool(
            "get_file_metadata", {}, auth_token="tok"
        )
        assert result.is_error
        assert "file_id" in result.error_message.lower()
