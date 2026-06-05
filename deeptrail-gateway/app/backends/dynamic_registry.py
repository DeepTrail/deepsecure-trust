"""
Dynamic Backend Loader

Fetches the service registry from the Control Plane and manages backend
lifecycle in the gateway. On startup, it loads all active services and
instantiates the appropriate client type (DirectClient for REST, or
GenericMCPClient via BackendConnectionManager for MCP). A periodic refresh
loop adds new backends, removes deactivated ones, and updates tool caches.

Usage:
    loader = DynamicBackendLoader(
        adapter=backend_adapter,
        connection_manager=conn_mgr,
        tool_cache=tool_cache,
        control_plane_url="http://localhost:8000",
        internal_api_token="gateway-internal-secret-token",
    )
    await loader.initial_load()
    # Start periodic refresh as a background task
    asyncio.create_task(loader.run_refresh_loop())
"""

import asyncio
import logging
import time
from dataclasses import dataclass
from typing import Any

import httpx

from app.mcp.handlers.tools_call import drain_error_counts
from app.mcp.tool_cache import CachedTool, ToolCache

from .adapter import BackendClientAdapter
from .connection_manager import BackendConfig, BackendConnectionManager

logger = logging.getLogger(__name__)


# Known DirectClient classes keyed by service_id.  The dynamic loader
# uses this map to decide whether a REST service can be handled by a
# specialised DirectClient instead of the generic MCP path.
_DIRECT_CLIENT_MAP: dict[str, tuple[str, str]] = {
    "notion": ("app.backends.notion_client", "NotionDirectClient"),
    "slack": ("app.backends.slack_client", "SlackDirectClient"),
    "hubspot": ("app.backends.hubspot_client", "HubSpotDirectClient"),
    "gdrive": ("app.backends.gdrive_client", "GDriveDirectClient"),
    "gcalendar": ("app.backends.gcalendar_client", "GCalendarDirectClient"),
    "gmail": ("app.backends.gmail_client", "GmailDirectClient"),
}


@dataclass
class ServiceConfig:
    """Represents a service entry returned by the Control Plane registry API."""

    service_id: str
    display_name: str
    backend_type: str  # "rest" or "mcp"
    endpoint_url: str
    status: str = "active"
    transport: str = "rest"
    mcp_auth_method: str = "none"
    mcp_auth_header: str | None = None
    mcp_auth_value_decrypted: str | None = None
    mcp_protocol_version: str = "2024-11-05"
    discovered_tools: list[dict[str, Any]] | None = None
    permission_map: dict[str, str] | None = None
    health_status: str = "unknown"

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ServiceConfig":
        return cls(
            service_id=data["service_id"],
            display_name=data.get("display_name", data["service_id"]),
            backend_type=data.get("backend_type", "rest"),
            endpoint_url=data.get("endpoint_url", ""),
            status=data.get("status", "active"),
            transport=data.get("transport", "rest"),
            mcp_auth_method=data.get("mcp_auth_method", "none"),
            mcp_auth_header=data.get("mcp_auth_header"),
            mcp_auth_value_decrypted=data.get("mcp_auth_value_decrypted"),
            mcp_protocol_version=data.get("mcp_protocol_version", "2024-11-05"),
            discovered_tools=data.get("discovered_tools"),
            permission_map=data.get("permission_map"),
            health_status=data.get("health_status", "unknown"),
        )


