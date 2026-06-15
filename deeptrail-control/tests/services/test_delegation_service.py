"""Unit tests for DelegationService.

Tests cover:
- Delegation creation with permission validation (monotonic attenuation)
- Delegation validation (expiry, revocation)
- Delegation revocation
- Delegation queries (by user, by agent, active)
- Permission checking
- Constraint retrieval
- Bulk revocation operations
"""

import uuid
from datetime import datetime, timedelta, timezone
from typing import Generator

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.db.base import Base
from app.models.connected_service import ConnectedService
from app.models.delegation import DelegationToken
from app.models.agent_session import AgentSession, PartyType
from app.services.delegation_service import (
    DelegationForbiddenError,
    DelegationInvalidStateError,
    DelegationNotFoundError,
    DelegationService,
    PermissionValidationError,
    PermissionWideningError,
)


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
def service(db_session: Session) -> DelegationService:
    """Create a DelegationService for testing."""
    return DelegationService(db_session=db_session)


def unique_user_id() -> str:
    """Generate a unique user ID for test isolation."""
    return f"user_{uuid.uuid4().hex[:8]}@example.com"


def unique_agent_id() -> str:
    """Generate a unique agent ID for test isolation."""
    return f"agent-{uuid.uuid4().hex[:8]}"


def create_connected_service(
    db_session: Session,
    user_id: str,
    service_id: str,
    scopes: list[str],
) -> ConnectedService:
    """Helper to create a connected service for testing."""
    conn = ConnectedService(
        user_id=user_id,
        service_id=service_id,
        oauth_token_ref=f"vault://{user_id}-{service_id}-test",
        scopes_granted=scopes,
    )
    db_session.add(conn)
    db_session.commit()
    return conn


# ============================================================================
# Create Delegation Tests
# ============================================================================


