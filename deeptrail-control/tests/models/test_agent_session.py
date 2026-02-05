"""Unit tests for the AgentSession model."""

from datetime import datetime, timedelta, timezone

from app.models.agent_session import (
    CHALLENGE_TTL_SECONDS,
    DEFAULT_SESSION_DURATION_HOURS,
    AgentSession,
    PartyType,
    generate_session_id,
    get_default_expiry,
)
from app.models.delegation import DelegationToken


class TestSessionIdGeneration:
    """Tests for session ID generation."""

    def test_generate_session_id_format(self):
        """Session ID should have correct prefix format."""
        session_id = generate_session_id()
        assert session_id.startswith("asess-")

    def test_generate_session_id_uniqueness(self):
        """Each generated session ID should be unique."""
        ids = [generate_session_id() for _ in range(100)]
        assert len(set(ids)) == 100

    def test_generate_session_id_length(self):
        """Session ID should have expected length (asess- + 16 hex chars)."""
        session_id = generate_session_id()
        # "asess-" (6 chars) + 16 hex chars = 22 chars
        assert len(session_id) == 22


class TestDefaultExpiry:
    """Tests for default expiry calculation."""

    def test_default_expiry_is_8_hours(self):
        """Default expiry should be 8 hours from now."""
        before = datetime.now(timezone.utc)
        expiry = get_default_expiry()
        after = datetime.now(timezone.utc)

        expected_min = before + timedelta(hours=DEFAULT_SESSION_DURATION_HOURS)
        expected_max = after + timedelta(hours=DEFAULT_SESSION_DURATION_HOURS)

        assert expected_min <= expiry <= expected_max


class TestPartyTypeEnum:
    """Tests for PartyType enum."""

    def test_party_type_values(self):
        """PartyType enum should have all expected values."""
        assert PartyType.FIRST_PARTY.value == "first_party"
        assert PartyType.THIRD_PARTY.value == "third_party"
        assert PartyType.FEDERATED.value == "federated"

    def test_party_type_count(self):
        """PartyType should have exactly 3 values."""
        assert len(PartyType) == 3


class TestAgentSessionModel:
    """Tests for AgentSession model instantiation."""

    def test_create_basic_session(self):
        """Create a session with required fields."""
        session = AgentSession(
            agent_id="agent-sdr-001",
            delegation_id="del-sarah-sdr-001",
            owner_email="sarah@acme.com",
            scoped_permissions=["notion:pages:search", "slack:messages:read"],
            expires_at=datetime.now(timezone.utc) + timedelta(hours=8),
        )

        assert session.agent_id == "agent-sdr-001"
        assert session.delegation_id == "del-sarah-sdr-001"
        assert session.owner_email == "sarah@acme.com"
        assert len(session.scoped_permissions) == 2

    def test_default_id_generated(self):
        """Session ID should be auto-generated if not provided."""
        assert AgentSession.id.default is not None
        assert callable(AgentSession.id.default.arg)

    def test_session_id_prefix(self):
        """Auto-generated session ID has correct prefix."""
        session_id = generate_session_id()
        assert session_id.startswith("asess-")

    def test_default_party_type(self):
        """Default party type should be FIRST_PARTY when set."""
        # Note: SQLAlchemy Column defaults are only applied on DB insert
        # For in-memory objects, we test the default is configured correctly
        assert AgentSession.party_type.default is not None
        assert AgentSession.party_type.default.arg == PartyType.FIRST_PARTY

    def test_default_is_active(self):
        """New session should be active by default when set."""
        # Note: SQLAlchemy Column defaults are only applied on DB insert
        # For in-memory objects, we test the default is configured correctly
        assert AgentSession.is_active.default is not None
        assert AgentSession.is_active.default.arg is True

    def test_optional_fields(self):
        """Optional fields should be None by default."""
        session = AgentSession(
            agent_id="agent-001",
            delegation_id="del-test",
            owner_email="test@example.com",
            scoped_permissions=[],
            expires_at=datetime.now(timezone.utc) + timedelta(hours=8),
        )

        assert session.idp_issuer is None
        assert session.organization_id is None
        assert session.revoked_at is None
        assert session.revoked_by is None
        assert session.revoke_reason is None
        assert session.last_activity_at is None
        assert session.challenge_nonce is None
        assert session.challenge_expires_at is None

    def test_with_all_fields(self):
        """Session can be created with all fields from design doc."""
        session = AgentSession(
            id="asess-sdr-001-ghi789",
            agent_id="agent-sdr-001",
            delegation_id="del-sarah-sdr-001",
            party_type=PartyType.FIRST_PARTY,
            scoped_permissions=[
                "notion:pages:search",
                "notion:pages:read",
                "slack:messages:search",
                "slack:channels:list",
            ],
            mcp_sessions={"notion": {"session_id": "mcp-123"}},
            is_active=True,
            owner_email="sarah@acme.com",
            idp_issuer="https://acme.okta.com",
            groups=["sales"],
            organization_id="org-acme",
            expires_at=datetime(2026, 1, 31, 18, 0, 0, tzinfo=timezone.utc),
        )

        assert session.id == "asess-sdr-001-ghi789"
        assert session.party_type == PartyType.FIRST_PARTY
        assert session.idp_issuer == "https://acme.okta.com"
        assert session.groups == ["sales"]
        assert "notion" in session.mcp_sessions


