"""
Tests for AuditMiddleware (E3).

Comprehensive tests covering:
- Full attribution capture
- Asynchronous, non-blocking audit
- Fail-open behavior (audit failures don't block tool execution)
- Sensitive data redaction
- MVP mode (local logging)
- Control Plane integration
"""

import asyncio
import logging
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from app.middleware.audit import (
    AuditEvent,
    AuditEventType,
    AuditMiddleware,
    configure_audit_middleware,
    get_audit_middleware,
    log_permission_denied,
    log_tool_call,
    reset_audit_middleware,
)
from app.middleware.jwt_validation import AgentContext


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def agent_context() -> AgentContext:
    """Standard agent context for testing."""
    return AgentContext(
        agent_id="agent-123",
        owner="sarah@example.com",
        delegation_id="deleg-456",
        session_id="sess-789",
        delegated_permissions=["notion:pages:read", "notion:pages:search"],
    )


@pytest.fixture
def middleware() -> AuditMiddleware:
    """Audit middleware in MVP mode (no control plane URL)."""
    return AuditMiddleware()


@pytest.fixture
def middleware_with_control_plane() -> AuditMiddleware:
    """Audit middleware configured with control plane."""
    return AuditMiddleware(
        control_plane_url="http://localhost:8000",
        timeout_seconds=5.0,
    )


@pytest.fixture(autouse=True)
def reset_globals():
    """Reset global middleware before each test."""
    reset_audit_middleware()
    yield
    reset_audit_middleware()


# =============================================================================
# AuditEvent Tests
# =============================================================================


class TestAuditEvent:
    """Tests for AuditEvent data class."""

    def test_creates_event_with_defaults(self):
        """Should create event with default timestamp."""
        event = AuditEvent(
            event_type=AuditEventType.MCP_TOOL_CALL,
            agent_id="agent-123",
            on_behalf_of="sarah@example.com",
            tool="notion.search_pages",
        )

        assert event.event_type == AuditEventType.MCP_TOOL_CALL
        assert event.agent_id == "agent-123"
        assert event.on_behalf_of == "sarah@example.com"
        assert event.tool == "notion.search_pages"
        assert event.timestamp is not None  # Auto-generated

    def test_to_dict_serialization(self):
        """Should serialize to dictionary."""
        event = AuditEvent(
            event_type=AuditEventType.PERMISSION_DENIED,
            agent_id="agent-123",
            on_behalf_of="sarah@example.com",
            tool="notion.create_page",
            error="Permission denied",
            duration_ms=150,
        )

        data = event.to_dict()

        assert data["event_type"] == "permission_denied"
        assert data["agent_id"] == "agent-123"
        assert data["tool"] == "notion.create_page"
        assert data["error"] == "Permission denied"
        assert data["duration_ms"] == 150


class TestAuditEventType:
    """Tests for AuditEventType enum."""

    def test_event_types(self):
        """Should have expected event types."""
        assert AuditEventType.MCP_TOOL_CALL.value == "mcp_tool_call"
        assert AuditEventType.PERMISSION_DENIED.value == "permission_denied"
        assert AuditEventType.CREDENTIAL_ERROR.value == "credential_error"
        assert AuditEventType.TOOL_ERROR.value == "tool_error"
        assert AuditEventType.DELEGATION_REVOKED.value == "delegation_revoked"


# =============================================================================
# Full Attribution Tests
# =============================================================================


