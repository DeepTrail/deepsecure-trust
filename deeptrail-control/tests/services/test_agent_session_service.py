"""Unit tests for AgentSessionService."""

import base64
import uuid
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock

import jwt
import pytest

from app.core.jwt_signing import reset_jwt_signing_service
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

# Note: We don't import AgentSession/DelegationToken for spec= usage
# because SQLAlchemy hybrid_property causes issues with MagicMock spec resolution
from app.services.agent_session_service import (
    AgentNotFoundError,
    AgentSessionService,
    AuthenticationResult,
    ChallengeExpiredError,
    InvalidSignatureError,
    NoDelegationError,
    SessionExpiredError,
    SessionNotFoundError,
    _pending_challenges,
)


# ─────────────────────────────────────────────────────────────────
# Fixtures
# ─────────────────────────────────────────────────────────────────


@pytest.fixture(autouse=True)
def _clear_pending_challenges():
    """Clear global pending challenges between tests."""
    _pending_challenges.clear()
    yield
    _pending_challenges.clear()


@pytest.fixture(autouse=True)
def _force_hs256_jwt_for_tests(monkeypatch, jwt_secret):
    """Align JWT signing with test decode key (HS256 + test secret)."""
    monkeypatch.setenv("JWT_ALGORITHM", "HS256")
    monkeypatch.setenv("SECRET_KEY", jwt_secret)
    monkeypatch.setenv("JWT_SECRET", jwt_secret)
    reset_jwt_signing_service()
    yield
    reset_jwt_signing_service()


@pytest.fixture
def ed25519_keypair():
    """Generate Ed25519 keypair for testing."""
    private_key = Ed25519PrivateKey.generate()
    public_key = private_key.public_key()

    public_bytes = public_key.public_bytes_raw()
    public_b64 = base64.urlsafe_b64encode(public_bytes).decode()

    return private_key, public_b64


@pytest.fixture
def mock_db_session():
    """Create mock database session."""
    session = MagicMock()
    session.query.return_value.filter.return_value.first.return_value = None
    session.query.return_value.filter.return_value.all.return_value = []
    session.query.return_value.filter.return_value.order_by.return_value.first.return_value = None
    return session


@pytest.fixture
def mock_delegation_service():
    """Create mock delegation service."""
    service = MagicMock()
    return service


@pytest.fixture
def jwt_secret():
    """JWT secret for testing."""
    return "test-secret-key-for-jwt-signing"


@pytest.fixture
def agent_id():
    """Standard agent ID for tests."""
    return f"agent-test-{uuid.uuid4().hex[:8]}"


@pytest.fixture
def agent_session_service(
    mock_db_session, mock_delegation_service, ed25519_keypair, jwt_secret, agent_id
):
    """Create AgentSessionService with test fixtures."""
    _, public_b64 = ed25519_keypair

    return AgentSessionService(
        db_session=mock_db_session,
        delegation_service=mock_delegation_service,
        jwt_secret=jwt_secret,
        agent_registry={agent_id: public_b64},
    )


@pytest.fixture
def mock_delegation(agent_id):
    """Create a mock delegation for testing.
    
    Note: We don't use spec=DelegationToken because SQLAlchemy hybrid_property
    causes issues with MagicMock spec resolution.
    """
    delegation = MagicMock()
    delegation.id = f"del-{uuid.uuid4().hex[:12]}"
    delegation.agent_id = agent_id
    delegation.is_valid = True
    delegation.delegated_permissions = ["notion:pages:search", "slack:messages:search"]
    delegation.delegator = "sarah@acme.com"
    delegation.delegator_idp = "https://acme.okta.com"
    delegation.created_at = datetime.now(timezone.utc)
    return delegation


def sign_challenge(private_key: Ed25519PrivateKey, challenge: str) -> str:
    """Helper to sign a challenge with Ed25519 private key."""
    signature_bytes = private_key.sign(challenge.encode("utf-8"))
    return base64.urlsafe_b64encode(signature_bytes).decode()


# ─────────────────────────────────────────────────────────────────
# Challenge Generation Tests
# ─────────────────────────────────────────────────────────────────


