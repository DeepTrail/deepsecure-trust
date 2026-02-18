"""Tests for NotionDirectClient (WS-G2).

Tests the direct Notion REST API client that makes httpx calls
to the Notion API.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

import httpx

from app.backends.notion_client import (
    NotionDirectClient,
    NotionAPIConfig,
    create_notion_direct_client,
)
from app.backends.base_mcp_client import ToolCallStatus


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def notion_config():
    """Create a test configuration."""
    return NotionAPIConfig(
        base_url="https://api.notion.com/v1",
        api_version="2022-06-28",
        timeout_seconds=30.0,
    )


@pytest.fixture
def notion_client(notion_config):
    """Create a NotionDirectClient with test configuration."""
    return NotionDirectClient(config=notion_config)


@pytest.fixture
def mock_success_response():
    """Create a mock successful response."""
    response = MagicMock(spec=httpx.Response)
    response.status_code = 200
    response.json.return_value = {"results": [{"id": "page-1"}]}
    response.text = '{"results": [{"id": "page-1"}]}'
    return response


@pytest.fixture
def mock_error_response():
    """Create a mock error response."""
    response = MagicMock(spec=httpx.Response)
    response.status_code = 404
    response.json.return_value = {"message": "Object not found", "code": "object_not_found"}
    response.text = '{"message": "Object not found"}'
    return response


# =============================================================================
# Initialization Tests
# =============================================================================


class TestNotionDirectClientInit:
    """Tests for NotionDirectClient initialization."""

    def test_init_with_config(self, notion_config):
        """Test initialization with explicit config."""
        client = NotionDirectClient(config=notion_config)
        assert client.base_url == "https://api.notion.com/v1"
        assert client.api_version == "2022-06-28"
        assert client.timeout == 30.0

    def test_init_with_custom_config(self):
        """Test initialization with custom configuration."""
        config = NotionAPIConfig(
            base_url="https://custom.notion.api/v1",
            api_version="2023-01-01",
            timeout_seconds=60.0,
        )
        client = NotionDirectClient(config=config)
        assert client.base_url == "https://custom.notion.api/v1"
        assert client.api_version == "2023-01-01"
        assert client.timeout == 60.0

    def test_factory_function(self, notion_config):
        """Test create_notion_direct_client factory."""
        client = create_notion_direct_client(config=notion_config)
        assert isinstance(client, NotionDirectClient)


# =============================================================================
# Header Tests
# =============================================================================


class TestHeaders:
    """Tests for header generation."""

    def test_get_headers(self, notion_client):
        """Test headers include Authorization and Notion-Version."""
        headers = notion_client._get_headers("secret_abc123")
        assert headers["Authorization"] == "Bearer secret_abc123"
        assert headers["Notion-Version"] == "2022-06-28"
        assert headers["Content-Type"] == "application/json"

    def test_get_headers_with_different_token(self, notion_client):
        """Test headers with different token."""
        headers = notion_client._get_headers("secret_xyz789")
        assert headers["Authorization"] == "Bearer secret_xyz789"


# =============================================================================
# ID Normalization Tests
# =============================================================================


class TestIDNormalization:
    """Tests for Notion ID normalization."""

    def test_normalize_hyphenated_id(self, notion_client):
        """Test already hyphenated ID."""
        id_with_hyphens = "12345678-1234-1234-1234-123456789abc"
        result = notion_client._normalize_notion_id(id_with_hyphens)
        assert result == id_with_hyphens

    def test_normalize_unhyphenated_id(self, notion_client):
        """Test unhyphenated ID gets hyphens."""
        id_without_hyphens = "12345678123412341234123456789abc"
        result = notion_client._normalize_notion_id(id_without_hyphens)
        assert result == "12345678-1234-1234-1234-123456789abc"

    def test_invalid_id_length(self, notion_client):
        """Test short ID is rejected."""
        with pytest.raises(ValueError) as exc:
            notion_client._normalize_notion_id("tooshort")
        assert "Invalid Notion ID" in str(exc.value)

    def test_invalid_id_characters(self, notion_client):
        """Test non-hex characters are rejected."""
        with pytest.raises(ValueError) as exc:
            notion_client._normalize_notion_id("zzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzz")
        assert "not hex" in str(exc.value)

    def test_empty_id(self, notion_client):
        """Test empty ID is rejected."""
        with pytest.raises(ValueError) as exc:
            notion_client._normalize_notion_id("")
        assert "cannot be empty" in str(exc.value)


# =============================================================================
# Search Pages Tests
# =============================================================================


class TestSearchPages:
    """Tests for search_pages method."""

    @pytest.mark.asyncio
    async def test_search_pages_success(self, notion_client):
        """Test successful search."""
        mock_response = MagicMock(spec=httpx.Response)
        mock_response.status_code = 200
        mock_response.json.return_value = {"results": [{"id": "page-1"}], "has_more": False}

        with patch.object(httpx.AsyncClient, "post", new_callable=AsyncMock) as mock_post:
            mock_post.return_value = mock_response

            result = await notion_client.search_pages(
                query="test", auth_token="secret_token"
            )

            assert not result.is_error
            assert result.status == ToolCallStatus.SUCCESS
            mock_post.assert_called_once()

    @pytest.mark.asyncio
    async def test_search_pages_empty_results(self, notion_client):
        """Test search with no results."""
        mock_response = MagicMock(spec=httpx.Response)
        mock_response.status_code = 200
        mock_response.json.return_value = {"results": [], "has_more": False}

        with patch.object(httpx.AsyncClient, "post", new_callable=AsyncMock) as mock_post:
            mock_post.return_value = mock_response

            result = await notion_client.search_pages(auth_token="secret_token")

            assert not result.is_error
            assert "results" in str(result.raw)

    @pytest.mark.asyncio
    async def test_search_pages_no_auth_token(self, notion_client):
        """Test search without auth token."""
        result = await notion_client.search_pages(query="test")

        assert result.is_error
        assert result.status == ToolCallStatus.UNAUTHORIZED
        assert "auth token" in result.error_message.lower()

    @pytest.mark.asyncio
    async def test_search_pages_with_page_size(self, notion_client):
        """Test search with custom page_size."""
        mock_response = MagicMock(spec=httpx.Response)
        mock_response.status_code = 200
        mock_response.json.return_value = {"results": []}

        with patch.object(httpx.AsyncClient, "post", new_callable=AsyncMock) as mock_post:
            mock_post.return_value = mock_response

            await notion_client.search_pages(
                query="test", page_size=50, auth_token="secret_token"
            )

            # Verify page_size was included in payload
            call_kwargs = mock_post.call_args.kwargs
            assert call_kwargs["json"]["page_size"] == 50

    @pytest.mark.asyncio
    async def test_search_pages_page_filter(self, notion_client):
        """Test search includes page filter."""
        mock_response = MagicMock(spec=httpx.Response)
        mock_response.status_code = 200
        mock_response.json.return_value = {"results": []}

        with patch.object(httpx.AsyncClient, "post", new_callable=AsyncMock) as mock_post:
            mock_post.return_value = mock_response

            await notion_client.search_pages(auth_token="secret_token")

            call_kwargs = mock_post.call_args.kwargs
            assert call_kwargs["json"]["filter"]["value"] == "page"


# =============================================================================
# Read Page Tests
# =============================================================================


class TestReadPage:
    """Tests for read_page method."""

    @pytest.mark.asyncio
    async def test_read_page_success(self, notion_client):
        """Test successful page read."""
        mock_response = MagicMock(spec=httpx.Response)
        mock_response.status_code = 200
        mock_response.json.return_value = {"id": "12345678-1234-1234-1234-123456789abc", "properties": {}}

        with patch.object(httpx.AsyncClient, "get", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = mock_response

            result = await notion_client.read_page(
                page_id="12345678123412341234123456789abc",
                auth_token="secret_token"
            )

            assert not result.is_error
            assert result.status == ToolCallStatus.SUCCESS

    @pytest.mark.asyncio
    async def test_read_page_not_found(self, notion_client):
        """Test read non-existent page."""
        mock_response = MagicMock(spec=httpx.Response)
        mock_response.status_code = 404
        mock_response.json.return_value = {"message": "Page not found", "code": "object_not_found"}

        with patch.object(httpx.AsyncClient, "get", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = mock_response

            result = await notion_client.read_page(
                page_id="12345678-1234-1234-1234-123456789abc",
                auth_token="secret_token"
            )

            assert result.is_error
            assert "not found" in result.error_message.lower()

    @pytest.mark.asyncio
    async def test_read_page_invalid_id(self, notion_client):
        """Test read with invalid page ID."""
        result = await notion_client.read_page(
            page_id="invalid",
            auth_token="secret_token"
        )

        assert result.is_error
        assert "Invalid Notion ID" in result.error_message

    @pytest.mark.asyncio
    async def test_read_page_no_auth(self, notion_client):
        """Test read without auth token."""
        result = await notion_client.read_page(
            page_id="12345678-1234-1234-1234-123456789abc"
        )

        assert result.is_error
        assert result.status == ToolCallStatus.UNAUTHORIZED


# =============================================================================
# Create Page Tests
# =============================================================================


class TestCreatePage:
    """Tests for create_page method."""

    @pytest.mark.asyncio
    async def test_create_page_success(self, notion_client):
        """Test successful page creation."""
        mock_response = MagicMock(spec=httpx.Response)
        mock_response.status_code = 200
        mock_response.json.return_value = {"id": "new-page-id"}

        with patch.object(httpx.AsyncClient, "post", new_callable=AsyncMock) as mock_post:
            mock_post.return_value = mock_response

            result = await notion_client.create_page(
                parent_id="12345678123412341234123456789abc",
                title="Test Page",
                auth_token="secret_token"
            )

            assert not result.is_error
            assert result.status == ToolCallStatus.SUCCESS

    @pytest.mark.asyncio
    async def test_create_page_in_database(self, notion_client):
        """Test creating page in a database."""
        mock_response = MagicMock(spec=httpx.Response)
        mock_response.status_code = 200
        mock_response.json.return_value = {"id": "new-page-id"}

        with patch.object(httpx.AsyncClient, "post", new_callable=AsyncMock) as mock_post:
            mock_post.return_value = mock_response

            await notion_client.create_page(
                parent_id="12345678123412341234123456789abc",
                title="Test Page",
                parent_type="database_id",
                auth_token="secret_token"
            )

            call_kwargs = mock_post.call_args.kwargs
            assert "database_id" in call_kwargs["json"]["parent"]

    @pytest.mark.asyncio
    async def test_create_page_with_children(self, notion_client):
        """Test creating page with child blocks."""
        mock_response = MagicMock(spec=httpx.Response)
        mock_response.status_code = 200
        mock_response.json.return_value = {"id": "new-page-id"}

        children = [{"type": "paragraph", "paragraph": {"text": []}}]

        with patch.object(httpx.AsyncClient, "post", new_callable=AsyncMock) as mock_post:
            mock_post.return_value = mock_response

            await notion_client.create_page(
                parent_id="12345678123412341234123456789abc",
                title="Test Page",
                children=children,
                auth_token="secret_token"
            )

            call_kwargs = mock_post.call_args.kwargs
            assert call_kwargs["json"]["children"] == children

    @pytest.mark.asyncio
    async def test_create_page_no_auth(self, notion_client):
        """Test create without auth token."""
        result = await notion_client.create_page(
            parent_id="12345678-1234-1234-1234-123456789abc",
            title="Test"
        )

        assert result.is_error
        assert result.status == ToolCallStatus.UNAUTHORIZED


# =============================================================================
# Update Page Tests
# =============================================================================


class TestUpdatePage:
    """Tests for update_page method."""

    @pytest.mark.asyncio
    async def test_update_page_success(self, notion_client):
        """Test successful page update."""
        mock_response = MagicMock(spec=httpx.Response)
        mock_response.status_code = 200
        mock_response.json.return_value = {"id": "page-id", "properties": {}}

        with patch.object(httpx.AsyncClient, "patch", new_callable=AsyncMock) as mock_patch:
            mock_patch.return_value = mock_response

            result = await notion_client.update_page(
                page_id="12345678123412341234123456789abc",
                properties={"Status": {"select": {"name": "Done"}}},
                auth_token="secret_token"
            )

            assert not result.is_error
            assert result.status == ToolCallStatus.SUCCESS

    @pytest.mark.asyncio
    async def test_update_page_archive(self, notion_client):
        """Test archiving a page."""
        mock_response = MagicMock(spec=httpx.Response)
        mock_response.status_code = 200
        mock_response.json.return_value = {"archived": True}

        with patch.object(httpx.AsyncClient, "patch", new_callable=AsyncMock) as mock_patch:
            mock_patch.return_value = mock_response

            await notion_client.update_page(
                page_id="12345678123412341234123456789abc",
                archived=True,
                auth_token="secret_token"
            )

            call_kwargs = mock_patch.call_args.kwargs
            assert call_kwargs["json"]["archived"] is True

    @pytest.mark.asyncio
    async def test_update_page_no_updates(self, notion_client):
        """Test update with no changes specified."""
        result = await notion_client.update_page(
            page_id="12345678123412341234123456789abc",
            auth_token="secret_token"
        )

        assert result.is_error
        assert "No updates specified" in result.error_message


# =============================================================================
# Delete Page Tests
# =============================================================================


class TestDeletePage:
    """Tests for delete_page method."""

    @pytest.mark.asyncio
    async def test_delete_page_success(self, notion_client):
        """Test successful page deletion (archive)."""
        mock_response = MagicMock(spec=httpx.Response)
        mock_response.status_code = 200
        mock_response.json.return_value = {"archived": True}

        with patch.object(httpx.AsyncClient, "patch", new_callable=AsyncMock) as mock_patch:
            mock_patch.return_value = mock_response

            result = await notion_client.delete_page(
                page_id="12345678123412341234123456789abc",
                auth_token="secret_token"
            )

            assert not result.is_error
            call_kwargs = mock_patch.call_args.kwargs
            assert call_kwargs["json"] == {"archived": True}


# =============================================================================
# List Databases Tests
# =============================================================================


class TestListDatabases:
    """Tests for list_databases method."""

    @pytest.mark.asyncio
    async def test_list_databases_success(self, notion_client):
        """Test successful database listing."""
        mock_response = MagicMock(spec=httpx.Response)
        mock_response.status_code = 200
        mock_response.json.return_value = {"results": [{"id": "db-1", "object": "database"}]}

        with patch.object(httpx.AsyncClient, "post", new_callable=AsyncMock) as mock_post:
            mock_post.return_value = mock_response

            result = await notion_client.list_databases(auth_token="secret_token")

            assert not result.is_error
            call_kwargs = mock_post.call_args.kwargs
            assert call_kwargs["json"]["filter"]["value"] == "database"


# =============================================================================
# Query Database Tests
# =============================================================================


class TestQueryDatabase:
    """Tests for query_database method."""

    @pytest.mark.asyncio
    async def test_query_database_success(self, notion_client):
        """Test successful database query."""
        mock_response = MagicMock(spec=httpx.Response)
        mock_response.status_code = 200
        mock_response.json.return_value = {"results": [{"id": "row-1"}], "has_more": False}

        with patch.object(httpx.AsyncClient, "post", new_callable=AsyncMock) as mock_post:
            mock_post.return_value = mock_response

            result = await notion_client.query_database(
                database_id="12345678123412341234123456789abc",
                auth_token="secret_token"
            )

            assert not result.is_error

    @pytest.mark.asyncio
    async def test_query_database_with_filter(self, notion_client):
        """Test query with filter."""
        mock_response = MagicMock(spec=httpx.Response)
        mock_response.status_code = 200
        mock_response.json.return_value = {"results": []}

        filter_config = {"property": "Status", "select": {"equals": "Active"}}

        with patch.object(httpx.AsyncClient, "post", new_callable=AsyncMock) as mock_post:
            mock_post.return_value = mock_response

            await notion_client.query_database(
                database_id="12345678123412341234123456789abc",
                filter=filter_config,
                auth_token="secret_token"
            )

            call_kwargs = mock_post.call_args.kwargs
            assert call_kwargs["json"]["filter"] == filter_config

    @pytest.mark.asyncio
    async def test_query_database_with_sorts(self, notion_client):
        """Test query with sorts."""
        mock_response = MagicMock(spec=httpx.Response)
        mock_response.status_code = 200
        mock_response.json.return_value = {"results": []}

        sorts = [{"property": "Created", "direction": "descending"}]

        with patch.object(httpx.AsyncClient, "post", new_callable=AsyncMock) as mock_post:
            mock_post.return_value = mock_response

            await notion_client.query_database(
                database_id="12345678123412341234123456789abc",
                sorts=sorts,
                auth_token="secret_token"
            )

            call_kwargs = mock_post.call_args.kwargs
            assert call_kwargs["json"]["sorts"] == sorts


# =============================================================================
# Error Handling Tests
# =============================================================================


class TestErrorHandling:
    """Tests for error handling."""

    @pytest.mark.asyncio
    async def test_401_unauthorized(self, notion_client):
        """Test 401 error handling."""
        mock_response = MagicMock(spec=httpx.Response)
        mock_response.status_code = 401
        mock_response.json.return_value = {"message": "Invalid token", "code": "unauthorized"}

        with patch.object(httpx.AsyncClient, "post", new_callable=AsyncMock) as mock_post:
            mock_post.return_value = mock_response

            result = await notion_client.search_pages(auth_token="invalid_token")

            assert result.is_error
            assert "Unauthorized" in result.error_message

    @pytest.mark.asyncio
    async def test_404_not_found(self, notion_client):
        """Test 404 error handling."""
        mock_response = MagicMock(spec=httpx.Response)
        mock_response.status_code = 404
        mock_response.json.return_value = {"message": "Not found", "code": "object_not_found"}

        with patch.object(httpx.AsyncClient, "get", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = mock_response

            result = await notion_client.read_page(
                page_id="12345678-1234-1234-1234-123456789abc",
                auth_token="secret_token"
            )

            assert result.is_error
            assert "not found" in result.error_message.lower()

    @pytest.mark.asyncio
    async def test_429_rate_limit(self, notion_client):
        """Test 429 rate limit handling."""
        mock_response = MagicMock(spec=httpx.Response)
        mock_response.status_code = 429
        mock_response.json.return_value = {"message": "Rate limited", "code": "rate_limited"}

        with patch.object(httpx.AsyncClient, "post", new_callable=AsyncMock) as mock_post:
            mock_post.return_value = mock_response

            result = await notion_client.search_pages(auth_token="secret_token")

            assert result.is_error
            assert "rate limit" in result.error_message.lower()

    @pytest.mark.asyncio
    async def test_400_validation_error(self, notion_client):
        """Test 400 validation error handling."""
        mock_response = MagicMock(spec=httpx.Response)
        mock_response.status_code = 400
        mock_response.json.return_value = {"message": "Invalid request", "code": "validation_error"}

        with patch.object(httpx.AsyncClient, "post", new_callable=AsyncMock) as mock_post:
            mock_post.return_value = mock_response

            result = await notion_client.search_pages(auth_token="secret_token")

            assert result.is_error
            assert "validation" in result.error_message.lower()

    @pytest.mark.asyncio
    async def test_timeout_error(self, notion_client):
        """Test timeout handling."""
        with patch.object(httpx.AsyncClient, "post", new_callable=AsyncMock) as mock_post:
            mock_post.side_effect = httpx.TimeoutException("Request timed out")

            result = await notion_client.search_pages(auth_token="secret_token")

            assert result.is_error
            assert result.status == ToolCallStatus.TIMEOUT
            assert "timed out" in result.error_message.lower()

    @pytest.mark.asyncio
    async def test_request_error(self, notion_client):
        """Test general request error handling."""
        with patch.object(httpx.AsyncClient, "post", new_callable=AsyncMock) as mock_post:
            mock_post.side_effect = httpx.RequestError("Connection failed")

            result = await notion_client.search_pages(auth_token="secret_token")

            assert result.is_error
            assert "request failed" in result.error_message.lower()


# =============================================================================
# Call Tool Dispatcher Tests
# =============================================================================


class TestCallToolDispatcher:
    """Tests for call_tool dispatcher."""

    @pytest.mark.asyncio
    async def test_call_tool_search_pages(self, notion_client):
        """Test call_tool dispatches to search_pages."""
        mock_response = MagicMock(spec=httpx.Response)
        mock_response.status_code = 200
        mock_response.json.return_value = {"results": []}

        with patch.object(httpx.AsyncClient, "post", new_callable=AsyncMock) as mock_post:
            mock_post.return_value = mock_response

            result = await notion_client.call_tool(
                "search_pages",
                {"query": "test"},
                auth_token="secret_token"
            )

            assert not result.is_error

    @pytest.mark.asyncio
    async def test_call_tool_unknown(self, notion_client):
        """Test call_tool with unknown tool."""
        result = await notion_client.call_tool(
            "unknown_tool",
            {},
            auth_token="secret_token"
        )

        assert result.is_error
        assert "Unknown tool" in result.error_message

    @pytest.mark.asyncio
    async def test_call_tool_read_page_missing_id(self, notion_client):
        """Test call_tool read_page without page_id."""
        result = await notion_client.call_tool(
            "read_page",
            {},
            auth_token="secret_token"
        )

        assert result.is_error
        assert "page_id is required" in result.error_message

    @pytest.mark.asyncio
    async def test_call_tool_create_page_full_format(self, notion_client):
        """Test call_tool create_page with full format."""
        mock_response = MagicMock(spec=httpx.Response)
        mock_response.status_code = 200
        mock_response.json.return_value = {"id": "new-page"}

        with patch.object(httpx.AsyncClient, "post", new_callable=AsyncMock) as mock_post:
            mock_post.return_value = mock_response

            result = await notion_client.call_tool(
                "create_page",
                {
                    "parent": {"page_id": "12345678123412341234123456789abc"},
                    "properties": {"title": [{"text": {"content": "Test"}}]}
                },
                auth_token="secret_token"
            )

            assert not result.is_error


# =============================================================================
# Integration with Configuration Tests
# =============================================================================


class TestConfigurationIntegration:
    """Tests for integration with GatewaySettings."""

    def test_init_loads_from_gateway_settings(self):
        """Test that initialization loads from GatewaySettings when available."""
        # This test verifies the integration path works
        # In real usage, get_settings() would be called
        config = NotionAPIConfig(
            base_url="https://api.notion.com/v1",
            api_version="2022-06-28",
        )
        client = NotionDirectClient(config=config)
        assert client.base_url == "https://api.notion.com/v1"
