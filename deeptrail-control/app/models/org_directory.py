"""SQLAlchemy model for the Organization Directory.

Stores groups and users synced from Google Workspace (or seeded locally)
so that the admin UI can offer autocomplete when assigning service access.
"""

import uuid
from datetime import datetime, timezone

from sqlalchemy import Column, DateTime, Integer, JSON, String
from sqlalchemy.dialects import postgresql

from app.db.base import Base


class OrgDirectory(Base):
    __tablename__ = "org_directory"

    id = Column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid.uuid4()),
    )
    entity_type = Column(
        String(10),
        nullable=False,
        comment="'group' or 'user'",
    )
    email = Column(String(255), unique=True, nullable=False)
    display_name = Column(String(200), nullable=True)
    member_count = Column(Integer, nullable=True)
    members = Column(
        JSON().with_variant(postgresql.JSONB(), "postgresql"),
        nullable=True,
        comment="List of member emails (only for group entries)",
    )
    synced_at = Column(DateTime(timezone=True), nullable=True)

    def __repr__(self) -> str:
        return f"<OrgDirectory({self.entity_type}: {self.email})>"
