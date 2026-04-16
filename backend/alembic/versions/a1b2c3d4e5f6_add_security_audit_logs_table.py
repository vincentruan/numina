"""add security_audit_logs table

Revision ID: a1b2c3d4e5f6
Revises: fffd4c754ec1
Create Date: 2026-04-16 09:00:00.000000

"""
from __future__ import annotations

from typing import Union

import sqlalchemy as sa
from alembic import op

revision: str = 'a1b2c3d4e5f6'
down_revision: Union[str, None] = 'fffd4c754ec1'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'security_audit_logs',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('event_type', sa.String(64), nullable=False, index=True),
        sa.Column('user_id', sa.String(36), nullable=True, index=True),
        sa.Column('family_id', sa.String(36), nullable=True, index=True),
        sa.Column('ip_address', sa.String(45), nullable=True),
        sa.Column('user_agent', sa.String(512), nullable=True),
        sa.Column('outcome', sa.String(16), nullable=False),
        sa.Column('detail', sa.Text, nullable=True),
        sa.Column('created_at', sa.DateTime, server_default=sa.func.now(), nullable=False, index=True),
    )


def downgrade() -> None:
    op.drop_table('security_audit_logs')
