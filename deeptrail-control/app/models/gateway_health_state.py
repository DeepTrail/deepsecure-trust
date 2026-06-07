"""Singleton row tracking gateway liveness from heartbeat POSTs."""

import uuid
from datetime import datetime, timezone

from sqlalchemy import Column, DateTime, String, func

from app.db.base import Base


class GatewayHealthState(Base):
    """Tracks when the gateway last reported a heartbeat."""

    __tablename__ = "gateway_health_state"

    id = Column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid.uuid4()),
    )
    gateway_last_seen_at = Column(DateTime(timezone=True), nullable=True)
    gateway_instance_id = Column(String(64), nullable=True)
    updated_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        server_default=func.now(),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    def __repr__(self) -> str:
        return (
            f"<GatewayHealthState(last_seen={self.gateway_last_seen_at}, "
            f"instance={self.gateway_instance_id})>"
        )
