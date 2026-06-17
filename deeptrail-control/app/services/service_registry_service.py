"""Business logic for the service catalog CRUD and MCP tool discovery.

Handles:
  - Service creation/update/deletion for REST and MCP backends
  - OAuth credential management (encrypted via KMS)
  - MCP tool discovery proxy
  - Internal registry API for gateway consumption
  - Health status updates from gateway
"""

import logging
import time
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import httpx
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.kms import KMSClient
from app.models.gateway_health_state import GatewayHealthState
from app.models.service_registry import ServiceOAuthConfig, ServiceRegistry

logger = logging.getLogger(__name__)


class ServiceRegistryService:
    def __init__(self, db: Session, kms: KMSClient):
        self.db = db
        self.kms = kms

    # --- CRUD ---

    def list_services(
        self,
        status_filter: Optional[str] = None,
        backend_type: Optional[str] = None,
    ) -> List[ServiceRegistry]:
        q = self.db.query(ServiceRegistry)
        if status_filter:
            q = q.filter(ServiceRegistry.status == status_filter)
        if backend_type:
            q = q.filter(ServiceRegistry.backend_type == backend_type)
        return q.order_by(ServiceRegistry.display_name).all()

    def get_service(self, service_id: str) -> Optional[ServiceRegistry]:
        return (
            self.db.query(ServiceRegistry)
            .filter(ServiceRegistry.service_id == service_id)
            .first()
        )

    def create_service(self, data: Dict[str, Any]) -> ServiceRegistry:
        raw_auth_value = data.pop("mcp_auth_value", None)

        service = ServiceRegistry(**data)

        if raw_auth_value and self.kms.backend != "none":
            service.mcp_auth_value_encrypted = self.kms.encrypt(raw_auth_value)

        self.db.add(service)
        self.db.commit()
        self.db.refresh(service)
        return service

    def update_service(self, service_id: str, updates: Dict[str, Any]) -> Optional[ServiceRegistry]:
        service = self.get_service(service_id)
        if not service:
            return None

        raw_auth_value = updates.pop("mcp_auth_value", None)
        if raw_auth_value and self.kms.backend != "none":
            updates["mcp_auth_value_encrypted"] = self.kms.encrypt(raw_auth_value)

        for key, value in updates.items():
            if hasattr(service, key):
                setattr(service, key, value)

        service.updated_at = datetime.now(timezone.utc)
        self.db.commit()
        self.db.refresh(service)
        return service

    def delete_service(self, service_id: str) -> bool:
        service = self.get_service(service_id)
        if not service:
            return False
        self.db.delete(service)
        self.db.commit()
        return True

    # --- OAuth Config ---

    def get_oauth_config(self, service_id: str) -> Optional[ServiceOAuthConfig]:
        return (
            self.db.query(ServiceOAuthConfig)
            .filter(ServiceOAuthConfig.service_id == service_id)
            .first()
        )

    def set_oauth_config(
        self,
        service_id: str,
        client_id: str,
        client_secret: str,
        auth_url: Optional[str] = None,
        token_url: Optional[str] = None,
        scopes: Optional[List[str]] = None,
    ) -> ServiceOAuthConfig:
        service = self.get_service(service_id)
        if not service:
            raise ValueError(f"Service '{service_id}' not found")

        encrypted_secret = self.kms.encrypt(client_secret)

        existing = self.get_oauth_config(service_id)
        if existing:
            existing.client_id = client_id
            existing.client_secret_encrypted = encrypted_secret
            existing.auth_url = auth_url
            existing.token_url = token_url
            existing.scopes = scopes
            existing.updated_at = datetime.now(timezone.utc)
            self.db.commit()
            self.db.refresh(existing)
            return existing

        config = ServiceOAuthConfig(
            service_id=service_id,
            client_id=client_id,
            client_secret_encrypted=encrypted_secret,
            auth_url=auth_url,
            token_url=token_url,
            scopes=scopes,
        )
        self.db.add(config)
        self.db.commit()
        self.db.refresh(config)
        return config

    # --- Connection Test ---

    def test_connection(self, service_id: str) -> Dict[str, Any]:
        service = self.get_service(service_id)
        if not service:
            raise ValueError(f"Service '{service_id}' not found")

        url = service.endpoint_url
        is_mcp = service.backend_type == "mcp"
        start = time.monotonic()

        try:
            with httpx.Client(timeout=10.0) as client:
                if is_mcp:
                    resp = client.post(
                        url,
                        json=self._mcp_initialize_payload(),
                        headers=self._mcp_probe_headers(service),
                    )
                else:
                    probe_url, probe_headers = self._rest_probe_config(service)
                    resp = client.get(probe_url, headers=probe_headers)

            latency_ms = int((time.monotonic() - start) * 1000)
            status_code = resp.status_code

            mcp_info = self._extract_mcp_info(resp) if is_mcp and status_code == 200 else {}
            message = self._connection_message(status_code, is_mcp, latency_ms, mcp_info)

            reachable = status_code < 500
            service.health_latency_ms = latency_ms
            service.health_last_checked_at = datetime.now(timezone.utc)
            service.health_status = "healthy" if reachable else "down"
            self.db.commit()

            result: Dict[str, Any] = {
                "service_id": service_id,
                "status": "success" if reachable else "error",
                "backend_type": service.backend_type,
                "endpoint_url": url,
                "latency_ms": latency_ms,
                "message": message,
            }
            if mcp_info:
                result["mcp_server_info"] = mcp_info
            return result

        except httpx.ConnectError:
            latency_ms = int((time.monotonic() - start) * 1000)
            service.health_status = "down"
            service.health_last_checked_at = datetime.now(timezone.utc)
            self.db.commit()
            return {
                "service_id": service_id,
                "status": "error",
                "backend_type": service.backend_type,
                "endpoint_url": url,
                "message": "Connection refused — server may be down or URL incorrect",
            }
        except httpx.TimeoutException:
            service.health_status = "slow"
            service.health_last_checked_at = datetime.now(timezone.utc)
            self.db.commit()
            return {
                "service_id": service_id,
                "status": "error",
                "backend_type": service.backend_type,
                "endpoint_url": url,
                "message": "Timed out after 10s — check network/firewall",
            }
        except Exception as exc:
            logger.warning("Connection test failed for %s: %s", service_id, exc)
            return {
                "service_id": service_id,
                "status": "error",
                "backend_type": service.backend_type,
                "endpoint_url": url,
                "message": f"Connection test failed — {exc}",
            }

    @staticmethod
    def _mcp_initialize_payload() -> Dict[str, Any]:
        return {
            "jsonrpc": "2.0",
            "method": "initialize",
            "id": 1,
            "params": {
                "protocolVersion": "2024-11-05",
                "capabilities": {},
                "clientInfo": {"name": "deepsecure-test", "version": "1.0.0"},
            },
        }

    @staticmethod
    def _rest_probe_config(service: "ServiceRegistry") -> tuple:
        """Return (probe_url, headers) tailored to the service's API.

        Uses a lightweight endpoint and required headers per provider so the
        health probe gets a meaningful response instead of a generic 400.
        """
        url = service.endpoint_url.rstrip("/")
        sid = (service.service_id or "").lower()
        headers: Dict[str, str] = {}

        if "notion" in sid or "notion.com" in url:
            headers["Notion-Version"] = "2022-06-28"
            return f"{url}/users/me", headers

        if "slack" in sid or "slack.com" in url:
            return f"{url}/api.test", headers

        if "github" in sid or "github.com" in url or "api.github.com" in url:
            headers["Accept"] = "application/vnd.github+json"
            headers["User-Agent"] = "DeepSecure-HealthProbe/1.0"
            return url, headers

        if "gmail" in sid or "gmail.googleapis.com" in url:
            return f"{url}/gmail/v1/users/me/profile", headers

        if "gcalendar" in sid or "googleapis.com/calendar" in url:
            return f"{url}/calendars/primary", headers

        if "gdrive" in sid or "googleapis.com/drive" in url:
            return f"{url}/about?fields=user", headers

        return url, headers

    def _mcp_probe_headers(self, service: "ServiceRegistry") -> Dict[str, str]:
        headers: Dict[str, str] = {"Content-Type": "application/json"}
        if (
            service.mcp_auth_method
            and service.mcp_auth_method != "none"
            and service.mcp_auth_header
            and service.mcp_auth_value_encrypted
        ):
            try:
                if self.kms.backend != "none":
                    decrypted = self.kms.decrypt(service.mcp_auth_value_encrypted)
                    headers[service.mcp_auth_header] = decrypted
            except Exception:
                logger.debug("Skipping MCP auth header for test — decryption unavailable")
        return headers

    @staticmethod
    def _extract_mcp_info(resp: httpx.Response) -> Dict[str, Any]:
        """Pull protocol version, capabilities, and serverInfo from a JSON-RPC response."""
        try:
            body = resp.json()
        except Exception:
            return {}
        result = body.get("result", {})
        if not isinstance(result, dict):
            return {}
        info: Dict[str, Any] = {}
        if "protocolVersion" in result:
            info["protocol_version"] = result["protocolVersion"]
        if "capabilities" in result:
            info["capabilities"] = result["capabilities"]
        if "serverInfo" in result:
            info["server_info"] = result["serverInfo"]
        return info

    @staticmethod
    def _connection_message(
        status_code: int,
        is_mcp: bool,
        latency_ms: int,
        mcp_info: Dict[str, Any],
    ) -> str:
        if status_code == 200:
            if is_mcp:
                version = mcp_info.get("protocol_version", "unknown")
                return f"Healthy — MCP server responding, protocol version: {version}"
            return "Healthy — API responding"
        if status_code in (401, 403):
            if is_mcp:
                return "Auth required — check MCP credentials in service config"
            return (
                "Reachable — authentication required "
                "(expected for OAuth services, employees authorize individually)"
            )
        if status_code == 400:
            if is_mcp:
                return "Bad request — MCP server may expect a different payload format"
            return "Reachable — API responded (HTTP 400 is normal for base URL without a resource path)"
        if status_code == 404:
            if is_mcp:
                return "Endpoint not found — verify MCP server URL"
            return "Endpoint not found — verify URL"
        if 400 <= status_code < 500:
            return f"Reachable — API responded with HTTP {status_code}"
        if 500 <= status_code < 600:
            if is_mcp:
                return "Server error — MCP server may be down"
            return "Server error — backend may be down"
        return f"Unexpected response — HTTP {status_code} in {latency_ms}ms"

    # --- Internal API (for Gateway) ---

    def get_registry_for_gateway(self) -> List[Dict[str, Any]]:
        """Return active/sandbox services with decrypted credentials for gateway internal API."""
        services = (
            self.db.query(ServiceRegistry)
            .filter(ServiceRegistry.status.in_(["active", "sandbox"]))
            .all()
        )
        result = []
        for s in services:
            entry: Dict[str, Any] = {
                "service_id": s.service_id,
                "display_name": s.display_name,
                "backend_type": s.backend_type,
                "endpoint_url": s.endpoint_url,
                "transport": s.transport,
                "mcp_auth_method": s.mcp_auth_method,
                "mcp_auth_header": s.mcp_auth_header,
                "mcp_protocol_version": s.mcp_protocol_version,
                "discovered_tools": s.discovered_tools,
                "permission_map": s.permission_map,
            }
            if s.mcp_auth_value_encrypted and self.kms.backend != "none":
                entry["mcp_auth_value"] = self.kms.decrypt(s.mcp_auth_value_encrypted)
            result.append(entry)
        return result

    # --- Health Updates (from Gateway) ---

    def update_health(
        self,
        service_id: str,
        health_status: str,
        latency_ms: Optional[int] = None,
        error_count_24h: Optional[int] = None,
        probe_source: str = "gateway",
    ) -> Optional[ServiceRegistry]:
        service = self.get_service(service_id)
        if not service:
            return None

        service.health_status = health_status
        service.health_last_checked_at = datetime.now(timezone.utc)
        service.health_probe_source = probe_source
        if latency_ms is not None:
            service.health_latency_ms = latency_ms
        if error_count_24h is not None:
            service.health_error_count_24h = error_count_24h
        self.db.commit()
        self.db.refresh(service)
        return service

    # --- Gateway Liveness ---

    def record_gateway_heartbeat(
        self,
        instance_id: Optional[str] = None,
        reported_at: Optional[datetime] = None,
    ) -> GatewayHealthState:
        """Update singleton gateway heartbeat timestamp."""
        now = reported_at or datetime.now(timezone.utc)
        state = self.db.query(GatewayHealthState).first()
        if state is None:
            state = GatewayHealthState(
                gateway_last_seen_at=now,
                gateway_instance_id=instance_id,
            )
            self.db.add(state)
        else:
            state.gateway_last_seen_at = now
            if instance_id:
                state.gateway_instance_id = instance_id
            state.updated_at = now
        self.db.commit()
        self.db.refresh(state)
        return state

    def _resolve_gateway_status(self) -> tuple[str, Optional[datetime]]:
        """Return (gateway_status, gateway_last_seen_at).

        Distinguishes between:
        - "up": heartbeat is fresh (within stale threshold)
        - "sleeping": heartbeat is stale but within 30 min — likely Cloud Run
          scale-to-zero, not a crash. Gateway will wake on next request.
        - "down": heartbeat is stale beyond 30 min — likely a real outage
        - "unknown": no heartbeat has ever been recorded
        """
        SLEEPING_WINDOW_SECONDS = 1800  # 30 min

        state = self.db.query(GatewayHealthState).first()
        if state is None or state.gateway_last_seen_at is None:
            return "unknown", None

        last_seen = state.gateway_last_seen_at
        if last_seen.tzinfo is None:
            last_seen = last_seen.replace(tzinfo=timezone.utc)

        age_seconds = (datetime.now(timezone.utc) - last_seen).total_seconds()
        if age_seconds <= settings.GATEWAY_STALE_THRESHOLD_SECONDS:
            return "up", state.gateway_last_seen_at
        if age_seconds <= SLEEPING_WINDOW_SECONDS:
            return "sleeping", state.gateway_last_seen_at
        return "down", state.gateway_last_seen_at

    def _effective_service_status(
        self,
        raw_status: str,
        last_checked: Optional[datetime],
    ) -> str:
        """Mark service stale when last check exceeds threshold."""
        if last_checked is None:
            return raw_status if raw_status != "unknown" else "unknown"

        checked = last_checked
        if checked.tzinfo is None:
            checked = checked.replace(tzinfo=timezone.utc)

        age_seconds = (datetime.now(timezone.utc) - checked).total_seconds()
        if age_seconds > settings.SERVICE_HEALTH_STALE_THRESHOLD_SECONDS:
            return "stale"
        return raw_status

    # --- Health Aggregation ---

    def get_health_summary(self) -> Dict[str, Any]:
        services = self.db.query(ServiceRegistry).filter(
            ServiceRegistry.status.in_(["active", "sandbox"])
        ).all()

        gateway_status, gateway_last_seen = self._resolve_gateway_status()

        summary: Dict[str, Any] = {
            "gateway_status": gateway_status,
            "gateway_last_seen_at": (
                gateway_last_seen.isoformat() if gateway_last_seen else None
            ),
            "gateway_stale_threshold_seconds": settings.GATEWAY_STALE_THRESHOLD_SECONDS,
            "total": len(services),
            "up": 0,
            "healthy": 0,
            "down": 0,
            "slow": 0,
            "unknown": 0,
            "stale": 0,
            "services": [],
        }
        for s in services:
            raw_status = s.health_status or "unknown"
            effective_status = self._effective_service_status(
                raw_status, s.health_last_checked_at
            )
            summary[effective_status] = summary.get(effective_status, 0) + 1
            summary["services"].append({
                "service_id": s.service_id,
                "display_name": s.display_name,
                "backend_type": s.backend_type or "rest",
                "health_status": effective_status,
                "probe_source": s.health_probe_source,
                "latency_ms": s.health_latency_ms,
                "error_count_24h": s.health_error_count_24h or 0,
                "last_checked": (
                    s.health_last_checked_at.isoformat()
                    if s.health_last_checked_at
                    else None
                ),
            })
        return summary