class TestCreateDelegation:
    """Tests for create_delegation method."""

    def test_create_delegation_success(
        self,
        service: DelegationService,
        db_session: Session,
    ):
        """create_delegation should create a valid delegation."""
        user_id = unique_user_id()
        agent_id = unique_agent_id()

        # Create connected service with scopes that map to permissions
        create_connected_service(
            db_session, user_id, "notion", ["read_pages"]
        )

        delegation = service.create_delegation(
            delegator=user_id,
            agent_id=agent_id,
            permissions=["notion:pages:search", "notion:pages:read"],
        )
        db_session.commit()

        assert delegation is not None
        assert delegation.delegator == user_id
        assert delegation.agent_id == agent_id
        assert delegation.is_valid is True

    def test_create_delegation_with_constraints(
        self,
        service: DelegationService,
        db_session: Session,
    ):
        """create_delegation should store constraints."""
        user_id = unique_user_id()
        agent_id = unique_agent_id()

        create_connected_service(db_session, user_id, "notion", ["read_pages"])

        delegation = service.create_delegation(
            delegator=user_id,
            agent_id=agent_id,
            permissions=["notion:pages:search"],
            constraints={"max_actions_per_day": 100, "rate_limit": "10/min"},
        )
        db_session.commit()

        assert delegation.constraints == {
            "max_actions_per_day": 100,
            "rate_limit": "10/min",
        }
        assert delegation.get_constraint("max_actions_per_day") == 100

    def test_create_delegation_with_custom_expiry(
        self,
        service: DelegationService,
        db_session: Session,
    ):
        """create_delegation should support custom expiry."""
        user_id = unique_user_id()
        agent_id = unique_agent_id()

        create_connected_service(db_session, user_id, "slack", ["search:read"])

        delegation = service.create_delegation(
            delegator=user_id,
            agent_id=agent_id,
            permissions=["slack:messages:search"],
            expires_in_days=30,
        )
        db_session.commit()

        # Should expire in ~30 days
        expected_expiry = datetime.now(timezone.utc) + timedelta(days=30)
        actual_expiry = delegation.expires_at
        if actual_expiry.tzinfo is None:
            actual_expiry = actual_expiry.replace(tzinfo=timezone.utc)

        delta = abs((actual_expiry - expected_expiry).total_seconds())
        assert delta < 60  # Within 1 minute

    def test_create_delegation_with_idp(
        self,
        service: DelegationService,
        db_session: Session,
    ):
        """create_delegation should store delegator IDP."""
        user_id = unique_user_id()
        agent_id = unique_agent_id()

        create_connected_service(db_session, user_id, "notion", ["read_pages"])

        delegation = service.create_delegation(
            delegator=user_id,
            agent_id=agent_id,
            permissions=["notion:pages:search"],
            delegator_idp="https://acme.okta.com",
        )
        db_session.commit()

        assert delegation.delegator_idp == "https://acme.okta.com"

    def test_create_delegation_generates_token_hashes(
        self,
        service: DelegationService,
        db_session: Session,
    ):
        """create_delegation should generate token binding hashes."""
        user_id = unique_user_id()
        agent_id = unique_agent_id()

        create_connected_service(db_session, user_id, "notion", ["read_pages"])

        delegation = service.create_delegation(
            delegator=user_id,
            agent_id=agent_id,
            permissions=["notion:pages:search"],
        )
        db_session.commit()

        assert delegation.user_token_hash is not None
        assert delegation.user_token_hash.startswith("sha256:")
        assert delegation.agent_token_hash is not None
        assert delegation.agent_token_hash.startswith("sha256:")

    def test_create_delegation_generates_revocation_uri(
        self,
        service: DelegationService,
        db_session: Session,
    ):
        """create_delegation should generate revocation URI."""
        user_id = unique_user_id()
        agent_id = unique_agent_id()

        create_connected_service(db_session, user_id, "notion", ["read_pages"])

        delegation = service.create_delegation(
            delegator=user_id,
            agent_id=agent_id,
            permissions=["notion:pages:search"],
        )
        db_session.commit()

        assert delegation.revocation_uri is not None
        assert "revoke" in delegation.revocation_uri
        assert delegation.id in delegation.revocation_uri

    def test_create_delegation_revokes_existing(
        self,
        service: DelegationService,
        db_session: Session,
    ):
        """create_delegation should revoke existing delegation for same user-agent."""
        user_id = unique_user_id()
        agent_id = unique_agent_id()

        create_connected_service(
            db_session, user_id, "notion", ["read_pages"]
        )

        # Create first delegation
        first = service.create_delegation(
            delegator=user_id,
            agent_id=agent_id,
            permissions=["notion:pages:search"],
        )
        db_session.commit()
        first_id = first.id

        # Create second delegation (should revoke first)
        second = service.create_delegation(
            delegator=user_id,
            agent_id=agent_id,
            permissions=["notion:pages:read"],
        )
        db_session.commit()

        # First should be revoked
        first_updated = service.get_delegation(first_id)
        assert first_updated.is_revoked is True

        # Second should be valid
        assert second.is_valid is True


# ============================================================================
# Permission Validation Tests (Monotonic Attenuation)
# ============================================================================


