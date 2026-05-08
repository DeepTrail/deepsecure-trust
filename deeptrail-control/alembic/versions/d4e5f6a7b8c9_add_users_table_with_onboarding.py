"""Add users table with onboarding_completed field.

Revision ID: d4e5f6a7b8c9
Revises: b7d3f8a1c2e5
Create Date: 2026-05-06

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "d4e5f6a7b8c9"
down_revision = "b7d3f8a1c2e5"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Create users table for storing user profiles and onboarding status."""
    op.create_table(
        "users",
        sa.Column(
            "user_id",
            sa.String(255),
            primary_key=True,
            index=True,
            comment="User identifier, typically email",
        ),
        sa.Column(
            "email",
            sa.String(255),
            nullable=True,
            comment="User email address",
        ),
        sa.Column(
            "onboarding_completed",
            sa.Boolean(),
            nullable=False,
            server_default="false",
            comment="Whether the user has completed onboarding",
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )


def downgrade() -> None:
    """Drop users table."""
    op.drop_table("users")
