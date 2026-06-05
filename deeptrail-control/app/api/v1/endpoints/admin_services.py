"""Admin service catalog endpoints.

Implements:
  GET    /api/v1/admin/services                       — List all services
  POST   /api/v1/admin/services                       — Add service (REST or MCP)
  PATCH  /api/v1/admin/services/{service_id}           — Update service
  DELETE /api/v1/admin/services/{service_id}           — Remove service
  POST   /api/v1/admin/services/{service_id}/test      — Test connection
  GET    /api/v1/admin/services/{service_id}/oauth     — Get OAuth config (redacted)
  PUT    /api/v1/admin/services/{service_id}/oauth     — Set OAuth credentials
  POST   /api/v1/admin/services/{service_id}/discover-tools — MCP tools/list
  GET    /api/v1/admin/health                          — Health aggregation

All endpoints require admin role.
"""

import logging
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.core.kms import get_kms_client, KMSClient
from app.middleware.admin_auth import require_admin
from app.services.service_registry_service import ServiceRegistryService

logger = logging.getLogger(__name__)

router = APIRouter()


# --- Request/Response Models ---

class ServiceCreateRequest(BaseModel):
    service_id: str = Field(..., max_length=50)
    display_name: str = Field(..., max_length=100)
    description: Optional[str] = None
    backend_type: str = Field(default="rest", pattern="^(rest|mcp)$")
    endpoint_url: str = Field(..., max_length=500)
    status: str = Field(default="active", pattern="^(active|sandbox|disable)$")
    transport: str = Field(default="rest")
    mcp_auth_method: str = Field(default="none")
    mcp_auth_header: Optional[str] = None
    mcp_auth_value: Optional[str] = None
    mcp_protocol_version: str = Field(default="2024-11-05")
    data_classification: str = Field(default="internal")
    available_to_roles: List[str] = Field(default=["all"])
    available_to_groups: List[str] = Field(default=[])
    available_to_users: List[str] = Field(default=[])
    requires_approval: bool = False


class ServiceUpdateRequest(BaseModel):
    display_name: Optional[str] = None
    description: Optional[str] = None
    endpoint_url: Optional[str] = None
    transport: Optional[str] = None
    mcp_auth_method: Optional[str] = None
    mcp_auth_header: Optional[str] = None
    mcp_auth_value: Optional[str] = None
    data_classification: Optional[str] = None
    status: Optional[str] = None
    available_to_roles: Optional[List[str]] = None
    available_to_groups: Optional[List[str]] = None
    available_to_users: Optional[List[str]] = None
    requires_approval: Optional[bool] = None


class ServiceResponse(BaseModel):
    service_id: str
    display_name: str
    description: Optional[str] = None
    backend_type: str
    endpoint_url: str
    transport: str
    status: str
    health_status: str
    data_classification: str
    mcp_auth_method: Optional[str] = None
    mcp_auth_configured: bool = False
    discovered_tools_count: int = 0
    permission_map: Optional[Dict[str, str]] = None
    available_to_roles: Optional[List[str]] = None
    available_to_groups: Optional[List[str]] = None
    available_to_users: Optional[List[str]] = None
    requires_approval: bool = False

    model_config = {"from_attributes": True}


class OAuthConfigRequest(BaseModel):
    client_id: str
    client_secret: str
    auth_url: Optional[str] = None
    token_url: Optional[str] = None
    scopes: Optional[List[str]] = None


class OAuthConfigResponse(BaseModel):
    service_id: str
    client_id: str
    client_secret_configured: bool = True
    auth_url: Optional[str] = None
    token_url: Optional[str] = None
    scopes: Optional[List[str]] = None
    source: str = "db"  # "db" = per-service config, "env" = centralized env vars


class ConnectionTestResponse(BaseModel):
    service_id: str
    status: str
    backend_type: str
    endpoint_url: str
    message: str
    latency_ms: Optional[int] = None
    mcp_server_info: Optional[Dict[str, Any]] = None


