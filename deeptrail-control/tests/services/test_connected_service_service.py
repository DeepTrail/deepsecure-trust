"""Unit tests for ConnectedServiceService.

Tests cover:
- Service connection (new and reconnection)
- Service disconnection
- Token retrieval for credential injection
- Connection queries
- Scope checking
- Token refresh
- Bulk operations
"""

import uuid
from datetime import datetime, timezone
from typing import Generator
from unittest.mock import MagicMock, patch

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.db.base import Base
from app.models.connected_service import ConnectedService
from app.services.connected_service_service import ConnectedServiceService
from app.services.vault_client import VaultClient


# ============================================================================
# Fixtures
# ============================================================================


@pytest.fixture(scope="function")
def db_session() -> Generator[Session, None, None]:
    """Create an in-memory SQLite database session for testing."""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(bind=engine)
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture
def vault() -> VaultClient:
    """Create a VaultClient with a test encryption key."""
    from cryptography.fernet import Fernet

    test_key = Fernet.generate_key().decode()
    return VaultClient(encryption_key=test_key)


@pytest.fixture
def service(vault: VaultClient, db_session: Session) -> ConnectedServiceService:
    """Create a ConnectedServiceService for testing."""
    return ConnectedServiceService(vault_client=vault, db_session=db_session)


@pytest.fixture
def sample_oauth_response() -> dict:
    """Sample OAuth token response."""
    return {
        "access_token": "test_access_token_abc123",
        "refresh_token": "test_refresh_token_xyz789",
        "expires_in": 3600,
        "token_type": "Bearer",
    }


def unique_user_id() -> str:
    """Generate a unique user ID for test isolation."""
    return f"testuser_{uuid.uuid4().hex[:8]}@example.com"


# ============================================================================
# Connect Service Tests
# ============================================================================


class TestConnectService:
    """Tests for connect_service method."""

    def test_connect_service_creates_record(
        self,
        service: ConnectedServiceService,
        db_session: Session,
        sample_oauth_response: dict,
    ):
        """connect_service should create a ConnectedService record."""
        user_id = unique_user_id()

        conn = service.connect_service(
            user_id=user_id,
            service_id="notion",
            oauth_response=sample_oauth_response,
            scopes_granted=["read_content", "search"],
        )
        db_session.commit()

        assert conn is not None
        assert conn.user_id == user_id
        assert conn.service_id == "notion"
        assert conn.scopes_granted == ["read_content", "search"]

    def test_connect_service_stores_token_in_vault(
        self,
        service: ConnectedServiceService,
        vault: VaultClient,
        db_session: Session,
        sample_oauth_response: dict,
    ):
        """connect_service should store OAuth token in vault."""
        user_id = unique_user_id()

        conn = service.connect_service(
            user_id=user_id,
            service_id="notion",
            oauth_response=sample_oauth_response,
            scopes_granted=["read"],
        )
        db_session.commit()

        # Token reference should point to vault
        assert conn.oauth_token_ref.startswith("vault://")

        # Token should be retrievable from vault (may include extra metadata)
        token = vault.retrieve_token(conn.oauth_token_ref)
        for key, value in sample_oauth_response.items():
            assert token[key] == value

    def test_connect_service_with_optional_fields(
        self,
        service: ConnectedServiceService,
        db_session: Session,
        sample_oauth_response: dict,
    ):
        """connect_service should support optional fields."""
        user_id = unique_user_id()

        conn = service.connect_service(
            user_id=user_id,
            service_id="slack",
            oauth_response=sample_oauth_response,
            scopes_granted=["chat:write"],
            service_name="Slack",
            organization_id="org-123",
        )
        db_session.commit()

        assert conn.service_name == "Slack"
        assert conn.organization_id == "org-123"

    def test_reconnect_updates_existing_record(
        self,
        service: ConnectedServiceService,
        db_session: Session,
        sample_oauth_response: dict,
    ):
        """Reconnecting should update existing record, not create new one."""
        user_id = unique_user_id()

        # First connection
        conn1 = service.connect_service(
            user_id=user_id,
            service_id="notion",
            oauth_response=sample_oauth_response,
            scopes_granted=["read"],
        )
        db_session.commit()
        conn1_id = conn1.id

        # Reconnect with new scopes
        new_response = {"access_token": "new_token", "refresh_token": "new_refresh"}
        conn2 = service.connect_service(
            user_id=user_id,
            service_id="notion",
            oauth_response=new_response,
            scopes_granted=["read", "write"],
        )
        db_session.commit()

        # Should be same record
        assert conn2.id == conn1_id
        assert conn2.scopes_granted == ["read", "write"]

    def test_reconnect_deletes_old_token(
        self,
        service: ConnectedServiceService,
        vault: VaultClient,
        db_session: Session,
        sample_oauth_response: dict,
    ):
        """Reconnecting should delete old token from vault."""
        user_id = unique_user_id()

        # First connection
        conn1 = service.connect_service(
            user_id=user_id,
            service_id="notion",
            oauth_response=sample_oauth_response,
            scopes_granted=["read"],
        )
        db_session.commit()
        old_token_ref = conn1.oauth_token_ref

        # Reconnect
        service.connect_service(
            user_id=user_id,
            service_id="notion",
            oauth_response={"access_token": "new"},
            scopes_granted=["read"],
        )
        db_session.commit()

        # Old token should be deleted
        assert vault.token_exists(old_token_ref) is False

    def test_reconnect_clears_disconnected_at(
        self,
        service: ConnectedServiceService,
        db_session: Session,
        sample_oauth_response: dict,
    ):
        """Reconnecting a disconnected service should clear disconnected_at."""
        user_id = unique_user_id()

        # Connect and disconnect
        service.connect_service(
            user_id=user_id,
            service_id="notion",
            oauth_response=sample_oauth_response,
            scopes_granted=["read"],
        )
        db_session.commit()
        service.disconnect_service(user_id, "notion")
        db_session.commit()

        # Reconnect
        conn = service.connect_service(
            user_id=user_id,
            service_id="notion",
            oauth_response=sample_oauth_response,
            scopes_granted=["read"],
        )
        db_session.commit()

        assert conn.disconnected_at is None
        assert conn.is_active is True


