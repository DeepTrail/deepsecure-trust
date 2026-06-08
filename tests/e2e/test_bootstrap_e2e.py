"""End-to-end bootstrap tests against a live backend.

Requires: docker compose up db redis deeptrail-control deeptrail-gateway
Run with: pytest tests/e2e/test_bootstrap_e2e.py -v -m e2e
"""

from __future__ import annotations

import json
import os
import subprocess

import httpx
import pytest

from deepsecure._core.bootstrap import BootstrapClient, Platform

pytestmark = pytest.mark.e2e

CONTROL_URL = os.environ.get("DEEPSECURE_DEEPTRAIL_CONTROL_URL", "http://localhost:8000")
GATEWAY_URL = os.environ.get("DEEPSECURE_DEEPTRAIL_GATEWAY_URL", "http://localhost:8002")


def _backend_reachable() -> bool:
    try:
        resp = httpx.get(f"{CONTROL_URL}/health", timeout=3)
        return resp.status_code == 200
    except Exception:
        return False


@pytest.fixture(autouse=True)
def skip_if_no_backend():
    if not _backend_reachable():
        pytest.skip("Backend not reachable — start with: docker compose up -d")


class TestBootstrapLocalE2E:
    """Test local keyring bootstrap against live control plane.

    Pre-condition: an agent must be registered with a keypair in the OS keyring.
    This is typically done via ``deepsecure agent create --name test-e2e``.
    """

    @pytest.fixture
    def registered_agent(self):
        """Create a test agent and register it, cleaning up afterwards."""
        from deepsecure._core.identity_manager import IdentityManager
        from deepsecure._core.base_client import BaseClient

        user_token = os.environ.get("DEEPSECURE_API_TOKEN")
        if not user_token:
            pytest.skip("DEEPSECURE_API_TOKEN not set — cannot register test agent")

        client = BaseClient(api_url=CONTROL_URL, token=user_token)
        im = IdentityManager(api_client=client, silent_mode=True)

        agent_id = "agent-e2e-bootstrap-test"
        keys = im.create_keypair_for_agent(agent_id)

        try:
            resp = client._request(
                "POST",
                "/api/v1/agents/",
                json={
                    "agent_id": agent_id,
                    "name": "E2E Bootstrap Test",
                    "public_key": keys["public_key"],
                },
            )
        except Exception:
            pass

        yield agent_id

        im.delete_private_key(agent_id)

    def test_local_bootstrap_returns_jwt(self, registered_agent):
        agent_id = registered_agent
        client = BootstrapClient(control_url=CONTROL_URL, gateway_url=GATEWAY_URL)
        result = client.bootstrap(agent_id, Platform.LOCAL, fetch_delegations=False)

        assert result.jwt
        assert result.agent_id == agent_id
        assert result.platform == Platform.LOCAL

    def test_local_bootstrap_mcp_json_valid(self, registered_agent):
        agent_id = registered_agent
        client = BootstrapClient(control_url=CONTROL_URL, gateway_url=GATEWAY_URL)
        result = client.bootstrap(agent_id, Platform.LOCAL, fetch_delegations=False)

        mcp = result.to_mcp_json()
        assert "mcpServers" in mcp
        assert "deepsecure" in mcp["mcpServers"]
        assert mcp["mcpServers"]["deepsecure"]["url"].startswith("http")

    def test_local_bootstrap_env_format(self, registered_agent):
        agent_id = registered_agent
        client = BootstrapClient(control_url=CONTROL_URL, gateway_url=GATEWAY_URL)
        result = client.bootstrap(agent_id, Platform.LOCAL, fetch_delegations=False)

        env = result.to_env()
        assert "export DEEPSECURE_AGENT_JWT=" in env
        assert "export DEEPSECURE_GATEWAY_URL=" in env


class TestBootstrapCLIE2E:
    """Test the CLI entry point end-to-end."""

    def test_cli_help_works(self):
        result = subprocess.run(
            ["python", "-m", "deepsecure", "bootstrap", "--help"],
            capture_output=True,
            text=True,
            timeout=30,
        )
        assert result.returncode == 0
        assert "agent-id" in result.stdout.lower() or "agent_id" in result.stdout.lower()

    def test_cli_invalid_agent_exits_1(self):
        result = subprocess.run(
            [
                "python", "-m", "deepsecure", "bootstrap",
                "--agent-id", "agent-nonexistent-999",
                "--platform", "local",
                "--quiet",
            ],
            capture_output=True,
            text=True,
            timeout=30,
        )
        assert result.returncode != 0
