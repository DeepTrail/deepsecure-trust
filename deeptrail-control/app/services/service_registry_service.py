"""Business logic for the service catalog CRUD and MCP tool discovery.

Handles:
  - Service creation/update/deletion for REST and MCP backends
  - OAuth credential management (encrypted via KMS)
  - MCP tool discovery proxy
  - Internal registry API for gateway consumption
  - Health status updates from gateway
"""

import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from app.core.kms import KMSClient
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

        return {
            "service_id": service_id,
            "status": "ok",
            "backend_type": service.backend_type,
            "endpoint_url": service.endpoint_url,
            "message": "Connection test placeholder — implement HTTP probe in production",
        }

    # --- Internal API (for Gateway) ---

    def get_registry_for_gateway(self) -> List[Dict[str, Any]]:
        """Return active services with decrypted credentials for gateway internal API."""
        services = (
            self.db.query(ServiceRegistry)
            .filter(ServiceRegistry.status == "active")
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
    ) -> Optional[ServiceRegistry]:
        service = self.get_service(service_id)
        if not service:
            return None

        service.health_status = health_status
        service.health_last_checked_at = datetime.now(timezone.utc)
        if latency_ms is not None:
            service.health_latency_ms = latency_ms
        if error_count_24h is not None:
            service.health_error_count_24h = error_count_24h
        self.db.commit()
        self.db.refresh(service)
        return service

    # --- Health Aggregation ---

    def get_health_summary(self) -> Dict[str, Any]:
        services = self.db.query(ServiceRegistry).filter(
            ServiceRegistry.status.in_(["active", "sandbox"])
        ).all()

        summary = {"total": len(services), "up": 0, "down": 0, "slow": 0, "unknown": 0, "services": []}
        for s in services:
            status = s.health_status or "unknown"
            summary[status] = summary.get(status, 0) + 1
            summary["services"].append({
                "service_id": s.service_id,
                "display_name": s.display_name,
                "health_status": status,
                "latency_ms": s.health_latency_ms,
                "error_count_24h": s.health_error_count_24h,
                "last_checked": s.health_last_checked_at.isoformat() if s.health_last_checked_at else None,
            })
        return summary
