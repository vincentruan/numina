"""add markdown_file_path to ai_reports

Revision ID: 538588b30845
Revises: 936d56ebc0ea
Create Date: 2026-06-11 18:58:37.730890

"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = '538588b30845'
down_revision: str | None = '936d56ebc0ea'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Fresh-DB guard: bootstrap creates ai_reports with markdown_file_path already.
    bind = op.get_bind()
    cols = {c['name'] for c in bind.dialect.get_columns(bind, 'ai_reports')} if bind.dialect.has_table(bind, 'ai_reports') else set()
    if 'markdown_file_path' not in cols:
        # Only add the markdown_file_path column to ai_reports
        op.add_column('ai_reports', sa.Column('markdown_file_path', sa.String(length=255), nullable=True))


def downgrade() -> None:
    # Only remove the markdown_file_path column from ai_reports
    op.drop_column('ai_reports', 'markdown_file_path')