class HealthSummaryResponse(BaseModel):
    total: int
    up: int
    down: int
    slow: int
    unknown: int
    services: List[Dict[str, Any]]


# --- Dependency ---

def get_service(db: Session = Depends(get_db)) -> ServiceRegistryService:
    return ServiceRegistryService(db=db, kms=get_kms_client())


# --- Endpoints ---

@router.get("/services", response_model=List[ServiceResponse])
def list_services(
    status_filter: Optional[str] = None,
    backend_type: Optional[str] = None,
    svc: ServiceRegistryService = Depends(get_service),
    _admin: dict = Depends(require_admin),
):
    services = svc.list_services(status_filter=status_filter, backend_type=backend_type)
    return [
        ServiceResponse(
            service_id=s.service_id,
            display_name=s.display_name,
            description=s.description,
            backend_type=s.backend_type,
            endpoint_url=s.endpoint_url,
            transport=s.transport or "rest",
            status=s.status or "sandbox",
            health_status=s.health_status or "unknown",
            data_classification=s.data_classification or "internal",
            mcp_auth_method=s.mcp_auth_method,
            mcp_auth_configured=bool(s.mcp_auth_value_encrypted),
            discovered_tools_count=len(s.discovered_tools) if s.discovered_tools else 0,
            permission_map=s.permission_map,
            available_to_roles=s.available_to_roles,
            available_to_groups=s.available_to_groups or [],
            available_to_users=s.available_to_users or [],
            requires_approval=s.requires_approval or False,
        )
        for s in services
    ]


@router.post("/services", response_model=ServiceResponse, status_code=status.HTTP_201_CREATED)
def create_service(
    body: ServiceCreateRequest,
    svc: ServiceRegistryService = Depends(get_service),
    _admin: dict = Depends(require_admin),
):
    existing = svc.get_service(body.service_id)
    if existing:
        raise HTTPException(status_code=409, detail=f"Service '{body.service_id}' already exists")

    data = body.model_dump()
    service = svc.create_service(data)
    return ServiceResponse(
        service_id=service.service_id,
        display_name=service.display_name,
        description=service.description,
        backend_type=service.backend_type,
        endpoint_url=service.endpoint_url,
        transport=service.transport or "rest",
        status=service.status or "sandbox",
        health_status=service.health_status or "unknown",
        data_classification=service.data_classification or "internal",
        mcp_auth_configured=bool(service.mcp_auth_value_encrypted),
        available_to_roles=service.available_to_roles,
        available_to_groups=service.available_to_groups or [],
        available_to_users=service.available_to_users or [],
        requires_approval=service.requires_approval or False,
    )


@router.patch("/services/{service_id}", response_model=ServiceResponse)
def update_service(
    service_id: str,
    body: ServiceUpdateRequest,
    svc: ServiceRegistryService = Depends(get_service),
    _admin: dict = Depends(require_admin),
):
    updates = body.model_dump(exclude_none=True)
    if not updates:
        raise HTTPException(status_code=400, detail="No fields to update")

    service = svc.update_service(service_id, updates)
    if not service:
        raise HTTPException(status_code=404, detail=f"Service '{service_id}' not found")

    return ServiceResponse(
        service_id=service.service_id,
        display_name=service.display_name,
        description=service.description,
        backend_type=service.backend_type,
        endpoint_url=service.endpoint_url,
        transport=service.transport or "rest",
        status=service.status or "sandbox",
        health_status=service.health_status or "unknown",
        data_classification=service.data_classification or "internal",
        mcp_auth_configured=bool(service.mcp_auth_value_encrypted),
        available_to_roles=service.available_to_roles,
        available_to_groups=service.available_to_groups or [],
        available_to_users=service.available_to_users or [],
        requires_approval=service.requires_approval or False,
    )


@router.delete("/services/{service_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_service(
    service_id: str,
    svc: ServiceRegistryService = Depends(get_service),
    _admin: dict = Depends(require_admin),
):
    if not svc.delete_service(service_id):
        raise HTTPException(status_code=404, detail=f"Service '{service_id}' not found")


