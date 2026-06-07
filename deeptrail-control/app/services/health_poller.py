"""Background health probes independent of the gateway."""

import asyncio
import logging
import time
from datetime import datetime, timezone
from typing import Optional, Tuple

import httpx
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.session import SessionLocal
from app.models.service_registry import ServiceRegistry
from app.services.service_registry_service import ServiceRegistryService

logger = logging.getLogger(__name__)

_SLOW_THRESHOLD_MS = 3000


class HealthPoller:
    """Probe active services and update health when gateway is down or stale."""

    def __init__(self, interval_seconds: Optional[int] = None) -> None:
        self.interval_seconds = interval_seconds or settings.HEALTH_POLLER_INTERVAL_SECONDS
        self._running = False

    async def run_once(self) -> int:
        """Probe all active services once. Returns count of services probed."""
        db = SessionLocal()
        try:
            from app.core.kms import get_kms_client

            svc = ServiceRegistryService(db=db, kms=get_kms_client())
            services = (
                db.query(ServiceRegistry)
                .filter(ServiceRegistry.status == "active")
                .all()
            )
            probed = 0
            for service in services:
                health_status, latency_ms = await self._probe_service(service)
                svc.update_health(
                    service_id=service.service_id,
                    health_status=health_status,
                    latency_ms=latency_ms,
                    probe_source="control_plane",
                )
                probed += 1
            return probed
        finally:
            db.close()

    async def run_loop(self, interval_seconds: Optional[int] = None) -> None:
        """Long-running coroutine that periodically probes services."""
        interval = interval_seconds or self.interval_seconds
        self._running = True
        logger.info("HealthPoller started (interval=%ds)", interval)
        while self._running:
            try:
                count = await self.run_once()
                logger.debug("HealthPoller probed %d services", count)
            except Exception as e:
                logger.error("HealthPoller run_once failed: %s", e)
            await asyncio.sleep(interval)

    def stop(self) -> None:
        """Signal the polling loop to stop."""
        self._running = False

    async def _probe_service(self, service: ServiceRegistry) -> Tuple[str, Optional[int]]:
        """Probe a single service endpoint (REST GET or MCP initialize)."""
        start = time.monotonic()
        endpoint_url = service.endpoint_url
        backend_type = service.backend_type or "rest"
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                if backend_type == "mcp":
                    payload = {
                        "jsonrpc": "2.0",
                        "method": "initialize",
                        "id": 1,
                        "params": {
                            "protocolVersion": service.mcp_protocol_version or "2024-11-05",
                            "capabilities": {},
                            "clientInfo": {"name": "deepsecure-control", "version": "1.0.0"},
                        },
                    }
                    resp = await client.post(
                        endpoint_url,
                        json=payload,
                        headers={"Content-Type": "application/json"},
                    )
                else:
                    resp = await client.get(endpoint_url)

            latency_ms = int((time.monotonic() - start) * 1000)
            if resp.status_code >= 500:
                return "down", latency_ms
            if latency_ms > _SLOW_THRESHOLD_MS:
                return "slow", latency_ms
            return "up", latency_ms
        except httpx.TimeoutException:
            latency_ms = int((time.monotonic() - start) * 1000)
            return "slow", latency_ms
        except Exception as exc:
            logger.debug("Control-plane probe failed for '%s': %s", service.service_id, exc)
            return "down", None
