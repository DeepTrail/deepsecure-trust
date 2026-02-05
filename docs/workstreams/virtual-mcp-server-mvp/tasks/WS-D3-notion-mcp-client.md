# Task: WS-D3 Implement Notion MCP Client

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
- [ ] Notion API documentation reviewed for tool schemas

---

## Task Description

Implement the Notion MCP client that extends `BaseMCPClient` to provide Notion-specific tool operations. This enables the gateway to proxy MCP requests to a Notion MCP server backend.

### Context

From the MVP design (Section 2.6 - Step 8: Agent Executes Task):

```
Sarah's agent needs to access Notion tools:
- search_pages: Search for pages in Notion workspace
- read_page: Read content from a specific page
- create_page: Create new pages in Notion

The Notion MCP client:
1. Extends BaseMCPClient with backend_id = "notion"
2. Provides Notion-specific argument validation
3. Transforms Notion API responses to standard MCP format
4. Handles Notion-specific error cases
```

### MVP Notion Tools

| Tool Name | Permission | Description |
|-----------|------------|-------------|
| `search_pages` | `notion:pages:search` | Search pages in workspace |
| `read_page` | `notion:pages:read` | Read page content by ID |
| `create_page` | `notion:pages:create` | Create a new page |
| `update_page` | `notion:pages:update` | Update existing page |
| `delete_page` | `notion:pages:delete` | Archive a page |
| `list_databases` | `notion:databases:list` | List databases |
| `query_database` | `notion:databases:query` | Query database |

---

## Files to Create/Modify

| File | Action | Description |
|------|--------|-------------|
| `deeptrail-gateway/app/backends/notion_client.py` | **CREATE** | Notion MCP client implementation |
| `deeptrail-gateway/app/backends/__init__.py` | **MODIFY** | Export NotionMCPClient |
| `deeptrail-gateway/tests/backends/test_notion_client.py` | **CREATE** | Unit tests |

---

## Implementation Details

### 1. Notion MCP Client

Create `deeptrail-gateway/app/backends/notion_client.py`:

