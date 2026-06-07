"""Tests for public service catalog endpoint (GET /api/v1/services/catalog).

Validates the Available To enforcement logic:
- Role-based filtering (available_to_roles)
- Group-based filtering (available_to_groups)
- Email-based filtering (available_to_users)
- "all" role grants universal visibility
"""

import pytest
from datetime import datetime, timezone, timedelta
from fastapi.testclient import TestClient

from app.main import app as fastapi_app
from app.api.deps import get_db
from app.core.security import create_access_token
from app.models.service_registry import ServiceRegistry
from app.models.user_session import UserSession


@pytest.fixture()
def client(db):
    db.query(ServiceRegistry).delete()
    db.query(UserSession).delete()
    db.commit()

    def _override_db():
        yield db

    fastapi_app.dependency_overrides[get_db] = _override_db
    yield TestClient(fastapi_app)
    fastapi_app.dependency_overrides.clear()


def _make_token(
    sub: str,
    groups: list[str] | None = None,
    roles: list[str] | None = None,
) -> dict:
    extra = {}
    if groups:
        extra["groups"] = groups
    if roles:
        extra["roles"] = roles
    token = create_access_token(
        subject=sub,
        expires_delta=timedelta(minutes=30),
        extra_claims=extra,
    )
    return {"Authorization": f"Bearer {token}"}


def _seed_services(db, services: list[dict]):
    for svc in services:
        db.add(ServiceRegistry(
            service_id=svc["service_id"],
            display_name=svc.get("display_name", svc["service_id"]),
            backend_type=svc.get("backend_type", "rest"),
            endpoint_url=svc.get("endpoint_url", f"https://{svc['service_id']}.example.com"),
            status="active",
            available_to_roles=svc.get("available_to_roles", ["all"]),
            available_to_groups=svc.get("available_to_groups", []),
            available_to_users=svc.get("available_to_users", []),
        ))
    db.commit()


def _seed_user_session(db, user_id: str, role: str = "employee"):
    db.add(UserSession(
        user_id=user_id,
        idp_issuer="test",
        role=role,
        created_at=datetime.now(timezone.utc),
    ))
    db.commit()


class TestCatalogEnforcement:
    """Available To enforcement tests."""

    def test_all_role_grants_universal_access(self, client, db):
        _seed_services(db, [
            {"service_id": "public-svc", "available_to_roles": ["all"]},
        ])
        _seed_user_session(db, "user@test.com", "employee")

        headers = _make_token("user@test.com")
        resp = client.get("/api/v1/services/catalog", headers=headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] >= 1
        ids = [s["service_id"] for s in data["services"]]
        assert "public-svc" in ids

    def test_role_filtering(self, client, db):
        """Catalog enforces visibility via available_to_roles and JWT roles claim."""
        _seed_services(db, [
            {
                "service_id": "admin-only",
                "available_to_roles": ["admin"],
                "available_to_users": [],
            },
            {
                "service_id": "eng-only",
                "available_to_roles": ["engineer"],
                "available_to_users": [],
            },
        ])
        _seed_user_session(db, "admin@test.com", "admin")
        _seed_user_session(db, "dev@test.com", "engineer")

        admin_resp = client.get(
            "/api/v1/services/catalog",
            headers=_make_token("admin@test.com", roles=["admin"]),
        )
        admin_ids = [s["service_id"] for s in admin_resp.json()["services"]]
        assert "admin-only" in admin_ids
        assert "eng-only" not in admin_ids

        dev_resp = client.get(
            "/api/v1/services/catalog",
            headers=_make_token("dev@test.com", roles=["engineer"]),
        )
        dev_ids = [s["service_id"] for s in dev_resp.json()["services"]]
        assert "eng-only" in dev_ids
        assert "admin-only" not in dev_ids

    def test_group_filtering(self, client, db):
        _seed_services(db, [
            {
                "service_id": "design-tool",
                "available_to_roles": [],
                "available_to_groups": ["design-team@test.com"],
            },
        ])
        _seed_user_session(db, "designer@test.com")
        _seed_user_session(db, "dev@test.com")

        headers_in_group = _make_token("designer@test.com", groups=["design-team@test.com"])
        resp = client.get("/api/v1/services/catalog", headers=headers_in_group)
        ids = [s["service_id"] for s in resp.json()["services"]]
        assert "design-tool" in ids

        headers_no_group = _make_token("dev@test.com", groups=["eng-team@test.com"])
        resp2 = client.get("/api/v1/services/catalog", headers=headers_no_group)
        ids2 = [s["service_id"] for s in resp2.json()["services"]]
        assert "design-tool" not in ids2

    def test_email_filtering(self, client, db):
        _seed_services(db, [
            {
                "service_id": "vip-svc",
                "available_to_roles": [],
                "available_to_users": ["vip@test.com"],
            },
        ])
        _seed_user_session(db, "vip@test.com")
        _seed_user_session(db, "regular@test.com")

        resp = client.get("/api/v1/services/catalog", headers=_make_token("vip@test.com"))
        ids = [s["service_id"] for s in resp.json()["services"]]
        assert "vip-svc" in ids

        resp2 = client.get("/api/v1/services/catalog", headers=_make_token("regular@test.com"))
        ids2 = [s["service_id"] for s in resp2.json()["services"]]
        assert "vip-svc" not in ids2

    def test_inactive_services_hidden(self, client, db):
        db.add(ServiceRegistry(
            service_id="inactive-svc",
            display_name="Inactive",
            backend_type="rest",
            endpoint_url="https://inactive.example.com",
            status="sandbox",
            available_to_roles=["all"],
        ))
        db.commit()
        _seed_user_session(db, "any@test.com")

        resp = client.get("/api/v1/services/catalog", headers=_make_token("any@test.com"))
        ids = [s["service_id"] for s in resp.json()["services"]]
        assert "inactive-svc" not in ids

    def test_unauthenticated_returns_401(self, client, db):
        resp = client.get("/api/v1/services/catalog")
        assert resp.status_code in (401, 422)

    def test_combined_access_paths(self, client, db):
        """User can access service via role OR group OR email (any match suffices)."""
        _seed_services(db, [
            {
                "service_id": "multi-access",
                "available_to_roles": ["security"],
                "available_to_groups": ["secops@test.com"],
                "available_to_users": ["ciso@test.com"],
            },
        ])
        _seed_user_session(db, "ciso@test.com", "employee")

        resp = client.get("/api/v1/services/catalog", headers=_make_token("ciso@test.com"))
        ids = [s["service_id"] for s in resp.json()["services"]]
        assert "multi-access" in ids