class TestChallengeGeneration:
    """Tests for challenge creation."""

    def test_create_challenge_success(self, agent_session_service, agent_id):
        """Test creating a challenge for registered agent."""
        challenge = agent_session_service.create_challenge(agent_id)

        assert challenge is not None
        # Decode and verify 256 bits (32 bytes)
        decoded = base64.urlsafe_b64decode(challenge)
        assert len(decoded) == 32

    def test_create_challenge_is_base64url_encoded(
        self, agent_session_service, agent_id
    ):
        """Test challenge is base64url encoded for transport."""
        challenge = agent_session_service.create_challenge(agent_id)

        # Should be valid base64url
        try:
            base64.urlsafe_b64decode(challenge)
        except Exception:
            pytest.fail("Challenge is not valid base64url")

    def test_create_challenge_agent_not_found(self, agent_session_service):
        """Test challenge creation fails for unknown agent."""
        with pytest.raises(AgentNotFoundError) as exc_info:
            agent_session_service.create_challenge("unknown-agent")

        assert "unknown-agent" in str(exc_info.value)

    def test_challenge_stored_with_expiration(self, agent_session_service, agent_id):
        """Test challenge is stored with expiration time."""
        agent_session_service.create_challenge(agent_id)

        assert agent_id in _pending_challenges
        _, expires_at = _pending_challenges[agent_id]
        assert expires_at > datetime.now(timezone.utc)

    def test_challenge_uniqueness(self, agent_session_service, agent_id):
        """Test each challenge is unique."""
        challenges = [agent_session_service.create_challenge(agent_id) for _ in range(10)]
        # All should be unique
        assert len(set(challenges)) == 10

    def test_challenge_ttl_is_5_minutes(self, agent_session_service, agent_id):
        """Test challenge expires approximately 5 minutes from creation."""
        before = datetime.now(timezone.utc)
        agent_session_service.create_challenge(agent_id)
        after = datetime.now(timezone.utc)

        _, expires_at = _pending_challenges[agent_id]

        # Should be ~5 minutes (300 seconds) from now
        expected_min = before + timedelta(seconds=300)
        expected_max = after + timedelta(seconds=300)

        assert expected_min <= expires_at <= expected_max


# ─────────────────────────────────────────────────────────────────
# Signature Verification Tests
# ─────────────────────────────────────────────────────────────────


class TestSignatureVerification:
    """Tests for Ed25519 signature verification."""

    def test_verify_valid_signature(
        self,
        agent_session_service,
        ed25519_keypair,
        mock_delegation_service,
        mock_delegation,
        agent_id,
    ):
        """Test successful signature verification."""
        private_key, _ = ed25519_keypair

        # Create challenge
        challenge = agent_session_service.create_challenge(agent_id)

        # Sign challenge
        signature = sign_challenge(private_key, challenge)

        # Mock delegation
        mock_delegation_service.get_delegations_for_agent.return_value = [
            mock_delegation
        ]

        # Verify
        result = agent_session_service.verify_and_create_session(
            agent_id, challenge, signature
        )

        assert isinstance(result, AuthenticationResult)
        assert result.session is not None
        assert result.token is not None
        assert result.expires_in == 8 * 3600

    def test_verify_invalid_signature(self, agent_session_service, agent_id):
        """Test invalid signature is rejected."""
        challenge = agent_session_service.create_challenge(agent_id)

        # Invalid signature (wrong bytes)
        invalid_sig = base64.urlsafe_b64encode(b"x" * 64).decode()

        with pytest.raises(InvalidSignatureError):
            agent_session_service.verify_and_create_session(
                agent_id, challenge, invalid_sig
            )

    def test_verify_wrong_key_signature(self, agent_session_service, agent_id):
        """Test signature from wrong key is rejected."""
        challenge = agent_session_service.create_challenge(agent_id)

        # Sign with different key
        wrong_key = Ed25519PrivateKey.generate()
        signature = sign_challenge(wrong_key, challenge)

        with pytest.raises(InvalidSignatureError):
            agent_session_service.verify_and_create_session(
                agent_id, challenge, signature
            )

    def test_verify_agent_not_found(self, agent_session_service, ed25519_keypair):
        """Test verification fails for unknown agent."""
        private_key, _ = ed25519_keypair

        with pytest.raises(AgentNotFoundError):
            agent_session_service.verify_and_create_session(
                "unknown-agent",
                "some-challenge",
                "some-signature",
            )


