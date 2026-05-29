"""P5.2: Admin role, service registry, delegation templates

Creates:
- service_registry table (dynamic service catalog)
- service_oauth_config table (per-service OAuth credentials)
- delegation_templates table (admin-defined permission ceilings)

Modifies:
- user_sessions: add 'role' column (employee/admin/security)
- delegation_tokens: add 'template_id' and 'source' columns

Revision ID: a1b2c3d4e5f6
Revises: p4a1b2c3d4e5
Create Date: 2026-05-29
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "a1b2c3d4e5f6"
down_revision = "p4a1b2c3d4e5"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # --- New tables ---

    op.create_table(
        "service_registry",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), primary_key=True),
        sa.Column("service_id", sa.String(50), nullable=False, unique=True, index=True),
        sa.Column("display_name", sa.String(100), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("backend_type", sa.String(20), nullable=False, server_default="rest"),
        sa.Column("endpoint_url", sa.String(500), nullable=False),
        sa.Column("transport", sa.String(20), server_default="rest"),
        sa.Column("mcp_auth_method", sa.String(20), server_default="none"),
        sa.Column("mcp_auth_header", sa.String(100), nullable=True),
        sa.Column("mcp_auth_value_encrypted", sa.String(2000), nullable=True),
        sa.Column("mcp_protocol_version", sa.String(20), server_default="2024-11-05"),
        sa.Column("discovered_tools", postgresql.JSONB(), nullable=True),
        sa.Column("tools_last_discovered_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("permission_map", postgresql.JSONB(), nullable=True),
        sa.Column("data_classification", sa.String(20), server_default="internal"),
        sa.Column("status", sa.String(20), server_default="sandbox"),
        sa.Column("available_to_roles", postgresql.JSONB(), server_default='["all"]'),
        sa.Column("requires_approval", sa.Boolean(), server_default=sa.text("false")),
        sa.Column("health_status", sa.String(20), server_default="unknown"),
        sa.Column("health_last_checked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("health_latency_ms", sa.Integer(), nullable=True),
        sa.Column("health_error_count_24h", sa.Integer(), server_default="0"),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now(), nullable=False),
    )

    op.create_table(
        "service_oauth_config",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), primary_key=True),
        sa.Column("service_id", sa.String(50), sa.ForeignKey("service_registry.service_id", ondelete="CASCADE"), nullable=False),
        sa.Column("client_id", sa.String(500), nullable=False),
        sa.Column("client_secret_encrypted", sa.String(2000), nullable=False),
        sa.Column("auth_url", sa.String(500), nullable=True),
        sa.Column("token_url", sa.String(500), nullable=True),
        sa.Column("scopes", postgresql.ARRAY(sa.Text()), nullable=True),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now(), nullable=False),
        sa.UniqueConstraint("service_id", "organization_id", name="uq_oauth_config_service_org"),
    )

    op.create_table(
        "delegation_templates",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), primary_key=True),
        sa.Column("agent_id", sa.String(100), nullable=False, index=True),
        sa.Column("max_permissions", postgresql.JSONB(), nullable=False),
        sa.Column("blocked_permissions", postgresql.JSONB(), server_default="[]"),
        sa.Column("default_ttl_days", sa.Integer(), server_default="7"),
        sa.Column("available_to_roles", postgresql.JSONB(), server_default='["all"]'),
        sa.Column("max_actions_per_day", sa.Integer(), nullable=True),
        sa.Column("working_hours_start", sa.Time(), nullable=True),
        sa.Column("working_hours_end", sa.Time(), nullable=True),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("created_by", sa.String(200), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now(), nullable=False),
    )

    # --- Modify existing tables ---

    op.add_column(
        "user_sessions",
        sa.Column("role", sa.String(20), server_default="employee", nullable=False),
    )

    op.add_column(
        "delegation_tokens",
        sa.Column(
            "template_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("delegation_templates.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )
    op.add_column(
        "delegation_tokens",
        sa.Column("source", sa.String(20), server_default="manual", nullable=False),
    )


def downgrade() -> None:
    op.drop_column("delegation_tokens", "source")
    op.drop_column("delegation_tokens", "template_id")
    op.drop_column("user_sessions", "role")
    op.drop_table("delegation_templates")
    op.drop_table("service_oauth_config")
    op.drop_table("service_registry")
