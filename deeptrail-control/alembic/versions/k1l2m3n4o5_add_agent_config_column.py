"""Add config JSONB column to agents table

Stores per-agent runtime configuration (tagged_prompts, operational
params) so agents can be reconfigured without rebuilding Docker images.

Revision ID: k1l2m3n4o5
Revises: j0k1l2m3n5
Create Date: 2026-06-15
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

revision = "k1l2m3n4o5"
down_revision = "j0k1l2m3n5"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "agents",
        sa.Column(
            "config",
            JSONB,
            nullable=True,
            server_default="{}",
            comment="Agent runtime config: tagged_prompts, operational params",
        ),
    )


def downgrade() -> None:
    op.drop_column("agents", "config")