class TestPermissionValidation:
    """Tests for monotonic attenuation (permission validation)."""

    def test_rejects_unconnected_service(
        self,
        service: DelegationService,
        db_session: Session,
    ):
        """Should reject permissions for unconnected service."""
        user_id = unique_user_id()
        agent_id = unique_agent_id()

        # User has Notion but not Gmail
        create_connected_service(db_session, user_id, "notion", ["read_pages"])

        with pytest.raises(PermissionValidationError, match="not allowed"):
            service.create_delegation(
                delegator=user_id,
                agent_id=agent_id,
                permissions=["gmail:messages:read"],
            )

    def test_rejects_when_no_connections(
        self,
        service: DelegationService,
        db_session: Session,
    ):
        """Should reject when user has no connected services."""
        user_id = unique_user_id()
        agent_id = unique_agent_id()

        with pytest.raises(PermissionValidationError, match="no connected services"):
            service.create_delegation(
                delegator=user_id,
                agent_id=agent_id,
                permissions=["notion:pages:search"],
            )

    def test_allows_permissions_for_connected_service(
        self,
        service: DelegationService,
        db_session: Session,
    ):
        """Should allow permissions for connected services."""
        user_id = unique_user_id()
        agent_id = unique_agent_id()

        create_connected_service(
            db_session, user_id, "notion", ["read_pages"]
        )
        create_connected_service(
            db_session, user_id, "slack", ["search:read", "chat:write"]
        )

        # Should succeed - user has both services
        delegation = service.create_delegation(
            delegator=user_id,
            agent_id=agent_id,
            permissions=["notion:pages:search", "slack:messages:search"],
        )
        db_session.commit()

        assert delegation is not None

    def test_rejects_invalid_permission_format(
        self,
        service: DelegationService,
        db_session: Session,
    ):
        """Should reject malformed permission strings (treated as not allowed)."""
        user_id = unique_user_id()
        agent_id = unique_agent_id()

        create_connected_service(db_session, user_id, "notion", ["read_pages"])

        with pytest.raises(PermissionValidationError, match="not allowed"):
            service.create_delegation(
                delegator=user_id,
                agent_id=agent_id,
                permissions=["invalid"],  # Missing service:resource:action
            )


# ============================================================================
# Validate Delegation Tests
# ============================================================================


class TestValidateDelegation:
    """Tests for validate_delegation method."""

    def test_valid_delegation(
        self,
        service: DelegationService,
        db_session: Session,
    ):
        """validate_delegation should return is_valid=True for valid delegation."""
        user_id = unique_user_id()
        agent_id = unique_agent_id()

        create_connected_service(db_session, user_id, "notion", ["read_pages"])
        delegation = service.create_delegation(
            delegator=user_id,
            agent_id=agent_id,
            permissions=["notion:pages:search"],
        )
        db_session.commit()

        result = service.validate_delegation(str(delegation.id))

        assert result.is_valid is True
        assert result.reason is None
        assert result.delegation is not None

    def test_nonexistent_delegation(
        self,
        service: DelegationService,
    ):
        """validate_delegation should return is_valid=False for unknown ID."""
        result = service.validate_delegation("del-nonexistent-id")

        assert result.is_valid is False
        assert "not found" in result.reason.lower()

    def test_revoked_delegation(
        self,
        service: DelegationService,
        db_session: Session,
    ):
        """validate_delegation should return is_valid=False for revoked delegation."""
        user_id = unique_user_id()
        agent_id = unique_agent_id()

        create_connected_service(db_session, user_id, "notion", ["read_pages"])
        delegation = service.create_delegation(
            delegator=user_id,
            agent_id=agent_id,
            permissions=["notion:pages:search"],
        )
        db_session.commit()

        service.revoke_delegation(str(delegation.id))
        db_session.commit()

        result = service.validate_delegation(str(delegation.id))

        assert result.is_valid is False
        assert "revoked" in result.reason.lower()
        assert result.delegation is not None

    def test_expired_delegation(
        self,
        service: DelegationService,
        db_session: Session,
    ):
        """validate_delegation should return is_valid=False for expired delegation."""
        user_id = unique_user_id()
        agent_id = unique_agent_id()

        create_connected_service(db_session, user_id, "notion", ["read_pages"])

        # Create delegation that's already expired
        delegation = DelegationToken(
            agent_id=agent_id,
            delegator=user_id,
            delegated_permissions=["notion:pages:search"],
            expires_at=datetime.now(timezone.utc) - timedelta(days=1),
        )
        db_session.add(delegation)
        db_session.commit()

        result = service.validate_delegation(str(delegation.id))

        assert result.is_valid is False
        assert "expired" in result.reason.lower()


# ============================================================================
# Revoke Delegation Tests
# ============================================================================


