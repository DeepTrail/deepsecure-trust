"""Admin IdP group → role mapping CRUD."""

import logging
from datetime import datetime
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.core.idp_config import IdPConfig
from app.middleware.admin_auth import require_admin
from app.models.audit_event import AuditEvent
from app.services.idp_mapping_service import IdpMappingService

logger = logging.getLogger(__name__)

router = APIRouter()


class MappingResponse(BaseModel):
    id: str
    idp_issuer: str
    group_name: str
    role: str
    enabled: bool
    created_by: Optional[str] = None
    created_at: datetime
    updated_at: Optional[datetime] = None


class MappingListResponse(BaseModel):
    mappings: list[MappingResponse]
    total: int
    idp_metadata: dict[str, Any]


class MappingCreateRequest(BaseModel):
    group_name: str = Field(..., max_length=255)
    role: str = Field(..., max_length=50)
    idp_issuer: Optional[str] = Field(None, max_length=512)
    enabled: bool = True


class MappingUpdateRequest(BaseModel):
    group_name: Optional[str] = Field(None, max_length=255)
    role: Optional[str] = Field(None, max_length=50)
    enabled: Optional[bool] = None


class ImportYamlResponse(BaseModel):
    imported: int
    skipped: int
    idp_issuer: str


def _to_response(mapping) -> MappingResponse:
    return MappingResponse(
        id=mapping.id,
        idp_issuer=mapping.idp_issuer,
        group_name=mapping.group_name,
        role=mapping.role,
        enabled=mapping.enabled,
        created_by=mapping.created_by,
        created_at=mapping.created_at,
        updated_at=mapping.updated_at,
    )


def _idp_config() -> IdPConfig:
    return IdPConfig()


def _default_issuer() -> str:
    return _idp_config().issuer_url


def _emit_audit(
    db: Session,
    *,
    event_type: str,
    actor: str,
    mapping_id: str,
    extra: dict[str, Any] | None = None,
) -> None:
    db.add(
        AuditEvent(
            event_type=event_type,
            on_behalf_of=actor,
            success=True,
            extra_data={"mapping_id": mapping_id, **(extra or {})},
        )
    )


@router.get("/idp/mappings", response_model=MappingListResponse)
def list_idp_mappings(
    idp_issuer: Optional[str] = None,
    db: Session = Depends(get_db),
    admin: dict = Depends(require_admin),
) -> MappingListResponse:
    svc = IdpMappingService(db)
    issuer = idp_issuer or _default_issuer()
    mappings = svc.list_mappings(idp_issuer=issuer)
    config = _idp_config()
    return MappingListResponse(
        mappings=[_to_response(m) for m in mappings],
        total=len(mappings),
        idp_metadata={
            "provider": config.provider.value,
            "issuer_url": config.issuer_url,
        },
    )


@router.post("/idp/mappings", response_model=MappingResponse, status_code=status.HTTP_201_CREATED)
def create_idp_mapping(
    body: MappingCreateRequest,
    db: Session = Depends(get_db),
    admin: dict = Depends(require_admin),
) -> MappingResponse:
    actor = admin.get("sub", "admin")
    issuer = body.idp_issuer or _default_issuer()
    svc = IdpMappingService(db)
    mapping = svc.create_mapping(
        idp_issuer=issuer,
        group_name=body.group_name,
        role=body.role,
        created_by=actor,
        enabled=body.enabled,
    )
    _emit_audit(
        db,
        event_type="idp_mapping_created",
        actor=actor,
        mapping_id=mapping.id,
        extra={"group_name": mapping.group_name, "role": mapping.role},
    )
    db.commit()
    return _to_response(mapping)


@router.patch("/idp/mappings/{mapping_id}", response_model=MappingResponse)
def update_idp_mapping(
    mapping_id: str,
    body: MappingUpdateRequest,
    db: Session = Depends(get_db),
    admin: dict = Depends(require_admin),
) -> MappingResponse:
    actor = admin.get("sub", "admin")
    svc = IdpMappingService(db)
    before = svc.get_mapping(mapping_id)
    if not before:
        raise HTTPException(status_code=404, detail="Mapping not found")

    mapping = svc.update_mapping(
        mapping_id,
        role=body.role,
        enabled=body.enabled,
        group_name=body.group_name,
    )
    _emit_audit(
        db,
        event_type="idp_mapping_updated",
        actor=actor,
        mapping_id=mapping_id,
        extra={
            "group_name": mapping.group_name,
            "role": mapping.role,
            "enabled": mapping.enabled,
            "before_role": before.role,
        },
    )
    db.commit()
    return _to_response(mapping)


@router.delete("/idp/mappings/{mapping_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_idp_mapping(
    mapping_id: str,
    db: Session = Depends(get_db),
    admin: dict = Depends(require_admin),
) -> None:
    actor = admin.get("sub", "admin")
    svc = IdpMappingService(db)
    mapping = svc.get_mapping(mapping_id)
    if not mapping:
        raise HTTPException(status_code=404, detail="Mapping not found")

    svc.delete_mapping(mapping_id)
    _emit_audit(
        db,
        event_type="idp_mapping_deleted",
        actor=actor,
        mapping_id=mapping_id,
        extra={"group_name": mapping.group_name, "role": mapping.role},
    )
    db.commit()


@router.post("/idp/mappings/import-yaml", response_model=ImportYamlResponse)
def import_yaml_mappings(
    idp_issuer: Optional[str] = None,
    db: Session = Depends(get_db),
    admin: dict = Depends(require_admin),
) -> ImportYamlResponse:
    actor = admin.get("sub", "admin")
    issuer = idp_issuer or _default_issuer()
    svc = IdpMappingService(db)
    result = svc.import_from_yaml(idp_issuer=issuer, created_by=actor)
    if result["imported"]:
        _emit_audit(
            db,
            event_type="idp_mapping_created",
            actor=actor,
            mapping_id="import-yaml",
            extra=result,
        )
        db.commit()
    return ImportYamlResponse(imported=result["imported"], skipped=result["skipped"], idp_issuer=issuer)