# ─────────────────────────────────────────────────────────────────
# Challenge Expiration Tests
# ─────────────────────────────────────────────────────────────────


class TestChallengeExpiration:
    """Tests for challenge expiration handling."""

    def test_challenge_expired(self, agent_session_service, ed25519_keypair, agent_id):
        """Test expired challenge is rejected."""
        private_key, _ = ed25519_keypair

        challenge = agent_session_service.create_challenge(agent_id)

        # Expire the challenge manually
        _pending_challenges[agent_id] = (
            challenge,
            datetime.now(timezone.utc) - timedelta(minutes=10),
        )

        signature = sign_challenge(private_key, challenge)

        with pytest.raises(ChallengeExpiredError) as exc_info:
            agent_session_service.verify_and_create_session(
                agent_id, challenge, signature
            )

        assert "expired" in str(exc_info.value).lower()

    def test_no_pending_challenge(self, agent_session_service, ed25519_keypair, agent_id):
        """Test error when no challenge was created."""
        private_key, _ = ed25519_keypair

        signature = sign_challenge(private_key, "fake-challenge")

        with pytest.raises(ChallengeExpiredError) as exc_info:
            agent_session_service.verify_and_create_session(
                agent_id, "fake-challenge", signature
            )

        assert "No pending challenge" in str(exc_info.value)

    def test_challenge_mismatch(
        self, agent_session_service, ed25519_keypair, agent_id
    ):
        """Test wrong challenge value is rejected."""
        private_key, _ = ed25519_keypair

        # Create challenge
        agent_session_service.create_challenge(agent_id)

        # Try with different challenge
        wrong_challenge = "wrong-challenge"
        signature = sign_challenge(private_key, wrong_challenge)

        with pytest.raises(ChallengeExpiredError) as exc_info:
            agent_session_service.verify_and_create_session(
                agent_id, wrong_challenge, signature
            )

        assert "mismatch" in str(exc_info.value).lower()

    def test_challenge_single_use(
        self,
        agent_session_service,
        ed25519_keypair,
        mock_delegation_service,
        mock_delegation,
        agent_id,
    ):
        """Test challenge cannot be reused."""
        private_key, _ = ed25519_keypair

        challenge = agent_session_service.create_challenge(agent_id)
        signature = sign_challenge(private_key, challenge)

        # Mock delegation
        mock_delegation_service.get_delegations_for_agent.return_value = [
            mock_delegation
        ]

        # First verification succeeds
        agent_session_service.verify_and_create_session(
            agent_id, challenge, signature
        )

        # Second attempt fails (challenge was cleared)
        with pytest.raises(ChallengeExpiredError):
            agent_session_service.verify_and_create_session(
                agent_id, challenge, signature
            )


# ─────────────────────────────────────────────────────────────────
# Delegation Tests
# ─────────────────────────────────────────────────────────────────


class TestDelegationHandling:
    """Tests for delegation lookup and validation."""

    def test_no_delegation_returns_empty_permissions(
        self,
        agent_session_service,
        ed25519_keypair,
        agent_id,
    ):
        """Test session created with empty permissions when no delegation exists."""
        private_key, _ = ed25519_keypair

        challenge = agent_session_service.create_challenge(agent_id)
        signature = sign_challenge(private_key, challenge)

        result = agent_session_service.verify_and_create_session(
            agent_id, challenge, signature
        )

        assert result.session is not None
        assert result.session.scoped_permissions == []

    def test_no_valid_delegation_returns_empty_permissions(
        self,
        agent_session_service,
        ed25519_keypair,
        agent_id,
    ):
        """Test session created with empty permissions when delegation is invalid."""
        private_key, _ = ed25519_keypair

        challenge = agent_session_service.create_challenge(agent_id)
        signature = sign_challenge(private_key, challenge)

        result = agent_session_service.verify_and_create_session(
            agent_id, challenge, signature
        )

        assert result.session is not None
        assert result.session.scoped_permissions == []

    def test_specific_delegation_id(
        self,
        agent_session_service,
        ed25519_keypair,
        agent_id,
    ):
        """Test using a specific delegation_id."""
        private_key, _ = ed25519_keypair

        challenge = agent_session_service.create_challenge(agent_id)
        signature = sign_challenge(private_key, challenge)

        result = agent_session_service.verify_and_create_session(
            agent_id, challenge, signature, delegation_id="test-delegation-123"
        )

        assert result.session is not None
        assert result.session.delegation_id == "test-delegation-123"


