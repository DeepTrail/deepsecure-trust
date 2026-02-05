"""Unit tests for the UserSessionService."""

import uuid
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy.orm import Session

from app.models.user_session import UserSession
from app.services.user_session_service import (
    DEFAULT_SESSION_DURATION_HOURS,
    UserSessionService,
)


def unique_user_id() -> str:
    """Generate a unique user ID for test isolation."""
    return f"test-user-{uuid.uuid4()}@acme.com"


@pytest.fixture
def user_session_service(db: Session) -> UserSessionService:
    """Fixture to provide a UserSessionService instance."""
    return UserSessionService(db)


@pytest.fixture
def sample_session(user_session_service: UserSessionService) -> UserSession:
    """Fixture to create a sample user session."""
    return user_session_service.create_session(
        user_id="sarah@acme.com",
        idp_issuer="https://acme.okta.com",
        organization_id="org-acme-123",
    )


class TestUserSessionServiceCreate:
    """Tests for UserSessionService.create_session()."""

    def test_create_session_basic(self, user_session_service: UserSessionService):
        """Create a session with basic required fields."""
        session = user_session_service.create_session(
            user_id="sarah@acme.com",
            idp_issuer="https://acme.okta.com",
        )

        assert session is not None
        assert session.user_id == "sarah@acme.com"
        assert session.idp_issuer == "https://acme.okta.com"
        assert session.session_id.startswith("usess-")

    def test_create_session_with_organization(
        self, user_session_service: UserSessionService
    ):
        """Create a session with organization ID."""
        session = user_session_service.create_session(
            user_id="sarah@acme.com",
            idp_issuer="https://acme.okta.com",
            organization_id="org-acme-123",
        )

        assert session.organization_id == "org-acme-123"

    def test_create_session_with_custom_expiry(
        self, user_session_service: UserSessionService
    ):
        """Create a session with custom expiry time."""
        session = user_session_service.create_session(
            user_id="sarah@acme.com",
            idp_issuer="https://acme.okta.com",
            expires_in_hours=4,
        )

        expected_expiry = datetime.now(timezone.utc) + timedelta(hours=4)
        # Handle timezone-naive datetimes from SQLite
        session_expiry = session.expires_at
        if session_expiry.tzinfo is None:
            session_expiry = session_expiry.replace(tzinfo=timezone.utc)
        # Allow 1 minute tolerance
        assert abs((session_expiry - expected_expiry).total_seconds()) < 60

    def test_create_session_default_expiry(
        self, user_session_service: UserSessionService
    ):
        """Session should default to 8 hours expiry."""
        session = user_session_service.create_session(
            user_id="sarah@acme.com",
            idp_issuer="https://acme.okta.com",
        )

        expected_expiry = datetime.now(timezone.utc) + timedelta(
            hours=DEFAULT_SESSION_DURATION_HOURS
        )
        # Handle timezone-naive datetimes from SQLite
        session_expiry = session.expires_at
        if session_expiry.tzinfo is None:
            session_expiry = session_expiry.replace(tzinfo=timezone.utc)
        # Allow 1 minute tolerance
        assert abs((session_expiry - expected_expiry).total_seconds()) < 60

    def test_create_session_with_idp_metadata(
        self, user_session_service: UserSessionService
    ):
        """Create a session with IdP metadata."""
        metadata = '{"groups": ["engineering", "admins"]}'
        session = user_session_service.create_session(
            user_id="sarah@acme.com",
            idp_issuer="https://acme.okta.com",
            idp_metadata=metadata,
        )

        assert session.idp_metadata == metadata

    def test_create_session_is_active(self, user_session_service: UserSessionService):
        """Newly created session should be active."""
        session = user_session_service.create_session(
            user_id="sarah@acme.com",
            idp_issuer="https://acme.okta.com",
        )

        assert session.is_active is True
        assert session.is_expired is False
        assert session.is_revoked is False


class TestUserSessionServiceGet:
    """Tests for UserSessionService.get_session()."""

    def test_get_session_found(
        self, user_session_service: UserSessionService, sample_session: UserSession
    ):
        """Get an existing session by ID."""
        retrieved = user_session_service.get_session(sample_session.session_id)

        assert retrieved is not None
        assert retrieved.session_id == sample_session.session_id
        assert retrieved.user_id == sample_session.user_id

    def test_get_session_not_found(self, user_session_service: UserSessionService):
        """Get a non-existent session returns None."""
        retrieved = user_session_service.get_session("usess-does-not-exist")

        assert retrieved is None

    def test_get_expired_session_returns_none(
        self, user_session_service: UserSessionService
    ):
        """Get an expired session returns None."""
        # Create a session that expires immediately
        session = user_session_service.create_session(
            user_id="sarah@acme.com",
            idp_issuer="https://acme.okta.com",
            expires_in_hours=0,  # Expires immediately
        )

        # Force the expiry to be in the past
        session.expires_at = datetime.now(timezone.utc) - timedelta(hours=1)
        user_session_service.db.commit()

        retrieved = user_session_service.get_session(session.session_id)
        assert retrieved is None

    def test_get_revoked_session_returns_none(
        self, user_session_service: UserSessionService, sample_session: UserSession
    ):
        """Get a revoked session returns None."""
        # Revoke the session
        user_session_service.revoke_session(sample_session.session_id)

        retrieved = user_session_service.get_session(sample_session.session_id)
        assert retrieved is None


