"""数据脱敏管道：发送给 LLM 前剥离 PII。"""

from typing import Any


def desensitize_assets(assets: list[dict]) -> list[dict]:
    """资产列表脱敏：资产名替换为类别标签，保留金额和类别信息。"""
    result = []
    for a in assets:
        result.append({
            "category": a.get("category_name", "未知类别"),
            "asset_type": a.get("asset_type", ""),
            "current_value": a.get("current_value"),
            "purchase_price": a.get("purchase_price"),
            "usage_frequency": a.get("usage_frequency"),
            "expected_lifespan_days": a.get("expected_lifespan_days"),
            "annual_maintenance_cost": a.get("annual_maintenance_cost"),
            "currency": a.get("currency", "CNY"),
        })
    return result


def desensitize_liabilities(liabilities: list[dict]) -> list[dict]:
    """负债列表脱敏：负债名/机构名替换为类别标签，金额转区间。"""
    result = []
    for li in liabilities:
        result.append({
            "category": li.get("category", "其他"),
            "remaining_amount_range": _amount_to_range(li.get("remaining_amount")),
            "remaining_amount_range_mid": _amount_to_range_mid(li.get("remaining_amount")),
            "monthly_payment_range": _amount_to_range(li.get("monthly_payment")),
            "interest_rate": li.get("interest_rate"),
            "end_date_ym": _date_to_ym(li.get("end_date")),
            "currency": li.get("currency", "CNY"),
        })
    return result


def desensitize_members(members: list[dict]) -> list[dict]:
    """成员列表脱敏：姓名替换为成员A/B/C。"""
    labels = ["成员A", "成员B", "成员C", "成员D", "成员E"]
    result = []
    for i, m in enumerate(members):
        label = labels[i] if i < len(labels) else f"成员{i + 1}"
        result.append({
            "label": label,
            "role": m.get("role", "member"),
            "asset_count": m.get("asset_count"),
            "total_value": m.get("total_value"),
        })
    return result


def _amount_to_range_mid(amount: float | None) -> float:
    """返回金额区间的中间值（用于估算汇总）。"""
    if amount is None:
        return 0.0
    if amount < 500:
        return 250.0
    elif amount < 1000:
        return 750.0
    elif amount < 5000:
        return 3000.0
    elif amount < 10000:
        return 7500.0
    elif amount < 50000:
        return 30000.0
    elif amount < 100000:
        return 75000.0
    elif amount < 500000:
        return 300000.0
    elif amount < 1000000:
        return 750000.0
    else:
        return 1500000.0


def _amount_to_range(amount: float | None) -> str:
    """将精确金额转换为区间描述。"""
    if amount is None:
        return "未知"
    if amount < 500:
        return "<500"
    elif amount < 1000:
        return "500-1000"
    elif amount < 5000:
        return "1000-5000"
    elif amount < 10000:
        return "5000-10000"
    elif amount < 50000:
        return "1万-5万"
    elif amount < 100000:
        return "5万-10万"
    elif amount < 500000:
        return "10万-50万"
    elif amount < 1000000:
        return "50万-100万"
    else:
        return ">100万"


def _date_to_ym(date_str: str | None) -> str | None:
    """将日期字符串截断为年月精度（YYYY-MM）。"""
    if not date_str:
        return None
    return str(date_str)[:7]
