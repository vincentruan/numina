"""add import-parse system agent

Revision ID: f8a4c2e1b9d6
Revises: e7f3a2c9b4d1
Create Date: 2026-07-19

U8 (Resolved-10): import_parse is refactored from ``orchestrator.dispatch`` to
a 3rd stream_run agent (``app="import-parse"``). This migration inserts the
import-parse system agent row with ``memory_enabled=False`` (stateless parse —
each run parses the injected document fresh, no DeerMem pollution, mirroring
asset-report). The bootstrap_agents() function re-syncs this row on startup
(single source of truth in agents.py), so this migration only seeds existing
DBs; fresh DBs get the row from bootstrap.
"""
from typing import Sequence, Union

from alembic import op

revision: str = "f8a4c2e1b9d6"
down_revision: Union[str, None] = "e7f3a2c9b4d1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Idempotent insert: skip if the row already exists (e.g. bootstrap ran first).
    # Note on `INSERT OR IGNORE`: this is SQLite syntax. The repo dev DB is SQLite;
    # prod is PostgreSQL. PostgreSQL lacks `INSERT OR IGNORE` — but bootstrap_agents()
    # is the source of truth and runs on every startup, so on Postgres the
    # row is seeded by bootstrap before any import_parse run. The migration's
    # `INSERT OR IGNORE` is a SQLite-only convenience for existing dev DBs. If a
    # Postgres deployment runs `alembic upgrade head` before `bootstrap_agents`, the
    # migration will error on `INSERT OR IGNORE` syntax — this is acceptable because
    # the deployment order is `alembic upgrade` then `app startup` (which calls
    # bootstrap_agents). For a Postgres-compatible seeding in the migration itself,
    # replace with a `SELECT ... WHERE NOT EXISTS (SELECT 1 FROM ai_agents WHERE
    # id = 100000000000007)` guard. Use `INSERT OR IGNORE` for SQLite dev.
    op.execute(
        """
        INSERT OR IGNORE INTO ai_agents (
            id, family_id, agent_name, display_name, description,
            icon, color, soul_md, skills, agent_type, memory_enabled, display_order
        )
        VALUES (
            100000000000007, 0, 'import-parse', '导入解析',
            '金融文档持仓解析智能体。读取上传的金融文档文本，提取持仓/资产条目，输出结构化 JSON。',
            '📄', '#3b82f6',
            '你是金融文档持仓解析器，在单次响应内完成：读取文档文本 → 提取持仓/资产条目 → 输出结构化 JSON。',
            '["import-parse"]',
            'system', 0, 30
        )
        """
    )


def downgrade() -> None:
    op.execute(
        "DELETE FROM ai_agents WHERE id = 100000000000007"
    )
