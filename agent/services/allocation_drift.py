"""资产配置漂移检测服务。

规则层：计算当前配置 vs 目标配置的偏差
LLM 层：生成再平衡建议
"""

import logging

from core.backend_client import BackendClient
from core.llm import LLMClient

logger = logging.getLogger(__name__)

REBALANCE_PROMPT = """你是资产配置顾问。以下是家庭资产配置漂移情况，请用2句话给出再平衡建议（不超过80字）。

目标配置：{target}
当前配置：{current}
最大偏差：{max_drift}个百分点（{drift_category}）

只输出建议文本，不要任何前缀。"""


async def detect_allocation_drift(family_id: str, targets: dict, threshold: float, llm: LLMClient) -> dict:
    """检测资产配置漂移，返回漂移报告。"""
    client = BackendClient(family_id=family_id)

    try:
        allocation = await client.get_dashboard_allocation()
    except Exception as e:
        logger.error(f"[allocation_drift] 拉取数据失败: {e}")
        raise

    items = allocation.get("items", [])
    total = sum(item.get("percentage", 0) for item in items) or 100

    # Build current allocation by category name
    current: dict[str, float] = {}
    for item in items:
        name = item.get("category_name") or item.get("name", "")
        current[name] = round(item.get("percentage", 0), 1)

    # Calculate drift per target category
    drifts = []
    for category, target_pct in targets.items():
        current_pct = current.get(category, 0.0)
        drift = current_pct - target_pct
        drifts.append({
            "category": category,
            "target_pct": target_pct,
            "current_pct": current_pct,
            "drift": round(drift, 1),
            "exceeds_threshold": abs(drift) > threshold,
        })

    drifts.sort(key=lambda x: abs(x["drift"]), reverse=True)
    max_drift_item = drifts[0] if drifts else None
    has_significant_drift = any(d["exceeds_threshold"] for d in drifts)

    narrative = ""
    if has_significant_drift and max_drift_item:
        narrative = await _get_narrative(
            llm=llm,
            target=str(targets),
            current=str({d["category"]: d["current_pct"] for d in drifts}),
            max_drift=str(abs(max_drift_item["drift"])),
            drift_category=max_drift_item["category"],
        )

    return {
        "has_significant_drift": has_significant_drift,
        "drifts": drifts,
        "narrative": narrative,
        "threshold": threshold,
    }


async def _get_narrative(llm: LLMClient, target: str, current: str, max_drift: str, drift_category: str) -> str:
    try:
        prompt = REBALANCE_PROMPT.format(
            target=target, current=current, max_drift=max_drift, drift_category=drift_category
        )
        return (await llm.complete(prompt, max_tokens=120)).strip()
    except Exception as e:
        logger.warning(f"[allocation_drift] LLM 叙事失败: {e}")
        return ""
