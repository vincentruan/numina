"""Remove family-* skill orphan rows from ai_skills

Revision ID: c3a1f5e7d901
Revises: a4c7e9d2f1b8
Create Date: 2026-07-18

The 4 family-* builtin skills (family-asset-checkup, family-liability-review,
fixed-asset-followup, family-finance-insight-planner) are merged into the
numina chat SOUL (chat/SKILL.md body) as part of the two-ai-apps unified
dispatch refactor (plan U3). Their skill directories, bootstrap registrations,
and system_ids constants are removed; this migration removes the lingering
system-template rows (family_id=0) and any family-enabled rows from the
``ai_skills`` table.

The 4 skills were never in BUILTIN_CAPABILITIES, so ``family_skill_configs``
(which is keyed by capability, not skill_id) has no rows to clean — only
``ai_skills`` (keyed by skill_id) is affected.

Idempotent: a DELETE of non-existent rows is a no-op. Safe to re-run.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect

revision: str = "c3a1f5e7d901"
down_revision: str | None = "a4c7e9d2f1b8"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


# The 4 merged family-* skill_id values. Kept as raw literals (not imported
# from system_ids, which no longer defines them) so this migration snapshot
# remains self-contained — see system_ids.py docstring on the same convention.
_MERGED_SKILL_IDS = (
    "family-asset-checkup",
    "family-liability-review",
    "fixed-asset-followup",
    "family-finance-insight-planner",
)


def _has_table(table: str) -> bool:
    bind = op.get_bind()
    insp = inspect(bind)
    return table in insp.get_table_names()


def upgrade() -> None:
    if not _has_table("ai_skills"):
        # Nothing to clean — table not yet created on a fresh DB.
        return

    # Remove system-template rows (family_id=0) and any family-enabled rows
    # for the 4 merged skills. Parameterised to avoid injection on skill_id
    # values (which are developer-controlled constants, but defence-in-depth).
    bind = op.get_bind()
    bind.execute(
        sa.text(
            "DELETE FROM ai_skills WHERE skill_id IN (:s1, :s2, :s3, :s4)"
        ).bindparams(
            sa.bindparam("s1", _MERGED_SKILL_IDS[0]),
            sa.bindparam("s2", _MERGED_SKILL_IDS[1]),
            sa.bindparam("s3", _MERGED_SKILL_IDS[2]),
            sa.bindparam("s4", _MERGED_SKILL_IDS[3]),
        )
    )


def downgrade() -> None:
    # Data migration: downgrade cannot re-materialise the merged skill rows
    # (their definitions are removed from bootstrap/skills.py + system_ids.py).
    # A schema rollback to a4c7e9d2f1b8 is the recovery path if the merge must
    # be reverted — the skill directories/registrations are restored from git.
    pass
