"""drop_ai_ws_tickets_table

Revision ID: 936d56ebc0ea
Revises: c7896d99es4
Create Date: 2026-06-09 21:25:03.337312

"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = '936d56ebc0ea'
down_revision: str | None = 'c7896d99es4'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.drop_table('ai_ws_tickets')


def downgrade() -> None:
    op.create_table(
        'ai_ws_tickets',
        sa.Column('id', sa.BigInteger(), nullable=False),
        sa.Column('user_id', sa.BigInteger(), nullable=False),
        sa.Column('family_id', sa.BigInteger(), nullable=False),
        sa.Column('expires_at', sa.DateTime(), nullable=False),
        sa.Column('used', sa.Boolean(), nullable=False, server_default='0'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id']),
        sa.ForeignKeyConstraint(['family_id'], ['families.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_ai_ws_tickets_user_id', 'ai_ws_tickets', ['user_id'])