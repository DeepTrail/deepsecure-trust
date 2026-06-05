"""
Gateway-side agent session revocation checks (WS-D5).

Reads revocation markers written by the control plane into Redis.
"""

from __future__ import annotations

import logging
import os
from typing import Optional

logger = logging.getLogger(__name__)

REVOKED_SESSION_KEY_PREFIX = "revoked_agent_session:"


class SessionRevocationChecker:
    """Async Redis lookup for revoked agent session IDs."""

    def __init__(self, redis_url: str | None = None) -> None:
        self._redis_url = redis_url or os.getenv("REDIS_URL")
        self._client: Optional[object] = None

    async def _get_client(self):
        if self._client is not None:
            return self._client
        if not self._redis_url:
            return None
        try:
            import redis.asyncio as aioredis

            self._client = aioredis.from_url(
                self._redis_url, decode_responses=True
            )
            await self._client.ping()
            return self._client
        except Exception as exc:
            logger.warning("Redis unavailable for revocation check: %s", exc)
            self._client = None
            return None

    async def is_revoked(self, session_id: str | None) -> bool:
        """Return True when the session has been revoked."""
        if not session_id:
            return False

        if not self._redis_url:
            return False

        client = await self._get_client()
        if client is None:
            logger.error(
                "Revocation check failed closed for session %s — Redis unavailable",
                session_id,
            )
            return True

        try:
            key = f"{REVOKED_SESSION_KEY_PREFIX}{session_id}"
            return bool(await client.exists(key))
        except Exception as exc:
            logger.error(
                "Revocation Redis error for session %s: %s — failing closed",
                session_id,
                exc,
            )
            return True

    async def close(self) -> None:
        if self._client is not None:
            try:
                await self._client.aclose()
            except Exception:
                pass
            self._client = None


_checker: SessionRevocationChecker | None = None


def configure_session_revocation_checker(
    redis_url: str | None = None,
) -> SessionRevocationChecker:
    global _checker
    _checker = SessionRevocationChecker(redis_url=redis_url)
    return _checker


def get_session_revocation_checker() -> SessionRevocationChecker | None:
    return _checker


def reset_session_revocation_checker() -> None:
    global _checker
    _checker = None
