"""
Delegation Validator for tools/call requests.

Validates that the agent has permission to execute a tool based on their
active delegation. This is a critical security component implementing:
- Demo 4: Permission Enforcement
- Step 8-9 of Sarah's Journey

Security Principles:
- Fail-closed: Deny if validation cannot complete
- Defense in depth: Validates even if tools/list filtered
- Real-time revocation support: Can check Control Plane
- Audit trail: Logs all denials

Usage:
    from app.middleware.delegation_validator import DelegationValidator
    from app.middleware.jwt_validation import AgentContext
    
    validator = DelegationValidator()
    
    result = await validator.validate_tool_call(
        tool_name="notion.search_pages",
        agent_context=agent_context,
    )
    
    if not result.allowed:
        raise PermissionDenied(result.error_message)
"""

import logging
import time
from dataclasses import dataclass
from enum import Enum
from typing import Any

import httpx

from .jwt_validation import AgentContext
from ..mcp.permission_mapper import PermissionMapper

logger = logging.getLogger(__name__)


# =============================================================================
# Enums and Data Classes
# =============================================================================


class DenialReason(Enum):
    """
    Reasons for denying a tool call.
    
    Used for structured error reporting and audit logging.
    """
    NO_CONTEXT = "no_agent_context"
    UNKNOWN_TOOL = "unknown_tool"
    PERMISSION_NOT_DELEGATED = "permission_not_delegated"
    DELEGATION_REVOKED = "delegation_revoked"
    DELEGATION_EXPIRED = "delegation_expired"
    CONSTRAINT_VIOLATED = "constraint_violated"
    VALIDATION_ERROR = "validation_error"


@dataclass
class ValidationResult:
    """
    Result of delegation validation.
    
    Provides structured information about whether a tool call is allowed,
    and if not, why it was denied.
    
    Attributes:
        allowed: Whether the tool call is permitted
        required_permission: The permission string that was checked
        denial_reason: Why the request was denied (if not allowed)
        error_message: Human-readable error message (if not allowed)
    """
    allowed: bool
    required_permission: str | None = None
    denial_reason: DenialReason | None = None
    error_message: str | None = None
    
    @classmethod
    def allow(cls, permission: str) -> "ValidationResult":
        """
        Create a result indicating the call is allowed.
        
        Args:
            permission: The permission that was validated
            
        Returns:
            ValidationResult with allowed=True
        """
        return cls(allowed=True, required_permission=permission)
    
    @classmethod
    def deny(
        cls, 
        reason: DenialReason, 
        permission: str | None = None,
        message: str | None = None
    ) -> "ValidationResult":
        """
        Create a result indicating the call is denied.
        
        Args:
            reason: Why the call was denied
            permission: The permission that was checked (if applicable)
            message: Custom error message (defaults to reason description)
            
        Returns:
            ValidationResult with allowed=False
        """
        return cls(
            allowed=False,
            required_permission=permission,
            denial_reason=reason,
            error_message=message or f"Permission denied: {reason.value}"
        )


# =============================================================================
# DelegationValidator Class
# =============================================================================


