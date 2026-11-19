"""add description_zh to preset_learning_paths

Revision ID: e805c16f361a
Revises: lrnprst00001
Create Date: 2026-10-19 19:58:00.377908

"""
from typing import Sequence, Union

import sqlalchemy as sa

from apps.backend.alembic import ddl

# revision identifiers, used by Alembic.
revision: str = 'e805c16f361a'
down_revision: Union[str, None] = 'lrnprst00001'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    ddl.add_column('preset_learning_paths', sa.Column('description_zh', sa.Text(), nullable=True))


def downgrade() -> None:
    ddl.drop_column('preset_learning_paths', 'description_zh')
