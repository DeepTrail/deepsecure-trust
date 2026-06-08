"""Round-robin delegation rotation for multi-user agent scenarios."""

from __future__ import annotations

import logging
from typing import Optional

import httpx

from deepsecure._core.bootstrap import BootstrapClient

logger = logging.getLogger(__name__)


class DelegationRotator:
    """Cycles through an agent's active delegations in round-robin order.

    Fetch delegations from the control plane, then call ``rotate()`` after
    completing a batch of tool calls to switch to the next delegating user.
    """

    def __init__(self, bootstrap_client: BootstrapClient, agent_id: str) -> None:
        self._client = bootstrap_client
        self._agent_id = agent_id
        self._delegations: list[dict] = []
        self._index: int = 0

    async def refresh_delegations(self, discovery_jwt: str) -> None:
        """Fetch the current delegation list from the control plane."""
        async with httpx.AsyncClient() as client:
            resp = await client.get(
                f"{self._client.control_url}/api/v1/auth/agent/delegations",
                headers={"Authorization": f"Bearer {discovery_jwt}"},
                timeout=30.0,
            )
            resp.raise_for_status()
            self._delegations = resp.json()

        logger.info(
            "Loaded %d delegations for agent %s",
            len(self._delegations),
            self._agent_id,
        )
        self._index = 0

    @property
    def current(self) -> Optional[dict]:
        if not self._delegations:
            return None
        return self._delegations[self._index % len(self._delegations)]

    def rotate(self) -> Optional[dict]:
        """Advance to the next delegation and return it."""
        if not self._delegations:
            return None
        self._index = (self._index + 1) % len(self._delegations)
        logger.debug("Rotated to delegation index %d", self._index)
        return self.current

    @property
    def count(self) -> int:
        return len(self._delegations)
