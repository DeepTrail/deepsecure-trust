"""Add platform and selector to agents, make public_key nullable.

Revision ID: p4a1b2c3d4e5
Revises: e5f6a7b8c9d0
Create Date: 2026-05-16

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers
revision = 'p4a1b2c3d4e5'
down_revision = 'e5f6a7b8c9d0'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('agents', sa.Column('platform', sa.String(64), nullable=True))
    op.add_column('agents', sa.Column('selector', sa.String(255), nullable=True))
    op.create_unique_constraint('uq_agents_selector', 'agents', ['selector'])
    op.alter_column('agents', 'public_key', nullable=True)


def downgrade():
    op.alter_column('agents', 'public_key', nullable=False)
    op.drop_constraint('uq_agents_selector', 'agents', type_='unique')
    op.drop_column('agents', 'selector')
    op.drop_column('agents', 'platform')
