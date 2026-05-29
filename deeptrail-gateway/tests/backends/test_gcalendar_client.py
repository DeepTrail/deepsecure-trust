"""Tests for ``GCalendarDirectClient`` (WS-D3).

Covers all 15 test cases from the WS-D3 task ticket:

1.  list_calendars success
2.  list_events success
3.  list_events with time_min (RFC 3339 forwarded)
4.  list_events default to "primary"
5.  read_event success
6.  search_events success
7.  No auth token (all methods → UNAUTHORIZED)
8.  HTTP 401 → ToolResult(ERROR)
9.  HTTP 404 → ToolResult(ERROR)
10. Timeout (httpx.TimeoutException → TIMEOUT)
11. Connection error (httpx.ConnectError → ERROR)
12. call_tool dispatch (each tool routes to correct method)
13. call_tool unknown tool → ERROR
14. Config from settings (no explicit config)
15. Factory function (create_gcalendar_direct_client)
"""

from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from app.backends.base_mcp_client import ToolCallStatus
from app.backends.gcalendar_client import (
    GCalendarAPIConfig,
    GCalendarDirectClient,
    create_gcalendar_direct_client,
)


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def gcalendar_config():
    return GCalendarAPIConfig(
        base_url="https://www.googleapis.com/calendar/v3",
        timeout_seconds=30.0,
    )


@pytest.fixture
def gcalendar_client(gcalendar_config):
    return GCalendarDirectClient(config=gcalendar_config)


def _mock_response(status_code: int, body: dict | None = None, text: str | None = None):
    """Build a MagicMock that mimics ``httpx.Response``."""
    response = MagicMock(spec=httpx.Response)
    response.status_code = status_code
    response.json.return_value = body if body is not None else {}
    response.text = text if text is not None else ("" if body is None else str(body))
    return response


# =============================================================================
# Initialization / Config Tests
# =============================================================================


class TestInit:
    def test_init_with_explicit_config(self, gcalendar_config):
        client = GCalendarDirectClient(config=gcalendar_config)
        assert client.base_url == "https://www.googleapis.com/calendar/v3"
        assert client.timeout == 30.0

    def test_init_with_custom_config(self):
        config = GCalendarAPIConfig(
            base_url="http://mock-gcal:8080",
            timeout_seconds=60.0,
        )
        client = GCalendarDirectClient(config=config)
        assert client.base_url == "http://mock-gcal:8080"
        assert client.timeout == 60.0

    def test_init_loads_from_settings(self):
        """Test 14: when no config provided, loads from get_settings().gcalendar."""
        from app.core.config import reset_settings

        reset_settings()
        client = GCalendarDirectClient()
        assert client.base_url == "https://www.googleapis.com/calendar/v3"
        assert client.timeout == 30.0

    def test_factory_function(self, gcalendar_config):
        """Test 15: factory returns a GCalendarDirectClient."""
        client = create_gcalendar_direct_client(config=gcalendar_config)
        assert isinstance(client, GCalendarDirectClient)

    def test_factory_function_no_config(self):
        client = create_gcalendar_direct_client()
        assert isinstance(client, GCalendarDirectClient)


# =============================================================================
# Headers
# =============================================================================


class TestHeaders:
    def test_get_headers_uses_bearer_token(self, gcalendar_client):
        headers = gcalendar_client._get_headers("ya29.test_token")
        assert headers["Authorization"] == "Bearer ya29.test_token"
        assert headers["Accept"] == "application/json"


# =============================================================================
# list_calendars (Test 1)
# =============================================================================


