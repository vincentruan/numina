"""add finance-coach system agent

Revision ID: c4d5e6f7a8b9
Revises: f8a4c2e1b9d6
Create Date: 2026-07-19

Plan A: finance_coach is a new system fixed-flow (KTD-8) — a 4th stream_run
agent (``app="finance-coach"``). This migration inserts the finance-coach
system agent row with ``memory_enabled=False`` (stateless — each run builds a
fresh family finance snapshot, no DeerMem pollution, mirroring asset-report
and import-parse). The bootstrap_agents() function re-syncs this row on
startup (single source of truth in bootstrap/agents.py), so this migration
only seeds existing DBs; fresh DBs get the row from bootstrap.
"""
from typing import Sequence, Union

from alembic import op

revision: str = "c4d5e6f7a8b9"
down_revision: Union[str, None] = "f8a4c2e1b9d6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Idempotent insert: skip if the row already exists (e.g. bootstrap ran first).
    # Uses a portable `INSERT ... SELECT ... WHERE NOT EXISTS` guard so the
    # statement is valid on BOTH SQLite (dev) and PostgreSQL (prod). The previous
    # `INSERT OR IGNORE` form was SQLite-only and raised a syntax error when an
    # operator ran `alembic upgrade head` on PostgreSQL before app startup —
    # moving the Postgres deploy blocker from f8a4c2e1b9d6 to this later migration
    # if left unfixed. bootstrap_agents() remains the single source of truth
    # (re-syncs on every startup); this seed is only needed for existing DBs that
    # haven't run bootstrap yet.
    op.execute(
        """
        INSERT INTO ai_agents (
            id, family_id, agent_name, display_name, description,
            icon, color, soul_md, skills, agent_type, memory_enabled, display_order
        )
        SELECT
            100000000000008, 0, 'finance-coach', '财务教练',
            '家庭财务处方建议智能体。读取家庭财务快照，输出结构化 suggestions JSON（前 3 条优先建议）。',
            '🎯', '#10b981',
            '你是家庭财务教练，在单次响应内完成：读取家庭财务快照 → 识别高息负债/闲置资产/储蓄缺口 → 输出结构化 suggestions JSON。',
            '["finance-coach"]',
            'system', 0, 40
        WHERE NOT EXISTS (SELECT 1 FROM ai_agents WHERE id = 100000000000008)
        """
    )


def downgrade() -> None:
    op.execute(
        "DELETE FROM ai_agents WHERE id = 100000000000008"
    )
