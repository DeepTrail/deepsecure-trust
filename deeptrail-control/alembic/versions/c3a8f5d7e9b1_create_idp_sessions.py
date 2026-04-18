"""Create idp_sessions table for encrypted IdP token storage.

Revision ID: c3a8f5d7e9b1
Revises: b7d3f8a1c2e5
Create Date: 2026-04-18

Stores server-side IdP refresh / access tokens with Fernet encryption
so that DeepTrail can silently renew user sessions without requiring
users to re-authenticate through the full SSO flow.
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "c3a8f5d7e9b1"
down_revision = "b7d3f8a1c2e5"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Create idp_sessions table with indexes."""
    op.create_table(
        "idp_sessions",
        sa.Column(
            "id",
            sa.String(64),
            primary_key=True,
            comment="UUID generated in Python",
        ),
        sa.Column(
            "session_id",
            sa.String(128),
            nullable=False,
            unique=True,
            comment="Links to DeepTrail JWT session_id claim",
        ),
        sa.Column(
            "user_id",
            sa.String(255),
            nullable=False,
            comment="User email / identifier",
        ),
        sa.Column(
            "idp",
            sa.String(32),
            nullable=False,
            comment="Identity provider: keycloak | google",
        ),
        sa.Column(
            "encrypted_refresh_token",
            sa.Text(),
            nullable=True,
            comment="Fernet-encrypted IdP refresh token",
        ),
        sa.Column(
            "encrypted_access_token",
            sa.Text(),
            nullable=True,
            comment="Fernet-encrypted IdP access token",
        ),
        sa.Column(
            "id_token_claims",
            postgresql.JSONB(),
            nullable=True,
            comment="Cached claims dict from the ID token",
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
            comment="Row creation timestamp",
        ),
        sa.Column(
            "refreshed_at",
            sa.DateTime(timezone=True),
            nullable=True,
            comment="Last successful token refresh timestamp",
        ),
        sa.Column(
            "expires_at",
            sa.DateTime(timezone=True),
            nullable=True,
            comment="Refresh token expiry (NULL = unknown / no expiry)",
        ),
        sa.Column(
            "revoked",
            sa.Boolean(),
            nullable=False,
            server_default="false",
            comment="Set to true on logout to prevent further refreshes",
        ),
    )

    op.create_index(
        "ix_idp_session_session_id",
        "idp_sessions",
        ["session_id"],
        unique=True,
    )
    op.create_index(
        "ix_idp_session_user_id",
        "idp_sessions",
        ["user_id"],
    )
    op.create_index(
        "ix_idp_session_idp",
        "idp_sessions",
        ["idp"],
    )


def downgrade() -> None:
    """Drop idp_sessions indexes then table."""
    op.drop_index("ix_idp_session_idp", table_name="idp_sessions")
    op.drop_index("ix_idp_session_user_id", table_name="idp_sessions")
    op.drop_index("ix_idp_session_session_id", table_name="idp_sessions")
    op.drop_table("idp_sessions")
