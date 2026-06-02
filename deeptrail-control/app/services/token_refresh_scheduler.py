"""Event-driven OAuth token refresh scheduler.

Provides a pluggable scheduler that proactively refreshes OAuth tokens
before they expire. Hooks into VaultClient.store_token() and
VaultClient.refresh_token() to schedule refreshes automatically.

Environment backends:
- LocalScheduler: in-process asyncio timers (local/dev)
- CloudTasksScheduler: GCP Cloud Tasks (production)
- EventBridgeScheduler: AWS EventBridge (future)

The backend is selected via TOKEN_REFRESH_BACKEND env var.
"""

import asyncio
import hashlib
import logging
import os
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Dict, Optional

logger = logging.getLogger(__name__)

REFRESH_BUFFER_SECONDS = 600  # Schedule refresh 10 min before expiry
MIN_DELAY_SECONDS = 60  # Never schedule sooner than 60s from now


@dataclass
class RefreshMetrics:
    """In-memory counters for token refresh observability."""

    scheduled_count: int = 0
    success_count: int = 0
    failure_count: int = 0
    cancel_count: int = 0
    total_latency_ms: float = 0.0

    @property
    def avg_latency_ms(self) -> float:
        if self.success_count == 0:
            return 0.0
        return self.total_latency_ms / self.success_count

    def to_dict(self) -> dict:
        return {
            "scheduled_count": self.scheduled_count,
            "success_count": self.success_count,
            "failure_count": self.failure_count,
            "cancel_count": self.cancel_count,
            "avg_latency_ms": round(self.avg_latency_ms, 2),
        }


class TokenRefreshScheduler(ABC):
    """Abstract base class for token refresh scheduling."""

    def __init__(self) -> None:
        self.metrics = RefreshMetrics()

    @abstractmethod
    def schedule_refresh(
        self,
        token_ref: str,
        service_id: str,
        user_id: str,
        refresh_at: datetime,
    ) -> None:
        """Schedule a token refresh at the given time.

        If a refresh is already scheduled for this token_ref, the old
        one is cancelled and replaced.

        Args:
            token_ref: Vault reference (e.g., "vault://sarah-notion-abc123")
            service_id: Service identifier (e.g., "notion")
            user_id: Owner's email (e.g., "sarah@acme.com")
            refresh_at: When to trigger the refresh (UTC)
        """

    @abstractmethod
    def cancel_refresh(self, token_ref: str) -> None:
        """Cancel a pending refresh for a token.

        No-op if no refresh is scheduled for this token_ref.
        """

    @abstractmethod
    def shutdown(self) -> None:
        """Cancel all pending refreshes and clean up resources."""

    @property
    def pending_count(self) -> int:
        """Number of refreshes currently scheduled."""
        return 0


