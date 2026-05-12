"""add delegation_tokens, agent_sessions, audit_events tables

Revision ID: f1a2b3c4d5e6
Revises: 62d521598579
Create Date: 2026-05-08
"""

revision = "f1a2b3c4d5e6"
down_revision = "62d521598579"
branch_labels = None
depends_on = None

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


def upgrade() -> None:
    # --- delegation_tokens ---
    op.create_table(
        "delegation_tokens",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("agent_id", sa.String(64), nullable=False),
        sa.Column("delegator", sa.String(255), nullable=False),
        sa.Column("delegator_idp", sa.String(512), nullable=True),
        sa.Column("user_token_hash", sa.String(128), nullable=True),
        sa.Column("agent_token_hash", sa.String(128), nullable=True),
        sa.Column(
            "delegated_permissions",
            sa.JSON().with_variant(postgresql.JSONB(), "postgresql"),
            nullable=False,
            server_default="[]",
        ),
        sa.Column(
            "constraints",
            sa.JSON().with_variant(postgresql.JSONB(), "postgresql"),
            nullable=False,
            server_default="{}",
        ),
        sa.Column("organization_id", sa.String(64), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("logging_uri", sa.String(512), nullable=True),
        sa.Column("revocation_uri", sa.String(512), nullable=True),
    )
    op.create_index("ix_delegation_tokens_agent_id", "delegation_tokens", ["agent_id"])
    op.create_index("ix_delegation_tokens_delegator", "delegation_tokens", ["delegator"])
    op.create_index("ix_delegation_tokens_organization_id", "delegation_tokens", ["organization_id"])
    op.create_index("ix_delegation_agent_delegator", "delegation_tokens", ["agent_id", "delegator"])
    op.create_index("ix_delegation_delegator_time", "delegation_tokens", ["delegator", "created_at"])
    op.create_index("ix_delegation_org", "delegation_tokens", ["organization_id"])

    # --- agent_sessions ---
    # Create enum via raw SQL with idempotent guard, then reference it
    # with create_type=False to prevent SQLAlchemy's DDL events from
    # trying to auto-create it again during create_table.
    op.execute(
        "DO $$ BEGIN "
        "CREATE TYPE partytype AS ENUM ('first_party', 'third_party', 'federated'); "
        "EXCEPTION WHEN duplicate_object THEN null; "
        "END $$;"
    )
    party_type_enum = postgresql.ENUM(
        "first_party", "third_party", "federated",
        name="partytype",
        create_type=False,
    )

    op.create_table(
        "agent_sessions",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("agent_id", sa.String(128), nullable=False),
        sa.Column(
            "delegation_id",
            sa.String(64),
            sa.ForeignKey("delegation_tokens.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("party_type", party_type_enum, nullable=False),
        sa.Column(
            "scoped_permissions",
            sa.JSON().with_variant(postgresql.JSONB(), "postgresql"),
            nullable=False,
            server_default="[]",
        ),
        sa.Column(
            "mcp_sessions",
            sa.JSON().with_variant(postgresql.JSONB(), "postgresql"),
            nullable=False,
            server_default="{}",
        ),
        sa.Column("challenge_nonce", sa.String(128), nullable=True),
        sa.Column("challenge_expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default=sa.text("true")),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_activity_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revoked_by", sa.String(128), nullable=True),
        sa.Column("revoke_reason", sa.String(256), nullable=True),
        sa.Column("owner_email", sa.String(256), nullable=False),
        sa.Column("idp_issuer", sa.String(512), nullable=True),
        sa.Column(
            "groups",
            sa.JSON().with_variant(postgresql.JSONB(), "postgresql"),
            nullable=False,
            server_default="[]",
        ),
        sa.Column("organization_id", sa.String(64), nullable=True),
    )
    op.create_index("ix_agent_sessions_agent_id", "agent_sessions", ["agent_id"])
    op.create_index("ix_agent_sessions_delegation_id", "agent_sessions", ["delegation_id"])
    op.create_index("ix_agent_sessions_organization_id", "agent_sessions", ["organization_id"])
    op.create_index("ix_agent_session_agent_owner", "agent_sessions", ["agent_id", "owner_email"])
    op.create_index("ix_agent_session_delegation", "agent_sessions", ["delegation_id"])
    op.create_index("ix_agent_session_org", "agent_sessions", ["organization_id"])

    # --- audit_events ---
    op.create_table(
        "audit_events",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column(
            "timestamp",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column("event_type", sa.String(50), nullable=False),
        sa.Column("agent_id", sa.String(64), nullable=True),
        sa.Column("on_behalf_of", sa.String(255), nullable=False),
        sa.Column("organization_id", sa.String(64), nullable=True),
        sa.Column("success", sa.Boolean, nullable=True),
        sa.Column("tool", sa.String(255), nullable=True),
        sa.Column(
            "arguments",
            sa.JSON().with_variant(postgresql.JSONB(), "postgresql"),
            nullable=True,
        ),
        sa.Column("result_summary", sa.String(500), nullable=True),
        sa.Column("attempted_tool", sa.String(255), nullable=True),
        sa.Column("required_permission", sa.String(255), nullable=True),
        sa.Column("reason", sa.Text, nullable=True),
        sa.Column("session_id", sa.String(64), nullable=True),
        sa.Column("agent_session_id", sa.String(64), nullable=True),
        sa.Column("mcp_session_id", sa.String(64), nullable=True),
        sa.Column("delegation_id", sa.String(64), nullable=True),
        sa.Column(
            "extra_data",
            sa.JSON().with_variant(postgresql.JSONB(), "postgresql"),
            nullable=True,
        ),
    )
    op.create_index("ix_audit_events_timestamp", "audit_events", ["timestamp"])
    op.create_index("ix_audit_events_event_type", "audit_events", ["event_type"])
    op.create_index("ix_audit_events_agent_id", "audit_events", ["agent_id"])
    op.create_index("ix_audit_events_on_behalf_of", "audit_events", ["on_behalf_of"])
    op.create_index("ix_audit_events_organization_id", "audit_events", ["organization_id"])
    op.create_index("ix_audit_events_session_id", "audit_events", ["session_id"])
    op.create_index("ix_audit_events_agent_session_id", "audit_events", ["agent_session_id"])
    op.create_index("ix_audit_events_delegation_id", "audit_events", ["delegation_id"])
    op.create_index("ix_audit_agent_time", "audit_events", ["agent_id", "timestamp"])
    op.create_index("ix_audit_user_time", "audit_events", ["on_behalf_of", "timestamp"])
    op.create_index("ix_audit_org_time", "audit_events", ["organization_id", "timestamp"])
    op.create_index("ix_audit_type_time", "audit_events", ["event_type", "timestamp"])
    op.create_index("ix_audit_delegation_time", "audit_events", ["delegation_id", "timestamp"])


def downgrade() -> None:
    op.drop_table("audit_events")
    op.drop_table("agent_sessions")
    sa.Enum(name="partytype").drop(op.get_bind(), checkfirst=True)
    op.drop_table("delegation_tokens")
