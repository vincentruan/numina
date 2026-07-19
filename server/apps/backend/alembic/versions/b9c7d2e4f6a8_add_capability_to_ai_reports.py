"""add capability column to ai_reports

Revision ID: b9c7d2e4f6a8
Revises: c4d5e6f7a8b9
Create Date: 2026-07-19

Plan A: the existing ai_reports cache (ai_report.py _latest_report) filters only
by (family_id, status='completed') with NO capability column — a finance_coach
row would collide with the report row for the same family (spec §7.2 core issue 1).
This migration adds ``capability VARCHAR(32) NOT NULL DEFAULT 'report'`` so:
  - existing rows backfill to 'report' (server_default covers them; no data fixup
    needed) and existing report queries are unaffected once the model/router also
    filter by capability (Task 8 + the _latest_report update below).
  - three independent cache keys coexist: family_id:report (existing),
    family_id:finance_coach (D2), family_id:wish_advice:{fingerprint} (Plan B W4).
Index on (family_id, capability, status) makes the latest-by-capability lookup
sub-millisecond.
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "b9c7d2e4f6a8"
down_revision: str | None = "c4d5e6f7a8b9"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "ai_reports",
        sa.Column(
            "capability",
            sa.String(length=32),
            nullable=False,
            server_default="report",
        ),
    )
    op.create_index(
        "ix_ai_reports_family_capability_status",
        "ai_reports",
        ["family_id", "capability", "status"],
    )


def downgrade() -> None:
    op.drop_index("ix_ai_reports_family_capability_status", table_name="ai_reports")
    op.drop_column("ai_reports", "capability")