class TestUserSessionServiceGetIncludingInactive:
    """Tests for UserSessionService.get_session_including_inactive()."""

    def test_get_expired_session_including_inactive(
        self, user_session_service: UserSessionService
    ):
        """Get an expired session when including inactive."""
        session = user_session_service.create_session(
            user_id="sarah@acme.com",
            idp_issuer="https://acme.okta.com",
        )
        
        # Force expiry
        session.expires_at = datetime.now(timezone.utc) - timedelta(hours=1)
        user_session_service.db.commit()

        retrieved = user_session_service.get_session_including_inactive(
            session.session_id
        )
        assert retrieved is not None
        assert retrieved.session_id == session.session_id

    def test_get_revoked_session_including_inactive(
        self, user_session_service: UserSessionService, sample_session: UserSession
    ):
        """Get a revoked session when including inactive."""
        user_session_service.revoke_session(sample_session.session_id)

        retrieved = user_session_service.get_session_including_inactive(
            sample_session.session_id
        )
        assert retrieved is not None
        assert retrieved.revoked_at is not None


class TestUserSessionServiceGetByUser:
    """Tests for UserSessionService.get_sessions_by_user()."""

    def test_get_sessions_by_user(self, user_session_service: UserSessionService):
        """Get all sessions for a user."""
        # Use unique user IDs for test isolation
        user_id = unique_user_id()
        other_user_id = unique_user_id()
        
        # Create multiple sessions
        user_session_service.create_session(
            user_id=user_id,
            idp_issuer="https://acme.okta.com",
        )
        user_session_service.create_session(
            user_id=user_id,
            idp_issuer="https://acme.okta.com",
        )
        # Different user
        user_session_service.create_session(
            user_id=other_user_id,
            idp_issuer="https://acme.okta.com",
        )

        sessions = user_session_service.get_sessions_by_user(user_id)
        assert len(sessions) == 2
        assert all(s.user_id == user_id for s in sessions)

    def test_get_sessions_by_user_excludes_expired(
        self, user_session_service: UserSessionService
    ):
        """Expired sessions are excluded by default."""
        user_id = unique_user_id()
        session = user_session_service.create_session(
            user_id=user_id,
            idp_issuer="https://acme.okta.com",
        )
        
        # Expire the session
        session.expires_at = datetime.now(timezone.utc) - timedelta(hours=1)
        user_session_service.db.commit()

        sessions = user_session_service.get_sessions_by_user(user_id)
        assert len(sessions) == 0

    def test_get_sessions_by_user_include_inactive(
        self, user_session_service: UserSessionService
    ):
        """Include inactive sessions when requested."""
        user_id = unique_user_id()
        session = user_session_service.create_session(
            user_id=user_id,
            idp_issuer="https://acme.okta.com",
        )
        
        # Expire the session
        session.expires_at = datetime.now(timezone.utc) - timedelta(hours=1)
        user_session_service.db.commit()

        sessions = user_session_service.get_sessions_by_user(
            user_id, include_inactive=True
        )
        assert len(sessions) == 1

    def test_get_sessions_by_user_empty(self, user_session_service: UserSessionService):
        """Get sessions for user with no sessions."""
        sessions = user_session_service.get_sessions_by_user(unique_user_id())
        assert sessions == []


class TestUserSessionServiceExpire:
    """Tests for UserSessionService.expire_session()."""

    def test_expire_session(
        self, user_session_service: UserSessionService, sample_session: UserSession
    ):
        """Expire an existing session."""
        result = user_session_service.expire_session(sample_session.session_id)

        assert result is True
        
        # Session should no longer be retrievable
        retrieved = user_session_service.get_session(sample_session.session_id)
        assert retrieved is None

    def test_expire_nonexistent_session(self, user_session_service: UserSessionService):
        """Expire a non-existent session returns False."""
        result = user_session_service.expire_session("usess-does-not-exist")
        assert result is False


