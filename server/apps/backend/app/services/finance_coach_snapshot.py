"""Build the PII-minimized family finance snapshot for finance_coach (Plan A T8).

spec §7.1 PII minimization: the snapshot uses entity ``id + category`` (NOT
``name``) unless the prompt strictly requires a name. finance_coach's suggestions
link back by id, so name is dropped here. The snapshot is JSON-injected as the
run's user message; pii_redactor runs again in the worker as defense-in-depth.
"""

from typing import Any

from sqlalchemy.orm import Session

from apps.backend.app.models.asset import Asset
from apps.backend.app.models.liability import Liability
from apps.backend.app.models.wish import Wish


from decimal import Decimal


def _money(v: float | Decimal | None) -> float:
    return float(v) if v is not None else 0.0


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


def build_family_finance_snapshot(db: Session, family_id: str | int) -> dict[str, Any]:
    """Return the family finance snapshot dict (PII-minimized: id+category, no name).

    Fields mirror spec §7.1 finance_coach input:
      net_worth, total_liabilities, high_interest_debts[], idle_assets[],
      top_daily_cost_assets[], wishes[].
    """
    fid = int(family_id)
    assets = db.query(Asset).filter(Asset.family_id == fid).all()
    liabilities = (
        db.query(Liability)
        .filter(Liability.family_id == fid, Liability.is_active.is_(True))
        .all()
    )
    wishes = (
        db.query(Wish).filter(Wish.family_id == fid, Wish.status == "pending").all()
    )

    total_assets = sum(_money(a.current_value) for a in assets)
    total_liabilities = sum(_money(liab.remaining_amount) for liab in liabilities)
    net_worth = total_assets - total_liabilities

    # High-interest debts: rate >= 10% heuristic (the per-category threshold from
    # Plan B W5 is applied for *display* triggers; finance_coach gets the raw set
    # and the SKILL prompt identifies severity). monthly_interest = remaining * monthly_rate.
    high_interest_debts = []
    for liab in liabilities:
        rate = float(_money(liab.interest_rate)) / 100.0 if liab.interest_rate else 0.0
        if rate >= 0.10:
            monthly_interest = _money(liab.remaining_amount) * (rate / 12.0)
            high_interest_debts.append(
                {
                    "id": str(liab.id),
                    "category": liab.category,
                    "rate": _money(liab.interest_rate),
                    "monthly_interest": round(monthly_interest, 2),
                }
            )

    # Idle assets: usage_frequency == 'idle' if the column exists; else
    # target_daily_cost>0 low-usage. Asset has ``usage_frequency`` +
    # ``target_daily_cost`` (not ``daily_cost`` — confirmed in models/asset.py).
    idle_assets = []
    for a in assets:
        daily_cost = _money(getattr(a, "target_daily_cost", None))
        usage = getattr(a, "usage_frequency", None)
        if usage == "idle" or (daily_cost > 0 and usage in (None, "rare", "rarely")):
            idle_assets.append(
                {
                    "id": str(a.id),
                    "category": _asset_category(a),
                    "daily_cost": daily_cost,
                }
            )

    def _daily_cost_key(entry: dict[str, Any]) -> float:
        return float(entry["daily_cost"])

    top_daily_cost_assets = sorted(
        (
            {
                "id": str(a.id),
                "category": _asset_category(a),
                "daily_cost": _money(getattr(a, "target_daily_cost", None)),
            }
            for a in assets
        ),
        key=_daily_cost_key,
        reverse=True,
    )[:5]

    # Wishes with a savings plan (spec §7.2 product-lens: filter out
    # saved_amount=0 AND monthly_saving=0 so the prompt focuses on actionable items).
    # Plan B W1 adds saved_amount/monthly_saving/target_date — Plan A runs first,
    # so these columns are absent here; getattr-guards make this a no-op skip
    # (every wish has saved=0 & monthly=0 → filtered out) until Plan B lands.
    wish_snapshots = []
    for w in wishes:
        saved = _money(getattr(w, "saved_amount", None))
        monthly = _money(getattr(w, "monthly_saving", None))
        if saved == 0 and monthly == 0:
            continue
        wish_snapshots.append(
            {
                "id": str(w.id),
                "price": float(_money(w.expected_price)),
                "saved": saved,
                "monthly_saving": monthly,
                "target_date": str(td)
                if (td := getattr(w, "target_date", None))
                else None,
            }
        )

    return {
        "net_worth": round(net_worth, 2),
        "total_liabilities": round(total_liabilities, 2),
        "high_interest_debts": high_interest_debts,
        "idle_assets": idle_assets,
        "top_daily_cost_assets": top_daily_cost_assets,
        "wishes": wish_snapshots,
    }
