"""Tests for SDK step-up auth flow (E3)."""

from unittest.mock import patch

import httpx
import pytest

from deepsecure._core.base_client import BaseClient


class TestWWWAuthenticateParsing:
    def test_parse_scopes(self):
        header = (
            'Bearer error="insufficient_scope", '
            'scope="mcp:notion:pages:search mcp:notion:pages:create"'
        )
        scopes = BaseClient._parse_www_authenticate_scopes(header)
        assert scopes == ["mcp:notion:pages:search", "mcp:notion:pages:create"]

    def test_empty_when_no_scope(self):
        assert BaseClient._parse_www_authenticate_scopes('Bearer error="unauthorized"') == []


class TestGatewayRequestWithStepUp:
    def test_retries_on_insufficient_scope(self):
        client = BaseClient(token="test-token")
        client._access_token = "jwt-1"
        client._token_expires_at = None

        forbidden = httpx.Response(
            403,
            headers={
                "WWW-Authenticate": (
                    'Bearer error="insufficient_scope", '
                    'scope="mcp:notion:pages:create"'
                )
            },
            request=httpx.Request("POST", "http://localhost:8002/mcp"),
        )
        success = httpx.Response(
            200,
            json={"ok": True},
            request=httpx.Request("POST", "http://localhost:8002/mcp"),
        )

        with patch.object(
            client, "_authenticated_request", side_effect=[forbidden, success]
        ) as mock_auth, patch.object(client, "get_access_token", return_value="jwt-2"):
            response = client.gateway_request_with_step_up(
                "POST", "/mcp", agent_id="agent-1", json={}
            )

        assert response.status_code == 200
        assert mock_auth.call_count == 2
        assert client._step_up_retry_count == 1
        assert "mcp:notion:pages:create" in client._cumulative_oauth_scopes

    def test_stops_after_max_retries(self):
        client = BaseClient(token="test-token")
        client._access_token = "jwt-1"
        client._max_step_up_retries = 1

        forbidden = httpx.Response(
            403,
            headers={
                "WWW-Authenticate": (
                    'Bearer error="insufficient_scope", scope="mcp:tools"'
                )
            },
            request=httpx.Request("POST", "http://localhost:8002/mcp"),
        )

        with patch.object(
            client, "_authenticated_request", return_value=forbidden
        ), patch.object(client, "get_access_token", return_value="jwt-2"):
            with pytest.raises(httpx.HTTPStatusError):
                client.gateway_request_with_step_up(
                    "POST", "/mcp", agent_id="agent-1", json={}
                )

        assert client._step_up_retry_count == 1
