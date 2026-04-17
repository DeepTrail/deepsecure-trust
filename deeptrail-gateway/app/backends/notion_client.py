"""
Notion Client

Provides two client implementations for Notion:

1. NotionMCPClient - Uses BackendConnectionManager for MCP protocol (original)
2. NotionDirectClient - Makes direct REST API calls to Notion API (WS-G2)

The NotionDirectClient is the primary implementation for production use,
translating MCP tool calls into direct Notion REST API requests.

MVP Tools:
- search_pages: Search pages in workspace -> POST /v1/search
- read_page: Read page content by ID -> GET /v1/pages/{page_id}
- create_page: Create a new page -> POST /v1/pages
- update_page: Update existing page -> PATCH /v1/pages/{page_id}
- delete_page: Archive a page -> PATCH /v1/pages/{page_id} (archived=true)
- list_databases: List all databases -> POST /v1/search (database filter)
- query_database: Query a database -> POST /v1/databases/{database_id}/query

Usage:
    from app.backends.notion_client import NotionDirectClient

    client = NotionDirectClient()

    # Search for pages (auth_token from credential injection)
    result = await client.search_pages(
        query="meeting notes",
        auth_token="secret_xxx"
    )
"""

import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

import httpx

from .base_mcp_client import (
    BackendConnectionManager,
    BaseMCPClient,
    ToolCallStatus,
    ToolResult,
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
# Direct Notion API Client (WS-G2)
# =============================================================================


@dataclass
class NotionAPIConfig:
    """Configuration for Notion API client."""
    base_url: str = "https://api.notion.com/v1"
    api_version: str = "2022-06-28"
    timeout_seconds: float = 30.0
    retry_attempts: int = 3
    retry_backoff_factor: float = 0.5


class NotionDirectClient:
    """
    Direct Notion REST API client.

    Makes direct HTTP calls to Notion's REST API, translating tool calls
    into appropriate API requests. Uses configuration from NotionConfig (WS-G1).

    Attributes:
        base_url: Notion API base URL
        api_version: Notion API version (for Notion-Version header)
        timeout: Request timeout in seconds

    Usage:
        client = NotionDirectClient()
        result = await client.search_pages("test query", auth_token="secret_xxx")
    """

    def __init__(self, config: NotionAPIConfig | None = None) -> None:
        """
        Initialize Notion direct client.

        Args:
            config: Optional configuration. If not provided, loads from
                    GatewaySettings (WS-G1).
        """
        if config is not None:
            self._config = config
        else:
            # Load from gateway settings (WS-G1)
            try:
                from app.core.config import get_settings
                settings = get_settings()
                self._config = NotionAPIConfig(
                    base_url=settings.notion.base_url,
                    api_version=settings.notion.api_version,
                    timeout_seconds=settings.notion.timeout_seconds,
                    retry_attempts=settings.notion.retry_attempts,
                    retry_backoff_factor=settings.notion.retry_backoff_factor,
                )
            except ImportError:
                # Fallback to defaults if config module not available
                self._config = NotionAPIConfig()

        self.base_url = self._config.base_url
        self.api_version = self._config.api_version
        self.timeout = self._config.timeout_seconds

        logger.info(
            "NotionDirectClient initialized: base_url=%s, api_version=%s",
            self.base_url,
            self.api_version,
        )

    # ─────────────────────────────────────────────────────────────────────────
    # HTTP Helpers
    # ─────────────────────────────────────────────────────────────────────────

    def _get_headers(self, auth_token: str) -> dict[str, str]:
        """
        Get headers for Notion API requests.

        Args:
            auth_token: Notion integration token (secret_xxx)

        Returns:
            Headers dict including Authorization and Notion-Version
        """
        return {
            "Authorization": f"Bearer {auth_token}",
            "Notion-Version": self.api_version,
            "Content-Type": "application/json",
        }

    def _transform_response(
        self,
        tool_name: str,
        response: httpx.Response,
        start_time: datetime,
    ) -> ToolResult:
        """
        Transform httpx response into ToolResult.

        Args:
            tool_name: Name of the tool that was called
            response: httpx Response object
            start_time: Request start time for duration calculation

        Returns:
            ToolResult with success or error status
        """
        duration_ms = (datetime.now(timezone.utc) - start_time).total_seconds() * 1000

        # Handle error responses
        if response.status_code >= 400:
            try:
                error_data = response.json()
                message = error_data.get("message", "Unknown error")
                code = error_data.get("code", "unknown")
            except Exception:
                message = response.text[:500] if response.text else "Unknown error"
                code = "unknown"

            # Map HTTP status codes to error types
            error_message = f"{code}: {message}"

            if response.status_code == 401:
                error_message = f"Unauthorized: {message}"
            elif response.status_code == 403:
                error_message = f"Forbidden: {message}"
            elif response.status_code == 404:
                error_message = f"Not found: {message}"
            elif response.status_code == 429:
                error_message = f"Rate limit exceeded: {message}"
            elif response.status_code == 400:
                error_message = f"Validation error: {message}"

            logger.warning(
                "Notion API error for %s: %s (HTTP %d)",
                tool_name,
                error_message,
                response.status_code,
            )

            return ToolResult(
                status=ToolCallStatus.ERROR,
                is_error=True,
                error_message=error_message,
                content=[{"type": "text", "text": error_message}],
                raw={"status_code": response.status_code, "error": message},
                duration_ms=duration_ms,
            )

        # Success response
        try:
            data = response.json()
        except Exception:
            data = {"raw_text": response.text}

        logger.debug(
            "Notion API success for %s in %.1fms",
            tool_name,
            duration_ms,
        )

        return ToolResult(
            status=ToolCallStatus.SUCCESS,
            is_error=False,
            content=[{"type": "text", "text": str(data)}],
            raw=data,
            duration_ms=duration_ms,
        )

    def _normalize_notion_id(self, notion_id: str) -> str:
        """
        Normalize Notion ID to hyphenated UUID format.

        Notion accepts both:
        - 12345678-1234-1234-1234-123456789abc
        - 123456781234123412341234567890abc

        Args:
            notion_id: Notion object ID

        Returns:
            Normalized ID with hyphens

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
    # Tool Methods
    # ─────────────────────────────────────────────────────────────────────────

    async def search_pages(
        self,
        query: str | None = None,
        page_size: int = 10,
        start_cursor: str | None = None,
        auth_token: str | None = None,
    ) -> ToolResult:
        """
        Search for pages in the Notion workspace.

        Calls POST /v1/search with filter for pages.

        Args:
            query: Search query string (optional)
            page_size: Number of results (1-100)
            start_cursor: Cursor for pagination
            auth_token: Notion integration token

        Returns:
            ToolResult with search results or error
        """
        if auth_token is None:
            return ToolResult.from_error(
                ToolCallStatus.UNAUTHORIZED, "No auth token provided"
            )

        url = f"{self.base_url}/search"
        payload: dict[str, Any] = {
            "page_size": min(max(page_size, 1), 100),
            "filter": {"property": "object", "value": "page"},
        }
        if query:
            payload["query"] = query
        if start_cursor:
            payload["start_cursor"] = start_cursor

        start_time = datetime.now(timezone.utc)

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(
                    url,
                    json=payload,
                    headers=self._get_headers(auth_token),
                )
            return self._transform_response("search_pages", response, start_time)

        except httpx.TimeoutException:
            return ToolResult.from_error(
                ToolCallStatus.TIMEOUT, "Request timed out"
            )
        except httpx.RequestError as e:
            return ToolResult.from_error(
                ToolCallStatus.ERROR, f"Request failed: {e}"
            )

    async def read_page(
        self,
        page_id: str,
        auth_token: str | None = None,
    ) -> ToolResult:
        """
        Read a page's content.

        Calls GET /v1/pages/{page_id}

        Args:
            page_id: Notion page ID (with or without hyphens)
            auth_token: Notion integration token

        Returns:
            ToolResult with page data or error
        """
        if auth_token is None:
            return ToolResult.from_error(
                ToolCallStatus.UNAUTHORIZED, "No auth token provided"
            )

        try:
            normalized_id = self._normalize_notion_id(page_id)
        except ValueError as e:
            return ToolResult.from_error(ToolCallStatus.ERROR, str(e))

        url = f"{self.base_url}/pages/{normalized_id}"
        start_time = datetime.now(timezone.utc)

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.get(
                    url,
                    headers=self._get_headers(auth_token),
                )
            return self._transform_response("read_page", response, start_time)

        except httpx.TimeoutException:
            return ToolResult.from_error(
                ToolCallStatus.TIMEOUT, "Request timed out"
            )
        except httpx.RequestError as e:
            return ToolResult.from_error(
                ToolCallStatus.ERROR, f"Request failed: {e}"
            )

    async def get_page_content(
        self,
        page_id: str,
        page_size: int = 100,
        auth_token: str | None = None,
    ) -> ToolResult:
        """
        Get a page's content blocks (paragraphs, headings, lists, etc.).

        Calls GET /v1/blocks/{page_id}/children

        Args:
            page_id: Notion page ID (with or without hyphens)
            page_size: Max blocks to return (1-100)
            auth_token: Notion integration token

        Returns:
            ToolResult with block children data or error
        """
        if auth_token is None:
            return ToolResult.from_error(
                ToolCallStatus.UNAUTHORIZED, "No auth token provided"
            )

        try:
            normalized_id = self._normalize_notion_id(page_id)
        except ValueError as e:
            return ToolResult.from_error(ToolCallStatus.ERROR, str(e))

        url = f"{self.base_url}/blocks/{normalized_id}/children"
        params = {"page_size": min(max(page_size, 1), 100)}
        start_time = datetime.now(timezone.utc)

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.get(
                    url,
                    params=params,
                    headers=self._get_headers(auth_token),
                )
            return self._transform_response("get_page_content", response, start_time)

        except httpx.TimeoutException:
            return ToolResult.from_error(
                ToolCallStatus.TIMEOUT, "Request timed out"
            )
        except httpx.RequestError as e:
            return ToolResult.from_error(
                ToolCallStatus.ERROR, f"Request failed: {e}"
            )

    async def create_page(
        self,
        parent_id: str,
        title: str,
        parent_type: str = "page_id",
        properties: dict[str, Any] | None = None,
        children: list[dict[str, Any]] | None = None,
        auth_token: str | None = None,
    ) -> ToolResult:
        """
        Create a new page in Notion.

        Calls POST /v1/pages

        Args:
            parent_id: Parent page or database ID
            title: Page title
            parent_type: Type of parent ("page_id" or "database_id")
            properties: Additional page properties
            children: Child blocks to add
            auth_token: Notion integration token

        Returns:
            ToolResult with created page data or error
        """
        if auth_token is None:
            return ToolResult.from_error(
                ToolCallStatus.UNAUTHORIZED, "No auth token provided"
            )

        try:
            normalized_parent = self._normalize_notion_id(parent_id)
        except ValueError as e:
            return ToolResult.from_error(ToolCallStatus.ERROR, str(e))

        url = f"{self.base_url}/pages"

        # Build payload
        if parent_type == "database_id":
            payload: dict[str, Any] = {
                "parent": {"database_id": normalized_parent},
                "properties": {"Name": {"title": [{"text": {"content": title}}]}},
            }
        else:
            payload = {
                "parent": {"page_id": normalized_parent},
                "properties": {"title": [{"text": {"content": title}}]},
            }

        # Merge additional properties
        if properties:
            if "properties" in payload:
                payload["properties"].update(properties)
            else:
                payload["properties"] = properties

        if children:
            payload["children"] = children

        start_time = datetime.now(timezone.utc)

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(
                    url,
                    json=payload,
                    headers=self._get_headers(auth_token),
                )
            return self._transform_response("create_page", response, start_time)

        except httpx.TimeoutException:
            return ToolResult.from_error(
                ToolCallStatus.TIMEOUT, "Request timed out"
            )
        except httpx.RequestError as e:
            return ToolResult.from_error(
                ToolCallStatus.ERROR, f"Request failed: {e}"
            )

    async def update_page(
        self,
        page_id: str,
        properties: dict[str, Any] | None = None,
        archived: bool | None = None,
        icon: dict[str, Any] | None = None,
        cover: dict[str, Any] | None = None,
        auth_token: str | None = None,
    ) -> ToolResult:
        """
        Update an existing page in Notion.

        Calls PATCH /v1/pages/{page_id}

        Args:
            page_id: Notion page ID
            properties: Updated properties
            archived: Whether to archive the page
            icon: Page icon
            cover: Page cover
            auth_token: Notion integration token

        Returns:
            ToolResult with updated page data or error
        """
        if auth_token is None:
            return ToolResult.from_error(
                ToolCallStatus.UNAUTHORIZED, "No auth token provided"
            )

        try:
            normalized_id = self._normalize_notion_id(page_id)
        except ValueError as e:
            return ToolResult.from_error(ToolCallStatus.ERROR, str(e))

        url = f"{self.base_url}/pages/{normalized_id}"
        payload: dict[str, Any] = {}

        if properties is not None:
            payload["properties"] = properties
        if archived is not None:
            payload["archived"] = archived
        if icon is not None:
            payload["icon"] = icon
        if cover is not None:
            payload["cover"] = cover

        if not payload:
            return ToolResult.from_error(
                ToolCallStatus.ERROR, "No updates specified"
            )

        start_time = datetime.now(timezone.utc)

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.patch(
                    url,
                    json=payload,
                    headers=self._get_headers(auth_token),
                )
            return self._transform_response("update_page", response, start_time)

        except httpx.TimeoutException:
            return ToolResult.from_error(
                ToolCallStatus.TIMEOUT, "Request timed out"
            )
        except httpx.RequestError as e:
            return ToolResult.from_error(
                ToolCallStatus.ERROR, f"Request failed: {e}"
            )

    async def delete_page(
        self,
        page_id: str,
        auth_token: str | None = None,
    ) -> ToolResult:
        """
        Delete (archive) a page in Notion.

        Calls PATCH /v1/pages/{page_id} with {"archived": true}

        Args:
            page_id: Notion page ID
            auth_token: Notion integration token

        Returns:
            ToolResult with archived page data or error
        """
        if auth_token is None:
            return ToolResult.from_error(
                ToolCallStatus.UNAUTHORIZED, "No auth token provided"
            )

        try:
            normalized_id = self._normalize_notion_id(page_id)
        except ValueError as e:
            return ToolResult.from_error(ToolCallStatus.ERROR, str(e))

        url = f"{self.base_url}/pages/{normalized_id}"
        payload = {"archived": True}

        start_time = datetime.now(timezone.utc)

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.patch(
                    url,
                    json=payload,
                    headers=self._get_headers(auth_token),
                )
            return self._transform_response("delete_page", response, start_time)

        except httpx.TimeoutException:
            return ToolResult.from_error(
                ToolCallStatus.TIMEOUT, "Request timed out"
            )
        except httpx.RequestError as e:
            return ToolResult.from_error(
                ToolCallStatus.ERROR, f"Request failed: {e}"
            )

    async def list_databases(
        self,
        page_size: int = 10,
        start_cursor: str | None = None,
        auth_token: str | None = None,
    ) -> ToolResult:
        """
        List databases in the Notion workspace.

        Calls POST /v1/search with filter for databases.

        Args:
            page_size: Number of results (1-100)
            start_cursor: Cursor for pagination
            auth_token: Notion integration token

        Returns:
            ToolResult with database list or error
        """
        if auth_token is None:
            return ToolResult.from_error(
                ToolCallStatus.UNAUTHORIZED, "No auth token provided"
            )

        url = f"{self.base_url}/search"
        payload: dict[str, Any] = {
            "page_size": min(max(page_size, 1), 100),
            "filter": {"property": "object", "value": "database"},
        }
        if start_cursor:
            payload["start_cursor"] = start_cursor

        start_time = datetime.now(timezone.utc)

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(
                    url,
                    json=payload,
                    headers=self._get_headers(auth_token),
                )
            return self._transform_response("list_databases", response, start_time)

        except httpx.TimeoutException:
            return ToolResult.from_error(
                ToolCallStatus.TIMEOUT, "Request timed out"
            )
        except httpx.RequestError as e:
            return ToolResult.from_error(
                ToolCallStatus.ERROR, f"Request failed: {e}"
            )

    async def query_database(
        self,
        database_id: str,
        filter: dict[str, Any] | None = None,
        sorts: list[dict[str, Any]] | None = None,
        page_size: int = 100,
        start_cursor: str | None = None,
        auth_token: str | None = None,
    ) -> ToolResult:
        """
        Query a Notion database.

        Calls POST /v1/databases/{database_id}/query

        Args:
            database_id: Notion database ID
            filter: Filter conditions
            sorts: Sort configuration
            page_size: Number of results (1-100)
            start_cursor: Cursor for pagination
            auth_token: Notion integration token

        Returns:
            ToolResult with query results or error
        """
        if auth_token is None:
            return ToolResult.from_error(
                ToolCallStatus.UNAUTHORIZED, "No auth token provided"
            )

        try:
            normalized_id = self._normalize_notion_id(database_id)
        except ValueError as e:
            return ToolResult.from_error(ToolCallStatus.ERROR, str(e))

        url = f"{self.base_url}/databases/{normalized_id}/query"
        payload: dict[str, Any] = {
            "page_size": min(max(page_size, 1), 100),
        }
        if filter:
            payload["filter"] = filter
        if sorts:
            payload["sorts"] = sorts
        if start_cursor:
            payload["start_cursor"] = start_cursor

        start_time = datetime.now(timezone.utc)

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(
                    url,
                    json=payload,
                    headers=self._get_headers(auth_token),
                )
            return self._transform_response("query_database", response, start_time)

        except httpx.TimeoutException:
            return ToolResult.from_error(
                ToolCallStatus.TIMEOUT, "Request timed out"
            )
        except httpx.RequestError as e:
            return ToolResult.from_error(
                ToolCallStatus.ERROR, f"Request failed: {e}"
            )

    async def call_tool(
        self,
        tool_name: str,
        arguments: dict[str, Any],
        auth_token: str | None = None,
    ) -> ToolResult:
        """
        Dispatch a tool call to the appropriate method.

        Args:
            tool_name: Name of the tool to call
            arguments: Tool arguments
            auth_token: Notion integration token

        Returns:
            ToolResult from the tool execution
        """
        # Map tool names to methods
        tool_map = {
            "search_pages": self._call_search_pages,
            "read_page": self._call_read_page,
            "get_page_content": self._call_get_page_content,
            "create_page": self._call_create_page,
            "update_page": self._call_update_page,
            "delete_page": self._call_delete_page,
            "list_databases": self._call_list_databases,
            "query_database": self._call_query_database,
        }

        handler = tool_map.get(tool_name)
        if handler is None:
            return ToolResult.from_error(
                ToolCallStatus.ERROR, f"Unknown tool: {tool_name}"
            )

        return await handler(arguments, auth_token)

    async def _call_search_pages(
        self, args: dict[str, Any], auth_token: str | None
    ) -> ToolResult:
        page_size = args.get("page_size") or args.get("limit", 10)
        return await self.search_pages(
            query=args.get("query"),
            page_size=page_size,
            start_cursor=args.get("start_cursor"),
            auth_token=auth_token,
        )

    async def _call_read_page(
        self, args: dict[str, Any], auth_token: str | None
    ) -> ToolResult:
        page_id = args.get("page_id")
        if not page_id:
            return ToolResult.from_error(
                ToolCallStatus.ERROR, "page_id is required"
            )
        return await self.read_page(page_id=page_id, auth_token=auth_token)

    async def _call_get_page_content(
        self, args: dict[str, Any], auth_token: str | None
    ) -> ToolResult:
        page_id = args.get("page_id")
        if not page_id:
            return ToolResult.from_error(
                ToolCallStatus.ERROR, "page_id is required"
            )
        return await self.get_page_content(
            page_id=page_id,
            page_size=args.get("page_size", 100),
            auth_token=auth_token,
        )

    async def _call_create_page(
        self, args: dict[str, Any], auth_token: str | None
    ) -> ToolResult:
        # Support both simple (parent_id, title) and full (parent, properties) formats
        parent = args.get("parent")
        if parent:
            # Full format: {"parent": {"page_id": "xxx"}, "properties": {...}}
            if "page_id" in parent:
                parent_id = parent["page_id"]
                parent_type = "page_id"
            elif "database_id" in parent:
                parent_id = parent["database_id"]
                parent_type = "database_id"
            else:
                return ToolResult.from_error(
                    ToolCallStatus.ERROR, "parent must contain page_id or database_id"
                )
            properties = args.get("properties", {})
            # Extract title from properties
            title = ""
            if "title" in properties:
                title_prop = properties.get("title", [])
                if title_prop and len(title_prop) > 0:
                    title = title_prop[0].get("text", {}).get("content", "")
            elif "Name" in properties:
                name_prop = properties.get("Name", {}).get("title", [])
                if name_prop and len(name_prop) > 0:
                    title = name_prop[0].get("text", {}).get("content", "")
        else:
            # Simple format
            parent_id = args.get("parent_id")
            if not parent_id:
                return ToolResult.from_error(
                    ToolCallStatus.ERROR, "parent or parent_id is required"
                )
            parent_type = args.get("parent_type", "page_id")
            title = args.get("title", "")
            properties = args.get("properties")

        return await self.create_page(
            parent_id=parent_id,
            title=title,
            parent_type=parent_type,
            properties=properties,
            children=args.get("children"),
            auth_token=auth_token,
        )

    async def _call_update_page(
        self, args: dict[str, Any], auth_token: str | None
    ) -> ToolResult:
        page_id = args.get("page_id")
        if not page_id:
            return ToolResult.from_error(
                ToolCallStatus.ERROR, "page_id is required"
            )
        return await self.update_page(
            page_id=page_id,
            properties=args.get("properties"),
            archived=args.get("archived"),
            icon=args.get("icon"),
            cover=args.get("cover"),
            auth_token=auth_token,
        )

    async def _call_delete_page(
        self, args: dict[str, Any], auth_token: str | None
    ) -> ToolResult:
        page_id = args.get("page_id")
        if not page_id:
            return ToolResult.from_error(
                ToolCallStatus.ERROR, "page_id is required"
            )
        return await self.delete_page(page_id=page_id, auth_token=auth_token)

    async def _call_list_databases(
        self, args: dict[str, Any], auth_token: str | None
    ) -> ToolResult:
        return await self.list_databases(
            page_size=args.get("page_size", 10),
            start_cursor=args.get("start_cursor"),
            auth_token=auth_token,
        )

    async def _call_query_database(
        self, args: dict[str, Any], auth_token: str | None
    ) -> ToolResult:
        database_id = args.get("database_id")
        if not database_id:
            return ToolResult.from_error(
                ToolCallStatus.ERROR, "database_id is required"
            )
        return await self.query_database(
            database_id=database_id,
            filter=args.get("filter"),
            sorts=args.get("sorts"),
            page_size=args.get("page_size", 100),
            start_cursor=args.get("start_cursor"),
            auth_token=auth_token,
        )


# =============================================================================
# MCP Protocol Client (Original - for backwards compatibility)
# =============================================================================


class NotionMCPClient(BaseMCPClient):
    """
    MCP client for Notion backend.

    Provides Notion-specific:
    - Argument validation for Notion tools
    - Result transformation for Notion responses
    - Error handling for Notion API errors

    Note: This client uses BackendConnectionManager for MCP protocol.
    For direct REST API calls, use NotionDirectClient instead.

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
# Factory Functions
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


def create_notion_direct_client(
    config: NotionAPIConfig | None = None,
) -> NotionDirectClient:
    """
    Create a Notion direct API client.

    Args:
        config: Optional configuration (loads from GatewaySettings if not provided)

    Returns:
        Configured NotionDirectClient
    """
    return NotionDirectClient(config)