class TestFullAttribution:
    """Tests for capturing full attribution in audit events."""

    @pytest.mark.asyncio
    async def test_captures_agent_context(
        self, middleware: AuditMiddleware, agent_context: AgentContext, caplog
    ):
        """Should capture full agent context in audit."""
        with caplog.at_level(logging.INFO):
            await middleware.log_tool_call(
                agent_context=agent_context,
                tool_name="notion.search_pages",
                arguments={"query": "test"},
                duration_ms=150,
            )

            # Wait for async task
            await middleware.flush()

        # Check log contains attribution
        assert "agent=agent-123" in caplog.text
        assert "user=sarah@example.com" in caplog.text
        assert "tool=notion.search_pages" in caplog.text

    @pytest.mark.asyncio
    async def test_captures_delegation_info(
        self, middleware: AuditMiddleware, agent_context: AgentContext
    ):
        """Should include delegation and session IDs."""
        events = []

        # Capture the event
        original_send = middleware._send_event

        async def capture_event(event):
            events.append(event)
            return await original_send(event)

        middleware._send_event = capture_event

        await middleware.log_tool_call(
            agent_context=agent_context,
            tool_name="notion.search_pages",
            arguments={},
        )
        await middleware.flush()

        assert len(events) == 1
        assert events[0].delegation_id == "deleg-456"
        assert events[0].session_id == "sess-789"

    @pytest.mark.asyncio
    async def test_captures_duration_ms(
        self, middleware: AuditMiddleware, agent_context: AgentContext
    ):
        """Should capture execution duration."""
        events = []

        async def capture_event(event):
            events.append(event)
            return True

        middleware._send_event = capture_event

        await middleware.log_tool_call(
            agent_context=agent_context,
            tool_name="notion.search_pages",
            arguments={},
            duration_ms=250,
        )
        await middleware.flush()

        assert events[0].duration_ms == 250


# =============================================================================
# Non-Blocking Async Tests
# =============================================================================


class TestNonBlockingAsync:
    """Tests for non-blocking, asynchronous audit."""

    @pytest.mark.asyncio
    async def test_returns_immediately(
        self, middleware: AuditMiddleware, agent_context: AgentContext
    ):
        """Should return immediately without waiting for send."""
        # Make _send_event slow
        slow_called = []

        async def slow_send(event):
            slow_called.append(True)
            await asyncio.sleep(0.5)  # Simulate slow network
            return True

        middleware._send_event = slow_send

        import time

        start = time.time()
        await middleware.log_tool_call(
            agent_context=agent_context,
            tool_name="notion.search_pages",
            arguments={},
        )
        elapsed = time.time() - start

        # Should return in < 100ms (not waiting for 500ms send)
        assert elapsed < 0.2
        assert middleware.get_pending_count() == 1

        # Cleanup
        await middleware.flush()
        assert slow_called == [True]

    @pytest.mark.asyncio
    async def test_tracks_pending_tasks(
        self, middleware: AuditMiddleware, agent_context: AgentContext
    ):
        """Should track pending audit tasks."""
        hold_events = []

        async def hold_send(event):
            hold_events.append(event)
            await asyncio.sleep(0.2)
            return True

        middleware._send_event = hold_send

        # Send multiple events
        for _ in range(3):
            await middleware.log_tool_call(
                agent_context=agent_context,
                tool_name="notion.search_pages",
                arguments={},
            )

        # Should have 3 pending
        assert middleware.get_pending_count() == 3

        # Flush waits for all
        await middleware.flush()
        assert middleware.get_pending_count() == 0
        assert len(hold_events) == 3


# =============================================================================
# Fail-Open Behavior Tests
# =============================================================================