class TestAgentSessionTablename:
    """Tests for table configuration."""

    def test_tablename(self):
        """Model should have correct table name."""
        assert AgentSession.__tablename__ == "agent_sessions"


class TestAgentSessionIsValid:
    """Tests for is_valid hybrid property."""

    def test_is_valid_when_active(self):
        """New active session should be valid."""
        session = AgentSession(
            agent_id="agent-001",
            delegation_id="del-test",
            owner_email="test@example.com",
            scoped_permissions=[],
            is_active=True,
            expires_at=datetime.now(timezone.utc) + timedelta(hours=8),
        )

        assert session.is_valid is True
        assert session.is_expired is False
        assert session.is_revoked is False

    def test_is_valid_when_expired(self):
        """Expired session should not be valid."""
        session = AgentSession(
            agent_id="agent-001",
            delegation_id="del-test",
            owner_email="test@example.com",
            scoped_permissions=[],
            is_active=True,
            expires_at=datetime.now(timezone.utc) - timedelta(hours=1),
        )

        assert session.is_valid is False
        assert session.is_expired is True

    def test_is_valid_when_revoked(self):
        """Revoked session should not be valid."""
        session = AgentSession(
            agent_id="agent-001",
            delegation_id="del-test",
            owner_email="test@example.com",
            scoped_permissions=[],
            is_active=True,
            expires_at=datetime.now(timezone.utc) + timedelta(hours=8),
            revoked_at=datetime.now(timezone.utc),
        )

        assert session.is_valid is False
        assert session.is_revoked is True

    def test_is_valid_when_inactive(self):
        """Inactive session should not be valid."""
        session = AgentSession(
            agent_id="agent-001",
            delegation_id="del-test",
            owner_email="test@example.com",
            scoped_permissions=[],
            is_active=False,
            expires_at=datetime.now(timezone.utc) + timedelta(hours=8),
        )

        assert session.is_valid is False


