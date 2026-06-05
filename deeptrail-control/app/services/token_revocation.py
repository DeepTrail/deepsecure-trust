"""
Redis-backed agent session revocation (WS-D5).

When a session is revoked at the control plane, its ID is written to Redis
with a TTL matching the session's remaining lifetime.  The gateway checks
this set before accepting DeepSecure agent JWTs.
"""

from __future__ import annotations

import logging
import os
from datetime import datetime, timezone
from typing import Optional

logger = logging.getLogger(__name__)

REVOKED_SESSION_KEY_PREFIX = "revoked_agent_session:"

_redis_client: Optional[object] = None


def _get_redis():
    global _redis_client
    if _redis_client is not None:
        return _redis_client

    url = os.getenv("REDIS_URL")
    if not url:
        return None

    try:
        import redis

        client = redis.from_url(url, decode_responses=True)
        client.ping()
        _redis_client = client
        return _redis_client
    except Exception as exc:
        logger.warning("Redis unavailable for token revocation: %s", exc)
        return None


def revoke_agent_session(session_id: str, ttl_seconds: int) -> bool:
    """Mark an agent session as revoked in Redis until its natural expiry."""
    client = _get_redis()
    if not client:
        logger.error(
            "Cannot record revocation for session %s — Redis unavailable",
            session_id,
        )
        return False

    ttl = max(int(ttl_seconds), 60)
    key = f"{REVOKED_SESSION_KEY_PREFIX}{session_id}"
    client.setex(key, ttl, "1")
    logger.info("Recorded revoked session %s in Redis (ttl=%ss)", session_id, ttl)
    return True


def ttl_seconds_until(expires_at: datetime | None, default: int = 28800) -> int:
    """Compute Redis TTL from a session expiry timestamp."""
    if expires_at is None:
        return default
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)
    remaining = int((expires_at - datetime.now(timezone.utc)).total_seconds())
    return max(remaining, 60)


def is_agent_session_revoked(session_id: str) -> bool:
    """Return True if the session ID is present in the revocation store."""
    client = _get_redis()
    if not client or not session_id:
        return False
    key = f"{REVOKED_SESSION_KEY_PREFIX}{session_id}"
    return bool(client.exists(key))


def reset_revocation_client() -> None:
    """Reset cached Redis client (for tests)."""
    global _redis_client
    _redis_client = None
