"""消费漏洞检测服务。

规则层（无需 LLM）：
- high_idle_cost: usage_frequency in (rarely, idle) 且 daily_cost > 5
- redundant: 同 category_id 下 >= 2 个 in_use 资产
- high_maintenance: annual_maintenance_cost / current_value > 0.15

LLM 层：为每条漏洞生成建议文本。
"""

import logging
from collections import defaultdict

from apps.agent.core.backend_client import BackendClient
from apps.agent.core.llm import LLMClient
from apps.agent.schemas.context import RedactedContext

logger = logging.getLogger(__name__)

SUGGEST_PROMPT = """你是家庭资产管理顾问。以下是一项资产的消费漏洞信息，请用一句话（30字以内）给出具体建议。

资产名称：{name}
漏洞类型：{leak_type_label}
年度估算浪费：{waste}元

只输出建议文本，不要任何前缀或解释。"""

LEAK_TYPE_LABELS = {
    "high_idle_cost": "高闲置成本",
    "redundant": "冗余持有",
    "high_maintenance": "高维护负担",
}


async def scan_spending_leaks(family_id: str, llm: LLMClient, ctx: RedactedContext) -> list[dict]:
    """扫描家庭资产，返回消费漏洞列表。"""
    client = BackendClient(family_id=family_id)

    try:
        low_usage = await client.get_dashboard_low_usage()
        daily_cost_ranking = await client.get_dashboard_daily_cost()
    except Exception as e:
        logger.error(f"[spending_leak] 拉取数据失败 family={family_id}: {e}")
        raise

    leaks: list[dict] = []
    seen_asset_ids: set = set()

    # ── high_idle_cost: 低频 + 日均成本 > 5 ──────────────────────────
    for asset in low_usage:
        freq = asset.get("usage_frequency", "")
        daily_cost = asset.get("daily_cost") or 0.0
        if freq not in ("rarely", "idle") or daily_cost <= 5.0:
            continue
        asset_id = asset.get("id")
        seen_asset_ids.add(asset_id)
        annual_waste = round(daily_cost * 365, 2)
        severity = "high" if daily_cost > 30 else "medium"
        suggestion = await _get_suggestion(
            llm=llm,
            name=asset.get("name", ""),
            leak_type_label=LEAK_TYPE_LABELS["high_idle_cost"],
            waste=annual_waste,
        )
        leaks.append({
            "asset_id": asset_id,
            "asset_name": asset.get("name", ""),
            "leak_type": "high_idle_cost",
            "severity": severity,
            "estimated_annual_waste": annual_waste,
            "suggestion": suggestion,
        })

    # ── redundant: 同类别 >= 2 个资产 ────────────────────────────────
    category_assets: dict[str, list[dict]] = defaultdict(list)
    for asset in daily_cost_ranking:
        cat = str(asset.get("category_id") or asset.get("category_name", ""))
        if cat:
            category_assets[cat].append(asset)

    for _cat, assets in category_assets.items():
        if len(assets) < 2:
            continue
        sorted_assets = sorted(assets, key=lambda a: a.get("current_value") or 0, reverse=True)
        for asset in sorted_assets[1:]:
            asset_id = asset.get("id")
            if asset_id in seen_asset_ids:
                continue
            seen_asset_ids.add(asset_id)
            daily_cost = asset.get("daily_cost") or 0.0
            annual_waste = round(daily_cost * 365, 2)
            suggestion = await _get_suggestion(
                llm=llm,
                name=asset.get("name", ""),
                leak_type_label=LEAK_TYPE_LABELS["redundant"],
                waste=annual_waste,
            )
            leaks.append({
                "asset_id": asset_id,
                "asset_name": asset.get("name", ""),
                "leak_type": "redundant",
                "severity": "low",
                "estimated_annual_waste": annual_waste,
                "suggestion": suggestion,
            })

    # ── high_maintenance: 年维护费 / 当前价值 > 15% ───────────────────
    for asset in daily_cost_ranking:
        asset_id = asset.get("id")
        if asset_id in seen_asset_ids:
            continue
        maintenance = asset.get("annual_maintenance_cost") or 0.0
        value = asset.get("current_value") or 0.0
        if value <= 0 or maintenance / value <= 0.15:
            continue
        seen_asset_ids.add(asset_id)
        annual_waste = round(maintenance, 2)
        suggestion = await _get_suggestion(
            llm=llm,
            name=asset.get("name", ""),
            leak_type_label=LEAK_TYPE_LABELS["high_maintenance"],
            waste=annual_waste,
        )
        leaks.append({
            "asset_id": asset_id,
            "asset_name": asset.get("name", ""),
            "leak_type": "high_maintenance",
            "severity": "high" if maintenance / value > 0.30 else "medium",
            "estimated_annual_waste": annual_waste,
            "suggestion": suggestion,
        })

    return leaks


async def _get_suggestion(llm: LLMClient, name: str, leak_type_label: str, waste: float) -> str:
    try:
        prompt = SUGGEST_PROMPT.format(
            name=name,
            leak_type_label=leak_type_label,
            waste=waste,
        )
        return (await llm.complete(prompt, max_tokens=60)).strip()
    except Exception as e:
        logger.warning(f"[spending_leak] LLM 建议生成失败: {e}")
        return ""
