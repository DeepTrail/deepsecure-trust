"""Unit tests for IdPSession model.

Tests cover:
- Model field definitions and column types
- Default values (revoked, created_at)
- is_expired property (None, future, past)
- is_revoked property
- Nullable encrypted fields
- Nullable id_token_claims
- Database persistence and retrieval
- Index-based queries
- Import from app.models
- String representation
"""

import uuid
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy.orm import Session

from app.models.idp_session import IdPSession


def _make_session(**overrides) -> IdPSession:
    """Helper to create an IdPSession with sensible defaults."""
    defaults = {
        "id": uuid.uuid4().hex,
        "session_id": f"sess-{uuid.uuid4().hex[:12]}",
        "user_id": "test@example.com",
        "idp": "google",
    }
    defaults.update(overrides)
    return IdPSession(**defaults)


# ─────────────────────────────────────────────────────────────────────────────
# Test: Model instantiation and fields
# ─────────────────────────────────────────────────────────────────────────────


class TestIdPSessionModel:
    """Tests for IdPSession column definitions and persistence."""

    def test_create_with_required_fields(self, db: Session):
        """IdPSession can be created with only required fields."""
        session = _make_session()
        db.add(session)
        db.commit()

        retrieved = db.query(IdPSession).filter(IdPSession.id == session.id).first()
        assert retrieved is not None
        assert retrieved.session_id == session.session_id
        assert retrieved.user_id == "test@example.com"
        assert retrieved.idp == "google"

    def test_create_with_all_fields(self, db: Session):
        """IdPSession can be created with all fields populated."""
        now = datetime.now(timezone.utc)
        session = _make_session(
            encrypted_refresh_token="gAAAAA...encrypted_refresh",
            encrypted_access_token="gAAAAA...encrypted_access",
            id_token_claims={"sub": "1234", "email": "test@example.com"},
            refreshed_at=now,
            expires_at=now + timedelta(days=14),
            revoked=False,
        )
        db.add(session)
        db.commit()

        retrieved = db.query(IdPSession).filter(IdPSession.id == session.id).first()
        assert retrieved.encrypted_refresh_token == "gAAAAA...encrypted_refresh"
        assert retrieved.encrypted_access_token == "gAAAAA...encrypted_access"
        assert retrieved.id_token_claims == {"sub": "1234", "email": "test@example.com"}
        assert retrieved.refreshed_at is not None
        assert retrieved.expires_at is not None

    def test_table_name(self):
        """Table name is 'idp_sessions' (plural)."""
        assert IdPSession.__tablename__ == "idp_sessions"

    def test_column_count(self):
        """Model has exactly 11 columns."""
        columns = [c.name for c in IdPSession.__table__.columns]
        assert len(columns) == 11

    def test_all_column_names(self):
        """All 11 columns are present with correct names."""
        expected = {
            "id", "session_id", "user_id", "idp",
            "encrypted_refresh_token", "encrypted_access_token",
            "id_token_claims", "created_at", "refreshed_at",
            "expires_at", "revoked",
        }
        actual = {c.name for c in IdPSession.__table__.columns}
        assert actual == expected


# ─────────────────────────────────────────────────────────────────────────────
# Test: Default values
# ─────────────────────────────────────────────────────────────────────────────


class TestIdPSessionDefaults:
    """Tests for default values on IdPSession columns."""

    def test_revoked_defaults_to_false(self, db: Session):
        """revoked defaults to False."""
        session = _make_session()
        db.add(session)
        db.commit()

        retrieved = db.query(IdPSession).filter(IdPSession.id == session.id).first()
        assert retrieved.revoked is False

    def test_created_at_auto_set(self, db: Session):
        """created_at is automatically set on insert."""
        session = _make_session()
        db.add(session)
        db.commit()

        retrieved = db.query(IdPSession).filter(IdPSession.id == session.id).first()
        assert retrieved.created_at is not None

    def test_refreshed_at_defaults_to_none(self):
        """refreshed_at defaults to None."""
        session = _make_session()
        assert session.refreshed_at is None

    def test_expires_at_defaults_to_none(self):
        """expires_at defaults to None."""
        session = _make_session()
        assert session.expires_at is None


# ─────────────────────────────────────────────────────────────────────────────
# Test: Nullable fields
# ─────────────────────────────────────────────────────────────────────────────


class TestIdPSessionNullableFields:
    """Tests that nullable fields accept None."""

    def test_encrypted_refresh_token_nullable(self, db: Session):
        """encrypted_refresh_token can be None."""
        session = _make_session(encrypted_refresh_token=None)
        db.add(session)
        db.commit()

        retrieved = db.query(IdPSession).filter(IdPSession.id == session.id).first()
        assert retrieved.encrypted_refresh_token is None

    def test_encrypted_access_token_nullable(self, db: Session):
        """encrypted_access_token can be None."""
        session = _make_session(encrypted_access_token=None)
        db.add(session)
        db.commit()

        retrieved = db.query(IdPSession).filter(IdPSession.id == session.id).first()
        assert retrieved.encrypted_access_token is None

    def test_id_token_claims_nullable(self, db: Session):
        """id_token_claims can be None."""
        session = _make_session(id_token_claims=None)
        db.add(session)
        db.commit()

        retrieved = db.query(IdPSession).filter(IdPSession.id == session.id).first()
        assert retrieved.id_token_claims is None


# ─────────────────────────────────────────────────────────────────────────────
# Test: is_expired property
# ─────────────────────────────────────────────────────────────────────────────