class TestFailOpenBehavior:
    """Tests for fail-open security (audit failures don't block execution)."""

    @pytest.mark.asyncio
    async def test_continues_on_http_error(
        self, middleware_with_control_plane: AuditMiddleware, agent_context: AgentContext
    ):
        """Should continue if Control Plane returns error."""
        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.__aenter__.return_value = mock_client
            mock_client.__aexit__.return_value = None
            mock_client.post = AsyncMock(
                return_value=MagicMock(status_code=500)
            )
            mock_client_class.return_value = mock_client

            # Should not raise
            await middleware_with_control_plane.log_tool_call(
                agent_context=agent_context,
                tool_name="notion.search_pages",
                arguments={},
            )
            await middleware_with_control_plane.flush()

    @pytest.mark.asyncio
    async def test_continues_on_timeout(
        self, middleware_with_control_plane: AuditMiddleware, agent_context: AgentContext, caplog
    ):
        """Should continue if Control Plane times out."""
        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.__aenter__.return_value = mock_client
            mock_client.__aexit__.return_value = None
            mock_client.post = AsyncMock(side_effect=httpx.TimeoutException("Timeout"))
            mock_client_class.return_value = mock_client

            with caplog.at_level(logging.WARNING):
                await middleware_with_control_plane.log_tool_call(
                    agent_context=agent_context,
                    tool_name="notion.search_pages",
                    arguments={},
                )
                await middleware_with_control_plane.flush()

            # Should log warning and fall back to local logging
            assert "timeout" in caplog.text.lower()

    @pytest.mark.asyncio
    async def test_continues_on_connection_error(
        self, middleware_with_control_plane: AuditMiddleware, agent_context: AgentContext
    ):
        """Should continue if Control Plane is unreachable."""
        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.__aenter__.return_value = mock_client
            mock_client.__aexit__.return_value = None
            mock_client.post = AsyncMock(
                side_effect=httpx.ConnectError("Connection refused")
            )
            mock_client_class.return_value = mock_client

            # Should not raise
            await middleware_with_control_plane.log_tool_call(
                agent_context=agent_context,
                tool_name="notion.search_pages",
                arguments={},
            )
            await middleware_with_control_plane.flush()

    @pytest.mark.asyncio
    async def test_fallback_to_local_logging(
        self, middleware_with_control_plane: AuditMiddleware, agent_context: AgentContext, caplog
    ):
        """Should fall back to local logging on error."""
        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.__aenter__.return_value = mock_client
            mock_client.__aexit__.return_value = None
            mock_client.post = AsyncMock(
                return_value=MagicMock(status_code=503)
            )
            mock_client_class.return_value = mock_client

            with caplog.at_level(logging.INFO):
                await middleware_with_control_plane.log_tool_call(
                    agent_context=agent_context,
                    tool_name="notion.search_pages",
                    arguments={},
                )
                await middleware_with_control_plane.flush()

            # Should have local log as fallback
            assert "AUDIT" in caplog.text


# =============================================================================
# Sensitive Data Redaction Tests
# =============================================================================


