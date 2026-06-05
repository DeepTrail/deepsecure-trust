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

import base64
import logging
import secrets
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional, Tuple

import jwt
from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
from sqlalchemy.orm import Session

from app.models.agent_session import AgentSession, PartyType
from app.models.delegation import DelegationToken
from app.services.delegation_service import DelegationService

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────────
# Module-level storage for pending challenges (MVP)
# Production: Use Redis with TTL
# ─────────────────────────────────────────────────────────────────

_pending_challenges: Dict[str, Tuple[str, datetime]] = {}


# ─────────────────────────────────────────────────────────────────
# Exceptions
# ─────────────────────────────────────────────────────────────────


class AgentSessionError(Exception):
    """Base exception for agent session operations."""

    pass


class AgentNotFoundError(AgentSessionError):
    """Raised when agent_id is not found in registry."""

    pass


class ChallengeExpiredError(AgentSessionError):
    """Raised when challenge nonce has expired or doesn't exist."""

    pass


class InvalidSignatureError(AgentSessionError):
    """Raised when Ed25519 signature verification fails."""

    pass


class NoDelegationError(AgentSessionError):
    """Raised when no valid delegation exists for the agent."""

    pass


class SessionExpiredError(AgentSessionError):
    """Raised when attempting to use an expired session."""

    pass


class SessionNotFoundError(AgentSessionError):
    """Raised when session is not found."""

    pass


@dataclass
class MVPSession:
    """Simplified session for MVP (no database).

    Represents an agent session without requiring database tables.
    """
    id: str
    agent_id: str
    party_type: "PartyType"
    expires_at: datetime
    scoped_permissions: List[str]
    owner_email: str
    organization_id: Optional[str] = None
    delegation_id: Optional[str] = None


@dataclass
class AuthenticationResult:
    """Result of successful agent authentication.

    Attributes:
        session: The created AgentSession or MVPSession
        token: The signed JWT token
        expires_in: Seconds until token expires
    """

    session: any  # AgentSession or MVPSession
    token: str
    expires_in: int


