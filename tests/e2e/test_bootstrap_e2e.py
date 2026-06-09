"""End-to-end bootstrap tests against a live backend.

Requires: docker compose up db redis deeptrail-control deeptrail-gateway
Run with: pytest tests/e2e/test_bootstrap_e2e.py -v -m e2e
"""

from __future__ import annotations

import base64
import json
import os
import subprocess

import httpx
import pytest

from deepsecure._core.bootstrap import BootstrapClient, BootstrapResult, Platform

pytestmark = pytest.mark.e2e

CONTROL_URL = os.environ.get(
    "DEEPSECURE_DEEPTRAIL_CONTROL_URL", "http://localhost:8000"
)
GATEWAY_URL = os.environ.get(
    "DEEPSECURE_DEEPTRAIL_GATEWAY_URL", "http://localhost:8002"
)

AGENT_ID = "agent-e2e-bootstrap-test"


def _backend_reachable() -> bool:
    try:
        resp = httpx.get(f"{CONTROL_URL}/health", timeout=3)
        return resp.status_code == 200
    except Exception:
        return False


def _get_user_token() -> str:
    """Login and return user token."""
    resp = httpx.post(
        f"{CONTROL_URL}/api/v1/auth/login",
        json={"email": "admin@example.com", "password": "admin"},
        timeout=10,
    )
    resp.raise_for_status()
    return resp.json()["token"]


def _register_agent_with_keypair(user_token: str, agent_id: str):
    """Generate Ed25519 keypair, register agent, store key in keyring.

    If the agent already exists, delete it first so the new keypair is
    registered.  Returns (public_key_b64, private_key_b64).
    """
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

    private_key = Ed25519PrivateKey.generate()
    private_bytes = private_key.private_bytes_raw()
    public_bytes = private_key.public_key().public_bytes_raw()

    private_key_b64 = base64.b64encode(private_bytes).decode()
    public_key_b64 = base64.b64encode(public_bytes).decode()

    headers = {"Authorization": f"Bearer {user_token}"}

    httpx.delete(
        f"{CONTROL_URL}/api/v1/agents/{agent_id}",
        headers=headers,
        timeout=10,
    )

    resp = httpx.post(
        f"{CONTROL_URL}/api/v1/agents",
        json={
            "agent_id": agent_id,
            "name": "E2E Bootstrap Test Agent",
            "public_key": public_key_b64,
        },
        headers=headers,
        timeout=10,
    )
    resp.raise_for_status()

    import keyring
    from deepsecure._core.identity_provider import _get_keyring_service_name_for_agent

    service = _get_keyring_service_name_for_agent(agent_id)
    keyring.set_password(service, agent_id, private_key_b64)

    return public_key_b64, private_key_b64


def _connect_service_and_delegate(user_token: str, agent_id: str) -> str:
    """Connect a service and create a delegation. Returns delegation_id."""
    httpx.post(
        f"{CONTROL_URL}/api/v1/users/me/services/connect",
        json={
            "service_id": "notion",
            "oauth_token": {
                "access_token": "e2e-test-notion-token",
                "scope": "read_content search",
                "token_type": "bearer",
            },
        },
        headers={"Authorization": f"Bearer {user_token}"},
        timeout=10,
    )

    resp = httpx.post(
        f"{CONTROL_URL}/api/v1/auth/delegate",
        json={
            "agent_id": agent_id,
            "permissions": ["notion:pages:search", "notion:pages:read"],
        },
        headers={"Authorization": f"Bearer {user_token}"},
        timeout=10,
    )
    resp.raise_for_status()
    return resp.json()["delegation_id"]


def _cleanup_keyring(agent_id: str):
    try:
        import keyring
        from deepsecure._core.identity_provider import (
            _get_keyring_service_name_for_agent,
        )

        service = _get_keyring_service_name_for_agent(agent_id)
        keyring.delete_password(service, agent_id)
    except Exception:
        pass


@pytest.fixture(autouse=True)
def skip_if_no_backend():
    if not _backend_reachable():
        pytest.skip("Backend not reachable — start with: docker compose up -d")