# ============================================================================
# Disconnect Service Tests
# ============================================================================


class TestDisconnectService:
    """Tests for disconnect_service method."""

    def test_disconnect_service_marks_as_disconnected(
        self,
        service: ConnectedServiceService,
        db_session: Session,
        sample_oauth_response: dict,
    ):
        """disconnect_service should set disconnected_at timestamp."""
        user_id = unique_user_id()

        service.connect_service(
            user_id=user_id,
            service_id="notion",
            oauth_response=sample_oauth_response,
            scopes_granted=["read"],
        )
        db_session.commit()

        result = service.disconnect_service(user_id, "notion")
        db_session.commit()

        assert result is True

        # Fetch fresh from DB
        conn = service.get_connection(user_id, "notion", include_disconnected=True)
        assert conn.disconnected_at is not None
        assert conn.is_active is False

    def test_disconnect_service_deletes_token(
        self,
        service: ConnectedServiceService,
        vault: VaultClient,
        db_session: Session,
        sample_oauth_response: dict,
    ):
        """disconnect_service should delete token from vault."""
        user_id = unique_user_id()

        conn = service.connect_service(
            user_id=user_id,
            service_id="notion",
            oauth_response=sample_oauth_response,
            scopes_granted=["read"],
        )
        db_session.commit()
        token_ref = conn.oauth_token_ref

        service.disconnect_service(user_id, "notion")
        db_session.commit()

        assert vault.token_exists(token_ref) is False

    def test_disconnect_nonexistent_returns_false(
        self,
        service: ConnectedServiceService,
    ):
        """disconnect_service should return False if connection not found."""
        result = service.disconnect_service("unknown@example.com", "notion")

        assert result is False

    def test_disconnect_already_disconnected_returns_true(
        self,
        service: ConnectedServiceService,
        db_session: Session,
        sample_oauth_response: dict,
    ):
        """Disconnecting already-disconnected service should return True."""
        user_id = unique_user_id()

        service.connect_service(
            user_id=user_id,
            service_id="notion",
            oauth_response=sample_oauth_response,
            scopes_granted=["read"],
        )
        db_session.commit()

        service.disconnect_service(user_id, "notion")
        db_session.commit()

        # Second disconnect
        result = service.disconnect_service(user_id, "notion")
        assert result is True


