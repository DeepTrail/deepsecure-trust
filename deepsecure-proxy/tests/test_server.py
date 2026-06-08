"""Tests for DeepSecureProxy server — stdin/stdout forwarding."""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from deepsecure_proxy.server import DeepSecureProxy


class TestForward:
    @pytest.mark.asyncio
    async def test_forward_adds_bearer_token(self):
        with patch("deepsecure_proxy.server.BootstrapClient") as MockBC:
            mock_bc = MagicMock()
            mock_bc.control_url = "http://localhost:8000"
            mock_bc.gateway_url = "http://localhost:8002"
            MockBC.return_value = mock_bc

            from .conftest import FakeBootstrapResult

            mock_bc.bootstrap.return_value = FakeBootstrapResult()

            proxy = DeepSecureProxy(
                agent_id="agent-1",
                control_url="http://localhost:8000",
                gateway_url="http://localhost:8002",
                platform="local",
            )

            mock_response = MagicMock()
            mock_response.json.return_value = {
                "jsonrpc": "2.0",
                "id": 1,
                "result": {"protocolVersion": "2024-11-05"},
            }
            mock_response.status_code = 200

            with patch("deepsecure_proxy.server.httpx.AsyncClient") as MockClient:
                instance = AsyncMock()
                instance.post.return_value = mock_response
                instance.__aenter__ = AsyncMock(return_value=instance)
                instance.__aexit__ = AsyncMock(return_value=False)
                MockClient.return_value = instance

                result = await proxy._forward({"jsonrpc": "2.0", "id": 1, "method": "initialize"})

            assert result["result"]["protocolVersion"] == "2024-11-05"
            call_kwargs = instance.post.call_args
            assert "Bearer" in call_kwargs.kwargs["headers"]["Authorization"]

    @pytest.mark.asyncio
    async def test_forward_retries_on_401(self):
        with patch("deepsecure_proxy.server.BootstrapClient") as MockBC:
            mock_bc = MagicMock()
            mock_bc.control_url = "http://localhost:8000"
            mock_bc.gateway_url = "http://localhost:8002"
            MockBC.return_value = mock_bc

            from .conftest import FakeBootstrapResult

            mock_bc.bootstrap.return_value = FakeBootstrapResult()

            proxy = DeepSecureProxy(
                agent_id="agent-1",
                control_url="http://localhost:8000",
                gateway_url="http://localhost:8002",
            )

            resp_401 = MagicMock()
            resp_401.status_code = 401
            resp_401.json.return_value = {"error": "unauthorized"}

            resp_200 = MagicMock()
            resp_200.status_code = 200
            resp_200.json.return_value = {"jsonrpc": "2.0", "id": 1, "result": {}}

            with patch("deepsecure_proxy.server.httpx.AsyncClient") as MockClient:
                instance = AsyncMock()
                instance.post.side_effect = [resp_401, resp_200]
                instance.__aenter__ = AsyncMock(return_value=instance)
                instance.__aexit__ = AsyncMock(return_value=False)
                MockClient.return_value = instance

                result = await proxy._forward({"jsonrpc": "2.0", "id": 1, "method": "tools/list"})

            assert result == {"jsonrpc": "2.0", "id": 1, "result": {}}
            assert instance.post.call_count == 2


class TestGetCurrentJWT:
    @pytest.mark.asyncio
    async def test_uses_fixed_delegation_id(self):
        with patch("deepsecure_proxy.server.BootstrapClient") as MockBC:
            mock_bc = MagicMock()
            mock_bc.control_url = "http://localhost:8000"
            mock_bc.gateway_url = "http://localhost:8002"
            MockBC.return_value = mock_bc

            from .conftest import FakeBootstrapResult

            mock_bc.bootstrap.return_value = FakeBootstrapResult()

            proxy = DeepSecureProxy(
                agent_id="agent-1",
                control_url="http://localhost:8000",
                gateway_url="http://localhost:8002",
                delegation_id="fixed-deleg-1",
            )
            proxy._jwt_mgr.get_delegation_jwt = AsyncMock(return_value="deleg-jwt")

            jwt = await proxy._get_current_jwt()
            assert jwt == "deleg-jwt"
            proxy._jwt_mgr.get_delegation_jwt.assert_called_with("fixed-deleg-1")

    @pytest.mark.asyncio
    async def test_falls_back_to_discovery_jwt(self):
        with patch("deepsecure_proxy.server.BootstrapClient") as MockBC:
            mock_bc = MagicMock()
            mock_bc.control_url = "http://localhost:8000"
            mock_bc.gateway_url = "http://localhost:8002"
            MockBC.return_value = mock_bc

            from .conftest import FakeBootstrapResult

            mock_bc.bootstrap.return_value = FakeBootstrapResult()

            proxy = DeepSecureProxy(
                agent_id="agent-1",
                control_url="http://localhost:8000",
                gateway_url="http://localhost:8002",
            )

            jwt = await proxy._get_current_jwt()
            assert jwt == "fake-discovery-jwt"
