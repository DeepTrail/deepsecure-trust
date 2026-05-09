"""Add user_sessions and pending_oauth_states tables.

Fixes 2 of the 3 residual CRITICALs from verify_integration.py:
  1. user_sessions ORM model existed but had no migration → creates table.
  2. pending_oauth_states replaces the in-memory _pending_sso dict in sso.py.

Revision ID: a1b2c3d4e5f7
Revises: f1a2b3c4d5e6
Create Date: 2026-05-08
"""

from alembic import op
import sqlalchemy as sa

revision = "a1b2c3d4e5f7"
down_revision = "f1a2b3c4d5e6"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ------------------------------------------------------------------
    # 1. user_sessions
    # ------------------------------------------------------------------
    op.create_table(
        "user_sessions",
        sa.Column("session_id", sa.String(64), primary_key=True, index=True,
                  comment="Unique session identifier (e.g., usess-<uuid>)"),
        sa.Column("user_id", sa.String(255), nullable=False, index=True,
                  comment="User identifier, typically email"),
        sa.Column("idp_issuer", sa.String(512), nullable=False,
                  comment="Identity provider issuer URL"),
        sa.Column("organization_id", sa.String(64), nullable=True, index=True,
                  comment="Organization identifier for multi-tenant deployments"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.text("now()"),
                  comment="When the session was created"),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False,
                  comment="When the session expires (default: 8 hours after creation)"),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True,
                  comment="When the session was explicitly revoked (NULL = active)"),
        sa.Column("idp_metadata", sa.Text, nullable=True,
                  comment="Optional JSON metadata from the IdP"),
    )
    op.create_index("ix_user_sessions_user_id", "user_sessions", ["user_id"])
    op.create_index("ix_user_sessions_organization_id", "user_sessions", ["organization_id"])

    # ------------------------------------------------------------------
    # 2. pending_oauth_states  (replaces in-memory _pending_sso dict)
    # ------------------------------------------------------------------
    op.create_table(
        "pending_oauth_states",
        sa.Column("state", sa.String(128), primary_key=True,
                  comment="OAuth state parameter (random, URL-safe)"),
        sa.Column("idp", sa.String(32), nullable=False,
                  comment="Identity provider: google | keycloak | etc."),
        sa.Column("redirect_uri", sa.Text, nullable=False,
                  comment="Callback URI passed to the IdP"),
        sa.Column("code_verifier", sa.Text, nullable=True,
                  comment="PKCE code_verifier (S256); NULL if PKCE not used"),
        sa.Column("post_login_redirect", sa.Text, nullable=True,
                  comment="Frontend URL to redirect to after successful login"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.text("now()"),
                  comment="When this pending state was created"),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False,
                  comment="When this state expires (5 minutes after creation)"),
    )
    op.create_index("ix_pending_oauth_states_expires_at", "pending_oauth_states", ["expires_at"])


def downgrade() -> None:
    op.drop_index("ix_pending_oauth_states_expires_at", table_name="pending_oauth_states")
    op.drop_table("pending_oauth_states")

    op.drop_index("ix_user_sessions_organization_id", table_name="user_sessions")
    op.drop_index("ix_user_sessions_user_id", table_name="user_sessions")
    op.drop_table("user_sessions")
