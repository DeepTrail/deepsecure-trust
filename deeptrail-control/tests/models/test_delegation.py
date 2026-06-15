"""Unit tests for the DelegationToken model."""

import uuid
from datetime import datetime, timedelta, timezone

from app.models.delegation import (
    DEFAULT_DELEGATION_DURATION_DAYS,
    DelegationToken,
    generate_delegation_id,
    get_default_expiry,
)


class TestDelegationIdGeneration:
    """Tests for delegation ID generation."""

    def test_generate_delegation_id_format(self):
        """Delegation ID should have correct prefix format."""
        del_id = generate_delegation_id()
        assert del_id.startswith("del-")

    def test_generate_delegation_id_uniqueness(self):
        """Each generated delegation ID should be unique."""
        ids = [generate_delegation_id() for _ in range(100)]
        assert len(set(ids)) == 100

    def test_generate_delegation_id_contains_uuid(self):
        """Delegation ID should contain a valid UUID after the prefix."""
        del_id = generate_delegation_id()
        uuid_part = del_id.replace("del-", "")
        # Should not raise
        uuid.UUID(uuid_part)


class TestDefaultExpiry:
    """Tests for default expiry calculation."""

    def test_default_expiry_is_7_days(self):
        """Default expiry should be 7 days from now."""
        before = datetime.now(timezone.utc)
        expiry = get_default_expiry()
        after = datetime.now(timezone.utc)

        expected_min = before + timedelta(days=DEFAULT_DELEGATION_DURATION_DAYS)
        expected_max = after + timedelta(days=DEFAULT_DELEGATION_DURATION_DAYS)

        assert expected_min <= expiry <= expected_max


class TestDelegationTokenModel:
    """Tests for DelegationToken model instantiation."""

    def test_create_basic_delegation(self):
        """Create a delegation with required fields."""
        delegation = DelegationToken(
            agent_id="agent-sdr-001",
            delegator="sarah@acme.com",
            delegated_permissions=["notion:pages:search", "slack:messages:search"],
            expires_at=datetime.now(timezone.utc) + timedelta(days=7),
        )

        assert delegation.agent_id == "agent-sdr-001"
        assert delegation.delegator == "sarah@acme.com"
        assert len(delegation.delegated_permissions) == 2

    def test_default_id_generated(self):
        """Delegation ID should be auto-generated if not provided."""
        assert DelegationToken.id.default is not None
        assert callable(DelegationToken.id.default.arg)

    def test_optional_fields(self):
        """Optional fields should be None by default."""
        delegation = DelegationToken(
            agent_id="agent-sdr-001",
            delegator="sarah@acme.com",
            delegated_permissions=[],
            expires_at=datetime.now(timezone.utc) + timedelta(days=7),
        )

        assert delegation.delegator_idp is None
        assert delegation.user_token_hash is None
        assert delegation.agent_token_hash is None
        assert delegation.organization_id is None
        assert delegation.revoked_at is None
        assert delegation.logging_uri is None
        assert delegation.revocation_uri is None

    def test_with_all_fields(self):
        """Delegation can be created with all fields from design doc."""
        delegation = DelegationToken(
            id="del-sarah-sdr-001",
            agent_id="agent-sdr-001",
            delegator="sarah@acme.com",
            delegator_idp="https://acme.okta.com",
            user_token_hash="sha256:abc123",
            agent_token_hash="sha256:def456",
            delegated_permissions=[
                "notion:pages:search",
                "notion:pages:read",
                "slack:messages:search",
                "slack:channels:list",
            ],
            constraints={"max_actions_per_day": 100},
            expires_at=datetime(2026, 2, 6, 10, 0, 0, tzinfo=timezone.utc),
            logging_uri="https://audit.deeptrail.io/log",
            revocation_uri="https://deeptrail.io/revoke/del-sarah-sdr-001",
        )

        assert delegation.id == "del-sarah-sdr-001"
        assert delegation.delegator_idp == "https://acme.okta.com"
        assert delegation.user_token_hash == "sha256:abc123"
        assert delegation.agent_token_hash == "sha256:def456"
        assert delegation.constraints == {"max_actions_per_day": 100}


