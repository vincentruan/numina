"""add_auto_trigger_fields_to_blind_box_draws

Revision ID: 564e56b7643c
Revises: l3502n85mjh2
Create Date: 2026-05-12 12:45:56.355263

"""
from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = '564e56b7643c'
down_revision: Union[str, None] = 'l3502n85mjh2'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('blind_box_draws', sa.Column('is_auto_triggered', sa.Boolean(), nullable=False, server_default=sa.false()))
    op.add_column('blind_box_draws', sa.Column('shown_to_child', sa.Boolean(), nullable=False, server_default=sa.false()))


def downgrade() -> None:
    op.drop_column('blind_box_draws', 'shown_to_child')
    op.drop_column('blind_box_draws', 'is_auto_triggered')
