"""Tests for admin middleware (require_admin).

Tests:
  - Admin JWT passes (roles claim)
  - Employee JWT returns 403
  - DB fallback when JWT has no roles claim
  - Missing/invalid token returns 401
"""

from datetime import timedelta

import pytest
from fastapi.testclient import TestClient

from app.core.security import create_access_token
from app.models.user_session import UserSession


def _make_admin_token(user_id: str = "admin@acme.com") -> dict:
    """Create auth headers with a JWT that has sub claim but no roles (DB fallback path)."""
    import jwt as pyjwt
    from app.core.config import settings

    payload = {"sub": user_id}
    token = pyjwt.encode(payload, settings.SECRET_KEY, algorithm="HS256")
    return {"Authorization": f"Bearer {token}"}


def _make_admin_token_with_roles(user_id: str = "admin@acme.com") -> dict:
    """Create auth headers with admin role embedded in JWT claims."""
    import jwt as pyjwt
    from app.core.config import settings

    payload = {
        "sub": user_id,
        "roles": ["admin"],
    }
    token = pyjwt.encode(payload, settings.SECRET_KEY, algorithm="HS256")
    return {"Authorization": f"Bearer {token}"}


def _make_employee_token(user_id: str = "employee@acme.com") -> dict:
    """Create auth headers with a JWT that has no admin role."""
    import jwt as pyjwt
    from app.core.config import settings

    payload = {
        "sub": user_id,
        "roles": ["employee"],
    }
    token = pyjwt.encode(payload, settings.SECRET_KEY, algorithm="HS256")
    return {"Authorization": f"Bearer {token}"}


class TestAdminRoleEndpoint:
    """Test POST /api/v1/admin/users/{user_id}/role"""

    def test_admin_jwt_can_set_role(self, client: TestClient, db):
        from datetime import datetime, timezone

        session = UserSession(
            session_id="usess-test-target",
            user_id="target@acme.com",
            idp_issuer="https://acme.okta.com",
            created_at=datetime.now(timezone.utc),
            expires_at=datetime(2099, 1, 1, tzinfo=timezone.utc),
        )
        db.add(session)

        admin_session = UserSession(
            session_id="usess-test-admin",
            user_id="admin@acme.com",
            idp_issuer="https://acme.okta.com",
            role="admin",
            created_at=datetime.now(timezone.utc),
            expires_at=datetime(2099, 1, 1, tzinfo=timezone.utc),
        )
        db.add(admin_session)
        db.commit()

        headers = _make_admin_token_with_roles()
        resp = client.post(
            "/api/v1/admin/users/target@acme.com/role",
            json={"role": "admin"},
            headers=headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["role"] == "admin"
        assert data["user_id"] == "target@acme.com"

        db.refresh(session)
        assert session.role == "admin"

        # Cleanup
        db.delete(session)
        db.delete(admin_session)
        db.commit()

    def test_employee_jwt_blocked(self, client: TestClient, db):
        headers = _make_employee_token()
        resp = client.post(
            "/api/v1/admin/users/someone@acme.com/role",
            json={"role": "admin"},
            headers=headers,
        )
        assert resp.status_code == 403

    def test_invalid_role_rejected(self, client: TestClient, db):
        from datetime import datetime, timezone

        admin_session = UserSession(
            session_id="usess-admin-2",
            user_id="admin2@acme.com",
            idp_issuer="https://acme.okta.com",
            role="admin",
            created_at=datetime.now(timezone.utc),
            expires_at=datetime(2099, 1, 1, tzinfo=timezone.utc),
        )
        db.add(admin_session)
        db.commit()

        headers = _make_admin_token_with_roles("admin2@acme.com")
        resp = client.post(
            "/api/v1/admin/users/someone@acme.com/role",
            json={"role": "superadmin"},
            headers=headers,
        )
        assert resp.status_code == 400

        db.delete(admin_session)
        db.commit()

    def test_db_fallback_when_jwt_has_no_roles(self, client: TestClient, db):
        from datetime import datetime, timezone

        admin_session = UserSession(
            session_id="usess-db-admin",
            user_id="db-admin@acme.com",
            idp_issuer="https://acme.okta.com",
            role="admin",
            created_at=datetime.now(timezone.utc),
            expires_at=datetime(2099, 1, 1, tzinfo=timezone.utc),
        )
        target_session = UserSession(
            session_id="usess-db-target",
            user_id="db-target@acme.com",
            idp_issuer="https://acme.okta.com",
            created_at=datetime.now(timezone.utc),
            expires_at=datetime(2099, 1, 1, tzinfo=timezone.utc),
        )
        db.add(admin_session)
        db.add(target_session)
        db.commit()

        headers = _make_admin_token("db-admin@acme.com")
        resp = client.post(
            "/api/v1/admin/users/db-target@acme.com/role",
            json={"role": "security"},
            headers=headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["role"] == "security"

        db.delete(admin_session)
        db.delete(target_session)
        db.commit()

    def test_missing_auth_header_returns_401(self, client: TestClient):
        resp = client.post(
            "/api/v1/admin/users/someone@acme.com/role",
            json={"role": "admin"},
        )
        assert resp.status_code in (401, 422)

    def test_user_not_found_returns_404(self, client: TestClient, db):
        from datetime import datetime, timezone

        admin_session = UserSession(
            session_id="usess-admin-nf",
            user_id="admin-nf@acme.com",
            idp_issuer="https://acme.okta.com",
            role="admin",
            created_at=datetime.now(timezone.utc),
            expires_at=datetime(2099, 1, 1, tzinfo=timezone.utc),
        )
        db.add(admin_session)
        db.commit()

        headers = _make_admin_token_with_roles("admin-nf@acme.com")
        resp = client.post(
            "/api/v1/admin/users/nonexistent@acme.com/role",
            json={"role": "admin"},
            headers=headers,
        )
        assert resp.status_code == 404

        db.delete(admin_session)
        db.commit()