```python
"""
Notion MCP Client

Extends BaseMCPClient to provide Notion-specific tool operations.
Proxies MCP requests to a Notion MCP server backend.

MVP Tools:
- search_pages: Search pages in workspace
- read_page: Read page content by ID
- create_page: Create a new page
- update_page: Update existing page
- delete_page: Archive a page
- list_databases: List all databases
- query_database: Query a database

Usage:
    from app.backends.notion_client import NotionMCPClient
    
    client = NotionMCPClient(connection_manager)
    await client.initialize(auth_token="Bearer xyz")
    
    # Search for pages
    result = await client.call_tool(
        "search_pages",
        {"query": "meeting notes"},
        auth_token="Bearer xyz"
    )
"""

import logging
from typing import Any

from .base_mcp_client import (
    BaseMCPClient,
    BackendConnectionManager,
    ToolResult,
    ToolCallStatus,
)

logger = logging.getLogger(__name__)


# =============================================================================
# Notion-Specific Types
# =============================================================================


class NotionPageType:
    """Notion page types."""
    PAGE = "page"
    DATABASE = "database"
    BLOCK = "block"


class NotionPropertyType:
    """Notion property types for validation."""
    TITLE = "title"
    RICH_TEXT = "rich_text"
    NUMBER = "number"
    SELECT = "select"
    MULTI_SELECT = "multi_select"
    DATE = "date"
    CHECKBOX = "checkbox"
    URL = "url"
    EMAIL = "email"
    PHONE_NUMBER = "phone_number"


# =============================================================================
# Exceptions
# =============================================================================


class NotionClientError(Exception):
    """Notion-specific client error."""
    pass


class NotionRateLimitError(NotionClientError):
    """Notion API rate limit exceeded."""
    pass


class NotionObjectNotFoundError(NotionClientError):
    """Notion object (page, database, block) not found."""
    pass


# =============================================================================
# Notion MCP Client
# =============================================================================


class NotionMCPClient(BaseMCPClient):
    """
    MCP client for Notion backend.
    
    Provides Notion-specific:
    - Argument validation for Notion tools
    - Result transformation for Notion responses
    - Error handling for Notion API errors
    
    Attributes:
        backend_id: Always "notion"
    """
    
    # Tool-specific argument schemas for validation
    TOOL_SCHEMAS = {
        "search_pages": {
            "required": [],
            "optional": ["query", "filter", "sort", "page_size", "start_cursor"],
        },
        "read_page": {
            "required": ["page_id"],
            "optional": [],
        },
        "create_page": {
            "required": ["parent", "properties"],
            "optional": ["children", "icon", "cover"],
        },
        "update_page": {
            "required": ["page_id"],
            "optional": ["properties", "icon", "cover", "archived"],
        },
        "delete_page": {
            "required": ["page_id"],
            "optional": [],
        },
        "list_databases": {
            "required": [],
            "optional": ["page_size", "start_cursor"],
        },
        "query_database": {
            "required": ["database_id"],
            "optional": ["filter", "sorts", "page_size", "start_cursor"],
        },
    }
    
    @property
    def backend_id(self) -> str:
        """Return the Notion backend identifier."""
        return "notion"
    
    # ─────────────────────────────────────────────────────────────────────────
    # Argument Validation
    # ─────────────────────────────────────────────────────────────────────────
    
    def validate_tool_arguments(
        self,
        tool_name: str,
        arguments: dict[str, Any],
    ) -> dict[str, Any]:
        """
        Validate and transform Notion tool arguments.
        
        Args:
            tool_name: Notion tool name
            arguments: Raw arguments
            
        Returns:
            Validated arguments
            
        Raises:
            ValueError: If required arguments missing or invalid
        """
        schema = self.TOOL_SCHEMAS.get(tool_name)
        
        if schema is None:
            # Unknown tool - pass through to backend
            logger.warning(f"No schema for Notion tool: {tool_name}")
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
        
        # Validate page_id format (UUID with or without hyphens)
        if "page_id" in validated:
            validated["page_id"] = self._normalize_notion_id(validated["page_id"])
        
        if "database_id" in validated:
            validated["database_id"] = self._normalize_notion_id(validated["database_id"])
        
        # Validate page_size range
        if "page_size" in validated:
            page_size = validated["page_size"]
            if not isinstance(page_size, int) or page_size < 1 or page_size > 100:
                raise ValueError("page_size must be integer between 1 and 100")
        
        return validated
    
    def _normalize_notion_id(self, notion_id: str) -> str:
        """
        Normalize Notion ID to hyphenated UUID format.
        
        Notion accepts both:
        - 12345678-1234-1234-1234-123456789abc
        - 123456781234123412341234567890abc
        
        Args:
            notion_id: Notion object ID
            
        Returns:
            Normalized ID
            
        Raises:
            ValueError: If ID format is invalid
        """
        if not notion_id:
            raise ValueError("Notion ID cannot be empty")
        
        # Remove any existing hyphens
        clean_id = notion_id.replace("-", "")
        
        # Validate length (32 hex chars)
        if len(clean_id) != 32:
            raise ValueError(f"Invalid Notion ID: {notion_id}")
        
        # Validate hex characters
        try:
            int(clean_id, 16)
        except ValueError:
            raise ValueError(f"Invalid Notion ID (not hex): {notion_id}")
        
        # Return with hyphens (Notion's preferred format)
        return f"{clean_id[:8]}-{clean_id[8:12]}-{clean_id[12:16]}-{clean_id[16:20]}-{clean_id[20:]}"
    
    # ─────────────────────────────────────────────────────────────────────────
    # Result Transformation
    # ─────────────────────────────────────────────────────────────────────────
    
    def transform_tool_result(
        self,
        tool_name: str,
        result: ToolResult,
    ) -> ToolResult:
        """
        Transform Notion tool results.
        
        Handles:
        - Rate limit errors (429)
        - Object not found errors (404)
        - Validation errors (400)
        - Extracting useful content from responses
        
        Args:
            tool_name: Tool that was called
            result: Raw result from backend
            
        Returns:
            Transformed result
        """
        # Check for Notion-specific errors in the result
        if result.is_error:
            result = self._transform_error(tool_name, result)
        
        # Transform successful results based on tool type
        if not result.is_error and tool_name in ("search_pages", "query_database"):
            result = self._transform_list_result(tool_name, result)
        
        return result
    
    def _transform_error(self, tool_name: str, result: ToolResult) -> ToolResult:
        """Transform Notion error responses."""
        error_msg = result.error_message or ""
        
        # Detect rate limiting
        if "rate" in error_msg.lower() or "429" in error_msg:
            logger.warning(f"Notion rate limit hit for {tool_name}")
            return ToolResult(
                status=ToolCallStatus.ERROR,
                is_error=True,
                error_message="Notion rate limit exceeded. Please retry after a moment.",
                content=[{"type": "text", "text": "Rate limit exceeded"}],
                raw=result.raw,
                duration_ms=result.duration_ms,
            )
        
        # Detect not found
        if "not found" in error_msg.lower() or "404" in error_msg:
            return ToolResult(
                status=ToolCallStatus.ERROR,
                is_error=True,
                error_message=f"Notion object not found: {error_msg}",
                content=[{"type": "text", "text": "Object not found"}],
                raw=result.raw,
                duration_ms=result.duration_ms,
            )
        
        # Detect validation errors
        if "validation" in error_msg.lower() or "400" in error_msg:
            return ToolResult(
                status=ToolCallStatus.ERROR,
                is_error=True,
                error_message=f"Invalid request: {error_msg}",
                content=[{"type": "text", "text": f"Validation error: {error_msg}"}],
                raw=result.raw,
                duration_ms=result.duration_ms,
            )
        
        return result
    
    def _transform_list_result(self, tool_name: str, result: ToolResult) -> ToolResult:
        """Transform list-type results (search, query)."""
        # Extract result count for logging
        content = result.content
        if content and len(content) > 0:
            first_content = content[0]
            if first_content.get("type") == "text":
                text = first_content.get("text", "")
                # Log result count if available
                if "results" in text.lower():
                    logger.debug(f"Notion {tool_name} returned results")
        
        return result
    
    # ─────────────────────────────────────────────────────────────────────────
    # Convenience Methods
    # ─────────────────────────────────────────────────────────────────────────
    
    async def search_pages(
        self,
        query: str | None = None,
        page_size: int = 10,
        auth_token: str | None = None,
    ) -> ToolResult:
        """
        Search for pages in the Notion workspace.
        
        Args:
            query: Search query string
            page_size: Number of results (1-100)
            auth_token: Authorization token
            
        Returns:
            ToolResult with search results
        """
        arguments = {"page_size": page_size}
        if query:
            arguments["query"] = query
        
        return await self.call_tool("search_pages", arguments, auth_token=auth_token)
    
    async def read_page(
        self,
        page_id: str,
        auth_token: str | None = None,
    ) -> ToolResult:
        """
        Read a page's content.
        
        Args:
            page_id: Notion page ID
            auth_token: Authorization token
            
        Returns:
            ToolResult with page content
        """
        return await self.call_tool(
            "read_page",
            {"page_id": page_id},
            auth_token=auth_token,
        )
    
    async def create_page(
        self,
        parent: dict[str, Any],
        properties: dict[str, Any],
        children: list[dict[str, Any]] | None = None,
        auth_token: str | None = None,
    ) -> ToolResult:
        """
        Create a new page in Notion.
        
        Args:
            parent: Parent page or database reference
            properties: Page properties
            children: Optional child blocks
            auth_token: Authorization token
            
        Returns:
            ToolResult with created page info
        """
        arguments = {
            "parent": parent,
            "properties": properties,
        }
        if children:
            arguments["children"] = children
        
        return await self.call_tool("create_page", arguments, auth_token=auth_token)
    
    async def query_database(
        self,
        database_id: str,
        filter: dict[str, Any] | None = None,
        sorts: list[dict[str, Any]] | None = None,
        page_size: int = 10,
        auth_token: str | None = None,
    ) -> ToolResult:
        """
        Query a Notion database.
        
        Args:
            database_id: Notion database ID
            filter: Filter conditions
            sorts: Sort configuration
            page_size: Number of results
            auth_token: Authorization token
            
        Returns:
            ToolResult with query results
        """
        arguments = {
            "database_id": database_id,
            "page_size": page_size,
        }
        if filter:
            arguments["filter"] = filter
        if sorts:
            arguments["sorts"] = sorts
        
        return await self.call_tool("query_database", arguments, auth_token=auth_token)


# =============================================================================
# Factory Function
# =============================================================================


def create_notion_client(
    connection_manager: BackendConnectionManager,
    **kwargs: Any,
) -> NotionMCPClient:
    """
    Create a Notion MCP client.
    
    Args:
        connection_manager: Backend connection manager
        **kwargs: Additional client options
        
    Returns:
        Configured NotionMCPClient
    """
    return NotionMCPClient(connection_manager, **kwargs)
```

