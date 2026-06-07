"""CRUD and resolution for DB-backed IdP group → role mappings."""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from sqlalchemy.orm import Session

from app.models.idp_group_role_mapping import CANONICAL_ROLES, IdpGroupRoleMapping
from app.services.group_policy import GroupPolicyMapper

logger = logging.getLogger(__name__)


class IdpMappingService:
    """Manage IdP mappings and resolve roles with DB-over-YAML precedence."""

    def __init__(self, db: Session):
        self.db = db

    # --- CRUD ---

    def list_mappings(self, idp_issuer: str | None = None) -> list[IdpGroupRoleMapping]:
        query = self.db.query(IdpGroupRoleMapping)
        if idp_issuer:
            query = query.filter(IdpGroupRoleMapping.idp_issuer == idp_issuer)
        return query.order_by(IdpGroupRoleMapping.group_name).all()

    def get_mapping(self, mapping_id: str) -> IdpGroupRoleMapping | None:
        return (
            self.db.query(IdpGroupRoleMapping)
            .filter(IdpGroupRoleMapping.id == mapping_id)
            .first()
        )

    def create_mapping(
        self,
        *,
        idp_issuer: str,
        group_name: str,
        role: str,
        created_by: str,
        enabled: bool = True,
    ) -> IdpGroupRoleMapping:
        role = self._validate_role(role)
        existing = (
            self.db.query(IdpGroupRoleMapping)
            .filter(
                IdpGroupRoleMapping.idp_issuer == idp_issuer,
                IdpGroupRoleMapping.group_name == group_name,
            )
            .first()
        )
        if existing:
            from fastapi import HTTPException, status

            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Mapping already exists for group '{group_name}' on issuer '{idp_issuer}'",
            )

        mapping = IdpGroupRoleMapping(
            idp_issuer=idp_issuer,
            group_name=group_name,
            role=role,
            enabled=enabled,
            created_by=created_by,
        )
        self.db.add(mapping)
        self.db.commit()
        self.db.refresh(mapping)
        return mapping

    def update_mapping(
        self,
        mapping_id: str,
        *,
        role: str | None = None,
        enabled: bool | None = None,
        group_name: str | None = None,
    ) -> IdpGroupRoleMapping | None:
        mapping = self.get_mapping(mapping_id)
        if not mapping:
            return None

        if role is not None:
            mapping.role = self._validate_role(role)
        if enabled is not None:
            mapping.enabled = enabled
        if group_name is not None and group_name != mapping.group_name:
            conflict = (
                self.db.query(IdpGroupRoleMapping)
                .filter(
                    IdpGroupRoleMapping.idp_issuer == mapping.idp_issuer,
                    IdpGroupRoleMapping.group_name == group_name,
                    IdpGroupRoleMapping.id != mapping_id,
                )
                .first()
            )
            if conflict:
                from fastapi import HTTPException, status

                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=f"Mapping already exists for group '{group_name}'",
                )
            mapping.group_name = group_name

        mapping.updated_at = datetime.now(timezone.utc)
        self.db.commit()
        self.db.refresh(mapping)
        return mapping

    def delete_mapping(self, mapping_id: str) -> bool:
        mapping = self.get_mapping(mapping_id)
        if not mapping:
            return False
        self.db.delete(mapping)
        self.db.commit()
        return True

    def import_from_yaml(
        self,
        *,
        idp_issuer: str,
        created_by: str,
        yaml_path: Path | None = None,
    ) -> dict[str, int]:
        """Import group→role entries from group_policies.yaml (skip existing keys)."""
        path = yaml_path or Path(__file__).resolve().parents[2] / "group_policies.yaml"
        if not path.exists():
            return {"imported": 0, "skipped": 0}

        import yaml

        with open(path) as fh:
            data = yaml.safe_load(fh) or {}
        imported = 0
        skipped = 0
        for entry in data.get("policies", []):
            group = entry.get("group")
            if not group:
                skipped += 1
                continue
            policy_role = (entry.get("role") or "").strip().lower()
            exists = (
                self.db.query(IdpGroupRoleMapping)
                .filter(
                    IdpGroupRoleMapping.idp_issuer == idp_issuer,
                    IdpGroupRoleMapping.group_name == group,
                )
                .first()
            )
            if exists:
                skipped += 1
                continue
            if policy_role not in CANONICAL_ROLES:
                skipped += 1
                continue
            self.db.add(
                IdpGroupRoleMapping(
                    idp_issuer=idp_issuer,
                    group_name=group,
                    role=policy_role,
                    enabled=True,
                    created_by=created_by,
                )
            )
            imported += 1

        if imported:
            self.db.commit()
        return {"imported": imported, "skipped": skipped}

    # --- Resolution (DB overrides YAML for same group) ---

    def resolve_group_roles(
        self,
        idp_issuer: str,
        groups: list[str],
        yaml_mapper: GroupPolicyMapper | None = None,
    ) -> list[str]:
        """Return roles for groups; enabled DB mappings win over YAML for same group."""
        if not groups:
            return []

        db_by_group: dict[str, str] = {}
        rows = (
            self.db.query(IdpGroupRoleMapping)
            .filter(
                IdpGroupRoleMapping.idp_issuer == idp_issuer,
                IdpGroupRoleMapping.group_name.in_(groups),
                IdpGroupRoleMapping.enabled.is_(True),
            )
            .all()
        )
        for row in rows:
            db_by_group[row.group_name] = row.role

        roles: list[str] = []
        yaml_groups: list[str] = []
        for group in groups:
            if group in db_by_group:
                roles.append(db_by_group[group])
            else:
                yaml_groups.append(group)

        if yaml_groups and yaml_mapper is not None:
            yaml_result = yaml_mapper.resolve(yaml_groups)
            roles.extend(yaml_result.roles)

        return self._dedupe_roles(roles)

    def resolve_group_policy_merge(
        self,
        idp_issuer: str,
        groups: list[str],
        yaml_mapper: GroupPolicyMapper,
    ) -> dict[str, Any]:
        """Roles (DB-over-YAML) plus YAML default_permissions for non-DB groups."""
        db_covered = {
            row.group_name
            for row in self.db.query(IdpGroupRoleMapping)
            .filter(
                IdpGroupRoleMapping.idp_issuer == idp_issuer,
                IdpGroupRoleMapping.group_name.in_(groups),
                IdpGroupRoleMapping.enabled.is_(True),
            )
            .all()
        }
        yaml_only_groups = [g for g in groups if g not in db_covered]
        yaml_result = yaml_mapper.resolve(yaml_only_groups) if yaml_only_groups else None

        roles = self.resolve_group_roles(idp_issuer, groups, yaml_mapper)
        default_permissions: list[str] = []
        if yaml_result:
            default_permissions = yaml_result.default_permissions

        return {
            "roles": roles,
            "default_permissions": default_permissions,
            "matched_groups": list(db_covered) + (yaml_result.matched_groups if yaml_result else []),
        }

    @staticmethod
    def _validate_role(role: str) -> str:
        normalized = (role or "").strip().lower()
        if normalized not in CANONICAL_ROLES:
            from fastapi import HTTPException, status

            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid role '{role}'. Must be one of: {sorted(CANONICAL_ROLES)}",
            )
        return normalized

    @staticmethod
    def _dedupe_roles(roles: list[str]) -> list[str]:
        seen: dict[str, None] = {}
        for role in roles:
            key = (role or "").strip().lower()
            if key and key not in seen:
                seen[key] = None
        return list(seen)