class AgentSessionService:
    """Service for managing agent authentication and session lifecycle.

    Handles:
        - Challenge generation for Ed25519 authentication
        - Signature verification
        - Agent Session JWT issuance
        - Session lifecycle (creation, validation, revocation)

    Example from design doc (Section 2.6 - Step 5):
        Agent authentication flow:
        1. POST /api/v1/auth/agent/challenge {"agent_id": "agent-sdr-001"}
        2. Response: {"challenge": "random-nonce-xyz"}
        3. Agent signs challenge with Ed25519 private key
        4. POST /api/v1/auth/agent/verify {"agent_id": "...", "challenge": "...", "signature": "..."}
        5. Response: {"access_token": "eyJhbG...", "token_type": "Bearer", "expires_in": 28800}
    """

    # Constants
    CHALLENGE_BYTES = 32  # 256-bit nonce
    CHALLENGE_TTL_SECONDS = 300  # 5 minutes
    SESSION_TTL_HOURS = 8
    JWT_ALGORITHM = "HS256"  # Fallback; overridden by JWTSigningService when available
    JWT_ISSUER = "deeptrail-control"
    JWT_AUDIENCE = "deeptrail-gateway"

    def __init__(
        self,
        db_session: Session,
        delegation_service: DelegationService,
        jwt_secret: str,
        agent_registry: Optional[Dict[str, str]] = None,
    ):
        """Initialize AgentSessionService.

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

        # Use module-level storage for pending challenges (MVP)
        # This ensures challenges persist across service instances
        # Production: Use Redis with TTL

    # ─────────────────────────────────────────────────────────────────
    # Challenge-Response Authentication
    # ─────────────────────────────────────────────────────────────────

    def create_challenge(self, agent_id: str) -> str:
        """Create a cryptographic challenge for agent authentication.

        Args:
            agent_id: The agent's unique identifier

        Returns:
            A base64url-encoded random nonce (challenge)

        Raises:
            AgentNotFoundError: If agent_id is not in the registry
        """
        # Verify agent exists
        if agent_id not in self.agent_registry:
            logger.warning(f"Challenge requested for unknown agent: {agent_id}")
            raise AgentNotFoundError(f"Agent '{agent_id}' not found in registry")

        # Generate cryptographically secure nonce
        nonce_bytes = secrets.token_bytes(self.CHALLENGE_BYTES)
        nonce = base64.urlsafe_b64encode(nonce_bytes).decode("utf-8")

        # Store with expiration (timezone-aware)
        expires_at = datetime.now(timezone.utc) + timedelta(
            seconds=self.CHALLENGE_TTL_SECONDS
        )
        _pending_challenges[agent_id] = (nonce, expires_at)

        logger.info(f"Challenge created for agent {agent_id}, expires in 5 minutes")
        return nonce

    def verify_and_create_session(
        self,
        agent_id: str,
        challenge: str,
        signature: str,
        delegation_id: Optional[str] = None,
        party_type: PartyType = PartyType.FIRST_PARTY,
    ) -> AuthenticationResult:
        """Verify agent's signature and create an authenticated session.

        Args:
            agent_id: The agent's unique identifier
            challenge: The nonce that was signed
            signature: Base64url-encoded Ed25519 signature of the challenge
            delegation_id: Optional specific delegation to use (else uses latest valid)
            party_type: The agent's party type (default: FIRST_PARTY)

        Returns:
            AuthenticationResult with session, JWT token, and expiry info

        Raises:
            AgentNotFoundError: If agent_id is not in registry
            ChallengeExpiredError: If challenge doesn't exist or expired
            InvalidSignatureError: If signature verification fails
            NoDelegationError: If no valid delegation exists for agent
        """
        # 1. Verify agent exists
        if agent_id not in self.agent_registry:
            logger.warning(f"Verification attempted for unknown agent: {agent_id}")
            raise AgentNotFoundError(f"Agent '{agent_id}' not found in registry")

        # 2. Verify challenge is valid
        if agent_id not in _pending_challenges:
            logger.warning(f"No pending challenge for agent: {agent_id}")
            raise ChallengeExpiredError("No pending challenge for this agent")

        stored_challenge, expires_at = _pending_challenges[agent_id]

        if datetime.now(timezone.utc) > expires_at:
            del _pending_challenges[agent_id]
            logger.warning(f"Challenge expired for agent: {agent_id}")
            raise ChallengeExpiredError("Challenge has expired")

        if stored_challenge != challenge:
            logger.warning(f"Challenge mismatch for agent: {agent_id}")
            raise ChallengeExpiredError("Challenge mismatch")

        # 3. Verify Ed25519 signature
        if not self._verify_signature(agent_id, challenge, signature):
            logger.warning(f"Signature verification failed for agent: {agent_id}")
            raise InvalidSignatureError("Signature verification failed")

        # 4. Clear the used challenge (single-use)
        del _pending_challenges[agent_id]

        # 5. Find delegation and create database-backed session
        delegation = (
            self.db.query(DelegationToken)
            .filter(
                DelegationToken.agent_id == agent_id,
                DelegationToken.revoked_at.is_(None),
            )
            .order_by(DelegationToken.created_at.desc())
            .first()
        )

        session_expires_at = datetime.now(timezone.utc) + timedelta(hours=self.SESSION_TTL_HOURS)

        if delegation and delegation.is_valid:
            session = AgentSession(
                agent_id=agent_id,
                delegation_id=delegation.id,
                party_type=party_type,
                scoped_permissions=delegation.delegated_permissions or [],
                owner_email=delegation.delegator or "unknown",
                idp_issuer=delegation.delegator_idp,
                groups=[],
                is_active=True,
                expires_at=session_expires_at,
            )
        else:
            # No delegation — still create a session but use the MVP in-memory approach
            # since delegation_id is NOT NULL in the DB schema
            mvp_session = self._create_mvp_session(agent_id, party_type, delegation_id)
            token = self._generate_mvp_jwt(agent_id, mvp_session)
            expires_in = int(self.SESSION_TTL_HOURS * 3600)

            logger.info(
                f"Agent {agent_id} authenticated (no delegation), "
                f"session {mvp_session.id} created (in-memory)"
            )

            return AuthenticationResult(
                token=token,
                session=mvp_session,
                expires_in=expires_in,
            )

        self.db.add(session)
        self.db.commit()
        self.db.refresh(session)

        # 6. Generate JWT
        token = self._generate_jwt(session)

        # 7. Calculate expires_in
        expires_in = int(self.SESSION_TTL_HOURS * 3600)

        logger.info(
            f"Agent {agent_id} authenticated successfully, "
            f"session {session.id} created"
        )

        return AuthenticationResult(
            session=session,
            token=token,
            expires_in=expires_in,
        )

    def _verify_signature(
        self, agent_id: str, challenge: str, signature: str
    ) -> bool:
        """Verify Ed25519 signature against agent's registered public key.

        Args:
            agent_id: Agent's identifier
            challenge: The message that was signed
            signature: Base64url-encoded signature (padding optional)

        Returns:
            True if signature is valid, False otherwise
        """
        try:
            # Get agent's public key
            public_key_b64 = self.agent_registry.get(agent_id)
            if not public_key_b64:
                return False

            # Decode public key (re-pad if needed)
            public_key_padded = public_key_b64 + "=" * (-len(public_key_b64) % 4)
            public_key_bytes = base64.urlsafe_b64decode(public_key_padded)
            public_key = Ed25519PublicKey.from_public_bytes(public_key_bytes)

            # Decode signature (re-pad if needed — browsers strip '=' from base64url)
            sig_padded = signature + "=" * (-len(signature) % 4)
            signature_bytes = base64.urlsafe_b64decode(sig_padded)

            # Verify - Ed25519 signs the raw bytes
            challenge_bytes = challenge.encode("utf-8")
            public_key.verify(signature_bytes, challenge_bytes)

            return True

        except InvalidSignature:
            return False
        except Exception as e:
            logger.error(f"Signature verification error: {e}")
            return False

    # ─────────────────────────────────────────────────────────────────
    # MVP Simplified Methods (no database tables required)
    # ─────────────────────────────────────────────────────────────────

    def _create_mvp_session(
        self,
        agent_id: str,
        party_type: PartyType = PartyType.FIRST_PARTY,
        delegation_id: Optional[str] = None,
    ) -> "MVPSession":
        """Create an in-memory session for MVP.

        Looks up the most recent valid DelegationToken from the database.
        """
        session_id = f"asess-{uuid.uuid4().hex[:12]}"
        expires_at = datetime.now(timezone.utc) + timedelta(
            hours=self.SESSION_TTL_HOURS
        )

        delegation = (
            self.db.query(DelegationToken)
            .filter(
                DelegationToken.agent_id == agent_id,
                DelegationToken.revoked_at.is_(None),
            )
            .order_by(DelegationToken.created_at.desc())
            .first()
        )

        resolved_delegation_id = delegation_id
        if delegation and delegation.is_valid:
            scoped_permissions = delegation.delegated_permissions or []
            owner_email = delegation.delegator or "unknown"
            organization_id = delegation.organization_id
            if not resolved_delegation_id:
                resolved_delegation_id = delegation.id
            logger.info(
                "Found delegation for agent %s with %d permissions, "
                "delegation_id=%s, org=%s",
                agent_id,
                len(scoped_permissions),
                resolved_delegation_id,
                organization_id,
            )
        else:
            scoped_permissions = []
            owner_email = "no-delegation"
            organization_id = None
            logger.warning(
                "No valid delegation found for agent %s, using empty permissions",
                agent_id,
            )

        return MVPSession(
            id=session_id,
            agent_id=agent_id,
            party_type=party_type,
            expires_at=expires_at,
            scoped_permissions=scoped_permissions,
            owner_email=owner_email,
            organization_id=organization_id,
            delegation_id=resolved_delegation_id,
        )

    def _generate_mvp_jwt(self, agent_id: str, session: "MVPSession") -> str:
        """Generate a JWT for an MVP session.

        Delegates to JWTSigningService (RS256) when available, falling
        back to HS256 symmetric signing for backward compatibility.
        """
        now = datetime.now(timezone.utc)
        payload = {
            "iss": self.JWT_ISSUER,
            "aud": self.JWT_AUDIENCE,
            "sub": agent_id,
            "iat": int(now.timestamp()),
            "exp": int(session.expires_at.timestamp()),
            "session_id": session.id,
            "owner": session.owner_email,
            "delegated_permissions": session.scoped_permissions,
            "delegation_id": session.delegation_id,
            "organization_id": session.organization_id,
        }

        try:
            from app.core.jwt_signing import get_jwt_signing_service
            svc = get_jwt_signing_service()
            return svc.sign(payload)
        except Exception:
            return jwt.encode(payload, self.jwt_secret, algorithm=self.JWT_ALGORITHM)

    def _get_valid_delegation(
        self,
        agent_id: str,
        delegation_id: Optional[str] = None,
    ) -> Optional[DelegationToken]:
        """Get a valid delegation for the agent.

        Args:
            agent_id: Agent's identifier (matches delegation.agent_id)
            delegation_id: Specific delegation ID, or None for latest valid

        Returns:
            Valid DelegationToken or None
        """
        if delegation_id:
            delegation = self.delegation_service.get_delegation(delegation_id)
            if delegation and delegation.agent_id == agent_id and delegation.is_valid:
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
        delegation: DelegationToken,
        party_type: PartyType = PartyType.FIRST_PARTY,
        source_ip: Optional[str] = None,
    ) -> AgentSession:
        """Create a new AgentSession from a delegation.

        Args:
            agent_id: Agent's identifier
            delegation: The delegation providing permissions
            party_type: The agent's party type
            source_ip: IP address of the authenticating client

        Returns:
            Newly created AgentSession
        """
        session = AgentSession(
            agent_id=agent_id,
            delegation_id=delegation.id,
            party_type=party_type,
            scoped_permissions=delegation.delegated_permissions or [],
            owner_email=delegation.delegator,
            idp_issuer=delegation.delegator_idp,
            groups=[],
            is_active=True,
            expires_at=datetime.now(timezone.utc)
            + timedelta(hours=self.SESSION_TTL_HOURS),
            source_ip=source_ip,
        )

        self.db.add(session)
        self.db.commit()
        self.db.refresh(session)

        return session

    def _generate_jwt(self, session: AgentSession) -> str:
        """Generate JWT token for an agent session.

        Delegates to JWTSigningService when available.
        """
        claims = session.to_jwt_claims()
        claims["iss"] = self.JWT_ISSUER
        claims["aud"] = self.JWT_AUDIENCE

        try:
            from app.core.jwt_signing import get_jwt_signing_service
            return get_jwt_signing_service().sign(claims)
        except Exception:
            return jwt.encode(claims, self.jwt_secret, algorithm=self.JWT_ALGORITHM)

    # ─────────────────────────────────────────────────────────────────
    # Session Management
    # ─────────────────────────────────────────────────────────────────

    def get_session(self, session_id: str) -> Optional[AgentSession]:
        """Get an agent session by ID.

        Args:
            session_id: The session identifier

        Returns:
            AgentSession or None if not found
        """
        return (
            self.db.query(AgentSession).filter(AgentSession.id == session_id).first()
        )

    def get_session_by_token(self, token: str) -> AgentSession:
        """Decode JWT and retrieve the associated session.

        Args:
            token: JWT token string

        Returns:
            AgentSession

        Raises:
            SessionExpiredError: If session has expired or JWT is invalid
            SessionNotFoundError: If session not found
        """
        try:
            claims = jwt.decode(
                token,
                self.jwt_secret,
                algorithms=[self.JWT_ALGORITHM],
                audience=self.JWT_AUDIENCE,
            )

            session_id = claims.get("session_id")
            if not session_id:
                raise SessionNotFoundError("No session_id in token")

            session = self.get_session(session_id)

            if not session:
                raise SessionNotFoundError(f"Session {session_id} not found")

            if not session.is_valid:
                raise SessionExpiredError("Session has expired or been revoked")

            return session

        except jwt.ExpiredSignatureError:
            raise SessionExpiredError("JWT has expired")
        except jwt.InvalidTokenError as e:
            raise SessionExpiredError(f"Invalid JWT: {e}")

    def validate_session(self, session_id: str) -> bool:
        """Check if a session is valid (active, not expired, not revoked).

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
        reason: Optional[str] = None,
    ) -> bool:
        """Revoke an agent session.

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

        logger.info(f"Session {session_id} revoked by {revoked_by}: {reason}")
        return True

    def revoke_all_for_agent(
        self,
        agent_id: str,
        revoked_by: str = "system",
        reason: Optional[str] = None,
    ) -> int:
        """Revoke all active sessions for an agent.

        Args:
            agent_id: The agent whose sessions to revoke
            revoked_by: Who initiated the revocation
            reason: Optional reason

        Returns:
            Number of sessions revoked
        """
        sessions = (
            self.db.query(AgentSession)
            .filter(
                AgentSession.agent_id == agent_id,
                AgentSession.is_active.is_(True),
            )
            .all()
        )

        count = 0
        for session in sessions:
            if session.is_valid:
                session.revoke(revoked_by=revoked_by, reason=reason)
                count += 1

        self.db.commit()

        if count > 0:
            logger.info(f"Revoked {count} sessions for agent {agent_id}")

        return count

    def revoke_all_for_delegation(
        self,
        delegation_id: str,
        revoked_by: str = "system",
        reason: str = "Delegation revoked",
    ) -> int:
        """Revoke all sessions using a specific delegation.

        Called when a delegation is revoked to cascade to sessions.

        Args:
            delegation_id: The delegation whose sessions to revoke
            revoked_by: Who initiated
            reason: Reason for revocation

        Returns:
            Number of sessions revoked
        """
        sessions = (
            self.db.query(AgentSession)
            .filter(
                AgentSession.delegation_id == delegation_id,
                AgentSession.is_active.is_(True),
            )
            .all()
        )

        count = 0
        for session in sessions:
            session.revoke(revoked_by=revoked_by, reason=reason)
            count += 1

        self.db.commit()

        if count > 0:
            logger.info(
                f"Revoked {count} sessions for delegation {delegation_id}"
            )

        return count

    def get_active_sessions_for_agent(self, agent_id: str) -> List[AgentSession]:
        """Get all active sessions for an agent.

        Args:
            agent_id: The agent's identifier

        Returns:
            List of active AgentSession objects
        """
        sessions = (
            self.db.query(AgentSession)
            .filter(
                AgentSession.agent_id == agent_id,
                AgentSession.is_active.is_(True),
            )
            .all()
        )

        return [s for s in sessions if s.is_valid]

    def get_sessions_for_delegation(
        self, delegation_id: str, include_expired: bool = False
    ) -> List[AgentSession]:
        """Get all sessions for a delegation.

        Args:
            delegation_id: The delegation identifier
            include_expired: Whether to include expired sessions

        Returns:
            List of AgentSession objects
        """
        query = self.db.query(AgentSession).filter(
            AgentSession.delegation_id == delegation_id
        )

        if not include_expired:
            query = query.filter(AgentSession.is_active.is_(True))

        sessions = query.all()

        if not include_expired:
            return [s for s in sessions if s.is_valid]

        return sessions

    def touch_session(self, session_id: str) -> bool:
        """Update last activity timestamp for a session.

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

    def check_session_permission(self, session_id: str, permission: str) -> bool:
        """Check if a session has a specific permission.

        Args:
            session_id: The session identifier
            permission: Permission string to check (e.g., "notion:pages:search")

        Returns:
            True if session has the permission
        """
        session = self.get_session(session_id)
        if not session or not session.is_valid:
            return False

        return session.has_permission(permission)

    # ─────────────────────────────────────────────────────────────────
    # Agent Registry Management (MVP)
    # ─────────────────────────────────────────────────────────────────

    def register_agent(self, agent_id: str, public_key_b64: str) -> None:
        """Register an agent's Ed25519 public key.

        Args:
            agent_id: Unique agent identifier
            public_key_b64: Base64url-encoded Ed25519 public key (32 bytes)

        Raises:
            ValueError: If public key is invalid
        """
        # Validate key format
        try:
            key_bytes = base64.urlsafe_b64decode(public_key_b64)
            if len(key_bytes) != 32:
                raise ValueError(
                    f"Ed25519 public key must be 32 bytes, got {len(key_bytes)}"
                )
            Ed25519PublicKey.from_public_bytes(key_bytes)
        except Exception as e:
            raise ValueError(f"Invalid Ed25519 public key: {e}")

        self.agent_registry[agent_id] = public_key_b64
        logger.info(f"Agent {agent_id} registered")

    def unregister_agent(self, agent_id: str) -> bool:
        """Remove an agent from the registry.

        Args:
            agent_id: The agent to remove

        Returns:
            True if removed, False if not found
        """
        if agent_id in self.agent_registry:
            del self.agent_registry[agent_id]
            logger.info(f"Agent {agent_id} unregistered")
            return True
        return False

    def is_agent_registered(self, agent_id: str) -> bool:
        """Check if an agent is registered.

        Args:
            agent_id: The agent identifier

        Returns:
            True if agent is in registry
        """
        return agent_id in self.agent_registry

    def get_pending_challenge(self, agent_id: str) -> Optional[str]:
        """Get pending challenge for an agent (for testing/debugging).

        Args:
            agent_id: The agent identifier

        Returns:
            The pending challenge nonce, or None if none exists
        """
        if agent_id in _pending_challenges:
            challenge, expires_at = _pending_challenges[agent_id]
            if datetime.now(timezone.utc) <= expires_at:
                return challenge
        return None

    def clear_expired_challenges(self) -> int:
        """Clear all expired challenges from memory.

        Returns:
            Number of challenges cleared
        """
        now = datetime.now(timezone.utc)
        expired = [
            agent_id
            for agent_id, (_, expires_at) in _pending_challenges.items()
            if now > expires_at
        ]

        for agent_id in expired:
            del _pending_challenges[agent_id]

        if expired:
            logger.debug(f"Cleared {len(expired)} expired challenges")

        return len(expired)
