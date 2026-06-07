"""P5.2 gap closure: idp_group_role_mappings table

Revision ID: j0k1l2m3n5
Revises: i9j0k1l3m4
Create Date: 2026-06-07
"""

from alembic import op
import sqlalchemy as sa

revision = "j0k1l2m3n5"
down_revision = "i9j0k1l3m4"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "idp_group_role_mappings",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("idp_issuer", sa.String(512), nullable=False),
        sa.Column("group_name", sa.String(255), nullable=False),
        sa.Column("role", sa.String(50), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_by", sa.String(255), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.UniqueConstraint("idp_issuer", "group_name", name="uq_idp_issuer_group_name"),
    )
    op.create_index(
        "ix_idp_group_role_mappings_idp_issuer",
        "idp_group_role_mappings",
        ["idp_issuer"],
    )
    op.create_index(
        "ix_idp_group_role_mappings_group_name",
        "idp_group_role_mappings",
        ["group_name"],
    )


def downgrade() -> None:
    op.drop_table("idp_group_role_mappings")
