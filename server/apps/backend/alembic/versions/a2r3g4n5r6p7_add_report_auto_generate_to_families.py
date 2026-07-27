"""add_report_auto_generate_enabled_to_families

Revision ID: a2r3g4n5r6p7
Revises: 1dc1e56027af
Create Date: 2026-07-27 10:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
from sqlalchemy import inspect
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a2r3g4n5r6p7'
down_revision: Union[str, None] = '1dc1e56027af'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _has_column(table: str, column: str) -> bool:
    bind = op.get_bind()
    insp = inspect(bind)
    cols = [c["name"] for c in insp.get_columns(table)]
    return column in cols


def upgrade() -> None:
    if not _has_column("families", "report_auto_generate_enabled"):
        op.add_column(
            "families",
            sa.Column(
                "report_auto_generate_enabled",
                sa.Boolean(),
                nullable=False,
                server_default=sa.text("false"),
            ),
        )


def downgrade() -> None:
    if _has_column("families", "report_auto_generate_enabled"):
        op.drop_column("families", "report_auto_generate_enabled")
