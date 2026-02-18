"""Add connected_services table for OAuth token reference storage.

Revision ID: 8b5c2d3e4f6a
Revises: 3695f3bddaa9
Create Date: 2026-02-17

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '8b5c2d3e4f6a'
down_revision = '3695f3bddaa9'
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Create connected_services table for storing OAuth token references."""
    op.create_table(
        'connected_services',
        sa.Column('id', sa.String(64), primary_key=True, comment='Unique connection identifier (e.g., conn-<uuid>)'),
        sa.Column('user_id', sa.String(255), nullable=False, index=True, comment='User identifier, typically email (e.g., sarah@acme.com)'),
        sa.Column('service_id', sa.String(64), nullable=False, index=True, comment='Backend service identifier (e.g., notion, slack, hubspot)'),
        sa.Column('service_name', sa.String(128), nullable=True, comment='Human-readable service name (e.g., Notion, Slack)'),
        sa.Column('oauth_token_ref', sa.String(512), nullable=False, comment='Reference to OAuth token in vault (e.g., vault://sarah-notion-oauth-xyz)'),
        sa.Column('scopes_granted', postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default='[]', comment='Scopes granted during OAuth consent'),
        sa.Column('organization_id', sa.String(64), nullable=True, index=True, comment='Organization identifier for multi-tenant deployments'),
        sa.Column('connected_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now(), comment='Timestamp when the service was connected'),
        sa.Column('disconnected_at', sa.DateTime(timezone=True), nullable=True, comment='Timestamp when the service was disconnected (NULL if still connected)'),
        sa.Column('last_used_at', sa.DateTime(timezone=True), nullable=True, comment='Timestamp when this connection was last used'),
        sa.UniqueConstraint('user_id', 'service_id', name='uq_user_service'),
    )

    # Create additional indexes
    op.create_index('ix_connected_service_user_service', 'connected_services', ['user_id', 'service_id'])
    op.create_index('ix_connected_service_org', 'connected_services', ['organization_id'])


def downgrade() -> None:
    """Drop connected_services table."""
    op.drop_index('ix_connected_service_org', table_name='connected_services')
    op.drop_index('ix_connected_service_user_service', table_name='connected_services')
    op.drop_table('connected_services')