class LocalScheduler(TokenRefreshScheduler):
    """In-process asyncio timer-based scheduler for local/dev.

    Each scheduled refresh creates an asyncio.TimerHandle via
    loop.call_later(). Timers are in-memory and lost on process
    restart -- the lifespan recovery sweep re-schedules them.
    """

    def __init__(self, control_plane_url: str = "http://localhost:8001") -> None:
        super().__init__()
        self._timers: Dict[str, asyncio.TimerHandle] = {}
        self._control_plane_url = control_plane_url
        self._internal_api_token = os.getenv(
            "GATEWAY_INTERNAL_API_TOKEN", "gateway-internal-secret-token"
        )

    def schedule_refresh(
        self,
        token_ref: str,
        service_id: str,
        user_id: str,
        refresh_at: datetime,
    ) -> None:
        self.cancel_refresh(token_ref)

        now = datetime.now(timezone.utc)
        delay = max((refresh_at - now).total_seconds(), MIN_DELAY_SECONDS)

        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            logger.debug("No event loop available, skipping schedule for %s", token_ref)
            return

        handle = loop.call_later(
            delay,
            lambda: asyncio.ensure_future(
                self._execute_refresh(token_ref, service_id, user_id)
            ),
        )
        self._timers[token_ref] = handle
        self.metrics.scheduled_count += 1

        logger.info(
            "Scheduled token refresh: service=%s user=%s delay=%.0fs",
            service_id,
            user_id,
            delay,
        )

    def cancel_refresh(self, token_ref: str) -> None:
        handle = self._timers.pop(token_ref, None)
        if handle is not None:
            handle.cancel()
            self.metrics.cancel_count += 1
            logger.debug("Cancelled pending refresh for %s", token_ref)

    def shutdown(self) -> None:
        for token_ref in list(self._timers.keys()):
            self.cancel_refresh(token_ref)
        logger.info("LocalScheduler shut down, all timers cancelled")

    @property
    def pending_count(self) -> int:
        return len(self._timers)

    async def _execute_refresh(
        self, token_ref: str, service_id: str, user_id: str
    ) -> None:
        """Fire the refresh by calling the existing vault refresh endpoint."""
        self._timers.pop(token_ref, None)

        start = time.monotonic()
        try:
            import httpx

            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(
                    f"{self._control_plane_url}/api/v1/vault/tokens/{service_id}/refresh",
                    headers={
                        "Authorization": f"Bearer {self._internal_api_token}",
                        "X-User-ID": user_id,
                    },
                    json={"force": False},
                )

            elapsed_ms = (time.monotonic() - start) * 1000

            if response.status_code == 200:
                self.metrics.success_count += 1
                self.metrics.total_latency_ms += elapsed_ms
                data = response.json()
                logger.info(
                    "Proactive refresh succeeded: service=%s user=%s refreshed=%s latency=%.0fms",
                    service_id,
                    user_id,
                    data.get("refreshed"),
                    elapsed_ms,
                )
            else:
                self.metrics.failure_count += 1
                logger.warning(
                    "Proactive refresh failed: service=%s user=%s status=%d",
                    service_id,
                    user_id,
                    response.status_code,
                )
                self._schedule_retry(token_ref, service_id, user_id)

        except Exception as e:
            self.metrics.failure_count += 1
            logger.error(
                "Proactive refresh error: service=%s user=%s error=%s",
                service_id,
                user_id,
                type(e).__name__,
            )
            self._schedule_retry(token_ref, service_id, user_id)

    def _schedule_retry(
        self, token_ref: str, service_id: str, user_id: str
    ) -> None:
        """Retry once after 60 seconds on failure."""
        if token_ref in self._timers:
            return

        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            return

        handle = loop.call_later(
            60,
            lambda: asyncio.ensure_future(
                self._execute_refresh(token_ref, service_id, user_id)
            ),
        )
        self._timers[token_ref] = handle
        logger.info("Scheduled retry in 60s for service=%s user=%s", service_id, user_id)


class NullScheduler(TokenRefreshScheduler):
    """No-op scheduler for testing or when scheduling is disabled."""

    def schedule_refresh(self, token_ref: str, service_id: str,
                         user_id: str, refresh_at: datetime) -> None:
        pass

    def cancel_refresh(self, token_ref: str) -> None:
        pass

    def shutdown(self) -> None:
        pass


# ---------------------------------------------------------------------------
# Singleton management
# ---------------------------------------------------------------------------

_scheduler: Optional[TokenRefreshScheduler] = None


def get_scheduler() -> TokenRefreshScheduler:
    """Get the singleton scheduler instance.

    Backend selected via TOKEN_REFRESH_BACKEND env var:
    - "local" (default): in-process asyncio timers
    - "cloud_tasks": GCP Cloud Tasks
    - "none": disabled (NullScheduler)
    """
    global _scheduler
    if _scheduler is not None:
        return _scheduler

    backend = os.getenv("TOKEN_REFRESH_BACKEND", "local")

    if backend == "cloud_tasks":
        _scheduler = _create_cloud_tasks_scheduler()
    elif backend == "none":
        _scheduler = NullScheduler()
        logger.info("Token refresh scheduler disabled (backend=none)")
    else:
        port = os.getenv("CONTROL_PLANE_PORT", "8001")
        url = f"http://localhost:{port}"
        _scheduler = LocalScheduler(control_plane_url=url)
        logger.info("Token refresh scheduler: LocalScheduler (url=%s)", url)

    return _scheduler


def _create_cloud_tasks_scheduler() -> TokenRefreshScheduler:
    """Lazy import to avoid requiring google-cloud-tasks in dev."""
    try:
        from app.services.cloud_tasks_scheduler import CloudTasksScheduler
        scheduler = CloudTasksScheduler()
        logger.info("Token refresh scheduler: CloudTasksScheduler")
        return scheduler
    except ImportError:
        logger.warning(
            "google-cloud-tasks not installed, falling back to LocalScheduler"
        )
        return LocalScheduler()


def reset_scheduler() -> None:
    """Reset the singleton (for testing)."""
    global _scheduler
    if _scheduler is not None:
        _scheduler.shutdown()
    _scheduler = None


def compute_refresh_at(expires_in: int) -> datetime:
    """Compute when to schedule a refresh given an expires_in value.

    Schedules REFRESH_BUFFER_SECONDS before expiry, but never sooner
    than MIN_DELAY_SECONDS from now.
    """
    from datetime import timedelta

    delay = max(expires_in - REFRESH_BUFFER_SECONDS, MIN_DELAY_SECONDS)
    return datetime.now(timezone.utc) + timedelta(seconds=delay)
