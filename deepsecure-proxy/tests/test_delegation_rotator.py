"""Tests for DelegationRotator — round-robin delegation cycling."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from deepsecure_proxy.delegation_rotator import DelegationRotator


class TestDelegationRotator:
    @pytest.mark.asyncio
    async def test_refresh_loads_delegations(self, mock_bootstrap_client):
        rotator = DelegationRotator(mock_bootstrap_client, agent_id="agent-1")

        delegations = [
            {"delegation_id": "d1", "permissions": ["github:repo:read"]},
            {"delegation_id": "d2", "permissions": ["notion:page:read"]},
        ]
        mock_response = MagicMock()
        mock_response.json.return_value = delegations
        mock_response.raise_for_status = MagicMock()

        with patch("deepsecure_proxy.delegation_rotator.httpx.AsyncClient") as MockClient:
            instance = AsyncMock()
            instance.get.return_value = mock_response
            instance.__aenter__ = AsyncMock(return_value=instance)
            instance.__aexit__ = AsyncMock(return_value=False)
            MockClient.return_value = instance

            await rotator.refresh_delegations("discovery-jwt")

        assert rotator.count == 2
        assert rotator.current["delegation_id"] == "d1"

    def test_rotate_cycles(self, mock_bootstrap_client):
        rotator = DelegationRotator(mock_bootstrap_client, agent_id="agent-1")
        rotator._delegations = [
            {"delegation_id": "d1"},
            {"delegation_id": "d2"},
            {"delegation_id": "d3"},
        ]
        rotator._index = 0

        assert rotator.current["delegation_id"] == "d1"
        rotator.rotate()
        assert rotator.current["delegation_id"] == "d2"
        rotator.rotate()
        assert rotator.current["delegation_id"] == "d3"
        rotator.rotate()
        assert rotator.current["delegation_id"] == "d1"

    def test_rotate_empty_returns_none(self, mock_bootstrap_client):
        rotator = DelegationRotator(mock_bootstrap_client, agent_id="agent-1")
        assert rotator.current is None
        assert rotator.rotate() is None

    def test_count_empty(self, mock_bootstrap_client):
        rotator = DelegationRotator(mock_bootstrap_client, agent_id="agent-1")
        assert rotator.count == 0