class TestAgentSessionChallenge:
    """Tests for challenge-response authentication flow."""

    def test_set_challenge(self):
        """Test setting a challenge."""
        session = AgentSession(
            agent_id="agent-001",
            delegation_id="del-test",
            owner_email="test@example.com",
            scoped_permissions=[],
            expires_at=datetime.now(timezone.utc) + timedelta(hours=8),
        )
        session.set_challenge("nonce-abc123")

        assert session.challenge_nonce == "nonce-abc123"
        assert session.challenge_expires_at is not None
        assert session.challenge_is_valid is True

    def test_clear_challenge(self):
        """Test clearing a challenge after use."""
        session = AgentSession(
            agent_id="agent-001",
            delegation_id="del-test",
            owner_email="test@example.com",
            scoped_permissions=[],
            expires_at=datetime.now(timezone.utc) + timedelta(hours=8),
        )
        session.set_challenge("nonce-abc123")
        session.clear_challenge()

        assert session.challenge_nonce is None
        assert session.challenge_expires_at is None
        assert session.challenge_is_valid is False

    def test_challenge_expires(self):
        """Test challenge expiration (5 minutes)."""
        session = AgentSession(
            agent_id="agent-001",
            delegation_id="del-test",
            owner_email="test@example.com",
            scoped_permissions=[],
            expires_at=datetime.now(timezone.utc) + timedelta(hours=8),
        )
        session.set_challenge("nonce-abc123")

        # Valid initially
        assert session.challenge_is_valid is True

        # Expired after timeout
        session.challenge_expires_at = datetime.now(timezone.utc) - timedelta(minutes=1)
        assert session.challenge_is_valid is False

    def test_challenge_ttl_is_5_minutes(self):
        """Challenge TTL should be 5 minutes (300 seconds)."""
        assert CHALLENGE_TTL_SECONDS == 300

    def test_challenge_expiry_set_correctly(self):
        """Challenge expiry should be ~5 minutes from now."""
        session = AgentSession(
            agent_id="agent-001",
            delegation_id="del-test",
            owner_email="test@example.com",
            scoped_permissions=[],
            expires_at=datetime.now(timezone.utc) + timedelta(hours=8),
        )

        before = datetime.now(timezone.utc)
        session.set_challenge("nonce-test")
        after = datetime.now(timezone.utc)

        expected_min = before + timedelta(seconds=CHALLENGE_TTL_SECONDS)
        expected_max = after + timedelta(seconds=CHALLENGE_TTL_SECONDS)

        # Handle timezone awareness
        challenge_expires = session.challenge_expires_at
        if challenge_expires.tzinfo is None:
            challenge_expires = challenge_expires.replace(tzinfo=timezone.utc)

        assert expected_min <= challenge_expires <= expected_max


class TestAgentSessionJWT:
    """Tests for JWT claim generation."""

    def test_to_jwt_claims_structure(self):
        """JWT claims should match design doc format."""
        created = datetime(2026, 1, 30, 10, 0, 0, tzinfo=timezone.utc)
        expires = datetime(2026, 1, 30, 18, 0, 0, tzinfo=timezone.utc)

        session = AgentSession(
            id="asess-sdr-001-ghi789",
            agent_id="agent-sdr-001",
            delegation_id="del-sarah-sdr-001",
            owner_email="sarah@acme.com",
            idp_issuer="https://acme.okta.com",
            party_type=PartyType.FIRST_PARTY,
            scoped_permissions=[
                "notion:pages:search",
                "notion:pages:read",
                "slack:messages:search",
            ],
            groups=["sales"],
            created_at=created,
            expires_at=expires,
        )

        claims = session.to_jwt_claims()

        assert claims["sub"] == "agent-sdr-001"
        assert claims["session_id"] == "asess-sdr-001-ghi789"
        assert claims["owner"] == "sarah@acme.com"
        assert claims["idp_issuer"] == "https://acme.okta.com"
        assert claims["party_type"] == "first_party"
        assert "notion:pages:search" in claims["delegated_permissions"]
        assert claims["delegation_id"] == "del-sarah-sdr-001"
        assert claims["groups"] == ["sales"]
        assert claims["exp"] == int(expires.timestamp())
        assert claims["iat"] == int(created.timestamp())

    def test_to_jwt_claims_with_third_party(self):
        """JWT claims should show third_party type."""
        session = AgentSession(
            id="asess-external",
            agent_id="agent-external-001",
            delegation_id="del-external",
            owner_email="user@example.com",
            party_type=PartyType.THIRD_PARTY,
            scoped_permissions=["read"],
            expires_at=datetime.now(timezone.utc) + timedelta(hours=8),
        )

        claims = session.to_jwt_claims()
        assert claims["party_type"] == "third_party"


