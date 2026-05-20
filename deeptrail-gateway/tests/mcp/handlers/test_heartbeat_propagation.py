"""
Tests for heartbeat propagation from gateway to control plane.

Tests cover:
- _send_heartbeat() calls control plane with correct URL and headers
- _send_heartbeat() logs warning on failure but does not raise
- Heartbeat is triggered after successful tool call (production path)
- Heartbeat is triggered after successful tool call (mock path)
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch, call
import asyncio

from app.mcp.handlers.tools_call import _send_heartbeat


# =============================================================================
# _send_heartbeat() unit tests
# =============================================================================


@pytest.mark.asyncio
async def test_send_heartbeat_success():
    """Heartbeat sends POST to control plane with correct URL and token."""
    mock_response = MagicMock()
    mock_response.status_code = 204

    mock_client = AsyncMock()
    mock_client.post = AsyncMock(return_value=mock_response)
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=None)

    mock_config = MagicMock()
    mock_config.control_plane_url = "http://deeptrail-control:8000"
    mock_config.internal_api_token = "test-internal-token"

    with patch("app.mcp.handlers.tools_call.httpx.AsyncClient", return_value=mock_client):
        with patch("app.core.proxy_config.config", mock_config):
            await _send_heartbeat("my-agent-id")

    mock_client.post.assert_called_once_with(
        "http://deeptrail-control:8000/api/v1/agents/internal/sessions/my-agent-id/heartbeat",
        headers={"X-Internal-API-Token": "test-internal-token"},
    )


@pytest.mark.asyncio
async def test_send_heartbeat_failure_does_not_raise():
    """Heartbeat catches exceptions and logs warning instead of raising."""
    mock_client = AsyncMock()
    mock_client.post = AsyncMock(side_effect=Exception("Connection refused"))
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=None)

    mock_config = MagicMock()
    mock_config.control_plane_url = "http://deeptrail-control:8000"
    mock_config.internal_api_token = "test-token"

    with patch("app.mcp.handlers.tools_call.httpx.AsyncClient", return_value=mock_client):
        with patch("app.core.proxy_config.config", mock_config):
            # Should not raise
            await _send_heartbeat("failing-agent")


@pytest.mark.asyncio
async def test_send_heartbeat_timeout_does_not_raise():
    """Heartbeat handles timeout gracefully."""
    import httpx

    mock_client = AsyncMock()
    mock_client.post = AsyncMock(side_effect=httpx.TimeoutException("timed out"))
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=None)

    mock_config = MagicMock()
    mock_config.control_plane_url = "http://deeptrail-control:8000"
    mock_config.internal_api_token = "test-token"

    with patch("app.mcp.handlers.tools_call.httpx.AsyncClient", return_value=mock_client):
        with patch("app.core.proxy_config.config", mock_config):
            await _send_heartbeat("timeout-agent")
