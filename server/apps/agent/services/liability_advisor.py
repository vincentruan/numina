"""负债优化顾问服务。

确定性策略计算（雪崩法 / 滚雪球法 / 混合法）+ LLM 叙事。
"""

import logging

from apps.agent.core.backend_client import BackendClient
from apps.agent.core.llm import LLMClient

logger = logging.getLogger(__name__)

NARRATIVE_PROMPT = """你是家庭财务顾问。根据以下负债优化分析，用2-3句话给出核心建议（不超过100字）。

负债总额：{total}
推荐策略：{strategy}
预计节省利息：{savings}
最优先还款：{priority_debt}

只输出建议文本，不要任何前缀。"""


def _avalanche(liabilities: list[dict]) -> dict:
    """雪崩法：优先还高利率负债，最小化总利息。"""
    sorted_debts = sorted(
        [l for l in liabilities if l.get("interest_rate")],
        key=lambda x: x.get("interest_rate", 0),
        reverse=True,
    )
    if not sorted_debts:
        return {"order": [], "total_interest_saved": 0}

    total_interest = sum(
        l.get("remaining_amount", 0) * l.get("interest_rate", 0) / 100
        for l in sorted_debts
    )
    return {
        "strategy": "avalanche",
        "strategy_name": "雪崩法（最省利息）",
        "order": [{"id": l.get("id"), "category": l.get("category"), "rate": l.get("interest_rate")} for l in sorted_debts],
        "priority_debt": sorted_debts[0].get("category", "未知") if sorted_debts else None,
        "estimated_interest_saved": round(total_interest * 0.15, 0),  # rough estimate
    }


def _snowball(liabilities: list[dict]) -> dict:
    """滚雪球法：优先还余额最小的负债，增强心理动力。"""
    sorted_debts = sorted(
        liabilities,
        key=lambda x: x.get("remaining_amount", float("inf")),
    )
    return {
        "strategy": "snowball",
        "strategy_name": "滚雪球法（最快清零）",
        "order": [{"id": l.get("id"), "category": l.get("category"), "remaining": l.get("remaining_amount")} for l in sorted_debts],
        "priority_debt": sorted_debts[0].get("category", "未知") if sorted_debts else None,
        "estimated_interest_saved": 0,
    }


def _hybrid(liabilities: list[dict]) -> dict:
    """混合法：小额负债先清零，大额高利率负债雪崩。"""
    small = [l for l in liabilities if l.get("remaining_amount", 0) < 50000]
    large = [l for l in liabilities if l.get("remaining_amount", 0) >= 50000]

    small_sorted = sorted(small, key=lambda x: x.get("remaining_amount", 0))
    large_sorted = sorted(large, key=lambda x: x.get("interest_rate", 0), reverse=True)
    combined = small_sorted + large_sorted

    return {
        "strategy": "hybrid",
        "strategy_name": "混合法（平衡心理与利息）",
        "order": [{"id": l.get("id"), "category": l.get("category")} for l in combined],
        "priority_debt": combined[0].get("category", "未知") if combined else None,
        "estimated_interest_saved": round(
            sum(l.get("remaining_amount", 0) * l.get("interest_rate", 0) / 100 for l in large_sorted) * 0.1, 0
        ),
    }


async def analyze_liabilities(family_id: str, llm: LLMClient) -> dict:
    """分析家庭负债，返回三种策略对比 + LLM 叙事。"""
    client = BackendClient(family_id=family_id)

    try:
        liabilities = await client.get_liabilities()
    except Exception as e:
        logger.error(f"[liability_advisor] 拉取数据失败 family={family_id}: {e}")
        raise

    if not liabilities:
        return {"has_liabilities": False, "strategies": [], "narrative": "当前家庭无活跃负债，财务状况良好。"}

    total = sum(l.get("remaining_amount", 0) for l in liabilities)
    total_monthly = sum(l.get("monthly_payment", 0) or 0 for l in liabilities)

    avalanche = _avalanche(liabilities)
    snowball = _snowball(liabilities)
    hybrid = _hybrid(liabilities)

    # Recommend best strategy
    has_rates = any(l.get("interest_rate") for l in liabilities)
    recommended = "avalanche" if has_rates else "snowball"

    best = avalanche if recommended == "avalanche" else snowball
    narrative = await _get_narrative(
        llm=llm,
        total=f"¥{total:,.0f}",
        strategy=best.get("strategy_name", ""),
        savings=f"¥{best.get('estimated_interest_saved', 0):,.0f}",
        priority_debt=best.get("priority_debt", "未知"),
    )

    return {
        "has_liabilities": True,
        "total_remaining": total,
        "total_monthly_payment": total_monthly,
        "liability_count": len(liabilities),
        "recommended_strategy": recommended,
        "strategies": [avalanche, snowball, hybrid],
        "narrative": narrative,
    }


async def _get_narrative(llm: LLMClient, total: str, strategy: str, savings: str, priority_debt: str) -> str:
    try:
        prompt = NARRATIVE_PROMPT.format(
            total=total, strategy=strategy, savings=savings, priority_debt=priority_debt
        )
        return (await llm.complete(prompt, max_tokens=150)).strip()
    except Exception as e:
        logger.warning(f"[liability_advisor] LLM 叙事生成失败: {e}")
        return ""
