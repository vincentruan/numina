"""split_connection_and_thinking_tests

Revision ID: c5724f07ecb4
Revises: b1c2d3e4f5a6
Create Date: 2026-04-27 19:40:50.197443

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = 'c5724f07ecb4'
down_revision: Union[str, None] = 'b1c2d3e4f5a6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Rename old columns to new structure for families table
    # Drop old columns first
    with op.batch_alter_table('families', schema=None) as batch_op:
        batch_op.drop_column('ai_test_success')
        batch_op.drop_column('ai_test_supports_thinking')
        batch_op.drop_column('ai_test_supports_image')

    # Add new columns for split tests
    with op.batch_alter_table('families', schema=None) as batch_op:
        # Connection test fields
        batch_op.add_column(sa.Column('ai_test_connected', sa.Boolean(), nullable=True))
        batch_op.add_column(sa.Column('ai_test_message', sa.Text(), nullable=True))
        batch_op.add_column(sa.Column('ai_test_latency_ms', sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column('ai_test_timestamp', sa.DateTime(), nullable=True))
        # Thinking test fields
        batch_op.add_column(sa.Column('ai_test_thinking_success', sa.Boolean(), nullable=True))
        batch_op.add_column(sa.Column('ai_test_thinking_message', sa.Text(), nullable=True))
        batch_op.add_column(sa.Column('ai_test_thinking_latency_ms', sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column('ai_test_thinking_timestamp', sa.DateTime(), nullable=True))
        # Vision test fields
        batch_op.add_column(sa.Column('ai_vision_test_success', sa.Boolean(), nullable=True))
        batch_op.add_column(sa.Column('ai_vision_test_message', sa.Text(), nullable=True))
        batch_op.add_column(sa.Column('ai_vision_test_latency_ms', sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column('ai_vision_test_timestamp', sa.DateTime(), nullable=True))


def downgrade() -> None:
    # Drop new columns
    with op.batch_alter_table('families', schema=None) as batch_op:
        batch_op.drop_column('ai_test_connected')
        batch_op.drop_column('ai_test_message')
        batch_op.drop_column('ai_test_latency_ms')
        batch_op.drop_column('ai_test_timestamp')
        batch_op.drop_column('ai_test_thinking_success')
        batch_op.drop_column('ai_test_thinking_message')
        batch_op.drop_column('ai_test_thinking_latency_ms')
        batch_op.drop_column('ai_test_thinking_timestamp')
        batch_op.drop_column('ai_vision_test_success')
        batch_op.drop_column('ai_vision_test_message')
        batch_op.drop_column('ai_vision_test_latency_ms')
        batch_op.drop_column('ai_vision_test_timestamp')

    # Add back old columns
    with op.batch_alter_table('families', schema=None) as batch_op:
        batch_op.add_column(sa.Column('ai_test_success', sa.Boolean(), nullable=True))
        batch_op.add_column(sa.Column('ai_test_supports_thinking', sa.Boolean(), nullable=True))
        batch_op.add_column(sa.Column('ai_test_supports_image', sa.Boolean(), nullable=True))