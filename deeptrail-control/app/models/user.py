"""SQLAlchemy model for User entities.

Stores user profile data including onboarding status.
User identity (email) comes from the authentication system.
"""

from datetime import datetime, timezone

from sqlalchemy import Boolean, Column, DateTime, String, func

from app.db.base import Base


class User(Base):
    """Represents a user profile in the database."""

    __tablename__ = "users"

    user_id = Column(
        String(255),
        primary_key=True,
        index=True,
        comment="User identifier, typically email (e.g., sarah@acme.com)",
    )

    email = Column(
        String(255),
        nullable=True,
        comment="User email address (may be same as user_id)",
    )

    onboarding_completed = Column(
        Boolean,
        nullable=False,
        default=False,
        server_default="false",
        comment="Whether the user has completed onboarding",
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
            f"<User(user_id='{self.user_id}', "
            f"onboarding_completed={self.onboarding_completed})>"
        )
