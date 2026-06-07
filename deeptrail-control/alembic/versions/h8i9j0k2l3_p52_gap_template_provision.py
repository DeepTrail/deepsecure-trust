"""P5.2 gap closure: delegation_templates auto_provision fields

Revision ID: h8i9j0k2l3
Revises: g7h8i9j0k1l2
Create Date: 2026-06-07
"""

from alembic import op
import sqlalchemy as sa

revision = "h8i9j0k2l3"
down_revision = "g7h8i9j0k1l2"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "delegation_templates",
        sa.Column(
            "auto_provision",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
    )
    op.add_column(
        "delegation_templates",
        sa.Column(
            "provision_mode",
            sa.String(20),
            nullable=False,
            server_default="off",
        ),
    )


def downgrade() -> None:
    op.drop_column("delegation_templates", "provision_mode")
    op.drop_column("delegation_templates", "auto_provision")