class TestRevokeDelegation:
    """Tests for revoke_delegation method."""

    def test_revoke_delegation_success(
        self,
        service: DelegationService,
        db_session: Session,
    ):
        """revoke_delegation should mark delegation as revoked."""
        user_id = unique_user_id()
        agent_id = unique_agent_id()

        create_connected_service(db_session, user_id, "notion", ["read_pages"])
        delegation = service.create_delegation(
            delegator=user_id,
            agent_id=agent_id,
            permissions=["notion:pages:search"],
        )
        db_session.commit()

        result = service.revoke_delegation(str(delegation.id))

        assert result is True
        assert delegation.is_revoked is True
        assert delegation.revoked_at is not None

    def test_revoke_nonexistent_returns_false(
        self,
        service: DelegationService,
    ):
        """revoke_delegation should return False for unknown ID."""
        result = service.revoke_delegation("del-nonexistent-id")

        assert result is False

    def test_revoke_already_revoked_returns_true(
        self,
        service: DelegationService,
        db_session: Session,
    ):
        """revoke_delegation should return True for already revoked."""
        user_id = unique_user_id()
        agent_id = unique_agent_id()

        create_connected_service(db_session, user_id, "notion", ["read_pages"])
        delegation = service.create_delegation(
            delegator=user_id,
            agent_id=agent_id,
            permissions=["notion:pages:search"],
        )
        db_session.commit()

        service.revoke_delegation(str(delegation.id))
        result = service.revoke_delegation(str(delegation.id))

        assert result is True


# ============================================================================
# Query Tests
# ============================================================================


class TestDelegationQueries:
    """Tests for delegation query methods."""

    def test_get_delegation(
        self,
        service: DelegationService,
        db_session: Session,
    ):
        """get_delegation should return delegation by ID."""
        user_id = unique_user_id()
        agent_id = unique_agent_id()

        create_connected_service(db_session, user_id, "notion", ["read_pages"])
        delegation = service.create_delegation(
            delegator=user_id,
            agent_id=agent_id,
            permissions=["notion:pages:search"],
        )
        db_session.commit()

        retrieved = service.get_delegation(str(delegation.id))

        assert retrieved is not None
        assert retrieved.id == delegation.id

    def test_get_delegation_returns_none(
        self,
        service: DelegationService,
    ):
        """get_delegation should return None for unknown ID."""
        result = service.get_delegation("del-nonexistent")

        assert result is None

    def test_get_delegations_for_user(
        self,
        service: DelegationService,
        db_session: Session,
    ):
        """get_delegations_for_user should return user's delegations."""
        user_id = unique_user_id()

        create_connected_service(db_session, user_id, "notion", ["read_pages"])
        create_connected_service(db_session, user_id, "slack", ["search:read"])

        service.create_delegation(
            delegator=user_id,
            agent_id=unique_agent_id(),
            permissions=["notion:pages:search"],
        )
        service.create_delegation(
            delegator=user_id,
            agent_id=unique_agent_id(),
            permissions=["slack:messages:search"],
        )
        db_session.commit()

        delegations = service.get_delegations_for_user(user_id)

        assert len(delegations) == 2

    def test_get_delegations_for_user_excludes_revoked(
        self,
        service: DelegationService,
        db_session: Session,
    ):
        """get_delegations_for_user should exclude revoked by default."""
        user_id = unique_user_id()

        create_connected_service(db_session, user_id, "notion", ["read_pages"])

        d1 = service.create_delegation(
            delegator=user_id,
            agent_id=unique_agent_id(),
            permissions=["notion:pages:search"],
        )
        service.create_delegation(
            delegator=user_id,
            agent_id=unique_agent_id(),
            permissions=["notion:pages:search"],
        )
        db_session.commit()

        service.revoke_delegation(str(d1.id))
        db_session.commit()

        delegations = service.get_delegations_for_user(user_id)
        assert len(delegations) == 1

        # Include revoked
        all_delegations = service.get_delegations_for_user(user_id, include_revoked=True)
        assert len(all_delegations) == 2

    def test_get_delegations_for_agent(
        self,
        service: DelegationService,
        db_session: Session,
    ):
        """get_delegations_for_agent should return agent's delegations."""
        agent_id = unique_agent_id()

        user1 = unique_user_id()
        user2 = unique_user_id()

        create_connected_service(db_session, user1, "notion", ["read_pages"])
        create_connected_service(db_session, user2, "slack", ["search:read"])

        service.create_delegation(
            delegator=user1,
            agent_id=agent_id,
            permissions=["notion:pages:search"],
        )
        service.create_delegation(
            delegator=user2,
            agent_id=agent_id,
            permissions=["slack:messages:search"],
        )
        db_session.commit()

        delegations = service.get_delegations_for_agent(agent_id)

        assert len(delegations) == 2

    def test_get_active_delegation(
        self,
        service: DelegationService,
        db_session: Session,
    ):
        """get_active_delegation should return active delegation."""
        user_id = unique_user_id()
        agent_id = unique_agent_id()

        create_connected_service(db_session, user_id, "notion", ["read_pages"])
        service.create_delegation(
            delegator=user_id,
            agent_id=agent_id,
            permissions=["notion:pages:search"],
        )
        db_session.commit()

        active = service.get_active_delegation(user_id, agent_id)

        assert active is not None
        assert active.is_valid is True

    def test_get_active_delegation_returns_none_when_revoked(
        self,
        service: DelegationService,
        db_session: Session,
    ):
        """get_active_delegation should return None for revoked."""
        user_id = unique_user_id()
        agent_id = unique_agent_id()

        create_connected_service(db_session, user_id, "notion", ["read_pages"])
        delegation = service.create_delegation(
            delegator=user_id,
            agent_id=agent_id,
            permissions=["notion:pages:search"],
        )
        db_session.commit()

        service.revoke_delegation(str(delegation.id))
        db_session.commit()

        active = service.get_active_delegation(user_id, agent_id)

        assert active is None

    def test_get_active_delegation_returns_none_for_unknown(
        self,
        service: DelegationService,
    ):
        """get_active_delegation should return None when none exists."""
        result = service.get_active_delegation("unknown@user.com", "unknown-agent")

        assert result is None


