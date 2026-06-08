"""Stdio MCP proxy: reads JSON-RPC from stdin, forwards to gateway via HTTP."""

from __future__ import annotations

import asyncio
import json
import logging
import sys
from typing import Optional

import httpx

from deepsecure._core.bootstrap import BootstrapClient

from .delegation_rotator import DelegationRotator
from .jwt_manager import JWTManager

logger = logging.getLogger(__name__)


class DeepSecureProxy:
    """Stdio-to-HTTP MCP proxy with transparent JWT refresh.

    Reads newline-delimited JSON-RPC messages from stdin, adds a valid
    Bearer token, forwards to the DeepSecure MCP gateway over HTTP, and
    writes the response to stdout.

    Features:
    - Automatic JWT refresh before expiry (default 5 min margin)
    - Optional round-robin delegation rotation
    - 401 retry with re-bootstrap
    """

    def __init__(
        self,
        agent_id: str,
        control_url: str,
        gateway_url: str,
        platform: str = "auto",
        round_robin: bool = False,
        delegation_id: Optional[str] = None,
        refresh_margin: int = 300,
    ) -> None:
        self._gateway_url = gateway_url.rstrip("/")
        self._round_robin = round_robin
        self._fixed_delegation_id = delegation_id

        bootstrap = BootstrapClient(control_url=control_url, gateway_url=gateway_url)
        self._jwt_mgr = JWTManager(bootstrap, agent_id, platform, refresh_margin)
        self._rotator = (
            DelegationRotator(bootstrap, agent_id) if round_robin else None
        )

    async def run(self) -> None:
        """Main event loop: stdin → forward → stdout."""
        reader = asyncio.StreamReader()
        protocol = asyncio.StreamReaderProtocol(reader)
        await asyncio.get_event_loop().connect_read_pipe(lambda: protocol, sys.stdin.buffer)

        discovery = await self._jwt_mgr.ensure_discovery_jwt()
        if self._rotator:
            await self._rotator.refresh_delegations(discovery)

        logger.info("Proxy started — reading from stdin")

        while True:
            line = await reader.readline()
            if not line:
                break
            try:
                request = json.loads(line)
            except json.JSONDecodeError:
                logger.warning("Ignoring non-JSON line from stdin")
                continue

            response = await self._forward(request)
            sys.stdout.write(json.dumps(response) + "\n")
            sys.stdout.flush()

    async def _forward(self, request: dict) -> dict:
        """Forward a single JSON-RPC request to the gateway."""
        jwt = await self._get_current_jwt()

        async with httpx.AsyncClient() as client:
            resp = await client.post(
                f"{self._gateway_url}/mcp",
                json=request,
                headers={
                    "Authorization": f"Bearer {jwt}",
                    "Content-Type": "application/json",
                    "Accept": "application/json, text/event-stream",
                },
                timeout=60.0,
            )

            if resp.status_code == 401:
                logger.info("Got 401 — refreshing JWT and retrying")
                self._jwt_mgr.invalidate()
                jwt = await self._get_current_jwt()
                resp = await client.post(
                    f"{self._gateway_url}/mcp",
                    json=request,
                    headers={
                        "Authorization": f"Bearer {jwt}",
                        "Content-Type": "application/json",
                    },
                    timeout=60.0,
                )

            return resp.json()

    async def _get_current_jwt(self) -> str:
        """Resolve the appropriate JWT for the current request."""
        if self._fixed_delegation_id:
            return await self._jwt_mgr.get_delegation_jwt(self._fixed_delegation_id)

        if self._rotator and self._rotator.current:
            delegation = self._rotator.current
            return await self._jwt_mgr.get_delegation_jwt(delegation["delegation_id"])

        return await self._jwt_mgr.ensure_discovery_jwt()
