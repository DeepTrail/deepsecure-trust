"""Google Calendar backend client for MCP Gateway.

Translates MCP tool calls into Google Calendar v3 REST API requests.
Auth tokens are injected per-call from the vault by the Gateway.

Tools:
- list_calendars: List user's calendars
- list_events: List events on a calendar (defaults to "primary")
- read_event: Get single event details
- search_events: Search events by free-text query
"""

import json
import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

import httpx

from .base_mcp_client import ToolCallStatus, ToolResult

logger = logging.getLogger(__name__)


@dataclass
class GCalendarAPIConfig:
    """Configuration for Google Calendar API client."""

    base_url: str = "https://www.googleapis.com/calendar/v3"
    timeout_seconds: float = 30.0
    retry_attempts: int = 3
    retry_backoff_factor: float = 0.5


class GCalendarDirectClient:
    """Direct Google Calendar REST API client.

    Makes direct HTTP calls to Google Calendar's REST API, translating
    tool calls into appropriate API requests.

    Usage:
        client = GCalendarDirectClient()
        result = await client.list_events("primary", auth_token="ya29.xxx")
    """

    def __init__(self, config: GCalendarAPIConfig | None = None) -> None:
        if config is not None:
            self._config = config
        else:
            try:
                from app.core.config import get_settings

                settings = get_settings()
                self._config = GCalendarAPIConfig(
                    base_url=settings.gcalendar.base_url,
                    timeout_seconds=settings.gcalendar.timeout_seconds,
                    retry_attempts=settings.gcalendar.retry_attempts,
                    retry_backoff_factor=settings.gcalendar.retry_backoff_factor,
                )
            except (ImportError, AttributeError):
                self._config = GCalendarAPIConfig()

        self.base_url = self._config.base_url
        self.timeout = self._config.timeout_seconds

        logger.info(
            "GCalendarDirectClient initialized: base_url=%s", self.base_url
        )

    def _get_headers(self, auth_token: str) -> dict[str, str]:
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
                message = response.text[:500] if response.text else "Unknown error"

            logger.warning(
                "Google Calendar API error for %s: %s (HTTP %d)",
                tool_name,
                message,
                response.status_code,
            )

            return ToolResult(
                status=ToolCallStatus.ERROR,
                is_error=True,
                error_message=(
                    f"Google Calendar API error ({response.status_code}): {message}"
                ),
                content=[{"type": "text", "text": f"Error: {message}"}],
                raw={"status_code": response.status_code, "error": message},
                duration_ms=duration_ms,
            )

        try:
            data = response.json()
        except Exception:
            data = {"raw_text": response.text}

        logger.debug(
            "Google Calendar API success for %s in %.1fms",
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

    async def list_calendars(
        self, auth_token: str | None = None
    ) -> ToolResult:
        """List user's calendars. Calls GET /users/me/calendarList."""
        if auth_token is None:
            return ToolResult.from_error(
                ToolCallStatus.UNAUTHORIZED, "No auth token provided"
            )

        url = f"{self.base_url}/users/me/calendarList"
        start_time = datetime.now(timezone.utc)

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.get(
                    url, headers=self._get_headers(auth_token)
                )
            return self._transform_response("list_calendars", response, start_time)

        except httpx.TimeoutException:
            return ToolResult.from_error(
                ToolCallStatus.TIMEOUT, "Request timed out"
            )
        except httpx.RequestError as e:
            return ToolResult.from_error(
                ToolCallStatus.ERROR, f"Request failed: {e}"
            )

    async def list_events(
        self,
        calendar_id: str,
        auth_token: str | None = None,
        max_results: int = 10,
        time_min: str | None = None,
    ) -> ToolResult:
        """List events on a calendar.

        Calls GET /calendars/{calendarId}/events with singleEvents=true
        and orderBy=startTime for expanded recurring event instances.
        """
        if auth_token is None:
            return ToolResult.from_error(
                ToolCallStatus.UNAUTHORIZED, "No auth token provided"
            )

        url = f"{self.base_url}/calendars/{calendar_id}/events"
        params: dict[str, Any] = {
            "maxResults": max_results,
            "singleEvents": "true",
            "orderBy": "startTime",
        }
        if time_min:
            params["timeMin"] = time_min

        start_time = datetime.now(timezone.utc)

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.get(
                    url,
                    params=params,
                    headers=self._get_headers(auth_token),
                )
            return self._transform_response("list_events", response, start_time)

        except httpx.TimeoutException:
            return ToolResult.from_error(
                ToolCallStatus.TIMEOUT, "Request timed out"
            )
        except httpx.RequestError as e:
            return ToolResult.from_error(
                ToolCallStatus.ERROR, f"Request failed: {e}"
            )

    async def read_event(
        self,
        calendar_id: str,
        event_id: str,
        auth_token: str | None = None,
    ) -> ToolResult:
        """Get single event details.

        Calls GET /calendars/{calendarId}/events/{eventId}.
        """
        if auth_token is None:
            return ToolResult.from_error(
                ToolCallStatus.UNAUTHORIZED, "No auth token provided"
            )

        url = f"{self.base_url}/calendars/{calendar_id}/events/{event_id}"
        start_time = datetime.now(timezone.utc)

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.get(
                    url, headers=self._get_headers(auth_token)
                )
            return self._transform_response("read_event", response, start_time)

        except httpx.TimeoutException:
            return ToolResult.from_error(
                ToolCallStatus.TIMEOUT, "Request timed out"
            )
        except httpx.RequestError as e:
            return ToolResult.from_error(
                ToolCallStatus.ERROR, f"Request failed: {e}"
            )

    async def search_events(
        self,
        calendar_id: str,
        query: str,
        auth_token: str | None = None,
        max_results: int = 10,
    ) -> ToolResult:
        """Search events by free-text query.

        Calls GET /calendars/{calendarId}/events?q={query}.
        """
        if auth_token is None:
            return ToolResult.from_error(
                ToolCallStatus.UNAUTHORIZED, "No auth token provided"
            )

        url = f"{self.base_url}/calendars/{calendar_id}/events"
        params: dict[str, Any] = {
            "q": query,
            "maxResults": max_results,
            "singleEvents": "true",
            "orderBy": "startTime",
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
                "search_events", response, start_time
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
        """Dispatch a tool call to the appropriate method."""
        tool_map = {
            "list_calendars": self._call_list_calendars,
            "list_events": self._call_list_events,
            "read_event": self._call_read_event,
            "search_events": self._call_search_events,
        }

        handler = tool_map.get(tool_name)
        if handler is None:
            return ToolResult.from_error(
                ToolCallStatus.ERROR, f"Unknown tool: {tool_name}"
            )

        return await handler(arguments, auth_token)

    async def _call_list_calendars(
        self, args: dict[str, Any], auth_token: str | None
    ) -> ToolResult:
        return await self.list_calendars(auth_token=auth_token)

    async def _call_list_events(
        self, args: dict[str, Any], auth_token: str | None
    ) -> ToolResult:
        calendar_id = args.get("calendar_id", "primary")
        return await self.list_events(
            calendar_id=calendar_id,
            auth_token=auth_token,
            max_results=args.get("max_results", 10),
            time_min=args.get("time_min"),
        )

    async def _call_read_event(
        self, args: dict[str, Any], auth_token: str | None
    ) -> ToolResult:
        calendar_id = args.get("calendar_id", "primary")
        event_id = args.get("event_id")
        if not event_id:
            return ToolResult.from_error(
                ToolCallStatus.ERROR, "event_id is required"
            )
        return await self.read_event(
            calendar_id=calendar_id,
            event_id=event_id,
            auth_token=auth_token,
        )

    async def _call_search_events(
        self, args: dict[str, Any], auth_token: str | None
    ) -> ToolResult:
        calendar_id = args.get("calendar_id", "primary")
        query = args.get("query")
        if not query:
            return ToolResult.from_error(
                ToolCallStatus.ERROR, "query is required"
            )
        return await self.search_events(
            calendar_id=calendar_id,
            query=query,
            auth_token=auth_token,
            max_results=args.get("max_results", 10),
        )


# =============================================================================
# Factory Function
# =============================================================================


def create_gcalendar_direct_client(
    config: GCalendarAPIConfig | None = None,
) -> GCalendarDirectClient:
    """Create a Google Calendar direct API client."""
    return GCalendarDirectClient(config)
