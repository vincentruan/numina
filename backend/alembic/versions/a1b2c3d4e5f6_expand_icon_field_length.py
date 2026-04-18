"""expand icon field length for SVG icon IDs

Revision ID: a1b2c3d4e5f6
Revises: f4af635328aa
Create Date: 2026-04-05 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'icon_len_001'
down_revision: Union[str, None] = 'f4af635328aa'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Expand icon field from String(10) to String(50) to accommodate icon ID format
    # e.g., "icon-home" instead of emoji "🏠"
    # Use batch_alter_table for SQLite compatibility
    with op.batch_alter_table('categories', schema=None) as batch_op:
        batch_op.alter_column(
            'icon',
            existing_type=sa.String(10),
            type_=sa.String(50),
            existing_nullable=False
        )


def downgrade() -> None:
    # Revert icon field back to String(10)
    # Note: This will fail if any icon values are longer than 10 characters
    with op.batch_alter_table('categories', schema=None) as batch_op:
        batch_op.alter_column(
            'icon',
            existing_type=sa.String(50),
            type_=sa.String(10),
            existing_nullable=False
        )