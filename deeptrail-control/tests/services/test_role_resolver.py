"""Tests for RoleResolver (CR-1)."""

import pytest
from datetime import datetime, timezone

from app.models.user_session import UserSession
from app.services.role_resolver import RoleResolver


@pytest.fixture()
def resolver():
    return RoleResolver()


def test_jwt_roles_take_precedence(db, resolver):
    db.add(
        UserSession(
            user_id="user@test.com",
            idp_issuer="test",
            role="admin",
            created_at=datetime.now(timezone.utc),
        )
    )
    db.commit()

    roles = resolver.resolve(
        jwt_roles=["sales"],
        user_session_role="admin",
        groups=["engineering@deeptrail.com"],
        db=db,
    )
    assert roles == ["sales"]


def test_session_role_when_no_jwt_roles(db, resolver):
    db.add(
        UserSession(
            user_id="user@test.com",
            idp_issuer="test",
            role="engineer",
            created_at=datetime.now(timezone.utc),
        )
    )
    db.commit()

    roles = resolver.resolve(jwt_roles=None, user_session_role="engineer", groups=None, db=db)
    assert roles == ["engineer"]


def test_default_employee_when_no_signals(resolver):
    roles = resolver.resolve(jwt_roles=None, user_session_role=None, groups=None, db=None)
    assert roles == ["employee"]


def test_resolve_context_includes_groups(db, resolver):
    ctx = resolver.resolve_context(
        sub="user@test.com",
        jwt_roles=["sales"],
        groups=["sales-team"],
        db=db,
    )
    assert ctx.sub == "user@test.com"
    assert ctx.groups == ["sales-team"]
    assert ctx.roles == ["sales"]
