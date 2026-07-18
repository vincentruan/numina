"""Drop 5 trigger skill tables + ai_allocation_targets (U7)

Revision ID: d7b2c4e9f108
Revises: c3a1f5e7d901
Create Date: 2026-07-18

U7 of the two-AI-apps unified dispatch refactor deletes the 5 外扩 trigger skills
(alerts/allocation/disposal/liability/spending_leak) full-stack plus the
``ai_allocation_targets`` table that backed the allocation-drift cron. Their
analysis capability regresses to numina SOUL (chat/SKILL.md structured framework).

Tables dropped (by name, idempotent via ``_has_table`` guard):
- ai_asset_alerts            (alerts skill)
- ai_allocation_drift_results (allocation skill structured result)
- ai_disposal_suggestions    (disposal skill)
- ai_liability_results        (liability skill)
- ai_spending_leaks           (spending_leak skill)
- ai_allocation_targets       (allocation-drift cron targets)

Note: ``ai_spending_leaks`` has no create migration in the chain (per plan
feasibility Finding 2), so we drop by name directly rather than relying on the
downgrade chain. downgrade() is a no-op — recovery is via git rollback (the
ORM models are deleted in the same commit).
"""

from collections.abc import Sequence

from alembic import op
from sqlalchemy import inspect

revision: str = "d7b2c4e9f108"
down_revision: str | None = "c3a1f5e7d901"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _has_table(table: str) -> bool:
    bind = op.get_bind()
    insp = inspect(bind)
    return table in insp.get_table_names()


# Tables to drop. Ordered child-before-parent is unnecessary here — these tables
# have no FK dependencies among each other (each is family-scoped, standalone).
_TABLES_TO_DROP = (
    "ai_asset_alerts",
    "ai_allocation_drift_results",
    "ai_disposal_suggestions",
    "ai_liability_results",
    "ai_spending_leaks",
    "ai_allocation_targets",
)


def upgrade() -> None:
    for table in _TABLES_TO_DROP:
        if _has_table(table):
            op.execute(f'DROP TABLE IF EXISTS "{table}"')


def downgrade() -> None:
    # Schema/data loss is intentional (trigger skills removed full-stack in U7).
    # Recovery is via git rollback of this commit + the ORM model deletions.
    pass
