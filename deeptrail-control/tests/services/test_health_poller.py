"""Tests for HealthPoller and gateway liveness aggregation."""

from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.config import settings
from app.db.base import Base
from app.models.gateway_health_state import GatewayHealthState
from app.models.service_registry import ServiceRegistry
from app.services.health_poller import HealthPoller
from app.services.service_registry_service import ServiceRegistryService

import app.models.delegation_template  # noqa: ensure tables created
import app.models.gateway_health_state  # noqa: ensure tables created


@pytest.fixture()
def db():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()


@pytest.fixture()
def svc(db, monkeypatch):
    from cryptography.fernet import Fernet

    key = Fernet.generate_key().decode()
    monkeypatch.setenv("FERNET_KEY", key)
    monkeypatch.delenv("GOOGLE_CLOUD_PROJECT", raising=False)
    from app.core.kms import KMSClient

    return ServiceRegistryService(db=db, kms=KMSClient(fernet_key=key))


def _add_service(db, service_id: str = "notion") -> ServiceRegistry:
    entry = ServiceRegistry(
        service_id=service_id,
        display_name=service_id.title(),
        backend_type="rest",
        endpoint_url="https://api.example.com",
        status="active",
        health_status="up",
    )
    db.add(entry)
    db.commit()
    return entry


class TestGatewayStatus:
    def test_gateway_status_unknown_when_no_heartbeat(self, svc):
        summary = svc.get_health_summary()
        assert summary["gateway_status"] == "unknown"
        assert summary["gateway_last_seen_at"] is None

    def test_gateway_status_up_when_recent_heartbeat(self, svc, db):
        db.add(
            GatewayHealthState(
                gateway_last_seen_at=datetime.now(timezone.utc) - timedelta(seconds=30),
                gateway_instance_id="gw-1",
            )
        )
        db.commit()
        summary = svc.get_health_summary()
        assert summary["gateway_status"] == "up"

    def test_gateway_status_down_when_stale(self, svc, db):
        db.add(
            GatewayHealthState(
                gateway_last_seen_at=datetime.now(timezone.utc)
                - timedelta(seconds=settings.GATEWAY_STALE_THRESHOLD_SECONDS + 10),
                gateway_instance_id="gw-1",
            )
        )
        db.commit()
        summary = svc.get_health_summary()
        assert summary["gateway_status"] == "down"


class TestServiceStale:
    def test_service_marked_stale_when_last_check_old(self, svc, db):
        service = _add_service(db)
        service.health_last_checked_at = datetime.now(timezone.utc) - timedelta(
            seconds=settings.SERVICE_HEALTH_STALE_THRESHOLD_SECONDS + 60
        )
        service.health_probe_source = "gateway"
        db.commit()

        summary = svc.get_health_summary()
        assert summary["stale"] == 1
        assert summary["services"][0]["health_status"] == "stale"
        assert summary["services"][0]["probe_source"] == "gateway"

    def test_probe_source_recorded_on_update(self, svc, db):
        _add_service(db)
        svc.update_health("notion", "up", latency_ms=42, probe_source="control_plane")
        summary = svc.get_health_summary()
        assert summary["services"][0]["probe_source"] == "control_plane"


class TestHealthPoller:
    @pytest.mark.asyncio
    async def test_run_once_probes_active_services(self, db, monkeypatch):
        from cryptography.fernet import Fernet

        key = Fernet.generate_key().decode()
        monkeypatch.setenv("FERNET_KEY", key)
        monkeypatch.delenv("GOOGLE_CLOUD_PROJECT", raising=False)

        _add_service(db, "notion")
        _add_service(db, "slack")

        mock_resp = MagicMock()
        mock_resp.status_code = 200

        db.close = lambda: None  # prevent closing shared fixture session
        with patch("app.services.health_poller.SessionLocal", return_value=db):
            with patch("app.services.health_poller.httpx.AsyncClient") as mock_client_cls:
                mock_client = AsyncMock()
                mock_client.__aenter__ = AsyncMock(return_value=mock_client)
                mock_client.__aexit__ = AsyncMock(return_value=False)
                mock_client.get = AsyncMock(return_value=mock_resp)
                mock_client_cls.return_value = mock_client

                poller = HealthPoller()
                count = await poller.run_once()

        assert count == 2
        notion = db.query(ServiceRegistry).filter(ServiceRegistry.service_id == "notion").one()
        assert notion.health_probe_source == "control_plane"
        assert notion.health_last_checked_at is not None

    def test_record_gateway_heartbeat_creates_singleton(self, svc, db):
        state = svc.record_gateway_heartbeat(instance_id="pod-abc")
        assert state.gateway_instance_id == "pod-abc"
        assert state.gateway_last_seen_at is not None

        state2 = svc.record_gateway_heartbeat(instance_id="pod-xyz")
        assert db.query(GatewayHealthState).count() == 1
        assert state2.gateway_instance_id == "pod-xyz"