# ============================================================================
# Permission Checking Tests
# ============================================================================


class TestHasPermission:
    """Tests for has_permission method."""

    def test_has_permission_true(
        self,
        service: DelegationService,
        db_session: Session,
    ):
        """has_permission should return True for delegated permission."""
        user_id = unique_user_id()
        agent_id = unique_agent_id()

        create_connected_service(db_session, user_id, "notion", ["read_pages"])
        delegation = service.create_delegation(
            delegator=user_id,
            agent_id=agent_id,
            permissions=["notion:pages:search"],
        )
        db_session.commit()

        assert service.has_permission(str(delegation.id), "notion:pages:search") is True

    def test_has_permission_false_for_non_delegated(
        self,
        service: DelegationService,
        db_session: Session,
    ):
        """has_permission should return False for non-delegated permission."""
        user_id = unique_user_id()
        agent_id = unique_agent_id()

        create_connected_service(db_session, user_id, "notion", ["read_pages"])
        delegation = service.create_delegation(
            delegator=user_id,
            agent_id=agent_id,
            permissions=["notion:pages:search"],
        )
        db_session.commit()

        assert service.has_permission(str(delegation.id), "notion:pages:create") is False

    def test_has_permission_false_for_revoked(
        self,
        service: DelegationService,
        db_session: Session,
    ):
        """has_permission should return False for revoked delegation."""
        user_id = unique_user_id()
        agent_id = unique_agent_id()

        create_connected_service(db_session, user_id, "notion", ["read_pages"])
        delegation = service.create_delegation(
            delegator=user_id,
            agent_id=agent_id,
            permissions=["notion:pages:search"],
        )
        db_session.commit()

        service.revoke_delegation(str(delegation.id))
        db_session.commit()

        assert service.has_permission(str(delegation.id), "notion:pages:search") is False

    def test_has_permission_false_for_unknown(
        self,
        service: DelegationService,
    ):
        """has_permission should return False for unknown delegation."""
        assert service.has_permission("del-unknown", "any:permission") is False