class TestDelegationTokenTablename:
    """Tests for table configuration."""

    def test_tablename(self):
        """Model should have correct table name."""
        assert DelegationToken.__tablename__ == "delegation_tokens"


class TestDelegationTokenIsValid:
    """Tests for is_valid hybrid property."""

    def test_is_valid_when_active(self):
        """New delegation should be valid."""
        delegation = DelegationToken(
            agent_id="agent-sdr-001",
            delegator="sarah@acme.com",
            delegated_permissions=[],
            expires_at=datetime.now(timezone.utc) + timedelta(days=7),
        )

        assert delegation.is_valid is True
        assert delegation.is_expired is False
        assert delegation.is_revoked is False

    def test_is_valid_when_expired(self):
        """Expired delegation should not be valid."""
        delegation = DelegationToken(
            agent_id="agent-sdr-001",
            delegator="sarah@acme.com",
            delegated_permissions=[],
            expires_at=datetime.now(timezone.utc) - timedelta(hours=1),
        )

        assert delegation.is_valid is False
        assert delegation.is_expired is True

    def test_is_valid_when_revoked(self):
        """Revoked delegation should not be valid."""
        delegation = DelegationToken(
            agent_id="agent-sdr-001",
            delegator="sarah@acme.com",
            delegated_permissions=[],
            expires_at=datetime.now(timezone.utc) + timedelta(days=7),
            revoked_at=datetime.now(timezone.utc),
        )

        assert delegation.is_valid is False
        assert delegation.is_revoked is True


class TestDelegationTokenHasPermission:
    """Tests for has_permission method."""

    def test_has_permission_present(self):
        """has_permission returns True when permission is present."""
        delegation = DelegationToken(
            agent_id="agent-sdr-001",
            delegator="sarah@acme.com",
            delegated_permissions=[
                "notion:pages:search",
                "notion:pages:read",
                "slack:messages:search",
            ],
            expires_at=datetime.now(timezone.utc) + timedelta(days=7),
        )

        assert delegation.has_permission("notion:pages:search") is True
        assert delegation.has_permission("slack:messages:search") is True

    def test_has_permission_absent(self):
        """has_permission returns False when permission is absent."""
        delegation = DelegationToken(
            agent_id="agent-sdr-001",
            delegator="sarah@acme.com",
            delegated_permissions=["notion:pages:read"],
            expires_at=datetime.now(timezone.utc) + timedelta(days=7),
        )

        assert delegation.has_permission("notion:pages:write") is False
        assert delegation.has_permission("slack:messages:send") is False

    def test_has_permission_empty_list(self):
        """has_permission handles empty permissions list."""
        delegation = DelegationToken(
            agent_id="agent-sdr-001",
            delegator="sarah@acme.com",
            delegated_permissions=[],
            expires_at=datetime.now(timezone.utc) + timedelta(days=7),
        )

        assert delegation.has_permission("anything") is False


class TestDelegationTokenHasAllPermissions:
    """Tests for has_all_permissions method."""

    def test_has_all_permissions_when_present(self):
        """has_all_permissions returns True when all permissions are present."""
        delegation = DelegationToken(
            agent_id="agent-sdr-001",
            delegator="sarah@acme.com",
            delegated_permissions=["read", "write", "delete"],
            expires_at=datetime.now(timezone.utc) + timedelta(days=7),
        )

        assert delegation.has_all_permissions(["read", "write"]) is True
        assert delegation.has_all_permissions(["read"]) is True

    def test_has_all_permissions_when_missing_one(self):
        """has_all_permissions returns False when any permission is missing."""
        delegation = DelegationToken(
            agent_id="agent-sdr-001",
            delegator="sarah@acme.com",
            delegated_permissions=["read", "write"],
            expires_at=datetime.now(timezone.utc) + timedelta(days=7),
        )

        assert delegation.has_all_permissions(["read", "delete"]) is False


