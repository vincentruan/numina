"""unified_agent_model

Revision ID: a53453cf574b
Revises: x2581y64zqr9
Create Date: 2026-05-26 11:33:51.750691

"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = 'a53453cf574b'
down_revision: str | None = 'x2581y64zqr9'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    bind = op.get_bind()
    is_sqlite = bind.dialect.name == 'sqlite'

    def _has_column(table: str, col: str) -> bool:
        if not bind.dialect.has_table(bind, table):
            return False
        return any(c['name'] == col for c in bind.dialect.get_columns(bind, table))

    def _has_index(table: str, index: str) -> bool:
        if not bind.dialect.has_table(bind, table):
            return False
        return any(i['name'] == index for i in bind.dialect.get_indexes(bind, table))

    # Fresh-DB guard: if ai_agents already has agent_type (current model), the
    # is_builtin->agent_type transition is already done; skip the column swap +
    # index dance + builtin re-seed (system agents seeded app-side on fresh DB).
    if _has_column('ai_agents', 'agent_type') and not _has_column('ai_agents', 'is_builtin'):
        return

    # 1. Add agent_type column with default 'builtin'
    if not _has_column('ai_agents', 'agent_type'):
        op.add_column(
            'ai_agents',
            sa.Column(
                'agent_type',
                sa.String(20),
                nullable=False,
                server_default=sa.text("'builtin'")
            )
        )

    # 2. Update existing records based on is_builtin
    if _has_column('ai_agents', 'is_builtin'):
        op.execute(
            "UPDATE ai_agents SET agent_type = 'builtin' WHERE is_builtin = true"
        )
        op.execute(
            "UPDATE ai_agents SET agent_type = 'custom' WHERE is_builtin = false"
        )

        # 3. Drop is_builtin column
        op.drop_column('ai_agents', 'is_builtin')

    # 4. Drop the old index on is_builtin (guard: may not exist on SQLite fresh DB)
    if _has_index('ai_agents', 'ix_ai_agents_builtin'):
        op.drop_index('ix_ai_agents_builtin', table_name='ai_agents')

    # 5. Create new index on agent_type (Postgres partial index; skip on SQLite)
    if not is_sqlite and not _has_index('ai_agents', 'ix_ai_agents_type'):
        op.create_index(
            'ix_ai_agents_type',
            'ai_agents',
            ['agent_type'],
            postgresql_where=sa.text("agent_type IN ('system', 'builtin')")
        )

    # 6. Insert system agents (ai-assistant, time-machine) — Postgres-only seed
    #    (SQLite fresh DBs are seeded app-side; the multi-line SQL with emoji is
    #     Postgres-tested). Skip on SQLite to avoid encoding/seed-dup issues.
    if not is_sqlite:
        op.execute("""
            INSERT INTO ai_agents (id, family_id, agent_name, display_name, description,
                icon, color, soul_md, skills, agent_type, display_order)
            VALUES (
                100000000000003, 0, 'ai-assistant', 'AI助手',
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
            )
        """)

        op.execute("""
            INSERT INTO ai_agents (id, family_id, agent_name, display_name, description,
                icon, color, soul_md, skills, agent_type, display_order)
            VALUES (
                100000000000004, 0, 'time-machine', '时光机',
                '帮助用户回顾历史决策，分析过去行为，总结经验教训',
                '⏰', '#8B5CF6',
                '你是一位时光机助手，专门帮助用户回顾和分析过去的决策与行为。你的职责是帮助用户从历史中学习，总结经验教训。

    ## 核心能力
    - **历史回顾**：查询和展示用户的历史记录
    - **决策分析**：分析过去决策的背景、过程和结果
    - **经验总结**：提炼有价值的经验教训
    - **趋势洞察**：识别历史趋势和模式

    ## 工作原则
    1. 客观呈现：如实展示历史数据，不做主观评判
    2. 语境还原：还原决策时的具体情境和约束条件
    3. 经验提炼：从具体案例中抽象出可复用的经验
    4. 未来导向：总结的经验应有助于未来决策

    ## 禁止事项
    - 不评判用户的人格和品质
    - 不对过去的错误过度批评
    - 不替用户做未来决策',
                '["time_machine"]',
                'system', 20
            )
        """)

        # 7. Adjust builtin agents display_order to specific values
        op.execute(
            "UPDATE ai_agents SET display_order = 100 WHERE agent_name = 'asset-health-advisor'"
        )
        op.execute(
            "UPDATE ai_agents SET display_order = 200 WHERE agent_name = 'finance-optimizer'"
        )


def downgrade() -> None:
    # 1. Revert builtin agents display_order (restore original seed values: 100 and 200)
    op.execute(
        "UPDATE ai_agents SET display_order = 100 WHERE agent_name = 'asset-health-advisor'"
    )
    op.execute(
        "UPDATE ai_agents SET display_order = 200 WHERE agent_name = 'finance-optimizer'"
    )

    # 2. Delete system agents
    op.execute(
        "DELETE FROM ai_agents WHERE agent_type = 'system'"
    )

    # 3. Drop new index on agent_type
    op.drop_index('ix_ai_agents_type', table_name='ai_agents')

    # 4. Re-add is_builtin column
    op.add_column(
        'ai_agents',
        sa.Column(
            'is_builtin',
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false")
        )
    )

    # 5. Restore is_builtin values based on agent_type
    op.execute(
        "UPDATE ai_agents SET is_builtin = true WHERE agent_type IN ('system', 'builtin')"
    )
    op.execute(
        "UPDATE ai_agents SET is_builtin = false WHERE agent_type = 'custom'"
    )

    # 6. Re-create old index on is_builtin
    op.create_index(
        'ix_ai_agents_builtin',
        'ai_agents',
        ['is_builtin'],
        postgresql_where=sa.text("is_builtin = true")
    )

    # 7. Drop agent_type column
    op.drop_column('ai_agents', 'agent_type')