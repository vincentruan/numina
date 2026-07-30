"""add_skill_creation_type_and_source_url

Revision ID: 4637e33e94ac
Revises: d9b3f8e1a2c5
Create Date: 2026-05-31 13:17:33.224049

"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = '4637e33e94ac'
down_revision: str | None = 'd9b3f8e1a2c5'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column('ai_skills', sa.Column('creation_type', sa.String(length=16), server_default='manual', nullable=False))
    op.add_column('ai_skills', sa.Column('source_url', sa.String(length=512), nullable=True))


def downgrade() -> None:
    op.drop_column('ai_skills', 'source_url')
    op.drop_column('ai_skills', 'creation_type')
