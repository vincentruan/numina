"""add timeout_seconds to ai_provider_configs

Revision ID: g8057i30hfe7
Revises: f7946h29ged6
Create Date: 2026-05-03 10:00:00.000000

Adds:
- ai_provider_configs.timeout_seconds (integer, default 60, nullable)
"""

from alembic import op
import sqlalchemy as sa

revision = 'g8057i30hfe7'
down_revision = 'f7946h29ged6'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        'ai_provider_configs',
        sa.Column('timeout_seconds', sa.Integer(), nullable=True, server_default='60'),
    )


def downgrade() -> None:
    op.drop_column('ai_provider_configs', 'timeout_seconds')
