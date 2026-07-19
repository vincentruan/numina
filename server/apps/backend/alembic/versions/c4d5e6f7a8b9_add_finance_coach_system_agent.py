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
    # Note on `INSERT OR IGNORE`: this is SQLite syntax. The repo dev DB is SQLite;
    # prod is PostgreSQL. PostgreSQL lacks `INSERT OR IGNORE` — but bootstrap_agents()
    # is the source of truth and runs on every startup (Task 3), so on Postgres the
    # row is seeded by bootstrap before any finance_coach run. The migration's
    # `INSERT OR IGNORE` is a SQLite-only convenience for existing dev DBs. If a
    # Postgres deployment runs `alembic upgrade head` before `bootstrap_agents`, the
    # migration will error on `INSERT OR IGNORE` syntax — this is acceptable because
    # the deployment order is `alembic upgrade` then `app startup` (which calls
    # bootstrap_agents). For a Postgres-compatible seeding in the migration itself,
    # replace with a `SELECT ... WHERE NOT EXISTS (SELECT 1 FROM ai_agents WHERE
    # id = 100000000000008)` guard. Use `INSERT OR IGNORE` for SQLite dev.
    op.execute(
        """
        INSERT OR IGNORE INTO ai_agents (
            id, family_id, agent_name, display_name, description,
            icon, color, soul_md, skills, agent_type, memory_enabled, display_order
        )
        VALUES (
            100000000000008, 0, 'finance-coach', '财务教练',
            '家庭财务处方建议智能体。读取家庭财务快照，输出结构化 suggestions JSON（前 3 条优先建议）。',
            '🎯', '#10b981',
            '你是家庭财务教练，在单次响应内完成：读取家庭财务快照 → 识别高息负债/闲置资产/储蓄缺口 → 输出结构化 suggestions JSON。',
            '["finance-coach"]',
            'system', 0, 40
        )
        """
    )


def downgrade() -> None:
    op.execute(
        "DELETE FROM ai_agents WHERE id = 100000000000008"
    )
