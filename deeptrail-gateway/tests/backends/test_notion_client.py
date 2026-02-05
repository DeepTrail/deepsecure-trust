"""Tests for Notion MCP client (WS-D3)."""

import pytest
from unittest.mock import AsyncMock, MagicMock

from app.backends.notion_client import (
    NotionMCPClient,
    NotionClientError,
    NotionRateLimitError,
    NotionObjectNotFoundError,
    NotionValidationError,
    NotionPageType,
    NotionPropertyType,
    create_notion_client,
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
def notion_client(mock_connection_manager):
    """Create Notion client with mock connection manager."""
    return NotionMCPClient(mock_connection_manager)


# =============================================================================
# Basic Properties Tests
# =============================================================================


class TestNotionMCPClient:
    """Tests for NotionMCPClient basic properties."""
    
    def test_backend_id(self, notion_client):
        """Test backend_id is 'notion'."""
        assert notion_client.backend_id == "notion"
    
    def test_repr(self, notion_client):
        """Test string representation."""
        repr_str = repr(notion_client)
        assert "NotionMCPClient" in repr_str
        assert "notion" in repr_str
    
    def test_is_not_initialized_by_default(self, notion_client):
        """Test client is not initialized by default."""
        assert not notion_client.is_initialized
    
    def test_server_info_is_none_before_initialize(self, notion_client):
        """Test server_info is None before initialize."""
        assert notion_client.server_info is None


# =============================================================================
# Argument Validation Tests
# =============================================================================


class TestArgumentValidation:
    """Tests for argument validation."""
    
    # ─────────────────────────────────────────────────────────────────────────
    # search_pages
    # ─────────────────────────────────────────────────────────────────────────
    
    def test_search_pages_no_required_args(self, notion_client):
        """Test search_pages has no required args."""
        result = notion_client.validate_tool_arguments("search_pages", {})
        assert result == {}
    
    def test_search_pages_with_query(self, notion_client):
        """Test search_pages with query."""
        args = {"query": "test", "page_size": 10}
        result = notion_client.validate_tool_arguments("search_pages", args)
        assert result["query"] == "test"
        assert result["page_size"] == 10
    
    def test_search_pages_all_optional_args(self, notion_client):
        """Test search_pages with all optional args."""
        args = {
            "query": "meeting",
            "filter": {"property": "status"},
            "sort": {"direction": "ascending"},
            "page_size": 50,
            "start_cursor": "abc123",
        }
        result = notion_client.validate_tool_arguments("search_pages", args)
        assert result["query"] == "meeting"
        assert result["filter"] == {"property": "status"}
        assert result["page_size"] == 50
    
    # ─────────────────────────────────────────────────────────────────────────
    # read_page
    # ─────────────────────────────────────────────────────────────────────────
    
    def test_read_page_requires_page_id(self, notion_client):
        """Test read_page requires page_id."""
        with pytest.raises(ValueError) as exc:
            notion_client.validate_tool_arguments("read_page", {})
        assert "page_id" in str(exc.value)
    
    def test_read_page_with_none_page_id(self, notion_client):
        """Test read_page rejects None page_id."""
        with pytest.raises(ValueError) as exc:
            notion_client.validate_tool_arguments("read_page", {"page_id": None})
        assert "page_id" in str(exc.value)
    
    def test_read_page_with_page_id(self, notion_client):
        """Test read_page normalizes page_id."""
        args = {"page_id": "12345678123412341234123456789abc"}
        result = notion_client.validate_tool_arguments("read_page", args)
        # Should be normalized to hyphenated format
        assert result["page_id"] == "12345678-1234-1234-1234-123456789abc"
    
    def test_read_page_with_hyphenated_id(self, notion_client):
        """Test read_page accepts hyphenated page_id."""
        args = {"page_id": "12345678-1234-1234-1234-123456789abc"}
        result = notion_client.validate_tool_arguments("read_page", args)
        assert result["page_id"] == "12345678-1234-1234-1234-123456789abc"
    
    # ─────────────────────────────────────────────────────────────────────────
    # create_page
    # ─────────────────────────────────────────────────────────────────────────
    
    def test_create_page_requires_parent_and_properties(self, notion_client):
        """Test create_page requires parent and properties."""
        with pytest.raises(ValueError) as exc:
            notion_client.validate_tool_arguments("create_page", {})
        assert "parent" in str(exc.value) or "properties" in str(exc.value)
    
    def test_create_page_requires_properties_with_parent(self, notion_client):
        """Test create_page requires properties when parent is given."""
        with pytest.raises(ValueError) as exc:
            notion_client.validate_tool_arguments(
                "create_page", {"parent": {"page_id": "abc"}}
            )
        assert "properties" in str(exc.value)
    
    def test_create_page_with_all_required(self, notion_client):
        """Test create_page with all required args."""
        args = {
            "parent": {"page_id": "12345678123412341234123456789abc"},
            "properties": {"title": [{"text": {"content": "Test"}}]},
        }
        result = notion_client.validate_tool_arguments("create_page", args)
        assert result["parent"] == args["parent"]
        assert result["properties"] == args["properties"]
    
    def test_create_page_with_optional_args(self, notion_client):
        """Test create_page with optional args."""
        args = {
            "parent": {"database_id": "12345678123412341234123456789abc"},
            "properties": {"Name": {"title": [{"text": {"content": "New Page"}}]}},
            "children": [{"type": "paragraph", "paragraph": {"text": []}}],
            "icon": {"emoji": "📝"},
            "cover": {"external": {"url": "https://example.com/image.jpg"}},
        }
        result = notion_client.validate_tool_arguments("create_page", args)
        assert result["children"] == args["children"]
        assert result["icon"] == args["icon"]
        assert result["cover"] == args["cover"]
    
    # ─────────────────────────────────────────────────────────────────────────
    # update_page
    # ─────────────────────────────────────────────────────────────────────────
    
    def test_update_page_requires_page_id(self, notion_client):
        """Test update_page requires page_id."""
        with pytest.raises(ValueError) as exc:
            notion_client.validate_tool_arguments("update_page", {})
        assert "page_id" in str(exc.value)
    
    def test_update_page_with_page_id_only(self, notion_client):
        """Test update_page with just page_id."""
        args = {"page_id": "12345678123412341234123456789abc"}
        result = notion_client.validate_tool_arguments("update_page", args)
        assert result["page_id"] == "12345678-1234-1234-1234-123456789abc"
    
    def test_update_page_with_all_options(self, notion_client):
        """Test update_page with all optional args."""
        args = {
            "page_id": "12345678123412341234123456789abc",
            "properties": {"Status": {"select": {"name": "Done"}}},
            "archived": True,
            "icon": {"emoji": "✅"},
            "cover": None,
        }
        result = notion_client.validate_tool_arguments("update_page", args)
        assert result["archived"] is True
        assert result["properties"] == args["properties"]
    
    # ─────────────────────────────────────────────────────────────────────────
    # delete_page
    # ─────────────────────────────────────────────────────────────────────────
    
    def test_delete_page_requires_page_id(self, notion_client):
        """Test delete_page requires page_id."""
        with pytest.raises(ValueError) as exc:
            notion_client.validate_tool_arguments("delete_page", {})
        assert "page_id" in str(exc.value)
    
    def test_delete_page_with_page_id(self, notion_client):
        """Test delete_page with page_id."""
        args = {"page_id": "12345678123412341234123456789abc"}
        result = notion_client.validate_tool_arguments("delete_page", args)
        assert result["page_id"] == "12345678-1234-1234-1234-123456789abc"
    
    # ─────────────────────────────────────────────────────────────────────────
    # list_databases
    # ─────────────────────────────────────────────────────────────────────────
    
    def test_list_databases_no_required_args(self, notion_client):
        """Test list_databases has no required args."""
        result = notion_client.validate_tool_arguments("list_databases", {})
        assert result == {}
    
    def test_list_databases_with_page_size(self, notion_client):
        """Test list_databases with page_size."""
        args = {"page_size": 20}
        result = notion_client.validate_tool_arguments("list_databases", args)
        assert result["page_size"] == 20
    
    # ─────────────────────────────────────────────────────────────────────────
    # query_database
    # ─────────────────────────────────────────────────────────────────────────
    
    def test_query_database_requires_database_id(self, notion_client):
        """Test query_database requires database_id."""
        with pytest.raises(ValueError) as exc:
            notion_client.validate_tool_arguments("query_database", {})
        assert "database_id" in str(exc.value)
    
    def test_query_database_with_database_id(self, notion_client):
        """Test query_database normalizes database_id."""
        args = {"database_id": "abcdef12abcdef12abcdef12abcdef12"}
        result = notion_client.validate_tool_arguments("query_database", args)
        assert result["database_id"] == "abcdef12-abcd-ef12-abcd-ef12abcdef12"
    
    def test_query_database_with_all_options(self, notion_client):
        """Test query_database with all optional args."""
        args = {
            "database_id": "abcdef12abcdef12abcdef12abcdef12",
            "filter": {"property": "Status", "select": {"equals": "Active"}},
            "sorts": [{"property": "Created", "direction": "descending"}],
            "page_size": 50,
            "start_cursor": "cursor123",
        }
        result = notion_client.validate_tool_arguments("query_database", args)
        assert result["filter"] == args["filter"]
        assert result["sorts"] == args["sorts"]
        assert result["page_size"] == 50
    
    # ─────────────────────────────────────────────────────────────────────────
    # page_size validation
    # ─────────────────────────────────────────────────────────────────────────
    
    def test_page_size_validation_above_100(self, notion_client):
        """Test page_size must be <= 100."""
        with pytest.raises(ValueError) as exc:
            notion_client.validate_tool_arguments(
                "search_pages", {"page_size": 101}
            )
        assert "page_size" in str(exc.value)
    
    def test_page_size_zero_invalid(self, notion_client):
        """Test page_size 0 is invalid."""
        with pytest.raises(ValueError):
            notion_client.validate_tool_arguments(
                "search_pages", {"page_size": 0}
            )
    
    def test_page_size_negative_invalid(self, notion_client):
        """Test negative page_size is invalid."""
        with pytest.raises(ValueError):
            notion_client.validate_tool_arguments(
                "search_pages", {"page_size": -1}
            )
    
    def test_page_size_not_integer_invalid(self, notion_client):
        """Test non-integer page_size is invalid."""
        with pytest.raises(ValueError):
            notion_client.validate_tool_arguments(
                "search_pages", {"page_size": "10"}
            )
    
    def test_page_size_boundary_1(self, notion_client):
        """Test page_size = 1 is valid."""
        result = notion_client.validate_tool_arguments(
            "search_pages", {"page_size": 1}
        )
        assert result["page_size"] == 1
    
    def test_page_size_boundary_100(self, notion_client):
        """Test page_size = 100 is valid."""
        result = notion_client.validate_tool_arguments(
            "search_pages", {"page_size": 100}
        )
        assert result["page_size"] == 100
    
    # ─────────────────────────────────────────────────────────────────────────
    # Unknown tool handling
    # ─────────────────────────────────────────────────────────────────────────
    
    def test_unknown_tool_passthrough(self, notion_client):
        """Test unknown tools pass through."""
        args = {"foo": "bar", "baz": 123}
        result = notion_client.validate_tool_arguments("unknown_tool", args)
        assert result == args


# =============================================================================
# Notion ID Normalization Tests
# =============================================================================


class TestNotionIDNormalization:
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
    
    def test_normalize_uppercase_id(self, notion_client):
        """Test uppercase hex characters are accepted."""
        id_uppercase = "12345678ABCD1234ABCD123456789ABC"
        result = notion_client._normalize_notion_id(id_uppercase)
        # Normalization preserves original case but adds hyphens
        assert result == "12345678-ABCD-1234-ABCD-123456789ABC"
    
    def test_normalize_mixed_case_id(self, notion_client):
        """Test mixed case hex characters are accepted."""
        id_mixed = "12345678AbCd1234aBcD123456789abc"
        result = notion_client._normalize_notion_id(id_mixed)
        assert "-" in result
        assert len(result) == 36
    
    def test_invalid_id_length_short(self, notion_client):
        """Test short ID length rejected."""
        with pytest.raises(ValueError) as exc:
            notion_client._normalize_notion_id("tooshort")
        assert "Invalid Notion ID" in str(exc.value)
    
    def test_invalid_id_length_long(self, notion_client):
        """Test long ID length rejected."""
        with pytest.raises(ValueError) as exc:
            notion_client._normalize_notion_id(
                "12345678123412341234123456789abc0000"
            )
        assert "Invalid Notion ID" in str(exc.value)
    
    def test_invalid_id_characters(self, notion_client):
        """Test invalid characters rejected."""
        with pytest.raises(ValueError) as exc:
            notion_client._normalize_notion_id("zzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzz")
        assert "not hex" in str(exc.value)
    
    def test_invalid_id_with_special_chars(self, notion_client):
        """Test special characters rejected."""
        with pytest.raises(ValueError) as exc:
            notion_client._normalize_notion_id("1234567812341234123412345678!@#$")
        assert "not hex" in str(exc.value)
    
    def test_empty_id(self, notion_client):
        """Test empty ID rejected."""
        with pytest.raises(ValueError) as exc:
            notion_client._normalize_notion_id("")
        assert "cannot be empty" in str(exc.value)


# =============================================================================
# Result Transformation Tests
# =============================================================================


class TestResultTransformation:
    """Tests for result transformation."""
    
    def test_transform_rate_limit_error(self, notion_client):
        """Test rate limit error transformation."""
        error_result = ToolResult(
            status=ToolCallStatus.ERROR,
            is_error=True,
            error_message="rate limit exceeded (429)",
            content=[{"type": "text", "text": "Error"}],
        )
        
        result = notion_client.transform_tool_result("search_pages", error_result)
        
        assert result.is_error
        assert "rate limit" in result.error_message.lower()
    
    def test_transform_rate_limit_error_uppercase(self, notion_client):
        """Test rate limit error with uppercase RATE."""
        error_result = ToolResult(
            status=ToolCallStatus.ERROR,
            is_error=True,
            error_message="RATE LIMIT EXCEEDED",
            content=[{"type": "text", "text": "Error"}],
        )
        
        result = notion_client.transform_tool_result("search_pages", error_result)
        
        assert result.is_error
        assert "rate limit" in result.error_message.lower()
    
    def test_transform_429_error(self, notion_client):
        """Test 429 status code detection."""
        error_result = ToolResult(
            status=ToolCallStatus.ERROR,
            is_error=True,
            error_message="HTTP error 429",
            content=[{"type": "text", "text": "Error"}],
        )
        
        result = notion_client.transform_tool_result("read_page", error_result)
        
        assert result.is_error
        assert "rate limit" in result.error_message.lower()
    
    def test_transform_not_found_error(self, notion_client):
        """Test not found error transformation."""
        error_result = ToolResult(
            status=ToolCallStatus.ERROR,
            is_error=True,
            error_message="Object not found (404)",
            content=[{"type": "text", "text": "Error"}],
        )
        
        result = notion_client.transform_tool_result("read_page", error_result)
        
        assert result.is_error
        assert "not found" in result.error_message.lower()
    
    def test_transform_404_error(self, notion_client):
        """Test 404 status code detection."""
        error_result = ToolResult(
            status=ToolCallStatus.ERROR,
            is_error=True,
            error_message="HTTP 404: Page does not exist",
            content=[{"type": "text", "text": "Error"}],
        )
        
        result = notion_client.transform_tool_result("read_page", error_result)
        
        assert result.is_error
        assert "not found" in result.error_message.lower()
    
    def test_transform_validation_error(self, notion_client):
        """Test validation error transformation."""
        error_result = ToolResult(
            status=ToolCallStatus.ERROR,
            is_error=True,
            error_message="validation failed (400)",
            content=[{"type": "text", "text": "Error"}],
        )
        
        result = notion_client.transform_tool_result("create_page", error_result)
        
        assert result.is_error
        assert "invalid" in result.error_message.lower() or "validation" in result.error_message.lower()
    
    def test_transform_400_error(self, notion_client):
        """Test 400 status code detection."""
        error_result = ToolResult(
            status=ToolCallStatus.ERROR,
            is_error=True,
            error_message="400 Bad Request: Missing required field",
            content=[{"type": "text", "text": "Error"}],
        )
        
        result = notion_client.transform_tool_result("create_page", error_result)
        
        assert result.is_error
        assert "invalid" in result.error_message.lower()
    
    def test_transform_generic_error_unchanged(self, notion_client):
        """Test generic errors pass through unchanged."""
        error_result = ToolResult(
            status=ToolCallStatus.ERROR,
            is_error=True,
            error_message="Some other error",
            content=[{"type": "text", "text": "Error"}],
        )
        
        result = notion_client.transform_tool_result("read_page", error_result)
        
        assert result.is_error
        assert result.error_message == "Some other error"
    
    def test_transform_none_error_message(self, notion_client):
        """Test handling of None error message."""
        error_result = ToolResult(
            status=ToolCallStatus.ERROR,
            is_error=True,
            error_message=None,
            content=[{"type": "text", "text": "Error"}],
        )
        
        result = notion_client.transform_tool_result("read_page", error_result)
        
        assert result.is_error
    
    def test_successful_result_unchanged(self, notion_client):
        """Test successful results pass through."""
        success_result = ToolResult(
            status=ToolCallStatus.SUCCESS,
            is_error=False,
            content=[{"type": "text", "text": "Page content"}],
        )
        
        result = notion_client.transform_tool_result("read_page", success_result)
        
        assert not result.is_error
        assert result.content == success_result.content
    
    def test_successful_search_result(self, notion_client):
        """Test successful search result transformation."""
        success_result = ToolResult(
            status=ToolCallStatus.SUCCESS,
            is_error=False,
            content=[{"type": "text", "text": '{"results": [...]}'}],
        )
        
        result = notion_client.transform_tool_result("search_pages", success_result)
        
        assert not result.is_error
        assert result.content == success_result.content
    
    def test_preserves_raw_and_duration(self, notion_client):
        """Test transformation preserves raw and duration_ms."""
        error_result = ToolResult(
            status=ToolCallStatus.ERROR,
            is_error=True,
            error_message="rate limit",
            content=[{"type": "text", "text": "Error"}],
            raw={"original": "data"},
            duration_ms=150.5,
        )
        
        result = notion_client.transform_tool_result("search_pages", error_result)
        
        assert result.raw == {"original": "data"}
        assert result.duration_ms == 150.5


# =============================================================================
# Convenience Methods Tests
# =============================================================================


class TestConvenienceMethods:
    """Tests for convenience methods."""
    
    @pytest.mark.asyncio
    async def test_search_pages(self, notion_client, mock_connection_manager):
        """Test search_pages convenience method."""
        mock_response = MagicMock()
        mock_response.is_success = True
        mock_response.result = {"content": [{"type": "text", "text": "results"}]}
        mock_response.error = None
        mock_response.raw = {}
        mock_connection_manager.send_tools_call.return_value = mock_response
        
        await notion_client.search_pages(
            query="test",
            page_size=5,
            auth_token="Bearer xyz"
        )
        
        mock_connection_manager.send_tools_call.assert_called_once()
        call_args = mock_connection_manager.send_tools_call.call_args
        assert call_args.kwargs["tool_name"] == "search_pages"
        assert call_args.kwargs["arguments"]["query"] == "test"
        assert call_args.kwargs["arguments"]["page_size"] == 5
    
    @pytest.mark.asyncio
    async def test_search_pages_no_query(self, notion_client, mock_connection_manager):
        """Test search_pages without query."""
        mock_response = MagicMock()
        mock_response.is_success = True
        mock_response.result = {"content": [{"type": "text", "text": "results"}]}
        mock_response.error = None
        mock_response.raw = {}
        mock_connection_manager.send_tools_call.return_value = mock_response
        
        await notion_client.search_pages(page_size=20)
        
        call_args = mock_connection_manager.send_tools_call.call_args
        assert "query" not in call_args.kwargs["arguments"]
        assert call_args.kwargs["arguments"]["page_size"] == 20
    
    @pytest.mark.asyncio
    async def test_read_page(self, notion_client, mock_connection_manager):
        """Test read_page convenience method."""
        mock_response = MagicMock()
        mock_response.is_success = True
        mock_response.result = {"content": [{"type": "text", "text": "page content"}]}
        mock_response.error = None
        mock_response.raw = {}
        mock_connection_manager.send_tools_call.return_value = mock_response
        
        await notion_client.read_page(
            page_id="12345678-1234-1234-1234-123456789abc",
            auth_token="Bearer xyz"
        )
        
        call_args = mock_connection_manager.send_tools_call.call_args
        assert call_args.kwargs["tool_name"] == "read_page"
        assert call_args.kwargs["arguments"]["page_id"] == "12345678-1234-1234-1234-123456789abc"
    
    @pytest.mark.asyncio
    async def test_create_page(self, notion_client, mock_connection_manager):
        """Test create_page convenience method."""
        mock_response = MagicMock()
        mock_response.is_success = True
        mock_response.result = {"content": [{"type": "text", "text": "created"}]}
        mock_response.error = None
        mock_response.raw = {}
        mock_connection_manager.send_tools_call.return_value = mock_response
        
        parent = {"database_id": "12345678-1234-1234-1234-123456789abc"}
        properties = {"Name": {"title": [{"text": {"content": "Test"}}]}}
        children = [{"type": "paragraph"}]
        
        await notion_client.create_page(
            parent=parent,
            properties=properties,
            children=children,
            auth_token="Bearer xyz"
        )
        
        call_args = mock_connection_manager.send_tools_call.call_args
        assert call_args.kwargs["tool_name"] == "create_page"
        assert call_args.kwargs["arguments"]["parent"] == parent
        assert call_args.kwargs["arguments"]["properties"] == properties
        assert call_args.kwargs["arguments"]["children"] == children
    
    @pytest.mark.asyncio
    async def test_create_page_no_children(self, notion_client, mock_connection_manager):
        """Test create_page without children."""
        mock_response = MagicMock()
        mock_response.is_success = True
        mock_response.result = {"content": [{"type": "text", "text": "created"}]}
        mock_response.error = None
        mock_response.raw = {}
        mock_connection_manager.send_tools_call.return_value = mock_response
        
        await notion_client.create_page(
            parent={"page_id": "12345678-1234-1234-1234-123456789abc"},
            properties={"Name": {"title": []}}
        )
        
        call_args = mock_connection_manager.send_tools_call.call_args
        assert "children" not in call_args.kwargs["arguments"]
    
    @pytest.mark.asyncio
    async def test_update_page(self, notion_client, mock_connection_manager):
        """Test update_page convenience method."""
        mock_response = MagicMock()
        mock_response.is_success = True
        mock_response.result = {"content": [{"type": "text", "text": "updated"}]}
        mock_response.error = None
        mock_response.raw = {}
        mock_connection_manager.send_tools_call.return_value = mock_response
        
        await notion_client.update_page(
            page_id="12345678-1234-1234-1234-123456789abc",
            properties={"Status": {"select": {"name": "Done"}}},
            archived=False,
            auth_token="Bearer xyz"
        )
        
        call_args = mock_connection_manager.send_tools_call.call_args
        assert call_args.kwargs["tool_name"] == "update_page"
        assert call_args.kwargs["arguments"]["archived"] is False
    
    @pytest.mark.asyncio
    async def test_delete_page(self, notion_client, mock_connection_manager):
        """Test delete_page convenience method."""
        mock_response = MagicMock()
        mock_response.is_success = True
        mock_response.result = {"content": [{"type": "text", "text": "deleted"}]}
        mock_response.error = None
        mock_response.raw = {}
        mock_connection_manager.send_tools_call.return_value = mock_response
        
        await notion_client.delete_page(
            page_id="12345678-1234-1234-1234-123456789abc",
            auth_token="Bearer xyz"
        )
        
        call_args = mock_connection_manager.send_tools_call.call_args
        assert call_args.kwargs["tool_name"] == "delete_page"
    
    @pytest.mark.asyncio
    async def test_list_databases(self, notion_client, mock_connection_manager):
        """Test list_databases convenience method."""
        mock_response = MagicMock()
        mock_response.is_success = True
        mock_response.result = {"content": [{"type": "text", "text": "databases"}]}
        mock_response.error = None
        mock_response.raw = {}
        mock_connection_manager.send_tools_call.return_value = mock_response
        
        await notion_client.list_databases(
            page_size=25,
            auth_token="Bearer xyz"
        )
        
        call_args = mock_connection_manager.send_tools_call.call_args
        assert call_args.kwargs["tool_name"] == "list_databases"
        assert call_args.kwargs["arguments"]["page_size"] == 25
    
    @pytest.mark.asyncio
    async def test_query_database(self, notion_client, mock_connection_manager):
        """Test query_database convenience method."""
        mock_response = MagicMock()
        mock_response.is_success = True
        mock_response.result = {"content": [{"type": "text", "text": "results"}]}
        mock_response.error = None
        mock_response.raw = {}
        mock_connection_manager.send_tools_call.return_value = mock_response
        
        filter_config = {"property": "Status", "select": {"equals": "Active"}}
        sorts_config = [{"property": "Created", "direction": "descending"}]
        
        await notion_client.query_database(
            database_id="12345678-1234-1234-1234-123456789abc",
            filter=filter_config,
            sorts=sorts_config,
            page_size=30,
            auth_token="Bearer xyz"
        )
        
        call_args = mock_connection_manager.send_tools_call.call_args
        assert call_args.kwargs["tool_name"] == "query_database"
        assert call_args.kwargs["arguments"]["filter"] == filter_config
        assert call_args.kwargs["arguments"]["sorts"] == sorts_config
        assert call_args.kwargs["arguments"]["page_size"] == 30
    
    @pytest.mark.asyncio
    async def test_query_database_minimal(self, notion_client, mock_connection_manager):
        """Test query_database with minimal args."""
        mock_response = MagicMock()
        mock_response.is_success = True
        mock_response.result = {"content": [{"type": "text", "text": "results"}]}
        mock_response.error = None
        mock_response.raw = {}
        mock_connection_manager.send_tools_call.return_value = mock_response
        
        await notion_client.query_database(
            database_id="12345678-1234-1234-1234-123456789abc"
        )
        
        call_args = mock_connection_manager.send_tools_call.call_args
        assert "filter" not in call_args.kwargs["arguments"]
        assert "sorts" not in call_args.kwargs["arguments"]
        assert call_args.kwargs["arguments"]["page_size"] == 10  # Default


# =============================================================================
# Factory Function Tests
# =============================================================================


class TestFactoryFunction:
    """Tests for factory function."""
    
    def test_create_notion_client(self, mock_connection_manager):
        """Test create_notion_client factory."""
        client = create_notion_client(mock_connection_manager)
        
        assert isinstance(client, NotionMCPClient)
        assert client.backend_id == "notion"
    
    def test_create_notion_client_with_options(self, mock_connection_manager):
        """Test create_notion_client with additional options."""
        client = create_notion_client(
            mock_connection_manager,
            auto_initialize=True
        )
        
        assert isinstance(client, NotionMCPClient)
        # auto_initialize is passed to BaseMCPClient


# =============================================================================
# Type Constants Tests
# =============================================================================


class TestTypeConstants:
    """Tests for type constant classes."""
    
    def test_notion_page_types(self):
        """Test NotionPageType constants."""
        assert NotionPageType.PAGE == "page"
        assert NotionPageType.DATABASE == "database"
        assert NotionPageType.BLOCK == "block"
    
    def test_notion_property_types(self):
        """Test NotionPropertyType constants."""
        assert NotionPropertyType.TITLE == "title"
        assert NotionPropertyType.RICH_TEXT == "rich_text"
        assert NotionPropertyType.NUMBER == "number"
        assert NotionPropertyType.SELECT == "select"
        assert NotionPropertyType.MULTI_SELECT == "multi_select"
        assert NotionPropertyType.DATE == "date"
        assert NotionPropertyType.CHECKBOX == "checkbox"
        assert NotionPropertyType.URL == "url"
        assert NotionPropertyType.EMAIL == "email"
        assert NotionPropertyType.PHONE_NUMBER == "phone_number"


# =============================================================================
# Exception Classes Tests
# =============================================================================


class TestExceptionClasses:
    """Tests for exception classes."""
    
    def test_notion_client_error(self):
        """Test NotionClientError base exception."""
        error = NotionClientError("Test error")
        assert str(error) == "Test error"
        assert isinstance(error, Exception)
    
    def test_notion_rate_limit_error(self):
        """Test NotionRateLimitError inheritance."""
        error = NotionRateLimitError("Rate limit exceeded")
        assert isinstance(error, NotionClientError)
        assert str(error) == "Rate limit exceeded"
    
    def test_notion_object_not_found_error(self):
        """Test NotionObjectNotFoundError inheritance."""
        error = NotionObjectNotFoundError("Page not found")
        assert isinstance(error, NotionClientError)
        assert str(error) == "Page not found"
    
    def test_notion_validation_error(self):
        """Test NotionValidationError inheritance."""
        error = NotionValidationError("Invalid input")
        assert isinstance(error, NotionClientError)
        assert str(error) == "Invalid input"