# ============================================================================
# Get Token Tests
# ============================================================================


class TestGetTokenForService:
    """Tests for get_token_for_service method."""

    def test_get_token_returns_oauth_data(
        self,
        service: ConnectedServiceService,
        db_session: Session,
        sample_oauth_response: dict,
    ):
        """get_token_for_service should return the OAuth token data."""
        user_id = unique_user_id()

        service.connect_service(
            user_id=user_id,
            service_id="notion",
            oauth_response=sample_oauth_response,
            scopes_granted=["read"],
        )
        db_session.commit()

        token = service.get_token_for_service(user_id, "notion")

        for key, value in sample_oauth_response.items():
            assert token[key] == value

    def test_get_token_returns_none_for_disconnected(
        self,
        service: ConnectedServiceService,
        db_session: Session,
        sample_oauth_response: dict,
    ):
        """get_token_for_service should return None for disconnected service."""
        user_id = unique_user_id()

        service.connect_service(
            user_id=user_id,
            service_id="notion",
            oauth_response=sample_oauth_response,
            scopes_granted=["read"],
        )
        db_session.commit()

        service.disconnect_service(user_id, "notion")
        db_session.commit()

        token = service.get_token_for_service(user_id, "notion")

        assert token is None

    def test_get_token_returns_none_for_nonexistent(
        self,
        service: ConnectedServiceService,
    ):
        """get_token_for_service should return None if not connected."""
        token = service.get_token_for_service("unknown@example.com", "notion")

        assert token is None

    def test_get_token_updates_last_used_at(
        self,
        service: ConnectedServiceService,
        db_session: Session,
        sample_oauth_response: dict,
    ):
        """get_token_for_service should update last_used_at timestamp."""
        user_id = unique_user_id()

        conn = service.connect_service(
            user_id=user_id,
            service_id="notion",
            oauth_response=sample_oauth_response,
            scopes_granted=["read"],
        )
        db_session.commit()

        assert conn.last_used_at is None

        service.get_token_for_service(user_id, "notion")

        # Note: last_used_at is set but not committed by get_token
        assert conn.last_used_at is not None


# ============================================================================
# Connection Query Tests
# ============================================================================


class TestConnectionQueries:
    """Tests for connection query methods."""

    def test_get_connection_returns_active(
        self,
        service: ConnectedServiceService,
        db_session: Session,
        sample_oauth_response: dict,
    ):
        """get_connection should return active connection."""
        user_id = unique_user_id()

        service.connect_service(
            user_id=user_id,
            service_id="notion",
            oauth_response=sample_oauth_response,
            scopes_granted=["read"],
        )
        db_session.commit()

        conn = service.get_connection(user_id, "notion")

        assert conn is not None
        assert conn.service_id == "notion"

    def test_get_connection_excludes_disconnected_by_default(
        self,
        service: ConnectedServiceService,
        db_session: Session,
        sample_oauth_response: dict,
    ):
        """get_connection should exclude disconnected by default."""
        user_id = unique_user_id()

        service.connect_service(
            user_id=user_id,
            service_id="notion",
            oauth_response=sample_oauth_response,
            scopes_granted=["read"],
        )
        db_session.commit()
        service.disconnect_service(user_id, "notion")
        db_session.commit()

        conn = service.get_connection(user_id, "notion")

        assert conn is None

    def test_get_connection_includes_disconnected_when_asked(
        self,
        service: ConnectedServiceService,
        db_session: Session,
        sample_oauth_response: dict,
    ):
        """get_connection should include disconnected when requested."""
        user_id = unique_user_id()

        service.connect_service(
            user_id=user_id,
            service_id="notion",
            oauth_response=sample_oauth_response,
            scopes_granted=["read"],
        )
        db_session.commit()
        service.disconnect_service(user_id, "notion")
        db_session.commit()

        conn = service.get_connection(user_id, "notion", include_disconnected=True)

        assert conn is not None

    def test_get_user_connections_returns_all_active(
        self,
        service: ConnectedServiceService,
        db_session: Session,
        sample_oauth_response: dict,
    ):
        """get_user_connections should return all active connections."""
        user_id = unique_user_id()

        service.connect_service(
            user_id=user_id,
            service_id="notion",
            oauth_response=sample_oauth_response,
            scopes_granted=["read"],
        )
        service.connect_service(
            user_id=user_id,
            service_id="slack",
            oauth_response=sample_oauth_response,
            scopes_granted=["chat"],
        )
        db_session.commit()

        connections = service.get_user_connections(user_id)

        assert len(connections) == 2
        service_ids = {c.service_id for c in connections}
        assert service_ids == {"notion", "slack"}

    def test_get_organization_connections(
        self,
        service: ConnectedServiceService,
        db_session: Session,
        sample_oauth_response: dict,
    ):
        """get_organization_connections should return org connections."""
        org_id = f"org-{uuid.uuid4().hex[:8]}"

        service.connect_service(
            user_id=unique_user_id(),
            service_id="notion",
            oauth_response=sample_oauth_response,
            scopes_granted=["read"],
            organization_id=org_id,
        )
        service.connect_service(
            user_id=unique_user_id(),
            service_id="slack",
            oauth_response=sample_oauth_response,
            scopes_granted=["chat"],
            organization_id=org_id,
        )
        db_session.commit()

        connections = service.get_organization_connections(org_id)

        assert len(connections) == 2


