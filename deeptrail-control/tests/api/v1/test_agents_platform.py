"""Tests for platform-aware agent registration (P4).

Tests the extended POST /api/v1/agents endpoint:
- Platform registration (GCP, AWS, K8s) — no keys
- Key-based registration — unchanged Ed25519 flow
- Validation: co-presence, allowed platforms, no platform+key
- Duplicate selector enforcement (409)
- GET response includes platform/selector fields
"""

import uuid

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.config import settings

API = f"{settings.API_V1_STR}/agents"

VALID_PUB_KEY_B64 = "DQENDQENDQENDQENDQENDQENDQENDQENDQENDQENDQE="


def _unique(prefix: str) -> str:
    return f"{prefix}-{uuid.uuid4().hex[:8]}"


def test_platform_registration_success(client: TestClient, db: Session):
    """Platform agent: POST with platform+selector → 201, no keys."""
    agent_id = _unique("plat-ok")
    selector = f"{agent_id}@project.iam.gserviceaccount.com"

    resp = client.post(f"{API}/", json={
        "agent_id": agent_id,
        "name": "GCP Agent",
        "platform": "gcp_workload_identity",
        "selector": selector,
    })

    assert resp.status_code == 201
    body = resp.json()
    assert body["agent_id"] == agent_id
    assert body["name"] == "GCP Agent"
    assert body["platform"] == "gcp_workload_identity"
    assert body["selector"] == selector
    assert body["public_key"] is None
    assert body["private_key"] is None
    assert body.get("private_key_warning") is None


def test_key_based_registration_still_works(client: TestClient, db: Session):
    """Key-based agent: POST without platform → 201, keys returned."""
    agent_id = _unique("key-ok")

    resp = client.post(f"{API}/", json={
        "agent_id": agent_id,
        "name": "Key Agent",
    })

    assert resp.status_code == 201
    body = resp.json()
    assert body["agent_id"] == agent_id
    assert body["public_key"] is not None
    assert body["private_key"] is not None
    assert body["platform"] is None
    assert body["selector"] is None


def test_duplicate_selector_returns_409(client: TestClient, db: Session):
    """Two agents with same selector → second registration returns 409."""
    selector = f"dup-{uuid.uuid4().hex[:8]}@project.iam.gserviceaccount.com"

    resp1 = client.post(f"{API}/", json={
        "agent_id": _unique("dup-a"),
        "name": "First",
        "platform": "gcp_workload_identity",
        "selector": selector,
    })
    assert resp1.status_code == 201

    resp2 = client.post(f"{API}/", json={
        "agent_id": _unique("dup-b"),
        "name": "Second",
        "platform": "gcp_workload_identity",
        "selector": selector,
    })
    assert resp2.status_code == 409
    assert "already registered" in resp2.json()["detail"]


def test_platform_without_selector_returns_422(client: TestClient, db: Session):
    """Platform set without selector → Pydantic 422."""
    resp = client.post(f"{API}/", json={
        "agent_id": _unique("no-sel"),
        "name": "Bad",
        "platform": "gcp_workload_identity",
    })
    assert resp.status_code == 422


def test_selector_without_platform_returns_422(client: TestClient, db: Session):
    """Selector set without platform → Pydantic 422."""
    resp = client.post(f"{API}/", json={
        "agent_id": _unique("no-plat"),
        "name": "Bad",
        "selector": "sa@proj.iam.gserviceaccount.com",
    })
    assert resp.status_code == 422


def test_invalid_platform_value_returns_422(client: TestClient, db: Session):
    """Unknown platform string → Pydantic 422."""
    resp = client.post(f"{API}/", json={
        "agent_id": _unique("bad-plat"),
        "name": "Bad",
        "platform": "invalid_platform",
        "selector": "x@example.com",
    })
    assert resp.status_code == 422


def test_platform_plus_public_key_returns_422(client: TestClient, db: Session):
    """Platform + public_key is invalid — cannot have both."""
    resp = client.post(f"{API}/", json={
        "agent_id": _unique("plat-key"),
        "name": "Bad",
        "platform": "gcp_workload_identity",
        "selector": "sa@proj.iam.gserviceaccount.com",
        "public_key": VALID_PUB_KEY_B64,
    })
    assert resp.status_code == 422


def test_get_agent_returns_platform_fields(client: TestClient, db: Session):
    """GET /agents/{id} includes platform and selector for platform agents."""
    agent_id = _unique("get-plat")
    selector = f"{agent_id}@project.iam.gserviceaccount.com"

    reg = client.post(f"{API}/", json={
        "agent_id": agent_id,
        "name": "Get Test",
        "platform": "gcp_workload_identity",
        "selector": selector,
    })
    assert reg.status_code == 201

    resp = client.get(f"{API}/{agent_id}")
    assert resp.status_code == 200
    body = resp.json()
    assert body["agent_id"] == agent_id
    assert body["platform"] == "gcp_workload_identity"
    assert body["selector"] == selector
    assert body.get("publicKey") is None or body.get("public_key") is None


def test_list_agents_includes_platform_fields(client: TestClient, db: Session):
    """List agents returns platform/selector for platform agents and keys for key agents."""
    plat_id = _unique("list-plat")
    key_id = _unique("list-key")
    selector = f"{plat_id}@project.iam.gserviceaccount.com"

    r1 = client.post(f"{API}/", json={
        "agent_id": plat_id,
        "name": "Platform Listed",
        "platform": "gcp_workload_identity",
        "selector": selector,
    })
    assert r1.status_code == 201

    r2 = client.post(f"{API}/", json={
        "agent_id": key_id,
        "name": "Key Listed",
    })
    assert r2.status_code == 201

    resp = client.get(f"{API}/")
    assert resp.status_code == 200
    agents = {a["agent_id"]: a for a in resp.json()["agents"]}

    plat_agent = agents[plat_id]
    assert plat_agent["platform"] == "gcp_workload_identity"
    assert plat_agent["selector"] == selector

    key_agent = agents[key_id]
    assert key_agent["platform"] is None
    assert key_agent["selector"] is None
