"""Google Drive backend client for the DeepTrail MCP Gateway.

Translates MCP `tools/call` requests into Google Drive v3 REST API calls and
returns MCP-formatted ``ToolResult`` objects.

Auth tokens are injected per-call by the Gateway from the user's vault-stored
OAuth access token; the client itself never stores credentials.

MVP Tools:

- ``search_files``: Search files by query → ``GET /files?q={query}``
- ``read_file``: Get file metadata by ID → ``GET /files/{fileId}``
- ``list_files``: List files in Drive → ``GET /files?pageSize={n}&orderBy={ord}``
- ``get_file_metadata``: Full metadata → ``GET /files/{fileId}?fields=*``

Usage::

    from app.backends.gdrive_client import GDriveDirectClient

    client = GDriveDirectClient()
    result = await client.search_files(
        query="name contains 'budget'",
        auth_token="ya29.xxxx",
    )
"""

import json
import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

import httpx

from .base_mcp_client import ToolCallStatus, ToolResult

logger = logging.getLogger(__name__)


# =============================================================================
# Configuration
# =============================================================================


@dataclass
class GDriveAPIConfig:
    """Configuration for the Google Drive direct API client."""

    base_url: str = "https://www.googleapis.com/drive/v3"
    timeout_seconds: float = 30.0
    retry_attempts: int = 3
    retry_backoff_factor: float = 0.5


# =============================================================================
# Direct Google Drive API Client
# =============================================================================