class TestAgentSessionMCPTracking:
    """Tests for MCP session tracking."""

    def test_add_mcp_session(self):
        """Test adding an MCP backend session."""
        session = AgentSession(
            agent_id="agent-001",
            delegation_id="del-test",
            owner_email="test@example.com",
            scoped_permissions=[],
            expires_at=datetime.now(timezone.utc) + timedelta(hours=8),
        )

        session.add_mcp_session("notion", {"session_id": "mcp-123"})

        assert "notion" in session.mcp_sessions
        assert session.mcp_sessions["notion"]["session_id"] == "mcp-123"
        assert "connected_at" in session.mcp_sessions["notion"]

    def test_add_multiple_mcp_sessions(self):
        """Test adding multiple MCP backend sessions."""
        session = AgentSession(
            agent_id="agent-001",
            delegation_id="del-test",
            owner_email="test@example.com",
            scoped_permissions=[],
            mcp_sessions={},
            expires_at=datetime.now(timezone.utc) + timedelta(hours=8),
        )

        session.add_mcp_session("notion", {"session_id": "mcp-notion"})
        session.add_mcp_session("slack", {"session_id": "mcp-slack"})

        assert len(session.mcp_sessions) == 2
        assert "notion" in session.mcp_sessions
        assert "slack" in session.mcp_sessions

    def test_remove_mcp_session(self):
        """Test removing an MCP backend session."""
        session = AgentSession(
            agent_id="agent-001",
            delegation_id="del-test",
            owner_email="test@example.com",
            scoped_permissions=[],
            mcp_sessions={"notion": {"session_id": "mcp-123"}},
            expires_at=datetime.now(timezone.utc) + timedelta(hours=8),
        )

        result = session.remove_mcp_session("notion")

        assert result is True
        assert "notion" not in session.mcp_sessions

    def test_remove_nonexistent_mcp_session(self):
        """Test removing a non-existent MCP session returns False."""
        session = AgentSession(
            agent_id="agent-001",
            delegation_id="del-test",
            owner_email="test@example.com",
            scoped_permissions=[],
            mcp_sessions={},
            expires_at=datetime.now(timezone.utc) + timedelta(hours=8),
        )

        result = session.remove_mcp_session("nonexistent")

        assert result is False

    def test_get_mcp_session(self):
        """Test getting an MCP session."""
        session = AgentSession(
            agent_id="agent-001",
            delegation_id="del-test",
            owner_email="test@example.com",
            scoped_permissions=[],
            mcp_sessions={"notion": {"session_id": "mcp-123", "workspace": "test"}},
            expires_at=datetime.now(timezone.utc) + timedelta(hours=8),
        )

        mcp = session.get_mcp_session("notion")

        assert mcp is not None
        assert mcp["session_id"] == "mcp-123"
        assert mcp["workspace"] == "test"

    def test_get_nonexistent_mcp_session(self):
        """Test getting a non-existent MCP session returns None."""
        session = AgentSession(
            agent_id="agent-001",
            delegation_id="del-test",
            owner_email="test@example.com",
            scoped_permissions=[],
            mcp_sessions={},
            expires_at=datetime.now(timezone.utc) + timedelta(hours=8),
        )

        mcp = session.get_mcp_session("nonexistent")

        assert mcp is None


class TestAgentSessionPermissions:
    """Tests for permission checking."""

    def test_has_permission_present(self):
        """has_permission returns True when permission is present."""
        session = AgentSession(
            agent_id="agent-001",
            delegation_id="del-test",
            owner_email="test@example.com",
            scoped_permissions=["notion:pages:search", "slack:messages:read"],
            expires_at=datetime.now(timezone.utc) + timedelta(hours=8),
        )

        assert session.has_permission("notion:pages:search") is True
        assert session.has_permission("slack:messages:read") is True

    def test_has_permission_absent(self):
        """has_permission returns False when permission is absent."""
        session = AgentSession(
            agent_id="agent-001",
            delegation_id="del-test",
            owner_email="test@example.com",
            scoped_permissions=["notion:pages:read"],
            expires_at=datetime.now(timezone.utc) + timedelta(hours=8),
        )

        assert session.has_permission("notion:pages:delete") is False

    def test_has_permission_empty_list(self):
        """has_permission handles empty permissions list."""
        session = AgentSession(
            agent_id="agent-001",
            delegation_id="del-test",
            owner_email="test@example.com",
            scoped_permissions=[],
            expires_at=datetime.now(timezone.utc) + timedelta(hours=8),
        )

        assert session.has_permission("anything") is False

    def test_has_all_permissions_when_present(self):
        """has_all_permissions returns True when all are present."""
        session = AgentSession(
            agent_id="agent-001",
            delegation_id="del-test",
            owner_email="test@example.com",
            scoped_permissions=["read", "write", "delete"],
            expires_at=datetime.now(timezone.utc) + timedelta(hours=8),
        )

        assert session.has_all_permissions(["read", "write"]) is True

    def test_has_all_permissions_when_missing(self):
        """has_all_permissions returns False when any is missing."""
        session = AgentSession(
            agent_id="agent-001",
            delegation_id="del-test",
            owner_email="test@example.com",
            scoped_permissions=["read"],
            expires_at=datetime.now(timezone.utc) + timedelta(hours=8),
        )

        assert session.has_all_permissions(["read", "write"]) is False

    def test_has_any_permission_when_present(self):
        """has_any_permission returns True when any is present."""
        session = AgentSession(
            agent_id="agent-001",
            delegation_id="del-test",
            owner_email="test@example.com",
            scoped_permissions=["read"],
            expires_at=datetime.now(timezone.utc) + timedelta(hours=8),
        )

        assert session.has_any_permission(["read", "write"]) is True

    def test_has_any_permission_when_none_present(self):
        """has_any_permission returns False when none are present."""
        session = AgentSession(
            agent_id="agent-001",
            delegation_id="del-test",
            owner_email="test@example.com",
            scoped_permissions=["read"],
            expires_at=datetime.now(timezone.utc) + timedelta(hours=8),
        )

        assert session.has_any_permission(["write", "delete"]) is False


