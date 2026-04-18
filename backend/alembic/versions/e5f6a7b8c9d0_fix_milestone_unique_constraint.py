"""fix_milestone_unique_constraint

Remove the global unique constraint on (child_user_id, milestone_type) which
incorrectly prevents per-cycle streak milestones (streak_7, streak_14, streak_30)
from being re-triggered after a streak reset. Uniqueness for once-per-child
milestone types is enforced at the application layer in _try_record_once().

Revision ID: e5f6a7b8c9d0
Revises: d4e5f6a7b8c9
Create Date: 2026-04-16 12:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = 'e5f6a7b8c9d0'
down_revision: Union[str, None] = 'd4e5f6a7b8c9'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_context().connection
    inspector = sa.inspect(conn)
    constraints = {c['name'] for c in inspector.get_unique_constraints('child_milestones')}
    if 'uq_child_milestone_type' in constraints:
        with op.batch_alter_table('child_milestones') as batch_op:
            batch_op.drop_constraint('uq_child_milestone_type', type_='unique')


def downgrade() -> None:
    with op.batch_alter_table('child_milestones') as batch_op:
        batch_op.create_unique_constraint(
            'uq_child_milestone_type', ['child_user_id', 'milestone_type']
        )
