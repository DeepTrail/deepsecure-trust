"""
Slack Client

Provides two client implementations for Slack:

1. SlackMCPClient - Uses BackendConnectionManager for MCP protocol (original)
2. SlackDirectClient - Makes direct REST API calls to Slack API (WS-G3)

The SlackDirectClient is the primary implementation for production use,
translating MCP tool calls into direct Slack REST API requests.

MVP Tools:
- search_messages: Search messages in workspace -> GET /api/search.messages
- send_message: Send message to a channel -> POST /api/chat.postMessage
- list_channels: List accessible channels -> GET /api/conversations.list
- join_channel: Join a channel -> POST /api/conversations.join
- post_reaction: Add reaction to a message -> POST /api/reactions.add
- list_users: List workspace users -> GET /api/users.list
- search_users: Search users by name or email -> GET /api/users.list (client-side filter)
- get_channel_history: Get channel message history -> GET /api/conversations.history

Usage:
    from app.backends.slack_client import SlackDirectClient

    client = SlackDirectClient()

    # List channels (auth_token from credential injection)
    result = await client.list_channels(auth_token="xoxb-xxx")
"""

import logging
import re
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
# Slack-Specific Types
# =============================================================================


class SlackChannelType:
    """Slack channel types."""
    PUBLIC = "public_channel"
    PRIVATE = "private_channel"
    MPIM = "mpim"
    IM = "im"


# =============================================================================
# Exceptions
# =============================================================================


class SlackClientError(Exception):
    """Slack-specific client error."""
    pass


class SlackRateLimitError(SlackClientError):
    """Slack API rate limit exceeded."""
    pass


class SlackChannelNotFoundError(SlackClientError):
    """Slack channel not found."""
    pass


class SlackPermissionError(SlackClientError):
    """Insufficient permissions for Slack operation."""
    pass


# =============================================================================
# Direct Slack API Client (WS-G3)
# =============================================================================


@dataclass
class SlackAPIConfig:
    """Configuration for Slack API client."""
    base_url: str = "https://slack.com/api"
    timeout_seconds: float = 30.0
    retry_attempts: int = 3
    retry_backoff_factor: float = 0.5


