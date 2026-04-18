"""add currency to liabilities and user settings

Revision ID: f4af635328aa
Revises: 8cf6b8081321
Create Date: 2026-03-25 10:56:53.661507

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'f4af635328aa'
down_revision: Union[str, None] = '8cf6b8081321'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_context().connection
    inspector = sa.inspect(conn)

    liab_cols = {c['name'] for c in inspector.get_columns('liabilities')}
    if 'currency' not in liab_cols:
        with op.batch_alter_table('liabilities', schema=None) as batch_op:
            batch_op.add_column(sa.Column('currency', sa.String(10), nullable=True))
        op.execute("UPDATE liabilities SET currency = 'CNY' WHERE currency IS NULL")

    user_cols = {c['name'] for c in inspector.get_columns('users')}
    new_user_cols = {'theme', 'language', 'default_currency', 'view_mode'} - user_cols
    if new_user_cols:
        with op.batch_alter_table('users', schema=None) as batch_op:
            if 'theme' not in user_cols:
                batch_op.add_column(sa.Column('theme', sa.String(20), nullable=True))
            if 'language' not in user_cols:
                batch_op.add_column(sa.Column('language', sa.String(10), nullable=True))
            if 'default_currency' not in user_cols:
                batch_op.add_column(sa.Column('default_currency', sa.String(10), nullable=True))
            if 'view_mode' not in user_cols:
                batch_op.add_column(sa.Column('view_mode', sa.String(20), nullable=True))
        # Backfill defaults only for newly added columns to avoid overwriting
        # existing user preferences when only a subset of columns was missing.
        set_parts = []
        if 'theme' not in user_cols:
            set_parts.append("theme = 'light'")
        if 'language' not in user_cols:
            set_parts.append("language = 'zh-CN'")
        if 'default_currency' not in user_cols:
            set_parts.append("default_currency = 'CNY'")
        if 'view_mode' not in user_cols:
            set_parts.append("view_mode = 'card'")
        if set_parts:
            first_col = set_parts[0].split(' = ')[0]
            op.execute(f"UPDATE users SET {', '.join(set_parts)} WHERE {first_col} IS NULL")


def downgrade() -> None:
    with op.batch_alter_table('liabilities', schema=None) as batch_op:
        batch_op.drop_column('currency')

    with op.batch_alter_table('users', schema=None) as batch_op:
        batch_op.drop_column('view_mode')
        batch_op.drop_column('default_currency')
        batch_op.drop_column('language')
        batch_op.drop_column('theme')