@router.post("/services/{service_id}/test", response_model=ConnectionTestResponse)
def test_connection(
    service_id: str,
    svc: ServiceRegistryService = Depends(get_service),
    _admin: dict = Depends(require_admin),
):
    try:
        result = svc.test_connection(service_id)
        return ConnectionTestResponse(**result)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.get("/services/{service_id}/oauth", response_model=OAuthConfigResponse)
def get_oauth_config(
    service_id: str,
    svc: ServiceRegistryService = Depends(get_service),
    _admin: dict = Depends(require_admin),
):
    config = svc.get_oauth_config(service_id)
    if config:
        return OAuthConfigResponse(
            service_id=config.service_id,
            client_id=config.client_id,
            auth_url=config.auth_url,
            token_url=config.token_url,
            scopes=config.scopes,
            source="db",
        )

    from app.services.oauth_service import OAuthService, OAuthConfigError
    from app.schemas.oauth import OAuthProvider

    centralized_services = {
        "gmail": OAuthProvider.GOOGLE,
        "gcalendar": OAuthProvider.GOOGLE,
        "gdrive": OAuthProvider.GOOGLE,
    }
    provider = centralized_services.get(service_id)
    if not provider:
        raise HTTPException(status_code=404, detail=f"No OAuth config for '{service_id}'")

    try:
        oauth_svc = OAuthService()
        env_config = oauth_svc._get_config_from_env(provider, service_id=service_id)
        return OAuthConfigResponse(
            service_id=service_id,
            client_id=env_config.client_id,
            auth_url=env_config.authorization_url,
            token_url=env_config.token_url,
            scopes=env_config.scopes,
            source="env",
        )
    except OAuthConfigError:
        raise HTTPException(
            status_code=404, detail=f"No OAuth config for '{service_id}'"
        )


@router.put("/services/{service_id}/oauth", response_model=OAuthConfigResponse)
def set_oauth_config(
    service_id: str,
    body: OAuthConfigRequest,
    svc: ServiceRegistryService = Depends(get_service),
    _admin: dict = Depends(require_admin),
):
    try:
        config = svc.set_oauth_config(
            service_id=service_id,
            client_id=body.client_id,
            client_secret=body.client_secret,
            auth_url=body.auth_url,
            token_url=body.token_url,
            scopes=body.scopes,
        )
        return OAuthConfigResponse(
            service_id=config.service_id,
            client_id=config.client_id,
            auth_url=config.auth_url,
            token_url=config.token_url,
            scopes=config.scopes,
        )
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.post("/services/{service_id}/discover-tools")
def discover_tools(
    service_id: str,
    svc: ServiceRegistryService = Depends(get_service),
    _admin: dict = Depends(require_admin),
):
    service = svc.get_service(service_id)
    if not service:
        raise HTTPException(status_code=404, detail=f"Service '{service_id}' not found")
    if service.backend_type != "mcp":
        raise HTTPException(status_code=400, detail="Tool discovery only available for MCP services")

    return {
        "service_id": service_id,
        "message": "Tool discovery placeholder — requires gateway proxy in production",
        "discovered_tools": service.discovered_tools or [],
        "permission_map": service.permission_map or {},
    }


@router.get("/directory")
def list_directory(
    db: Session = Depends(get_db),
    _admin: dict = Depends(require_admin),
):
    from app.services.directory_sync_service import DirectorySyncService

    sync_svc = DirectorySyncService(db)
    return sync_svc.get_all()


@router.post("/directory/sync")
def trigger_directory_sync(
    db: Session = Depends(get_db),
    _admin: dict = Depends(require_admin),
):
    from app.services.directory_sync_service import DirectorySyncService

    sync_svc = DirectorySyncService(db)
    result = sync_svc.sync_from_google()
    return {"status": "completed", **result}


@router.get("/health", response_model=HealthSummaryResponse)
def get_health_summary(
    svc: ServiceRegistryService = Depends(get_service),
    _admin: dict = Depends(require_admin),
):
    return svc.get_health_summary()
