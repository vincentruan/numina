"""merge learning branch heads

Revision ID: mrg001lrnheads
Revises: mc001misc0003, mpx001, tb001crp0001
Create Date: 2026-11-18

mc001misc0003, mpx001 and tb001crp0001 all descend from the same
(h0011q22r3s4, rwc001) merge point but were never merged back together,
leaving three independent heads. ``alembic upgrade head`` refuses to run
with multiple heads, so operators had to name a branch explicitly — and
each single branch silently skipped the other two branches' tables.

No DDL: this revision only reconnects the graph.
"""
from collections.abc import Sequence

revision: str = "mrg001lrnheads"
down_revision: tuple[str, ...] = (
    "mc001misc0003",
    "mpx001",
    "tb001crp0001",
)  # type: ignore[assignment]
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
