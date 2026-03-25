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
    # Add currency column to liabilities
    with op.batch_alter_table('liabilities', schema=None) as batch_op:
        batch_op.add_column(sa.Column('currency', sa.String(10), nullable=True))

    # Set default currency for existing liabilities
    op.execute("UPDATE liabilities SET currency = 'CNY' WHERE currency IS NULL")

    # Add user settings columns
    with op.batch_alter_table('users', schema=None) as batch_op:
        batch_op.add_column(sa.Column('theme', sa.String(20), nullable=True))
        batch_op.add_column(sa.Column('language', sa.String(10), nullable=True))
        batch_op.add_column(sa.Column('default_currency', sa.String(10), nullable=True))
        batch_op.add_column(sa.Column('view_mode', sa.String(20), nullable=True))

    # Set defaults for existing users
    op.execute("""
        UPDATE users SET
            theme = 'light',
            language = 'zh-CN',
            default_currency = 'CNY',
            view_mode = 'card'
        WHERE theme IS NULL
    """)


def downgrade() -> None:
    with op.batch_alter_table('liabilities', schema=None) as batch_op:
        batch_op.drop_column('currency')

    with op.batch_alter_table('users', schema=None) as batch_op:
        batch_op.drop_column('view_mode')
        batch_op.drop_column('default_currency')
        batch_op.drop_column('language')
        batch_op.drop_column('theme')