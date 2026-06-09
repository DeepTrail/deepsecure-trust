"""Tests for JWTManager — token lifecycle and refresh logic."""

from __future__ import annotations

import time
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from deepsecure_proxy.jwt_manager import JWTManager
from .conftest import FakeBootstrapResult


class TestEnsureDiscoveryJWT:
    @pytest.mark.asyncio
    async def test_first_call_bootstraps(self, mock_bootstrap_client):
        mgr = JWTManager(mock_bootstrap_client, agent_id="agent-1")
        jwt = await mgr.ensure_discovery_jwt()

        assert jwt == "fake-discovery-jwt"
        mock_bootstrap_client.bootstrap.assert_called_once_with(
            agent_id="agent-1", platform="auto"
        )

    @pytest.mark.asyncio
    async def test_cached_jwt_returned(self, mock_bootstrap_client):
        mgr = JWTManager(mock_bootstrap_client, agent_id="agent-1")
        await mgr.ensure_discovery_jwt()
        await mgr.ensure_discovery_jwt()

        assert mock_bootstrap_client.bootstrap.call_count == 1

    @pytest.mark.asyncio
    async def test_refresh_when_near_expiry(self, mock_bootstrap_client):
        mgr = JWTManager(
            mock_bootstrap_client, agent_id="agent-1", refresh_margin=300
        )
        await mgr.ensure_discovery_jwt()
        mgr._discovery_expires_at = time.time() + 100  # within margin

        await mgr.ensure_discovery_jwt()
        assert mock_bootstrap_client.bootstrap.call_count == 2

    @pytest.mark.asyncio
    async def test_no_refresh_when_far_from_expiry(self, mock_bootstrap_client):
        mgr = JWTManager(
            mock_bootstrap_client, agent_id="agent-1", refresh_margin=300
        )
        await mgr.ensure_discovery_jwt()
        mgr._discovery_expires_at = time.time() + 3600

        await mgr.ensure_discovery_jwt()
        assert mock_bootstrap_client.bootstrap.call_count == 1


class TestGetDelegationJWT:
    @pytest.mark.asyncio
    async def test_fetches_delegation_token(self, mock_bootstrap_client):
        mgr = JWTManager(mock_bootstrap_client, agent_id="agent-1")

        mock_response = MagicMock()
        mock_response.json.return_value = {
            "access_token": "delegation-jwt-abc",
            "expires_in": 3600,
        }
        mock_response.raise_for_status = MagicMock()

        with patch("deepsecure_proxy.jwt_manager.httpx.AsyncClient") as MockClient:
            instance = AsyncMock()
            instance.post.return_value = mock_response
            instance.__aenter__ = AsyncMock(return_value=instance)
            instance.__aexit__ = AsyncMock(return_value=False)
            MockClient.return_value = instance

            jwt = await mgr.get_delegation_jwt("deleg-1")

        assert jwt == "delegation-jwt-abc"
        instance.post.assert_called_once()

    @pytest.mark.asyncio
    async def test_cached_delegation_jwt(self, mock_bootstrap_client):
        mgr = JWTManager(mock_bootstrap_client, agent_id="agent-1")
        mgr._delegation_jwt = "cached-jwt"
        mgr._current_delegation_id = "deleg-1"
        mgr._delegation_expires_at = time.time() + 3600

        jwt = await mgr.get_delegation_jwt("deleg-1")
        assert jwt == "cached-jwt"

    @pytest.mark.asyncio
    async def test_different_delegation_refetches(self, mock_bootstrap_client):
        mgr = JWTManager(mock_bootstrap_client, agent_id="agent-1")
        mgr._delegation_jwt = "old-jwt"
        mgr._current_delegation_id = "deleg-1"
        mgr._delegation_expires_at = time.time() + 3600

        mock_response = MagicMock()
        mock_response.json.return_value = {
            "access_token": "new-deleg-jwt",
            "expires_in": 3600,
        }
        mock_response.raise_for_status = MagicMock()

        with patch("deepsecure_proxy.jwt_manager.httpx.AsyncClient") as MockClient:
            instance = AsyncMock()
            instance.post.return_value = mock_response
            instance.__aenter__ = AsyncMock(return_value=instance)
            instance.__aexit__ = AsyncMock(return_value=False)
            MockClient.return_value = instance

            jwt = await mgr.get_delegation_jwt("deleg-2")

        assert jwt == "new-deleg-jwt"


class TestInvalidate:
    @pytest.mark.asyncio
    async def test_invalidate_forces_refetch(self, mock_bootstrap_client):
        mgr = JWTManager(mock_bootstrap_client, agent_id="agent-1")
        await mgr.ensure_discovery_jwt()
        mgr.invalidate()

        assert mgr._discovery_jwt is None
        assert mgr._delegation_jwt is None

        await mgr.ensure_discovery_jwt()
        assert mock_bootstrap_client.bootstrap.call_count == 2
