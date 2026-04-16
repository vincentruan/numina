"""add_child_wish_table

Revision ID: f32c9ec07d5e
Revises: 2a9cb7dc0b62
Create Date: 2026-04-15 21:20:35.251704

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = 'f32c9ec07d5e'
down_revision: Union[str, None] = '0ba0aea34839'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'child_wishes',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('family_id', sa.String(length=36), nullable=False),
        sa.Column('child_user_id', sa.String(length=36), nullable=False),
        sa.Column('name', sa.String(length=50), nullable=False),
        sa.Column('description', sa.String(length=200), nullable=True),
        sa.Column('emoji', sa.String(length=10), nullable=True),
        sa.Column('priority', sa.String(length=10), nullable=False),
        sa.Column('status', sa.String(length=30), nullable=False),
        sa.Column('star_coin_cost', sa.Integer(), nullable=True),
        sa.Column('rejection_reason', sa.String(length=200), nullable=True),
        sa.Column('realized_asset_id', sa.String(length=36), nullable=True),
        sa.Column('star_coin_cost_history', sa.JSON(), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=False),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=False),
        sa.CheckConstraint("priority IN ('high', 'medium', 'low')", name='ck_child_wish_priority'),
        sa.CheckConstraint(
            "status IN ('pending_review', 'active', 'rejected', 'redemption_requested', 'realized')",
            name='ck_child_wish_status',
        ),
        sa.ForeignKeyConstraint(['child_user_id'], ['users.id']),
        sa.ForeignKeyConstraint(['family_id'], ['families.id']),
        sa.ForeignKeyConstraint(['realized_asset_id'], ['assets.id']),
        sa.PrimaryKeyConstraint('id'),
    )


def downgrade() -> None:
    op.drop_table('child_wishes')
