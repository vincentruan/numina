"""add vision text test fields to families

Revision ID: d6835g18fdc5
Revises: c5724f07ecb4
Create Date: 2026-04-28 10:00:00.000000

"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = 'd6835g18fdc5'
down_revision: str | None = 'c5724f07ecb4'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table('families', schema=None) as batch_op:
        batch_op.add_column(sa.Column('ai_vision_text_test_success', sa.Boolean(), nullable=True))
        batch_op.add_column(sa.Column('ai_vision_text_test_message', sa.Text(), nullable=True))
        batch_op.add_column(sa.Column('ai_vision_text_test_latency_ms', sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column('ai_vision_text_test_timestamp', sa.DateTime(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table('families', schema=None) as batch_op:
        batch_op.drop_column('ai_vision_text_test_success')
        batch_op.drop_column('ai_vision_text_test_message')
        batch_op.drop_column('ai_vision_text_test_latency_ms')
        batch_op.drop_column('ai_vision_text_test_timestamp')