# ─────────────────────────────────────────────────────────────────
# JWT Generation Tests
# ─────────────────────────────────────────────────────────────────


class TestJWTGeneration:
    """Tests for JWT token generation."""

    def test_jwt_contains_required_claims(
        self,
        agent_session_service,
        ed25519_keypair,
        jwt_secret,
        agent_id,
        mock_delegation,
    ):
        """Test JWT contains all required claims from design doc."""
        private_key, _ = ed25519_keypair

        agent_session_service.db.query.return_value.filter.return_value.order_by.return_value.first.return_value = mock_delegation

        def _fake_refresh(session):
            if not hasattr(session, "id") or session.id is None:
                session.id = f"asess-{uuid.uuid4().hex[:12]}"
            if not hasattr(session, "created_at") or session.created_at is None:
                session.created_at = datetime.now(timezone.utc)

        agent_session_service.db.refresh.side_effect = _fake_refresh

        challenge = agent_session_service.create_challenge(agent_id)
        signature = sign_challenge(private_key, challenge)

        result = agent_session_service.verify_and_create_session(
            agent_id, challenge, signature
        )

        claims = jwt.decode(
            result.token,
            jwt_secret,
            algorithms=["HS256"],
            audience="deeptrail-gateway",
        )

        assert claims["sub"] == agent_id
        assert claims["owner"] == "sarah@acme.com"
        assert claims["iss"] == "deeptrail-control"
        assert claims["aud"] == "deeptrail-gateway"
        assert "session_id" in claims
        assert "exp" in claims
        assert "iat" in claims
        assert "delegated_permissions" in claims

    def test_jwt_expiration_matches_session(
        self,
        agent_session_service,
        ed25519_keypair,
        jwt_secret,
        agent_id,
    ):
        """Test JWT expiration is 8 hours."""
        private_key, _ = ed25519_keypair

        challenge = agent_session_service.create_challenge(agent_id)
        signature = sign_challenge(private_key, challenge)

        before = datetime.now(timezone.utc)

        result = agent_session_service.verify_and_create_session(
            agent_id, challenge, signature
        )
        after = datetime.now(timezone.utc)

        claims = jwt.decode(
            result.token,
            jwt_secret,
            algorithms=["HS256"],
            audience="deeptrail-gateway",
        )

        exp_datetime = datetime.fromtimestamp(claims["exp"], tz=timezone.utc)

        expected_min = before + timedelta(hours=8) - timedelta(seconds=1)
        expected_max = after + timedelta(hours=8) + timedelta(seconds=1)

        assert expected_min <= exp_datetime <= expected_max


# ─────────────────────────────────────────────────────────────────
# Session Management Tests
# ─────────────────────────────────────────────────────────────────


