"""add submitted_by_user_id to chore_instances

Revision ID: j1k2l3m4n5o6
Revises: h8i9j0k1l2m3
Create Date: 2026-04-18 08:30:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = 'j1k2l3m4n5o6'
down_revision: Union[str, None] = 'i9j0k1l2m3n4'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_context().connection
    inspector = sa.inspect(conn)
    existing_cols = {c['name'] for c in inspector.get_columns('chore_instances')}
    if 'submitted_by_user_id' not in existing_cols:
        with op.batch_alter_table('chore_instances') as batch_op:
            batch_op.add_column(
                sa.Column(
                    'submitted_by_user_id',
                    sa.String(36),
                    sa.ForeignKey('users.id'),
                    nullable=True,
                    comment='Actual child who submitted — needed for pool chores where child_user_id is family_id',
                )
            )


def downgrade() -> None:
    with op.batch_alter_table('chore_instances') as batch_op:
        batch_op.drop_column('submitted_by_user_id')
