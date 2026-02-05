# Task: WS-A8 Implement AgentSessionService

---

## Metadata

| Field | Value |
|-------|-------|
| **Status** | `ready` |
| **Design Doc** | [deepsecure-virtual-mcp-server-mvp.md](../../../design/internal/markdowns/deepsecure-virtual-mcp-server-mvp.md) |
| **Workstream** | WS-A: Control Plane Foundation |
| **Dependencies** | A6 (DelegationService), A7 (Agent Session model) |
| **Blocked By** | None (A6, A7 are complete ✅) |
| **Assigned** | - |
| **Created** | January 30, 2026 |
| **Estimated Complexity** | `M` (2-4 hours) |
| **Batch** | 4 |

---

## Validation Mapping

| Mapping | Value |
|---------|-------|
| **Validates Demo** | Demo 3: Delegation Execution, Demo 4: Permission Enforcement |
| **Validates User Journey Step** | Step 5: Agent Authenticates |

---

## Pre-Conditions

Before starting this task, ensure:

- [x] A6 (DelegationService) is complete
- [x] A7 (Agent Session model) is complete
- [ ] `deeptrail-control/` service structure exists
- [ ] AgentSession model can be imported from `deeptrail-control.models`
- [ ] DelegationService can be imported
- [ ] Ed25519 cryptographic utilities available (or use `cryptography` library)

---

## Task Description

Implement the AgentSessionService that manages the agent authentication lifecycle via challenge-response and issues Agent Session JWTs. This is the core service enabling Step 5 of Sarah's journey where an agent authenticates and receives a scoped JWT.

### Context

From the MVP design (Section 2.6 - Step 5: Agent Authenticates):

```
Agent Authentication Flow:

1. Agent requests challenge:
   POST /api/v1/auth/agent/challenge
   { "agent_id": "agent-sdr-001" }
   
   Response: { "challenge": "random-nonce-xyz" }

2. Agent signs challenge with Ed25519 private key

3. Agent submits signature for verification:
   POST /api/v1/auth/agent/verify
   {
     "agent_id": "agent-sdr-001",
     "challenge": "random-nonce-xyz",
     "signature": "ed25519-signature-of-challenge"
   }

4. Control Plane validates signature, issues JWT:
   {
     "access_token": "eyJhbG...",
     "token_type": "Bearer",
     "expires_in": 28800
   }
```

The service must:
- **Generate Challenge**: Create cryptographically secure nonces
- **Verify Signature**: Validate Ed25519 signatures against registered public keys
- **Issue JWT**: Create Agent Session JWT with scoped permissions from delegation
- **Manage Sessions**: Track active sessions, handle expiry/revocation
- **Link to Delegation**: Each session is scoped to a specific delegation

### Technical Notes

