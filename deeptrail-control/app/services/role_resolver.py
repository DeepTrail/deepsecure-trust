"""Resolve effective DeepSecure roles for a user from JWT, session, and groups."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

from app.services.group_policy import GroupPolicyMapper

if TYPE_CHECKING:
    from sqlalchemy.orm import Session

    from app.models.user_session import UserSession


@dataclass(frozen=True)
class UserContext:
    sub: str
    groups: list[str]
    roles: list[str]


class RoleResolver:
    """CR-1: JWT roles > session.role > group-derived roles > default employee."""

    _mapper: GroupPolicyMapper | None = None

    def _get_mapper(self) -> GroupPolicyMapper:
        if self._mapper is None:
            config_path = Path(__file__).resolve().parents[2] / "group_policies.yaml"
            if config_path.exists():
                self._mapper = GroupPolicyMapper.from_yaml(config_path)
            else:
                self._mapper = GroupPolicyMapper([])
        return self._mapper

    def resolve(
        self,
        jwt_roles: list[str] | None,
        user_session_role: str | None,
        groups: list[str] | None,
        db: Session | None = None,
        idp_issuer: str | None = None,
    ) -> list[str]:
        """Return deduplicated lowercase role names for visibility checks."""
        if jwt_roles:
            return self._normalize(jwt_roles)

        if user_session_role:
            return self._normalize([user_session_role])

        if groups:
            if db is not None and idp_issuer:
                from app.services.idp_mapping_service import IdpMappingService

                group_roles = IdpMappingService(db).resolve_group_roles(
                    idp_issuer, groups, self._get_mapper()
                )
            else:
                group_roles = self._get_mapper().resolve(groups).roles
            if group_roles:
                return self._normalize(group_roles)

        return ["employee"]

    def resolve_context(
        self,
        sub: str,
        jwt_roles: list[str] | None,
        groups: list[str] | None,
        db: Session,
    ) -> UserContext:
        """Build UserContext with session lookup for role resolution."""
        from app.models.user_session import UserSession

        session_role: str | None = None
        idp_issuer: str | None = None
        session = (
            db.query(UserSession)
            .filter(
                UserSession.user_id == sub,
                UserSession.revoked_at.is_(None),
            )
            .order_by(UserSession.created_at.desc())
            .first()
        )
        if session:
            session_role = session.role
            idp_issuer = session.idp_issuer

        normalized_groups = list(groups or [])
        roles = self.resolve(
            jwt_roles, session_role, normalized_groups, db, idp_issuer=idp_issuer
        )
        return UserContext(sub=sub, groups=normalized_groups, roles=roles)

    @staticmethod
    def _normalize(roles: list[str]) -> list[str]:
        seen: dict[str, None] = {}
        for role in roles:
            key = (role or "").strip().lower()
            if key and key not in seen:
                seen[key] = None
        return list(seen) or ["employee"]
