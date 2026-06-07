"""API tests for delegation PATCH endpoints (WS-C2)."""

import uuid
from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient

from app.main import app as fastapi_app
from app.api.deps import get_db
from app.middleware.admin_auth import require_admin
from app.models.connected_service import ConnectedService
from app.models.delegation import DelegationToken


@pytest.fixture()
def client(db):
    def _override_db():
        yield db

    def _override_admin():
        return {"sub": "admin@test.com", "roles": ["admin"]}

    fastapi_app.dependency_overrides[get_db] = _override_db
    fastapi_app.dependency_overrides[require_admin] = _override_admin
    yield TestClient(fastapi_app)
    fastapi_app.dependency_overrides.pop(get_db, None)
    fastapi_app.dependency_overrides.pop(require_admin, None)


def _create_connected_service(db, user_id: str, service_id: str, scopes: list[str]):
    conn = ConnectedService(
        user_id=user_id,
        service_id=service_id,
        oauth_token_ref=f"vault://{user_id}-{service_id}",
        scopes_granted=scopes,
    )
    db.add(conn)
    db.commit()
    return conn


def _create_delegation(db, delegator: str, permissions: list[str]):
    delegation = DelegationToken(
        agent_id="agent-patch-test",
        delegator=delegator,
        delegated_permissions=permissions,
        source="manual",
        status="active",
    )
    db.add(delegation)
    db.commit()
    db.refresh(delegation)
    return delegation


def _unique_user(prefix: str = "user") -> str:
    return f"{prefix}-{uuid.uuid4().hex[:8]}@acme.com"


class TestUserDelegationPatch:
    def test_user_patch_narrows_permissions(self, client, db):
        user = _unique_user("sarah")
        _create_connected_service(db, user, "notion", ["read_pages", "search_content"])
        delegation = _create_delegation(
            db,
            user,
            ["notion:pages:read", "notion:pages:search"],
        )

        resp = client.patch(
            f"/api/v1/delegations/{delegation.id}",
            headers={"Authorization": f"Bearer mock_user_token_{user}"},
            json={"permissions": ["notion:pages:read"]},
        )

        assert resp.status_code == 200
        data = resp.json()
        assert data["delegation_id"] == delegation.id
        assert data["permissions"] == ["notion:pages:read"]
        assert data["status"] == "active"
        assert "sessions_revoked" in data

    def test_user_patch_widening_rejected(self, client, db):
        user = _unique_user("sarah")
        _create_connected_service(db, user, "notion", ["read_pages", "search_content"])
        delegation = _create_delegation(db, user, ["notion:pages:read"])

        resp = client.patch(
            f"/api/v1/delegations/{delegation.id}",
            headers={"Authorization": f"Bearer mock_user_token_{user}"},
            json={"permissions": ["notion:pages:read", "notion:pages:search"]},
        )

        assert resp.status_code == 400
        assert resp.json()["detail"]["error"] == "permission_widening_not_allowed"

    def test_user_patch_forbidden_for_other_user(self, client, db):
        delegation = _create_delegation(
            db,
            "owner@acme.com",
            ["notion:pages:read"],
        )

        resp = client.patch(
            f"/api/v1/delegations/{delegation.id}",
            headers={"Authorization": "Bearer mock_user_token_intruder@acme.com"},
            json={"permissions": []},
        )

        assert resp.status_code == 403

    def test_user_patch_revoked_delegation_conflict(self, client, db):
        user = _unique_user("sarah")
        delegation = _create_delegation(db, user, ["notion:pages:read"])
        delegation.revoke()
        db.commit()

        resp = client.patch(
            f"/api/v1/delegations/{delegation.id}",
            headers={"Authorization": f"Bearer mock_user_token_{user}"},
            json={"permissions": []},
        )

        assert resp.status_code == 409


class TestAdminDelegationPatch:
    def test_admin_patch_narrows_permissions(self, client, db):
        user = _unique_user("employee")
        _create_connected_service(db, user, "notion", ["read_pages", "search_content"])
        delegation = _create_delegation(
            db,
            user,
            ["notion:pages:read", "notion:pages:search"],
        )

        resp = client.patch(
            f"/api/v1/admin/delegations/{delegation.id}",
            json={"permissions": ["notion:pages:read"]},
        )

        assert resp.status_code == 200
        assert resp.json()["permissions"] == ["notion:pages:read"]

    def test_admin_patch_updates_constraints(self, client, db):
        user = _unique_user("employee")
        delegation = _create_delegation(db, user, ["notion:pages:read"])

        resp = client.patch(
            f"/api/v1/admin/delegations/{delegation.id}",
            json={"constraints": {"max_actions_per_day": 25}},
        )

        assert resp.status_code == 200
        db.refresh(delegation)
        assert delegation.constraints["max_actions_per_day"] == 25

    def test_admin_patch_updates_expires_at(self, client, db):
        user = _unique_user("employee")
        delegation = _create_delegation(db, user, ["notion:pages:read"])
        new_expiry = (datetime.now(timezone.utc) + timedelta(days=3)).isoformat()

        resp = client.patch(
            f"/api/v1/admin/delegations/{delegation.id}",
            json={"expires_at": new_expiry},
        )

        assert resp.status_code == 200
        assert resp.json()["expires_at"] is not None
