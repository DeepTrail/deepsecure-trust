"""Add created_via and llm_provider to agent_sessions.

Tracks how each session was created (bootstrap_gcp, challenge_response, etc.)
and which LLM provider was used (gemini, claude, codex). Both nullable so
existing rows are unaffected.

Revision ID: l2m3n4o5p6
Revises: k1l2m3n4o5
Create Date: 2026-06-16
"""

from alembic import op
import sqlalchemy as sa

revision = "l2m3n4o5p6"
down_revision = "k1l2m3n4o5"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "agent_sessions",
        sa.Column(
            "created_via",
            sa.String(64),
            nullable=True,
            comment="How this session was created (bootstrap_gcp, challenge_response, etc.)",
        ),
    )
    op.add_column(
        "agent_sessions",
        sa.Column(
            "llm_provider",
            sa.String(32),
            nullable=True,
            comment="LLM provider used (gemini, claude, codex)",
        ),
    )


def downgrade() -> None:
    op.drop_column("agent_sessions", "llm_provider")
    op.drop_column("agent_sessions", "created_via")
