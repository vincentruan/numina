"""add_core_earn_loop_chores_coins

Revision ID: 0ba0aea34839
Revises: a1b2c3d4e5f7
Create Date: 2026-04-15 14:49:17.769024

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = '0ba0aea34839'
down_revision: Union[str, None] = 'a1b2c3d4e5f7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_context().connection
    inspector = sa.inspect(conn)
    existing_tables = set(inspector.get_table_names())

    if 'chore_templates' not in existing_tables:
        op.create_table(
            'chore_templates',
            sa.Column('id', sa.String(36), primary_key=True),
            sa.Column('family_id', sa.String(36), sa.ForeignKey('families.id'), nullable=False),
            sa.Column('created_by', sa.String(36), sa.ForeignKey('users.id'), nullable=False),
            sa.Column('name', sa.String(100), nullable=False),
            sa.Column('emoji', sa.String(10), nullable=True),
            sa.Column('coin_reward', sa.Integer(), nullable=False),
            sa.Column('frequency', sa.String(10), nullable=False),
            sa.Column('assignment_type', sa.String(10), nullable=False),
            sa.Column('is_active', sa.Boolean(), nullable=False, server_default=sa.true()),
            sa.Column('created_at', sa.DateTime(), server_default=sa.func.now()),
            sa.Column('updated_at', sa.DateTime(), server_default=sa.func.now()),
        )

    if 'chore_template_assignees' not in existing_tables:
        op.create_table(
            'chore_template_assignees',
            sa.Column('template_id', sa.String(36), sa.ForeignKey('chore_templates.id'), primary_key=True),
            sa.Column('child_user_id', sa.String(36), sa.ForeignKey('users.id'), primary_key=True),
        )

    if 'chore_instances' not in existing_tables:
        op.create_table(
            'chore_instances',
            sa.Column('id', sa.String(36), primary_key=True),
            sa.Column('template_id', sa.String(36), sa.ForeignKey('chore_templates.id'), nullable=False),
            sa.Column('family_id', sa.String(36), sa.ForeignKey('families.id'), nullable=False),
            sa.Column('child_user_id', sa.String(36), sa.ForeignKey('users.id'), nullable=False),
            sa.Column('chore_name', sa.String(100), nullable=False),
            sa.Column('chore_emoji', sa.String(10), nullable=True),
            sa.Column('coin_reward', sa.Integer(), nullable=False),
            sa.Column('date_bucket', sa.String(10), nullable=False),
            sa.Column('status', sa.String(20), nullable=False, server_default='available'),
            sa.Column('submitted_at', sa.DateTime(), nullable=True),
            sa.Column('approved_at', sa.DateTime(), nullable=True),
            sa.Column('streak_count', sa.Integer(), nullable=False, server_default='0'),
            sa.Column('streak_bonus', sa.Integer(), nullable=False, server_default='0'),
            sa.UniqueConstraint('template_id', 'child_user_id', 'date_bucket', name='uq_chore_instance'),
        )

    if 'coin_transactions' not in existing_tables:
        op.create_table(
            'coin_transactions',
            sa.Column('id', sa.String(36), primary_key=True),
            sa.Column('family_id', sa.String(36), sa.ForeignKey('families.id'), nullable=False),
            sa.Column('child_user_id', sa.String(36), sa.ForeignKey('users.id'), nullable=False),
            sa.Column('amount', sa.Integer(), nullable=False),
            sa.Column('transaction_type', sa.String(20), nullable=False),
            sa.Column('ref_id', sa.String(36), nullable=True),
            sa.Column('narrative', sa.Text(), nullable=True),
            sa.Column('narrative_emoji', sa.String(20), nullable=True),
            sa.Column('streak_bonus', sa.Integer(), nullable=False, server_default='0'),
            sa.Column('created_at', sa.DateTime(), server_default=sa.func.now(), nullable=False),
            sa.UniqueConstraint('ref_id', 'transaction_type', name='uq_coin_tx_ref_type'),
        )

    # Add auto_approve_hours to families if not present
    families_cols = {c['name'] for c in inspector.get_columns('families')}
    if 'auto_approve_hours' not in families_cols:
        with op.batch_alter_table('families') as batch_op:
            batch_op.add_column(sa.Column('auto_approve_hours', sa.Integer(), nullable=False, server_default='24'))


def downgrade() -> None:
    with op.batch_alter_table('families') as batch_op:
        batch_op.drop_column('auto_approve_hours')
    op.drop_table('coin_transactions')
    op.drop_table('chore_instances')
    op.drop_table('chore_template_assignees')
    op.drop_table('chore_templates')
