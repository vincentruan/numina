import csv
import io
import json
from datetime import date

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session, joinedload

from apps.backend.app.auth.deps import require_adult
from apps.backend.app.database import get_db
from apps.backend.app.models.asset import Asset
from apps.backend.app.models.category import Category
from apps.backend.app.models.liability import Liability
from apps.backend.app.models.tag import Tag
from apps.backend.app.models.user import User

router = APIRouter(prefix="/export", tags=["export"])


@router.get("/assets/csv")
def export_assets_csv(
    db: Session = Depends(get_db),
    user: User = Depends(require_adult),
):
    assets = (
        db.query(Asset)
        .options(joinedload(Asset.category), joinedload(Asset.tags))
        .filter(Asset.family_id == user.family_id)
        .order_by(Asset.created_at.desc())
        .all()
    )

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow([
        "名称", "类型", "分类", "购入价格", "当前估值", "币种",
        "购入日期", "状态", "位置/机构", "标签", "备注",
    ])
    for a in assets:
        writer.writerow([
            a.name,
            a.asset_type,
            a.category.name if a.category else "",
            str(a.purchase_price) if a.purchase_price is not None else "",
            str(a.current_value) if a.current_value is not None else "",
            a.currency,
            a.purchase_date.isoformat() if a.purchase_date else "",
            a.status,
            a.location or a.institution or "",
            ",".join(t.name for t in a.tags) if a.tags else "",
            a.notes or "",
        ])

    output.seek(0)
    today = date.today().isoformat()
    return StreamingResponse(
        iter(["\ufeff" + output.getvalue()]),  # BOM for Excel compatibility
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="assets_{today}.csv"'},
    )


@router.get("/liabilities/csv")
def export_liabilities_csv(
    db: Session = Depends(get_db),
    user: User = Depends(require_adult),
):
    liabilities = (
        db.query(Liability)
        .filter(Liability.family_id == user.family_id)
        .order_by(Liability.created_at.desc())
        .all()
    )

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow([
        "名称", "类别", "原始金额", "剩余金额", "月供",
        "利率", "开始日期", "结束日期", "机构", "状态", "备注",
    ])
    for liab in liabilities:
        writer.writerow([
            liab.name,
            liab.category,
            liab.original_amount,
            liab.remaining_amount,
            liab.monthly_payment or "",
            liab.interest_rate or "",
            liab.start_date.isoformat() if liab.start_date else "",
            liab.end_date.isoformat() if liab.end_date else "",
            liab.institution or "",
            "还款中" if liab.is_active else "已结清",
            liab.notes or "",
        ])

    output.seek(0)
    today = date.today().isoformat()
    return StreamingResponse(
        iter(["\ufeff" + output.getvalue()]),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="liabilities_{today}.csv"'},
    )


@router.get("/all/json")
def export_all_json(
    db: Session = Depends(get_db),
    user: User = Depends(require_adult),
):
    family_id = user.family_id

    assets = (
        db.query(Asset)
        .options(joinedload(Asset.tags))
        .filter(Asset.family_id == family_id)
        .all()
    )
    liabilities = db.query(Liability).filter(Liability.family_id == family_id).all()
    categories = (
        db.query(Category)
        .filter((Category.family_id == family_id) | (Category.family_id.is_(None)))
        .all()
    )
    tags = db.query(Tag).filter(Tag.family_id == family_id).all()

    def _serialize_date(v):
        if isinstance(v, date):
            return v.isoformat()
        return v

    data = {
        "export_version": "1.0",
        "export_date": date.today().isoformat(),
        "assets": [
            {
                "name": a.name,
                "asset_type": a.asset_type,
                "category_id": str(a.category_id) if a.category_id is not None else None,
                "purchase_price": str(a.purchase_price) if a.purchase_price is not None else None,
                "current_value": str(a.current_value) if a.current_value is not None else None,
                "currency": a.currency,
                "purchase_date": _serialize_date(a.purchase_date),
                "status": a.status,
                "location": a.location,
                "institution": a.institution,
                "interest_rate": a.interest_rate,
                "maturity_date": _serialize_date(a.maturity_date),
                "expected_lifespan_days": a.expected_lifespan_days,
                "annual_maintenance_cost": str(a.annual_maintenance_cost) if a.annual_maintenance_cost is not None else None,
                "usage_frequency": a.usage_frequency,
                "notes": a.notes,
                "is_archived": a.is_archived,
                "tag_names": [t.name for t in a.tags] if a.tags else [],
            }
            for a in assets
        ],
        "liabilities": [
            {
                "name": liab.name,
                "category": liab.category,
                "original_amount": str(liab.original_amount) if liab.original_amount is not None else None,
                "remaining_amount": str(liab.remaining_amount) if liab.remaining_amount is not None else None,
                "monthly_payment": str(liab.monthly_payment) if liab.monthly_payment is not None else None,
                "interest_rate": liab.interest_rate,
                "start_date": _serialize_date(liab.start_date),
                "end_date": _serialize_date(liab.end_date),
                "institution": liab.institution,
                "notes": liab.notes,
                "is_active": liab.is_active,
            }
            for liab in liabilities
        ],
        "categories": [
            {
                "name": c.name,
                "icon": c.icon,
                "color": c.color,
                "asset_type": c.asset_type,
                "is_system": c.family_id is None,
            }
            for c in categories
            if c.family_id is not None  # Only export custom categories
        ],
        "tags": [{"name": t.name, "color": t.color} for t in tags],
    }

    content = json.dumps(data, ensure_ascii=False, indent=2)
    today = date.today().isoformat()
    return StreamingResponse(
        iter([content]),
        media_type="application/json; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="numina_backup_{today}.json"'},
    )
