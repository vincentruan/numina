"""低效资产处置建议服务。

规则层：多维度评分（使用频率 + 日均成本 + 资产年龄）
LLM 层：生成渠道建议和处置理由
"""

import logging
from datetime import date

from core.backend_client import BackendClient
from core.llm import LLMClient

logger = logging.getLogger(__name__)

DISPOSAL_PROMPT = """你是二手资产处置顾问。请为以下闲置资产给出一句话处置建议（40字以内），包含推荐渠道。

资产类别：{category}
使用频率：{frequency}
日均成本：{daily_cost}
资产年龄：{age}

只输出建议文本，不要任何前缀。"""

FREQ_SCORE = {"idle": 40, "rarely": 25, "monthly": 10, "weekly": 0, "daily": 0}
CHANNEL_MAP = {
    "数码": "闲鱼/转转",
    "家电": "闲鱼/回收站",
    "车辆": "瓜子二手车/优信",
    "珠宝": "典当行/闲鱼",
    "服饰": "闲鱼/得物",
    "运动": "闲鱼/转转",
    "玩具": "闲鱼",
    "乐器": "闲鱼/乐器行",
    "箱包": "闲鱼/得物",
}


def _score_asset(asset: dict) -> int:
    """计算低效评分 0-100。"""
    score = 0
    freq = asset.get("usage_frequency", "")
    score += FREQ_SCORE.get(freq, 0)

    daily_cost = asset.get("daily_cost", 0) or 0
    if daily_cost > 10:
        score += 30
    elif daily_cost > 3:
        score += 15
    elif daily_cost > 0:
        score += 5

    purchase_date_str = asset.get("purchase_date")
    if purchase_date_str:
        try:
            purchase_date = date.fromisoformat(purchase_date_str[:10])
            age_years = (date.today() - purchase_date).days / 365
            if age_years > 5:
                score += 20
            elif age_years > 3:
                score += 10
        except ValueError:
            pass

    return min(score, 100)


async def scan_disposal_suggestions(family_id: str, llm: LLMClient) -> list[dict]:
    """扫描低效资产，返回处置建议列表。"""
    client = BackendClient(family_id=family_id)

    try:
        low_usage = await client.get_dashboard_low_usage()
    except Exception as e:
        logger.error(f"[disposal] 拉取数据失败 family={family_id}: {e}")
        raise

    suggestions = []
    for asset in low_usage:
        score = _score_asset(asset)
        if score < 20:
            continue

        category = asset.get("category_name", "")
        channel = next((v for k, v in CHANNEL_MAP.items() if k in category), "闲鱼")

        purchase_date_str = asset.get("purchase_date", "")
        age_str = "未知"
        if purchase_date_str:
            try:
                age_days = (date.today() - date.fromisoformat(purchase_date_str[:10])).days
                age_str = f"{age_days // 365}年{(age_days % 365) // 30}个月"
            except ValueError:
                pass

        daily_cost = asset.get("daily_cost", 0) or 0
        freq_label = {"idle": "闲置", "rarely": "极少使用", "monthly": "偶尔使用"}.get(
            asset.get("usage_frequency", ""), "低频使用"
        )

        suggestion = await _get_suggestion(
            llm=llm,
            category=category,
            frequency=freq_label,
            daily_cost=f"¥{daily_cost:.1f}/天" if daily_cost > 0 else "无",
            age=age_str,
        )

        # Estimate resale range based on current_value
        current_value = asset.get("current_value", 0) or 0
        if current_value > 0:
            low = round(current_value * 0.4)
            high = round(current_value * 0.7)
            resale_range = f"¥{low:,} ~ ¥{high:,}"
        else:
            resale_range = None

        suggestions.append({
            "asset_id": asset.get("id"),
            "asset_name": asset.get("name", ""),
            "category_name": category,
            "inefficiency_score": score,
            "suggested_channel": channel,
            "estimated_resale_range": resale_range,
            "suggestion": suggestion,
            "daily_cost": daily_cost,
        })

    suggestions.sort(key=lambda x: x["inefficiency_score"], reverse=True)
    return suggestions


async def _get_suggestion(llm: LLMClient, category: str, frequency: str, daily_cost: str, age: str) -> str:
    try:
        prompt = DISPOSAL_PROMPT.format(
            category=category, frequency=frequency, daily_cost=daily_cost, age=age
        )
        return (await llm.complete(prompt, max_tokens=80)).strip()
    except Exception as e:
        logger.warning(f"[disposal] LLM 建议生成失败: {e}")
        return ""
