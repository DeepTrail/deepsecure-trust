"""Gmail backend client for the DeepTrail MCP Gateway.

Translates MCP ``tools/call`` requests into Gmail v1 REST API calls and returns
MCP-formatted ``ToolResult`` objects.

Auth tokens are injected per-call by the Gateway from the user's vault-stored
OAuth access token; the client itself never stores credentials and never logs
message content or token values.

All Gmail API paths use the ``/users/me/`` prefix because the API always
operates on the authenticated user's mailbox.

MVP Tools:

- ``list_messages``: List message IDs → ``GET /users/me/messages``
- ``read_message``: Get full message → ``GET /users/me/messages/{id}?format={fmt}``
- ``search_messages``: Search by Gmail query syntax → ``GET /users/me/messages?q={query}``
- ``list_labels``: List labels → ``GET /users/me/labels``

Usage::

    from app.backends.gmail_client import GmailDirectClient

    client = GmailDirectClient()
    result = await client.search_messages(
        query="from:alice subject:meeting newer_than:7d",
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
class GmailAPIConfig:
    """Configuration for the Gmail direct API client."""

    base_url: str = "https://gmail.googleapis.com/gmail/v1"
    timeout_seconds: float = 30.0
    retry_attempts: int = 3
    retry_backoff_factor: float = 0.5


# Allowed values for the ``format`` parameter of GET messages/{id}.
# Per https://developers.google.com/gmail/api/reference/rest/v1/users.messages/get
_VALID_MESSAGE_FORMATS = frozenset({"full", "metadata", "minimal", "raw"})


# =============================================================================
# Direct Gmail API Client
# =============================================================================


class GmailDirectClient:
    """Direct Gmail v1 REST API client.

    Makes authenticated HTTPS calls to the Gmail API and translates responses
    into MCP ``ToolResult`` objects. Configuration defaults to
    ``GatewaySettings.gmail`` (loaded via :func:`app.core.config.get_settings`)
    when no explicit ``GmailAPIConfig`` is supplied.
    """

    def __init__(self, config: GmailAPIConfig | None = None) -> None:
        if config is not None:
            self._config = config
        else:
            try:
                from app.core.config import get_settings

                settings = get_settings()
                self._config = GmailAPIConfig(
                    base_url=settings.gmail.base_url,
                    timeout_seconds=settings.gmail.timeout_seconds,
                    retry_attempts=settings.gmail.retry_attempts,
                    retry_backoff_factor=settings.gmail.retry_backoff_factor,
                )
            except (ImportError, AttributeError):
                self._config = GmailAPIConfig()

        self.base_url = self._config.base_url
        self.timeout = self._config.timeout_seconds

        logger.info(
            "GmailDirectClient initialized: base_url=%s, timeout=%.1fs",
            self.base_url,
            self.timeout,
        )

    # ─────────────────────────────────────────────────────────────────────────
    # HTTP Helpers
    # ─────────────────────────────────────────────────────────────────────────

    def _get_headers(self, auth_token: str) -> dict[str, str]:
        """Build authenticated headers for the Gmail API.

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

        Gmail (like other Google APIs) returns errors as
        ``{"error": {"code": ..., "message": ...}}``.
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
                    f"Gmail API error ({response.status_code}): {message}"
                )

            # Never log message content; just status + tool name.
            logger.warning(
                "Gmail API error for %s: HTTP %d",
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

        # Never log message bodies; only tool name + duration.
        logger.debug(
            "Gmail API success for %s in %.1fms",
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

    # ─────────────────────────────────────────────────────────────────────────
    # Tool Methods
    # ─────────────────────────────────────────────────────────────────────────

    async def list_messages(
        self,
        auth_token: str | None = None,
        max_results: int = 10,
        label_ids: list[str] | None = None,
    ) -> ToolResult:
        """List messages in the user's mailbox.

        Calls ``GET /users/me/messages``. Returns only
        ``{id, threadId}`` per message — full content requires
        :meth:`read_message`.

        ``label_ids`` is forwarded as repeated ``labelIds`` query params, e.g.
        ``?labelIds=INBOX&labelIds=UNREAD``.
        """
        if auth_token is None:
            return ToolResult.from_error(
                ToolCallStatus.UNAUTHORIZED, "No auth token provided"
            )

        url = f"{self.base_url}/users/me/messages"
        # httpx serialises a list value into repeated params, which matches
        # Gmail's API expectation for `labelIds`.
        params: dict[str, Any] = {
            "maxResults": min(max(int(max_results), 1), 500),
        }
        if label_ids:
            params["labelIds"] = list(label_ids)

        start_time = datetime.now(timezone.utc)

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.get(
                    url,
                    params=params,
                    headers=self._get_headers(auth_token),
                )
            return self._transform_response("list_messages", response, start_time)

        except httpx.TimeoutException:
            return ToolResult.from_error(
                ToolCallStatus.TIMEOUT, "Request timed out"
            )
        except httpx.RequestError as e:
            return ToolResult.from_error(
                ToolCallStatus.ERROR, f"Request failed: {e}"
            )

    async def read_message(
        self,
        message_id: str,
        auth_token: str | None = None,
        format: str = "full",
    ) -> ToolResult:
        """Get a single message by ID.

        Calls ``GET /users/me/messages/{id}?format={format}``.

        ``format`` must be one of: ``full`` (default), ``metadata``,
        ``minimal``, or ``raw``. Invalid values fall back to ``full``
        rather than calling Gmail with garbage.
        """
        if auth_token is None:
            return ToolResult.from_error(
                ToolCallStatus.UNAUTHORIZED, "No auth token provided"
            )

        if not message_id:
            return ToolResult.from_error(
                ToolCallStatus.ERROR, "message_id is required"
            )

        if format not in _VALID_MESSAGE_FORMATS:
            format = "full"

        url = f"{self.base_url}/users/me/messages/{message_id}"
        params = {"format": format}

        start_time = datetime.now(timezone.utc)

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.get(
                    url,
                    params=params,
                    headers=self._get_headers(auth_token),
                )
            return self._transform_response("read_message", response, start_time)

        except httpx.TimeoutException:
            return ToolResult.from_error(
                ToolCallStatus.TIMEOUT, "Request timed out"
            )
        except httpx.RequestError as e:
            return ToolResult.from_error(
                ToolCallStatus.ERROR, f"Request failed: {e}"
            )

    async def search_messages(
        self,
        query: str,
        auth_token: str | None = None,
        max_results: int = 10,
    ) -> ToolResult:
        """Search messages using Gmail's ``q`` query syntax.

        Calls ``GET /users/me/messages?q={query}&maxResults={n}``.
        See https://support.google.com/mail/answer/7190 for the full query
        syntax (e.g., ``from:alice subject:meeting newer_than:7d``).
        """
        if auth_token is None:
            return ToolResult.from_error(
                ToolCallStatus.UNAUTHORIZED, "No auth token provided"
            )

        url = f"{self.base_url}/users/me/messages"
        params: dict[str, Any] = {
            "q": query,
            "maxResults": min(max(int(max_results), 1), 500),
        }

        start_time = datetime.now(timezone.utc)

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.get(
                    url,
                    params=params,
                    headers=self._get_headers(auth_token),
                )
            return self._transform_response(
                "search_messages", response, start_time
            )

        except httpx.TimeoutException:
            return ToolResult.from_error(
                ToolCallStatus.TIMEOUT, "Request timed out"
            )
        except httpx.RequestError as e:
            return ToolResult.from_error(
                ToolCallStatus.ERROR, f"Request failed: {e}"
            )

    async def list_labels(
        self,
        auth_token: str | None = None,
    ) -> ToolResult:
        """List all labels in the user's mailbox.

        Calls ``GET /users/me/labels``.
        """
        if auth_token is None:
            return ToolResult.from_error(
                ToolCallStatus.UNAUTHORIZED, "No auth token provided"
            )

        url = f"{self.base_url}/users/me/labels"

        start_time = datetime.now(timezone.utc)

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.get(
                    url,
                    headers=self._get_headers(auth_token),
                )
            return self._transform_response("list_labels", response, start_time)

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
            "list_messages": self._call_list_messages,
            "read_message": self._call_read_message,
            "search_messages": self._call_search_messages,
            "list_labels": self._call_list_labels,
        }

        handler = tool_map.get(tool_name)
        if handler is None:
            return ToolResult.from_error(
                ToolCallStatus.ERROR, f"Unknown tool: {tool_name}"
            )

        return await handler(arguments, auth_token)

    async def _call_list_messages(
        self, args: dict[str, Any], auth_token: str | None
    ) -> ToolResult:
        max_results = (
            args.get("max_results")
            or args.get("maxResults")
            or 10
        )
        # Tolerate both snake_case (`label_ids`) and Gmail-native (`labelIds`).
        label_ids = args.get("label_ids") or args.get("labelIds")
        if label_ids is not None and not isinstance(label_ids, list):
            label_ids = [label_ids]
        return await self.list_messages(
            auth_token=auth_token,
            max_results=int(max_results),
            label_ids=label_ids,
        )

    async def _call_read_message(
        self, args: dict[str, Any], auth_token: str | None
    ) -> ToolResult:
        message_id = args.get("message_id") or args.get("messageId") or args.get("id")
        if not message_id:
            return ToolResult.from_error(
                ToolCallStatus.ERROR, "message_id is required"
            )
        return await self.read_message(
            message_id=message_id,
            auth_token=auth_token,
            format=args.get("format", "full"),
        )

    async def _call_search_messages(
        self, args: dict[str, Any], auth_token: str | None
    ) -> ToolResult:
        query = args.get("query") or args.get("q")
        if not query:
            return ToolResult.from_error(
                ToolCallStatus.ERROR, "query is required"
            )
        max_results = (
            args.get("max_results")
            or args.get("maxResults")
            or 10
        )
        return await self.search_messages(
            query=query,
            auth_token=auth_token,
            max_results=int(max_results),
        )

    async def _call_list_labels(
        self, args: dict[str, Any], auth_token: str | None
    ) -> ToolResult:
        return await self.list_labels(auth_token=auth_token)


# =============================================================================
# Factory
# =============================================================================


def create_gmail_direct_client(
    config: GmailAPIConfig | None = None,
) -> GmailDirectClient:
    """Create a Gmail direct API client.

    Args:
        config: Optional configuration. Loads from :class:`GatewaySettings`
            (``settings.gmail``) when not provided.

    Returns:
        Configured :class:`GmailDirectClient`.
    """
    return GmailDirectClient(config)
