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
from collections.abc import Sequence

from alembic import op

revision: str = "f8a4c2e1b9d6"
down_revision: str | None = "e7f3a2c9b4d1"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Idempotent insert: skip if the row already exists (e.g. bootstrap ran first).
    # Uses a portable `INSERT ... SELECT ... WHERE NOT EXISTS` guard so the
    # statement is valid on BOTH SQLite (dev) and PostgreSQL (prod). The previous
    # `INSERT OR IGNORE` form was SQLite-only and raised a syntax error when an
    # operator ran `alembic upgrade head` on PostgreSQL before app startup — and
    # because this migration sits mid-chain (down_revision e7f3a2c9b4d1), that
    # single syntax error aborted the entire upgrade. bootstrap_agents() remains
    # the single source of truth (re-syncs on every startup); this seed is only
    # needed for existing DBs that haven't run bootstrap yet.
    op.execute(
        """
        INSERT INTO ai_agents (
            id, family_id, agent_name, display_name, description,
            icon, color, soul_md, skills, agent_type, memory_enabled, display_order
        )
        SELECT
            100000000000007, 0, 'import-parse', '导入解析',
            '金融文档持仓解析智能体。读取上传的金融文档文本，提取持仓/资产条目，输出结构化 JSON。',
            '📄', '#3b82f6',
            '你是金融文档持仓解析器，在单次响应内完成：读取文档文本 → 提取持仓/资产条目 → 输出结构化 JSON。',
            '["import-parse"]',
            'system', 0, 30
        WHERE NOT EXISTS (SELECT 1 FROM ai_agents WHERE id = 100000000000007)
        """
    )


def downgrade() -> None:
    op.execute(
        "DELETE FROM ai_agents WHERE id = 100000000000007"
    )
