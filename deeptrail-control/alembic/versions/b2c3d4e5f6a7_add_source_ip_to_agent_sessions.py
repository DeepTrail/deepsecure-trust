"""Add source_ip column to agent_sessions table.

Tracks the IP address of the authenticating agent for session history
and security auditing. VARCHAR(45) accommodates both IPv4 and IPv6
mapped-IPv4 addresses (e.g., "::ffff:192.168.1.1").

Revision ID: b2c3d4e5f6a7
Revises: a1b2c3d4e5f7
Create Date: 2026-05-10
"""

from alembic import op
import sqlalchemy as sa

revision = "b2c3d4e5f6a7"
down_revision = "a1b2c3d4e5f7"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "agent_sessions",
        sa.Column(
            "source_ip",
            sa.String(45),
            nullable=True,
            comment="IP address of the authenticating agent (IPv4 or IPv6)",
        ),
    )


def downgrade() -> None:
    op.drop_column("agent_sessions", "source_ip")
