"""Tests for ServiceRegistryService — the business logic layer for the service catalog."""

import uuid
from unittest.mock import MagicMock

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.kms import KMSClient
from app.db.base import Base
from app.models.service_registry import ServiceOAuthConfig, ServiceRegistry
from app.services.service_registry_service import ServiceRegistryService

import app.models.delegation_template  # noqa: ensure table created


@pytest.fixture()
def db():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()


@pytest.fixture()
def kms(monkeypatch):
    from cryptography.fernet import Fernet
    key = Fernet.generate_key().decode()
    monkeypatch.setenv("FERNET_KEY", key)
    monkeypatch.delenv("GOOGLE_CLOUD_PROJECT", raising=False)
    return KMSClient(fernet_key=key)


@pytest.fixture()
def svc(db, kms):
    return ServiceRegistryService(db=db, kms=kms)


# --- CRUD ---


def test_create_and_get_service(svc):
    s = svc.create_service({
        "service_id": "notion",
        "display_name": "Notion",
        "backend_type": "rest",
        "endpoint_url": "https://api.notion.com",
    })
    assert s.service_id == "notion"
    assert svc.get_service("notion") is not None


def test_list_services(svc):
    svc.create_service({"service_id": "a", "display_name": "A", "backend_type": "rest", "endpoint_url": "http://a"})
    svc.create_service({"service_id": "b", "display_name": "B", "backend_type": "mcp", "endpoint_url": "http://b"})
    assert len(svc.list_services()) == 2
    assert len(svc.list_services(backend_type="mcp")) == 1


def test_update_service(svc):
    svc.create_service({"service_id": "x", "display_name": "X", "backend_type": "rest", "endpoint_url": "http://x"})
    updated = svc.update_service("x", {"display_name": "Updated X"})
    assert updated.display_name == "Updated X"


def test_update_nonexistent_returns_none(svc):
    assert svc.update_service("nope", {"display_name": "Y"}) is None


def test_delete_service(svc):
    svc.create_service({"service_id": "d", "display_name": "D", "backend_type": "rest", "endpoint_url": "http://d"})
    assert svc.delete_service("d") is True
    assert svc.get_service("d") is None


def test_delete_nonexistent_returns_false(svc):
    assert svc.delete_service("nope") is False


# --- OAuth Config ---


def test_set_and_get_oauth_config(svc):
    svc.create_service({"service_id": "gh", "display_name": "GitHub", "backend_type": "rest", "endpoint_url": "http://gh"})
    config = svc.set_oauth_config("gh", "client-id", "super-secret")
    assert config.client_id == "client-id"
    assert config.client_secret_encrypted is not None

    fetched = svc.get_oauth_config("gh")
    assert fetched.client_id == "client-id"


def test_set_oauth_config_upsert(svc):
    svc.create_service({"service_id": "sl", "display_name": "Slack", "backend_type": "rest", "endpoint_url": "http://sl"})
    svc.set_oauth_config("sl", "c1", "s1")
    svc.set_oauth_config("sl", "c2", "s2")
    config = svc.get_oauth_config("sl")
    assert config.client_id == "c2"


def test_set_oauth_config_unknown_service(svc):
    with pytest.raises(ValueError, match="not found"):
        svc.set_oauth_config("nope", "c", "s")


# --- KMS Encryption ---


def test_mcp_auth_value_encrypted(svc):
    s = svc.create_service({
        "service_id": "mcp1",
        "display_name": "MCP 1",
        "backend_type": "mcp",
        "endpoint_url": "https://mcp.example.com",
        "mcp_auth_value": "secret-token-123",
    })
    assert s.mcp_auth_value_encrypted is not None
    assert s.mcp_auth_value_encrypted != "secret-token-123"


# --- Internal Gateway API ---


def test_get_registry_for_gateway(svc):
    svc.create_service({
        "service_id": "active-svc",
        "display_name": "Active",
        "backend_type": "rest",
        "endpoint_url": "http://active",
        "status": "active",
    })
    svc.create_service({
        "service_id": "sandbox-svc",
        "display_name": "Sandbox",
        "backend_type": "rest",
        "endpoint_url": "http://sandbox",
        "status": "sandbox",
    })
    registry = svc.get_registry_for_gateway()
    assert len(registry) == 1
    assert registry[0]["service_id"] == "active-svc"


# --- Health ---


def test_update_health(svc):
    svc.create_service({
        "service_id": "h1",
        "display_name": "H1",
        "backend_type": "rest",
        "endpoint_url": "http://h1",
    })
    updated = svc.update_health("h1", "up", latency_ms=42)
    assert updated.health_status == "up"
    assert updated.health_latency_ms == 42


def test_health_summary(svc):
    svc.create_service({
        "service_id": "s1", "display_name": "S1", "backend_type": "rest",
        "endpoint_url": "http://s1", "status": "active",
    })
    svc.update_health("s1", "up")
    summary = svc.get_health_summary()
    assert summary["total"] == 1
    assert summary["up"] == 1