# ============================================================================
# Get Permissions Tests
# ============================================================================


class TestGetPermissionsForAgent:
    """Tests for get_permissions_for_agent method."""

    def test_get_all_permissions(
        self,
        service: DelegationService,
        db_session: Session,
    ):
        """get_permissions_for_agent should return all permissions."""
        user_id = unique_user_id()
        agent_id = unique_agent_id()

        create_connected_service(
            db_session, user_id, "notion", ["read_pages"]
        )
        service.create_delegation(
            delegator=user_id,
            agent_id=agent_id,
            permissions=["notion:pages:search", "notion:pages:read"],
        )
        db_session.commit()

        permissions = service.get_permissions_for_agent(user_id, agent_id)

        assert len(permissions) == 2
        assert "notion:pages:search" in permissions
        assert "notion:pages:read" in permissions

    def test_get_permissions_filtered_by_service(
        self,
        service: DelegationService,
        db_session: Session,
    ):
        """get_permissions_for_agent should filter by service."""
        user_id = unique_user_id()
        agent_id = unique_agent_id()

        create_connected_service(db_session, user_id, "notion", ["read_pages"])
        create_connected_service(db_session, user_id, "slack", ["search:read"])

        service.create_delegation(
            delegator=user_id,
            agent_id=agent_id,
            permissions=["notion:pages:search", "slack:messages:search"],
        )
        db_session.commit()

        notion_perms = service.get_permissions_for_agent(user_id, agent_id, service="notion")

        assert len(notion_perms) == 1
        assert "notion:pages:search" in notion_perms

    def test_get_permissions_returns_empty_when_no_delegation(
        self,
        service: DelegationService,
    ):
        """get_permissions_for_agent should return empty list when none exists."""
        permissions = service.get_permissions_for_agent("unknown@user.com", "unknown-agent")

        assert permissions == []


# ============================================================================
# Bulk Revocation Tests
# ============================================================================


class TestBulkRevocation:
    """Tests for bulk revocation methods."""

    def test_revoke_all_for_user(
        self,
        service: DelegationService,
        db_session: Session,
    ):
        """revoke_all_for_user should revoke all user's delegations."""
        user_id = unique_user_id()

        create_connected_service(db_session, user_id, "notion", ["read_pages"])
        create_connected_service(db_session, user_id, "slack", ["search:read"])

        service.create_delegation(
            delegator=user_id,
            agent_id=unique_agent_id(),
            permissions=["notion:pages:search"],
        )
        service.create_delegation(
            delegator=user_id,
            agent_id=unique_agent_id(),
            permissions=["slack:messages:search"],
        )
        db_session.commit()

        count = service.revoke_all_for_user(user_id)
        db_session.commit()

        assert count == 2

        # All should be revoked
        active = service.get_delegations_for_user(user_id)
        assert len(active) == 0

    def test_revoke_all_for_agent(
        self,
        service: DelegationService,
        db_session: Session,
    ):
        """revoke_all_for_agent should revoke all agent's delegations."""
        agent_id = unique_agent_id()

        user1 = unique_user_id()
        user2 = unique_user_id()

        create_connected_service(db_session, user1, "notion", ["read_pages"])
        create_connected_service(db_session, user2, "slack", ["search:read"])

        service.create_delegation(
            delegator=user1,
            agent_id=agent_id,
            permissions=["notion:pages:search"],
        )
        service.create_delegation(
            delegator=user2,
            agent_id=agent_id,
            permissions=["slack:messages:search"],
        )
        db_session.commit()

        count = service.revoke_all_for_agent(agent_id)
        db_session.commit()

        assert count == 2

        # All should be revoked
        active = service.get_delegations_for_agent(agent_id)
        assert len(active) == 0