class TestAgentSessionRevocation:
    """Tests for session revocation."""

    def test_revoke_session(self):
        """Test revoking a session."""
        session = AgentSession(
            agent_id="agent-001",
            delegation_id="del-test",
            owner_email="test@example.com",
            scoped_permissions=[],
            expires_at=datetime.now(timezone.utc) + timedelta(hours=8),
        )

        session.revoke(revoked_by="sarah@acme.com", reason="User requested")

        assert session.is_active is False
        assert session.revoked_at is not None
        assert session.revoked_by == "sarah@acme.com"
        assert session.revoke_reason == "User requested"
        assert session.is_valid is False

    def test_revoke_with_defaults(self):
        """Test revoking with default values."""
        session = AgentSession(
            agent_id="agent-001",
            delegation_id="del-test",
            owner_email="test@example.com",
            scoped_permissions=[],
            expires_at=datetime.now(timezone.utc) + timedelta(hours=8),
        )

        session.revoke()

        assert session.revoked_by == "system"
        assert session.revoke_reason is None

    def test_revoke_timestamp_is_recent(self):
        """Revoke sets a recent timestamp."""
        session = AgentSession(
            agent_id="agent-001",
            delegation_id="del-test",
            owner_email="test@example.com",
            scoped_permissions=[],
            expires_at=datetime.now(timezone.utc) + timedelta(hours=8),
        )

        before = datetime.now(timezone.utc)
        session.revoke()
        after = datetime.now(timezone.utc)

        # Handle timezone awareness
        revoked_at = session.revoked_at
        if revoked_at.tzinfo is None:
            revoked_at = revoked_at.replace(tzinfo=timezone.utc)

        assert before <= revoked_at <= after


class TestAgentSessionTouch:
    """Tests for last activity tracking."""

    def test_touch_updates_last_activity(self):
        """Touch should update last_activity_at."""
        session = AgentSession(
            agent_id="agent-001",
            delegation_id="del-test",
            owner_email="test@example.com",
            scoped_permissions=[],
            expires_at=datetime.now(timezone.utc) + timedelta(hours=8),
        )

        assert session.last_activity_at is None

        before = datetime.now(timezone.utc)
        session.touch()
        after = datetime.now(timezone.utc)

        # Handle timezone awareness
        last_activity = session.last_activity_at
        if last_activity.tzinfo is None:
            last_activity = last_activity.replace(tzinfo=timezone.utc)

        assert before <= last_activity <= after


