"""add_manifesto_rejection

Revision ID: 05b3d24d6b98
Revises: c7timestz01
Create Date: 2026-09-08 10:49:55.464234

"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

import packages.db.session

# revision identifiers, used by Alembic.
revision: str = '05b3d24d6b98'
down_revision: str | None = 'c7timestz01'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table('manifesto_rejection',
    sa.Column('id', sa.BigInteger(), nullable=False),
    sa.Column('version_id', sa.BigInteger(), nullable=False),
    sa.Column('user_id', sa.BigInteger(), nullable=False),
    sa.Column('reason', sa.Text(), nullable=True),
    sa.Column('created_at', packages.db.session.UTCDateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('version_id', 'user_id', name='uq_manifesto_rejection_version_user')
    )
    op.create_index(op.f('ix_manifesto_rejection_version_id'), 'manifesto_rejection', ['version_id'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_manifesto_rejection_version_id'), table_name='manifesto_rejection')
    op.drop_table('manifesto_rejection')