class TestSessionManagement:
    """Tests for session lifecycle operations."""

    def test_get_session(self, agent_session_service, mock_db_session):
        """Test retrieving a session by ID."""
        mock_session = MagicMock()
        mock_db_session.query.return_value.filter.return_value.first.return_value = (
            mock_session
        )

        result = agent_session_service.get_session("asess-test-123")

        assert result == mock_session

    def test_get_session_not_found(self, agent_session_service, mock_db_session):
        """Test get_session returns None for missing session."""
        mock_db_session.query.return_value.filter.return_value.first.return_value = None

        result = agent_session_service.get_session("asess-nonexistent")

        assert result is None

    def test_validate_session_valid(self, agent_session_service, mock_db_session):
        """Test session validation for valid session."""
        mock_session = MagicMock()
        mock_session.is_valid = True
        mock_db_session.query.return_value.filter.return_value.first.return_value = (
            mock_session
        )

        assert agent_session_service.validate_session("asess-123") is True

    def test_validate_session_invalid(self, agent_session_service, mock_db_session):
        """Test session validation for invalid session."""
        mock_session = MagicMock()
        mock_session.is_valid = False
        mock_db_session.query.return_value.filter.return_value.first.return_value = (
            mock_session
        )

        assert agent_session_service.validate_session("asess-123") is False

    def test_validate_session_not_found(self, agent_session_service, mock_db_session):
        """Test session validation for missing session."""
        mock_db_session.query.return_value.filter.return_value.first.return_value = None

        assert agent_session_service.validate_session("asess-nonexistent") is False

    def test_revoke_session(self, agent_session_service, mock_db_session):
        """Test session revocation."""
        mock_session = MagicMock()
        mock_db_session.query.return_value.filter.return_value.first.return_value = (
            mock_session
        )

        result = agent_session_service.revoke_session(
            "asess-123", revoked_by="sarah@acme.com", reason="User requested"
        )

        assert result is True
        mock_session.revoke.assert_called_once_with(
            revoked_by="sarah@acme.com", reason="User requested"
        )
        mock_db_session.commit.assert_called()

    def test_revoke_session_not_found(self, agent_session_service, mock_db_session):
        """Test revoke returns False for missing session."""
        mock_db_session.query.return_value.filter.return_value.first.return_value = None

        result = agent_session_service.revoke_session("asess-nonexistent")

        assert result is False

    def test_touch_session(self, agent_session_service, mock_db_session):
        """Test updating session activity."""
        mock_session = MagicMock()
        mock_session.is_valid = True
        mock_db_session.query.return_value.filter.return_value.first.return_value = (
            mock_session
        )

        result = agent_session_service.touch_session("asess-123")

        assert result is True
        mock_session.touch.assert_called_once()
        mock_db_session.commit.assert_called()


# ─────────────────────────────────────────────────────────────────
# Bulk Revocation Tests
# ─────────────────────────────────────────────────────────────────


class TestBulkRevocation:
    """Tests for bulk session revocation."""

    def test_revoke_all_for_agent(self, agent_session_service, mock_db_session, agent_id):
        """Test revoking all sessions for an agent."""
        mock_session1 = MagicMock()
        mock_session1.is_valid = True
        mock_session2 = MagicMock()
        mock_session2.is_valid = True
        mock_db_session.query.return_value.filter.return_value.all.return_value = [
            mock_session1,
            mock_session2,
        ]

        count = agent_session_service.revoke_all_for_agent(
            agent_id, revoked_by="admin", reason="Security incident"
        )

        assert count == 2
        mock_session1.revoke.assert_called_once()
        mock_session2.revoke.assert_called_once()

    def test_revoke_all_for_delegation(self, agent_session_service, mock_db_session):
        """Test revoking all sessions for a delegation."""
        mock_session1 = MagicMock()
        mock_session2 = MagicMock()
        mock_db_session.query.return_value.filter.return_value.all.return_value = [
            mock_session1,
            mock_session2,
        ]

        count = agent_session_service.revoke_all_for_delegation(
            "del-123", revoked_by="system", reason="Delegation revoked"
        )

        assert count == 2
        mock_session1.revoke.assert_called_once()
        mock_session2.revoke.assert_called_once()


# ─────────────────────────────────────────────────────────────────
# Token Decoding Tests
# ─────────────────────────────────────────────────────────────────