### 2. Update `__init__.py`

Add to `deeptrail-gateway/app/backends/__init__.py`:

```python
from .base_mcp_client import (
    BaseMCPClient,
    GenericMCPClient,
    ToolResult,
    ToolSchema,
    ServerInfo,
    ToolCallStatus,
    MCPCapability,
    MCPClientError,
    MCPInitializeError,
    MCPToolNotFoundError,
    MCPToolCallError,
    create_mcp_client,
)
from .connection_manager import (
    BackendConnectionManager,
    BackendConfig,
    BackendError,
    BackendTimeoutError,
    BackendUnavailableError,
)
from .notion_client import (
    NotionMCPClient,
    NotionClientError,
    NotionRateLimitError,
    NotionObjectNotFoundError,
    create_notion_client,
)

__all__ = [
    # Base client
    "BaseMCPClient",
    "GenericMCPClient",
    "ToolResult",
    "ToolSchema",
    "ServerInfo",
    "ToolCallStatus",
    "MCPCapability",
    "MCPClientError",
    "MCPInitializeError",
    "MCPToolNotFoundError",
    "MCPToolCallError",
    "create_mcp_client",
    # Connection manager
    "BackendConnectionManager",
    "BackendConfig",
    "BackendError",
    "BackendTimeoutError",
    "BackendUnavailableError",
    # Notion client
    "NotionMCPClient",
    "NotionClientError",
    "NotionRateLimitError",
    "NotionObjectNotFoundError",
    "create_notion_client",
]
```

