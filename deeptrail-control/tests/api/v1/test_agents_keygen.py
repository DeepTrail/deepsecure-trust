"""Tests for modified POST /api/v1/agents/ with backend key generation."""

import base64

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.config import settings

VALID_PUB_KEY_B64 = "EBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBA="


def test_register_agent_with_provided_key(client: TestClient, db: Session):
    """Test agent registration with user-provided public key (backward compatible)."""
    data = {
        "agent_id": "keygen-test-provided",
        "name": "Test Agent",
        "public_key": VALID_PUB_KEY_B64,
    }

    response = client.post(f"{settings.API_V1_STR}/agents/", json=data)
    assert response.status_code == 201

    content = response.json()
    assert content["agent_id"] == "keygen-test-provided"
    assert content["name"] == "Test Agent"
    assert content["public_key"] == VALID_PUB_KEY_B64
    # Should NOT have private_key when user provides key
    assert content.get("private_key") is None
    assert content.get("private_key_warning") is None


def test_register_agent_backend_generates_keypair(client: TestClient, db: Session):
    """Test agent registration without public_key triggers backend key generation."""
    data = {
        "agent_id": "keygen-test-generated",
        "name": "Generated Key Agent",
    }

    response = client.post(f"{settings.API_V1_STR}/agents/", json=data)
    assert response.status_code == 201

    content = response.json()
    assert content["agent_id"] == "keygen-test-generated"
    assert content["name"] == "Generated Key Agent"

    # Should have public_key
    assert content["public_key"] is not None
    pub_key_bytes = base64.b64decode(content["public_key"])
    assert len(pub_key_bytes) == 32

    # Should have private_key (only for backend-generated)
    assert content["private_key"] is not None
    priv_key_bytes = base64.b64decode(content["private_key"])
    assert len(priv_key_bytes) == 32

    # Should have warning
    assert content["private_key_warning"] is not None
    assert "not be shown again" in content["private_key_warning"]


def test_register_agent_generated_key_is_valid_ed25519(client: TestClient, db: Session):
    """Test that backend-generated keypair is a valid Ed25519 pair."""
    from nacl.signing import SigningKey, VerifyKey

    data = {
        "agent_id": "keygen-test-valid",
        "name": "Crypto Validation Agent",
    }

    response = client.post(f"{settings.API_V1_STR}/agents/", json=data)
    assert response.status_code == 201

    content = response.json()
    priv_key_bytes = base64.b64decode(content["private_key"])
    pub_key_bytes = base64.b64decode(content["public_key"])

    # Verify the keys are a matching pair
    signing_key = SigningKey(priv_key_bytes)
    assert signing_key.verify_key.encode() == pub_key_bytes

    # Verify we can sign and verify with the generated keys
    message = b"test message"
    signed = signing_key.sign(message)
    verify_key = VerifyKey(pub_key_bytes)
    verify_key.verify(signed.message, signed.signature)


def test_register_agent_generated_key_stored_in_db(client: TestClient, db: Session):
    """Test that only public key is stored in DB (private key never persisted)."""
    from app.models.agent import Agent

    data = {
        "agent_id": "keygen-test-stored",
        "name": "Storage Test Agent",
    }

    response = client.post(f"{settings.API_V1_STR}/agents/", json=data)
    assert response.status_code == 201

    content = response.json()
    pub_key_b64 = content["public_key"]

    # Verify agent in DB has public key but not private key
    db_agent = db.query(Agent).filter(Agent.agent_id == "keygen-test-stored").first()
    assert db_agent is not None
    assert db_agent.public_key == base64.b64decode(pub_key_b64)
    # The Agent model has no private_key column
    assert not hasattr(db_agent, "private_key")


def test_register_agent_no_key_no_id_generates_both(client: TestClient, db: Session):
    """Test agent creation without agent_id or public_key generates both."""
    data = {"name": "Auto-generated Agent"}

    response = client.post(f"{settings.API_V1_STR}/agents/", json=data)
    assert response.status_code == 201

    content = response.json()
    # agent_id should be auto-generated
    assert content["agent_id"].startswith("agent-")
    # Keys should be generated
    assert content["public_key"] is not None
    assert content["private_key"] is not None
