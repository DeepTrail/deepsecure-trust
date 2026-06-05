"""Tests for MCP Mcp-Method header validation (WS-B4)."""

import json
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient
from jose import jwt as jose_jwt

from app.mcp.header_validation import mcp_method_header_mismatch


class TestMcpMethodHeaderMismatchHelper:
    def test_no_header_no_mismatch(self):
        assert mcp_method_header_mismatch(None, "tools/list") is False

    def test_no_body_method_no_mismatch(self):
        assert mcp_method_header_mismatch("tools/list", None) is False

    def test_matching_methods(self):
        assert mcp_method_header_mismatch("tools/list", "tools/list") is False

    def test_mismatch(self):
        assert mcp_method_header_mismatch("tools/list", "tools/call") is True

    def test_strips_whitespace(self):
        assert mcp_method_header_mismatch(" tools/list ", "tools/list") is False


class TestMcpEndpointHeaderValidation:
    """Integration tests against POST /mcp."""

    @pytest.fixture
    def client(self):
        from app.main import app

        return TestClient(app)

    @pytest.fixture
    def agent_token(self):
        from datetime import datetime, timedelta, timezone

        now = datetime.now(timezone.utc)
        payload = {
            "sub": "agent-header-test",
            "owner": "test@example.com",
            "delegated_permissions": ["notion:pages:search"],
            "delegation_id": "del-header-test",
            "session_id": "asess-header-test",
            "iss": "deeptrail-control",
            "aud": "deeptrail-gateway",
            "iat": int(now.timestamp()),
            "exp": int((now + timedelta(hours=8)).timestamp()),
        }
        return jose_jwt.encode(payload, "your-secret-key-for-jwt", algorithm="HS256")

    def test_mismatch_returns_400(self, client, agent_token):
        with patch(
            "app.security.session_revocation.SessionRevocationChecker.is_revoked",
            return_value=False,
        ):
            resp = client.post(
                "/mcp",
                headers={
                    "Authorization": f"Bearer {agent_token}",
                    "Mcp-Method": "tools/list",
                },
                json={
                    "jsonrpc": "2.0",
                    "id": 1,
                    "method": "tools/call",
                    "params": {"name": "notion.search_pages", "arguments": {}},
                },
            )
        assert resp.status_code == 400
        body = resp.json()
        assert body["error_code"] == "header_body_mismatch"

    def test_matching_header_not_rejected_as_mismatch(self, client, agent_token):
        """Matching header must not produce the 400 mismatch response."""
        with patch(
            "app.security.session_revocation.SessionRevocationChecker.is_revoked",
            return_value=False,
        ), patch(
            "app.main.mcp_protocol_handler.handle_request",
            side_effect=RuntimeError("passed header gate"),
        ):
            resp = client.post(
                "/mcp",
                headers={
                    "Authorization": f"Bearer {agent_token}",
                    "Mcp-Method": "tools/list",
                },
                json={
                    "jsonrpc": "2.0",
                    "id": 1,
                    "method": "tools/list",
                    "params": {},
                },
            )
        assert resp.status_code != 400
        assert "header_body_mismatch" not in resp.text

    def test_absent_header_not_rejected_as_mismatch(self, client, agent_token):
        with patch(
            "app.security.session_revocation.SessionRevocationChecker.is_revoked",
            return_value=False,
        ), patch(
            "app.main.mcp_protocol_handler.handle_request",
            side_effect=RuntimeError("passed header gate"),
        ):
            resp = client.post(
                "/mcp",
                headers={"Authorization": f"Bearer {agent_token}"},
                json={
                    "jsonrpc": "2.0",
                    "id": 1,
                    "method": "tools/list",
                    "params": {},
                },
            )
        assert resp.status_code != 400
