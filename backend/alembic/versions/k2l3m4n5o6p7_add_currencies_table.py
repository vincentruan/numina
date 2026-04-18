"""add currencies table

Revision ID: k2l3m4n5o6p7
Revises: j1k2l3m4n5o6
Create Date: 2026-04-18 12:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = 'k2l3m4n5o6p7'
down_revision: Union[str, None] = 'j1k2l3m4n5o6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_context().connection
    inspector = sa.inspect(conn)
    existing_tables = set(inspector.get_table_names())

    if 'currencies' not in existing_tables:
        op.create_table(
            'currencies',
            sa.Column('code', sa.String(10), primary_key=True),
            sa.Column('name_zh', sa.String(50), nullable=False),
            sa.Column('name_en', sa.String(50), nullable=False),
            sa.Column('symbol', sa.String(10), nullable=False),
            sa.Column('flag_emoji', sa.String(10), nullable=False),
            sa.Column('is_favorite', sa.Boolean(), nullable=False, server_default=sa.text('0')),
            sa.Column('sort_order', sa.Integer(), nullable=False, server_default=sa.text('999')),
        )


def downgrade() -> None:
    op.drop_table('currencies', if_exists=True)