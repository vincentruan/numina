"""standardize skill_id values to match SKILL.md names

Revision ID: a7b8c9d0e1f2
Revises: l3502n85mjh2
Create Date: 2026-09-14

Data migration: rename skill_id values in ai_reports and ai_tasks tables
to use the canonical SKILL.md names (with hyphens).

Mapping:
  'report'        → 'asset-report'
  'finance_coach' → 'finance-coach'
  'coach'         → 'finance-coach'  (ai_tasks only)
  'wish_advice'   → 'wish-advice'
  'literacy'      → 'literacy-weekly-report'  (ai_tasks only)
"""

from collections.abc import Sequence

from alembic import op


def upgrade() -> None:
    # ai_reports: cache-layer skill_id values
    op.execute("UPDATE ai_reports SET skill_id = 'asset-report' WHERE skill_id = 'report'")
    op.execute("UPDATE ai_reports SET skill_id = 'finance-coach' WHERE skill_id = 'finance_coach'")
    op.execute("UPDATE ai_reports SET skill_id = 'wish-advice' WHERE skill_id = 'wish_advice'")

    # ai_tasks: task-tracking skill_id values
    op.execute("UPDATE ai_tasks SET skill_id = 'asset-report' WHERE skill_id = 'report'")
    op.execute("UPDATE ai_tasks SET skill_id = 'finance-coach' WHERE skill_id = 'coach'")
    op.execute("UPDATE ai_tasks SET skill_id = 'finance-coach' WHERE skill_id = 'finance_coach'")
    op.execute("UPDATE ai_tasks SET skill_id = 'wish-advice' WHERE skill_id = 'wish_advice'")
    op.execute(
        "UPDATE ai_tasks SET skill_id = 'literacy-weekly-report' WHERE skill_id = 'literacy'"
    )


def downgrade() -> None:
    # Reverse: ai_reports
    op.execute("UPDATE ai_reports SET skill_id = 'report' WHERE skill_id = 'asset-report'")
    op.execute("UPDATE ai_reports SET skill_id = 'finance_coach' WHERE skill_id = 'finance-coach'")
    op.execute("UPDATE ai_reports SET skill_id = 'wish_advice' WHERE skill_id = 'wish-advice'")

    # Reverse: ai_tasks (finance-coach → coach is the original task-level name)
    op.execute("UPDATE ai_tasks SET skill_id = 'report' WHERE skill_id = 'asset-report'")
    op.execute("UPDATE ai_tasks SET skill_id = 'coach' WHERE skill_id = 'finance-coach'")
    op.execute("UPDATE ai_tasks SET skill_id = 'wish_advice' WHERE skill_id = 'wish-advice'")
    op.execute(
        "UPDATE ai_tasks SET skill_id = 'literacy' WHERE skill_id = 'literacy-weekly-report'"
    )