class TestDelegationTokenHasAnyPermission:
    """Tests for has_any_permission method."""

    def test_has_any_permission_when_present(self):
        """has_any_permission returns True when any permission is present."""
        delegation = DelegationToken(
            agent_id="agent-sdr-001",
            delegator="sarah@acme.com",
            delegated_permissions=["read"],
            expires_at=datetime.now(timezone.utc) + timedelta(days=7),
        )

        assert delegation.has_any_permission(["read", "write"]) is True

    def test_has_any_permission_when_none_present(self):
        """has_any_permission returns False when no permissions are present."""
        delegation = DelegationToken(
            agent_id="agent-sdr-001",
            delegator="sarah@acme.com",
            delegated_permissions=["read"],
            expires_at=datetime.now(timezone.utc) + timedelta(days=7),
        )

        assert delegation.has_any_permission(["write", "delete"]) is False


class TestDelegationTokenGetPermissionsForService:
    """Tests for get_permissions_for_service method."""

    def test_get_permissions_for_service(self):
        """Get all permissions for a specific service."""
        delegation = DelegationToken(
            agent_id="agent-sdr-001",
            delegator="sarah@acme.com",
            delegated_permissions=[
                "notion:pages:search",
                "notion:pages:read",
                "slack:messages:search",
                "slack:channels:list",
            ],
            expires_at=datetime.now(timezone.utc) + timedelta(days=7),
        )

        notion_perms = delegation.get_permissions_for_service("notion")
        assert len(notion_perms) == 2
        assert "notion:pages:search" in notion_perms
        assert "notion:pages:read" in notion_perms

        slack_perms = delegation.get_permissions_for_service("slack")
        assert len(slack_perms) == 2

    def test_get_permissions_for_nonexistent_service(self):
        """Get permissions for a service with no grants."""
        delegation = DelegationToken(
            agent_id="agent-sdr-001",
            delegator="sarah@acme.com",
            delegated_permissions=["notion:pages:read"],
            expires_at=datetime.now(timezone.utc) + timedelta(days=7),
        )

        assert delegation.get_permissions_for_service("gdrive") == []


class TestDelegationTokenGetConstraint:
    """Tests for get_constraint method."""

    def test_get_constraint_present(self):
        """get_constraint returns value when constraint is present."""
        delegation = DelegationToken(
            agent_id="agent-sdr-001",
            delegator="sarah@acme.com",
            delegated_permissions=[],
            constraints={"max_actions_per_day": 100, "rate_limit": 10},
            expires_at=datetime.now(timezone.utc) + timedelta(days=7),
        )

        assert delegation.get_constraint("max_actions_per_day") == 100
        assert delegation.get_constraint("rate_limit") == 10

    def test_get_constraint_absent_with_default(self):
        """get_constraint returns default when constraint is absent."""
        delegation = DelegationToken(
            agent_id="agent-sdr-001",
            delegator="sarah@acme.com",
            delegated_permissions=[],
            constraints={},
            expires_at=datetime.now(timezone.utc) + timedelta(days=7),
        )

        assert delegation.get_constraint("max_actions_per_day", 50) == 50
        assert delegation.get_constraint("nonexistent") is None


class TestDelegationTokenRevoke:
    """Tests for revoke method."""

    def test_revoke_sets_timestamp(self):
        """revoke method sets revoked_at timestamp."""
        delegation = DelegationToken(
            agent_id="agent-sdr-001",
            delegator="sarah@acme.com",
            delegated_permissions=[],
            expires_at=datetime.now(timezone.utc) + timedelta(days=7),
        )

        assert delegation.revoked_at is None
        delegation.revoke()
        assert delegation.revoked_at is not None
        assert delegation.is_valid is False

    def test_revoke_timestamp_is_recent(self):
        """revoke sets a recent timestamp."""
        delegation = DelegationToken(
            agent_id="agent-sdr-001",
            delegator="sarah@acme.com",
            delegated_permissions=[],
            expires_at=datetime.now(timezone.utc) + timedelta(days=7),
        )

        before = datetime.now(timezone.utc)
        delegation.revoke()
        after = datetime.now(timezone.utc)

        assert before <= delegation.revoked_at <= after


