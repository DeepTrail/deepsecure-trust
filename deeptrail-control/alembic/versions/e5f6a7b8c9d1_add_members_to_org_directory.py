"""Add members JSONB column to org_directory

The original migration (b2c3d4e5f7a8) created org_directory without
the members column, but the OrgDirectory model declares it.

Revision ID: e5f6a7b8c9d1
Revises: d4e5f6a7b8c0
Create Date: 2026-06-02
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

revision = "e5f6a7b8c9d1"
down_revision = "d4e5f6a7b8c0"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "org_directory",
        sa.Column(
            "members",
            JSONB,
            nullable=True,
            comment="List of member emails (only for group entries)",
        ),
    )


def downgrade() -> None:
    op.drop_column("org_directory", "members")