class TestListCalendars:
    @pytest.mark.asyncio
    async def test_list_calendars_success(self, gcalendar_client):
        """Test 1: 200 response with calendar list."""
        mock_response = _mock_response(
            200,
            body={
                "items": [
                    {"id": "primary", "summary": "Primary"},
                    {"id": "u@x.com", "summary": "Work"},
                ]
            },
        )

        with patch.object(httpx.AsyncClient, "get", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = mock_response

            result = await gcalendar_client.list_calendars(auth_token="ya29.test")

            assert not result.is_error
            assert result.status == ToolCallStatus.SUCCESS
            assert len(result.raw["items"]) == 2
            assert (
                mock_get.call_args.args[0]
                == "https://www.googleapis.com/calendar/v3/users/me/calendarList"
            )


# =============================================================================
# list_events (Tests 2, 3, 4)
# =============================================================================


class TestListEvents:
    @pytest.mark.asyncio
    async def test_list_events_success(self, gcalendar_client):
        """Test 2: 200 response with events.

        The implementation defaults ``timeMin`` to the current time when
        not explicitly provided, so it is always present in params.
        """
        mock_response = _mock_response(
            200,
            body={
                "items": [
                    {"id": "evt-1", "summary": "Meeting"},
                    {"id": "evt-2", "summary": "Lunch"},
                ]
            },
        )

        with patch.object(httpx.AsyncClient, "get", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = mock_response

            result = await gcalendar_client.list_events(
                calendar_id="primary", auth_token="ya29.test"
            )

            assert not result.is_error
            assert result.status == ToolCallStatus.SUCCESS
            assert (
                mock_get.call_args.args[0]
                == "https://www.googleapis.com/calendar/v3/calendars/primary/events"
            )
            params = mock_get.call_args.kwargs["params"]
            assert params["singleEvents"] == "true"
            assert params["orderBy"] == "startTime"
            assert params["maxResults"] == 10
            assert "timeMin" in params

    @pytest.mark.asyncio
    async def test_list_events_with_time_min(self, gcalendar_client):
        """Test 3: time_min (RFC 3339) is forwarded as `timeMin` param."""
        mock_response = _mock_response(200, body={"items": []})

        with patch.object(httpx.AsyncClient, "get", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = mock_response

            await gcalendar_client.list_events(
                calendar_id="primary",
                auth_token="ya29.test",
                time_min="2026-04-18T00:00:00Z",
            )

            params = mock_get.call_args.kwargs["params"]
            assert params["timeMin"] == "2026-04-18T00:00:00Z"

    @pytest.mark.asyncio
    async def test_list_events_default_calendar_primary(self, gcalendar_client):
        """Test 4: dispatcher defaults calendar_id to "primary" when missing."""
        mock_response = _mock_response(200, body={"items": []})

        with patch.object(httpx.AsyncClient, "get", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = mock_response

            await gcalendar_client.call_tool(
                "list_events", {}, auth_token="ya29.test"
            )

            assert (
                mock_get.call_args.args[0]
                == "https://www.googleapis.com/calendar/v3/calendars/primary/events"
            )


# =============================================================================
# read_event (Test 5)
# =============================================================================


class TestReadEvent:
    @pytest.mark.asyncio
    async def test_read_event_success(self, gcalendar_client):
        """Test 5: 200 response with single event."""
        mock_response = _mock_response(
            200,
            body={
                "id": "evt-1",
                "summary": "Meeting",
                "start": {"dateTime": "2026-04-18T10:00:00Z"},
            },
        )

        with patch.object(httpx.AsyncClient, "get", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = mock_response

            result = await gcalendar_client.read_event(
                calendar_id="primary",
                event_id="evt-1",
                auth_token="ya29.test",
            )

            assert not result.is_error
            assert result.status == ToolCallStatus.SUCCESS
            assert result.raw["id"] == "evt-1"
            assert (
                mock_get.call_args.args[0]
                == "https://www.googleapis.com/calendar/v3/calendars/primary/events/evt-1"
            )


# =============================================================================
# search_events (Test 6)
# =============================================================================


class TestSearchEvents:
    @pytest.mark.asyncio
    async def test_search_events_success(self, gcalendar_client):
        """Test 6: 200 response with `q` param set."""
        mock_response = _mock_response(
            200, body={"items": [{"id": "evt-1", "summary": "Standup"}]}
        )

        with patch.object(httpx.AsyncClient, "get", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = mock_response

            result = await gcalendar_client.search_events(
                calendar_id="primary",
                query="standup",
                auth_token="ya29.test",
                max_results=25,
            )

            assert not result.is_error
            params = mock_get.call_args.kwargs["params"]
            assert params["q"] == "standup"
            assert params["maxResults"] == 25
            assert params["singleEvents"] == "true"


# =============================================================================
# No auth token (Test 7)
# =============================================================================


class TestUnauthorized:
    @pytest.mark.asyncio
    async def test_list_calendars_no_auth_token(self, gcalendar_client):
        result = await gcalendar_client.list_calendars(auth_token=None)
        assert result.is_error
        assert result.status == ToolCallStatus.UNAUTHORIZED

    @pytest.mark.asyncio
    async def test_list_events_no_auth_token(self, gcalendar_client):
        result = await gcalendar_client.list_events(
            calendar_id="primary", auth_token=None
        )
        assert result.is_error
        assert result.status == ToolCallStatus.UNAUTHORIZED

    @pytest.mark.asyncio
    async def test_read_event_no_auth_token(self, gcalendar_client):
        result = await gcalendar_client.read_event(
            calendar_id="primary", event_id="evt-1", auth_token=None
        )
        assert result.is_error
        assert result.status == ToolCallStatus.UNAUTHORIZED

    @pytest.mark.asyncio
    async def test_search_events_no_auth_token(self, gcalendar_client):
        result = await gcalendar_client.search_events(
            calendar_id="primary", query="x", auth_token=None
        )
        assert result.is_error
        assert result.status == ToolCallStatus.UNAUTHORIZED


# =============================================================================
# HTTP error responses (Tests 8, 9)
# =============================================================================


class TestHTTPErrors:
    @pytest.mark.asyncio
    async def test_http_401_unauthorized(self, gcalendar_client):
        """Test 8: HTTP 401 → ToolResult(ERROR) carrying Google error message."""
        mock_response = _mock_response(
            401,
            body={"error": {"code": 401, "message": "Invalid Credentials"}},
        )

        with patch.object(httpx.AsyncClient, "get", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = mock_response

            result = await gcalendar_client.list_calendars(auth_token="bad_token")

            assert result.is_error
            assert result.status == ToolCallStatus.ERROR
            assert "Invalid Credentials" in result.error_message
            assert result.raw["status_code"] == 401

    @pytest.mark.asyncio
    async def test_http_404_not_found(self, gcalendar_client):
        """Test 9: HTTP 404 → ToolResult(ERROR) carrying Google error message."""
        mock_response = _mock_response(
            404, body={"error": {"code": 404, "message": "Event not found"}}
        )

        with patch.object(httpx.AsyncClient, "get", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = mock_response

            result = await gcalendar_client.read_event(
                calendar_id="primary",
                event_id="nonexistent",
                auth_token="ya29.test",
            )

            assert result.is_error
            assert "Event not found" in result.error_message

    @pytest.mark.asyncio
    async def test_error_with_unparseable_body(self, gcalendar_client):
        """Error response with non-JSON body falls back to raw text (truncated)."""
        long_text = "a" * 1000
        mock_response = MagicMock(spec=httpx.Response)
        mock_response.status_code = 502
        mock_response.json.side_effect = ValueError("not json")
        mock_response.text = long_text

        with patch.object(httpx.AsyncClient, "get", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = mock_response

            result = await gcalendar_client.list_calendars(auth_token="ya29.test")

            assert result.is_error
            assert len(result.raw["error"]) <= 500


# =============================================================================
# Network errors (Tests 10, 11)
# =============================================================================


class TestNetworkErrors:
    @pytest.mark.asyncio
    async def test_timeout(self, gcalendar_client):
        """Test 10: httpx.TimeoutException → ToolResult(TIMEOUT)."""
        with patch.object(httpx.AsyncClient, "get", new_callable=AsyncMock) as mock_get:
            mock_get.side_effect = httpx.TimeoutException("timed out")

            result = await gcalendar_client.list_events(
                calendar_id="primary", auth_token="ya29.test"
            )

            assert result.is_error
            assert result.status == ToolCallStatus.TIMEOUT
            assert "timed out" in result.error_message.lower()

    @pytest.mark.asyncio
    async def test_connection_error(self, gcalendar_client):
        """Test 11: httpx.ConnectError → ToolResult(ERROR)."""
        with patch.object(httpx.AsyncClient, "get", new_callable=AsyncMock) as mock_get:
            mock_get.side_effect = httpx.ConnectError("connection refused")

            result = await gcalendar_client.read_event(
                calendar_id="primary",
                event_id="evt-1",
                auth_token="ya29.test",
            )

            assert result.is_error
            assert result.status == ToolCallStatus.ERROR
            assert "Request failed" in result.error_message


# =============================================================================
# call_tool dispatcher (Tests 12, 13)
# =============================================================================


class TestCallToolDispatch:
    @pytest.mark.asyncio
    async def test_dispatch_list_calendars(self, gcalendar_client):
        """Test 12a: call_tool('list_calendars', ...) routes to list_calendars."""
        with patch.object(
            gcalendar_client, "list_calendars", new_callable=AsyncMock
        ) as mock_method:
            mock_method.return_value = MagicMock(is_error=False)

            await gcalendar_client.call_tool(
                "list_calendars", {}, auth_token="ya29.test"
            )

            mock_method.assert_awaited_once()
            assert mock_method.await_args.kwargs["auth_token"] == "ya29.test"

    @pytest.mark.asyncio
    async def test_dispatch_list_events(self, gcalendar_client):
        """Test 12b: call_tool('list_events', ...) routes to list_events."""
        with patch.object(
            gcalendar_client, "list_events", new_callable=AsyncMock
        ) as mock_method:
            mock_method.return_value = MagicMock(is_error=False)

            await gcalendar_client.call_tool(
                "list_events",
                {"calendar_id": "u@x.com", "max_results": 50, "time_min": "2026-04-18T00:00:00Z"},
                auth_token="ya29.test",
            )

            mock_method.assert_awaited_once()
            kwargs = mock_method.await_args.kwargs
            assert kwargs["calendar_id"] == "u@x.com"
            assert kwargs["max_results"] == 50
            assert kwargs["time_min"] == "2026-04-18T00:00:00Z"

    @pytest.mark.asyncio
    async def test_dispatch_read_event(self, gcalendar_client):
        """Test 12c: call_tool('read_event', ...) routes to read_event."""
        with patch.object(
            gcalendar_client, "read_event", new_callable=AsyncMock
        ) as mock_method:
            mock_method.return_value = MagicMock(is_error=False)

            await gcalendar_client.call_tool(
                "read_event",
                {"calendar_id": "primary", "event_id": "evt-1"},
                auth_token="ya29.test",
            )

            mock_method.assert_awaited_once()
            assert mock_method.await_args.kwargs["event_id"] == "evt-1"

    @pytest.mark.asyncio
    async def test_dispatch_search_events(self, gcalendar_client):
        """Test 12d: call_tool('search_events', ...) routes to search_events."""
        with patch.object(
            gcalendar_client, "search_events", new_callable=AsyncMock
        ) as mock_method:
            mock_method.return_value = MagicMock(is_error=False)

            await gcalendar_client.call_tool(
                "search_events",
                {"query": "standup", "max_results": 25},
                auth_token="ya29.test",
            )

            mock_method.assert_awaited_once()
            kwargs = mock_method.await_args.kwargs
            assert kwargs["query"] == "standup"
            assert kwargs["max_results"] == 25
            # calendar_id defaults to "primary" via dispatcher
            assert kwargs["calendar_id"] == "primary"

    @pytest.mark.asyncio
    async def test_dispatch_read_event_missing_id(self, gcalendar_client):
        """call_tool('read_event', {}) → ERROR (no event_id)."""
        result = await gcalendar_client.call_tool(
            "read_event", {}, auth_token="ya29.test"
        )
        assert result.is_error
        assert "event_id is required" in result.error_message

    @pytest.mark.asyncio
    async def test_dispatch_search_events_missing_query(self, gcalendar_client):
        """call_tool('search_events', {}) → ERROR (no query)."""
        result = await gcalendar_client.call_tool(
            "search_events", {}, auth_token="ya29.test"
        )
        assert result.is_error
        assert "query is required" in result.error_message

    @pytest.mark.asyncio
    async def test_dispatch_unknown_tool(self, gcalendar_client):
        """Test 13: unknown tool → ToolResult(ERROR) with 'Unknown tool'."""
        result = await gcalendar_client.call_tool(
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
    async def test_auth_token_not_in_logs(self, gcalendar_client, caplog):
        """Auth token must never appear in log output."""
        import logging

        caplog.set_level(logging.DEBUG, logger="app.backends.gcalendar_client")

        mock_response = _mock_response(200, body={"items": []})
        with patch.object(httpx.AsyncClient, "get", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = mock_response
            await gcalendar_client.list_calendars(
                auth_token="SUPER_SECRET_TOKEN_456"
            )

        for record in caplog.records:
            assert "SUPER_SECRET_TOKEN_456" not in record.getMessage()


# =============================================================================
# WS-D6 gap-fill tests — coverage matrix cells
# =============================================================================


class TestConfigFallback:
    def test_config_fallback_on_attribute_error(self):
        mock_settings = MagicMock()
        del mock_settings.gcalendar
        with patch("app.core.config.get_settings", return_value=mock_settings):
            client = GCalendarDirectClient()
        assert client.base_url == "https://www.googleapis.com/calendar/v3"
        assert client.timeout == 30.0


class TestTransformResponseEdgeCases:
    @pytest.mark.asyncio
    async def test_success_response_with_unparseable_json(self, gcalendar_client):
        response = MagicMock(spec=httpx.Response)
        response.status_code = 200
        response.json.side_effect = ValueError("bad json")
        response.text = "not-json"

        with patch.object(httpx.AsyncClient, "get", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = response
            result = await gcalendar_client.list_calendars(auth_token="tok")

        assert not result.is_error
        assert result.raw == {"raw_text": "not-json"}


class TestPerToolNetworkErrors:
    @pytest.mark.asyncio
    async def test_list_events_timeout(self, gcalendar_client):
        with patch.object(httpx.AsyncClient, "get", new_callable=AsyncMock) as mock_get:
            mock_get.side_effect = httpx.TimeoutException("timed out")
            result = await gcalendar_client.list_events(
                calendar_id="primary", auth_token="tok"
            )
        assert result.is_error
        assert result.status == ToolCallStatus.TIMEOUT

    @pytest.mark.asyncio
    async def test_read_event_connection_error(self, gcalendar_client):
        with patch.object(httpx.AsyncClient, "get", new_callable=AsyncMock) as mock_get:
            mock_get.side_effect = httpx.ConnectError("refused")
            result = await gcalendar_client.read_event(
                calendar_id="primary", event_id="e1", auth_token="tok"
            )
        assert result.is_error
        assert result.status == ToolCallStatus.ERROR

    @pytest.mark.asyncio
    async def test_search_events_timeout(self, gcalendar_client):
        with patch.object(httpx.AsyncClient, "get", new_callable=AsyncMock) as mock_get:
            mock_get.side_effect = httpx.TimeoutException("timed out")
            result = await gcalendar_client.search_events(
                query="standup", calendar_id="primary", auth_token="tok"
            )
        assert result.is_error
        assert result.status == ToolCallStatus.TIMEOUT

    @pytest.mark.asyncio
    async def test_list_calendars_connection_error(self, gcalendar_client):
        with patch.object(httpx.AsyncClient, "get", new_callable=AsyncMock) as mock_get:
            mock_get.side_effect = httpx.ConnectError("refused")
            result = await gcalendar_client.list_calendars(auth_token="tok")
        assert result.is_error
        assert result.status == ToolCallStatus.ERROR