@pytest.fixture(scope="module")
def setup_agent_and_delegation():
    """Module-scoped fixture: register agent, create delegation, yield info."""
    if not _backend_reachable():
        pytest.skip("Backend not reachable")

    user_token = _get_user_token()
    pub_key, priv_key = _register_agent_with_keypair(user_token, AGENT_ID)

    try:
        delegation_id = _connect_service_and_delegate(user_token, AGENT_ID)
    except Exception:
        delegation_id = None

    yield {
        "agent_id": AGENT_ID,
        "user_token": user_token,
        "delegation_id": delegation_id,
    }

    _cleanup_keyring(AGENT_ID)


class TestBootstrapLocalE2E:
    """Test local keyring bootstrap against live control + gateway."""

    def test_bootstrap_returns_jwt(self, setup_agent_and_delegation):
        info = setup_agent_and_delegation
        client = BootstrapClient(control_url=CONTROL_URL, gateway_url=GATEWAY_URL)
        result = client.bootstrap(
            info["agent_id"], Platform.LOCAL, fetch_delegations=False
        )

        assert result.jwt, "JWT must be non-empty"
        assert result.agent_id == info["agent_id"]
        assert result.platform == Platform.LOCAL

    def test_bootstrap_mcp_json_no_double_mcp(self, setup_agent_and_delegation):
        info = setup_agent_and_delegation
        client = BootstrapClient(
            control_url=CONTROL_URL, gateway_url=GATEWAY_URL
        )
        result = client.bootstrap(
            info["agent_id"], Platform.LOCAL, fetch_delegations=False
        )

        mcp = result.to_mcp_json()
        url = mcp["mcpServers"]["deepsecure"]["url"]
        assert url.endswith("/mcp"), f"URL should end with /mcp, got {url}"
        assert "/mcp/mcp" not in url, f"Double /mcp in URL: {url}"

    def test_bootstrap_env_format(self, setup_agent_and_delegation):
        info = setup_agent_and_delegation
        client = BootstrapClient(control_url=CONTROL_URL, gateway_url=GATEWAY_URL)
        result = client.bootstrap(
            info["agent_id"], Platform.LOCAL, fetch_delegations=False
        )
        env = result.to_env()
        assert "export DEEPSECURE_AGENT_JWT=" in env
        assert "export DEEPSECURE_GATEWAY_URL=" in env
        assert "export DEEPSECURE_CONTROL_URL=" in env

    def test_jwt_can_mcp_initialize(self, setup_agent_and_delegation):
        """Prove the JWT works against the MCP gateway."""
        info = setup_agent_and_delegation
        client = BootstrapClient(control_url=CONTROL_URL, gateway_url=GATEWAY_URL)
        result = client.bootstrap(
            info["agent_id"], Platform.LOCAL, fetch_delegations=False
        )

        resp = httpx.post(
            f"{GATEWAY_URL}/mcp",
            json={
                "jsonrpc": "2.0",
                "id": 1,
                "method": "initialize",
                "params": {
                    "protocolVersion": "2024-11-05",
                    "capabilities": {},
                    "clientInfo": {"name": "e2e-test", "version": "1.0.0"},
                },
            },
            headers={"Authorization": f"Bearer {result.jwt}"},
            timeout=10,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "result" in data
        assert data["result"]["protocolVersion"] == "2024-11-05"

    def test_jwt_can_list_tools(self, setup_agent_and_delegation):
        """After initialize, tools/list returns delegated tools."""
        info = setup_agent_and_delegation
        client = BootstrapClient(control_url=CONTROL_URL, gateway_url=GATEWAY_URL)
        result = client.bootstrap(
            info["agent_id"], Platform.LOCAL, fetch_delegations=False
        )

        headers = {"Authorization": f"Bearer {result.jwt}"}

        httpx.post(
            f"{GATEWAY_URL}/mcp",
            json={
                "jsonrpc": "2.0",
                "id": 1,
                "method": "initialize",
                "params": {
                    "protocolVersion": "2024-11-05",
                    "capabilities": {},
                    "clientInfo": {"name": "e2e-test", "version": "1.0.0"},
                },
            },
            headers=headers,
            timeout=10,
        )

        resp = httpx.post(
            f"{GATEWAY_URL}/mcp",
            json={"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}},
            headers=headers,
            timeout=10,
        )
        assert resp.status_code == 200
        data = resp.json()
        tools = data.get("result", {}).get("tools", [])
        assert len(tools) > 0, "Expected at least 1 tool from delegation"
        tool_names = [t["name"] for t in tools]
        assert any(
            "notion" in name for name in tool_names
        ), f"Expected Notion tool, got: {tool_names}"


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

    def test_cli_jwt_output(self, setup_agent_and_delegation):
        info = setup_agent_and_delegation
        result = subprocess.run(
            [
                "python", "-m", "deepsecure", "bootstrap",
                "-a", info["agent_id"],
                "--platform", "local",
                "-o", "jwt",
                "--control-url", CONTROL_URL,
                "--gateway-url", GATEWAY_URL,
            ],
            capture_output=True,
            text=True,
            timeout=30,
        )
        assert result.returncode == 0
        jwt_line = result.stdout.strip().split("\n")[-1]
        assert jwt_line.startswith("eyJ"), f"Expected JWT, got: {jwt_line[:40]}"

    def test_cli_mcp_json_output(self, setup_agent_and_delegation):
        info = setup_agent_and_delegation
        result = subprocess.run(
            [
                "python", "-m", "deepsecure", "bootstrap",
                "-a", info["agent_id"],
                "--platform", "local",
                "-o", "mcp-json",
                "--control-url", CONTROL_URL,
                "--gateway-url", GATEWAY_URL,
            ],
            capture_output=True,
            text=True,
            timeout=30,
        )
        assert result.returncode == 0
        stdout = result.stdout
        start = stdout.find('{\n  "mcpServers"')
        if start == -1:
            start = stdout.find('{"mcpServers"')
        assert start != -1, f"mcpServers JSON not found in stdout: {stdout[:300]}"
        mcp_json = json.loads(stdout[start:])
        assert "mcpServers" in mcp_json
        assert "deepsecure" in mcp_json["mcpServers"]

    def test_cli_env_output(self, setup_agent_and_delegation):
        info = setup_agent_and_delegation
        result = subprocess.run(
            [
                "python", "-m", "deepsecure", "bootstrap",
                "-a", info["agent_id"],
                "--platform", "local",
                "-o", "env",
                "--control-url", CONTROL_URL,
                "--gateway-url", GATEWAY_URL,
            ],
            capture_output=True,
            text=True,
            timeout=30,
        )
        assert result.returncode == 0
        assert "export DEEPSECURE_AGENT_JWT=" in result.stdout

    def test_cli_invalid_agent_exits_nonzero(self):
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


class TestProxyStdioE2E:
    """Test the deepsecure-proxy in stdio mode against live backend."""

    def test_proxy_initialize(self, setup_agent_and_delegation):
        info = setup_agent_and_delegation
        stdin_data = json.dumps({
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {
                "protocolVersion": "2024-11-05",
                "capabilities": {},
                "clientInfo": {"name": "proxy-e2e", "version": "1.0.0"},
            },
        })

        result = subprocess.run(
            [
                "deepsecure-proxy",
                "-a", info["agent_id"],
                "--control-url", CONTROL_URL,
                "--gateway-url", GATEWAY_URL,
                "-p", "local",
            ],
            input=stdin_data,
            capture_output=True,
            text=True,
            timeout=15,
        )
        assert result.returncode == 0, f"Proxy failed: {result.stderr}"

        stdout_lines = [
            l for l in result.stdout.strip().split("\n")
            if l.strip().startswith("{")
        ]
        assert stdout_lines, f"No JSON response on stdout: {result.stdout[:200]}"
        resp = json.loads(stdout_lines[0])
        assert "result" in resp
        assert resp["result"]["protocolVersion"] == "2024-11-05"