class TestTokenDecoding:
    """Tests for JWT token decoding."""

    def test_get_session_by_token_success(
        self, agent_session_service, mock_db_session, jwt_secret
    ):
        """Test retrieving session from valid token."""
        mock_session = MagicMock()
        mock_session.is_valid = True
        mock_db_session.query.return_value.filter.return_value.first.return_value = (
            mock_session
        )

        # Create a valid token
        claims = {
            "session_id": "asess-test-123",
            "sub": "agent-001",
            "iss": "deeptrail-control",
            "aud": "deeptrail-gateway",
            "exp": int((datetime.now(timezone.utc) + timedelta(hours=8)).timestamp()),
        }
        token = jwt.encode(claims, jwt_secret, algorithm="HS256")

        result = agent_session_service.get_session_by_token(token)

        assert result == mock_session

    def test_get_session_by_token_expired(self, agent_session_service, jwt_secret):
        """Test expired token raises SessionExpiredError."""
        claims = {
            "session_id": "asess-test-123",
            "sub": "agent-001",
            "iss": "deeptrail-control",
            "aud": "deeptrail-gateway",
            "exp": int((datetime.now(timezone.utc) - timedelta(hours=1)).timestamp()),
        }
        token = jwt.encode(claims, jwt_secret, algorithm="HS256")

        with pytest.raises(SessionExpiredError) as exc_info:
            agent_session_service.get_session_by_token(token)

        assert "JWT has expired" in str(exc_info.value)

    def test_get_session_by_token_invalid_session(
        self, agent_session_service, mock_db_session, jwt_secret
    ):
        """Test invalid session raises error."""
        mock_session = MagicMock()
        mock_session.is_valid = False
        mock_db_session.query.return_value.filter.return_value.first.return_value = (
            mock_session
        )

        claims = {
            "session_id": "asess-test-123",
            "sub": "agent-001",
            "iss": "deeptrail-control",
            "aud": "deeptrail-gateway",
            "exp": int((datetime.now(timezone.utc) + timedelta(hours=8)).timestamp()),
        }
        token = jwt.encode(claims, jwt_secret, algorithm="HS256")

        with pytest.raises(SessionExpiredError):
            agent_session_service.get_session_by_token(token)

    def test_get_session_by_token_not_found(
        self, agent_session_service, mock_db_session, jwt_secret
    ):
        """Test missing session raises SessionNotFoundError."""
        mock_db_session.query.return_value.filter.return_value.first.return_value = None

        claims = {
            "session_id": "asess-nonexistent",
            "sub": "agent-001",
            "iss": "deeptrail-control",
            "aud": "deeptrail-gateway",
            "exp": int((datetime.now(timezone.utc) + timedelta(hours=8)).timestamp()),
        }
        token = jwt.encode(claims, jwt_secret, algorithm="HS256")

        with pytest.raises(SessionNotFoundError):
            agent_session_service.get_session_by_token(token)


# ─────────────────────────────────────────────────────────────────
# Agent Registry Tests
# ─────────────────────────────────────────────────────────────────


class TestAgentRegistry:
    """Tests for agent registry management."""

    def test_register_agent(self, agent_session_service, ed25519_keypair):
        """Test registering a new agent."""
        _, public_b64 = ed25519_keypair
        new_agent_id = "agent-new-001"

        agent_session_service.register_agent(new_agent_id, public_b64)

        assert new_agent_id in agent_session_service.agent_registry
        assert agent_session_service.is_agent_registered(new_agent_id)

    def test_register_agent_invalid_key(self, agent_session_service):
        """Test registering with invalid key fails."""
        with pytest.raises(ValueError) as exc_info:
            agent_session_service.register_agent("agent-bad", "not-a-valid-key")

        assert "Invalid Ed25519 public key" in str(exc_info.value)

    def test_register_agent_wrong_key_size(self, agent_session_service):
        """Test registering with wrong key size fails."""
        # 16 bytes instead of 32
        wrong_size = base64.urlsafe_b64encode(b"x" * 16).decode()

        with pytest.raises(ValueError) as exc_info:
            agent_session_service.register_agent("agent-bad", wrong_size)

        assert "32 bytes" in str(exc_info.value)

    def test_unregister_agent(self, agent_session_service, agent_id):
        """Test unregistering an agent."""
        result = agent_session_service.unregister_agent(agent_id)

        assert result is True
        assert agent_id not in agent_session_service.agent_registry

    def test_unregister_agent_not_found(self, agent_session_service):
        """Test unregistering unknown agent returns False."""
        result = agent_session_service.unregister_agent("agent-unknown")

        assert result is False

    def test_is_agent_registered(self, agent_session_service, agent_id):
        """Test checking agent registration."""
        assert agent_session_service.is_agent_registered(agent_id) is True
        assert agent_session_service.is_agent_registered("unknown") is False


# ─────────────────────────────────────────────────────────────────
# Permission Checking Tests
# ─────────────────────────────────────────────────────────────────


