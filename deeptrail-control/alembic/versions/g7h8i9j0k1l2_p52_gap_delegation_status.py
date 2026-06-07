"""P5.2 gap closure: delegation_tokens status column

Revision ID: g7h8i9j0k1l2
Revises: f6a7b8c9d1e2
Create Date: 2026-06-07
"""

from alembic import op
import sqlalchemy as sa

revision = "g7h8i9j0k1l2"
down_revision = "f6a7b8c9d1e2"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "delegation_tokens",
        sa.Column(
            "status",
            sa.String(20),
            nullable=False,
            server_default="active",
        ),
    )
    op.execute(
        "UPDATE delegation_tokens SET status = 'revoked' WHERE revoked_at IS NOT NULL"
    )
    op.execute(
        "UPDATE delegation_tokens SET status = 'expired' "
        "WHERE revoked_at IS NULL AND expires_at < NOW()"
    )


def downgrade() -> None:
    op.drop_column("delegation_tokens", "status")