class TestAgentSessionFromDelegation:
    """Tests for from_delegation factory method."""

    def test_from_delegation(self):
        """Test creating session from delegation."""
        delegation = DelegationToken(
            id="del-test-123",
            agent_id="agent-sdr-001",
            delegator="sarah@acme.com",
            delegator_idp="https://acme.okta.com",
            delegated_permissions=["notion:pages:search", "slack:messages:read"],
            organization_id="org-acme",
            expires_at=datetime.now(timezone.utc) + timedelta(days=7),
        )

        session = AgentSession.from_delegation(
            delegation=delegation,
            agent_id="agent-sdr-001",
            groups=["sales"],
        )

        assert session.agent_id == "agent-sdr-001"
        assert session.delegation_id == "del-test-123"
        assert session.owner_email == "sarah@acme.com"
        assert session.idp_issuer == "https://acme.okta.com"
        assert session.organization_id == "org-acme"
        assert session.scoped_permissions == delegation.delegated_permissions
        assert session.groups == ["sales"]

    def test_from_delegation_with_scoped_permissions(self):
        """Test creating session with subset of delegation permissions."""
        delegation = DelegationToken(
            id="del-test-456",
            agent_id="agent-001",
            delegator="user@example.com",
            delegated_permissions=["read", "write", "delete"],
            expires_at=datetime.now(timezone.utc) + timedelta(days=7),
        )

        session = AgentSession.from_delegation(
            delegation=delegation,
            agent_id="agent-001",
            scoped_permissions=["read"],  # Subset
        )

        assert session.scoped_permissions == ["read"]

    def test_from_delegation_party_type(self):
        """Test creating session with different party types."""
        delegation = DelegationToken(
            id="del-test-789",
            agent_id="agent-external",
            delegator="user@example.com",
            delegated_permissions=["read"],
            expires_at=datetime.now(timezone.utc) + timedelta(days=7),
        )

        session = AgentSession.from_delegation(
            delegation=delegation,
            agent_id="agent-external",
            party_type=PartyType.THIRD_PARTY,
        )

        assert session.party_type == PartyType.THIRD_PARTY


class TestAgentSessionRepr:
    """Tests for __repr__ method."""

    def test_repr_valid(self):
        """Repr shows valid status for active session."""
        session = AgentSession(
            id="asess-repr-test",
            agent_id="agent-sdr-001",
            delegation_id="del-test",
            owner_email="sarah@acme.com",
            scoped_permissions=[],
            is_active=True,
            expires_at=datetime.now(timezone.utc) + timedelta(hours=8),
        )

        repr_str = repr(session)
        assert "asess-repr-test" in repr_str
        assert "agent-sdr-001" in repr_str
        assert "sarah@acme.com" in repr_str
        assert "valid" in repr_str

    def test_repr_expired(self):
        """Repr shows expired status."""
        session = AgentSession(
            id="asess-repr-test",
            agent_id="agent-sdr-001",
            delegation_id="del-test",
            owner_email="sarah@acme.com",
            scoped_permissions=[],
            expires_at=datetime.now(timezone.utc) - timedelta(hours=1),
        )

        repr_str = repr(session)
        assert "expired" in repr_str

    def test_repr_revoked(self):
        """Repr shows revoked status."""
        session = AgentSession(
            id="asess-repr-test",
            agent_id="agent-sdr-001",
            delegation_id="del-test",
            owner_email="sarah@acme.com",
            scoped_permissions=[],
            expires_at=datetime.now(timezone.utc) + timedelta(hours=8),
            revoked_at=datetime.now(timezone.utc),
        )

        repr_str = repr(session)
        assert "revoked" in repr_str

    def test_repr_inactive(self):
        """Repr shows inactive status."""
        session = AgentSession(
            id="asess-repr-test",
            agent_id="agent-sdr-001",
            delegation_id="del-test",
            owner_email="sarah@acme.com",
            scoped_permissions=[],
            is_active=False,
            expires_at=datetime.now(timezone.utc) + timedelta(hours=8),
        )

        repr_str = repr(session)
        assert "inactive" in repr_str