---

## Acceptance Criteria

### Implementation Criteria

- [ ] `NotionMCPClient` extends `BaseMCPClient`
- [ ] `backend_id` property returns `"notion"`
- [ ] Implements `validate_tool_arguments()` for Notion tools
- [ ] Implements `transform_tool_result()` for Notion responses
- [ ] Notion ID normalization works (both formats accepted)

### Tool Support Criteria

- [ ] `search_pages` tool supported with query parameter
- [ ] `read_page` tool supported with page_id parameter
- [ ] `create_page` tool supported with parent and properties
- [ ] `update_page` tool supported
- [ ] `delete_page` tool supported
- [ ] `list_databases` tool supported
- [ ] `query_database` tool supported with filter/sorts

### Validation Criteria

- [ ] Missing required arguments raise `ValueError`
- [ ] Invalid page_id format raises `ValueError`
- [ ] Invalid database_id format raises `ValueError`
- [ ] page_size validated (1-100)
- [ ] Unknown tools pass through to backend

### Error Handling Criteria

- [ ] Rate limit errors (429) transformed to user-friendly message
- [ ] Not found errors (404) transformed appropriately
- [ ] Validation errors (400) include error details
- [ ] Errors logged at appropriate levels

### Test Criteria

- [ ] Test `backend_id` property
- [ ] Test argument validation for each tool
- [ ] Test Notion ID normalization (both formats)
- [ ] Test invalid ID rejection
- [ ] Test page_size validation
- [ ] Test error transformation for rate limits
- [ ] Test error transformation for not found
- [ ] Test convenience methods
- [ ] All tests pass with `pytest tests/backends/test_notion_client.py`

---

## Test Cases

Create `deeptrail-gateway/tests/backends/test_notion_client.py`:

