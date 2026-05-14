# backend/app/services/notification/rules.py
from datetime import date

from sqlalchemy.orm import Session


def check_large_purchase(
    db: Session,
    family_id: int,
    asset_id: int,
    asset_name: str,
    purchase_price: float,
    threshold_fixed: float | None,
    threshold_multiplier: float | None,
    avg_monthly_spend: float | None,
) -> dict | None:
    """大额消费冷静期规则。满足任一阈值条件则返回 reminder dict，否则返回 None。"""
    triggered = False
    if threshold_fixed is not None and purchase_price >= threshold_fixed:
        triggered = True
    if (
        threshold_multiplier is not None
        and avg_monthly_spend is not None
        and purchase_price >= avg_monthly_spend * threshold_multiplier
    ):
        triggered = True
    if not triggered:
        return None
    return {
        "family_id": family_id,
        "reminder_type": "large_purchase",
        "title": f"大额消费提醒：{asset_name}",
        "body": f"购买「{asset_name}」金额 ¥{purchase_price:.0f}，建议冷静 48 小时再决定。",
        "severity": "warning",
        "asset_id": asset_id,
        "template_vars": {
            "asset_name": asset_name,
            "amount": f"{purchase_price:.0f}",
            "threshold": f"¥{threshold_fixed:.0f}" if threshold_fixed else "月均支出倍数",
        },
    }


def check_expiring_soon(
    family_id: int,
    asset_id: int,
    asset_name: str,
    expiry_date: date,
) -> dict | None:
    """保修/保险到期规则。提前 30 天 warning，提前 7 天 critical。"""
    today = date.today()
    days_left = (expiry_date - today).days
    if days_left > 30 or days_left < 0:
        return None
    severity = "critical" if days_left <= 7 else "warning"
    return {
        "family_id": family_id,
        "reminder_type": "expiring_soon",
        "title": f"保修即将到期：{asset_name}",
        "body": f"「{asset_name}」保修将于 {expiry_date} 到期，还有 {days_left} 天。",
        "severity": severity,
        "asset_id": asset_id,
        "template_vars": {
            "asset_name": asset_name,
            "expiry_date": str(expiry_date),
            "days_left": str(days_left),
        },
    }


def check_maturity(
    family_id: int,
    asset_id: int,
    asset_name: str,
    maturity_date: date,
    amount: float | None,
) -> dict | None:
    """理财产品到期规则。提前 30 天 warning，提前 7 天 critical。"""
    today = date.today()
    days_left = (maturity_date - today).days
    if days_left > 30 or days_left < 0:
        return None
    severity = "critical" if days_left <= 7 else "warning"
    amt_str = f"{amount:.0f}" if amount else "未知"
    return {
        "family_id": family_id,
        "reminder_type": "maturity",
        "title": f"理财产品即将到期：{asset_name}",
        "body": f"「{asset_name}」将于 {maturity_date} 到期，还有 {days_left} 天，金额 ¥{amt_str}。",
        "severity": severity,
        "asset_id": asset_id,
        "template_vars": {
            "asset_name": asset_name,
            "maturity_date": str(maturity_date),
            "days_left": str(days_left),
            "amount": amt_str,
        },
    }


def check_allocation_drift(
    family_id: int,
    category: str,
    current_pct: float,
    target_pct: float,
    drift_threshold: float,
) -> dict | None:
    """资产配置失衡规则。偏差超过 drift_threshold 百分点则触发。"""
    drift = abs(current_pct - target_pct)
    if drift <= drift_threshold:
        return None
    return {
        "family_id": family_id,
        "reminder_type": "allocation_drift",
        "title": f"资产配置失衡：{category}",
        "body": f"「{category}」当前占比 {current_pct:.1f}%，目标 {target_pct:.1f}%，偏差 {drift:.1f}%。",
        "severity": "warning",
        "asset_id": None,
        "template_vars": {
            "category": category,
            "current_pct": f"{current_pct:.1f}",
            "target_pct": f"{target_pct:.1f}",
            "drift_pct": f"{drift:.1f}",
        },
    }
