"""
Constraint Counter Storage for the Gateway.

Provides storage backends for tracking constraint counters such as
daily action limits. Supports multiple backends:
- InMemoryConstraintStore: For testing and development
- RedisConstraintStore: For production with persistence

The storage is keyed by (agent_id, delegation_id, date) to ensure:
- Separate counters per agent
- Separate counters per delegation
- Automatic daily reset via date-based keys

Usage:
    from app.security.constraint_store import (
        InMemoryConstraintStore,
        get_constraint_store,
        configure_constraint_store,
    )
    
    # Configure for development
    configure_constraint_store(InMemoryConstraintStore())
    
    # Use the store
    store = get_constraint_store()
    count = await store.get_daily_action_count(agent_id, delegation_id)
"""

import logging
from abc import ABC, abstractmethod
from datetime import datetime, timezone
from typing import Any

logger = logging.getLogger(__name__)


# =============================================================================
# Abstract Base Class
# =============================================================================


class ConstraintStore(ABC):
    """
    Abstract base for constraint counter storage.
    
    Implementations must provide thread-safe counter operations
    with proper TTL/cleanup handling.
    """
    
    @abstractmethod
    async def get_daily_action_count(
        self, agent_id: str, delegation_id: str
    ) -> int:
        """
        Get today's action count for an agent/delegation pair.
        
        Args:
            agent_id: The agent identifier
            delegation_id: The delegation identifier
            
        Returns:
            Current action count (0 if no actions today)
        """
        pass
    
    @abstractmethod
    async def increment_daily_action_count(
        self, agent_id: str, delegation_id: str
    ) -> int:
        """
        Increment the daily action counter.
        
        Args:
            agent_id: The agent identifier
            delegation_id: The delegation identifier
            
        Returns:
            The new count after incrementing
        """
        pass
    
    @abstractmethod
    async def get_session_action_count(
        self, agent_id: str, session_id: str
    ) -> int:
        """
        Get session action count for an agent/session pair.
        
        Args:
            agent_id: The agent identifier
            session_id: The session identifier
            
        Returns:
            Current action count for the session
        """
        pass
    
    @abstractmethod
    async def increment_session_action_count(
        self, agent_id: str, session_id: str
    ) -> int:
        """
        Increment the session action counter.
        
        Args:
            agent_id: The agent identifier
            session_id: The session identifier
            
        Returns:
            The new count after incrementing
        """
        pass
    
    @abstractmethod
    async def reset_session_count(
        self, agent_id: str, session_id: str
    ) -> None:
        """
        Reset the session counter (e.g., when session ends).
        
        Args:
            agent_id: The agent identifier
            session_id: The session identifier
        """
        pass


# =============================================================================
# In-Memory Implementation
# =============================================================================


class InMemoryConstraintStore(ConstraintStore):
    """
    In-memory store for testing and development.
    
    Counters are keyed by date (for daily) or session_id (for session).
    Not persistent across restarts - use Redis for production.
    
    Thread-safety note: This implementation is NOT thread-safe.
    Use RedisConstraintStore for concurrent access.
    """
    
    def __init__(self):
        # Key: (agent_id, delegation_id, date_str) -> count
        self._daily_counts: dict[tuple[str, str, str], int] = {}
        # Key: (agent_id, session_id) -> count
        self._session_counts: dict[tuple[str, str], int] = {}
    
    def _get_today(self) -> str:
        """Get today's date string in UTC."""
        return datetime.now(timezone.utc).strftime("%Y-%m-%d")
    
    def _get_daily_key(
        self, agent_id: str, delegation_id: str
    ) -> tuple[str, str, str]:
        """Generate daily counter key."""
        return (agent_id, delegation_id, self._get_today())
    
    async def get_daily_action_count(
        self, agent_id: str, delegation_id: str
    ) -> int:
        key = self._get_daily_key(agent_id, delegation_id)
        return self._daily_counts.get(key, 0)
    
    async def increment_daily_action_count(
        self, agent_id: str, delegation_id: str
    ) -> int:
        key = self._get_daily_key(agent_id, delegation_id)
        self._daily_counts[key] = self._daily_counts.get(key, 0) + 1
        return self._daily_counts[key]
    
    async def get_session_action_count(
        self, agent_id: str, session_id: str
    ) -> int:
        key = (agent_id, session_id)
        return self._session_counts.get(key, 0)
    
    async def increment_session_action_count(
        self, agent_id: str, session_id: str
    ) -> int:
        key = (agent_id, session_id)
        self._session_counts[key] = self._session_counts.get(key, 0) + 1
        return self._session_counts[key]
    
    async def reset_session_count(
        self, agent_id: str, session_id: str
    ) -> None:
        key = (agent_id, session_id)
        self._session_counts.pop(key, None)
    
    def clear_all(self) -> None:
        """Clear all counters (for testing)."""
        self._daily_counts.clear()
        self._session_counts.clear()
    
    def get_all_counts(self) -> dict[str, Any]:
        """Get all counts for debugging."""
        return {
            "daily": dict(self._daily_counts),
            "session": dict(self._session_counts),
        }