class TestIsExpired:
    """Tests for the is_expired property."""

    def test_none_expires_at_not_expired(self):
        """is_expired returns False when expires_at is None."""
        session = _make_session(expires_at=None)
        assert session.is_expired is False

    def test_future_expires_at_not_expired(self):
        """is_expired returns False when expires_at is in the future."""
        session = _make_session(
            expires_at=datetime.now(timezone.utc) + timedelta(hours=1),
        )
        assert session.is_expired is False

    def test_past_expires_at_is_expired(self):
        """is_expired returns True when expires_at is in the past."""
        session = _make_session(
            expires_at=datetime.now(timezone.utc) - timedelta(hours=1),
        )
        assert session.is_expired is True

    def test_expired_persisted(self, db: Session):
        """is_expired works correctly after database round-trip."""
        session = _make_session(
            expires_at=datetime.now(timezone.utc) - timedelta(hours=1),
        )
        db.add(session)
        db.commit()

        retrieved = db.query(IdPSession).filter(IdPSession.id == session.id).first()
        assert retrieved.is_expired is True

    def test_not_expired_persisted(self, db: Session):
        """is_expired returns False after database round-trip for future expiry."""
        session = _make_session(
            expires_at=datetime.now(timezone.utc) + timedelta(days=7),
        )
        db.add(session)
        db.commit()

        retrieved = db.query(IdPSession).filter(IdPSession.id == session.id).first()
        assert retrieved.is_expired is False


# ─────────────────────────────────────────────────────────────────────────────
# Test: is_revoked property
# ─────────────────────────────────────────────────────────────────────────────


class TestIsRevoked:
    """Tests for the is_revoked property."""

    def test_is_revoked_false(self):
        """is_revoked returns False when revoked is False."""
        session = _make_session(revoked=False)
        assert session.is_revoked is False

    def test_is_revoked_true(self):
        """is_revoked returns True when revoked is True."""
        session = _make_session(revoked=True)
        assert session.is_revoked is True

    def test_is_revoked_persisted(self, db: Session):
        """is_revoked works correctly after database round-trip."""
        session = _make_session(revoked=True)
        db.add(session)
        db.commit()

        retrieved = db.query(IdPSession).filter(IdPSession.id == session.id).first()
        assert retrieved.is_revoked is True


# ─────────────────────────────────────────────────────────────────────────────
# Test: Index-based queries
# ─────────────────────────────────────────────────────────────────────────────


class TestIdPSessionIndexes:
    """Tests verifying index-backed queries work correctly."""

    def test_query_by_session_id(self, db: Session):
        """Can look up session by session_id (unique index)."""
        session = _make_session(session_id="unique-sid-123")
        db.add(session)
        db.commit()

        retrieved = db.query(IdPSession).filter(
            IdPSession.session_id == "unique-sid-123"
        ).first()
        assert retrieved is not None
        assert retrieved.id == session.id

    def test_query_by_user_id(self, db: Session):
        """Can query all sessions for a user (non-unique index)."""
        uid = f"multi-{uuid.uuid4().hex[:8]}@example.com"
        s1 = _make_session(user_id=uid, session_id=f"s1-{uuid.uuid4().hex[:8]}")
        s2 = _make_session(user_id=uid, session_id=f"s2-{uuid.uuid4().hex[:8]}")
        db.add_all([s1, s2])
        db.commit()

        results = db.query(IdPSession).filter(IdPSession.user_id == uid).all()
        assert len(results) == 2

    def test_query_by_idp(self, db: Session):
        """Can filter sessions by provider (non-unique index)."""
        tag = uuid.uuid4().hex[:8]
        s_google = _make_session(idp="google", user_id=f"idp-{tag}@example.com")
        s_keycloak = _make_session(idp="keycloak", user_id=f"idp-{tag}@example.com")
        db.add_all([s_google, s_keycloak])
        db.commit()

        results = db.query(IdPSession).filter(
            IdPSession.idp == "google",
            IdPSession.user_id == f"idp-{tag}@example.com",
        ).all()
        assert len(results) == 1
        assert results[0].idp == "google"

    def test_session_id_unique_constraint(self, db: Session):
        """session_id enforces uniqueness."""
        sid = f"dup-{uuid.uuid4().hex[:8]}"
        s1 = _make_session(session_id=sid)
        db.add(s1)
        db.commit()

        s2 = _make_session(session_id=sid)
        db.add(s2)
        with pytest.raises(Exception):
            db.commit()
        db.rollback()


# ─────────────────────────────────────────────────────────────────────────────
# Test: Import from app.models
# ─────────────────────────────────────────────────────────────────────────────


class TestIdPSessionImport:
    """Tests that IdPSession is properly registered in models package."""

    def test_import_from_models(self):
        """IdPSession is importable via app.models."""
        from app.models import IdPSession as Imported
        assert Imported is IdPSession

    def test_in_all(self):
        """IdPSession is listed in app.models.__all__."""
        from app import models
        assert "IdPSession" in models.__all__


# ─────────────────────────────────────────────────────────────────────────────
# Test: __repr__
# ─────────────────────────────────────────────────────────────────────────────


class TestIdPSessionRepr:
    """Tests for string representation."""

    def test_repr_active(self):
        session = _make_session()
        r = repr(session)
        assert "active" in r
        assert "test@example.com" in r
        assert "google" in r

    def test_repr_revoked(self):
        session = _make_session(revoked=True)
        r = repr(session)
        assert "revoked" in r

    def test_repr_expired(self):
        session = _make_session(
            expires_at=datetime.now(timezone.utc) - timedelta(hours=1),
        )
        r = repr(session)
        assert "expired" in r
