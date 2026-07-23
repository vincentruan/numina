"""Build + sanitize the A1b context payload per source (Plan B T6).

spec §7.3: the injected entity JSON is sanitized (control-char strip + length
cap) before entering the first user turn. Family-scope is enforced by the
caller via the family_id filter on the query — the builder only shapes +
sanitizes what's already family-scoped.
"""
import json
import re
from typing import Any

from sqlalchemy.orm import Session

from apps.backend.app.models.liability import Liability
from apps.backend.app.models.user import User
from apps.backend.app.models.wish import Wish

MAX_CONTEXT_LEN = 4000  # chars — cap to bound the first user turn.

_CONTROL_CHARS = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")


def _sanitize(text: str) -> str:
    """Strip control chars + cap length."""
    cleaned = _CONTROL_CHARS.sub("", text)
    return cleaned[:MAX_CONTEXT_LEN]


def _dec(v: Any) -> float | None:
    if v is None:
        return None
    return float(v)


def build_liability_detail(db: Session, user: User, liability_id: str) -> str | None:
    liab = db.query(Liability).filter(
        Liability.id == liability_id, Liability.family_id == user.family_id
    ).first()
    if not liab:
        return None
    payload = {
        "type": "liability_detail",
        "id": str(liab.id),
        "category": liab.category,
        "remaining_amount": _dec(liab.remaining_amount),
        "interest_rate": _dec(liab.interest_rate),
        "monthly_payment": _dec(liab.monthly_payment),
        "is_active": liab.is_active,
        "end_date": str(liab.end_date) if liab.end_date else None,
    }
    return _sanitize(json.dumps(payload, ensure_ascii=False))


def build_wish_detail(db: Session, user: User, wish_id: str) -> str | None:
    w = db.query(Wish).filter(
        Wish.id == wish_id, Wish.family_id == user.family_id
    ).first()
    if not w:
        return None
    payload = {
        "type": "wish_detail",
        "id": str(w.id),
        # name is prompt-required for wish context (the user names wishes)
        "name": w.name,
        "expected_price": _dec(w.expected_price),
        "saved_amount": _dec(w.saved_amount),
        "monthly_saving": _dec(w.monthly_saving),
        "target_date": str(w.target_date) if w.target_date else None,
        "priority": w.priority,
        "status": w.status,
    }
    return _sanitize(json.dumps(payload, ensure_ascii=False))


def build_liability_strategy(db: Session, user: User) -> str:
    """All active liabilities summary for the '问 AI 详细规划' jump (no single id)."""
    liabilities = db.query(Liability).filter(
        Liability.family_id == user.family_id, Liability.is_active.is_(True)
    ).all()
    payload = {
        "type": "liability_strategy",
        "liabilities": [
            {
                "id": str(liab.id),
                "category": liab.category,
                "remaining_amount": _dec(liab.remaining_amount),
                "interest_rate": _dec(liab.interest_rate),
                "monthly_payment": _dec(liab.monthly_payment),
            }
            for liab in liabilities
        ],
    }
    return _sanitize(json.dumps(payload, ensure_ascii=False))


def build_wish_advice(db: Session, user: User) -> str:
    """All pending wishes summary for the W4 '看完整建议' jump."""
    wishes = db.query(Wish).filter(
        Wish.family_id == user.family_id, Wish.status == "pending"
    ).all()
    payload = {
        "type": "wish_advice",
        "wishes": [
            {
                "id": str(w.id),
                "name": w.name,
                "expected_price": _dec(w.expected_price),
                "saved_amount": _dec(w.saved_amount),
                "monthly_saving": _dec(w.monthly_saving),
                "target_date": str(w.target_date) if w.target_date else None,
                "priority": w.priority,
            }
            for w in wishes
        ],
    }
    return _sanitize(json.dumps(payload, ensure_ascii=False))
