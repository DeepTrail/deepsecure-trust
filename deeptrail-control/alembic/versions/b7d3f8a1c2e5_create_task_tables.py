"""Create tasks and scoped_permissions tables for Token Layer 4.

Revision ID: b7d3f8a1c2e5
Revises: a9f7c2d4e1b3
Create Date: 2026-04-06

Tasks are the atomic unit of agent work (Layer 4 of the 6-layer token
hierarchy). Each task has scoped permissions that are automatically
revoked on completion, enforcing the principle of least privilege.
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "b7d3f8a1c2e5"
down_revision = "a9f7c2d4e1b3"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "tasks",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("agent_id", sa.String(64), nullable=False),
        sa.Column("delegation_id", sa.String(64), nullable=True),
        sa.Column("initiated_by", sa.String(255), nullable=False),
        sa.Column("name", sa.String(255), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("status", sa.String(50), nullable=False, server_default="pending"),
        sa.Column("scoped_permissions", postgresql.JSONB(), nullable=False, server_default="[]"),
        sa.Column("constraints", postgresql.JSONB(), nullable=False, server_default="{}"),
        sa.Column("deadline", sa.DateTime(timezone=True), nullable=True),
        sa.Column("auto_revoke_on_complete", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("usage_summary", postgresql.JSONB(), nullable=False, server_default="{}"),
    )
    op.create_index("ix_task_agent_id", "tasks", ["agent_id"])
    op.create_index("ix_task_status", "tasks", ["status"])
    op.create_index("ix_task_agent_status", "tasks", ["agent_id", "status"])
    op.create_index("ix_task_deadline", "tasks", ["deadline"])
    op.create_index("ix_task_initiated_by", "tasks", ["initiated_by"])

    op.create_table(
        "scoped_permissions",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column(
            "task_id",
            sa.String(64),
            sa.ForeignKey("tasks.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("permission_urn", sa.String(512), nullable=False),
        sa.Column("constraints", postgresql.JSONB(), nullable=False, server_default="{}"),
        sa.Column("valid_until", sa.DateTime(timezone=True), nullable=False),
        sa.Column("usage_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("max_usage", sa.Integer(), nullable=True),
        sa.Column("revoked", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_scoped_perm_task_id", "scoped_permissions", ["task_id"])
    op.create_index("ix_scoped_perm_urn", "scoped_permissions", ["permission_urn"])
    op.create_index("ix_scoped_perm_task_urn", "scoped_permissions", ["task_id", "permission_urn"])


def downgrade() -> None:
    op.drop_index("ix_scoped_perm_task_urn", table_name="scoped_permissions")
    op.drop_index("ix_scoped_perm_urn", table_name="scoped_permissions")
    op.drop_index("ix_scoped_perm_task_id", table_name="scoped_permissions")
    op.drop_table("scoped_permissions")
    op.drop_index("ix_task_initiated_by", table_name="tasks")
    op.drop_index("ix_task_deadline", table_name="tasks")
    op.drop_index("ix_task_agent_status", table_name="tasks")
    op.drop_index("ix_task_status", table_name="tasks")
    op.drop_index("ix_task_agent_id", table_name="tasks")
    op.drop_table("tasks")
