"""Add vault_tokens table for persistent OAuth token storage.

Revision ID: a9f7c2d4e1b3
Revises: 8b5c2d3e4f6a
Create Date: 2026-02-22

This migration creates the vault_tokens table to replace in-memory token storage
in VaultClient. OAuth tokens are stored with Fernet encryption for persistence
across container restarts.
"""

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "a9f7c2d4e1b3"
down_revision = "8b5c2d3e4f6a"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Create vault_tokens table for encrypted OAuth token storage."""
    op.create_table(
        "vault_tokens",
        sa.Column(
            "token_ref",
            sa.String(512),
            primary_key=True,
            comment="Vault reference (e.g., vault://sarah-notion-abc123)",
        ),
        sa.Column(
            "user_id",
            sa.String(255),
            nullable=False,
            index=True,
            comment="User identifier (e.g., sarah@acme.com)",
        ),
        sa.Column(
            "service_id",
            sa.String(64),
            nullable=False,
            index=True,
            comment="Service identifier (e.g., notion, slack, hubspot)",
        ),
        sa.Column(
            "encrypted_data",
            sa.LargeBinary(),
            nullable=False,
            comment="Fernet-encrypted OAuth token JSON",
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
            comment="When token was stored",
        ),
        sa.Column(
            "expires_at",
            sa.DateTime(timezone=True),
            nullable=True,
            comment="Token expiration (NULL = no expiry)",
        ),
        sa.Column(
            "last_used_at",
            sa.DateTime(timezone=True),
            nullable=True,
            comment="Last retrieval timestamp",
        ),
        sa.Column(
            "refresh_count",
            sa.Integer(),
            nullable=False,
            server_default="0",
            comment="Number of times token was refreshed",
        ),
    )

    # Create composite index for user+service lookups
    op.create_index(
        "ix_vault_token_user_service",
        "vault_tokens",
        ["user_id", "service_id"],
    )

    # Create index for expiration-based queries (proactive refresh)
    op.create_index(
        "ix_vault_token_expires",
        "vault_tokens",
        ["expires_at"],
    )


def downgrade() -> None:
    """Drop vault_tokens table and indexes."""
    op.drop_index("ix_vault_token_expires", table_name="vault_tokens")
    op.drop_index("ix_vault_token_user_service", table_name="vault_tokens")
    op.drop_table("vault_tokens")
