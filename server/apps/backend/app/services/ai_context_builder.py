"""Build structured JSON context for AI entity prefill (Plan B T6 + multi-currency).

spec §7.3: the injected entity context is sanitized (control-char strip + length
cap) before entering the first user turn. Family-scope is enforced by the
caller via the family_id filter on the query — the builder only shapes +
sanitizes what's already family-scoped.

Output format: structured JSON — AI can parse precisely, with explicit currency
and amount fields. All monetary values are converted to the user's
``default_currency`` via ``ExchangeRateService.convert()``. The original
currency is preserved in ``original_currency`` for debugging/auditing.

When an exchange rate is missing the original amount is returned unchanged
(no silent 1:1 fallback) and ``rate_missing`` flags are set so the AI (and
the frontend) can warn the user.
"""
import json
import logging
import re
from decimal import Decimal
from typing import Any

from sqlalchemy.orm import Session

from apps.backend.app.models.liability import Liability
from apps.backend.app.models.user import User
from apps.backend.app.models.wish import Wish
from packages.domain.exchange_rate.service import ExchangeRateService

logger = logging.getLogger(__name__)

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


def _fmt_pct(v: Any) -> str:
    """Format a decimal rate as percentage, e.g. 0.049 → 4.90%."""
    f = _dec(v)
    if f is None:
        return "未设置"
    return f"{f * 100:.2f}%"


def _fmt_date(v: Any) -> str:
    s = str(v) if v else None
    return s if s else "未设置"


def _convert(
    amount: Decimal | float | None,
    from_currency: str,
    to_currency: str,
    db: Session,
) -> tuple[float, bool]:
    """Convert *amount* to *to_currency*. Returns ``(converted, rate_missing)``.

    When the rate is missing the original amount is returned unchanged and
    ``rate_missing`` is True — callers must propagate the flag so the AI
    can warn the user.
    """
    if amount is None:
        return 0.0, False
    if from_currency == to_currency:
        return float(amount), False

    rate_from, _ = ExchangeRateService.get_rate(from_currency, db)
    rate_to, _ = ExchangeRateService.get_rate(to_currency, db)
    if rate_from is None or rate_to is None:
        logger.warning(
            "AI context 汇率缺失: %s→%s，返回原始金额", from_currency, to_currency
        )
        return float(amount), True

    converted = ExchangeRateService.convert(float(amount), from_currency, to_currency, db)
    return converted, False


def _serialize(data: dict[str, Any]) -> str:
    """Serialize a structured dict to a sanitized JSON string for the summary field."""
    raw = json.dumps(data, ensure_ascii=False, indent=None)
    return _sanitize(raw)


# ── Builder functions ────────────────────────────────────────────────


def build_liability_detail(db: Session, user: User, liability_id: str) -> str | None:
    """Single-liability detail as structured JSON."""
    liab = db.query(Liability).filter(
        Liability.id == liability_id, Liability.family_id == user.family_id
    ).first()
    if not liab:
        return None

    dc = user.default_currency or "CNY"
    cat = _CATEGORY_LABELS.get(liab.category, liab.category)

    remaining, rm_rate = _convert(liab.remaining_amount, liab.currency, dc, db)
    monthly, mm_rate = _convert(liab.monthly_payment, liab.currency, dc, db)

    data: dict[str, Any] = {
        "type": "liability_detail",
        "category": cat,
        "name": liab.name,
        "currency": dc,
        "original_currency": liab.currency,
        "remaining_amount": round(remaining, 2),
        "monthly_payment": round(monthly, 2),
        "interest_rate": _fmt_pct(liab.interest_rate),
        "status": "还款中" if liab.is_active else "已结清",
        "end_date": _fmt_date(liab.end_date),
    }
    if rm_rate or mm_rate:
        data["rate_missing"] = True
    return _serialize(data)


def build_wish_detail(db: Session, user: User, wish_id: str) -> str | None:
    """Single-wish detail as structured JSON."""
    w = db.query(Wish).filter(
        Wish.id == wish_id, Wish.family_id == user.family_id
    ).first()
    if not w:
        return None

    dc = user.default_currency or "CNY"
    pri = _PRIORITY_LABELS.get(w.priority, w.priority or "未设置")

    price, p_rate = _convert(w.expected_price, w.currency, dc, db)
    saved, s_rate = _convert(w.saved_amount, w.currency, dc, db)
    monthly, m_rate = _convert(w.monthly_saving, w.currency, dc, db)

    data: dict[str, Any] = {
        "type": "wish_detail",
        "name": w.name,
        "currency": dc,
        "original_currency": w.currency,
        "expected_price": round(price, 2),
        "saved_amount": round(saved, 2),
        "monthly_saving": round(monthly, 2),
        "target_date": _fmt_date(w.target_date),
        "priority": pri,
        "status": w.status,
    }
    if p_rate or s_rate or m_rate:
        data["rate_missing"] = True
    return _serialize(data)


def build_liability_strategy(db: Session, user: User) -> str:
    """All active liabilities summary as structured JSON (for '问 AI 详细规划')."""
    liabilities = db.query(Liability).filter(
        Liability.family_id == user.family_id, Liability.is_active.is_(True)
    ).all()

    dc = user.default_currency or "CNY"

    if not liabilities:
        return _serialize({"type": "liability_strategy", "currency": dc, "count": 0, "liabilities": []})

    rate_missing = False
    items: list[dict[str, Any]] = []
    for liab in liabilities:
        cat = _CATEGORY_LABELS.get(liab.category, liab.category)
        remaining, rm = _convert(liab.remaining_amount, liab.currency, dc, db)
        monthly, mm = _convert(liab.monthly_payment, liab.currency, dc, db)
        if rm or mm:
            rate_missing = True
        items.append({
            "category": cat,
            "name": liab.name,
            "remaining_amount": round(remaining, 2),
            "monthly_payment": round(monthly, 2),
            "interest_rate": _fmt_pct(liab.interest_rate),
            "original_currency": liab.currency,
        })

    data: dict[str, Any] = {
        "type": "liability_strategy",
        "currency": dc,
        "count": len(liabilities),
        "liabilities": items,
    }
    if rate_missing:
        data["rate_missing"] = True
    return _serialize(data)


def build_wish_advice(db: Session, user: User) -> str:
    """All pending wishes summary as structured JSON (for '看完整建议')."""
    wishes = db.query(Wish).filter(
        Wish.family_id == user.family_id, Wish.status == "pending"
    ).all()

    dc = user.default_currency or "CNY"

    if not wishes:
        return _serialize({"type": "wish_advice", "currency": dc, "count": 0, "wishes": []})

    rate_missing = False
    items: list[dict[str, Any]] = []
    for w in wishes:
        pri = _PRIORITY_LABELS.get(w.priority, w.priority or "未设置")
        price, pr = _convert(w.expected_price, w.currency, dc, db)
        saved, sr = _convert(w.saved_amount, w.currency, dc, db)
        monthly, mr = _convert(w.monthly_saving, w.currency, dc, db)
        if pr or sr or mr:
            rate_missing = True
        items.append({
            "name": w.name,
            "expected_price": round(price, 2),
            "saved_amount": round(saved, 2),
            "monthly_saving": round(monthly, 2),
            "target_date": _fmt_date(w.target_date),
            "priority": pri,
            "original_currency": w.currency,
        })

    data: dict[str, Any] = {
        "type": "wish_advice",
        "currency": dc,
        "count": len(wishes),
        "wishes": items,
    }
    if rate_missing:
        data["rate_missing"] = True
    return _serialize(data)
