"""add skill_registry table

Revision ID: u1470x53wpq8
Revises: t1269u43vno9
Create Date: 2026-05-20

Adds:
- skill_registry table with all fields for per-family skill configuration
"""

import sqlalchemy as sa
from alembic import op

revision = 'u1470x53wpq8'
down_revision = 't1269u43vno9'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'skill_registry',
        sa.Column('id', sa.BigInteger, primary_key=True),
        sa.Column('family_id', sa.BigInteger, nullable=False, index=True),
        sa.Column('skill_id', sa.String(64), nullable=False),
        sa.Column('skill_type', sa.String(16), nullable=False),
        sa.Column('name', sa.String(128), nullable=True),
        sa.Column('description', sa.String(512), nullable=True),
        sa.Column('icon', sa.String(32), nullable=True),
        sa.Column('color', sa.String(16), nullable=True),
        sa.Column('route', sa.String(64), nullable=True),
        sa.Column('input_mode', sa.String(16), nullable=True, server_default='trigger'),
        sa.Column('placeholder', sa.String(256), nullable=True),
        sa.Column('examples', sa.JSON, nullable=True),
        sa.Column('is_enabled', sa.Boolean, nullable=False, server_default=sa.true()),
        sa.Column('display_order', sa.Integer, nullable=False, server_default=sa.text('0')),
        sa.Column('custom_prompt', sa.Text, nullable=True),
        sa.Column('created_at', sa.DateTime, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime, server_default=sa.func.now(), onupdate=sa.func.now()),
        sa.Column('created_by', sa.BigInteger, nullable=True),
        sa.UniqueConstraint('family_id', 'skill_id', name='uq_skill_registry_family_skill'),
    )
    op.create_index(
        'idx_skill_registry_order',
        'skill_registry',
        ['family_id', 'display_order'],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index('idx_skill_registry_order', table_name='skill_registry')
    op.drop_table('skill_registry')