class GDriveDirectClient:
    """Direct Google Drive v3 REST API client.

    Makes authenticated HTTPS calls to the Google Drive API and translates
    responses into MCP ``ToolResult`` objects. Configuration defaults to
    ``GatewaySettings.gdrive`` (loaded via :func:`app.core.config.get_settings`)
    when no explicit ``GDriveAPIConfig`` is supplied.
    """

    def __init__(self, config: GDriveAPIConfig | None = None) -> None:
        if config is not None:
            self._config = config
        else:
            try:
                from app.core.config import get_settings

                settings = get_settings()
                self._config = GDriveAPIConfig(
                    base_url=settings.gdrive.base_url,
                    timeout_seconds=settings.gdrive.timeout_seconds,
                    retry_attempts=settings.gdrive.retry_attempts,
                    retry_backoff_factor=settings.gdrive.retry_backoff_factor,
                )
            except (ImportError, AttributeError):
                self._config = GDriveAPIConfig()

        self.base_url = self._config.base_url
        self.timeout = self._config.timeout_seconds

        logger.info(
            "GDriveDirectClient initialized: base_url=%s, timeout=%.1fs",
            self.base_url,
            self.timeout,
        )

    # ─────────────────────────────────────────────────────────────────────────
    # HTTP Helpers
    # ─────────────────────────────────────────────────────────────────────────

    def _get_headers(self, auth_token: str) -> dict[str, str]:
        """Build authenticated headers for the Google Drive API.

        Note: never log the token value.
        """
        return {
            "Authorization": f"Bearer {auth_token}",
            "Accept": "application/json",
        }

    def _transform_response(
        self,
        tool_name: str,
        response: httpx.Response,
        start_time: datetime,
    ) -> ToolResult:
        """Convert an ``httpx.Response`` into a :class:`ToolResult`.

        Google API errors use ``response["error"]["message"]`` (different from
        Notion which uses ``response["message"]``).
        """
        duration_ms = (
            datetime.now(timezone.utc) - start_time
        ).total_seconds() * 1000

        if response.status_code >= 400:
            try:
                error_data = response.json()
                message = (
                    error_data.get("error", {}).get("message", "Unknown error")
                )
            except Exception:
                message = (
                    response.text[:500] if response.text else "Unknown error"
                )

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
            else:
                error_message = (
                    f"Google Drive API error ({response.status_code}): {message}"
                )

            logger.warning(
                "Google Drive API error for %s: HTTP %d",
                tool_name,
                response.status_code,
            )

            return ToolResult(
                status=ToolCallStatus.ERROR,
                is_error=True,
                error_message=error_message,
                content=[{"type": "text", "text": error_message}],
                raw={
                    "status_code": response.status_code,
                    "error": message[:500],
                },
                duration_ms=duration_ms,
            )

        try:
            data = response.json()
        except Exception:
            data = {"raw_text": response.text}

        logger.debug(
            "Google Drive API success for %s in %.1fms",
            tool_name,
            duration_ms,
        )

        return ToolResult(
            status=ToolCallStatus.SUCCESS,
            is_error=False,
            content=[{"type": "text", "text": json.dumps(data)}],
            raw=data,
            duration_ms=duration_ms,
        )

    # Compact field mask for search_files / list_files so responses include
    # file names, types, and sizes without all verbose metadata.
    _FILE_LIST_FIELDS = (
        "files(id,name,mimeType,modifiedTime,size,webViewLink,owners/displayName)"
    )

    # ─────────────────────────────────────────────────────────────────────────
    # Tool Methods
    # ─────────────────────────────────────────────────────────────────────────

    async def search_files(
        self,
        query: str,
        auth_token: str | None = None,
        max_results: int = 10,
    ) -> ToolResult:
        """Search Drive files matching ``query``.

        Calls ``GET /files?q={query}&pageSize={max_results}``.
        See https://developers.google.com/drive/api/guides/search-files for
        Google Drive query syntax.
        """
        if auth_token is None:
            return ToolResult.from_error(
                ToolCallStatus.UNAUTHORIZED, "No auth token provided"
            )

        url = f"{self.base_url}/files"
        params: dict[str, Any] = {
            "q": query,
            "pageSize": min(max(int(max_results), 1), 1000),
            "orderBy": "modifiedTime desc",
            "fields": self._FILE_LIST_FIELDS,
        }

        start_time = datetime.now(timezone.utc)

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.get(
                    url,
                    params=params,
                    headers=self._get_headers(auth_token),
                )
            return self._transform_response("search_files", response, start_time)

        except httpx.TimeoutException:
            return ToolResult.from_error(
                ToolCallStatus.TIMEOUT, "Request timed out"
            )
        except httpx.RequestError as e:
            return ToolResult.from_error(
                ToolCallStatus.ERROR, f"Request failed: {e}"
            )

    async def read_file(
        self,
        file_id: str,
        auth_token: str | None = None,
    ) -> ToolResult:
        """Get a file's basic metadata by ID.

        Calls ``GET /files/{fileId}``.
        """
        if auth_token is None:
            return ToolResult.from_error(
                ToolCallStatus.UNAUTHORIZED, "No auth token provided"
            )

        if not file_id:
            return ToolResult.from_error(
                ToolCallStatus.ERROR, "file_id is required"
            )

        url = f"{self.base_url}/files/{file_id}"

        start_time = datetime.now(timezone.utc)

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.get(
                    url,
                    headers=self._get_headers(auth_token),
                )
            return self._transform_response("read_file", response, start_time)

        except httpx.TimeoutException:
            return ToolResult.from_error(
                ToolCallStatus.TIMEOUT, "Request timed out"
            )
        except httpx.RequestError as e:
            return ToolResult.from_error(
                ToolCallStatus.ERROR, f"Request failed: {e}"
            )

    async def list_files(
        self,
        auth_token: str | None = None,
        page_size: int = 20,
        order_by: str = "modifiedTime desc",
    ) -> ToolResult:
        """List files in the user's Drive.

        Calls ``GET /files?pageSize={page_size}&orderBy={order_by}``.
        """
        if auth_token is None:
            return ToolResult.from_error(
                ToolCallStatus.UNAUTHORIZED, "No auth token provided"
            )

        url = f"{self.base_url}/files"
        params: dict[str, Any] = {
            "pageSize": min(max(int(page_size), 1), 1000),
            "orderBy": order_by,
            "fields": self._FILE_LIST_FIELDS,
        }

        start_time = datetime.now(timezone.utc)

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.get(
                    url,
                    params=params,
                    headers=self._get_headers(auth_token),
                )
            return self._transform_response("list_files", response, start_time)

        except httpx.TimeoutException:
            return ToolResult.from_error(
                ToolCallStatus.TIMEOUT, "Request timed out"
            )
        except httpx.RequestError as e:
            return ToolResult.from_error(
                ToolCallStatus.ERROR, f"Request failed: {e}"
            )

    async def get_file_metadata(
        self,
        file_id: str,
        auth_token: str | None = None,
    ) -> ToolResult:
        """Fetch full metadata for a file.

        Calls ``GET /files/{fileId}?fields=*`` to request all available
        metadata fields rather than the default subset.
        """
        if auth_token is None:
            return ToolResult.from_error(
                ToolCallStatus.UNAUTHORIZED, "No auth token provided"
            )

        if not file_id:
            return ToolResult.from_error(
                ToolCallStatus.ERROR, "file_id is required"
            )

        url = f"{self.base_url}/files/{file_id}"
        params = {"fields": "*"}

        start_time = datetime.now(timezone.utc)

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.get(
                    url,
                    params=params,
                    headers=self._get_headers(auth_token),
                )
            return self._transform_response(
                "get_file_metadata", response, start_time
            )

        except httpx.TimeoutException:
            return ToolResult.from_error(
                ToolCallStatus.TIMEOUT, "Request timed out"
            )
        except httpx.RequestError as e:
            return ToolResult.from_error(
                ToolCallStatus.ERROR, f"Request failed: {e}"
            )

    # ─────────────────────────────────────────────────────────────────────────
    # Tool Dispatcher
    # ─────────────────────────────────────────────────────────────────────────

    async def call_tool(
        self,
        tool_name: str,
        arguments: dict[str, Any],
        auth_token: str | None = None,
    ) -> ToolResult:
        """Dispatch a tool call to the appropriate implementation method."""
        tool_map = {
            "search_files": self._call_search_files,
            "read_file": self._call_read_file,
            "list_files": self._call_list_files,
            "get_file_metadata": self._call_get_file_metadata,
        }

        handler = tool_map.get(tool_name)
        if handler is None:
            return ToolResult.from_error(
                ToolCallStatus.ERROR, f"Unknown tool: {tool_name}"
            )

        return await handler(arguments, auth_token)

    async def _call_search_files(
        self, args: dict[str, Any], auth_token: str | None
    ) -> ToolResult:
        query = args.get("query") or args.get("q") or ""
        max_results = (
            args.get("max_results")
            or args.get("limit")
            or args.get("page_size")
            or args.get("pageSize")
            or 10
        )

        # Google Drive q parameter requires its own query syntax
        # (e.g. "fullText contains 'budget'"). If the caller passed a plain
        # text string, wrap it automatically so the API doesn't reject it.
        _DRIVE_OPERATORS = ("contains", "=", "!=", "<", ">", "<=", ">=", " in ")
        if query and not any(op in query for op in _DRIVE_OPERATORS):
            escaped = query.replace("\\", "\\\\").replace("'", "\\'")
            query = f"fullText contains '{escaped}'"

        return await self.search_files(
            query=query,
            auth_token=auth_token,
            max_results=int(max_results),
        )

    async def _call_read_file(
        self, args: dict[str, Any], auth_token: str | None
    ) -> ToolResult:
        file_id = args.get("file_id") or args.get("fileId")
        if not file_id:
            return ToolResult.from_error(
                ToolCallStatus.ERROR, "file_id is required"
            )
        return await self.read_file(file_id=file_id, auth_token=auth_token)

    async def _call_list_files(
        self, args: dict[str, Any], auth_token: str | None
    ) -> ToolResult:
        page_size = (
            args.get("page_size")
            or args.get("pageSize")
            or args.get("max_results")
            or 20
        )
        order_by = (
            args.get("order_by") or args.get("orderBy") or "modifiedTime desc"
        )
        return await self.list_files(
            auth_token=auth_token,
            page_size=int(page_size),
            order_by=order_by,
        )

    async def _call_get_file_metadata(
        self, args: dict[str, Any], auth_token: str | None
    ) -> ToolResult:
        file_id = args.get("file_id") or args.get("fileId")
        if not file_id:
            return ToolResult.from_error(
                ToolCallStatus.ERROR, "file_id is required"
            )
        return await self.get_file_metadata(
            file_id=file_id, auth_token=auth_token
        )


# =============================================================================
# Factory
# =============================================================================


def create_gdrive_direct_client(
    config: GDriveAPIConfig | None = None,
) -> GDriveDirectClient:
    """Create a Google Drive direct API client.

    Args:
        config: Optional configuration. Loads from :class:`GatewaySettings`
            (``settings.gdrive``) when not provided.

    Returns:
        Configured :class:`GDriveDirectClient`.
    """
    return GDriveDirectClient(config)
