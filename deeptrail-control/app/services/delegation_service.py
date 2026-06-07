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

from app.models.agent_session import AgentSession
from app.models.audit_event import AuditEventType
from app.models.connected_service import ConnectedService
from app.models.delegation import DelegationToken
from app.models.delegation_template import DelegationTemplate
from app.services.audit_logger_service import AuditLoggerService
from app.services.scope_mapper import ScopeMapper

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
    """Raised when requested permissions fail validation.

    Attributes:
        message: Human-readable error message
        invalid_permissions: List of permissions that were not allowed
        allowed_permissions: List of permissions that are allowed
    """

    def __init__(
        self,
        message: str,
        invalid_permissions: Optional[List[str]] = None,
        allowed_permissions: Optional[List[str]] = None,
    ):
        super().__init__(message)
        self.message = message
        self.invalid_permissions = invalid_permissions or []
        self.allowed_permissions = allowed_permissions or []


class DelegationNotFoundError(DelegationError):
    """Raised when a delegation is not found."""

    pass


class DelegationForbiddenError(DelegationError):
    """Raised when the actor cannot modify the delegation."""

    pass


class DelegationInvalidStateError(DelegationError):
    """Raised when a delegation is revoked or expired."""

    pass


class DelegationNotPendingError(DelegationError):
    """Raised when accept is attempted on a non-pending delegation."""

    pass


class PermissionWideningError(DelegationError):
    """Raised when PATCH attempts to widen permissions beyond current set."""

    def __init__(
        self,
        message: str,
        attempted: List[str],
        current: List[str],
        allowed_ceiling: List[str],
    ):
        super().__init__(message)
        self.message = message
        self.attempted = attempted
        self.current = current
        self.allowed_ceiling = allowed_ceiling


@dataclass
class PatchDelegationResult:
    """Result of a successful delegation permission patch."""

    delegation: DelegationToken
    sessions_revoked: int
    previous_permissions: List[str]


@dataclass
class AcceptDelegationResult:
    """Result of accepting a pending delegation invite."""

    delegation: DelegationToken


