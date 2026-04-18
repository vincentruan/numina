"""add image_url to asset

Revision ID: 50672c82a858
Revises:
Create Date: 2026-03-21 00:35:52.065587

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '50672c82a858'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_context().connection
    inspector = sa.inspect(conn)
    cols = {c['name'] for c in inspector.get_columns('assets')}
    if 'image_url' not in cols:
        op.add_column('assets', sa.Column('image_url', sa.String(length=500), nullable=True))


def downgrade() -> None:
    op.drop_column('assets', 'image_url')