"""Add org_directory table and granular access columns to service_registry

Creates:
- org_directory table (groups and users synced from Workspace)

Modifies:
- service_registry: add available_to_groups and available_to_users JSONB columns

Revision ID: b2c3d4e5f7a8
Revises: a1b2c3d4e5f6
Create Date: 2026-06-01
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "b2c3d4e5f7a8"
down_revision = "a1b2c3d4e5f6"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "org_directory",
        sa.Column(
            "id",
            sa.String(36),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("entity_type", sa.String(10), nullable=False),
        sa.Column("email", sa.String(255), nullable=False, unique=True),
        sa.Column("display_name", sa.String(200), nullable=True),
        sa.Column("member_count", sa.Integer(), nullable=True),
        sa.Column(
            "synced_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
    )

    op.add_column(
        "service_registry",
        sa.Column(
            "available_to_groups",
            postgresql.JSONB(),
            server_default="[]",
            nullable=True,
        ),
    )
    op.add_column(
        "service_registry",
        sa.Column(
            "available_to_users",
            postgresql.JSONB(),
            server_default="[]",
            nullable=True,
        ),
    )


def downgrade() -> None:
    op.drop_column("service_registry", "available_to_users")
    op.drop_column("service_registry", "available_to_groups")
    op.drop_table("org_directory")
