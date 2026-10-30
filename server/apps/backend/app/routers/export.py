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
from apps.backend.app.models.liability import Liability
from apps.backend.app.models.user import User
from packages.domain.backup.service import export_family_data

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
    writer.writerow(
        [
            "名称",
            "类型",
            "分类",
            "购入价格",
            "当前估值",
            "币种",
            "购入日期",
            "状态",
            "位置/机构",
            "标签",
            "备注",
        ]
    )
    for a in assets:
        writer.writerow(
            [
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
            ]
        )

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
    writer.writerow(
        [
            "名称",
            "类别",
            "原始金额",
            "剩余金额",
            "月供",
            "利率",
            "开始日期",
            "结束日期",
            "机构",
            "状态",
            "备注",
        ]
    )
    for liab in liabilities:
        writer.writerow(
            [
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
            ]
        )

    output.seek(0)
    today = date.today().isoformat()
    return StreamingResponse(
        iter(["\ufeff" + output.getvalue()]),
        media_type="text/csv; charset=utf-8",
        headers={
            "Content-Disposition": f'attachment; filename="liabilities_{today}.csv"'
        },
    )


@router.get("/all/json")
def export_all_json(
    db: Session = Depends(get_db),
    user: User = Depends(require_adult),
):
    data = export_family_data(db, user.family_id)

    content = json.dumps(data, ensure_ascii=False, indent=2)
    today = date.today().isoformat()
    return StreamingResponse(
        iter([content]),
        media_type="application/json; charset=utf-8",
        headers={
            "Content-Disposition": f'attachment; filename="numina_backup_{today}.json"'
        },
    )
