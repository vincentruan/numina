"""add timeout_seconds to ai_provider_configs

Revision ID: g8057i30hfe7
Revises: 3ec41c70c529
Create Date: 2026-05-03 10:00:00.000000

Adds:
- ai_provider_configs.timeout_seconds (integer, default 60, nullable)

Note: down_revision changed from f7946h29ged6 to 3ec41c70c529. The
ai_provider_configs table is created by 3ec41c70c529 (add_new_er_tables),
which was a parallel branch from f7946h29ged6. With the original
down_revision=f7946h29ged6, Alembic ran this migration BEFORE 3ec41c70c529
on a fresh DB (branch B before branch A), so add_column failed with
"no such table: ai_provider_configs". Pointing at 3ec41c70c529 ensures the
table exists first. The merge 724957cc6de9 still joins ac070c6b7aaf (child of
3ec41c70c529) and g8057i30hfe7 (now also child of 3ec41c70c529).
"""

import sqlalchemy as sa
from alembic import op

revision = 'g8057i30hfe7'
down_revision = '3ec41c70c529'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        'ai_provider_configs',
        sa.Column('timeout_seconds', sa.Integer(), nullable=True, server_default='60'),
    )


def downgrade() -> None:
    op.drop_column('ai_provider_configs', 'timeout_seconds')