- Use `cryptography` library for Ed25519 signature verification
- Use `PyJWT` for JWT generation with RS256 or EdDSA
- Nonces must be single-use (clear after verification)
- Challenge TTL: 5 minutes
- Session TTL: 8 hours (shorter than delegation's 7 days)
- Store agent public keys (MVP: can be in database or config)

---

## Files to Create/Modify

| File | Action | Description |
|------|--------|-------------|
| `deeptrail-control/services/agent_session_service.py` | **CREATE** | AgentSessionService implementation |
| `deeptrail-control/services/__init__.py` | **MODIFY** | Export AgentSessionService |
| `deeptrail-control/tests/services/test_agent_session_service.py` | **CREATE** | Unit tests |

---

## Implementation Details

### 1. AgentSessionService (`deeptrail-control/services/agent_session_service.py`)

```python
"""Agent Session Service for Virtual MCP Server MVP.

Manages agent authentication via Ed25519 challenge-response and issues
Agent Session JWTs (Layer 3) for accessing the Virtual MCP Server gateway.

Authentication Flow:
1. Agent calls create_challenge(agent_id) → receives nonce
2. Agent signs nonce with Ed25519 private key
3. Agent calls verify_and_create_session(agent_id, challenge, signature)
4. Service validates signature, creates AgentSession, returns JWT

Security Properties:
- Nonces are single-use and expire in 5 minutes
- JWTs are scoped to specific delegation permissions
- Sessions are shorter-lived (8h) than delegations (7d)
"""

import secrets
import jwt
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List, Tuple
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
from cryptography.hazmat.primitives import serialization
from cryptography.exceptions import InvalidSignature
import base64

from models.agent_session import AgentSession, PartyType
from models.delegation import DelegationToken
from services.delegation_service import DelegationService


class AgentNotFoundError(Exception):
    """Raised when agent_id is not found in registry."""
    pass


class ChallengeExpiredError(Exception):
    """Raised when challenge nonce has expired or doesn't exist."""
    pass


class InvalidSignatureError(Exception):
    """Raised when Ed25519 signature verification fails."""
    pass


class NoDelegationError(Exception):
    """Raised when no valid delegation exists for the agent."""
    pass


class SessionExpiredError(Exception):
    """Raised when attempting to use an expired session."""
    pass


class AgentSessionService:
    """
    Service for managing agent authentication and session lifecycle.
    
    Handles:
    - Challenge generation for Ed25519 authentication
    - Signature verification
    - Agent Session JWT issuance
    - Session lifecycle (creation, validation, revocation)
    
    Dependencies:
    - DelegationService: For fetching agent's delegated permissions
    - AgentSession model: For persisting session state
    - Agent registry: For Ed25519 public key lookup
    """
    
    # Constants
    CHALLENGE_BYTES = 32  # 256-bit nonce
    CHALLENGE_TTL_SECONDS = 300  # 5 minutes
    SESSION_TTL_HOURS = 8
    JWT_ALGORITHM = "HS256"  # MVP: Use symmetric key; Production: RS256 or EdDSA
    
    def __init__(
        self,
        db_session,
        delegation_service: DelegationService,
        jwt_secret: str,
        agent_registry: Optional[Dict[str, str]] = None
    ):
        """
        Initialize AgentSessionService.
        
        Args:
            db_session: SQLAlchemy database session
            delegation_service: Service for delegation operations
            jwt_secret: Secret key for JWT signing (MVP: symmetric)
            agent_registry: Dict mapping agent_id → base64 Ed25519 public key
                           MVP: Can be hardcoded; Production: from database
        """
        self.db = db_session
        self.delegation_service = delegation_service
        self.jwt_secret = jwt_secret
        self.agent_registry = agent_registry or {}
        
        # In-memory pending challenges (MVP)
        # Production: Use Redis with TTL
        self._pending_challenges: Dict[str, Tuple[str, datetime]] = {}
    
    # ─────────────────────────────────────────────────────────────────
    # Challenge-Response Authentication
    # ─────────────────────────────────────────────────────────────────
    
    def create_challenge(self, agent_id: str) -> str:
        """
        Create a cryptographic challenge for agent authentication.
        
        Args:
            agent_id: The agent's unique identifier
            
        Returns:
            A base64-encoded random nonce (challenge)
            
        Raises:
            AgentNotFoundError: If agent_id is not in the registry
        """
        # Verify agent exists
        if agent_id not in self.agent_registry:
            raise AgentNotFoundError(f"Agent '{agent_id}' not found in registry")
        
        # Generate cryptographically secure nonce
        nonce_bytes = secrets.token_bytes(self.CHALLENGE_BYTES)
        nonce = base64.urlsafe_b64encode(nonce_bytes).decode('utf-8')
        
        # Store with expiration
        expires_at = datetime.utcnow() + timedelta(seconds=self.CHALLENGE_TTL_SECONDS)
        self._pending_challenges[agent_id] = (nonce, expires_at)
        
        return nonce
    
    def verify_and_create_session(
        self,
        agent_id: str,
        challenge: str,
        signature: str,
        delegation_id: Optional[str] = None
    ) -> Tuple[AgentSession, str]:
        """
        Verify agent's signature and create an authenticated session.
        
        Args:
            agent_id: The agent's unique identifier
            challenge: The nonce that was signed
            signature: Base64-encoded Ed25519 signature of the challenge
            delegation_id: Optional specific delegation to use (else uses latest valid)
            
        Returns:
            Tuple of (AgentSession, JWT token string)
            
        Raises:
            AgentNotFoundError: If agent_id is not in registry
            ChallengeExpiredError: If challenge doesn't exist or expired
            InvalidSignatureError: If signature verification fails
            NoDelegationError: If no valid delegation exists for agent
        """
        # 1. Verify agent exists
        if agent_id not in self.agent_registry:
            raise AgentNotFoundError(f"Agent '{agent_id}' not found in registry")
        
        # 2. Verify challenge is valid
        if agent_id not in self._pending_challenges:
            raise ChallengeExpiredError("No pending challenge for this agent")
        
        stored_challenge, expires_at = self._pending_challenges[agent_id]
        
        if datetime.utcnow() > expires_at:
            del self._pending_challenges[agent_id]
            raise ChallengeExpiredError("Challenge has expired")
        
        if stored_challenge != challenge:
            raise ChallengeExpiredError("Challenge mismatch")
        
        # 3. Verify Ed25519 signature
        if not self._verify_signature(agent_id, challenge, signature):
            raise InvalidSignatureError("Signature verification failed")
        
        # 4. Clear the used challenge (single-use)
        del self._pending_challenges[agent_id]
        
        # 5. Get valid delegation for this agent
        delegation = self._get_valid_delegation(agent_id, delegation_id)
        if not delegation:
            raise NoDelegationError(f"No valid delegation found for agent '{agent_id}'")
        
        # 6. Create agent session
        session = self._create_session(agent_id, delegation)
        
        # 7. Generate JWT
        token = self._generate_jwt(session)
        
        return session, token
    
    def _verify_signature(self, agent_id: str, challenge: str, signature: str) -> bool:
        """
        Verify Ed25519 signature against agent's registered public key.
        
        Args:
            agent_id: Agent's identifier
            challenge: The message that was signed
            signature: Base64-encoded signature
            
        Returns:
            True if signature is valid, False otherwise
        """
        try:
            # Get agent's public key
            public_key_b64 = self.agent_registry.get(agent_id)
            if not public_key_b64:
                return False
            
            # Decode public key
            public_key_bytes = base64.urlsafe_b64decode(public_key_b64)
            public_key = Ed25519PublicKey.from_public_bytes(public_key_bytes)
            
            # Decode signature
            signature_bytes = base64.urlsafe_b64decode(signature)
            
            # Verify
            challenge_bytes = challenge.encode('utf-8')
            public_key.verify(signature_bytes, challenge_bytes)
            
            return True
            
        except (InvalidSignature, ValueError, Exception):
            return False
    
    def _get_valid_delegation(
        self,
        agent_id: str,
        delegation_id: Optional[str] = None
    ) -> Optional[DelegationToken]:
        """
        Get a valid delegation for the agent.
        
        Args:
            agent_id: Agent's identifier (matches delegation.sub)
            delegation_id: Specific delegation ID, or None for latest valid
            
        Returns:
            Valid DelegationToken or None
        """
        if delegation_id:
            delegation = self.delegation_service.get_delegation(delegation_id)
            if delegation and delegation.sub == agent_id and delegation.is_valid:
                return delegation
            return None
        
        # Get latest valid delegation for this agent
        delegations = self.delegation_service.get_delegations_for_agent(agent_id)
        valid_delegations = [d for d in delegations if d.is_valid]
        
        if not valid_delegations:
            return None
        
        # Return most recently created
        return max(valid_delegations, key=lambda d: d.created_at)
    
    def _create_session(
        self,
        agent_id: str,
        delegation: DelegationToken
    ) -> AgentSession:
        """
        Create a new AgentSession from a delegation.
        
        Args:
            agent_id: Agent's identifier
            delegation: The delegation providing permissions
            
        Returns:
            Newly created AgentSession
        """
        session = AgentSession(
            agent_id=agent_id,
            delegation_id=delegation.id,
            party_type=PartyType.FIRST_PARTY,  # MVP: assume first-party
            scoped_permissions=delegation.delegated_permissions,
            owner_email=delegation.delegator,
            idp_issuer=delegation.delegator_idp,
            groups=delegation.groups if hasattr(delegation, 'groups') else [],
            expires_at=datetime.utcnow() + timedelta(hours=self.SESSION_TTL_HOURS)
        )
        
        self.db.add(session)
        self.db.commit()
        self.db.refresh(session)
        
        return session
    
    def _generate_jwt(self, session: AgentSession) -> str:
        """
        Generate JWT token for an agent session.
        
        Args:
            session: The AgentSession to encode
            
        Returns:
            Signed JWT token string
        """
        claims = session.to_jwt_claims()
        
        # Add standard JWT claims
        claims["iss"] = "deeptrail-control"
        claims["aud"] = "deeptrail-gateway"
        
        token = jwt.encode(
            claims,
            self.jwt_secret,
            algorithm=self.JWT_ALGORITHM
        )
        
        return token
    
    # ─────────────────────────────────────────────────────────────────
    # Session Management
    # ─────────────────────────────────────────────────────────────────
    
    def get_session(self, session_id: str) -> Optional[AgentSession]:
        """
        Get an agent session by ID.
        
        Args:
            session_id: The session identifier
            
        Returns:
            AgentSession or None if not found
        """
        return self.db.query(AgentSession).filter(
            AgentSession.session_id == session_id
        ).first()
    
    def get_session_by_token(self, token: str) -> Optional[AgentSession]:
        """
        Decode JWT and retrieve the associated session.
        
        Args:
            token: JWT token string
            
        Returns:
            AgentSession or None if invalid/expired
            
        Raises:
            SessionExpiredError: If session has expired
        """
        try:
            claims = jwt.decode(
                token,
                self.jwt_secret,
                algorithms=[self.JWT_ALGORITHM],
                audience="deeptrail-gateway"
            )
            
            session_id = claims.get("session_id")
            if not session_id:
                return None
            
            session = self.get_session(session_id)
            
            if session and not session.is_valid:
                raise SessionExpiredError("Session has expired or been revoked")
            
            return session
            
        except jwt.ExpiredSignatureError:
            raise SessionExpiredError("JWT has expired")
        except jwt.InvalidTokenError:
            return None
    
    def validate_session(self, session_id: str) -> bool:
        """
        Check if a session is valid (active, not expired, not revoked).
        
        Args:
            session_id: The session identifier
            
        Returns:
            True if session is valid
        """
        session = self.get_session(session_id)
        return session is not None and session.is_valid
    
    def revoke_session(
        self,
        session_id: str,
        revoked_by: str = "system",
        reason: str = None
    ) -> bool:
        """
        Revoke an agent session.
        
        Args:
            session_id: The session to revoke
            revoked_by: Who initiated the revocation
            reason: Optional reason for revocation
            
        Returns:
            True if revoked, False if session not found
        """
        session = self.get_session(session_id)
        if not session:
            return False
        
        session.revoke(revoked_by=revoked_by, reason=reason)
        self.db.commit()
        
        return True
    
    def revoke_all_for_agent(
        self,
        agent_id: str,
        revoked_by: str = "system",
        reason: str = None
    ) -> int:
        """
        Revoke all active sessions for an agent.
        
        Args:
            agent_id: The agent whose sessions to revoke
            revoked_by: Who initiated the revocation
            reason: Optional reason
            
        Returns:
            Number of sessions revoked
        """
        sessions = self.db.query(AgentSession).filter(
            AgentSession.agent_id == agent_id,
            AgentSession.is_active == True
        ).all()
        
        count = 0
        for session in sessions:
            if session.is_valid:
                session.revoke(revoked_by=revoked_by, reason=reason)
                count += 1
        
        self.db.commit()
        return count
    
    def revoke_all_for_delegation(
        self,
        delegation_id: str,
        revoked_by: str = "system",
        reason: str = "Delegation revoked"
    ) -> int:
        """
        Revoke all sessions using a specific delegation.
        
        Called when a delegation is revoked to cascade to sessions.
        
        Args:
            delegation_id: The delegation whose sessions to revoke
            revoked_by: Who initiated
            reason: Reason for revocation
            
        Returns:
            Number of sessions revoked
        """
        sessions = self.db.query(AgentSession).filter(
            AgentSession.delegation_id == delegation_id,
            AgentSession.is_active == True
        ).all()
        
        count = 0
        for session in sessions:
            session.revoke(revoked_by=revoked_by, reason=reason)
            count += 1
        
        self.db.commit()
        return count
    
    def get_active_sessions_for_agent(self, agent_id: str) -> List[AgentSession]:
        """
        Get all active sessions for an agent.
        
        Args:
            agent_id: The agent's identifier
            
        Returns:
            List of active AgentSession objects
        """
        sessions = self.db.query(AgentSession).filter(
            AgentSession.agent_id == agent_id,
            AgentSession.is_active == True
        ).all()
        
        return [s for s in sessions if s.is_valid]
    
    def touch_session(self, session_id: str) -> bool:
        """
        Update last activity timestamp for a session.
        
        Args:
            session_id: The session to touch
            
        Returns:
            True if updated, False if session not found
        """
        session = self.get_session(session_id)
        if not session or not session.is_valid:
            return False
        
        session.touch()
        self.db.commit()
        return True
    
    # ─────────────────────────────────────────────────────────────────
    # Agent Registry Management (MVP)
    # ─────────────────────────────────────────────────────────────────
    
    def register_agent(self, agent_id: str, public_key_b64: str) -> None:
        """
        Register an agent's Ed25519 public key.
        
        Args:
            agent_id: Unique agent identifier
            public_key_b64: Base64-encoded Ed25519 public key (32 bytes)
        """
        # Validate key format
        try:
            key_bytes = base64.urlsafe_b64decode(public_key_b64)
            Ed25519PublicKey.from_public_bytes(key_bytes)
        except Exception as e:
            raise ValueError(f"Invalid Ed25519 public key: {e}")
        
        self.agent_registry[agent_id] = public_key_b64
    
    def unregister_agent(self, agent_id: str) -> bool:
        """
        Remove an agent from the registry.
        
        Args:
            agent_id: The agent to remove
            
        Returns:
            True if removed, False if not found
        """
        if agent_id in self.agent_registry:
            del self.agent_registry[agent_id]
            return True
        return False
```

### 2. Update `__init__.py`

```python
# Add to deeptrail-control/services/__init__.py
from .agent_session_service import (
    AgentSessionService,
    AgentNotFoundError,
    ChallengeExpiredError,
    InvalidSignatureError,
    NoDelegationError,
    SessionExpiredError,
)

__all__ = [
    # ... existing exports ...
    "AgentSessionService",
    "AgentNotFoundError",
    "ChallengeExpiredError",
    "InvalidSignatureError",
    "NoDelegationError",
    "SessionExpiredError",
]
```

---

## Acceptance Criteria

### Challenge-Response Criteria

- [ ] `create_challenge()` generates 256-bit cryptographically secure nonce
- [ ] Challenge is base64url-encoded for transport
- [ ] Challenge expires after 5 minutes (configurable)
- [ ] `AgentNotFoundError` raised if agent not in registry
- [ ] Pending challenges stored with expiration timestamp

### Signature Verification Criteria

- [ ] Ed25519 signature verification using `cryptography` library
- [ ] Signature decoded from base64url format
- [ ] Public key looked up from agent registry
- [ ] `InvalidSignatureError` raised on verification failure
- [ ] Challenge cleared (single-use) after successful verification

### JWT Issuance Criteria

- [ ] JWT contains all claims from `AgentSession.to_jwt_claims()`
- [ ] JWT includes `iss` (deeptrail-control) and `aud` (deeptrail-gateway)
- [ ] JWT signed with configurable algorithm (MVP: HS256)
- [ ] JWT expiration matches session expiration (8 hours)

### Session Management Criteria

- [ ] `get_session()` retrieves session by session_id
- [ ] `get_session_by_token()` decodes JWT and returns session
- [ ] `validate_session()` checks active + not expired + not revoked
- [ ] `revoke_session()` marks session as revoked with metadata
- [ ] `revoke_all_for_agent()` revokes all sessions for an agent
- [ ] `revoke_all_for_delegation()` cascades delegation revocation
- [ ] `touch_session()` updates last activity timestamp

### Integration Criteria

- [ ] Service uses DelegationService to fetch agent's delegation
- [ ] Session permissions copied from delegation (scoped_permissions)
- [ ] Session links to delegation via foreign key
- [ ] Service exported from `services/__init__.py`
- [ ] All tests pass with `pytest tests/services/test_agent_session_service.py`

### Security Criteria

- [ ] Nonces are single-use (deleted after verification)
- [ ] No plaintext credentials stored
- [ ] Public keys stored, not private keys
- [ ] JWT secret not hardcoded (passed via constructor)

---

## Test Cases

Create `deeptrail-control/tests/services/test_agent_session_service.py`:

```python
"""Tests for AgentSessionService."""

import pytest
import base64
from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from services.agent_session_service import (
    AgentSessionService,
    AgentNotFoundError,
    ChallengeExpiredError,
    InvalidSignatureError,
    NoDelegationError,
)


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
    return session


@pytest.fixture
def mock_delegation_service():
    """Create mock delegation service."""
    service = MagicMock()
    return service


@pytest.fixture
def agent_session_service(mock_db_session, mock_delegation_service, ed25519_keypair):
    """Create AgentSessionService with test fixtures."""
    _, public_b64 = ed25519_keypair
    
    return AgentSessionService(
        db_session=mock_db_session,
        delegation_service=mock_delegation_service,
        jwt_secret="test-secret-key-for-jwt",
        agent_registry={"agent-sdr-001": public_b64}
    )


class TestChallengeGeneration:
    """Test challenge creation."""
    
    def test_create_challenge_success(self, agent_session_service):
        """Test creating a challenge for registered agent."""
        challenge = agent_session_service.create_challenge("agent-sdr-001")
        
        assert challenge is not None
        assert len(base64.urlsafe_b64decode(challenge)) == 32  # 256 bits
    
    def test_create_challenge_agent_not_found(self, agent_session_service):
        """Test challenge creation fails for unknown agent."""
        with pytest.raises(AgentNotFoundError):
            agent_session_service.create_challenge("unknown-agent")
    
    def test_challenge_stored_with_expiration(self, agent_session_service):
        """Test challenge is stored with expiration time."""
        agent_session_service.create_challenge("agent-sdr-001")
        
        assert "agent-sdr-001" in agent_session_service._pending_challenges
        _, expires_at = agent_session_service._pending_challenges["agent-sdr-001"]
        assert expires_at > datetime.utcnow()


class TestSignatureVerification:
    """Test Ed25519 signature verification."""
    
    def test_verify_valid_signature(
        self, agent_session_service, ed25519_keypair, mock_delegation_service
    ):
        """Test successful signature verification."""
        private_key, _ = ed25519_keypair
        
        # Create challenge
        challenge = agent_session_service.create_challenge("agent-sdr-001")
        
        # Sign challenge
        signature_bytes = private_key.sign(challenge.encode('utf-8'))
        signature = base64.urlsafe_b64encode(signature_bytes).decode()
        
        # Mock delegation
        mock_delegation = MagicMock()
        mock_delegation.id = "del-123"
        mock_delegation.sub = "agent-sdr-001"
        mock_delegation.is_valid = True
        mock_delegation.delegated_permissions = ["notion:pages:search"]
        mock_delegation.delegator = "sarah@acme.com"
        mock_delegation.delegator_idp = "https://acme.okta.com"
        mock_delegation.created_at = datetime.utcnow()
        mock_delegation_service.get_delegations_for_agent.return_value = [mock_delegation]
        
        # Verify
        session, token = agent_session_service.verify_and_create_session(
            "agent-sdr-001",
            challenge,
            signature
        )
        
        assert session is not None
        assert token is not None
    
    def test_verify_invalid_signature(self, agent_session_service):
        """Test invalid signature is rejected."""
        challenge = agent_session_service.create_challenge("agent-sdr-001")
        
        # Invalid signature
        invalid_sig = base64.urlsafe_b64encode(b"x" * 64).decode()
        
        with pytest.raises(InvalidSignatureError):
            agent_session_service.verify_and_create_session(
                "agent-sdr-001",
                challenge,
                invalid_sig
            )
    
    def test_challenge_expired(self, agent_session_service, ed25519_keypair):
        """Test expired challenge is rejected."""
        private_key, _ = ed25519_keypair
        
        challenge = agent_session_service.create_challenge("agent-sdr-001")
        
        # Expire the challenge
        agent_session_service._pending_challenges["agent-sdr-001"] = (
            challenge,
            datetime.utcnow() - timedelta(minutes=10)
        )
        
        signature_bytes = private_key.sign(challenge.encode('utf-8'))
        signature = base64.urlsafe_b64encode(signature_bytes).decode()
        
        with pytest.raises(ChallengeExpiredError):
            agent_session_service.verify_and_create_session(
                "agent-sdr-001",
                challenge,
                signature
            )
    
    def test_challenge_single_use(
        self, agent_session_service, ed25519_keypair, mock_delegation_service
    ):
        """Test challenge cannot be reused."""
        private_key, _ = ed25519_keypair
        
        challenge = agent_session_service.create_challenge("agent-sdr-001")
        signature_bytes = private_key.sign(challenge.encode('utf-8'))
        signature = base64.urlsafe_b64encode(signature_bytes).decode()
        
        # Mock delegation
        mock_delegation = MagicMock()
        mock_delegation.id = "del-123"
        mock_delegation.sub = "agent-sdr-001"
        mock_delegation.is_valid = True
        mock_delegation.delegated_permissions = []
        mock_delegation.delegator = "sarah@acme.com"
        mock_delegation.delegator_idp = None
        mock_delegation.created_at = datetime.utcnow()
        mock_delegation_service.get_delegations_for_agent.return_value = [mock_delegation]
        
        # First verification succeeds
        agent_session_service.verify_and_create_session(
            "agent-sdr-001", challenge, signature
        )
        
        # Second attempt fails
        with pytest.raises(ChallengeExpiredError):
            agent_session_service.verify_and_create_session(
                "agent-sdr-001", challenge, signature
            )


class TestJWTGeneration:
    """Test JWT token generation."""
    
    def test_jwt_contains_required_claims(
        self, agent_session_service, ed25519_keypair, mock_delegation_service
    ):
        """Test JWT contains all required claims."""
        import jwt
        
        private_key, _ = ed25519_keypair
        
        challenge = agent_session_service.create_challenge("agent-sdr-001")
        signature_bytes = private_key.sign(challenge.encode('utf-8'))
        signature = base64.urlsafe_b64encode(signature_bytes).decode()
        
        # Mock delegation
        mock_delegation = MagicMock()
        mock_delegation.id = "del-123"
        mock_delegation.sub = "agent-sdr-001"
        mock_delegation.is_valid = True
        mock_delegation.delegated_permissions = ["notion:pages:search"]
        mock_delegation.delegator = "sarah@acme.com"
        mock_delegation.delegator_idp = "https://acme.okta.com"
        mock_delegation.created_at = datetime.utcnow()
        mock_delegation_service.get_delegations_for_agent.return_value = [mock_delegation]
        
        _, token = agent_session_service.verify_and_create_session(
            "agent-sdr-001", challenge, signature
        )
        
        # Decode and verify claims
        claims = jwt.decode(
            token,
            "test-secret-key-for-jwt",
            algorithms=["HS256"],
            audience="deeptrail-gateway"
        )
        
        assert claims["sub"] == "agent-sdr-001"
        assert claims["owner"] == "sarah@acme.com"
        assert claims["iss"] == "deeptrail-control"
        assert claims["aud"] == "deeptrail-gateway"
        assert "session_id" in claims
        assert "exp" in claims


class TestSessionManagement:
    """Test session lifecycle operations."""
    
    def test_revoke_session(self, agent_session_service, mock_db_session):
        """Test session revocation."""
        mock_session = MagicMock()
        mock_db_session.query.return_value.filter.return_value.first.return_value = mock_session
        
        result = agent_session_service.revoke_session(
            "asess-123",
            revoked_by="sarah@acme.com",
            reason="User requested"
        )
        
        assert result is True
        mock_session.revoke.assert_called_once_with(
            revoked_by="sarah@acme.com",
            reason="User requested"
        )
    
    def test_validate_session(self, agent_session_service, mock_db_session):
        """Test session validation."""
        mock_session = MagicMock()
        mock_session.is_valid = True
        mock_db_session.query.return_value.filter.return_value.first.return_value = mock_session
        
        assert agent_session_service.validate_session("asess-123") is True
        
        mock_session.is_valid = False
        assert agent_session_service.validate_session("asess-123") is False


class TestNoDelegation:
    """Test behavior when no valid delegation exists."""
    
    def test_no_delegation_error(
        self, agent_session_service, ed25519_keypair, mock_delegation_service
    ):
        """Test error when agent has no valid delegation."""
        private_key, _ = ed25519_keypair
        
        challenge = agent_session_service.create_challenge("agent-sdr-001")
        signature_bytes = private_key.sign(challenge.encode('utf-8'))
        signature = base64.urlsafe_b64encode(signature_bytes).decode()
        
        # No delegations
        mock_delegation_service.get_delegations_for_agent.return_value = []
        
        with pytest.raises(NoDelegationError):
            agent_session_service.verify_and_create_session(
                "agent-sdr-001", challenge, signature
            )
```

---

## Post-Conditions

After completing this task:

- [ ] AgentSessionService is available for import
- [ ] Agents can authenticate via challenge-response
- [ ] Agent Session JWTs are issued after authentication
- [ ] C1, C2 (agent auth endpoints) have service to call
- [ ] All unit tests pass

---

## References

- **Design Doc Section**: 2.6 Step 5: Agent Authenticates
- **Token Architecture**: Section 4.1 (Three-Layer Token Model)
- **Related Models**: 
  - [WS-A7: AgentSession](./WS-A7-agent-session-model.md)
  - [WS-A5: DelegationToken](./WS-A5-delegation-token-model.md)
- **Related Services**:
  - [WS-A6: DelegationService](./WS-A6-delegation-service.md)
- **Downstream Tasks**:
  - [WS-C1: Agent Challenge Endpoint](./WS-C1-agent-challenge-endpoint.md)
  - [WS-C2: Agent Verify Endpoint](./WS-C2-agent-verify-endpoint.md)

---

## Notes

- MVP uses in-memory challenge storage; production should use Redis with TTL
- MVP uses HS256 JWT signing; production should use RS256 or EdDSA
- Agent registry is in-memory for MVP; production should use database
- The service is the core component enabling agent authentication flow
