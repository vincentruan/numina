"""demote builtin agents and seed numina

Revision ID: b6745e8a2c14
Revises: a53453cf574b
Create Date: 2026-05-27

Per plan U2 + KD2/KD3:
- Insert 数鸣 (numina) as a third system agent with skills=["*"] sentinel
  (runtime-resolved by agent_dispatch._resolve_skills to all family-enabled skills).
- Delete the two builtin agents (asset-health-advisor + finance-optimizer)
  seeded by x2581y64zqr9 — their functionality lives on as skills now, not agents.

Down path restores both builtin agents with their original soul_md (mirrored from
x2581y64zqr9 verbatim) so rollback to a53453cf574b reproduces the prior state
exactly. Soul_md is inlined in the migration per KD2 — no fixture indirection.

The soul_md for numina is intentionally inlined here too. Future edits to
numina's persona should land as separate UPDATE migrations, not full down/up
cycles, so migration history stays readable.
"""

from collections.abc import Sequence

from alembic import op

revision: str = "b6745e8a2c14"
down_revision: str | None = "a53453cf574b"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # 1. Insert 数鸣 (numina) as a system agent.
    # display_order=15 places numina between ai-assistant (10) and time-machine (20).
    op.execute(
        """
        INSERT INTO ai_agents (id, family_id, agent_name, display_name, description,
            icon, color, soul_md, skills, agent_type, display_order)
        VALUES (
            100000000000005, 0, 'numina', '数鸣',
            '家庭财务大使。运行时自动持有所有已启用的家庭技能，主动洞察、温暖建议，是 Numina 的品牌入口。',
            '✨', '#8b5cf6',
            '你是数鸣，Numina 家庭资产平台的品牌财务大使。你的名字"数鸣"取自数据的清晰回响——把家庭财务的真相用温暖、清晰的方式讲给家人听。

## 核心定位

你是这个家庭的财务大使，不是冷冰冰的工具。你的存在是为了让每一位家庭成员都能轻松理解家庭资产的全貌、变化和方向。你天然持有家庭已启用的所有业务能力——资产体检、配置漂移、闲置清仓、资金泄漏、负债优化、老化预警等——可以根据用户的问题主动选择最合适的能力来回答。

## 风格基调

- **温暖**：用"我们"而不是"你"，把家庭财务当作共同关心的事
- **清晰**：用具体的数字和场景说话，避免泛泛而谈
- **主动**：在回答完用户问题后，主动建议下一步行动（"接下来想看看……吗？"）
- **节制**：不夸张、不预测收益、不替用户做决策

## 工作原则

1. **数据驱动**：所有结论基于家庭实际资产数据，不做无依据的推测
2. **能力适配**：根据问题选择最合适的已启用能力；如所需能力未启用，主动告知
   并指引用户前往技能管理开启
3. **边界清晰**：当用户提及具体投资建议、收益预测、个税筹划等敏感话题，
   礼貌引导回到平台能覆盖的范围
4. **逐步深入**：先给出整体判断，再用 1-2 个最关键的细节支撑，避免信息倾倒

## 零技能态行为

如果家庭尚未启用任何业务能力，你不报错。在第一次问候时主动告知：
"目前家庭还没有启用任何业务能力，可以前往「设置 → AI → 技能管理」开启需要的能力。
开启后我可以帮你做资产体检、配置分析、闲置清仓等等。"

## 禁止事项

- 不提供具体投资建议（如"买入某股票"、"现在该不该卖房"）
- 不做收益预测或承诺
- 不替用户做出重要财务决策
- 不在响应中泄露其他家庭成员的隐私数据',
            '["*"]',
            'system', 15
        )
        """
    )

    # 2. Delete the two builtin agents.
    # Their functionality continues to exist as skills (agent/skills/*.md files +
    # FamilySkillConfig rows) — the agent rows themselves are no longer needed.
    op.execute(
        "DELETE FROM ai_agents WHERE id IN (100000000000001, 100000000000002) "
        "AND family_id = 0 AND agent_type = 'builtin'"
    )


def downgrade() -> None:
    # 1. Delete numina.
    op.execute(
        "DELETE FROM ai_agents WHERE id = 100000000000005 "
        "AND family_id = 0 AND agent_name = 'numina'"
    )

    # 2. Restore the two builtin agents with their original soul_md.
    # Verbatim from x2581y64zqr9_unify_ai_tables_and_add_agents.py upgrade(),
    # but using agent_type column (introduced by a53453cf574b) instead of is_builtin.
    op.execute(
        """
        INSERT INTO ai_agents (id, family_id, agent_name, display_name, description,
            icon, color, soul_md, skills, agent_type, display_order)
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
            'builtin', 100
        )
        """
    )

    op.execute(
        """
        INSERT INTO ai_agents (id, family_id, agent_name, display_name, description,
            icon, color, soul_md, skills, agent_type, display_order)
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
            'builtin', 200
        )
        """
    )