class TestUserSessionServiceRevoke:
    """Tests for UserSessionService.revoke_session()."""

    def test_revoke_session(
        self, user_session_service: UserSessionService, sample_session: UserSession
    ):
        """Revoke an existing session."""
        result = user_session_service.revoke_session(sample_session.session_id)

        assert result is True
        
        # Session should no longer be retrievable
        retrieved = user_session_service.get_session(sample_session.session_id)
        assert retrieved is None
        
        # But should be retrievable including inactive
        retrieved_inactive = user_session_service.get_session_including_inactive(
            sample_session.session_id
        )
        assert retrieved_inactive is not None
        assert retrieved_inactive.revoked_at is not None

    def test_revoke_nonexistent_session(self, user_session_service: UserSessionService):
        """Revoke a non-existent session returns False."""
        result = user_session_service.revoke_session("usess-does-not-exist")
        assert result is False

    def test_revoke_already_revoked_session(
        self, user_session_service: UserSessionService, sample_session: UserSession
    ):
        """Revoking an already revoked session is idempotent."""
        user_session_service.revoke_session(sample_session.session_id)
        result = user_session_service.revoke_session(sample_session.session_id)

        assert result is True  # Idempotent


class TestUserSessionServiceIsValid:
    """Tests for UserSessionService.is_valid()."""

    def test_is_valid_active_session(
        self, user_session_service: UserSessionService, sample_session: UserSession
    ):
        """Active session is valid."""
        assert user_session_service.is_valid(sample_session.session_id) is True

    def test_is_valid_expired_session(
        self, user_session_service: UserSessionService, sample_session: UserSession
    ):
        """Expired session is not valid."""
        sample_session.expires_at = datetime.now(timezone.utc) - timedelta(hours=1)
        user_session_service.db.commit()

        assert user_session_service.is_valid(sample_session.session_id) is False

    def test_is_valid_revoked_session(
        self, user_session_service: UserSessionService, sample_session: UserSession
    ):
        """Revoked session is not valid."""
        user_session_service.revoke_session(sample_session.session_id)

        assert user_session_service.is_valid(sample_session.session_id) is False

    def test_is_valid_nonexistent_session(
        self, user_session_service: UserSessionService
    ):
        """Non-existent session is not valid."""
        assert user_session_service.is_valid("usess-does-not-exist") is False


class TestUserSessionServiceRefresh:
    """Tests for UserSessionService.refresh_session()."""

    def test_refresh_session(
        self, user_session_service: UserSessionService
    ):
        """Refresh extends session expiry."""
        # Create a session with short expiry (1 hour)
        session = user_session_service.create_session(
            user_id=unique_user_id(),
            idp_issuer="https://acme.okta.com",
            expires_in_hours=1,
        )
        original_expiry = session.expires_at

        # Refresh with more hours (4 hours from now)
        refreshed = user_session_service.refresh_session(
            session.session_id, additional_hours=4
        )

        assert refreshed is not None
        # Handle timezone-naive datetimes from SQLite
        refreshed_expiry = refreshed.expires_at
        if refreshed_expiry.tzinfo is None:
            refreshed_expiry = refreshed_expiry.replace(tzinfo=timezone.utc)
        if original_expiry.tzinfo is None:
            original_expiry = original_expiry.replace(tzinfo=timezone.utc)
        assert refreshed_expiry > original_expiry

    def test_refresh_nonexistent_session(
        self, user_session_service: UserSessionService
    ):
        """Refresh non-existent session returns None."""
        refreshed = user_session_service.refresh_session("usess-does-not-exist")
        assert refreshed is None

    def test_refresh_expired_session(
        self, user_session_service: UserSessionService, sample_session: UserSession
    ):
        """Cannot refresh an expired session."""
        sample_session.expires_at = datetime.now(timezone.utc) - timedelta(hours=1)
        user_session_service.db.commit()

        refreshed = user_session_service.refresh_session(sample_session.session_id)
        assert refreshed is None


class TestUserSessionServiceRevokeAll:
    """Tests for UserSessionService.revoke_all_user_sessions()."""

    def test_revoke_all_user_sessions(self, user_session_service: UserSessionService):
        """Revoke all sessions for a user."""
        user_id = unique_user_id()
        
        # Create multiple sessions
        user_session_service.create_session(
            user_id=user_id,
            idp_issuer="https://acme.okta.com",
        )
        user_session_service.create_session(
            user_id=user_id,
            idp_issuer="https://acme.okta.com",
        )

        count = user_session_service.revoke_all_user_sessions(user_id)

        assert count == 2
        
        # All sessions should be revoked
        sessions = user_session_service.get_sessions_by_user(user_id)
        assert len(sessions) == 0

    def test_revoke_all_user_sessions_no_sessions(
        self, user_session_service: UserSessionService
    ):
        """Revoke all for user with no sessions."""
        count = user_session_service.revoke_all_user_sessions(unique_user_id())
        assert count == 0
