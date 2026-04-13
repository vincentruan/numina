"""add ai_model_id and ai_vision_model_id to families

Revision ID: 2a9cb7dc0b62
Revises: f9b8ebd8a99b
Create Date: 2026-04-13 13:02:19.331658

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = '2a9cb7dc0b62'
down_revision: Union[str, None] = 'f9b8ebd8a99b'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('families', sa.Column('ai_model_id', sa.String(length=100), nullable=True))
    op.add_column('families', sa.Column('ai_vision_model_id', sa.String(length=100), nullable=True))


def downgrade() -> None:
    op.drop_column('families', 'ai_vision_model_id')
    op.drop_column('families', 'ai_model_id')
