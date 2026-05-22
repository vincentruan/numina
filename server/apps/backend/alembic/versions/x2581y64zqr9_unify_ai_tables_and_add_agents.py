"""unify AI table names to ai_ prefix and add ai_agents table

Revision ID: x2581y64zqr9
Revises: v1461w65xpq7, u1470x53wpq8
Create Date: 2026-05-22
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision: str = "x2581y64zqr9"
down_revision: Union[str, None] = ("v1461w65xpq7", "u1470x53wpq8")
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Rename existing tables to unified ai_ prefix + plural
    op.rename_table("ai_provider_configs", "ai_providers")
    op.rename_table("family_mcp_servers", "ai_mcp_servers")
    op.rename_table("skill_registry", "ai_skills")

    # 2. Create ai_agents table
    op.create_table(
        "ai_agents",
        sa.Column("id", sa.BigInteger(), nullable=False),
        sa.Column("family_id", sa.BigInteger(), nullable=False),
        sa.Column("agent_name", sa.String(64), nullable=False),
        sa.Column("display_name", sa.String(128), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("icon", sa.String(16), nullable=True),
        sa.Column("color", sa.String(16), nullable=True),
        sa.Column("soul_md", sa.Text(), nullable=False),
        sa.Column("skills", JSONB(), nullable=True),
        sa.Column("model", sa.String(64), nullable=True),
        sa.Column("subagent_enabled", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("tool_groups", JSONB(), nullable=True),
        sa.Column("is_builtin", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("is_enabled", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("display_order", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("created_by", sa.BigInteger(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("family_id", "agent_name", name="uq_ai_agents_family_name"),
        sa.CheckConstraint("agent_name ~ '^[a-z][a-z0-9_-]*$'", name="ck_ai_agents_name_format"),
    )
    op.create_index("ix_ai_agents_family_id", "ai_agents", ["family_id"])
    op.create_index("ix_ai_agents_builtin", "ai_agents", ["is_builtin"], postgresql_where=sa.text("is_builtin = true"))
    op.create_index("ix_ai_agents_enabled", "ai_agents", ["is_enabled"], postgresql_where=sa.text("is_enabled = true"))

    # 3. Seed builtin agents (family_id=0)
    # Use fixed large IDs to avoid collision with snowflake generator
    op.execute("""
        INSERT INTO ai_agents (id, family_id, agent_name, display_name, description,
            icon, color, soul_md, skills, is_builtin, display_order)
        VALUES (
            100000000000001, 0, 'asset-health-advisor', '资产健康顾问',
            '全方位监控家庭资产健康状况，提供体检报告、预警提醒、配置分析和闲置处置建议',
            '🏥', '#10B981',
            '你是一位专业的家庭资产健康顾问。你的职责是帮助用户全面了解家庭资产的健康状况，发现潜在风险，并提供专业的改善建议。

## 核心能力
- **资产体检**：综合评估家庭资产的整体健康度，输出结构化体检报告
- **老化预警**：扫描资产老化、高维护成本、闲置情况，提前预警
- **配置分析**：分析资产配置比例，识别偏离最优配置的资产类别
- **处置建议**：识别闲置资产，提供处置或盘活建议

## 工作原则
1. 数据驱动：所有分析基于用户的实际资产数据，不做无依据的推测
2. 风险优先：优先关注高风险、高老化、高闲置的资产
3. 可操作性：每条建议都要有具体的执行路径
4. 保守表达：对不确定的结论使用"可能"、"建议进一步确认"等措辞

## 禁止事项
- 不提供具体投资建议（如"买入某股票"）
- 不做收益预测或承诺
- 不替用户做出财务决策',
            '["report", "alerts", "allocation", "disposal"]',
            true, 100
        )
    """)

    op.execute("""
        INSERT INTO ai_agents (id, family_id, agent_name, display_name, description,
            icon, color, soul_md, skills, is_builtin, display_order)
        VALUES (
            100000000000002, 0, 'finance-optimizer', '财务优化师',
            '分析家庭负债结构和消费漏洞，提供优化建议和还款策略',
            '💰', '#F59E0B',
            '你是一位专业的财务优化师。你的职责是帮助用户识别财务漏洞，优化负债结构，制定科学的还款策略。

## 核心能力
- **负债分析**：评估负债健康度，识别高利率负债、还款压力过大的负债
- **消费漏洞扫描**：识别重复支出、低价值订阅、可替代的高成本服务

## 工作原则
1. 省钱优先：优先识别可立即削减的无意义支出
2. 利率敏感：高利率负债优先偿还
3. 心理友好：建议循序渐进，不一次性要求用户大幅改变消费习惯
4. 长期视角：关注优化后的长期收益，而非短期节省金额

## 禁止事项
- 不提供具体投资建议
- 不推荐具体金融产品
- 不替用户做出财务决策',
            '["liability", "spending_leak"]',
            true, 200
        )
    """)


def downgrade() -> None:
    op.drop_table("ai_agents")
    op.rename_table("ai_skills", "skill_registry")
    op.rename_table("ai_mcp_servers", "family_mcp_servers")
    op.rename_table("ai_providers", "ai_provider_configs")