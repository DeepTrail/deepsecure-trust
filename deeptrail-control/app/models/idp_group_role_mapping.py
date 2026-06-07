"""DB-backed IdP group → DeepSecure role mappings (overrides YAML for same key)."""

import uuid
from datetime import datetime, timezone

from sqlalchemy import Boolean, Column, DateTime, String, UniqueConstraint, func

from app.db.base import Base

CANONICAL_ROLES = frozenset({"employee", "engineer", "sales", "admin", "security"})


class IdpGroupRoleMapping(Base):
    """Maps an IdP group name to a canonical DeepSecure role for a given issuer."""

    __tablename__ = "idp_group_role_mappings"
    __table_args__ = (
        UniqueConstraint("idp_issuer", "group_name", name="uq_idp_issuer_group_name"),
    )

    id = Column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid.uuid4()),
    )
    idp_issuer = Column(String(512), nullable=False, index=True)
    group_name = Column(String(255), nullable=False, index=True)
    role = Column(String(50), nullable=False)
    enabled = Column(Boolean, nullable=False, server_default="true", default=True)
    created_by = Column(String(255), nullable=True)
    created_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        server_default=func.now(),
        nullable=False,
    )
    updated_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        server_default=func.now(),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    def __repr__(self) -> str:
        return (
            f"<IdpGroupRoleMapping(group='{self.group_name}', "
            f"role='{self.role}', issuer='{self.idp_issuer[:32]}...')>"
        )
