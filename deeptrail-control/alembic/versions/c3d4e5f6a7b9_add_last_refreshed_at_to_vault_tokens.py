"""Add last_refreshed_at and refresh_log columns to vault_tokens

Tracks when each OAuth token was last proactively refreshed by the
event-driven token refresh scheduler, and stores the last N refresh
events for debugging.

Revision ID: c3d4e5f6a7b9
Revises: b2c3d4e5f7a8
Create Date: 2026-06-02
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

revision = "c3d4e5f6a7b9"
down_revision = "b2c3d4e5f7a8"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "vault_tokens",
        sa.Column(
            "last_refreshed_at",
            sa.DateTime(timezone=True),
            nullable=True,
            comment="Timestamp of last successful proactive refresh",
        ),
    )
    op.add_column(
        "vault_tokens",
        sa.Column(
            "refresh_log",
            JSONB,
            nullable=True,
            comment="Last N refresh events [{timestamp, status, latency_ms, error}]",
        ),
    )


def downgrade() -> None:
    op.drop_column("vault_tokens", "refresh_log")
    op.drop_column("vault_tokens", "last_refreshed_at")
