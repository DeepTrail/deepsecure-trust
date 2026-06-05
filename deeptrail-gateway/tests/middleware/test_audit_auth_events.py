"""
Tests for audit logging of authentication events (WS-D7).
"""

import pytest
from unittest.mock import AsyncMock, patch, MagicMock

from app.middleware.audit import AuditMiddleware, AuditEventType


@pytest.fixture
def audit():
    m = AuditMiddleware(control_plane_url="http://localhost:8000")
    m._send_event_async = AsyncMock()
    return m


class TestAuthAuditEvents:
    @pytest.mark.asyncio
    async def test_log_auth_success(self, audit):
        await audit.log_auth_event(
            AuditEventType.AUTH_SUCCESS,
            agent_id="agent-1",
            owner="alice@test.com",
            token_type="deepsecure",
            success=True,
            method="POST",
            path="/mcp",
        )
        audit._send_event_async.assert_called_once()
        event = audit._send_event_async.call_args[0][0]
        assert event.event_type == AuditEventType.AUTH_SUCCESS
        assert event.agent_id == "agent-1"
        assert event.success is True

    @pytest.mark.asyncio
    async def test_log_auth_failure(self, audit):
        await audit.log_auth_event(
            AuditEventType.AUTH_FAILURE,
            agent_id="",
            token_type="oauth",
            success=False,
            error="Token expired",
            source_ip="10.0.0.1",
            method="POST",
            path="/mcp",
        )
        audit._send_event_async.assert_called_once()
        event = audit._send_event_async.call_args[0][0]
        assert event.event_type == AuditEventType.AUTH_FAILURE
        assert event.success is False
        assert event.error == "Token expired"
        assert event.extra_data["token_type"] == "oauth"
        assert event.extra_data["source_ip"] == "10.0.0.1"

    @pytest.mark.asyncio
    async def test_log_session_created(self, audit):
        await audit.log_auth_event(
            AuditEventType.SESSION_CREATED,
            agent_id="agent-2",
            owner="bob@test.com",
            token_type="deepsecure",
        )
        event = audit._send_event_async.call_args[0][0]
        assert event.event_type == AuditEventType.SESSION_CREATED

    @pytest.mark.asyncio
    async def test_log_mcp_request(self, audit):
        await audit.log_auth_event(
            AuditEventType.MCP_REQUEST,
            agent_id="agent-3",
            method="POST",
            path="/mcp",
        )
        event = audit._send_event_async.call_args[0][0]
        assert event.event_type == AuditEventType.MCP_REQUEST
        assert event.tool == "POST /mcp"

    @pytest.mark.asyncio
    async def test_disabled_audit_skips(self):
        audit = AuditMiddleware(control_plane_url="http://localhost:8000")
        audit.enabled = False
        audit._send_event_async = AsyncMock()
        await audit.log_auth_event(
            AuditEventType.AUTH_SUCCESS,
            agent_id="agent-1",
        )
        audit._send_event_async.assert_not_called()

    def test_event_types_exist(self):
        assert AuditEventType.AUTH_SUCCESS.value == "auth_success"
        assert AuditEventType.AUTH_FAILURE.value == "auth_failure"
        assert AuditEventType.SESSION_CREATED.value == "session_created"
        assert AuditEventType.SESSION_TERMINATED.value == "session_terminated"
        assert AuditEventType.MCP_REQUEST.value == "mcp_request"