class TestDelegationTokenToClaimsDict:
    """Tests for to_claims_dict method."""

    def test_to_claims_dict_structure(self):
        """to_claims_dict produces JWT-compatible structure."""
        created = datetime(2026, 1, 30, 10, 0, 0, tzinfo=timezone.utc)
        expires = datetime(2026, 2, 6, 10, 0, 0, tzinfo=timezone.utc)

        delegation = DelegationToken(
            id="del-test-123",
            agent_id="agent-sdr-001",
            delegator="sarah@acme.com",
            delegator_idp="https://acme.okta.com",
            user_token_hash="sha256:abc",
            agent_token_hash="sha256:def",
            delegated_permissions=["notion:pages:search"],
            constraints={"max_actions_per_day": 100},
            created_at=created,
            expires_at=expires,
            logging_uri="https://audit.deeptrail.io/log",
            revocation_uri="https://deeptrail.io/revoke/del-test-123",
        )

        claims = delegation.to_claims_dict()

        assert claims["jti"] == "del-test-123"
        assert claims["sub"] == "agent-sdr-001"
        assert claims["delegator"] == "sarah@acme.com"
        assert claims["delegator_idp"] == "https://acme.okta.com"
        assert claims["user_token_hash"] == "sha256:abc"
        assert claims["agent_token_hash"] == "sha256:def"
        assert claims["delegated_permissions"] == ["notion:pages:search"]
        assert claims["constraints"] == {"max_actions_per_day": 100}
        assert claims["iat"] == int(created.timestamp())
        assert claims["exp"] == int(expires.timestamp())
        assert claims["logging_uri"] == "https://audit.deeptrail.io/log"
        assert claims["revocation_uri"] == "https://deeptrail.io/revoke/del-test-123"


class TestDelegationTokenFromClaimsDict:
    """Tests for from_claims_dict class method."""

    def test_from_claims_dict(self):
        """from_claims_dict creates DelegationToken from claims."""
        claims = {
            "jti": "del-test-456",
            "sub": "agent-sdr-002",
            "delegator": "bob@acme.com",
            "delegator_idp": "https://acme.okta.com",
            "delegated_permissions": ["slack:messages:search"],
            "constraints": {"rate_limit": 50},
            "iat": 1738234800,  # 2026-01-30 10:00:00 UTC
            "exp": 1738839600,  # 2026-02-06 10:00:00 UTC
        }

        delegation = DelegationToken.from_claims_dict(claims)

        assert delegation.id == "del-test-456"
        assert delegation.agent_id == "agent-sdr-002"
        assert delegation.delegator == "bob@acme.com"
        assert delegation.delegated_permissions == ["slack:messages:search"]
        assert delegation.constraints == {"rate_limit": 50}

    def test_from_claims_dict_roundtrip(self):
        """to_claims_dict and from_claims_dict are inverses."""
        original = DelegationToken(
            id="del-roundtrip",
            agent_id="agent-test",
            delegator="test@acme.com",
            delegated_permissions=["notion:pages:read"],
            constraints={"limit": 10},
            created_at=datetime(2026, 1, 30, 10, 0, 0, tzinfo=timezone.utc),
            expires_at=datetime(2026, 2, 6, 10, 0, 0, tzinfo=timezone.utc),
        )

        claims = original.to_claims_dict()
        restored = DelegationToken.from_claims_dict(claims)

        assert restored.id == original.id
        assert restored.agent_id == original.agent_id
        assert restored.delegator == original.delegator
        assert restored.delegated_permissions == original.delegated_permissions


class TestDelegationTokenGenerateRevocationUri:
    """Tests for generate_revocation_uri method."""

    def test_generate_revocation_uri(self):
        """Generate revocation URI with default base."""
        delegation = DelegationToken(
            id="del-test-789",
            agent_id="agent-sdr-001",
            delegator="sarah@acme.com",
            delegated_permissions=[],
            expires_at=datetime.now(timezone.utc) + timedelta(days=7),
        )

        uri = delegation.generate_revocation_uri()
        assert uri == "https://deeptrail.io/revoke/del-test-789"

    def test_generate_revocation_uri_custom_base(self):
        """Generate revocation URI with custom base."""
        delegation = DelegationToken(
            id="del-test-789",
            agent_id="agent-sdr-001",
            delegator="sarah@acme.com",
            delegated_permissions=[],
            expires_at=datetime.now(timezone.utc) + timedelta(days=7),
        )

        uri = delegation.generate_revocation_uri("https://custom.example.com")
        assert uri == "https://custom.example.com/revoke/del-test-789"


