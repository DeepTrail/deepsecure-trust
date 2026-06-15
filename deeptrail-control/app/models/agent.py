"""SQLAlchemy model for Agent entities."""

from sqlalchemy import Column, String, DateTime, JSON, func, LargeBinary, Text
from sqlalchemy.dialects import postgresql
from sqlalchemy.orm import relationship

from app.db.base import Base


class Agent(Base):
    __tablename__ = "agents"

    agent_id = Column(String, primary_key=True, index=True, nullable=False)
    name = Column(String(255), index=True)
    description = Column(Text)
    public_key = Column(LargeBinary, nullable=True, unique=True)
    platform = Column(String(64), nullable=True)
    selector = Column(String(255), nullable=True, unique=True)
    config = Column(
        JSON().with_variant(postgresql.JSONB(), "postgresql"),
        nullable=True,
        server_default="{}",
        comment="Agent runtime config: tagged_prompts, operational params",
    )
    created_at = Column(DateTime(timezone=True), default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), default=func.now(), nullable=False)
    last_seen_at = Column(DateTime(timezone=True))

    nonces = relationship("Nonce", back_populates="agent", cascade="all, delete-orphan") 