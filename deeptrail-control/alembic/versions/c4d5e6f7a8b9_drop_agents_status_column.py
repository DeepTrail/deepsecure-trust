"""drop agents status column

Revision ID: c4d5e6f7a8b9
Revises: b2c3d4e5f6a7
Create Date: 2026-05-10
"""

from alembic import op
import sqlalchemy as sa

revision = "c4d5e6f7a8b9"
down_revision = "b2c3d4e5f6a7"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_index("ix_agents_status", table_name="agents", if_exists=True)
    op.drop_column("agents", "status")


def downgrade() -> None:
    op.add_column(
        "agents",
        sa.Column("status", sa.String(50), nullable=False, server_default="active"),
    )
    op.create_index("ix_agents_status", "agents", ["status"])
