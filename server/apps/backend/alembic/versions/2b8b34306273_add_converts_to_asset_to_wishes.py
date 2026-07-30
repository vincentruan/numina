"""add converts_to_asset to wishes

Revision ID: 2b8b34306273
Revises: 724957cc6de9
Create Date: 2026-05-03 17:28:39.203541

"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = '2b8b34306273'
down_revision: str | None = '724957cc6de9'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column('wishes', sa.Column('converts_to_asset', sa.Boolean(), server_default='1', nullable=False))


def downgrade() -> None:
    op.drop_column('wishes', 'converts_to_asset')
