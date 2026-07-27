"""Build the PII-minimized family finance snapshot for finance_coach (Plan A T8).

spec §7.1 PII minimization: the snapshot uses entity ``id + category`` (NOT
``name``) unless the prompt strictly requires a name. finance_coach's suggestions
link back by id, so name is dropped here. The snapshot is JSON-injected as the
run's user message; pii_redactor runs again in the worker as defense-in-depth.

Multi-currency: all monetary values are converted to the user's
``default_currency`` via ``ExchangeRateService.convert()``.  When an exchange
rate is missing the original amount is returned unchanged and a
``rate_missing`` flag is set so the AI can warn the user.
"""

import logging
from typing import Any

from sqlalchemy.orm import Session

from apps.backend.app.models.asset import Asset
from apps.backend.app.models.liability import Liability
from apps.backend.app.models.user import User
from apps.backend.app.models.wish import Wish
from packages.domain.exchange_rate.service import ExchangeRateService

logger = logging.getLogger(__name__)


def _money(v: Any) -> float:
    return float(v) if v is not None else 0.0


def _convert(
    amount: float,
    from_currency: str,
    to_currency: str,
    db: Session,
) -> tuple[float, bool]:
    """Convert *amount* to *to_currency*. Returns ``(converted, rate_missing)``."""
    if from_currency == to_currency:
        return amount, False
    rate_from, _ = ExchangeRateService.get_rate(from_currency, db)
    rate_to, _ = ExchangeRateService.get_rate(to_currency, db)
    if rate_from is None or rate_to is None:
        logger.warning(
            "finance_coach 汇率缺失: %s→%s，返回原始金额", from_currency, to_currency
        )
        return amount, True
    converted = ExchangeRateService.convert(amount, from_currency, to_currency, db)
    return converted, False


def _asset_category(asset: Asset) -> str | None:
    """Resolve an asset's category name via the relationship, falling back to
    the category_id string. ``Asset`` has no ``category`` column — only the FK
    ``category_id`` + ``category`` relationship to ``Category.name``."""
    try:
        cat = getattr(asset, "category", None)
        if cat is not None and getattr(cat, "name", None):
            return str(cat.name)
    except Exception:
        pass
    cid = getattr(asset, "category_id", None)
    return str(cid) if cid is not None else None


def build_family_finance_snapshot(
    db: Session, user: User
) -> dict[str, Any]:
    """Return the family finance snapshot dict (PII-minimized: id+category, no name).

    All monetary values are converted to ``user.default_currency``.
    Fields mirror spec §7.1 finance_coach input:
      net_worth, total_liabilities, high_interest_debts[], idle_assets[],
      top_daily_cost_assets[], wishes[].
    """
    fid = int(user.family_id)
    dc = user.default_currency or "CNY"
    assets = db.query(Asset).filter(Asset.family_id == fid).all()
    liabilities = (
        db.query(Liability)
        .filter(Liability.family_id == fid, Liability.is_active.is_(True))
        .all()
    )
    wishes = (
        db.query(Wish).filter(Wish.family_id == fid, Wish.status == "pending").all()
    )

    rate_missing = False

    # ── Aggregate totals (convert to default_currency before summing) ──
    total_assets = 0.0
    for a in assets:
        converted, rm = _convert(_money(a.current_value), a.currency, dc, db)
        if rm:
            rate_missing = True
        total_assets += converted

    total_liabilities = 0.0
    for liab in liabilities:
        converted, rm = _convert(_money(liab.remaining_amount), liab.currency, dc, db)
        if rm:
            rate_missing = True
        total_liabilities += converted

    net_worth = total_assets - total_liabilities

    # ── High-interest debts ──
    high_interest_debts = []
    for liab in liabilities:
        rate = float(_money(liab.interest_rate)) / 100.0 if liab.interest_rate else 0.0
        if rate >= 0.10:
            monthly_interest_raw = _money(liab.remaining_amount) * (rate / 12.0)
            mi, mi_rm = _convert(monthly_interest_raw, liab.currency, dc, db)
            if mi_rm:
                rate_missing = True
            high_interest_debts.append(
                {
                    "id": str(liab.id),
                    "category": liab.category,
                    "rate": _money(liab.interest_rate),
                    "monthly_interest": round(mi, 2),
                    "original_currency": liab.currency,
                }
            )

    # ── Idle assets ──
    idle_assets = []
    for a in assets:
        daily_cost_raw = _money(getattr(a, "target_daily_cost", None))
        usage = getattr(a, "usage_frequency", None)
        if usage == "idle" or (daily_cost_raw > 0 and usage in (None, "rare", "rarely")):
            dc_cost, dc_rm = _convert(daily_cost_raw, a.currency, dc, db)
            if dc_rm:
                rate_missing = True
            idle_assets.append(
                {
                    "id": str(a.id),
                    "category": _asset_category(a),
                    "daily_cost": round(dc_cost, 2),
                    "original_currency": a.currency,
                }
            )

    def _daily_cost_key(entry: dict[str, Any]) -> float:
        return float(entry["daily_cost"])

    # ── Top daily-cost assets (convert before ranking) ──
    converted_daily: list[dict[str, Any]] = []
    for a in assets:
        raw = _money(getattr(a, "target_daily_cost", None))
        c, cr = _convert(raw, a.currency, dc, db)
        if cr:
            rate_missing = True
        converted_daily.append({
            "id": str(a.id),
            "category": _asset_category(a),
            "daily_cost": round(c, 2),
            "original_currency": a.currency,
        })

    top_daily_cost_assets = sorted(
        converted_daily, key=_daily_cost_key, reverse=True
    )[:5]

    # ── Wishes with a savings plan (convert to default_currency) ──
    wish_snapshots = []
    for w in wishes:
        saved_raw = _money(getattr(w, "saved_amount", None))
        monthly_raw = _money(getattr(w, "monthly_saving", None))
        if saved_raw == 0 and monthly_raw == 0:
            continue
        price, pr = _convert(_money(w.expected_price), w.currency, dc, db)
        saved, sr = _convert(saved_raw, w.currency, dc, db)
        monthly, mr = _convert(monthly_raw, w.currency, dc, db)
        if pr or sr or mr:
            rate_missing = True
        wish_snapshots.append(
            {
                "id": str(w.id),
                "price": round(price, 2),
                "saved": round(saved, 2),
                "monthly_saving": round(monthly, 2),
                "target_date": str(td)
                if (td := getattr(w, "target_date", None))
                else None,
                "original_currency": w.currency,
            }
        )

    result: dict[str, Any] = {
        "currency": dc,
        "net_worth": round(net_worth, 2),
        "total_liabilities": round(total_liabilities, 2),
        "high_interest_debts": high_interest_debts,
        "idle_assets": idle_assets,
        "top_daily_cost_assets": top_daily_cost_assets,
        "wishes": wish_snapshots,
    }
    if rate_missing:
        result["rate_missing"] = True
    return result
