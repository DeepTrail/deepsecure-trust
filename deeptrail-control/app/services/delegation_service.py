"""Service for managing delegation tokens.

This service handles the lifecycle of user → agent permission delegations,
implementing the Layer 2 token management for the three-layer architecture.

Key principles:
- Monotonic Attenuation: Agent permissions ⊂ User's permissions
- Bounded Delegation: All delegations have explicit expiration
- Immediate Revocability: User can revoke at any time
- One Active Delegation: Per user-agent pair for simplicity

Example flow from design:
    Sarah → "My Agents" → "SDR-Assistant" → "Permissions"
    Grants: notion:pages:search, notion:pages:read
    Constraints: expires in 7 days, max 100 actions/day
"""

import hashlib
import logging
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from app.models.connected_service import ConnectedService
from app.models.delegation import DelegationToken

logger = logging.getLogger(__name__)


@dataclass
class ValidationResult:
    """Result of delegation validation.

    Attributes:
        is_valid: Whether the delegation is currently valid
        reason: Reason for invalidity (if not valid)
        delegation: The delegation token (even if invalid, for inspection)
    """

    is_valid: bool
    reason: Optional[str] = None
    delegation: Optional[DelegationToken] = None


class DelegationError(Exception):
    """Base exception for delegation operations."""

    pass


class PermissionValidationError(DelegationError):
    """Raised when requested permissions fail validation."""

    pass


class DelegationNotFoundError(DelegationError):
    """Raised when a delegation is not found."""

    pass


