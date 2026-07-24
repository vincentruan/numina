"""Build + sanitize the A1b context payload per source (Plan B T6).

spec §7.3: the injected entity context is sanitized (control-char strip + length
cap) before entering the first user turn. Family-scope is enforced by the
caller via the family_id filter on the query — the builder only shapes +
sanitizes what's already family-scoped.

Output format: structured text with Chinese labels and formatted values —
AI-friendly (clear delimiters, precise numbers) and human-readable when
displayed in the chat bubble.
"""
import re
from typing import Any

from sqlalchemy.orm import Session

from apps.backend.app.models.liability import Liability
from apps.backend.app.models.user import User
from apps.backend.app.models.wish import Wish

MAX_CONTEXT_LEN = 4000  # chars — cap to bound the first user turn.

_CONTROL_CHARS = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")

_CATEGORY_LABELS = {
    "mortgage": "房贷",
    "car_loan": "车贷",
    "credit_card": "信用卡",
    "personal_loan": "个人贷款",
    "other": "其他",
}

_PRIORITY_LABELS = {
    "high": "高",
    "medium": "中",
    "low": "低",
}


def _sanitize(text: str) -> str:
    """Strip control chars + cap length."""
    cleaned = _CONTROL_CHARS.sub("", text)
    return cleaned[:MAX_CONTEXT_LEN]


def _dec(v: Any) -> float | None:
    if v is None:
        return None
    return float(v)


def _fmt_money(v: Any) -> str:
    """Format a numeric value as currency string, e.g. ¥1,800,000.00."""
    f = _dec(v)
    if f is None:
        return "未设置"
    return f"¥{f:,.2f}"


def _fmt_pct(v: Any) -> str:
    """Format a decimal rate as percentage, e.g. 0.049 → 4.90%."""
    f = _dec(v)
    if f is None:
        return "未设置"
    return f"{f * 100:.2f}%"


def _fmt_date(v: Any) -> str:
    s = str(v) if v else None
    return s if s else "未设置"


def build_liability_detail(db: Session, user: User, liability_id: str) -> str | None:
    liab = db.query(Liability).filter(
        Liability.id == liability_id, Liability.family_id == user.family_id
    ).first()
    if not liab:
        return None
    cat = _CATEGORY_LABELS.get(liab.category, liab.category)
    lines = [
        f"【负债详情】{cat}「{liab.name}」",
        f"  剩余本金：{_fmt_money(liab.remaining_amount)}",
        f"  年利率：{_fmt_pct(liab.interest_rate)}",
        f"  月供：{_fmt_money(liab.monthly_payment)}",
        f"  状态：{'还款中' if liab.is_active else '已结清'}",
        f"  到期日：{_fmt_date(liab.end_date)}",
    ]
    return _sanitize("\n".join(lines))


def build_wish_detail(db: Session, user: User, wish_id: str) -> str | None:
    w = db.query(Wish).filter(
        Wish.id == wish_id, Wish.family_id == user.family_id
    ).first()
    if not w:
        return None
    pri = _PRIORITY_LABELS.get(w.priority, w.priority or "未设置")
    lines = [
        f"【心愿详情】{w.name}",
        f"  目标金额：{_fmt_money(w.expected_price)}",
        f"  已存金额：{_fmt_money(w.saved_amount)}",
        f"  每月储蓄：{_fmt_money(w.monthly_saving)}",
        f"  目标日期：{_fmt_date(w.target_date)}",
        f"  优先级：{pri}",
        f"  状态：{w.status}",
    ]
    return _sanitize("\n".join(lines))


def build_liability_strategy(db: Session, user: User) -> str:
    """All active liabilities summary for the '问 AI 详细规划' jump (no single id)."""
    liabilities = db.query(Liability).filter(
        Liability.family_id == user.family_id, Liability.is_active.is_(True)
    ).all()
    if not liabilities:
        return _sanitize("【负债还款规划】暂无还款中的负债。")
    parts = [f"【负债还款规划】共 {len(liabilities)} 笔还款中负债："]
    for i, liab in enumerate(liabilities, 1):
        cat = _CATEGORY_LABELS.get(liab.category, liab.category)
        parts.append(
            f"【负债 {i}】{cat}「{liab.name}」\n"
            f"  剩余本金：{_fmt_money(liab.remaining_amount)}\n"
            f"  年利率：{_fmt_pct(liab.interest_rate)}\n"
            f"  月供：{_fmt_money(liab.monthly_payment)}"
        )
    return _sanitize("\n".join(parts))


def build_wish_advice(db: Session, user: User) -> str:
    """All pending wishes summary for the W4 '看完整建议' jump."""
    wishes = db.query(Wish).filter(
        Wish.family_id == user.family_id, Wish.status == "pending"
    ).all()
    if not wishes:
        return _sanitize("【心愿储蓄建议】暂无待实现心愿。")
    parts = [f"【心愿储蓄建议】共 {len(wishes)} 个待实现心愿："]
    for i, w in enumerate(wishes, 1):
        pri = _PRIORITY_LABELS.get(w.priority, w.priority or "未设置")
        parts.append(
            f"【心愿 {i}】{w.name}\n"
            f"  目标金额：{_fmt_money(w.expected_price)}\n"
            f"  已存金额：{_fmt_money(w.saved_amount)}\n"
            f"  每月储蓄：{_fmt_money(w.monthly_saving)}\n"
            f"  目标日期：{_fmt_date(w.target_date)}\n"
            f"  优先级：{pri}"
        )
    return _sanitize("\n".join(parts))
