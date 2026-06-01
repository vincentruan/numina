"""Bootstrap builtin agents (system-wide, family_id=0)."""

from sqlalchemy.orm import Session

from apps.backend.app.core.logging_config import get_logger

logger = get_logger(__name__)

_NUMINA_AGENT = {
    "id": 100000000000005,
    "family_id": 0,
    "agent_name": "numina",
    "display_name": "数鸣",
    "description": "家庭财务大使。运行时自动持有所有已启用的家庭技能，主动洞察、温暖建议，是 Numina 的品牌入口。",
    "icon": "✨",
    "color": "#8b5cf6",
    "soul_md": """你是数鸣，Numina 家庭资产平台的品牌财务大使。你的名字"数鸣"取自数据的清晰回响——把家庭财务的真相用温暖、清晰的方式讲给家人听。

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
- 不在响应中泄露其他家庭成员的隐私数据""",
    "skills": '["*"]',
    "agent_type": "system",
    "display_order": 15,
}


def bootstrap_agents(db: Session) -> None:
    """Ensure builtin agents exist. Idempotent — skips if already present."""
    from apps.backend.app.models.ai_agent import AIAgent

    existing = db.query(AIAgent).filter(
        AIAgent.id == _NUMINA_AGENT["id"],
    ).first()

    if existing:
        return

    agent = AIAgent(
        id=_NUMINA_AGENT["id"],
        family_id=_NUMINA_AGENT["family_id"],
        agent_name=_NUMINA_AGENT["agent_name"],
        display_name=_NUMINA_AGENT["display_name"],
        description=_NUMINA_AGENT["description"],
        icon=_NUMINA_AGENT["icon"],
        color=_NUMINA_AGENT["color"],
        soul_md=_NUMINA_AGENT["soul_md"],
        skills=_NUMINA_AGENT["skills"],
        agent_type=_NUMINA_AGENT["agent_type"],
        display_order=_NUMINA_AGENT["display_order"],
    )
    db.add(agent)
    db.commit()
    logger.info("已初始化系统智能体: 数鸣 (numina)")
