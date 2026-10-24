"""add description_zh to preset_learning_paths

Revision ID: e805c16f361a
Revises: lrnprst00001
Create Date: 2026-10-19 19:58:00.377908

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = 'e805c16f361a'
down_revision: Union[str, None] = 'lrnprst00001'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('preset_learning_paths', sa.Column('description_zh', sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column('preset_learning_paths', 'description_zh')