class TestDelegationTokenRepr:
    """Tests for __repr__ method."""

    def test_repr_valid(self):
        """Repr shows valid status for active delegation."""
        delegation = DelegationToken(
            id="del-repr-test",
            agent_id="agent-sdr-001",
            delegator="sarah@acme.com",
            delegated_permissions=[],
            expires_at=datetime.now(timezone.utc) + timedelta(days=7),
        )

        repr_str = repr(delegation)
        assert "del-repr-test" in repr_str
        assert "sarah@acme.com" in repr_str
        assert "agent-sdr-001" in repr_str
        assert "valid" in repr_str

    def test_repr_expired(self):
        """Repr shows expired status."""
        delegation = DelegationToken(
            id="del-repr-test",
            agent_id="agent-sdr-001",
            delegator="sarah@acme.com",
            delegated_permissions=[],
            expires_at=datetime.now(timezone.utc) - timedelta(hours=1),
        )

        repr_str = repr(delegation)
        assert "expired" in repr_str

    def test_repr_revoked(self):
        """Repr shows revoked status."""
        delegation = DelegationToken(
            id="del-repr-test",
            agent_id="agent-sdr-001",
            delegator="sarah@acme.com",
            delegated_permissions=[],
            expires_at=datetime.now(timezone.utc) + timedelta(days=7),
            revoked_at=datetime.now(timezone.utc),
        )

        repr_str = repr(delegation)
        assert "revoked" in repr_str


class TestDelegationTokenDesignDocCompliance:
    """Tests verifying compliance with design document examples."""

    def test_design_doc_layer2_example(self):
        """Delegation matches the Layer 2 structure from design doc Section 2.5."""
        # From the design doc:
        # LAYER 2: DELEGATION TOKEN
        # {
        #   "sub": "agent-sdr-001",
        #   "delegator": "sarah@acme.com",
        #   "delegator_idp": "https://acme.okta.com",
        #   "user_token_hash": "sha256:abc...",
        #   "agent_token_hash": "sha256:def...",
        #   "delegated_permissions": [...],
        #   "constraints": {"max_actions_per_day": 100},
        #   "exp": 1738512000,  // 7 days
        #   ...
        # }
        delegation = DelegationToken(
            agent_id="agent-sdr-001",
            delegator="sarah@acme.com",
            delegator_idp="https://acme.okta.com",
            user_token_hash="sha256:abc123",
            agent_token_hash="sha256:def456",
            delegated_permissions=[
                "notion:pages:search",
                "notion:pages:read",
                "slack:messages:search",
                "slack:channels:list",
            ],
            constraints={"max_actions_per_day": 100},
            expires_at=datetime.now(timezone.utc) + timedelta(days=7),
            logging_uri="https://audit.deeptrail.io/log",
            revocation_uri="https://deeptrail.io/revoke/del-sarah-sdr-001",
        )

        # Verify all Layer 2 fields
        assert delegation.agent_id == "agent-sdr-001"  # sub
        assert delegation.delegator == "sarah@acme.com"
        assert delegation.delegator_idp == "https://acme.okta.com"
        assert delegation.user_token_hash.startswith("sha256:")
        assert delegation.agent_token_hash.startswith("sha256:")
        assert "notion:pages:search" in delegation.delegated_permissions
        assert delegation.get_constraint("max_actions_per_day") == 100
        assert delegation.is_valid is True

        # Verify JWT serialization
        claims = delegation.to_claims_dict()
        assert claims["sub"] == "agent-sdr-001"
        assert claims["delegator"] == "sarah@acme.com"
        assert "exp" in claims
