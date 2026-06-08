"""JWT lifecycle management with automatic refresh before expiry."""

from __future__ import annotations

import logging
import time
from typing import Optional

import httpx

from deepsecure._core.bootstrap import BootstrapClient

logger = logging.getLogger(__name__)


class JWTManager:
    """Manages discovery and delegation JWTs with proactive refresh.

    Tokens are refreshed ``refresh_margin`` seconds before they expire so
    that a tool call never hits the gateway with a stale token.
    """

    def __init__(
        self,
        bootstrap_client: BootstrapClient,
        agent_id: str,
        platform: str = "auto",
        refresh_margin: int = 300,
    ) -> None:
        self._client = bootstrap_client
        self._agent_id = agent_id
        self._platform = platform
        self._refresh_margin = refresh_margin

        self._discovery_jwt: Optional[str] = None
        self._discovery_expires_at: float = 0
        self._delegation_jwt: Optional[str] = None
        self._delegation_expires_at: float = 0
        self._current_delegation_id: Optional[str] = None

    def _discovery_valid(self) -> bool:
        return bool(
            self._discovery_jwt
            and time.time() < (self._discovery_expires_at - self._refresh_margin)
        )

    def _delegation_valid(self, delegation_id: str) -> bool:
        return bool(
            self._delegation_jwt
            and self._current_delegation_id == delegation_id
            and time.time() < (self._delegation_expires_at - self._refresh_margin)
        )

    async def ensure_discovery_jwt(self) -> str:
        """Return a valid discovery JWT, re-bootstrapping if needed."""
        if self._discovery_valid():
            return self._discovery_jwt  # type: ignore[return-value]

        logger.info("Refreshing discovery JWT for agent %s", self._agent_id)
        result = self._client.bootstrap(
            agent_id=self._agent_id, platform=self._platform
        )
        self._discovery_jwt = result.jwt
        self._discovery_expires_at = time.time() + result.expires_in
        return self._discovery_jwt

    async def get_delegation_jwt(self, delegation_id: str) -> str:
        """Return a valid delegation JWT, refreshing if needed."""
        if self._delegation_valid(delegation_id):
            return self._delegation_jwt  # type: ignore[return-value]

        discovery = await self.ensure_discovery_jwt()
        logger.info("Fetching delegation JWT for %s", delegation_id)

        async with httpx.AsyncClient() as client:
            resp = await client.post(
                f"{self._client.control_url}/api/v1/auth/agent/delegation-token",
                json={"delegation_id": delegation_id},
                headers={"Authorization": f"Bearer {discovery}"},
                timeout=30.0,
            )
            resp.raise_for_status()
            data = resp.json()

        self._delegation_jwt = data["access_token"]
        self._delegation_expires_at = time.time() + data.get("expires_in", 3600)
        self._current_delegation_id = delegation_id
        return self._delegation_jwt

    def invalidate(self) -> None:
        """Force re-fetch on next call (e.g. after a 401)."""
        self._discovery_jwt = None
        self._delegation_jwt = None
