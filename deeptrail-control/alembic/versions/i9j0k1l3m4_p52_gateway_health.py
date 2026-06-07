"""P5.2 gap closure: gateway health state + probe source

Revision ID: i9j0k1l3m4
Revises: h8i9j0k2l3
Create Date: 2026-06-07
"""

from alembic import op
import sqlalchemy as sa

revision = "i9j0k1l3m4"
down_revision = "h8i9j0k2l3"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "service_registry",
        sa.Column(
            "health_probe_source",
            sa.String(20),
            nullable=True,
            comment="Last probe origin: gateway or control_plane",
        ),
    )
    op.create_table(
        "gateway_health_state",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("gateway_last_seen_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("gateway_instance_id", sa.String(64), nullable=True),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )


def downgrade() -> None:
    op.drop_table("gateway_health_state")
    op.drop_column("service_registry", "health_probe_source")
