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
    result = await client.search_pages(
        query="meeting notes",
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


class NotionValidationError(NotionClientError):
    """Notion validation error."""
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
    TOOL_SCHEMAS: dict[str, dict[str, list[str]]] = {
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
        arguments: dict[str, Any] = {"page_size": page_size}
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
        arguments: dict[str, Any] = {
            "parent": parent,
            "properties": properties,
        }
        if children:
            arguments["children"] = children
        
        return await self.call_tool("create_page", arguments, auth_token=auth_token)
    
    async def update_page(
        self,
        page_id: str,
        properties: dict[str, Any] | None = None,
        archived: bool | None = None,
        auth_token: str | None = None,
    ) -> ToolResult:
        """
        Update an existing page in Notion.
        
        Args:
            page_id: Notion page ID
            properties: Updated properties
            archived: Whether to archive the page
            auth_token: Authorization token
            
        Returns:
            ToolResult with updated page info
        """
        arguments: dict[str, Any] = {"page_id": page_id}
        if properties:
            arguments["properties"] = properties
        if archived is not None:
            arguments["archived"] = archived
        
        return await self.call_tool("update_page", arguments, auth_token=auth_token)
    
    async def delete_page(
        self,
        page_id: str,
        auth_token: str | None = None,
    ) -> ToolResult:
        """
        Delete (archive) a page in Notion.
        
        Args:
            page_id: Notion page ID
            auth_token: Authorization token
            
        Returns:
            ToolResult with deletion confirmation
        """
        return await self.call_tool(
            "delete_page",
            {"page_id": page_id},
            auth_token=auth_token,
        )
    
    async def list_databases(
        self,
        page_size: int = 10,
        auth_token: str | None = None,
    ) -> ToolResult:
        """
        List databases in the Notion workspace.
        
        Args:
            page_size: Number of results (1-100)
            auth_token: Authorization token
            
        Returns:
            ToolResult with database list
        """
        return await self.call_tool(
            "list_databases",
            {"page_size": page_size},
            auth_token=auth_token,
        )
    
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
        arguments: dict[str, Any] = {
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