@dataclass
class InviteUsersResult:
    """Result of inviting users to a delegation template."""

    invited: int
    delegation_ids: List[str]
    skipped: List[str]


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
    ) -> tuple[bool, Optional[str], List[str], List[str]]:
        """Validate that requested permissions are subset of user's scopes.

        Enforces the Monotonic Attenuation principle: agent permissions must
        be a subset of the delegator's connected service scopes.

        Uses ScopeMapper to validate that requested permissions are allowed
        by the OAuth scopes the user granted when connecting services.

        Args:
            delegator: User ID (e.g., "sarah@acme.com")
            requested_permissions: List of permissions to delegate

        Returns:
            Tuple of (is_valid, reason_if_invalid, invalid_permissions, allowed_permissions)
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
            return False, "User has no connected services", [], []

        # Build list of (service_id, scopes) for ScopeMapper
        connected_services = [
            (conn.service_id, conn.scopes_granted or [])
            for conn in connections
        ]

        # Validate each requested permission using ScopeMapper
        is_valid, invalid_perms = ScopeMapper.validate_permissions(
            requested_permissions,
            connected_services,
        )

        if not is_valid:
            # Get allowed permissions for error message
            allowed = ScopeMapper.get_all_allowed_permissions(connected_services)
            return (
                False,
                f"Permissions not allowed by connected scopes: {invalid_perms}",
                invalid_perms,
                sorted(list(allowed)),
            )

        return True, None, [], []

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
        is_valid, reason, invalid_perms, allowed_perms = self._validate_permissions_subset(
            delegator, permissions
        )
        if not is_valid:
            logger.warning(
                "Permission validation failed: delegator=%s reason=%s invalid=%s",
                delegator,
                reason,
                invalid_perms,
            )
            raise PermissionValidationError(
                message=reason or "Permission validation failed",
                invalid_permissions=invalid_perms,
                allowed_permissions=allowed_perms,
            )

        # Enforce delegation template ceiling if one exists for this agent
        template = (
            self._db.query(DelegationTemplate)
            .filter(DelegationTemplate.agent_id == agent_id)
            .first()
        )
        if template:
            max_perms = set(template.max_permissions or [])
            blocked = set(template.blocked_permissions or [])

            blocked_requested = set(permissions) & blocked
            if blocked_requested:
                raise PermissionValidationError(
                    message=(
                        f"Permissions blocked by admin template: "
                        f"{sorted(blocked_requested)}"
                    ),
                    invalid_permissions=sorted(blocked_requested),
                    allowed_permissions=sorted(max_perms - blocked),
                )

            if max_perms:
                over_ceiling = set(permissions) - max_perms
                if over_ceiling:
                    raise PermissionValidationError(
                        message=(
                            f"Permissions exceed admin template ceiling: "
                            f"{sorted(over_ceiling)}"
                        ),
                        invalid_permissions=sorted(over_ceiling),
                        allowed_permissions=sorted(max_perms - blocked),
                    )

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
                DelegationToken.status == "active",
            )
            .first()
        )

    def _get_blocking_delegation(
        self,
        delegator: str,
        agent_id: str,
    ) -> Optional[DelegationToken]:
        """Return active or pending non-revoked delegation for user+agent."""
        now = datetime.now(timezone.utc)
        return (
            self._db.query(DelegationToken)
            .filter(
                DelegationToken.delegator == delegator,
                DelegationToken.agent_id == agent_id,
                DelegationToken.expires_at > now,
                DelegationToken.revoked_at.is_(None),
                DelegationToken.status.in_(("active", "pending")),
            )
            .first()
        )

    @staticmethod
    def template_effective_permissions(template: DelegationTemplate) -> List[str]:
        """Permissions granted from a template (max minus blocked)."""
        max_perms = set(template.max_permissions or [])
        blocked = set(template.blocked_permissions or [])
        return sorted(max_perms - blocked)

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

    def _validate_template_ceiling(
        self,
        agent_id: str,
        permissions: List[str],
    ) -> None:
        """Ensure permissions respect the admin template ceiling for an agent."""
        template = (
            self._db.query(DelegationTemplate)
            .filter(DelegationTemplate.agent_id == agent_id)
            .first()
        )
        if not template:
            return

        max_perms = set(template.max_permissions or [])
        blocked = set(template.blocked_permissions or [])

        blocked_requested = set(permissions) & blocked
        if blocked_requested:
            raise PermissionValidationError(
                message=(
                    f"Permissions blocked by admin template: "
                    f"{sorted(blocked_requested)}"
                ),
                invalid_permissions=sorted(blocked_requested),
                allowed_permissions=sorted(max_perms - blocked),
            )

        if max_perms:
            over_ceiling = set(permissions) - max_perms
            if over_ceiling:
                raise PermissionValidationError(
                    message=(
                        f"Permissions exceed admin template ceiling: "
                        f"{sorted(over_ceiling)}"
                    ),
                    invalid_permissions=sorted(over_ceiling),
                    allowed_permissions=sorted(max_perms - blocked),
                )

    def patch_delegation_permissions(
        self,
        delegation_id: str,
        actor: str,
        *,
        is_admin: bool = False,
        new_permissions: Optional[List[str]] = None,
        constraints: Optional[Dict[str, Any]] = None,
        expires_at: Optional[datetime] = None,
    ) -> PatchDelegationResult:
        """Narrow delegation permissions in place (monotonic attenuation).

        Revokes active agent sessions bound to the delegation on success.
        """
        delegation = self.get_delegation(delegation_id)
        if not delegation:
            raise DelegationNotFoundError(f"Delegation not found: {delegation_id}")

        if not is_admin and delegation.delegator != actor:
            raise DelegationForbiddenError("Not authorized to modify this delegation")

        if delegation.is_revoked or delegation.is_expired:
            raise DelegationInvalidStateError(
                "Delegation is revoked or expired and cannot be patched"
            )

        if delegation.status == "pending":
            raise DelegationInvalidStateError(
                "Pending delegations must be accepted before patching permissions"
            )

        if (
            new_permissions is None
            and constraints is None
            and expires_at is None
        ):
            raise DelegationError("At least one patch field is required")

        previous_permissions = list(delegation.delegated_permissions or [])

        if new_permissions is not None:
            current_set = set(previous_permissions)
            new_set = set(new_permissions)
            if not new_set.issubset(current_set):
                raise PermissionWideningError(
                    message="permission_widening_not_allowed",
                    attempted=list(new_permissions),
                    current=previous_permissions,
                    allowed_ceiling=previous_permissions,
                )

            is_valid, reason, invalid_perms, allowed_perms = (
                self._validate_permissions_subset(delegation.delegator, new_permissions)
            )
            if not is_valid:
                raise PermissionValidationError(
                    message=reason or "Permission validation failed",
                    invalid_permissions=invalid_perms,
                    allowed_permissions=allowed_perms,
                )

            self._validate_template_ceiling(delegation.agent_id, new_permissions)
            delegation.delegated_permissions = new_permissions

        if constraints is not None:
            merged = dict(delegation.constraints or {})
            merged.update(constraints)
            delegation.constraints = merged

        if expires_at is not None:
            expires_at_aware = expires_at
            if expires_at_aware.tzinfo is None:
                expires_at_aware = expires_at_aware.replace(tzinfo=timezone.utc)
            if expires_at_aware <= datetime.now(timezone.utc):
                raise DelegationError("expires_at must be in the future")
            delegation.expires_at = expires_at_aware

        delegation.sync_status()

        active_sessions = (
            self._db.query(AgentSession)
            .filter(
                AgentSession.delegation_id == delegation_id,
                AgentSession.is_active.is_(True),
            )
            .all()
        )
        sessions_revoked = 0
        for session in active_sessions:
            session.revoke(
                revoked_by=actor,
                reason="Delegation permissions updated",
            )
            sessions_revoked += 1

        AuditLoggerService(self._db).log_event(
            event_type=AuditEventType.DELEGATION_PERMISSIONS_UPDATED,
            on_behalf_of=delegation.delegator,
            agent_id=delegation.agent_id,
            delegation_id=delegation.id,
            extra_data={
                "previous_permissions": previous_permissions,
                "new_permissions": list(delegation.delegated_permissions or []),
                "patched_by": actor,
                "is_admin": is_admin,
                "sessions_revoked": sessions_revoked,
            },
        )

        self._db.commit()
        self._db.refresh(delegation)

        logger.info(
            "Patched delegation %s by %s (admin=%s) sessions_revoked=%d",
            delegation_id,
            actor,
            is_admin,
            sessions_revoked,
        )

        return PatchDelegationResult(
            delegation=delegation,
            sessions_revoked=sessions_revoked,
            previous_permissions=previous_permissions,
        )

    def accept_delegation(
        self,
        delegation_id: str,
        actor: str,
    ) -> AcceptDelegationResult:
        """Activate a pending invite with template ceiling permissions."""
        delegation = self.get_delegation(delegation_id)
        if not delegation:
            raise DelegationNotFoundError(f"Delegation not found: {delegation_id}")

        if delegation.delegator != actor:
            raise DelegationForbiddenError("Not authorized to accept this delegation")

        if delegation.status != "pending":
            raise DelegationNotPendingError(
                "Delegation is not pending and cannot be accepted"
            )

        if delegation.is_revoked or delegation.is_expired:
            raise DelegationInvalidStateError(
                "Delegation is revoked or expired and cannot be accepted"
            )

        if not delegation.template_id:
            raise DelegationError("Pending delegation has no associated template")

        template = (
            self._db.query(DelegationTemplate)
            .filter(DelegationTemplate.id == delegation.template_id)
            .first()
        )
        if not template:
            raise DelegationError("Associated template not found")

        permissions = self.template_effective_permissions(template)
        is_valid, reason, invalid_perms, allowed_perms = (
            self._validate_permissions_subset(delegation.delegator, permissions)
        )
        if not is_valid:
            raise PermissionValidationError(
                message=reason or "Connected services insufficient for template permissions",
                invalid_permissions=invalid_perms,
                allowed_permissions=allowed_perms,
            )

        delegation.delegated_permissions = permissions
        delegation.status = "active"
        delegation.sync_status()

        AuditLoggerService(self._db).log_event(
            event_type=AuditEventType.DELEGATION_ACCEPTED,
            on_behalf_of=delegation.delegator,
            agent_id=delegation.agent_id,
            delegation_id=delegation.id,
            extra_data={
                "template_id": str(delegation.template_id),
                "permissions": permissions,
                "accepted_by": actor,
            },
        )

        self._db.commit()
        self._db.refresh(delegation)

        logger.info(
            "Accepted delegation %s for %s agent=%s permissions=%d",
            delegation_id,
            actor,
            delegation.agent_id,
            len(permissions),
        )

        return AcceptDelegationResult(delegation=delegation)

    def invite_users_to_template(
        self,
        template_id: str,
        user_emails: List[str],
        actor: str,
    ) -> InviteUsersResult:
        """Create pending invite delegations for specific users."""
        template = (
            self._db.query(DelegationTemplate)
            .filter(DelegationTemplate.id == template_id)
            .first()
        )
        if not template:
            raise DelegationNotFoundError(f"Template not found: {template_id}")

        delegation_ids: List[str] = []
        skipped: List[str] = []
        ttl_days = template.default_ttl_days or self.DEFAULT_EXPIRY_DAYS
        expires_at = datetime.now(timezone.utc) + timedelta(days=ttl_days)

        for email in user_emails:
            normalized = email.strip().lower()
            if not normalized:
                continue

            existing = self._get_blocking_delegation(normalized, template.agent_id)
            if existing:
                skipped.append(normalized)
                continue

            delegation_id = f"del-{uuid.uuid4()}"
            delegation = DelegationToken(
                id=delegation_id,
                agent_id=template.agent_id,
                delegator=normalized,
                delegated_permissions=[],
                constraints={},
                source="invite",
                status="pending",
                template_id=str(template.id),
                expires_at=expires_at,
                revocation_uri=self._generate_revocation_uri(delegation_id),
            )
            self._db.add(delegation)
            delegation_ids.append(delegation_id)

        if delegation_ids:
            AuditLoggerService(self._db).log_event(
                event_type=AuditEventType.DELEGATION_INVITE_SENT,
                on_behalf_of=actor,
                agent_id=template.agent_id,
                extra_data={
                    "template_id": str(template.id),
                    "invited_users": [
                        e.strip().lower()
                        for e in user_emails
                        if e.strip().lower() not in skipped
                    ],
                    "delegation_ids": delegation_ids,
                    "skipped": skipped,
                },
            )
            self._db.commit()

        logger.info(
            "Template %s invite by %s: invited=%d skipped=%d",
            template_id,
            actor,
            len(delegation_ids),
            len(skipped),
        )

        return InviteUsersResult(
            invited=len(delegation_ids),
            delegation_ids=delegation_ids,
            skipped=skipped,
        )

    def create_template_delegation(
        self,
        delegator: str,
        template: DelegationTemplate,
        *,
        source: str = "template",
    ) -> Optional[DelegationToken]:
        """Create an active delegation from a template if user has required scopes."""
        if self.get_active_delegation(delegator, template.agent_id):
            return None

        permissions = self.template_effective_permissions(template)
        if not permissions:
            return None

        is_valid, _, _, _ = self._validate_permissions_subset(delegator, permissions)
        if not is_valid:
            return None

        ttl_days = template.default_ttl_days or self.DEFAULT_EXPIRY_DAYS
        delegation_id = f"del-{uuid.uuid4()}"
        delegation = DelegationToken(
            id=delegation_id,
            agent_id=template.agent_id,
            delegator=delegator,
            delegated_permissions=permissions,
            constraints={},
            source=source,
            status="active",
            template_id=str(template.id),
            expires_at=datetime.now(timezone.utc) + timedelta(days=ttl_days),
            revocation_uri=self._generate_revocation_uri(delegation_id),
        )
        self._db.add(delegation)
        return delegation

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