class TestSensitiveDataRedaction:
    """Tests for redacting sensitive data from audit logs."""

    def test_redacts_password_fields(self, middleware: AuditMiddleware):
        """Should redact password fields."""
        data = {"username": "user", "password": "secret123"}
        result = middleware._redact_sensitive(data)

        assert result["username"] == "user"
        assert result["password"] == "[REDACTED]"

    def test_redacts_token_fields(self, middleware: AuditMiddleware):
        """Should redact token fields."""
        data = {"access_token": "abc123", "refresh_token": "xyz789", "user_id": "123"}
        result = middleware._redact_sensitive(data)

        assert result["access_token"] == "[REDACTED]"
        assert result["refresh_token"] == "[REDACTED]"
        assert result["user_id"] == "123"

    def test_redacts_api_key_fields(self, middleware: AuditMiddleware):
        """Should redact API key fields."""
        data = {"api_key": "key123", "apikey": "key456", "data": "visible"}
        result = middleware._redact_sensitive(data)

        assert result["api_key"] == "[REDACTED]"
        assert result["apikey"] == "[REDACTED]"
        assert result["data"] == "visible"

    def test_redacts_authorization_fields(self, middleware: AuditMiddleware):
        """Should redact authorization fields."""
        data = {"Authorization": "Bearer xyz", "authorization": "Basic abc"}
        result = middleware._redact_sensitive(data)

        assert result["Authorization"] == "[REDACTED]"
        assert result["authorization"] == "[REDACTED]"

    def test_redacts_nested_sensitive_data(self, middleware: AuditMiddleware):
        """Should redact sensitive data in nested dicts."""
        data = {
            "config": {
                "api_key": "secret",
                "endpoint": "https://api.example.com",
            },
            "data": "visible",
        }
        result = middleware._redact_sensitive(data)

        assert result["config"]["api_key"] == "[REDACTED]"
        assert result["config"]["endpoint"] == "https://api.example.com"
        assert result["data"] == "visible"

    def test_redacts_sensitive_data_in_lists(self, middleware: AuditMiddleware):
        """Should redact sensitive data in lists."""
        data = {
            "items": [
                {"name": "item1", "secret": "abc"},
                {"name": "item2", "password": "def"},
            ]
        }
        result = middleware._redact_sensitive(data)

        assert result["items"][0]["name"] == "item1"
        assert result["items"][0]["secret"] == "[REDACTED]"
        assert result["items"][1]["password"] == "[REDACTED]"

    def test_handles_none_data(self, middleware: AuditMiddleware):
        """Should handle None data gracefully."""
        assert middleware._redact_sensitive(None) is None

    def test_handles_empty_dict(self, middleware: AuditMiddleware):
        """Should handle empty dict."""
        assert middleware._redact_sensitive({}) == {}

    @pytest.mark.asyncio
    async def test_redacts_in_logged_events(
        self, middleware: AuditMiddleware, agent_context: AgentContext
    ):
        """Should redact sensitive data in logged events."""
        events = []

        async def capture_event(event):
            events.append(event)
            return True

        middleware._send_event = capture_event

        await middleware.log_tool_call(
            agent_context=agent_context,
            tool_name="notion.search_pages",
            arguments={
                "query": "test",
                "api_key": "should_be_redacted",
            },
        )
        await middleware.flush()

        assert events[0].arguments["query"] == "test"
        assert events[0].arguments["api_key"] == "[REDACTED]"


# =============================================================================
# MVP Mode Tests (Local Logging)
# =============================================================================


class TestMVPMode:
    """Tests for MVP mode (local logging without Control Plane)."""

    @pytest.mark.asyncio
    async def test_logs_locally_without_control_plane(
        self, middleware: AuditMiddleware, agent_context: AgentContext, caplog
    ):
        """Should log locally when no control plane configured."""
        with caplog.at_level(logging.INFO):
            await middleware.log_tool_call(
                agent_context=agent_context,
                tool_name="notion.search_pages",
                arguments={"query": "test"},
                duration_ms=150,
            )
            await middleware.flush()

        assert "AUDIT" in caplog.text
        assert "mcp_tool_call" in caplog.text
        assert "agent=agent-123" in caplog.text

    @pytest.mark.asyncio
    async def test_logs_errors_at_warning_level(
        self, middleware: AuditMiddleware, agent_context: AgentContext, caplog
    ):
        """Should log errors at WARNING level."""
        with caplog.at_level(logging.WARNING):
            await middleware.log_tool_call(
                agent_context=agent_context,
                tool_name="notion.search_pages",
                arguments={},
                error="Something went wrong",
            )
            await middleware.flush()

        assert "AUDIT" in caplog.text
        assert "Something went wrong" in caplog.text


# =============================================================================
# Control Plane Integration Tests
# =============================================================================


