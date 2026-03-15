import csv
import io
import json
from datetime import date

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session, joinedload

from app.auth.deps import get_current_user
from app.database import get_db
from app.models.asset import Asset
from app.models.category import Category
from app.models.liability import Liability
from app.models.tag import Tag
from app.models.user import User

router = APIRouter(prefix="/export", tags=["export"])


@router.get("/assets/csv")
def export_assets_csv(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
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
            a.purchase_price or "",
            a.current_value or "",
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
    user: User = Depends(get_current_user),
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
    for l in liabilities:
        writer.writerow([
            l.name,
            l.category,
            l.original_amount,
            l.remaining_amount,
            l.monthly_payment or "",
            l.interest_rate or "",
            l.start_date.isoformat() if l.start_date else "",
            l.end_date.isoformat() if l.end_date else "",
            l.institution or "",
            "还款中" if l.is_active else "已结清",
            l.notes or "",
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
    user: User = Depends(get_current_user),
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
        .filter((Category.family_id == family_id) | (Category.family_id == None))
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
                "category_id": a.category_id,
                "purchase_price": a.purchase_price,
                "current_value": a.current_value,
                "currency": a.currency,
                "purchase_date": _serialize_date(a.purchase_date),
                "status": a.status,
                "location": a.location,
                "institution": a.institution,
                "interest_rate": a.interest_rate,
                "maturity_date": _serialize_date(a.maturity_date),
                "expected_lifespan_days": a.expected_lifespan_days,
                "annual_maintenance_cost": a.annual_maintenance_cost,
                "usage_frequency": a.usage_frequency,
                "notes": a.notes,
                "is_archived": a.is_archived,
                "tag_names": [t.name for t in a.tags] if a.tags else [],
            }
            for a in assets
        ],
        "liabilities": [
            {
                "name": l.name,
                "category": l.category,
                "original_amount": l.original_amount,
                "remaining_amount": l.remaining_amount,
                "monthly_payment": l.monthly_payment,
                "interest_rate": l.interest_rate,
                "start_date": _serialize_date(l.start_date),
                "end_date": _serialize_date(l.end_date),
                "institution": l.institution,
                "notes": l.notes,
                "is_active": l.is_active,
            }
            for l in liabilities
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