# =============================================================================
# Redis Implementation
# =============================================================================


class RedisConstraintStore(ConstraintStore):
    """
    Redis-backed store for production.
    
    Uses Redis INCR for atomic increments and TTL for automatic cleanup.
    Daily counters expire after 48 hours to handle timezone edge cases.
    Session counters expire after 24 hours (configurable).
    
    Key format:
    - Daily: "constraints:daily:{agent_id}:{delegation_id}:{date}"
    - Session: "constraints:session:{agent_id}:{session_id}"
    """
    
    DAILY_TTL_SECONDS = 48 * 60 * 60  # 48 hours
    SESSION_TTL_SECONDS = 24 * 60 * 60  # 24 hours
    
    def __init__(self, redis_client: Any):
        """
        Initialize with a Redis client.
        
        Args:
            redis_client: An async Redis client (e.g., redis.asyncio.Redis)
        """
        self.redis = redis_client
    
    def _get_today(self) -> str:
        """Get today's date string in UTC."""
        return datetime.now(timezone.utc).strftime("%Y-%m-%d")
    
    def _get_daily_key(self, agent_id: str, delegation_id: str) -> str:
        """Generate Redis key for daily counter."""
        today = self._get_today()
        return f"constraints:daily:{agent_id}:{delegation_id}:{today}"
    
    def _get_session_key(self, agent_id: str, session_id: str) -> str:
        """Generate Redis key for session counter."""
        return f"constraints:session:{agent_id}:{session_id}"
    
    async def get_daily_action_count(
        self, agent_id: str, delegation_id: str
    ) -> int:
        key = self._get_daily_key(agent_id, delegation_id)
        value = await self.redis.get(key)
        return int(value) if value else 0
    
    async def increment_daily_action_count(
        self, agent_id: str, delegation_id: str
    ) -> int:
        key = self._get_daily_key(agent_id, delegation_id)
        # Use pipeline for atomic INCR + EXPIRE
        pipe = self.redis.pipeline()
        pipe.incr(key)
        pipe.expire(key, self.DAILY_TTL_SECONDS)
        result = await pipe.execute()
        return result[0]
    
    async def get_session_action_count(
        self, agent_id: str, session_id: str
    ) -> int:
        key = self._get_session_key(agent_id, session_id)
        value = await self.redis.get(key)
        return int(value) if value else 0
    
    async def increment_session_action_count(
        self, agent_id: str, session_id: str
    ) -> int:
        key = self._get_session_key(agent_id, session_id)
        pipe = self.redis.pipeline()
        pipe.incr(key)
        pipe.expire(key, self.SESSION_TTL_SECONDS)
        result = await pipe.execute()
        return result[0]
    
    async def reset_session_count(
        self, agent_id: str, session_id: str
    ) -> None:
        key = self._get_session_key(agent_id, session_id)
        await self.redis.delete(key)


# =============================================================================
# Module-Level Configuration
# =============================================================================


# Singleton instance
_constraint_store: ConstraintStore | None = None


def get_constraint_store() -> ConstraintStore:
    """
    Get the configured constraint store instance.
    
    Returns the singleton, creating an InMemoryStore if not configured.
    
    Returns:
        ConstraintStore instance
    """
    global _constraint_store
    if _constraint_store is None:
        logger.warning(
            "Constraint store not configured, using in-memory store. "
            "Configure with configure_constraint_store() for production."
        )
        _constraint_store = InMemoryConstraintStore()
    return _constraint_store


def configure_constraint_store(store: ConstraintStore) -> ConstraintStore:
    """
    Configure the constraint store singleton.
    
    Args:
        store: The ConstraintStore implementation to use
        
    Returns:
        The configured store
    """
    global _constraint_store
    _constraint_store = store
    logger.info("Constraint store configured: %s", type(store).__name__)
    return _constraint_store


def reset_constraint_store() -> None:
    """Reset the constraint store (for testing)."""
    global _constraint_store
    _constraint_store = None