# ============================================================================
# Is Connected Tests
# ============================================================================


class TestIsConnected:
    """Tests for is_connected method."""

    def test_is_connected_true_when_active(
        self,
        service: ConnectedServiceService,
        db_session: Session,
        sample_oauth_response: dict,
    ):
        """is_connected should return True for active connection."""
        user_id = unique_user_id()

        service.connect_service(
            user_id=user_id,
            service_id="notion",
            oauth_response=sample_oauth_response,
            scopes_granted=["read"],
        )
        db_session.commit()

        assert service.is_connected(user_id, "notion") is True

    def test_is_connected_false_when_disconnected(
        self,
        service: ConnectedServiceService,
        db_session: Session,
        sample_oauth_response: dict,
    ):
        """is_connected should return False for disconnected service."""
        user_id = unique_user_id()

        service.connect_service(
            user_id=user_id,
            service_id="notion",
            oauth_response=sample_oauth_response,
            scopes_granted=["read"],
        )
        db_session.commit()
        service.disconnect_service(user_id, "notion")
        db_session.commit()

        assert service.is_connected(user_id, "notion") is False

    def test_is_connected_false_when_never_connected(
        self,
        service: ConnectedServiceService,
    ):
        """is_connected should return False if never connected."""
        assert service.is_connected("unknown@example.com", "notion") is False


# ============================================================================
# Scope Checking Tests
# ============================================================================


class TestHasScope:
    """Tests for has_scope method."""

    def test_has_scope_true_when_granted(
        self,
        service: ConnectedServiceService,
        db_session: Session,
        sample_oauth_response: dict,
    ):
        """has_scope should return True for granted scopes."""
        user_id = unique_user_id()

        service.connect_service(
            user_id=user_id,
            service_id="notion",
            oauth_response=sample_oauth_response,
            scopes_granted=["read_content", "search"],
        )
        db_session.commit()

        assert service.has_scope(user_id, "notion", "read_content") is True
        assert service.has_scope(user_id, "notion", "search") is True

    def test_has_scope_false_when_not_granted(
        self,
        service: ConnectedServiceService,
        db_session: Session,
        sample_oauth_response: dict,
    ):
        """has_scope should return False for non-granted scopes."""
        user_id = unique_user_id()

        service.connect_service(
            user_id=user_id,
            service_id="notion",
            oauth_response=sample_oauth_response,
            scopes_granted=["read_content"],
        )
        db_session.commit()

        assert service.has_scope(user_id, "notion", "write") is False

    def test_has_scope_false_when_not_connected(
        self,
        service: ConnectedServiceService,
    ):
        """has_scope should return False if not connected."""
        assert service.has_scope("unknown@example.com", "notion", "read") is False