class SlackDirectClient:
    """
    Direct Slack REST API client.

    Makes direct HTTP calls to Slack's REST API, translating tool calls
    into appropriate API requests. Uses configuration from SlackConfig (WS-G1).

    CRITICAL: Slack returns HTTP 200 even for errors! Must check the 'ok' field
    in the response body to determine success or failure.

    Attributes:
        base_url: Slack API base URL (https://slack.com/api)
        timeout: Request timeout in seconds

    Usage:
        client = SlackDirectClient()
        result = await client.list_channels(auth_token="xoxb-xxx")
    """

    def __init__(self, config: SlackAPIConfig | None = None) -> None:
        """
        Initialize Slack direct client.

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
                self._config = SlackAPIConfig(
                    base_url=settings.slack.base_url,
                    timeout_seconds=settings.slack.timeout_seconds,
                    retry_attempts=settings.slack.retry_attempts,
                    retry_backoff_factor=settings.slack.retry_backoff_factor,
                )
            except ImportError:
                # Fallback to defaults if config module not available
                self._config = SlackAPIConfig()

        self.base_url = self._config.base_url
        self.timeout = self._config.timeout_seconds

        logger.info(
            "SlackDirectClient initialized: base_url=%s",
            self.base_url,
        )

    # ─────────────────────────────────────────────────────────────────────────
    # HTTP Helpers
    # ─────────────────────────────────────────────────────────────────────────

    def _get_headers(self, auth_token: str) -> dict[str, str]:
        """
        Get headers for Slack API requests.

        Args:
            auth_token: Slack bot/user token (xoxb-xxx or xoxp-xxx)

        Returns:
            Headers dict including Authorization
        """
        return {
            "Authorization": f"Bearer {auth_token}",
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

        CRITICAL: Slack returns HTTP 200 even for errors!
        Must check the 'ok' field in the response body.

        Args:
            tool_name: Name of the tool that was called
            response: httpx Response object
            start_time: Request start time for duration calculation

        Returns:
            ToolResult with success or error status
        """
        duration_ms = (datetime.now(timezone.utc) - start_time).total_seconds() * 1000

        # Handle HTTP-level errors first (rare with Slack)
        if response.status_code >= 400:
            try:
                error_data = response.json()
                message = error_data.get("error", "Unknown error")
            except Exception:
                message = response.text[:500] if response.text else "Unknown error"

            error_message = f"HTTP {response.status_code}: {message}"
            logger.warning(
                "Slack API HTTP error for %s: %s",
                tool_name,
                error_message,
            )

            return ToolResult(
                status=ToolCallStatus.ERROR,
                is_error=True,
                error_message=error_message,
                content=[{"type": "text", "text": error_message}],
                raw={"status_code": response.status_code, "error": message},
                duration_ms=duration_ms,
            )

        # Parse JSON response
        try:
            data = response.json()
        except Exception:
            error_message = "Failed to parse Slack response as JSON"
            return ToolResult(
                status=ToolCallStatus.ERROR,
                is_error=True,
                error_message=error_message,
                content=[{"type": "text", "text": error_message}],
                raw={"raw_text": response.text},
                duration_ms=duration_ms,
            )

        # CRITICAL: Check the 'ok' field - Slack returns HTTP 200 for errors!
        if not data.get("ok", False):
            error_code = data.get("error", "unknown_error")
            error_message = self._get_error_message(error_code)

            logger.warning(
                "Slack API error for %s: %s (code: %s)",
                tool_name,
                error_message,
                error_code,
            )

            # Map certain error codes to specific statuses
            status = ToolCallStatus.ERROR
            if error_code in ("not_authed", "invalid_auth", "token_revoked"):
                status = ToolCallStatus.UNAUTHORIZED

            return ToolResult(
                status=status,
                is_error=True,
                error_message=error_message,
                content=[{"type": "text", "text": error_message}],
                raw=data,
                duration_ms=duration_ms,
            )

        # Success response
        logger.debug(
            "Slack API success for %s in %.1fms",
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

    def _get_error_message(self, error_code: str) -> str:
        """
        Get human-readable error message for Slack error code.

        Args:
            error_code: Slack error code

        Returns:
            Human-readable error message
        """
        error_messages = {
            # Auth errors
            "not_authed": "No authentication token provided",
            "invalid_auth": "Invalid authentication token",
            "token_revoked": "Authentication token has been revoked",
            "missing_scope": "Token is missing required scopes",
            # Channel errors
            "channel_not_found": "Channel not found",
            "not_in_channel": "Not a member of the channel",
            "is_archived": "Channel has been archived",
            "channel_not_member": "Bot is not a member of this channel",
            # Message errors
            "message_not_found": "Message not found",
            "cant_delete_message": "Cannot delete this message",
            "msg_too_long": "Message text is too long",
            "no_text": "Message text is required",
            # Rate limiting
            "ratelimited": "Rate limit exceeded. Please wait before retrying.",
            # User errors
            "user_not_found": "User not found",
            "user_not_visible": "User is not visible",
            # Reaction errors
            "already_reacted": "Already reacted with this emoji",
            "too_many_reactions": "Too many reactions on this message",
            # General errors
            "invalid_arguments": "Invalid arguments provided",
            "fatal_error": "A fatal error occurred on Slack's side",
        }
        return error_messages.get(error_code, f"Slack error: {error_code}")

    # ─────────────────────────────────────────────────────────────────────────
    # Tool Methods
    # ─────────────────────────────────────────────────────────────────────────

    async def search_messages(
        self,
        query: str,
        count: int = 20,
        sort: str = "score",
        sort_dir: str = "desc",
        auth_token: str | None = None,
    ) -> ToolResult:
        """
        Search for messages in the Slack workspace.

        Calls GET /api/search.messages

        Args:
            query: Search query string
            count: Number of results (1-100)
            sort: Sort order ("score" or "timestamp")
            sort_dir: Sort direction ("asc" or "desc")
            auth_token: Slack user token (xoxp-xxx) - requires search:read scope

        Returns:
            ToolResult with search results or error
        """
        if auth_token is None:
            return ToolResult.from_error(
                ToolCallStatus.UNAUTHORIZED, "No auth token provided"
            )

        url = f"{self.base_url}/search.messages"
        params = {
            "query": query,
            "count": min(max(count, 1), 100),
            "sort": sort,
            "sort_dir": sort_dir,
        }

        start_time = datetime.now(timezone.utc)

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.get(
                    url,
                    params=params,
                    headers=self._get_headers(auth_token),
                )
            return self._transform_response("search_messages", response, start_time)

        except httpx.TimeoutException:
            return ToolResult.from_error(
                ToolCallStatus.TIMEOUT, "Request timed out"
            )
        except httpx.RequestError as e:
            return ToolResult.from_error(
                ToolCallStatus.ERROR, f"Request failed: {e}"
            )

    async def send_message(
        self,
        channel: str,
        text: str,
        thread_ts: str | None = None,
        auth_token: str | None = None,
    ) -> ToolResult:
        """
        Send a message to a Slack channel.

        Calls POST /api/chat.postMessage

        Args:
            channel: Channel ID (C123...) or name
            text: Message text
            thread_ts: Thread timestamp for replies
            auth_token: Slack bot token (xoxb-xxx) - requires chat:write scope

        Returns:
            ToolResult with sent message info or error
        """
        if auth_token is None:
            return ToolResult.from_error(
                ToolCallStatus.UNAUTHORIZED, "No auth token provided"
            )

        url = f"{self.base_url}/chat.postMessage"
        payload: dict[str, Any] = {
            "channel": channel,
            "text": text,
        }
        if thread_ts:
            payload["thread_ts"] = thread_ts

        start_time = datetime.now(timezone.utc)

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(
                    url,
                    json=payload,
                    headers=self._get_headers(auth_token),
                )
            return self._transform_response("send_message", response, start_time)

        except httpx.TimeoutException:
            return ToolResult.from_error(
                ToolCallStatus.TIMEOUT, "Request timed out"
            )
        except httpx.RequestError as e:
            return ToolResult.from_error(
                ToolCallStatus.ERROR, f"Request failed: {e}"
            )

    async def list_channels(
        self,
        types: str = "public_channel",
        limit: int = 100,
        cursor: str | None = None,
        exclude_archived: bool = True,
        auth_token: str | None = None,
    ) -> ToolResult:
        """
        List channels in the Slack workspace.

        Calls GET /api/conversations.list

        Args:
            types: Channel types (comma-separated: public_channel, private_channel, mpim, im)
            limit: Number of results (1-1000)
            cursor: Pagination cursor
            exclude_archived: Whether to exclude archived channels
            auth_token: Slack bot token (xoxb-xxx) - requires channels:read scope

        Returns:
            ToolResult with channel list or error
        """
        if auth_token is None:
            return ToolResult.from_error(
                ToolCallStatus.UNAUTHORIZED, "No auth token provided"
            )

        url = f"{self.base_url}/conversations.list"
        params: dict[str, Any] = {
            "types": types,
            "limit": min(max(limit, 1), 1000),
            "exclude_archived": str(exclude_archived).lower(),
        }
        if cursor:
            params["cursor"] = cursor

        start_time = datetime.now(timezone.utc)

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.get(
                    url,
                    params=params,
                    headers=self._get_headers(auth_token),
                )
            return self._transform_response("list_channels", response, start_time)

        except httpx.TimeoutException:
            return ToolResult.from_error(
                ToolCallStatus.TIMEOUT, "Request timed out"
            )
        except httpx.RequestError as e:
            return ToolResult.from_error(
                ToolCallStatus.ERROR, f"Request failed: {e}"
            )

    async def join_channel(
        self,
        channel: str,
        auth_token: str | None = None,
    ) -> ToolResult:
        """
        Join a Slack channel.

        Calls POST /api/conversations.join

        Args:
            channel: Channel ID (C123...)
            auth_token: Slack bot token (xoxb-xxx) - requires channels:join scope

        Returns:
            ToolResult with joined channel info or error
        """
        if auth_token is None:
            return ToolResult.from_error(
                ToolCallStatus.UNAUTHORIZED, "No auth token provided"
            )

        url = f"{self.base_url}/conversations.join"
        payload = {"channel": channel}

        start_time = datetime.now(timezone.utc)

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(
                    url,
                    json=payload,
                    headers=self._get_headers(auth_token),
                )
            return self._transform_response("join_channel", response, start_time)

        except httpx.TimeoutException:
            return ToolResult.from_error(
                ToolCallStatus.TIMEOUT, "Request timed out"
            )
        except httpx.RequestError as e:
            return ToolResult.from_error(
                ToolCallStatus.ERROR, f"Request failed: {e}"
            )

    async def post_reaction(
        self,
        channel: str,
        timestamp: str,
        name: str,
        auth_token: str | None = None,
    ) -> ToolResult:
        """
        Add a reaction to a message.

        Calls POST /api/reactions.add

        Args:
            channel: Channel containing the message
            timestamp: Message timestamp (e.g., "1234567890.123456")
            name: Reaction emoji name (without colons, e.g., "thumbsup")
            auth_token: Slack bot token (xoxb-xxx) - requires reactions:write scope

        Returns:
            ToolResult with success or error
        """
        if auth_token is None:
            return ToolResult.from_error(
                ToolCallStatus.UNAUTHORIZED, "No auth token provided"
            )

        url = f"{self.base_url}/reactions.add"
        # Normalize reaction name (remove colons if present)
        normalized_name = name.strip(":")
        payload = {
            "channel": channel,
            "timestamp": timestamp,
            "name": normalized_name,
        }

        start_time = datetime.now(timezone.utc)

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(
                    url,
                    json=payload,
                    headers=self._get_headers(auth_token),
                )
            return self._transform_response("post_reaction", response, start_time)

        except httpx.TimeoutException:
            return ToolResult.from_error(
                ToolCallStatus.TIMEOUT, "Request timed out"
            )
        except httpx.RequestError as e:
            return ToolResult.from_error(
                ToolCallStatus.ERROR, f"Request failed: {e}"
            )

    async def list_users(
        self,
        limit: int = 100,
        cursor: str | None = None,
        include_locale: bool = False,
        auth_token: str | None = None,
    ) -> ToolResult:
        """
        List users in the Slack workspace.

        Calls GET /api/users.list

        Args:
            limit: Number of results (1-1000)
            cursor: Pagination cursor
            include_locale: Whether to include locale information
            auth_token: Slack bot token (xoxb-xxx) - requires users:read scope

        Returns:
            ToolResult with user list or error
        """
        if auth_token is None:
            return ToolResult.from_error(
                ToolCallStatus.UNAUTHORIZED, "No auth token provided"
            )

        url = f"{self.base_url}/users.list"
        params: dict[str, Any] = {
            "limit": min(max(limit, 1), 1000),
        }
        if cursor:
            params["cursor"] = cursor
        if include_locale:
            params["include_locale"] = "true"

        start_time = datetime.now(timezone.utc)

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.get(
                    url,
                    params=params,
                    headers=self._get_headers(auth_token),
                )
            return self._transform_response("list_users", response, start_time)

        except httpx.TimeoutException:
            return ToolResult.from_error(
                ToolCallStatus.TIMEOUT, "Request timed out"
            )
        except httpx.RequestError as e:
            return ToolResult.from_error(
                ToolCallStatus.ERROR, f"Request failed: {e}"
            )

    async def search_users(
        self,
        query: str,
        limit: int = 20,
        auth_token: str | None = None,
    ) -> ToolResult:
        """
        Search for users in the Slack workspace by name or email.

        Slack has no dedicated user-search endpoint, so this fetches
        users via GET /api/users.list and filters client-side by
        real_name, display_name, and email (case-insensitive substring).

        Args:
            query: Search string (matched against name and email)
            limit: Maximum users to return after filtering
            auth_token: Slack bot token (xoxb-xxx) - requires users:read scope

        Returns:
            ToolResult with matching users or error
        """
        if auth_token is None:
            return ToolResult.from_error(
                ToolCallStatus.UNAUTHORIZED, "No auth token provided"
            )

        url = f"{self.base_url}/users.list"
        params: dict[str, Any] = {
            "limit": 200,
        }

        start_time = datetime.now(timezone.utc)

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.get(
                    url,
                    params=params,
                    headers=self._get_headers(auth_token),
                )

            result = self._transform_response("search_users", response, start_time)

            if result.is_error:
                return result

            members = result.raw.get("members", [])
            query_lower = query.lower()
            matched = []
            for member in members:
                if member.get("deleted"):
                    continue
                real_name = (member.get("real_name") or "").lower()
                display_name = (
                    member.get("profile", {}).get("display_name") or ""
                ).lower()
                email = (
                    member.get("profile", {}).get("email") or ""
                ).lower()
                if (
                    query_lower in real_name
                    or query_lower in display_name
                    or query_lower in email
                ):
                    matched.append(member)
                    if len(matched) >= limit:
                        break

            duration_ms = (
                datetime.now(timezone.utc) - start_time
            ).total_seconds() * 1000
            filtered_data = {"ok": True, "members": matched}

            return ToolResult(
                status=ToolCallStatus.SUCCESS,
                is_error=False,
                content=[{"type": "text", "text": str(filtered_data)}],
                raw=filtered_data,
                duration_ms=duration_ms,
            )

        except httpx.TimeoutException:
            return ToolResult.from_error(
                ToolCallStatus.TIMEOUT, "Request timed out"
            )
        except httpx.RequestError as e:
            return ToolResult.from_error(
                ToolCallStatus.ERROR, f"Request failed: {e}"
            )

    async def get_channel_history(
        self,
        channel: str,
        limit: int = 100,
        cursor: str | None = None,
        latest: str | None = None,
        oldest: str | None = None,
        auth_token: str | None = None,
    ) -> ToolResult:
        """
        Get message history from a channel.

        Calls GET /api/conversations.history

        Args:
            channel: Channel ID (C123...)
            limit: Number of messages (1-1000)
            cursor: Pagination cursor
            latest: End of time range (timestamp)
            oldest: Start of time range (timestamp)
            auth_token: Slack bot token (xoxb-xxx) - requires channels:history scope

        Returns:
            ToolResult with message history or error
        """
        if auth_token is None:
            return ToolResult.from_error(
                ToolCallStatus.UNAUTHORIZED, "No auth token provided"
            )

        url = f"{self.base_url}/conversations.history"
        params: dict[str, Any] = {
            "channel": channel,
            "limit": min(max(limit, 1), 1000),
        }
        if cursor:
            params["cursor"] = cursor
        if latest:
            params["latest"] = latest
        if oldest:
            params["oldest"] = oldest

        start_time = datetime.now(timezone.utc)

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.get(
                    url,
                    params=params,
                    headers=self._get_headers(auth_token),
                )
            return self._transform_response("get_channel_history", response, start_time)

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
            auth_token: Slack token

        Returns:
            ToolResult from the tool execution
        """
        # Map tool names to methods
        tool_map = {
            "search_messages": self._call_search_messages,
            "send_message": self._call_send_message,
            "list_channels": self._call_list_channels,
            "join_channel": self._call_join_channel,
            "post_reaction": self._call_post_reaction,
            "list_users": self._call_list_users,
            "search_users": self._call_search_users,
            "get_channel_history": self._call_get_channel_history,
        }

        handler = tool_map.get(tool_name)
        if handler is None:
            return ToolResult.from_error(
                ToolCallStatus.ERROR, f"Unknown tool: {tool_name}"
            )

        return await handler(arguments, auth_token)

    async def _call_search_messages(
        self, args: dict[str, Any], auth_token: str | None
    ) -> ToolResult:
        query = args.get("query")
        if not query:
            return ToolResult.from_error(
                ToolCallStatus.ERROR, "query is required"
            )
        return await self.search_messages(
            query=query,
            count=args.get("count", 20),
            sort=args.get("sort", "score"),
            sort_dir=args.get("sort_dir", "desc"),
            auth_token=auth_token,
        )

    async def _call_send_message(
        self, args: dict[str, Any], auth_token: str | None
    ) -> ToolResult:
        channel = args.get("channel")
        text = args.get("text")
        if not channel:
            return ToolResult.from_error(
                ToolCallStatus.ERROR, "channel is required"
            )
        if not text:
            return ToolResult.from_error(
                ToolCallStatus.ERROR, "text is required"
            )
        return await self.send_message(
            channel=channel,
            text=text,
            thread_ts=args.get("thread_ts"),
            auth_token=auth_token,
        )

    async def _call_list_channels(
        self, args: dict[str, Any], auth_token: str | None
    ) -> ToolResult:
        return await self.list_channels(
            types=args.get("types", "public_channel"),
            limit=args.get("limit", 100),
            cursor=args.get("cursor"),
            exclude_archived=args.get("exclude_archived", True),
            auth_token=auth_token,
        )

    async def _call_join_channel(
        self, args: dict[str, Any], auth_token: str | None
    ) -> ToolResult:
        channel = args.get("channel")
        if not channel:
            return ToolResult.from_error(
                ToolCallStatus.ERROR, "channel is required"
            )
        return await self.join_channel(
            channel=channel,
            auth_token=auth_token,
        )

    async def _call_post_reaction(
        self, args: dict[str, Any], auth_token: str | None
    ) -> ToolResult:
        channel = args.get("channel")
        timestamp = args.get("timestamp")
        name = args.get("name")
        if not channel:
            return ToolResult.from_error(
                ToolCallStatus.ERROR, "channel is required"
            )
        if not timestamp:
            return ToolResult.from_error(
                ToolCallStatus.ERROR, "timestamp is required"
            )
        if not name:
            return ToolResult.from_error(
                ToolCallStatus.ERROR, "name is required"
            )
        return await self.post_reaction(
            channel=channel,
            timestamp=timestamp,
            name=name,
            auth_token=auth_token,
        )

    async def _call_list_users(
        self, args: dict[str, Any], auth_token: str | None
    ) -> ToolResult:
        return await self.list_users(
            limit=args.get("limit", 100),
            cursor=args.get("cursor"),
            include_locale=args.get("include_locale", False),
            auth_token=auth_token,
        )

    async def _call_search_users(
        self, args: dict[str, Any], auth_token: str | None
    ) -> ToolResult:
        query = args.get("query")
        if not query:
            return ToolResult.from_error(
                ToolCallStatus.ERROR, "query is required"
            )
        return await self.search_users(
            query=query,
            limit=args.get("limit", 20),
            auth_token=auth_token,
        )

    async def _call_get_channel_history(
        self, args: dict[str, Any], auth_token: str | None
    ) -> ToolResult:
        channel = args.get("channel")
        if not channel:
            return ToolResult.from_error(
                ToolCallStatus.ERROR, "channel is required"
            )
        return await self.get_channel_history(
            channel=channel,
            limit=args.get("limit", 100),
            cursor=args.get("cursor"),
            latest=args.get("latest"),
            oldest=args.get("oldest"),
            auth_token=auth_token,
        )


# =============================================================================
# MCP Protocol Client (Original - for backwards compatibility)
# =============================================================================


# =============================================================================
# Slack MCP Client
# =============================================================================


class SlackMCPClient(BaseMCPClient):
    """
    MCP client for Slack backend.
    
    Provides Slack-specific:
    - Argument validation for Slack tools
    - Result transformation for Slack responses
    - Error handling for Slack API errors
    
    Attributes:
        backend_id: Always "slack"
    """
    
    # Channel ID pattern: C/D/G followed by alphanumeric
    CHANNEL_ID_PATTERN = re.compile(r"^[CDG][A-Z0-9]{8,}$")
    
    # User ID pattern: U/W followed by alphanumeric
    USER_ID_PATTERN = re.compile(r"^[UW][A-Z0-9]{8,}$")
    
    # Message timestamp pattern: epoch.sequence
    TIMESTAMP_PATTERN = re.compile(r"^\d+\.\d+$")
    
    # Tool-specific argument schemas for validation
    TOOL_SCHEMAS: dict[str, dict[str, list[str]]] = {
        "search_messages": {
            "required": ["query"],
            "optional": ["sort", "sort_dir", "count", "page"],
        },
        "send_message": {
            "required": ["channel", "text"],
            "optional": ["thread_ts", "blocks", "attachments", "unfurl_links", "unfurl_media"],
        },
        "list_channels": {
            "required": [],
            "optional": ["types", "limit", "cursor", "exclude_archived"],
        },
        "join_channel": {
            "required": ["channel"],
            "optional": [],
        },
        "post_reaction": {
            "required": ["channel", "timestamp", "name"],
            "optional": [],
        },
        "list_users": {
            "required": [],
            "optional": ["limit", "cursor", "include_locale"],
        },
        "search_users": {
            "required": ["query"],
            "optional": ["limit"],
        },
        "get_channel_history": {
            "required": ["channel"],
            "optional": ["limit", "cursor", "latest", "oldest"],
        },
    }
    
    @property
    def backend_id(self) -> str:
        """Return the Slack backend identifier."""
        return "slack"
    
    # ─────────────────────────────────────────────────────────────────────────
    # Argument Validation
    # ─────────────────────────────────────────────────────────────────────────
    
    def validate_tool_arguments(
        self,
        tool_name: str,
        arguments: dict[str, Any],
    ) -> dict[str, Any]:
        """
        Validate and transform Slack tool arguments.
        
        Args:
            tool_name: Slack tool name
            arguments: Raw arguments
            
        Returns:
            Validated arguments
            
        Raises:
            ValueError: If required arguments missing or invalid
        """
        schema = self.TOOL_SCHEMAS.get(tool_name)
        
        if schema is None:
            # Unknown tool - pass through to backend
            logger.warning(f"No schema for Slack tool: {tool_name}")
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
        
        # Validate channel ID format
        if "channel" in validated:
            validated["channel"] = self._validate_channel_id(validated["channel"])
        
        # Validate timestamp format
        if "timestamp" in validated:
            validated["timestamp"] = self._validate_timestamp(validated["timestamp"])
        
        if "thread_ts" in validated and validated["thread_ts"]:
            validated["thread_ts"] = self._validate_timestamp(validated["thread_ts"])
        
        # Validate count/limit ranges
        if "count" in validated:
            count = validated["count"]
            if not isinstance(count, int) or count < 1 or count > 100:
                raise ValueError("count must be integer between 1 and 100")
        
        if "limit" in validated:
            limit = validated["limit"]
            if not isinstance(limit, int) or limit < 1 or limit > 1000:
                raise ValueError("limit must be integer between 1 and 1000")
        
        # Validate reaction name (emoji name without colons)
        if "name" in validated and tool_name == "post_reaction":
            validated["name"] = self._validate_reaction_name(validated["name"])
        
        return validated
    
    def _validate_channel_id(self, channel: str) -> str:
        """
        Validate Slack channel ID format.
        
        Slack channel IDs start with:
        - C: Public channel
        - D: DM
        - G: Private channel or group DM
        
        Args:
            channel: Channel ID or name
            
        Returns:
            Validated channel ID
            
        Raises:
            ValueError: If format is invalid
        """
        if not channel:
            raise ValueError("Channel ID cannot be empty")
        
        # If it looks like a channel ID, validate format
        if channel[0] in "CDG" and len(channel) > 8:
            if not self.CHANNEL_ID_PATTERN.match(channel):
                raise ValueError(f"Invalid channel ID format: {channel}")
        # Otherwise assume it's a channel name (let backend resolve)
        
        return channel
    
    def _validate_timestamp(self, timestamp: str) -> str:
        """
        Validate Slack message timestamp format.
        
        Format: epoch.sequence (e.g., "1234567890.123456")
        
        Args:
            timestamp: Message timestamp
            
        Returns:
            Validated timestamp
            
        Raises:
            ValueError: If format is invalid
        """
        if not timestamp:
            raise ValueError("Timestamp cannot be empty")
        
        if not self.TIMESTAMP_PATTERN.match(timestamp):
            raise ValueError(
                f"Invalid timestamp format: {timestamp}. "
                "Expected format: epoch.sequence (e.g., 1234567890.123456)"
            )
        
        return timestamp
    
    def _validate_reaction_name(self, name: str) -> str:
        """
        Validate and normalize reaction (emoji) name.
        
        Removes surrounding colons if present.
        
        Args:
            name: Reaction name (e.g., "thumbsup" or ":thumbsup:")
            
        Returns:
            Normalized reaction name without colons
        """
        if not name:
            raise ValueError("Reaction name cannot be empty")
        
        # Remove surrounding colons if present
        normalized = name.strip(":")
        
        if not normalized:
            raise ValueError("Reaction name cannot be empty after removing colons")
        
        return normalized
    
    # ─────────────────────────────────────────────────────────────────────────
    # Result Transformation
    # ─────────────────────────────────────────────────────────────────────────
    
    def transform_tool_result(
        self,
        tool_name: str,
        result: ToolResult,
    ) -> ToolResult:
        """
        Transform Slack tool results.
        
        Handles:
        - Rate limit errors (ratelimited)
        - Channel not found errors
        - Permission errors (missing_scope, not_in_channel)
        - Extracting useful content from responses
        
        Args:
            tool_name: Tool that was called
            result: Raw result from backend
            
        Returns:
            Transformed result
        """
        # Check for Slack-specific errors in the result
        if result.is_error:
            result = self._transform_error(tool_name, result)
        
        return result
    
    def _transform_error(self, tool_name: str, result: ToolResult) -> ToolResult:
        """Transform Slack error responses."""
        error_msg = result.error_message or ""
        error_lower = error_msg.lower()
        
        # Detect rate limiting
        if "ratelimited" in error_lower or "rate_limited" in error_lower:
            logger.warning(f"Slack rate limit hit for {tool_name}")
            return ToolResult(
                status=ToolCallStatus.ERROR,
                is_error=True,
                error_message="Slack rate limit exceeded. Please wait before retrying.",
                content=[{"type": "text", "text": "Rate limit exceeded"}],
                raw=result.raw,
                duration_ms=result.duration_ms,
            )
        
        # Detect channel not found
        if "channel_not_found" in error_lower:
            return ToolResult(
                status=ToolCallStatus.ERROR,
                is_error=True,
                error_message="Slack channel not found or not accessible",
                content=[{"type": "text", "text": "Channel not found"}],
                raw=result.raw,
                duration_ms=result.duration_ms,
            )
        
        # Detect permission errors
        if any(err in error_lower for err in ["missing_scope", "not_in_channel", "channel_not_member"]):
            return ToolResult(
                status=ToolCallStatus.ERROR,
                is_error=True,
                error_message=f"Insufficient permissions for Slack operation: {error_msg}",
                content=[{"type": "text", "text": f"Permission denied: {error_msg}"}],
                raw=result.raw,
                duration_ms=result.duration_ms,
            )
        
        # Detect not authed
        if "not_authed" in error_lower or "invalid_auth" in error_lower:
            return ToolResult(
                status=ToolCallStatus.UNAUTHORIZED,
                is_error=True,
                error_message="Slack authentication failed",
                content=[{"type": "text", "text": "Authentication failed"}],
                raw=result.raw,
                duration_ms=result.duration_ms,
            )
        
        # Detect message not found (for reactions)
        if "message_not_found" in error_lower:
            return ToolResult(
                status=ToolCallStatus.ERROR,
                is_error=True,
                error_message="Slack message not found",
                content=[{"type": "text", "text": "Message not found"}],
                raw=result.raw,
                duration_ms=result.duration_ms,
            )
        
        return result
    
    # ─────────────────────────────────────────────────────────────────────────
    # Convenience Methods
    # ─────────────────────────────────────────────────────────────────────────
    
    async def search_messages(
        self,
        query: str,
        count: int = 20,
        sort: str = "timestamp",
        auth_token: str | None = None,
    ) -> ToolResult:
        """
        Search for messages in the Slack workspace.
        
        Args:
            query: Search query string
            count: Number of results (1-100)
            sort: Sort order ("timestamp" or "score")
            auth_token: Authorization token
            
        Returns:
            ToolResult with search results
        """
        return await self.call_tool(
            "search_messages",
            {"query": query, "count": count, "sort": sort},
            auth_token=auth_token,
        )
    
    async def send_message(
        self,
        channel: str,
        text: str,
        thread_ts: str | None = None,
        auth_token: str | None = None,
    ) -> ToolResult:
        """
        Send a message to a Slack channel.
        
        Args:
            channel: Channel ID or name
            text: Message text
            thread_ts: Thread timestamp for replies
            auth_token: Authorization token
            
        Returns:
            ToolResult with sent message info
        """
        arguments: dict[str, Any] = {"channel": channel, "text": text}
        if thread_ts:
            arguments["thread_ts"] = thread_ts
        
        return await self.call_tool("send_message", arguments, auth_token=auth_token)
    
    async def list_channels(
        self,
        types: str = "public_channel",
        limit: int = 100,
        exclude_archived: bool = True,
        auth_token: str | None = None,
    ) -> ToolResult:
        """
        List accessible channels in the workspace.
        
        Args:
            types: Channel types to include (comma-separated)
            limit: Maximum channels to return
            exclude_archived: Whether to exclude archived channels
            auth_token: Authorization token
            
        Returns:
            ToolResult with channel list
        """
        return await self.call_tool(
            "list_channels",
            {
                "types": types,
                "limit": limit,
                "exclude_archived": exclude_archived,
            },
            auth_token=auth_token,
        )
    
    async def join_channel(
        self,
        channel: str,
        auth_token: str | None = None,
    ) -> ToolResult:
        """
        Join a Slack channel.
        
        Args:
            channel: Channel ID
            auth_token: Authorization token
            
        Returns:
            ToolResult with join result
        """
        return await self.call_tool(
            "join_channel",
            {"channel": channel},
            auth_token=auth_token,
        )
    
    async def post_reaction(
        self,
        channel: str,
        timestamp: str,
        name: str,
        auth_token: str | None = None,
    ) -> ToolResult:
        """
        Add a reaction to a message.
        
        Args:
            channel: Channel containing the message
            timestamp: Message timestamp
            name: Reaction emoji name (without colons)
            auth_token: Authorization token
            
        Returns:
            ToolResult with reaction result
        """
        return await self.call_tool(
            "post_reaction",
            {"channel": channel, "timestamp": timestamp, "name": name},
            auth_token=auth_token,
        )
    
    async def list_users(
        self,
        limit: int = 100,
        auth_token: str | None = None,
    ) -> ToolResult:
        """
        List users in the workspace.

        Args:
            limit: Maximum users to return
            auth_token: Authorization token

        Returns:
            ToolResult with user list
        """
        return await self.call_tool(
            "list_users",
            {"limit": limit},
            auth_token=auth_token,
        )

    async def get_channel_history(
        self,
        channel: str,
        limit: int = 100,
        cursor: str | None = None,
        auth_token: str | None = None,
    ) -> ToolResult:
        """
        Get message history from a channel.

        Args:
            channel: Channel ID
            limit: Maximum messages to return
            cursor: Pagination cursor
            auth_token: Authorization token

        Returns:
            ToolResult with message history
        """
        arguments: dict[str, Any] = {"channel": channel, "limit": limit}
        if cursor:
            arguments["cursor"] = cursor

        return await self.call_tool(
            "get_channel_history",
            arguments,
            auth_token=auth_token,
        )


# =============================================================================
# Factory Function
# =============================================================================


def create_slack_client(
    connection_manager: BackendConnectionManager,
    **kwargs: Any,
) -> SlackMCPClient:
    """
    Create a Slack MCP client.

    Args:
        connection_manager: Backend connection manager
        **kwargs: Additional client options

    Returns:
        Configured SlackMCPClient
    """
    return SlackMCPClient(connection_manager, **kwargs)


def create_slack_direct_client(
    config: SlackAPIConfig | None = None,
) -> SlackDirectClient:
    """
    Create a Slack direct API client.

    Args:
        config: Optional configuration (loads from GatewaySettings if not provided)

    Returns:
        Configured SlackDirectClient
    """
    return SlackDirectClient(config)
