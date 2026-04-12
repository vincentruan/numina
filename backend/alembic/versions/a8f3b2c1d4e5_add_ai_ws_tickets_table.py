"""add ai_ws_tickets table

Revision ID: a8f3b2c1d4e5
Revises: fffd4c754ec1
Create Date: 2026-04-13 00:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = 'a8f3b2c1d4e5'
down_revision: Union[str, None] = 'c21c36dc5fbf'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Table may already exist if created by SQLAlchemy create_all() at startup
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if 'ai_ws_tickets' not in inspector.get_table_names():
        op.create_table(
            'ai_ws_tickets',
            sa.Column('id', sa.String(36), primary_key=True),
            sa.Column('user_id', sa.String(36), sa.ForeignKey('users.id'), nullable=False),
            sa.Column('family_id', sa.String(36), sa.ForeignKey('families.id'), nullable=False),
            sa.Column('expires_at', sa.DateTime(), nullable=False),
            sa.Column('used', sa.Boolean(), nullable=False, server_default=sa.false()),
        )
        op.create_index('ix_ai_ws_tickets_user_id', 'ai_ws_tickets', ['user_id'])


def downgrade() -> None:
    op.drop_index('ix_ai_ws_tickets_user_id', table_name='ai_ws_tickets')
    op.drop_table('ai_ws_tickets')
