"""add gcp_workload_identity and sync platformtype enum

Revision ID: e5f6a7b8c9d0
Revises: c4d5e6f7a8b9
Create Date: 2026-05-15
"""

from alembic import op

revision = "e5f6a7b8c9d0"
down_revision = "c4d5e6f7a8b9"
branch_labels = None
depends_on = None

NEW_VALUES = [
    "azure_managed_identity",
    "docker_container",
    "gcp_workload_identity",
    "GCP_WORKLOAD_IDENTITY",
    "AZURE_MANAGED_IDENTITY",
    "DOCKER_CONTAINER",
]


def upgrade() -> None:
    for val in NEW_VALUES:
        op.execute(
            f"ALTER TYPE platformtype ADD VALUE IF NOT EXISTS '{val}'"
        )


def downgrade() -> None:
    pass
