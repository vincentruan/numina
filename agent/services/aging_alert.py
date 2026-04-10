"""固定资产老化预警服务。

规则层（无需 LLM）：
- 剩余寿命 < 180 天 → high
- 剩余寿命 < 365 天 → medium
- 年维护费 > 当前价值 * 20% → high_maintenance
- usage_frequency in (rarely, idle) + daily_cost > 0 → idle_cost

LLM 层：为每条预警生成建议文本。
"""

import logging
from datetime import date

from core.backend_client import BackendClient
from core.llm import LLMClient

logger = logging.getLogger(__name__)

SUGGEST_PROMPT = """你是资产管理顾问。以下是一项资产的老化预警信息，请用一句话（30字以内）给出具体建议。

资产类别：{category}
预警类型：{alert_type}
剩余寿命：{remaining}
日均成本：{daily_cost}

只输出建议文本，不要任何前缀或解释。"""

ALERT_TYPE_LABELS = {
    "aging": "即将到期",
    "high_maintenance": "维护成本过高",
    "idle_cost": "闲置资产持续产生成本",
}


async def scan_aging_alerts(family_id: str, llm: LLMClient) -> list[dict]:
    """扫描家庭资产，返回老化预警列表。"""
    client = BackendClient(family_id=family_id)

    try:
        expiring = await client.get_assets_expiring_soon(days_threshold=365)
        low_usage = await client.get_dashboard_low_usage()
    except Exception as e:
        logger.error(f"[aging_alert] 拉取数据失败 family={family_id}: {e}")
        raise

    alerts = []
    today = date.today()

    # Aging alerts from expiring assets
    for asset in expiring:
        expected_days = asset.get("expected_lifespan_days")
        purchase_date_str = asset.get("purchase_date")
        if not expected_days or not purchase_date_str:
            continue

        try:
            purchase_date = date.fromisoformat(purchase_date_str[:10])
        except ValueError:
            continue

        expiry_date = date.fromordinal(purchase_date.toordinal() + expected_days)
        remaining_days = (expiry_date - today).days
        if remaining_days < 0:
            remaining_days = 0

        severity = "high" if remaining_days < 180 else "medium"
        alert_type = "aging"

        suggestion = await _get_suggestion(
            llm=llm,
            category=asset.get("category_name", "未知"),
            alert_type=ALERT_TYPE_LABELS[alert_type],
            remaining=f"{remaining_days}天",
            daily_cost=f"¥{asset.get('daily_cost', 0):.1f}/天" if asset.get("daily_cost") else "未知",
        )

        alerts.append({
            "asset_id": asset.get("id"),
            "asset_name": asset.get("name", ""),
            "category_name": asset.get("category_name", ""),
            "alert_type": alert_type,
            "severity": severity,
            "suggestion": suggestion,
            "remaining_life_days": remaining_days,
            "daily_cost": asset.get("daily_cost"),
        })

    # Idle cost alerts
    idle_asset_ids = {a.get("id") for a in alerts}
    for asset in low_usage:
        if asset.get("id") in idle_asset_ids:
            continue
        freq = asset.get("usage_frequency", "")
        daily_cost = asset.get("daily_cost", 0) or 0
        if freq not in ("rarely", "idle") or daily_cost <= 0:
            continue

        suggestion = await _get_suggestion(
            llm=llm,
            category=asset.get("category_name", "未知"),
            alert_type=ALERT_TYPE_LABELS["idle_cost"],
            remaining="N/A",
            daily_cost=f"¥{daily_cost:.1f}/天",
        )

        alerts.append({
            "asset_id": asset.get("id"),
            "asset_name": asset.get("name", ""),
            "category_name": asset.get("category_name", ""),
            "alert_type": "idle_cost",
            "severity": "medium",
            "suggestion": suggestion,
            "remaining_life_days": None,
            "daily_cost": daily_cost,
        })

    return alerts


async def _get_suggestion(llm: LLMClient, category: str, alert_type: str, remaining: str, daily_cost: str) -> str:
    try:
        prompt = SUGGEST_PROMPT.format(
            category=category,
            alert_type=alert_type,
            remaining=remaining,
            daily_cost=daily_cost,
        )
        return (await llm.complete(prompt, max_tokens=60)).strip()
    except Exception as e:
        logger.warning(f"[aging_alert] LLM 建议生成失败: {e}")
        return ""
