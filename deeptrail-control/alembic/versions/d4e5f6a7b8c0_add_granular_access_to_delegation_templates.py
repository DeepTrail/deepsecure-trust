"""Add granular access columns to delegation_templates

The b2c3d4e5f7a8 migration added available_to_groups and available_to_users
to service_registry but missed adding the same columns to delegation_templates.
The DelegationTemplate model already declares these columns, so any query
against the table fails with UndefinedColumn.

Revision ID: d4e5f6a7b8c0
Revises: c3d4e5f6a7b9
Create Date: 2026-06-02
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

revision = "d4e5f6a7b8c0"
down_revision = "c3d4e5f6a7b9"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "delegation_templates",
        sa.Column(
            "available_to_groups",
            JSONB,
            server_default="[]",
            nullable=True,
            comment="Group emails that can use this template",
        ),
    )
    op.add_column(
        "delegation_templates",
        sa.Column(
            "available_to_users",
            JSONB,
            server_default="[]",
            nullable=True,
            comment="User emails that can use this template",
        ),
    )


def downgrade() -> None:
    op.drop_column("delegation_templates", "available_to_users")
    op.drop_column("delegation_templates", "available_to_groups")