class DelegationValidator:
    """
    Validates tool calls against agent's delegation.
    
    Responsibilities:
    1. Map tool name to required permission (via PermissionMapper)
    2. Check permission is in delegated_permissions
    3. (Optional) Verify delegation is still active with Control Plane
    4. Support wildcard permissions (e.g., "notion:*")
    
    Security:
    - Fail-closed: Returns deny if any validation fails
    - Unknown tools are denied by default
    - All denials are logged for audit
    
    Example:
        >>> validator = DelegationValidator()
        >>> result = await validator.validate_tool_call(
        ...     tool_name="notion.search_pages",
        ...     agent_context=context,
        ... )
        >>> if result.allowed:
        ...     print(f"Allowed with permission: {result.required_permission}")
        ... else:
        ...     print(f"Denied: {result.error_message}")
    """
    
    def __init__(
        self,
        control_plane_url: str | None = None,
        check_revocation: bool = False,
        cache_ttl_seconds: int = 60,
    ):
        """
        Initialize the delegation validator.
        
        Args:
            control_plane_url: URL to Control Plane for revocation checks
            check_revocation: Whether to check delegation status with Control Plane
            cache_ttl_seconds: How long to cache delegation status
        """
        self.control_plane_url = control_plane_url
        self.check_revocation = check_revocation
        self.cache_ttl_seconds = cache_ttl_seconds
        self._status_cache: dict[str, tuple[bool, float]] = {}
    
    async def validate_tool_call(
        self,
        tool_name: str,
        agent_context: AgentContext | None,
    ) -> ValidationResult:
        """
        Validate a tool call against the agent's delegation.
        
        This is the main entry point for delegation validation. It performs:
        1. Agent context check (fail-closed if missing)
        2. Permission lookup (via PermissionMapper)
        3. Permission validation against delegated_permissions
        4. (Optional) Delegation status check with Control Plane
        
        Args:
            tool_name: Namespaced tool name (e.g., "notion.search_pages")
            agent_context: Agent context from JWT validation (C3)
            
        Returns:
            ValidationResult indicating whether call is allowed
            
        Example:
            >>> result = await validator.validate_tool_call(
            ...     "notion.search_pages",
            ...     agent_context,
            ... )
            >>> result.allowed
            True
        """
        # Step 1: Check agent context exists (fail-closed)
        if agent_context is None:
            logger.warning(
                "Delegation validation failed: no agent context for tool %s",
                tool_name,
            )
            return ValidationResult.deny(
                DenialReason.NO_CONTEXT,
                message="No agent context. Authentication required."
            )
        
        # Step 2: Get required permission for tool
        required_permission = PermissionMapper.get_permission(tool_name)
        
        if required_permission is None:
            # Try to infer for better error message
            inferred = PermissionMapper.infer_permission(tool_name)
            logger.warning(
                "Unknown tool %s requested by agent %s",
                tool_name,
                agent_context.agent_id,
            )
            return ValidationResult.deny(
                DenialReason.UNKNOWN_TOOL,
                permission=inferred,
                message=f"Unknown tool: {tool_name}"
            )
        
        # Step 3: Check permission in delegated_permissions
        if not self._check_permission(
            required_permission, 
            agent_context.delegated_permissions
        ):
            logger.info(
                "Permission denied for %s: %s not in delegation for agent %s",
                tool_name,
                required_permission,
                agent_context.agent_id,
            )
            return ValidationResult.deny(
                DenialReason.PERMISSION_NOT_DELEGATED,
                permission=required_permission,
                message=f"Permission denied: {required_permission} not delegated"
            )
        
        # Step 4: (Optional) Check delegation is still active
        if self.check_revocation and agent_context.delegation_id:
            is_active = await self._check_delegation_active(
                agent_context.delegation_id
            )
            if not is_active:
                logger.warning(
                    "Delegation %s is revoked/expired for agent %s",
                    agent_context.delegation_id,
                    agent_context.agent_id,
                )
                return ValidationResult.deny(
                    DenialReason.DELEGATION_REVOKED,
                    permission=required_permission,
                    message="Delegation has been revoked or expired"
                )
        
        # All checks passed
        logger.debug(
            "Delegation validated: tool=%s, permission=%s, agent=%s",
            tool_name,
            required_permission,
            agent_context.agent_id,
        )
        return ValidationResult.allow(required_permission)
    
    def validate_permission_sync(
        self,
        tool_name: str,
        delegated_permissions: list[str],
    ) -> ValidationResult:
        """
        Synchronous permission validation (no revocation check).
        
        Useful when only permission checking is needed without
        async context or agent context.
        
        Args:
            tool_name: Namespaced tool name
            delegated_permissions: List of permission strings
            
        Returns:
            ValidationResult
        """
        required_permission = PermissionMapper.get_permission(tool_name)
        
        if required_permission is None:
            inferred = PermissionMapper.infer_permission(tool_name)
            return ValidationResult.deny(
                DenialReason.UNKNOWN_TOOL,
                permission=inferred,
                message=f"Unknown tool: {tool_name}"
            )
        
        if not self._check_permission(required_permission, delegated_permissions):
            return ValidationResult.deny(
                DenialReason.PERMISSION_NOT_DELEGATED,
                permission=required_permission,
                message=f"Permission denied: {required_permission} not delegated"
            )
        
        return ValidationResult.allow(required_permission)
    
    def _check_permission(
        self,
        required_permission: str,
        delegated_permissions: list[str],
    ) -> bool:
        """
        Check if required permission is in delegated permissions.
        
        Supports:
        - Exact match: "notion:pages:search" in permissions
        - Backend wildcard: "notion:*" matches any notion permission
        - Resource wildcard: "notion:pages:*" matches any notion pages action
        - Full wildcard: "*:*" matches anything (admin/testing)
        
        Args:
            required_permission: Permission string needed for tool
            delegated_permissions: Agent's delegated permissions
            
        Returns:
            True if permission is granted
        """
        # Exact match
        if required_permission in delegated_permissions:
            return True
        
        # Parse permission for wildcard checks
        parts = required_permission.split(":")
        if len(parts) < 1:
            return False
        
        backend = parts[0]
        
        # Check backend wildcard (e.g., "notion:*")
        if f"{backend}:*" in delegated_permissions:
            return True
        
        # Check resource wildcard (e.g., "notion:pages:*")
        if len(parts) >= 2:
            resource = parts[1]
            if f"{backend}:{resource}:*" in delegated_permissions:
                return True
        
        # Check full wildcard (admin/testing only)
        if "*:*" in delegated_permissions:
            return True
        
        return False
    
    async def _check_delegation_active(
        self,
        delegation_id: str,
    ) -> bool:
        """
        Check if delegation is still active with Control Plane.
        
        MVP: Always returns True (no Control Plane call)
        Production: Calls Control Plane with caching
        
        Args:
            delegation_id: Delegation ID from JWT
            
        Returns:
            True if delegation is active, False if revoked/expired
        """
        if not self.control_plane_url:
            # MVP: No Control Plane configured, assume active
            return True
        
        # Check cache first
        now = time.time()
        if delegation_id in self._status_cache:
            is_active, cached_at = self._status_cache[delegation_id]
            if now - cached_at < self.cache_ttl_seconds:
                logger.debug(
                    "Delegation status cache hit for %s: active=%s",
                    delegation_id,
                    is_active,
                )
                return is_active
        
        # Call Control Plane
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{self.control_plane_url}/api/v1/delegations/{delegation_id}/status",
                    timeout=5.0,
                )
                
                if response.status_code == 200:
                    data = response.json()
                    is_active = data.get("status") == "active"
                elif response.status_code == 404:
                    is_active = False
                else:
                    # Fail-closed: assume inactive on error
                    logger.error(
                        "Control Plane returned %d for delegation %s",
                        response.status_code,
                        delegation_id,
                    )
                    is_active = False
                
                # Cache result
                self._status_cache[delegation_id] = (is_active, now)
                return is_active
                
        except httpx.TimeoutException:
            logger.error(
                "Timeout checking delegation status for %s",
                delegation_id,
            )
            # Fail-closed: assume inactive on timeout
            return False
        except Exception as e:
            logger.error(
                "Failed to check delegation status for %s: %s",
                delegation_id,
                e,
            )
            # Fail-closed: assume inactive on network error
            return False
    
    def clear_cache(self) -> None:
        """Clear the delegation status cache."""
        self._status_cache.clear()
        logger.debug("Delegation status cache cleared")
    
    def get_cache_stats(self) -> dict[str, Any]:
        """Get cache statistics for monitoring."""
        return {
            "cached_delegations": len(self._status_cache),
            "cache_ttl_seconds": self.cache_ttl_seconds,
        }