# ============================================================================
# Token Refresh Tests
# ============================================================================


class TestRefreshToken:
    """Tests for refresh_token method."""

    def test_refresh_token_updates_stored_token(
        self,
        service: ConnectedServiceService,
        vault: VaultClient,
        db_session: Session,
        sample_oauth_response: dict,
    ):
        """refresh_token should update the stored token data."""
        user_id = unique_user_id()

        conn = service.connect_service(
            user_id=user_id,
            service_id="notion",
            oauth_response=sample_oauth_response,
            scopes_granted=["read"],
        )
        db_session.commit()

        new_token = {
            "access_token": "refreshed_token",
            "refresh_token": "new_refresh",
            "expires_in": 7200,
        }

        result = service.refresh_token(user_id, "notion", new_token)

        assert result is True

        # Verify token was updated in vault (may include extra metadata)
        retrieved = vault.retrieve_token(conn.oauth_token_ref)
        for key, value in new_token.items():
            assert retrieved[key] == value

    def test_refresh_token_returns_false_when_not_connected(
        self,
        service: ConnectedServiceService,
    ):
        """refresh_token should return False if not connected."""
        result = service.refresh_token(
            "unknown@example.com",
            "notion",
            {"access_token": "new"},
        )

        assert result is False


# ============================================================================
# Bulk Operations Tests
# ============================================================================


class TestBulkOperations:
    """Tests for bulk operations."""

    def test_disconnect_all_user_services(
        self,
        service: ConnectedServiceService,
        db_session: Session,
        sample_oauth_response: dict,
    ):
        """disconnect_all_user_services should disconnect all user services."""
        user_id = unique_user_id()

        service.connect_service(
            user_id=user_id,
            service_id="notion",
            oauth_response=sample_oauth_response,
            scopes_granted=["read"],
        )
        service.connect_service(
            user_id=user_id,
            service_id="slack",
            oauth_response=sample_oauth_response,
            scopes_granted=["chat"],
        )
        service.connect_service(
            user_id=user_id,
            service_id="gdrive",
            oauth_response=sample_oauth_response,
            scopes_granted=["contacts"],
        )
        db_session.commit()

        count = service.disconnect_all_user_services(user_id)
        db_session.commit()

        assert count == 3

        # All should be disconnected
        connections = service.get_user_connections(user_id)
        assert len(connections) == 0

    def test_disconnect_all_returns_zero_for_no_connections(
        self,
        service: ConnectedServiceService,
    ):
        """disconnect_all_user_services should return 0 if no connections."""
        count = service.disconnect_all_user_services("noconnections@example.com")

        assert count == 0


# ============================================================================
# Integration Tests
# ============================================================================


class TestIntegration:
    """Integration tests for full connect/disconnect flow."""

    def test_full_connect_disconnect_reconnect_flow(
        self,
        service: ConnectedServiceService,
        vault: VaultClient,
        db_session: Session,
        sample_oauth_response: dict,
    ):
        """Test complete lifecycle of a service connection."""
        user_id = unique_user_id()

        # 1. Connect
        conn1 = service.connect_service(
            user_id=user_id,
            service_id="notion",
            oauth_response=sample_oauth_response,
            scopes_granted=["read", "write"],
        )
        db_session.commit()

        assert service.is_connected(user_id, "notion")
        token1 = service.get_token_for_service(user_id, "notion")
        for key, value in sample_oauth_response.items():
            assert token1[key] == value

        # 2. Disconnect
        service.disconnect_service(user_id, "notion")
        db_session.commit()

        assert not service.is_connected(user_id, "notion")
        assert service.get_token_for_service(user_id, "notion") is None

        # 3. Reconnect with new token
        new_response = {"access_token": "new_token", "expires_in": 7200}
        conn2 = service.connect_service(
            user_id=user_id,
            service_id="notion",
            oauth_response=new_response,
            scopes_granted=["read"],
        )
        db_session.commit()

        # Same record, updated data
        assert conn2.id == conn1.id
        assert service.is_connected(user_id, "notion")
        token2 = service.get_token_for_service(user_id, "notion")
        for key, value in new_response.items():
            assert token2[key] == value
