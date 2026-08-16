"""merge_avatar_and_task_tracking_heads

Revision ID: 69689ce5e420
Revises: ua1v2a3t4r5u, x9876y54zqr0
Create Date: 2026-08-16 16:15:56.280825

"""
from collections.abc import Sequence

# revision identifiers, used by Alembic.
revision: str = "69689ce5e420"
down_revision: str | tuple[str, ...] | None = ("ua1v2a3t4r5u", "x9876y54zqr0")
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass