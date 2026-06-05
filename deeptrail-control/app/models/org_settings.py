from sqlalchemy import Column, JSON, String, DateTime
from sqlalchemy.dialects import postgresql
from sqlalchemy.sql import func

from app.db.base import Base


class OrgSettings(Base):
    __tablename__ = "org_settings"

    key = Column(String(100), primary_key=True)
    value = Column(JSON().with_variant(postgresql.JSONB(), "postgresql"))
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
