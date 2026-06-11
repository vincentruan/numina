"""add markdown_file_path to ai_reports

Revision ID: 538588b30845
Revises: 936d56ebc0ea
Create Date: 2026-06-11 18:58:37.730890

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '538588b30845'
down_revision: Union[str, None] = '936d56ebc0ea'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Only add the markdown_file_path column to ai_reports
    op.add_column('ai_reports', sa.Column('markdown_file_path', sa.String(length=255), nullable=True))


def downgrade() -> None:
    # Only remove the markdown_file_path column from ai_reports
    op.drop_column('ai_reports', 'markdown_file_path')