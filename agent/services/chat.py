"""自然语言问答助手服务 — 固定意图路由器。

支持的意图（8个）：
1. net_worth_query      — 净资产查询
2. asset_count_query    — 资产数量查询
3. liability_query      — 负债查询
4. allocation_query     — 资产配置查询
5. trend_query          — 净资产趋势查询
6. daily_cost_query     — 日均成本查询
7. low_usage_query      — 低效资产查询
8. expiring_query       — 即将到期资产查询
"""

import json
import logging

from core.backend_client import BackendClient
from core.llm import LLMClient

logger = logging.getLogger(__name__)

INTENT_PROMPT = """你是家庭资产管理助手。用户提问如下：

"{question}"

请判断用户意图，从以下选项中选择最匹配的一个，只输出意图名称，不要任何解释：

net_worth_query, asset_count_query, liability_query, allocation_query, trend_query, daily_cost_query, low_usage_query, expiring_query, unknown"""

ANSWER_PROMPT = """你是家庭资产管理助手。根据以下数据回答用户问题，用简洁中文回答（不超过100字）。

用户问题：{question}
相关数据：{data}

直接回答，不要重复问题，不要说"根据数据"等前缀。"""


async def answer_question(question: str, family_id: str, llm: LLMClient) -> str:
    """识别意图 → 查询数据 → LLM 生成回答。"""
    client = BackendClient(family_id=family_id)

    # Step 1: Intent classification
    intent = await _classify_intent(question, llm)
    logger.info(f"[chat] intent={intent} family={family_id}")

    # Step 2: Fetch relevant data
    try:
        data = await _fetch_data_for_intent(intent, client)
    except Exception as e:
        logger.error(f"[chat] 数据获取失败: {e}")
        return "抱歉，暂时无法获取数据，请稍后再试。"

    if intent == "unknown":
        return "抱歉，我目前只能回答关于净资产、资产配置、负债、趋势、日均成本、低效资产和到期资产的问题。"

    # Step 3: Generate answer
    try:
        prompt = ANSWER_PROMPT.format(
            question=question,
            data=json.dumps(data, ensure_ascii=False, default=str),
        )
        return (await llm.complete(prompt, max_tokens=200)).strip()
    except Exception as e:
        logger.error(f"[chat] LLM 回答生成失败: {e}")
        return "抱歉，AI 服务暂时不可用，请稍后再试。"


async def _classify_intent(question: str, llm: LLMClient) -> str:
    try:
        prompt = INTENT_PROMPT.format(question=question)
        raw = (await llm.complete(prompt, max_tokens=30)).strip().lower()
        valid = {
            "net_worth_query", "asset_count_query", "liability_query",
            "allocation_query", "trend_query", "daily_cost_query",
            "low_usage_query", "expiring_query", "unknown",
        }
        for intent in valid:
            if intent in raw:
                return intent
        return "unknown"
    except Exception:
        return "unknown"


async def _fetch_data_for_intent(intent: str, client: BackendClient) -> dict:
    if intent == "net_worth_query":
        data = await client.get_dashboard_overview()
        return {
            "net_worth": data.get("net_worth"),
            "total_assets": data.get("total_assets"),
            "total_liabilities": data.get("total_liabilities"),
            "mom_change_pct": data.get("mom_change_pct"),
        }
    elif intent == "asset_count_query":
        data = await client.get_dashboard_overview()
        return {"asset_count": data.get("asset_count")}
    elif intent == "liability_query":
        liabilities = await client.get_liabilities()
        return {
            "count": len(liabilities),
            "total": sum(l.get("remaining_amount", 0) for l in liabilities),
            "items": [{"category": l.get("category"), "remaining": l.get("remaining_amount")} for l in liabilities[:5]],
        }
    elif intent == "allocation_query":
        data = await client.get_dashboard_allocation()
        return {"items": data.get("items", [])[:6]}
    elif intent == "trend_query":
        data = await client.get_dashboard_trend(period="year")
        points = data.get("points", [])
        return {
            "period": "近一年",
            "points_count": len(points),
            "first": points[0] if points else None,
            "last": points[-1] if points else None,
        }
    elif intent == "daily_cost_query":
        data = await client.get_dashboard_overview()
        ranking = await client.get_dashboard_daily_cost()
        return {
            "total_daily_cost": data.get("total_daily_cost"),
            "top_items": ranking[:3] if isinstance(ranking, list) else [],
        }
    elif intent == "low_usage_query":
        items = await client.get_dashboard_low_usage()
        return {"count": len(items), "items": items[:5]}
    elif intent == "expiring_query":
        items = await client.get_assets_expiring_soon(days_threshold=365)
        return {"count": len(items), "items": items[:5]}
    return {}