# ============================================================================
# Constraint Tests
# ============================================================================


class TestConstraints:
    """Tests for constraint retrieval."""

    def test_get_constraint(
        self,
        service: DelegationService,
        db_session: Session,
    ):
        """get_constraint should return constraint value."""
        user_id = unique_user_id()
        agent_id = unique_agent_id()

        create_connected_service(db_session, user_id, "notion", ["read_pages"])
        delegation = service.create_delegation(
            delegator=user_id,
            agent_id=agent_id,
            permissions=["notion:pages:search"],
            constraints={"max_actions_per_day": 100},
        )
        db_session.commit()

        value = service.get_constraint(str(delegation.id), "max_actions_per_day")

        assert value == 100

    def test_get_constraint_default(
        self,
        service: DelegationService,
        db_session: Session,
    ):
        """get_constraint should return default for missing constraint."""
        user_id = unique_user_id()
        agent_id = unique_agent_id()

        create_connected_service(db_session, user_id, "notion", ["read_pages"])
        delegation = service.create_delegation(
            delegator=user_id,
            agent_id=agent_id,
            permissions=["notion:pages:search"],
        )
        db_session.commit()

        value = service.get_constraint(str(delegation.id), "nonexistent", default=50)

        assert value == 50

    def test_get_constraint_unknown_delegation(
        self,
        service: DelegationService,
    ):
        """get_constraint should return default for unknown delegation."""
        value = service.get_constraint("del-unknown", "any_key", default=0)

        assert value == 0


# ============================================================================
# PATCH Delegation Permissions
# ============================================================================


class TestPatchDelegationPermissions:
    """Tests for patch_delegation_permissions (monotonic narrowing)."""

    def test_patch_narrows_permissions(self, service: DelegationService, db_session: Session):
        user_id = unique_user_id()
        agent_id = unique_agent_id()
        create_connected_service(
            db_session, user_id, "notion", ["read_pages", "search_content"]
        )
        delegation = service.create_delegation(
            delegator=user_id,
            agent_id=agent_id,
            permissions=["notion:pages:read", "notion:pages:search"],
        )
        db_session.commit()

        result = service.patch_delegation_permissions(
            str(delegation.id),
            user_id,
            new_permissions=["notion:pages:read"],
        )

        assert result.delegation.delegated_permissions == ["notion:pages:read"]
        assert result.sessions_revoked == 0

    def test_patch_widening_rejected(self, service: DelegationService, db_session: Session):
        user_id = unique_user_id()
        agent_id = unique_agent_id()
        create_connected_service(db_session, user_id, "notion", ["read_pages"])
        delegation = service.create_delegation(
            delegator=user_id,
            agent_id=agent_id,
            permissions=["notion:pages:read"],
        )
        db_session.commit()

        with pytest.raises(PermissionWideningError) as exc_info:
            service.patch_delegation_permissions(
                str(delegation.id),
                user_id,
                new_permissions=["notion:pages:read", "notion:pages:search"],
            )
        assert exc_info.value.message == "permission_widening_not_allowed"

    def test_patch_revokes_agent_sessions(self, service: DelegationService, db_session: Session):
        user_id = unique_user_id()
        agent_id = unique_agent_id()
        create_connected_service(db_session, user_id, "notion", ["read_pages"])
        delegation = service.create_delegation(
            delegator=user_id,
            agent_id=agent_id,
            permissions=["notion:pages:read", "notion:pages:search"],
        )
        session = AgentSession(
            agent_id=agent_id,
            delegation_id=delegation.id,
            owner_email=user_id,
            scoped_permissions=["notion:pages:read"],
            party_type=PartyType.FIRST_PARTY,
            is_active=True,
        )
        db_session.add(session)
        db_session.commit()

        result = service.patch_delegation_permissions(
            str(delegation.id),
            user_id,
            new_permissions=["notion:pages:read"],
        )

        db_session.refresh(session)
        assert result.sessions_revoked == 1
        assert session.is_active is False

    def test_patch_forbidden_for_other_user(self, service: DelegationService, db_session: Session):
        user_id = unique_user_id()
        other_user = unique_user_id()
        agent_id = unique_agent_id()
        create_connected_service(db_session, user_id, "notion", ["read_pages"])
        delegation = service.create_delegation(
            delegator=user_id,
            agent_id=agent_id,
            permissions=["notion:pages:read"],
        )
        db_session.commit()

        with pytest.raises(DelegationForbiddenError):
            service.patch_delegation_permissions(
                str(delegation.id),
                other_user,
                new_permissions=[],
            )

    def test_patch_admin_can_modify_any_delegation(
        self, service: DelegationService, db_session: Session
    ):
        user_id = unique_user_id()
        agent_id = unique_agent_id()
        create_connected_service(db_session, user_id, "notion", ["read_pages"])
        delegation = service.create_delegation(
            delegator=user_id,
            agent_id=agent_id,
            permissions=["notion:pages:read", "notion:pages:search"],
        )
        db_session.commit()

        result = service.patch_delegation_permissions(
            str(delegation.id),
            "admin@test.com",
            is_admin=True,
            new_permissions=["notion:pages:read"],
        )
        assert result.delegation.delegated_permissions == ["notion:pages:read"]

    def test_patch_revoked_delegation_returns_invalid_state(
        self, service: DelegationService, db_session: Session
    ):
        user_id = unique_user_id()
        agent_id = unique_agent_id()
        create_connected_service(db_session, user_id, "notion", ["read_pages"])
        delegation = service.create_delegation(
            delegator=user_id,
            agent_id=agent_id,
            permissions=["notion:pages:read"],
        )
        service.revoke_delegation(str(delegation.id))
        db_session.commit()

        with pytest.raises(DelegationInvalidStateError):
            service.patch_delegation_permissions(
                str(delegation.id),
                user_id,
                new_permissions=[],
            )

    def test_patch_not_found(self, service: DelegationService):
        with pytest.raises(DelegationNotFoundError):
            service.patch_delegation_permissions(
                "del-does-not-exist",
                "user@test.com",
                new_permissions=[],
            )