class DynamicBackendLoader:
    """Fetches service registry from Control Plane and manages backend lifecycle.

    On startup: fetches registry, instantiates DirectClient (REST) or
    GenericMCPClient (MCP) for each active service.
    Periodic refresh: adds new backends, removes deactivated ones, updates configs.
    """

    def __init__(
        self,
        adapter: BackendClientAdapter,
        connection_manager: BackendConnectionManager,
        tool_cache: ToolCache,
        control_plane_url: str,
        internal_api_token: str,
        refresh_interval_seconds: int = 60,
    ):
        self.adapter = adapter
        self.connection_manager = connection_manager
        self.tool_cache = tool_cache
        self.control_plane_url = control_plane_url.rstrip("/")
        self.internal_api_token = internal_api_token
        self.refresh_interval = refresh_interval_seconds
        self._known_services: dict[str, ServiceConfig] = {}
        self._running = False
        self._error_counts: dict[str, int] = {}
        self._slow_threshold_ms = 3000

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def initial_load(self) -> int:
        """Fetch registry and instantiate all active backends.

        Returns the number of dynamically registered backends.
        """
        logger.info("Registry loading from: %s/api/v1/internal/services/registry", self.control_plane_url)
        try:
            services = await self._fetch_registry()
        except Exception as e:
            logger.warning("Registry initial load failed (will rely on hardcoded backends): %s", e)
            return 0

        registered = 0
        for svc in services:
            if self._register_service(svc):
                registered += 1

        logger.info(
            "Dynamic registry loaded: %d services registered (%d already existed)",
            registered,
            len(services) - registered,
        )
        return registered

    async def periodic_refresh(self) -> None:
        """Compare registry with current state, add/remove as needed."""
        try:
            services = await self._fetch_registry()
        except Exception as e:
            logger.error("Registry refresh failed: %s", e)
            return

        current_ids = set(self._known_services.keys())
        new_ids = {s.service_id for s in services}

        for svc in services:
            if svc.service_id not in current_ids:
                self._register_service(svc)
                logger.info("Dynamic registry: added backend '%s'", svc.service_id)

        for removed_id in current_ids - new_ids:
            self._unregister_service(removed_id)
            logger.info("Dynamic registry: removed backend '%s'", removed_id)

    async def run_refresh_loop(self) -> None:
        """Long-running coroutine that periodically refreshes the registry."""
        self._running = True
        while self._running:
            await asyncio.sleep(self.refresh_interval)
            try:
                await self.periodic_refresh()
            except Exception as e:
                logger.error("Unexpected error in registry refresh loop: %s", e)

    def stop(self) -> None:
        """Signal the refresh loop to stop."""
        self._running = False

    # ------------------------------------------------------------------
    # Health reporting
    # ------------------------------------------------------------------

    async def report_health(self) -> None:
        """Probe all known backends and report health to Control Plane."""
        tool_call_errors = drain_error_counts()
        for service_id, count in tool_call_errors.items():
            self._error_counts[service_id] = self._error_counts.get(service_id, 0) + count

        for service_id, svc in list(self._known_services.items()):
            health_status, latency_ms = await self._probe_backend_health(
                service_id, svc.endpoint_url, svc.backend_type,
            )
            error_count = self._error_counts.pop(service_id, 0)
            await self._post_health(service_id, health_status, latency_ms, error_count)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _register_service(self, service: ServiceConfig) -> bool:
        """Instantiate the correct client type based on backend_type.

        Returns True if a new backend was registered, False if it already existed.
        """
        if service.service_id in self._known_services:
            return False

        if service.backend_type == "rest":
            self._instantiate_rest_backend(service)
        elif service.backend_type == "mcp":
            self._instantiate_mcp_backend(service)
        else:
            logger.warning("Unknown backend_type '%s' for service '%s'", service.backend_type, service.service_id)
            return False

        self._known_services[service.service_id] = service
        return True

    def _unregister_service(self, service_id: str) -> None:
        """Remove a backend from the adapter and connection manager."""
        svc = self._known_services.pop(service_id, None)
        if svc is None:
            return

        if svc.backend_type == "mcp":
            self.connection_manager.unregister_backend(service_id)
        self._error_counts.pop(service_id, None)
        self.tool_cache.invalidate(service_id)

    def _instantiate_rest_backend(self, service: ServiceConfig) -> None:
        """Register a DirectClient for a REST+OAuth service.

        Only works for services with built-in DirectClient classes.
        Falls back to registering via BackendConnectionManager if no
        specialised DirectClient exists.
        """
        if service.service_id in _DIRECT_CLIENT_MAP:
            # Already registered by the hardcoded create_backend_adapter()
            if service.service_id in self.adapter.registered_backends:
                return
            module_path, class_name = _DIRECT_CLIENT_MAP[service.service_id]
            try:
                from importlib import import_module

                mod = import_module(module_path)
                client_cls = getattr(mod, class_name)
                client = client_cls()
                self.adapter.register_client(service.service_id, client)
            except Exception as e:
                logger.error("Failed to instantiate DirectClient for '%s': %s", service.service_id, e)
        else:
            config = BackendConfig(
                backend_id=service.service_id,
                base_url=service.endpoint_url,
            )
            self.connection_manager.register_backend(config)

    def _instantiate_mcp_backend(self, service: ServiceConfig) -> None:
        """Register a GenericMCPClient via BackendConnectionManager."""
        config = BackendConfig(
            backend_id=service.service_id,
            base_url=service.endpoint_url,
        )
        self.connection_manager.register_backend(config)

        if service.discovered_tools:
            tools = [CachedTool(**t) for t in service.discovered_tools]
            self.tool_cache.set_tools(service.service_id, tools)

    async def _fetch_registry(self) -> list[ServiceConfig]:
        """GET /api/v1/internal/services/registry from Control Plane."""
        url = f"{self.control_plane_url}/api/v1/internal/services/registry"
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.get(
                url,
                headers={"X-Internal-API-Token": self.internal_api_token},
            )
            resp.raise_for_status()
            data = resp.json()
            services_raw = data.get("services", data if isinstance(data, list) else [])
            return [ServiceConfig.from_dict(s) for s in services_raw]

    async def _probe_backend_health(
        self,
        service_id: str,
        endpoint_url: str,
        backend_type: str,
    ) -> tuple[str, int | None]:
        """Probe a single backend and return (health_status, latency_ms).

        REST backends get an HTTP GET; MCP backends get a JSON-RPC
        ``initialize`` POST.  A 5-second timeout is used for probes.
        """
        start = time.monotonic()
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                if backend_type == "mcp":
                    payload = {
                        "jsonrpc": "2.0",
                        "method": "initialize",
                        "id": 1,
                        "params": {
                            "protocolVersion": "2024-11-05",
                            "capabilities": {},
                            "clientInfo": {"name": "deepsecure-gateway", "version": "1.0.0"},
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
                self._error_counts[service_id] = self._error_counts.get(service_id, 0) + 1
                return "down", latency_ms

            self._error_counts.pop(service_id, None)
            if latency_ms > self._slow_threshold_ms:
                return "slow", latency_ms
            return "healthy", latency_ms

        except httpx.TimeoutException:
            latency_ms = int((time.monotonic() - start) * 1000)
            self._error_counts[service_id] = self._error_counts.get(service_id, 0) + 1
            return "slow", latency_ms
        except Exception as exc:
            logger.debug("Health probe failed for '%s': %s", service_id, exc)
            self._error_counts[service_id] = self._error_counts.get(service_id, 0) + 1
            return "down", None

    async def _post_health(
        self,
        service_id: str,
        health_status: str,
        latency_ms: int | None,
        error_count: int = 0,
    ) -> None:
        """POST health data to Control Plane."""
        url = f"{self.control_plane_url}/api/v1/internal/services/{service_id}/health"
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                await client.post(
                    url,
                    headers={"X-Internal-API-Token": self.internal_api_token},
                    json={
                        "health_status": health_status,
                        "latency_ms": latency_ms,
                        "error_count_24h": error_count,
                    },
                )
        except Exception as e:
            logger.debug("Failed to post health for '%s': %s", service_id, e)

    @property
    def known_service_ids(self) -> list[str]:
        """Return list of dynamically registered service IDs."""
        return list(self._known_services.keys())