class DelegationService:
    """Service for managing delegation tokens.

    Handles the lifecycle of user → agent permission delegations:
    - Create: Validate permissions and create delegation
    - Validate: Check expiry, revocation, and permissions
    - Revoke: Mark delegation as revoked (immediate, permanent)
    - Query: Find delegations by user or agent

    Example:
        service = DelegationService(db_session)

        # Create delegation
        delegation = service.create_delegation(
            delegator="sarah@acme.com",
            agent_id="agent-sdr-001",
            permissions=["notion:pages:search", "notion:pages:read"],
            constraints={"max_actions_per_day": 100}
        )

        # Validate
        result = service.validate_delegation(delegation.id)
        if result.is_valid:
            print("Delegation is valid")

        # Check permission
        if service.has_permission(delegation.id, "notion:pages:search"):
            print("Can search pages")
    """

    # Default delegation expiry (7 days as per design doc)
    DEFAULT_EXPIRY_DAYS = 7

    # Base URL for revocation URIs
    REVOCATION_BASE_URL = "https://deeptrail.io"

    def __init__(self, db_session: Session):
        """Initialize the service.

        Args:
            db_session: SQLAlchemy database session.
        """
        self._db = db_session

    def _generate_token_hash(self, token_data: str) -> str:
        """Generate SHA-256 hash for token binding.

        Args:
            token_data: Data to hash (typically identity + nonce)

        Returns:
            Hash string in format "sha256:{first 32 chars of hex digest}"
        """
        full_hash = hashlib.sha256(token_data.encode()).hexdigest()
        return f"sha256:{full_hash[:32]}"

    def _generate_revocation_uri(self, delegation_id: str) -> str:
        """Generate revocation URI for delegation.

        Args:
            delegation_id: Delegation ID

        Returns:
            Revocation URI string
        """
        return f"{self.REVOCATION_BASE_URL}/revoke/{delegation_id}"

    def _validate_permissions_subset(
        self,
        delegator: str,
        requested_permissions: List[str],
    ) -> tuple[bool, Optional[str]]:
        """Validate that requested permissions are subset of user's scopes.

        Enforces the Monotonic Attenuation principle: agent permissions must
        be a subset of the delegator's connected service scopes.

        Args:
            delegator: User ID (e.g., "sarah@acme.com")
            requested_permissions: List of permissions to delegate

        Returns:
            Tuple of (is_valid, reason_if_invalid)
        """
        # Get all user's active connected services
        connections = (
            self._db.query(ConnectedService)
            .filter(
                ConnectedService.user_id == delegator,
                ConnectedService.disconnected_at.is_(None),
            )
            .all()
        )

        if not connections:
            return False, "User has no connected services"

        # Build map of connected services and their scopes
        connected_services = {}
        for conn in connections:
            connected_services[conn.service_id] = set(conn.scopes_granted or [])

        # Validate each requested permission
        for perm in requested_permissions:
            parts = perm.split(":")
            if len(parts) < 2:
                return False, f"Invalid permission format: {perm}"

            service = parts[0]

            # Check if user has this service connected
            if service not in connected_services:
                return False, f"User not connected to service: {service}"

            # For MVP: Allow any permission if service is connected
            # In production, would check against specific scopes
            # e.g., "notion:pages:search" requires "pages:search" scope

        return True, None

    def create_delegation(
        self,
        delegator: str,
        agent_id: str,
        permissions: List[str],
        constraints: Optional[Dict[str, Any]] = None,
        expires_in_days: int = DEFAULT_EXPIRY_DAYS,
        delegator_idp: Optional[str] = None,
        organization_id: Optional[str] = None,
    ) -> DelegationToken:
        """Create a new delegation from user to agent.

        Creates a Layer 2 delegation token granting the agent specific
        permissions from the user's connected services.

        If an active delegation already exists for this user-agent pair,
        it is revoked before creating the new one.

        Args:
            delegator: User ID granting delegation (e.g., "sarah@acme.com")
            agent_id: Agent ID receiving delegation (e.g., "agent-sdr-001")
            permissions: List of permissions to delegate (e.g., ["notion:pages:search"])
            constraints: Optional constraints (e.g., {"max_actions_per_day": 100})
            expires_in_days: Delegation validity period (default 7 days)
            delegator_idp: Optional IdP issuer for delegator
            organization_id: Optional organization for multi-tenant

        Returns:
            Created DelegationToken

        Raises:
            PermissionValidationError: If permissions validation fails
        """
        # Validate permissions are subset of user's connected scopes
        is_valid, reason = self._validate_permissions_subset(delegator, permissions)
        if not is_valid:
            logger.warning(
                "Permission validation failed: delegator=%s reason=%s",
                delegator,
                reason,
            )
            raise PermissionValidationError(f"Permission validation failed: {reason}")

        # Check for existing active delegation and revoke it
        existing = self.get_active_delegation(delegator, agent_id)
        if existing:
            logger.info(
                "Revoking existing delegation before creating new: id=%s",
                existing.id,
            )
            self.revoke_delegation(str(existing.id))

        # Generate token binding hashes
        user_token_hash = self._generate_token_hash(f"{delegator}-{uuid.uuid4()}")
        agent_token_hash = self._generate_token_hash(f"{agent_id}-{uuid.uuid4()}")

        # Calculate expiration
        expires_at = datetime.now(timezone.utc) + timedelta(days=expires_in_days)

        # Generate delegation ID for revocation URI
        delegation_id = f"del-{uuid.uuid4()}"

        # Create delegation
        delegation = DelegationToken(
            id=delegation_id,
            agent_id=agent_id,
            delegator=delegator,
            delegator_idp=delegator_idp,
            user_token_hash=user_token_hash,
            agent_token_hash=agent_token_hash,
            delegated_permissions=permissions,
            constraints=constraints or {},
            expires_at=expires_at,
            organization_id=organization_id,
            revocation_uri=self._generate_revocation_uri(delegation_id),
        )

        self._db.add(delegation)

        logger.info(
            "Created delegation: id=%s delegator=%s agent=%s permissions=%d expires=%s",
            delegation.id,
            delegator,
            agent_id,
            len(permissions),
            expires_at.isoformat(),
        )

        return delegation

    def validate_delegation(self, delegation_id: str) -> ValidationResult:
        """Validate a delegation token.

        Checks:
        - Delegation exists
        - Not expired
        - Not revoked

        Args:
            delegation_id: Delegation UUID

        Returns:
            ValidationResult with is_valid flag and reason if invalid
        """
        delegation = self.get_delegation(delegation_id)

        if not delegation:
            return ValidationResult(
                is_valid=False,
                reason="Delegation not found",
            )

        if delegation.is_expired:
            return ValidationResult(
                is_valid=False,
                reason="Delegation expired",
                delegation=delegation,
            )

        if delegation.is_revoked:
            return ValidationResult(
                is_valid=False,
                reason="Delegation revoked",
                delegation=delegation,
            )

        return ValidationResult(
            is_valid=True,
            delegation=delegation,
        )

    def revoke_delegation(self, delegation_id: str) -> bool:
        """Revoke a delegation.

        Revocation is immediate and permanent. There is no "unrevoke".

        Args:
            delegation_id: Delegation UUID

        Returns:
            True if revoked, False if not found
        """
        delegation = self.get_delegation(delegation_id)
        if not delegation:
            logger.debug("Delegation not found for revoke: id=%s", delegation_id)
            return False

        # Already revoked?
        if delegation.is_revoked:
            logger.debug("Delegation already revoked: id=%s", delegation_id)
            return True

        delegation.revoke()

        logger.info(
            "Revoked delegation: id=%s delegator=%s agent=%s",
            delegation_id,
            delegation.delegator,
            delegation.agent_id,
        )

        return True

    def get_delegation(self, delegation_id: str) -> Optional[DelegationToken]:
        """Get delegation by ID.

        Args:
            delegation_id: Delegation UUID

        Returns:
            DelegationToken or None if not found
        """
        return (
            self._db.query(DelegationToken)
            .filter(DelegationToken.id == delegation_id)
            .first()
        )

    def get_delegations_for_user(
        self,
        user_id: str,
        include_revoked: bool = False,
        include_expired: bool = False,
    ) -> List[DelegationToken]:
        """Get all delegations created by a user.

        Args:
            user_id: User identifier
            include_revoked: If True, include revoked delegations
            include_expired: If True, include expired delegations

        Returns:
            List of DelegationToken records
        """
        query = self._db.query(DelegationToken).filter(
            DelegationToken.delegator == user_id,
        )

        if not include_revoked:
            query = query.filter(DelegationToken.revoked_at.is_(None))

        if not include_expired:
            now = datetime.now(timezone.utc)
            query = query.filter(DelegationToken.expires_at > now)

        return query.all()

    def get_delegations_for_agent(
        self,
        agent_id: str,
        include_revoked: bool = False,
        include_expired: bool = False,
    ) -> List[DelegationToken]:
        """Get all delegations granted to an agent.

        Args:
            agent_id: Agent identifier
            include_revoked: If True, include revoked delegations
            include_expired: If True, include expired delegations

        Returns:
            List of DelegationToken records
        """
        query = self._db.query(DelegationToken).filter(
            DelegationToken.agent_id == agent_id,
        )

        if not include_revoked:
            query = query.filter(DelegationToken.revoked_at.is_(None))

        if not include_expired:
            now = datetime.now(timezone.utc)
            query = query.filter(DelegationToken.expires_at > now)

        return query.all()

    def get_active_delegation(
        self,
        delegator: str,
        agent_id: str,
    ) -> Optional[DelegationToken]:
        """Get active (not expired, not revoked) delegation between user and agent.

        Args:
            delegator: User identifier
            agent_id: Agent identifier

        Returns:
            DelegationToken or None if no active delegation
        """
        now = datetime.now(timezone.utc)
        return (
            self._db.query(DelegationToken)
            .filter(
                DelegationToken.delegator == delegator,
                DelegationToken.agent_id == agent_id,
                DelegationToken.expires_at > now,
                DelegationToken.revoked_at.is_(None),
            )
            .first()
        )

    def has_permission(self, delegation_id: str, permission: str) -> bool:
        """Check if delegation grants a specific permission.

        Validates the delegation is still valid (not expired, not revoked)
        before checking the permission.

        Args:
            delegation_id: Delegation UUID
            permission: Permission string (e.g., "notion:pages:search")

        Returns:
            True if permission is delegated and delegation is valid
        """
        result = self.validate_delegation(delegation_id)
        if not result.is_valid:
            return False

        return result.delegation.has_permission(permission)

    def get_permissions_for_agent(
        self,
        delegator: str,
        agent_id: str,
        service: Optional[str] = None,
    ) -> List[str]:
        """Get all permissions an agent has from a specific user.

        Useful for the gateway to determine what tools the agent can see/use.

        Args:
            delegator: User identifier
            agent_id: Agent identifier
            service: Optional service filter (e.g., "notion")

        Returns:
            List of permission strings
        """
        delegation = self.get_active_delegation(delegator, agent_id)
        if not delegation:
            return []

        if service:
            return delegation.get_permissions_for_service(service)

        return list(delegation.delegated_permissions or [])

    def revoke_all_for_user(self, user_id: str) -> int:
        """Revoke all delegations created by a user.

        Useful when a user account is deactivated or compromised.

        Args:
            user_id: User identifier

        Returns:
            Number of delegations revoked
        """
        delegations = self.get_delegations_for_user(user_id)
        count = 0

        for delegation in delegations:
            if self.revoke_delegation(str(delegation.id)):
                count += 1

        logger.info("Revoked all delegations for user: user=%s count=%d", user_id, count)
        return count

    def revoke_all_for_agent(self, agent_id: str) -> int:
        """Revoke all delegations granted to an agent.

        Useful when an agent is decommissioned or compromised.

        Args:
            agent_id: Agent identifier

        Returns:
            Number of delegations revoked
        """
        delegations = self.get_delegations_for_agent(agent_id)
        count = 0

        for delegation in delegations:
            if self.revoke_delegation(str(delegation.id)):
                count += 1

        logger.info(
            "Revoked all delegations for agent: agent=%s count=%d", agent_id, count
        )
        return count

    def get_constraint(
        self,
        delegation_id: str,
        key: str,
        default: Any = None,
    ) -> Any:
        """Get a constraint value from a delegation.

        Args:
            delegation_id: Delegation UUID
            key: Constraint key (e.g., "max_actions_per_day")
            default: Default value if constraint not set

        Returns:
            Constraint value or default
        """
        delegation = self.get_delegation(delegation_id)
        if not delegation:
            return default

        return delegation.get_constraint(key, default)