# ============================================================================
# Integration Tests
# ============================================================================


class TestIntegration:
    """Integration tests for complete delegation flows."""

    def test_full_delegation_lifecycle(
        self,
        service: DelegationService,
        db_session: Session,
    ):
        """Test complete delegation lifecycle."""
        user_id = unique_user_id()
        agent_id = unique_agent_id()

        # 1. Connect services
        create_connected_service(
            db_session, user_id, "notion", ["read_pages"]
        )
        create_connected_service(
            db_session, user_id, "slack", ["search:read"]
        )

        # 2. Create delegation
        delegation = service.create_delegation(
            delegator=user_id,
            agent_id=agent_id,
            permissions=["notion:pages:search", "slack:messages:search"],
            constraints={"max_actions_per_day": 100},
            expires_in_days=7,
        )
        db_session.commit()

        # 3. Validate
        result = service.validate_delegation(str(delegation.id))
        assert result.is_valid is True

        # 4. Check permissions
        assert service.has_permission(str(delegation.id), "notion:pages:search") is True
        assert service.has_permission(str(delegation.id), "notion:pages:create") is False

        # 5. Get constraint
        assert service.get_constraint(str(delegation.id), "max_actions_per_day") == 100

        # 6. Get active
        active = service.get_active_delegation(user_id, agent_id)
        assert active is not None
        assert active.id == delegation.id

        # 7. Revoke
        service.revoke_delegation(str(delegation.id))
        db_session.commit()

        # 8. Verify revoked
        result = service.validate_delegation(str(delegation.id))
        assert result.is_valid is False
        assert "revoked" in result.reason.lower()

        # 9. No active delegation
        active = service.get_active_delegation(user_id, agent_id)
        assert active is None