class TestControlPlaneIntegration:
    """Tests for Control Plane audit service integration."""

    @pytest.mark.asyncio
    async def test_sends_to_control_plane(
        self, middleware_with_control_plane: AuditMiddleware, agent_context: AgentContext
    ):
        """Should send events to Control Plane."""
        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.__aenter__.return_value = mock_client
            mock_client.__aexit__.return_value = None
            mock_client.post = AsyncMock(
                return_value=MagicMock(status_code=201)
            )
            mock_client_class.return_value = mock_client

            await middleware_with_control_plane.log_tool_call(
                agent_context=agent_context,
                tool_name="notion.search_pages",
                arguments={"query": "test"},
            )
            await middleware_with_control_plane.flush()

            # Verify post was called
            mock_client.post.assert_called_once()
            call_args = mock_client.post.call_args
            assert call_args[0][0] == "http://localhost:8000/api/v1/audit/events"

    @pytest.mark.asyncio
    async def test_sends_correct_payload(
        self, middleware_with_control_plane: AuditMiddleware, agent_context: AgentContext
    ):
        """Should send correct JSON payload to Control Plane."""
        captured_payload = None

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.__aenter__.return_value = mock_client
            mock_client.__aexit__.return_value = None

            async def capture_post(*args, **kwargs):
                nonlocal captured_payload
                captured_payload = kwargs.get("json")
                return MagicMock(status_code=200)

            mock_client.post = AsyncMock(side_effect=capture_post)
            mock_client_class.return_value = mock_client

            await middleware_with_control_plane.log_tool_call(
                agent_context=agent_context,
                tool_name="notion.search_pages",
                arguments={"query": "test"},
                duration_ms=150,
            )
            await middleware_with_control_plane.flush()

        assert captured_payload is not None
        assert captured_payload["event_type"] == "mcp_tool_call"
        assert captured_payload["agent_id"] == "agent-123"
        assert captured_payload["on_behalf_of"] == "sarah@example.com"
        assert captured_payload["tool"] == "notion.search_pages"


# =============================================================================
# Event Type Tests
# =============================================================================


class TestEventTypes:
    """Tests for different event types."""

    @pytest.mark.asyncio
    async def test_permission_denied_event(
        self, middleware: AuditMiddleware, agent_context: AgentContext
    ):
        """Should create permission denied event."""
        events = []

        async def capture_event(event):
            events.append(event)
            return True

        middleware._send_event = capture_event

        await middleware.log_permission_denied(
            agent_context=agent_context,
            tool_name="notion.create_page",
            required_permission="notion:pages:create",
            denial_reason="permission_not_granted",
        )
        await middleware.flush()

        assert events[0].event_type == AuditEventType.PERMISSION_DENIED
        assert events[0].extra_data["required_permission"] == "notion:pages:create"
        assert events[0].extra_data["denial_reason"] == "permission_not_granted"

    @pytest.mark.asyncio
    async def test_credential_error_event(
        self, middleware: AuditMiddleware, agent_context: AgentContext
    ):
        """Should create credential error event."""
        events = []

        async def capture_event(event):
            events.append(event)
            return True

        middleware._send_event = capture_event

        await middleware.log_credential_error(
            agent_context=agent_context,
            tool_name="notion.search_pages",
            error_message="Token expired",
        )
        await middleware.flush()

        assert events[0].event_type == AuditEventType.CREDENTIAL_ERROR
        assert events[0].error == "Token expired"

    @pytest.mark.asyncio
    async def test_delegation_revoked_event(
        self, middleware: AuditMiddleware, agent_context: AgentContext
    ):
        """Should create delegation revoked event."""
        events = []

        async def capture_event(event):
            events.append(event)
            return True

        middleware._send_event = capture_event

        await middleware.log_delegation_revoked(
            agent_context=agent_context,
            tool_name="notion.search_pages",
        )
        await middleware.flush()

        assert events[0].event_type == AuditEventType.DELEGATION_REVOKED
        assert events[0].error == "Delegation has been revoked"


# =============================================================================
# Result Summary Tests
# =============================================================================


