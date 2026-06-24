"""Add created_by and owner_user_id to agents table.

Tracks which admin registered each agent and who owns it (for alert routing).
Both nullable for backwards compatibility with existing agents.
Backfills existing rows with the platform admin email.

Revision ID: m3n4o5p6q7
Revises: l2m3n4o5p6
Create Date: 2026-06-24
"""

from alembic import op
import sqlalchemy as sa

revision = "m3n4o5p6q7"
down_revision = "l2m3n4o5p6"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("agents", sa.Column("created_by", sa.String(200), nullable=True))
    op.add_column("agents", sa.Column("owner_user_id", sa.String(200), nullable=True))
    op.execute("UPDATE agents SET created_by = 'mahendra@deeptrail.com' WHERE created_by IS NULL")


def downgrade():
    op.drop_column("agents", "owner_user_id")
    op.drop_column("agents", "created_by")