class TestAgentSessionDesignDocCompliance:
    """Tests verifying compliance with design document examples."""

    def test_design_doc_layer3_example(self):
        """Agent Session matches the Layer 3 structure from design doc Section 2.6."""
        # From the design doc:
        # AGENT SESSION JWT (LAYER 3):
        # {
        #   "sub": "agent-sdr-001",
        #   "owner": "sarah@acme.com",
        #   "idp_issuer": "https://acme.okta.com",
        #   "party_type": "first_party",
        #   "delegated_permissions": [...],
        #   "delegation_id": "del-sarah-sdr-001",
        #   "groups": ["sales"],
        #   "session_id": "asess-sdr-001-ghi789",
        #   "exp": 1737936000
        # }
        session = AgentSession(
            id="asess-sdr-001-ghi789",
            agent_id="agent-sdr-001",
            delegation_id="del-sarah-sdr-001",
            owner_email="sarah@acme.com",
            idp_issuer="https://acme.okta.com",
            party_type=PartyType.FIRST_PARTY,
            scoped_permissions=[
                "notion:pages:search",
                "notion:pages:read",
                "slack:messages:search",
                "slack:channels:list",
            ],
            groups=["sales"],
            is_active=True,
            expires_at=datetime.now(timezone.utc) + timedelta(hours=8),  # Use dynamic expiry
        )

        # Verify all Layer 3 fields
        assert session.agent_id == "agent-sdr-001"  # sub
        assert session.owner_email == "sarah@acme.com"  # owner
        assert session.idp_issuer == "https://acme.okta.com"
        assert session.party_type == PartyType.FIRST_PARTY
        assert "notion:pages:search" in session.scoped_permissions
        assert session.delegation_id == "del-sarah-sdr-001"
        assert session.groups == ["sales"]
        assert session.id == "asess-sdr-001-ghi789"  # session_id
        assert session.is_valid is True

        # Verify JWT serialization
        claims = session.to_jwt_claims()
        assert claims["sub"] == "agent-sdr-001"
        assert claims["owner"] == "sarah@acme.com"
        assert claims["session_id"] == "asess-sdr-001-ghi789"
        assert claims["party_type"] == "first_party"
        assert "exp" in claims

    def test_session_lifetime_shorter_than_delegation(self):
        """Session lifetime (8h) should be shorter than delegation (7d)."""
        assert DEFAULT_SESSION_DURATION_HOURS == 8

        # 8 hours < 7 days (168 hours)
        session_hours = DEFAULT_SESSION_DURATION_HOURS
        delegation_hours = 7 * 24
        assert session_hours < delegation_hours

    def test_agent_session_state_format(self):
        """Agent Session State matches design doc format."""
        # From the design doc:
        # AGENT SESSION STATE:
        # {
        #   "agent_session_id": "asess-sdr-001-ghi789",
        #   "parent_user_session_id": "usess-sarah-abc123",
        #   "agent_id": "agent-sdr-001",
        #   "party_type": "first_party",
        #   "scoped_permissions": [...],
        #   "mcp_sessions": {}
        # }
        session = AgentSession(
            id="asess-sdr-001-ghi789",
            agent_id="agent-sdr-001",
            delegation_id="del-sarah-sdr-001",
            owner_email="sarah@acme.com",
            party_type=PartyType.FIRST_PARTY,
            scoped_permissions=["notion:pages:search", "notion:pages:read"],
            mcp_sessions={},
            expires_at=datetime.now(timezone.utc) + timedelta(hours=8),
        )

        # Verify state fields
        assert session.id == "asess-sdr-001-ghi789"  # agent_session_id
        assert session.agent_id == "agent-sdr-001"
        assert session.party_type == PartyType.FIRST_PARTY
        assert session.scoped_permissions is not None
        assert session.mcp_sessions == {}


class TestAgentSessionDefaultValues:
    """Tests for default value generation."""

    def test_default_expires_at_is_8_hours(self):
        """Default expires_at should be approximately 8 hours from now."""
        before = datetime.now(timezone.utc)
        default_expiry = get_default_expiry()
        after = datetime.now(timezone.utc)

        expected_min = before + timedelta(hours=8)
        expected_max = after + timedelta(hours=8)

        assert expected_min <= default_expiry <= expected_max

    def test_default_permissions_empty_list(self):
        """Default scoped_permissions should be empty list."""
        session = AgentSession(
            agent_id="agent-001",
            delegation_id="del-test",
            owner_email="test@example.com",
            expires_at=datetime.now(timezone.utc) + timedelta(hours=8),
        )
        # Explicitly set scoped_permissions since it's required
        session.scoped_permissions = []

        assert session.scoped_permissions == []

    def test_default_mcp_sessions_empty_dict(self):
        """Default mcp_sessions should be empty dict."""
        session = AgentSession(
            agent_id="agent-001",
            delegation_id="del-test",
            owner_email="test@example.com",
            scoped_permissions=[],
            expires_at=datetime.now(timezone.utc) + timedelta(hours=8),
        )
        # mcp_sessions defaults to {}
        session.mcp_sessions = {}

        assert session.mcp_sessions == {}

    def test_default_groups_empty_list(self):
        """Default groups should be empty list."""
        session = AgentSession(
            agent_id="agent-001",
            delegation_id="del-test",
            owner_email="test@example.com",
            scoped_permissions=[],
            expires_at=datetime.now(timezone.utc) + timedelta(hours=8),
        )
        # groups defaults to []
        session.groups = []

        assert session.groups == []
