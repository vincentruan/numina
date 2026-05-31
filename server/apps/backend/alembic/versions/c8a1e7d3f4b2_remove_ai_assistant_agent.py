"""remove ai-assistant system agent

Revision ID: c8a1e7d3f4b2
Revises: a7b2c3d4e5f6
Create Date: 2026-05-30

Numina (the brand-primary system agent seeded by b6745e8a2c14) covers the chat
capability that ai-assistant used to provide. Keeping both lets the recipient
picker show two parallel system chat personas, which dilutes the brand entry.
This migration removes the ai-assistant row (id=100000000000003, originally
seeded by a53453cf574b_unified_agent_model). Its chat-only behaviour is
naturally subsumed by numina's sentinel skills=["*"] resolved at runtime.

The downgrade re-seeds ai-assistant verbatim from a53453cf574b so a rollback
to the prior head reproduces the prior state exactly.
"""

from collections.abc import Sequence

from alembic import op

revision: str = "c8a1e7d3f4b2"
down_revision: str | None = "a7b2c3d4e5f6"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Idempotent: WHERE clause makes re-runs against an already-cleaned DB a no-op.
    op.execute(
        "DELETE FROM ai_agents "
        "WHERE id = 100000000000003 "
        "AND family_id = 0 "
        "AND agent_name = 'ai-assistant'"
    )


def downgrade() -> None:
    # Re-seed ai-assistant verbatim from a53453cf574b_unified_agent_model.py:62-87.
    # Idempotency guard mirrors b6745e8a2c14's WHERE NOT EXISTS pattern so a
    # downgrade against a DB that already has the row (e.g. partial rollback)
    # doesn't violate the primary-key constraint.
    op.execute(
        """
        INSERT INTO ai_agents (id, family_id, agent_name, display_name, description,
            icon, color, soul_md, skills, agent_type, display_order)
        SELECT 100000000000003, 0, 'ai-assistant', 'AI助手',
            '通用AI对话助手，支持聊天问答、信息检索和基础任务处理',
            '🤖', '#3B82F6',
            '你是一位友好的AI助手，随时准备帮助用户解决问题。你的目标是提供准确、有用的回答，并保持耐心和礼貌。

## 核心能力
- **对话交流**：理解用户意图，进行自然流畅的对话
- **信息查询**：帮助用户查找和整理信息
- **任务协助**：协助用户完成简单的日常任务

## 工作原则
1. 清晰简洁：用简单易懂的语言回答问题
2. 准确可靠：确保提供的信息准确无误
3. 主动帮助：主动询问是否需要更多帮助
4. 友好耐心：保持积极友好的态度

## 禁止事项
- 不提供具体投资建议
- 不做收益预测或承诺
- 不替用户做出重要决策',
            '["chat"]',
            'system', 10
        WHERE NOT EXISTS (SELECT 1 FROM ai_agents WHERE id = 100000000000003)
        """
    )
