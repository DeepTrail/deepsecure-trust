"""API tests for delegation invite + accept endpoints (WS-D3)."""

import uuid
from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient

from app.main import app as fastapi_app
from app.api.deps import get_db
from app.middleware.admin_auth import require_admin
from app.models.connected_service import ConnectedService
from app.models.delegation import DelegationToken
from app.models.delegation_template import DelegationTemplate


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


def _unique_user(prefix: str = "user") -> str:
    return f"{prefix}-{uuid.uuid4().hex[:8]}@acme.com"


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


def _create_template(db, agent_id: str = "agent-invite-test"):
    template = DelegationTemplate(
        agent_id=agent_id,
        max_permissions=["notion:pages:read", "notion:pages:search"],
        blocked_permissions=[],
        default_ttl_days=7,
        available_to_roles=["all"],
        provision_mode="on_invite",
    )
    db.add(template)
    db.commit()
    db.refresh(template)
    return template


def _create_pending_invite(db, user: str, template: DelegationTemplate):
    delegation = DelegationToken(
        agent_id=template.agent_id,
        delegator=user,
        delegated_permissions=[],
        source="invite",
        status="pending",
        template_id=str(template.id),
        expires_at=datetime.now(timezone.utc) + timedelta(days=7),
    )
    db.add(delegation)
    db.commit()
    db.refresh(delegation)
    return delegation


class TestDelegationAccept:
    def test_accept_pending_invite_activates_permissions(self, client, db):
        user = _unique_user("victor")
        _create_connected_service(db, user, "notion", ["read_pages", "search_content"])
        template = _create_template(db)
        delegation = _create_pending_invite(db, user, template)

        resp = client.post(
            f"/api/v1/delegations/{delegation.id}/accept",
            headers={"Authorization": f"Bearer mock_user_token_{user}"},
            json={},
        )

        assert resp.status_code == 200
        data = resp.json()
        assert data["delegation_id"] == delegation.id
        assert data["status"] == "active"
        assert set(data["permissions"]) == {"notion:pages:read", "notion:pages:search"}
        assert data["agent_id"] == template.agent_id

    def test_accept_insufficient_scopes_returns_400(self, client, db):
        user = _unique_user("victor")
        template = _create_template(db)
        delegation = _create_pending_invite(db, user, template)

        resp = client.post(
            f"/api/v1/delegations/{delegation.id}/accept",
            headers={"Authorization": f"Bearer mock_user_token_{user}"},
            json={},
        )

        assert resp.status_code == 400
        assert resp.json()["detail"]["error"] == "permission_validation_failed"

    def test_accept_forbidden_for_other_user(self, client, db):
        user = _unique_user("owner")
        template = _create_template(db)
        delegation = _create_pending_invite(db, user, template)

        resp = client.post(
            f"/api/v1/delegations/{delegation.id}/accept",
            headers={"Authorization": "Bearer mock_user_token_intruder@acme.com"},
            json={},
        )

        assert resp.status_code == 403

    def test_accept_non_pending_returns_409(self, client, db):
        user = _unique_user("sarah")
        _create_connected_service(db, user, "notion", ["read_pages", "search_content"])
        template = _create_template(db)
        delegation = _create_pending_invite(db, user, template)
        delegation.status = "active"
        delegation.delegated_permissions = ["notion:pages:read"]
        db.commit()

        resp = client.post(
            f"/api/v1/delegations/{delegation.id}/accept",
            headers={"Authorization": f"Bearer mock_user_token_{user}"},
            json={},
        )

        assert resp.status_code == 409


class TestTemplateInvite:
    def test_admin_invite_creates_pending_delegations(self, client, db):
        template = _create_template(db)
        user_a = _unique_user("priya")
        user_b = _unique_user("victor")

        resp = client.post(
            f"/api/v1/admin/delegation-templates/{template.id}/invite",
            headers={"Authorization": "Bearer admin-token"},
            json={"user_emails": [user_a, user_b]},
        )

        assert resp.status_code == 201
        data = resp.json()
        assert data["invited"] == 2
        assert len(data["delegation_ids"]) == 2

        for email in (user_a, user_b):
            row = (
                db.query(DelegationToken)
                .filter(
                    DelegationToken.delegator == email,
                    DelegationToken.agent_id == template.agent_id,
                )
                .first()
            )
            assert row is not None
            assert row.status == "pending"
            assert row.source == "invite"
            assert row.delegated_permissions == []

    def test_invite_skips_existing_active_delegation(self, client, db):
        template = _create_template(db)
        user = _unique_user("priya")
        existing = DelegationToken(
            agent_id=template.agent_id,
            delegator=user,
            delegated_permissions=["notion:pages:read"],
            source="manual",
            status="active",
        )
        db.add(existing)
        db.commit()

        resp = client.post(
            f"/api/v1/admin/delegation-templates/{template.id}/invite",
            headers={"Authorization": "Bearer admin-token"},
            json={"user_emails": [user]},
        )

        assert resp.status_code == 201
        data = resp.json()
        assert data["invited"] == 0
        assert user in data["skipped"]
