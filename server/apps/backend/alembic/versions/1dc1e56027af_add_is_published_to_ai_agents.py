"""add_is_published_to_ai_agents

Revision ID: 1dc1e56027af
Revises: s1k2l3m4n5o6
Create Date: 2026-07-26 20:44:17.170176

"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = '1dc1e56027af'
down_revision: str | None = 's1k2l3m4n5o6'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "ai_agents",
        sa.Column(
            "is_published",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
    )


def downgrade() -> None:
    op.drop_column("ai_agents", "is_published")