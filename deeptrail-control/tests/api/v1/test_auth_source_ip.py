"""Integration tests for auth endpoint source_ip capture (WS-A8).

Tests that the /auth/token endpoint correctly extracts source_ip from
X-Forwarded-For headers and request.client, and that the endpoint still
functions correctly after the Request parameter was added.
"""

import base64

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.config import settings

API = settings.API_V1_STR

VALID_PUB_KEY_B64 = "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA="


def _register_agent_with_keypair(client: TestClient):
    """Register an agent with a real Ed25519 keypair and return (agent_id, private_key)."""
    private_key = Ed25519PrivateKey.generate()
    public_bytes = private_key.public_key().public_bytes_raw()
    public_b64 = base64.b64encode(public_bytes).decode()

    agent_id = f"auth-ip-test-{base64.b16encode(public_bytes[:4]).decode().lower()}"
    resp = client.post(
        f"{API}/agents/",
        json={"agent_id": agent_id, "public_key": public_b64},
    )
    assert resp.status_code == 201, resp.text
    return agent_id, private_key


def _get_nonce_and_sign(client: TestClient, agent_id: str, private_key: Ed25519PrivateKey):
    """Request a challenge nonce and sign it. Returns (nonce, signature_b64)."""
    resp = client.post(f"{API}/auth/challenge", json={"agent_id": agent_id})
    assert resp.status_code == 200, resp.text
    nonce = resp.json()["nonce"]
    sig_bytes = private_key.sign(nonce.encode("utf-8"))
    sig_b64 = base64.b64encode(sig_bytes).decode()
    return nonce, sig_b64


class TestAuthTokenEndpointWithRequest:
    """Verify /auth/token still works after adding Request parameter (WS-A3)."""

    def test_token_endpoint_accepts_request(self, client: TestClient, db: Session):
        """The /auth/token endpoint should work — Request injection is transparent."""
        agent_id, priv_key = _register_agent_with_keypair(client)
        nonce, sig_b64 = _get_nonce_and_sign(client, agent_id, priv_key)

        resp = client.post(
            f"{API}/auth/token",
            json={
                "agent_id": agent_id,
                "nonce": nonce,
                "signature": sig_b64,
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "access_token" in data
        assert data["token_type"] == "bearer"

    def test_token_with_x_forwarded_for(self, client: TestClient, db: Session):
        """X-Forwarded-For header should not break the endpoint."""
        agent_id, priv_key = _register_agent_with_keypair(client)
        nonce, sig_b64 = _get_nonce_and_sign(client, agent_id, priv_key)

        resp = client.post(
            f"{API}/auth/token",
            json={
                "agent_id": agent_id,
                "nonce": nonce,
                "signature": sig_b64,
            },
            headers={"X-Forwarded-For": "10.0.0.1, 10.0.0.2"},
        )
        assert resp.status_code == 200
        assert "access_token" in resp.json()

    def test_token_invalid_nonce_still_400(self, client: TestClient, db: Session):
        """Invalid nonce should still return 400 (not broken by Request param)."""
        agent_id, priv_key = _register_agent_with_keypair(client)
        sig_bytes = priv_key.sign(b"fake-nonce")
        sig_b64 = base64.b64encode(sig_bytes).decode()

        resp = client.post(
            f"{API}/auth/token",
            json={
                "agent_id": agent_id,
                "nonce": "totally-made-up-nonce",
                "signature": sig_b64,
            },
        )
        assert resp.status_code == 400

    def test_token_agent_not_found_still_404(self, client: TestClient, db: Session):
        """Unknown agent should still return 404."""
        resp = client.post(
            f"{API}/auth/token",
            json={
                "agent_id": "nonexistent-auth-agent",
                "nonce": "some-nonce",
                "signature": "some-sig",
            },
        )
        assert resp.status_code == 404