```python
"""Tests for Notion MCP client (D3)."""

import pytest
from unittest.mock import AsyncMock, MagicMock

from app.backends.notion_client import (
    NotionMCPClient,
    NotionClientError,
    create_notion_client,
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
def notion_client(mock_connection_manager):
    """Create Notion client with mock connection manager."""
    return NotionMCPClient(mock_connection_manager)


class TestNotionMCPClient:
    """Tests for NotionMCPClient."""
    
    def test_backend_id(self, notion_client):
        """Test backend_id is 'notion'."""
        assert notion_client.backend_id == "notion"
    
    def test_repr(self, notion_client):
        """Test string representation."""
        assert "NotionMCPClient" in repr(notion_client)
        assert "notion" in repr(notion_client)


class TestArgumentValidation:
    """Tests for argument validation."""
    
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
    
    def test_read_page_requires_page_id(self, notion_client):
        """Test read_page requires page_id."""
        with pytest.raises(ValueError) as exc:
            notion_client.validate_tool_arguments("read_page", {})
        assert "page_id" in str(exc.value)
    
    def test_read_page_with_page_id(self, notion_client):
        """Test read_page normalizes page_id."""
        args = {"page_id": "12345678123412341234123456789abc"}
        result = notion_client.validate_tool_arguments("read_page", args)
        # Should be normalized to hyphenated format
        assert result["page_id"] == "12345678-1234-1234-1234-123456789abc"
    
    def test_create_page_requires_parent_and_properties(self, notion_client):
        """Test create_page requires parent and properties."""
        with pytest.raises(ValueError) as exc:
            notion_client.validate_tool_arguments("create_page", {})
        assert "parent" in str(exc.value) or "properties" in str(exc.value)
    
    def test_page_size_validation(self, notion_client):
        """Test page_size must be 1-100."""
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
    
    def test_unknown_tool_passthrough(self, notion_client):
        """Test unknown tools pass through."""
        args = {"foo": "bar"}
        result = notion_client.validate_tool_arguments("unknown_tool", args)
        assert result == args


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
    
    def test_invalid_id_length(self, notion_client):
        """Test invalid ID length rejected."""
        with pytest.raises(ValueError) as exc:
            notion_client._normalize_notion_id("tooshort")
        assert "Invalid Notion ID" in str(exc.value)
    
    def test_invalid_id_characters(self, notion_client):
        """Test invalid characters rejected."""
        with pytest.raises(ValueError) as exc:
            notion_client._normalize_notion_id("zzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzz")
        assert "not hex" in str(exc.value)
    
    def test_empty_id(self, notion_client):
        """Test empty ID rejected."""
        with pytest.raises(ValueError):
            notion_client._normalize_notion_id("")


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
        
        result = await notion_client.search_pages(
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
    async def test_read_page(self, notion_client, mock_connection_manager):
        """Test read_page convenience method."""
        mock_response = MagicMock()
        mock_response.is_success = True
        mock_response.result = {"content": [{"type": "text", "text": "page content"}]}
        mock_response.error = None
        mock_response.raw = {}
        mock_connection_manager.send_tools_call.return_value = mock_response
        
        result = await notion_client.read_page(
            page_id="12345678-1234-1234-1234-123456789abc",
            auth_token="Bearer xyz"
        )
        
        call_args = mock_connection_manager.send_tools_call.call_args
        assert call_args.kwargs["tool_name"] == "read_page"


class TestFactoryFunction:
    """Tests for factory function."""
    
    def test_create_notion_client(self, mock_connection_manager):
        """Test create_notion_client factory."""
        client = create_notion_client(mock_connection_manager)
        
        assert isinstance(client, NotionMCPClient)
        assert client.backend_id == "notion"
```

---

## Post-Conditions

After completing this task:

- [ ] `NotionMCPClient` is available in `app/backends/`
- [ ] Gateway can proxy MCP requests to Notion backend
- [ ] Notion tool arguments are validated before sending
- [ ] Notion errors are transformed to user-friendly messages
- [ ] D6 (Backend Router) can route to Notion client
- [ ] Demo 1 (Unified Connection) can include Notion tools
- [ ] All unit tests pass

---

## References

- **Design Doc Section**: 2.6 Step 8: Agent Executes Task
- **Upstream Tasks**:
  - [WS-D2: Base MCP Client](./WS-D2-base-mcp-client.md) - Provides base class
  - [WS-D1: Connection Manager](./WS-D1-backend-connection-manager.md) - HTTP transport
- **Parallel Tasks**:
  - [WS-D4: Slack MCP Client](./WS-D4-slack-mcp-client.md) - Similar implementation
  - [WS-D5: HubSpot MCP Client](./WS-D5-hubspot-mcp-client.md) - Similar implementation
- **Downstream Tasks**:
  - [WS-D6: Backend Router](./WS-D6-backend-router.md) - Routes to this client
  - [WS-F2: Demo 1 Unified Connection](./WS-F2-demo-unified-connection.md) - Uses Notion
- **External References**:
  - [Notion API Reference](https://developers.notion.com/reference)

---

## Notes

- Notion IDs can be in two formats (with/without hyphens) - normalize to hyphenated
- Rate limiting is common with Notion API - handle gracefully
- Page size is limited to 100 by Notion API
- For MVP, the client proxies to a Notion MCP server (not direct Notion API)
- Consider adding retry logic for transient errors in production
- The MCP server backend handles actual Notion API authentication