class TestResultSummary:
    """Tests for result summarization."""

    def test_summarizes_text_content(self, middleware: AuditMiddleware):
        """Should summarize text content."""
        result = {
            "content": [{"type": "text", "text": "Found 5 pages"}],
            "isError": False,
        }
        summary = middleware._summarize_result(result)
        assert summary == "Found 5 pages"

    def test_truncates_long_text(self, middleware: AuditMiddleware):
        """Should truncate text longer than 100 chars."""
        long_text = "x" * 150
        result = {
            "content": [{"type": "text", "text": long_text}],
            "isError": False,
        }
        summary = middleware._summarize_result(result)
        assert len(summary) == 103  # 100 + "..."
        assert summary.endswith("...")

    def test_handles_error_result(self, middleware: AuditMiddleware):
        """Should still extract text even on error results."""
        result = {
            "content": [{"type": "text", "text": "Error occurred"}],
            "isError": True,
        }
        summary = middleware._summarize_result(result)
        # Text is extracted even on error, isError checked after content
        assert summary == "Error occurred"

    def test_handles_non_text_content(self, middleware: AuditMiddleware):
        """Should describe non-text content types."""
        result = {
            "content": [{"type": "image", "data": "..."}],
            "isError": False,
        }
        summary = middleware._summarize_result(result)
        assert "image" in summary
        assert "1 items" in summary

    def test_handles_error_flag_without_content(self, middleware: AuditMiddleware):
        """Should return 'Error response' when isError with empty content."""
        result = {
            "content": [],
            "isError": True,
        }
        summary = middleware._summarize_result(result)
        # isError flag is checked when content is empty
        assert summary == "Error response"

    def test_handles_empty_result(self, middleware: AuditMiddleware):
        """Should handle empty result."""
        assert middleware._summarize_result(None) == "No result"
        assert middleware._summarize_result({}) == "No result"


# =============================================================================
# Disabled Mode Tests
# =============================================================================


class TestDisabledMode:
    """Tests for disabled audit mode."""

    @pytest.mark.asyncio
    async def test_does_nothing_when_disabled(
        self, agent_context: AgentContext, caplog
    ):
        """Should not log when disabled."""
        middleware = AuditMiddleware(enabled=False)

        with caplog.at_level(logging.INFO):
            await middleware.log_tool_call(
                agent_context=agent_context,
                tool_name="notion.search_pages",
                arguments={},
            )

        assert "AUDIT" not in caplog.text
        assert middleware.get_pending_count() == 0


# =============================================================================
# Module-Level Configuration Tests
# =============================================================================


class TestModuleLevelConfig:
    """Tests for module-level configuration functions."""

    def test_get_creates_default_middleware(self):
        """Should create default middleware if not configured."""
        middleware = get_audit_middleware()
        assert middleware is not None
        assert isinstance(middleware, AuditMiddleware)

    def test_configure_sets_middleware(self):
        """Should configure the singleton middleware."""
        middleware = configure_audit_middleware(
            control_plane_url="http://localhost:9000",
            timeout_seconds=10.0,
            enabled=True,
        )

        assert middleware.control_plane_url == "http://localhost:9000"
        assert middleware.timeout_seconds == 10.0
        assert middleware.enabled is True

        # Get should return same instance
        assert get_audit_middleware() is middleware

    def test_reset_clears_middleware(self):
        """Should reset the singleton."""
        configure_audit_middleware(control_plane_url="http://test")
        reset_audit_middleware()

        # Should create new default
        middleware = get_audit_middleware()
        assert middleware.control_plane_url is None


class TestConvenienceFunctions:
    """Tests for convenience functions."""

    @pytest.mark.asyncio
    async def test_log_tool_call_function(
        self, agent_context: AgentContext, caplog
    ):
        """Should use configured middleware."""
        with caplog.at_level(logging.INFO):
            await log_tool_call(
                agent_context=agent_context,
                tool_name="notion.search_pages",
                arguments={"query": "test"},
            )

            # Wait for async
            middleware = get_audit_middleware()
            await middleware.flush()

        assert "AUDIT" in caplog.text

    @pytest.mark.asyncio
    async def test_log_permission_denied_function(
        self, agent_context: AgentContext, caplog
    ):
        """Should use configured middleware for permission denied."""
        with caplog.at_level(logging.WARNING):
            await log_permission_denied(
                agent_context=agent_context,
                tool_name="notion.create_page",
                required_permission="notion:pages:create",
                denial_reason="not_delegated",
            )

            middleware = get_audit_middleware()
            await middleware.flush()

        assert "AUDIT" in caplog.text
        assert "permission_denied" in caplog.text
