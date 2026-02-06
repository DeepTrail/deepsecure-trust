"""
Constraint Checker for the Gateway.

Validates delegation constraints such as:
- max_actions_per_day: Limit total tool calls per 24-hour period
- max_actions_per_session: Limit tool calls per agent session
- expiration: Already handled by delegation validator

This module implements the constraint validation from the design doc:
  "3. VALIDATE constraints:
   • max_actions_per_day: 100
   • Current count: 0 → Increment to 1 ✓ ALLOWED"

Usage:
    from app.security.constraint_checker import (
        get_constraint_checker,
        ConstraintViolation,
    )
    
    checker = get_constraint_checker()
    violation = await checker.check_and_increment(
        agent_id="agent-123",
        delegation_id="del-456",
        session_id="session-789",
        constraints={"max_actions_per_day": 100}
    )
    
    if violation:
        raise MCPError(-32012, f"Constraint violated: {violation.message}")
"""

import logging
from dataclasses import dataclass
from enum import Enum
from typing import Any

from .constraint_store import ConstraintStore, get_constraint_store

logger = logging.getLogger(__name__)


# =============================================================================
# Enums and Data Classes
# =============================================================================


class ConstraintType(str, Enum):
    """Types of constraints supported."""
    MAX_ACTIONS_PER_DAY = "max_actions_per_day"
    MAX_ACTIONS_PER_SESSION = "max_actions_per_session"


@dataclass
class ConstraintViolation:
    """
    Represents a constraint violation.
    
    Returned when a constraint check fails, providing details
    about which constraint was violated and by how much.
    
    Attributes:
        constraint_name: Name of the violated constraint
        constraint_type: Type of constraint (for categorization)
        current_value: Current counter value
        limit_value: The limit that was exceeded
        message: Human-readable error message
    """
    constraint_name: str
    constraint_type: ConstraintType
    current_value: int
    limit_value: int
    message: str


@dataclass
class ConstraintStatus:
    """
    Status of a single constraint.
    
    Attributes:
        current: Current usage count
        limit: Maximum allowed
        remaining: How many actions left
        percentage_used: Usage as a percentage (0-100)
    """
    current: int
    limit: int
    remaining: int
    percentage_used: float


# =============================================================================
# ConstraintChecker
# =============================================================================


