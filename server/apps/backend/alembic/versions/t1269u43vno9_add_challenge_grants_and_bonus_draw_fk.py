"""add challenge_grants table and source_challenge_id to bonus_draws

Revision ID: t1269u43vno9
Revises: s0158t32umn8
Create Date: 2026-05-19

Adds:
- challenge_grants table with all fields
- bonus_draws.source_challenge_id FK nullable
"""

import sqlalchemy as sa

from alembic import op

revision = 't1269u43vno9'
down_revision = 's0158t32umn8'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create challenge_grants table
    op.create_table(
        'challenge_grants',
        sa.Column('id', sa.BigInteger(), nullable=False),
        sa.Column('family_id', sa.BigInteger(), sa.ForeignKey('families.id'), nullable=False),
        sa.Column('child_user_id', sa.BigInteger(), sa.ForeignKey('users.id'), nullable=False),
        sa.Column('target_type', sa.String(20), nullable=False),
        sa.Column('target_value', sa.Integer(), nullable=False),
        sa.Column('chore_template_id', sa.BigInteger(), sa.ForeignKey('chore_templates.id'), nullable=True),
        sa.Column('current_progress', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('deadline', sa.DateTime(), nullable=False),
        sa.Column('message', sa.String(100), nullable=True),
        sa.Column('status', sa.String(20), nullable=False, server_default='active'),
        sa.Column('completed_at', sa.DateTime(), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.func.now()),
        sa.PrimaryKeyConstraint('id'),
        sa.CheckConstraint(
            "status IN ('active', 'completed', 'expired', 'cancelled')",
            name="ck_challenge_grant_status",
        ),
        sa.CheckConstraint(
            "target_type IN ('task_count', 'streak_length', 'specific_chore', 'star_earnings')",
            name="ck_challenge_grant_target_type",
        ),
    )

    # Add source_challenge_id to bonus_draws
    op.add_column(
        'bonus_draws',
        sa.Column(
            'source_challenge_id',
            sa.BigInteger(),
            sa.ForeignKey('challenge_grants.id'),
            nullable=True,
        ),
    )


def downgrade() -> None:
    # Drop source_challenge_id from bonus_draws
    op.drop_column('bonus_draws', 'source_challenge_id')

    # Drop challenge_grants table
    op.drop_table('challenge_grants')