"""Remove report skill orphan rows from ai_skills + family_skill_configs

Revision ID: e7f3a2c9b4d1
Revises: a9c4f2e1b7d3
Create Date: 2026-07-19

The ``report`` builtin skill is removed as part of the two-ai-apps unified
dispatch refactor (plan U5). Its skill directory (report/report_generate/
report_structured) is deleted, the bootstrap registration + SKILL_REPORT_ID
constant are removed, and the agent ``/report/generate`` router is deleted —
asset-report is now the sole report path, run as a system fixed-flow via
``stream_run`` (KTD-7/KTD-8), not a toggleable BUILTIN_CAPABILITY.

This migration removes the lingering rows that reference the removed skill:
- ``ai_skills`` (keyed by skill_id): the family_id=0 system-template row
  inserted by bootstrap_skills + any family-enabled rows.
- ``family_skill_configs`` (keyed by capability): ``report`` was in
  BUILTIN_CAPABILITIES, so families may have toggle/override rows for it.

Idempotent: a DELETE of non-existent rows is a no-op. Safe to re-run.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect

revision: str = "e7f3a2c9b4d1"
down_revision: str | None = "a9c4f2e1b7d3"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# Raw literal (not imported from system_ids, which no longer defines it) so
# this migration snapshot stays self-contained — see system_ids.py docstring.
_REMOVED_SKILL_ID = "report"
_REMOVED_CAPABILITY = "report"


def _has_table(table: str) -> bool:
    bind = op.get_bind()
    insp = inspect(bind)
    return table in insp.get_table_names()


def upgrade() -> None:
    bind = op.get_bind()

    if _has_table("ai_skills"):
        # Remove system-template (family_id=0) + family-enabled rows for the
        # removed report skill_id. Parameterised defence-in-depth.
        bind.execute(
            sa.text(
                "DELETE FROM ai_skills WHERE skill_id = :sid"
            ).bindparams(
                sa.bindparam("sid", _REMOVED_SKILL_ID),
            )
        )

    if _has_table("family_skill_configs"):
        # report was in BUILTIN_CAPABILITIES, so families may have toggle/
        # override rows keyed by capability="report".
        bind.execute(
            sa.text(
                "DELETE FROM family_skill_configs WHERE capability = :cap"
            ).bindparams(
                sa.bindparam("cap", _REMOVED_CAPABILITY),
            )
        )


def downgrade() -> None:
    # Data migration: downgrade cannot re-materialise the report skill rows
    # (its bootstrap registration + SKILL_REPORT_ID are removed). A schema
    # rollback to a9c4f2e1b7d3 is the recovery path if U5 must be reverted —
    # the skill directory/router/registration are restored from git.
    pass