# =============================================================================
# Module-Level Configuration
# =============================================================================


# Singleton instance for handler use
_validator: DelegationValidator | None = None


def get_delegation_validator() -> DelegationValidator:
    """
    Get the configured delegation validator.
    
    Returns the singleton validator instance, creating it with
    defaults if not configured.
    
    Returns:
        DelegationValidator instance
    """
    global _validator
    if _validator is None:
        _validator = DelegationValidator()
    return _validator


def configure_delegation_validator(
    control_plane_url: str | None = None,
    check_revocation: bool = False,
    cache_ttl_seconds: int = 60,
) -> DelegationValidator:
    """
    Configure and return the delegation validator.
    
    Args:
        control_plane_url: URL to Control Plane for revocation checks
        check_revocation: Whether to check delegation status
        cache_ttl_seconds: Cache TTL for delegation status
        
    Returns:
        Configured DelegationValidator instance
    """
    global _validator
    _validator = DelegationValidator(
        control_plane_url=control_plane_url,
        check_revocation=check_revocation,
        cache_ttl_seconds=cache_ttl_seconds,
    )
    logger.info(
        "Delegation validator configured: check_revocation=%s, control_plane_url=%s",
        check_revocation,
        control_plane_url or "None",
    )
    return _validator


def reset_delegation_validator() -> None:
    """Reset the delegation validator (for testing)."""
    global _validator
    _validator = None


# =============================================================================
# Convenience Functions
# =============================================================================


async def validate_tool_call(
    tool_name: str,
    agent_context: AgentContext | None,
) -> ValidationResult:
    """
    Convenience function to validate a tool call.
    
    Uses the configured singleton validator.
    
    Args:
        tool_name: Namespaced tool name
        agent_context: Agent context from JWT validation
        
    Returns:
        ValidationResult
    """
    validator = get_delegation_validator()
    return await validator.validate_tool_call(tool_name, agent_context)


def is_tool_permitted(
    tool_name: str,
    delegated_permissions: list[str],
) -> bool:
    """
    Quick check if a tool is permitted by the given permissions.
    
    Synchronous helper for simple permission checks.
    
    Args:
        tool_name: Namespaced tool name
        delegated_permissions: List of permission strings
        
    Returns:
        True if permitted, False otherwise
    """
    validator = get_delegation_validator()
    result = validator.validate_permission_sync(tool_name, delegated_permissions)
    return result.allowed