class TestPermissionChecking:
    """Tests for session permission checking."""

    def test_check_session_permission_granted(
        self, agent_session_service, mock_db_session
    ):
        """Test permission check for granted permission."""
        mock_session = MagicMock()
        mock_session.is_valid = True
        mock_session.has_permission.return_value = True
        mock_db_session.query.return_value.filter.return_value.first.return_value = (
            mock_session
        )

        result = agent_session_service.check_session_permission(
            "asess-123", "notion:pages:search"
        )

        assert result is True
        mock_session.has_permission.assert_called_once_with("notion:pages:search")

    def test_check_session_permission_denied(
        self, agent_session_service, mock_db_session
    ):
        """Test permission check for denied permission."""
        mock_session = MagicMock()
        mock_session.is_valid = True
        mock_session.has_permission.return_value = False
        mock_db_session.query.return_value.filter.return_value.first.return_value = (
            mock_session
        )

        result = agent_session_service.check_session_permission(
            "asess-123", "notion:pages:delete"
        )

        assert result is False

    def test_check_session_permission_invalid_session(
        self, agent_session_service, mock_db_session
    ):
        """Test permission check for invalid session."""
        mock_session = MagicMock()
        mock_session.is_valid = False
        mock_db_session.query.return_value.filter.return_value.first.return_value = (
            mock_session
        )

        result = agent_session_service.check_session_permission(
            "asess-123", "notion:pages:search"
        )

        assert result is False


# ─────────────────────────────────────────────────────────────────
# Challenge Cleanup Tests
# ─────────────────────────────────────────────────────────────────


class TestChallengeCleanup:
    """Tests for challenge cleanup operations."""

    def test_get_pending_challenge(self, agent_session_service, agent_id):
        """Test getting pending challenge."""
        challenge = agent_session_service.create_challenge(agent_id)

        result = agent_session_service.get_pending_challenge(agent_id)

        assert result == challenge

    def test_get_pending_challenge_expired(self, agent_session_service, agent_id):
        """Test expired challenge returns None."""
        challenge = agent_session_service.create_challenge(agent_id)

        # Expire it
        _pending_challenges[agent_id] = (
            challenge,
            datetime.now(timezone.utc) - timedelta(minutes=10),
        )

        result = agent_session_service.get_pending_challenge(agent_id)

        assert result is None

    def test_get_pending_challenge_not_found(self, agent_session_service):
        """Test no pending challenge returns None."""
        result = agent_session_service.get_pending_challenge("agent-unknown")

        assert result is None

    def test_clear_expired_challenges(self, agent_session_service, agent_id):
        """Test clearing expired challenges."""
        # Create some challenges
        agent_session_service.create_challenge(agent_id)

        # Expire one
        _pending_challenges[agent_id] = (
            "expired-challenge",
            datetime.now(timezone.utc) - timedelta(minutes=10),
        )

        # Add another expired one
        _pending_challenges["expired-agent"] = (
            "another-expired",
            datetime.now(timezone.utc) - timedelta(minutes=20),
        )

        count = agent_session_service.clear_expired_challenges()

        assert count == 2
        assert agent_id not in _pending_challenges
        assert "expired-agent" not in _pending_challenges


# ─────────────────────────────────────────────────────────────────
# Security Tests
# ─────────────────────────────────────────────────────────────────


class TestSecurityProperties:
    """Tests for security properties."""

    def test_challenge_is_cryptographically_random(self, agent_session_service, agent_id):
        """Test challenges are cryptographically random."""
        challenges = [agent_session_service.create_challenge(agent_id) for _ in range(100)]

        # All unique
        assert len(set(challenges)) == 100

        # All 32 bytes when decoded
        for challenge in challenges:
            decoded = base64.urlsafe_b64decode(challenge)
            assert len(decoded) == 32

    def test_jwt_secret_not_in_token(
        self,
        agent_session_service,
        ed25519_keypair,
        mock_delegation_service,
        mock_delegation,
        jwt_secret,
        agent_id,
    ):
        """Test JWT secret is not exposed in token."""
        private_key, _ = ed25519_keypair

        challenge = agent_session_service.create_challenge(agent_id)
        signature = sign_challenge(private_key, challenge)

        mock_delegation_service.get_delegations_for_agent.return_value = [
            mock_delegation
        ]

        result = agent_session_service.verify_and_create_session(
            agent_id, challenge, signature
        )

        # Token should not contain the secret
        assert jwt_secret not in result.token

    def test_session_ttl_shorter_than_delegation(self):
        """Test session TTL (8h) is shorter than delegation (7d)."""
        assert AgentSessionService.SESSION_TTL_HOURS == 8
        # 8 hours < 7 days (168 hours)
        assert AgentSessionService.SESSION_TTL_HOURS < 168
