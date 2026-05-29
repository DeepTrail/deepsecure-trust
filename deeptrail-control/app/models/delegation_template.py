"""SQLAlchemy model for Delegation Templates.

Delegation templates define admin-configured permission ceilings for agents.
When a user creates a delegation, the template's max_permissions and
blocked_permissions constrain what the user can grant (monotonic attenuation).
"""

import uuid
from datetime import datetime, time, timezone
from typing import Any, Dict, List, Optional

from sqlalchemy import Column, DateTime, Integer, JSON, String, Time, func
from sqlalchemy.dialects import postgresql

_uuid_str = lambda: str(uuid.uuid4())

from app.db.base import Base


class DelegationTemplate(Base):
    """Admin-defined permission ceiling for an agent's delegations.

    Example:
        IT Admin creates a template for agent-sdr-001:
          max_permissions: ["notion:pages:search", "slack:messages:read"]
          blocked_permissions: ["slack:messages:delete"]
          default_ttl_days: 7
          max_actions_per_day: 100
          working_hours_start: 09:00
          working_hours_end: 18:00

        When Sarah delegates to agent-sdr-001, the delegation is constrained
        to the template's ceiling — she cannot grant permissions outside
        max_permissions, and blocked_permissions are always denied.
    """

    __tablename__ = "delegation_templates"

    id = Column(
        String(36),
        primary_key=True,
        default=_uuid_str,
    )
    agent_id = Column(
        String(100),
        nullable=False,
        index=True,
        comment="Agent this template applies to",
    )
    max_permissions = Column(
        JSON().with_variant(postgresql.JSONB(), "postgresql"),
        nullable=False,
        comment='Permission ceiling (e.g., ["notion:pages:search"])',
    )
    blocked_permissions = Column(
        JSON().with_variant(postgresql.JSONB(), "postgresql"),
        server_default="[]",
        comment="Explicitly blocked permissions",
    )
    default_ttl_days = Column(Integer, server_default="7")
    available_to_roles = Column(
        JSON().with_variant(postgresql.JSONB(), "postgresql"),
        server_default='["all"]',
        comment='Which roles can use this template: ["all"] or ["sales"]',
    )
    max_actions_per_day = Column(
        Integer,
        nullable=True,
        comment="Rate limit per day (null = unlimited)",
    )
    working_hours_start = Column(
        Time,
        nullable=True,
        comment="Earliest allowed hour (e.g., 09:00)",
    )
    working_hours_end = Column(
        Time,
        nullable=True,
        comment="Latest allowed hour (e.g., 18:00)",
    )
    organization_id = Column(String(36), nullable=True)
    created_by = Column(
        String(200),
        nullable=True,
        comment="Admin who created this template",
    )
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
            f"<DelegationTemplate(agent_id='{self.agent_id}', "
            f"max_permissions={self.max_permissions})>"
        )
