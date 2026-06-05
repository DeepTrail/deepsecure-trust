"""Tests for admin service catalog endpoints (WS-B2, B3, B5)."""

import os

import pytest
from cryptography.fernet import Fernet
from fastapi.testclient import TestClient

from app.main import app as fastapi_app
from app.api.deps import get_db
from app.core import kms as kms_mod
from app.middleware.admin_auth import require_admin


@pytest.fixture(autouse=True)
def _ensure_fernet(monkeypatch):
    """Ensure KMS has a Fernet backend for tests that encrypt."""
    key = Fernet.generate_key().decode()
    monkeypatch.setenv("FERNET_KEY", key)
    kms_mod.reset_kms_client()
    yield
    kms_mod.reset_kms_client()


@pytest.fixture()
def client(db):
    def _override_db():
        yield db

    def _override_admin():
        return {"sub": "admin@test.com", "roles": ["admin"]}

    fastapi_app.dependency_overrides[get_db] = _override_db
    fastapi_app.dependency_overrides[require_admin] = _override_admin
    yield TestClient(fastapi_app)
    fastapi_app.dependency_overrides.clear()


def test_create_service(client):
    resp = client.post("/api/v1/admin/services", json={
        "service_id": "notion",
        "display_name": "Notion",
        "backend_type": "rest",
        "endpoint_url": "https://api.notion.com",
    })
    assert resp.status_code == 201
    data = resp.json()
    assert data["service_id"] == "notion"
    assert data["status"] == "active"


def test_create_duplicate_service(client):
    client.post("/api/v1/admin/services", json={
        "service_id": "dup", "display_name": "Dup", "backend_type": "rest", "endpoint_url": "http://dup",
    })
    resp = client.post("/api/v1/admin/services", json={
        "service_id": "dup", "display_name": "Dup2", "backend_type": "rest", "endpoint_url": "http://dup2",
    })
    assert resp.status_code == 409


def test_list_services(client):
    client.post("/api/v1/admin/services", json={
        "service_id": "a", "display_name": "A", "backend_type": "rest", "endpoint_url": "http://a",
    })
    client.post("/api/v1/admin/services", json={
        "service_id": "b", "display_name": "B", "backend_type": "mcp", "endpoint_url": "http://b",
    })
    resp = client.get("/api/v1/admin/services")
    assert resp.status_code == 200
    assert len(resp.json()) >= 2


def test_list_services_with_filter(client):
    client.post("/api/v1/admin/services", json={
        "service_id": "r1", "display_name": "R1", "backend_type": "rest", "endpoint_url": "http://r1",
    })
    client.post("/api/v1/admin/services", json={
        "service_id": "m1", "display_name": "M1", "backend_type": "mcp", "endpoint_url": "http://m1",
    })
    resp = client.get("/api/v1/admin/services?backend_type=mcp")
    assert resp.status_code == 200
    services = [s for s in resp.json() if s["backend_type"] == "mcp"]
    assert len(services) >= 1


def test_update_service(client):
    client.post("/api/v1/admin/services", json={
        "service_id": "up", "display_name": "Before", "backend_type": "rest", "endpoint_url": "http://up",
    })
    resp = client.patch("/api/v1/admin/services/up", json={"display_name": "After"})
    assert resp.status_code == 200
    assert resp.json()["display_name"] == "After"


def test_update_nonexistent_service(client):
    resp = client.patch("/api/v1/admin/services/nope", json={"display_name": "X"})
    assert resp.status_code == 404


def test_delete_service(client):
    client.post("/api/v1/admin/services", json={
        "service_id": "del-svc", "display_name": "Del", "backend_type": "rest", "endpoint_url": "http://del",
    })
    resp = client.delete("/api/v1/admin/services/del-svc")
    assert resp.status_code == 204


def test_delete_nonexistent_service(client):
    resp = client.delete("/api/v1/admin/services/nope")
    assert resp.status_code == 404


def test_test_connection(client):
    client.post("/api/v1/admin/services", json={
        "service_id": "tc", "display_name": "TC", "backend_type": "rest", "endpoint_url": "http://tc",
    })
    resp = client.post("/api/v1/admin/services/tc/test")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] in ("success", "error")
    assert "message" in data


def test_test_connection_mcp(client):
    """MCP backends should send JSON-RPC initialize, not plain GET."""
    client.post("/api/v1/admin/services", json={
        "service_id": "mcp-tc",
        "display_name": "MCP TC",
        "backend_type": "mcp",
        "endpoint_url": "http://localhost:9999",
    })
    resp = client.post("/api/v1/admin/services/mcp-tc/test")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] in ("success", "error")
    assert "message" in data


def test_set_and_get_oauth(client):
    client.post("/api/v1/admin/services", json={
        "service_id": "oauth-svc", "display_name": "OAuth", "backend_type": "rest", "endpoint_url": "http://oauth",
    })
    resp = client.put("/api/v1/admin/services/oauth-svc/oauth", json={
        "client_id": "cid",
        "client_secret": "csecret",
        "auth_url": "https://auth",
        "token_url": "https://token",
        "scopes": ["read", "write"],
    })
    assert resp.status_code == 200
    data = resp.json()
    assert data["client_id"] == "cid"
    assert data["client_secret_configured"] is True

    resp = client.get("/api/v1/admin/services/oauth-svc/oauth")
    assert resp.status_code == 200
    assert resp.json()["client_id"] == "cid"


def test_discover_tools_rest_service_rejected(client):
    client.post("/api/v1/admin/services", json={
        "service_id": "rest-svc", "display_name": "REST", "backend_type": "rest", "endpoint_url": "http://rest",
    })
    resp = client.post("/api/v1/admin/services/rest-svc/discover-tools")
    assert resp.status_code == 400


def test_health_summary(client):
    resp = client.get("/api/v1/admin/health")
    assert resp.status_code == 200
    assert "total" in resp.json()