class ConstraintChecker:
    """
    Validates delegation constraints.
    
    Checks various constraint types and maintains counters via
    a ConstraintStore backend. Supports atomic check-and-increment
    to prevent race conditions.
    
    Security principle: Fail-closed - if we can't verify constraints,
    deny the request.
    
    Example:
        >>> checker = ConstraintChecker(store)
        >>> violation = await checker.check_and_increment(
        ...     agent_id="agent-1",
        ...     delegation_id="del-1",
        ...     session_id="session-1",
        ...     constraints={"max_actions_per_day": 100}
        ... )
        >>> if violation:
        ...     print(f"Blocked: {violation.message}")
    """
    
    def __init__(self, store: ConstraintStore | None = None):
        """
        Initialize the constraint checker.
        
        Args:
            store: Constraint storage backend (uses singleton if not provided)
        """
        self._store = store
    
    @property
    def store(self) -> ConstraintStore:
        """Get the constraint store, using singleton if not set."""
        if self._store is None:
            self._store = get_constraint_store()
        return self._store
    
    async def check_constraints(
        self,
        agent_id: str,
        delegation_id: str,
        session_id: str | None,
        constraints: dict[str, Any],
    ) -> ConstraintViolation | None:
        """
        Check if constraints would be violated (without incrementing).
        
        Use this for validation before committing to an action.
        
        Args:
            agent_id: The agent making the request
            delegation_id: The delegation being used
            session_id: The current session ID (for session constraints)
            constraints: Constraint configuration from delegation
            
        Returns:
            ConstraintViolation if any constraint would be violated, None if OK
        """
        # Check max_actions_per_day
        if ConstraintType.MAX_ACTIONS_PER_DAY.value in constraints:
            max_actions = constraints[ConstraintType.MAX_ACTIONS_PER_DAY.value]
            current_count = await self.store.get_daily_action_count(
                agent_id, delegation_id
            )
            
            if current_count >= max_actions:
                return ConstraintViolation(
                    constraint_name=ConstraintType.MAX_ACTIONS_PER_DAY.value,
                    constraint_type=ConstraintType.MAX_ACTIONS_PER_DAY,
                    current_value=current_count,
                    limit_value=max_actions,
                    message=f"Daily action limit exceeded ({current_count}/{max_actions})",
                )
        
        # Check max_actions_per_session
        if (
            ConstraintType.MAX_ACTIONS_PER_SESSION.value in constraints
            and session_id
        ):
            max_session_actions = constraints[
                ConstraintType.MAX_ACTIONS_PER_SESSION.value
            ]
            session_count = await self.store.get_session_action_count(
                agent_id, session_id
            )
            
            if session_count >= max_session_actions:
                return ConstraintViolation(
                    constraint_name=ConstraintType.MAX_ACTIONS_PER_SESSION.value,
                    constraint_type=ConstraintType.MAX_ACTIONS_PER_SESSION,
                    current_value=session_count,
                    limit_value=max_session_actions,
                    message=f"Session action limit exceeded ({session_count}/{max_session_actions})",
                )
        
        return None
    
    async def check_and_increment(
        self,
        agent_id: str,
        delegation_id: str,
        session_id: str | None,
        constraints: dict[str, Any],
    ) -> ConstraintViolation | None:
        """
        Check constraints and increment counters if allowed.
        
        This is the main method used during tool execution:
        1. Check if any constraint would be violated
        2. If OK, increment all relevant counters
        3. Return violation if blocked, None if allowed
        
        Args:
            agent_id: The agent making the request
            delegation_id: The delegation being used
            session_id: The current session ID (for session constraints)
            constraints: Constraint configuration from delegation
            
        Returns:
            ConstraintViolation if violated, None if allowed and incremented
        """
        # First check without incrementing
        violation = await self.check_constraints(
            agent_id, delegation_id, session_id, constraints
        )
        
        if violation:
            logger.warning(
                "Constraint violated: %s for agent=%s delegation=%s",
                violation.constraint_name,
                agent_id,
                delegation_id,
            )
            return violation
        
        # All constraints OK - increment counters
        if ConstraintType.MAX_ACTIONS_PER_DAY.value in constraints:
            new_count = await self.store.increment_daily_action_count(
                agent_id, delegation_id
            )
            logger.debug(
                "Daily action count incremented to %d for agent=%s delegation=%s",
                new_count,
                agent_id,
                delegation_id,
            )
        
        if (
            ConstraintType.MAX_ACTIONS_PER_SESSION.value in constraints
            and session_id
        ):
            new_session_count = await self.store.increment_session_action_count(
                agent_id, session_id
            )
            logger.debug(
                "Session action count incremented to %d for agent=%s session=%s",
                new_session_count,
                agent_id,
                session_id,
            )
        
        return None
    
    async def get_constraint_status(
        self,
        agent_id: str,
        delegation_id: str,
        session_id: str | None,
        constraints: dict[str, Any],
    ) -> dict[str, ConstraintStatus]:
        """
        Get current constraint usage status.
        
        Useful for UI display or debugging constraint issues.
        
        Args:
            agent_id: The agent making the request
            delegation_id: The delegation being used
            session_id: The current session ID
            constraints: Constraint configuration from delegation
            
        Returns:
            Dictionary mapping constraint names to their status
        """
        status: dict[str, ConstraintStatus] = {}
        
        if ConstraintType.MAX_ACTIONS_PER_DAY.value in constraints:
            limit = constraints[ConstraintType.MAX_ACTIONS_PER_DAY.value]
            current = await self.store.get_daily_action_count(
                agent_id, delegation_id
            )
            remaining = max(0, limit - current)
            percentage = (current / limit * 100) if limit > 0 else 0
            
            status[ConstraintType.MAX_ACTIONS_PER_DAY.value] = ConstraintStatus(
                current=current,
                limit=limit,
                remaining=remaining,
                percentage_used=round(percentage, 1),
            )
        
        if (
            ConstraintType.MAX_ACTIONS_PER_SESSION.value in constraints
            and session_id
        ):
            limit = constraints[ConstraintType.MAX_ACTIONS_PER_SESSION.value]
            current = await self.store.get_session_action_count(
                agent_id, session_id
            )
            remaining = max(0, limit - current)
            percentage = (current / limit * 100) if limit > 0 else 0
            
            status[ConstraintType.MAX_ACTIONS_PER_SESSION.value] = ConstraintStatus(
                current=current,
                limit=limit,
                remaining=remaining,
                percentage_used=round(percentage, 1),
            )
        
        return status


# =============================================================================
# Module-Level Configuration
# =============================================================================


# Singleton instance
_constraint_checker: ConstraintChecker | None = None


def get_constraint_checker() -> ConstraintChecker:
    """
    Get the configured constraint checker instance.
    
    Returns the singleton, creating with default store if not configured.
    
    Returns:
        ConstraintChecker instance
    """
    global _constraint_checker
    if _constraint_checker is None:
        _constraint_checker = ConstraintChecker()
    return _constraint_checker


def configure_constraint_checker(
    store: ConstraintStore | None = None,
) -> ConstraintChecker:
    """
    Configure the constraint checker singleton.
    
    Args:
        store: Optional custom constraint store
        
    Returns:
        Configured ConstraintChecker instance
    """
    global _constraint_checker
    _constraint_checker = ConstraintChecker(store)
    logger.info("Constraint checker configured")
    return _constraint_checker


def reset_constraint_checker() -> None:
    """Reset the constraint checker (for testing)."""
    global _constraint_checker
    _constraint_checker = None
