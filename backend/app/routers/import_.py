from datetime import date

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.auth.deps import require_adult
from app.database import get_db
from app.models.asset import Asset
from app.models.category import Category
from app.models.liability import Liability
from app.models.tag import Tag
from app.models.user import User

router = APIRouter(prefix="/import", tags=["import"])


class ImportRequest(BaseModel):
    mode: str = "incremental"  # "incremental" or "full"
    data: dict


@router.post("/json")
def import_json(
    req: ImportRequest,
    db: Session = Depends(get_db),
    user: User = Depends(require_adult),
):
    family_id = user.family_id
    data = req.data
    stats = {"assets": 0, "liabilities": 0, "categories": 0, "tags": 0}

    if req.mode == "full":
        # Delete existing user data (not system categories)
        db.query(Liability).filter(Liability.family_id == family_id).delete()
        db.query(Asset).filter(Asset.family_id == family_id).delete()
        db.query(Tag).filter(Tag.family_id == family_id).delete()
        db.query(Category).filter(Category.family_id == family_id).delete()
        db.flush()

    # Import custom categories
    category_map: dict[str, str] = {}  # name -> id
    existing_cats = db.query(Category).filter(
        (Category.family_id == family_id) | (Category.family_id == None)
    ).all()
    for c in existing_cats:
        category_map[c.name] = c.id

    for cat_data in data.get("categories", []):
        if cat_data["name"] not in category_map:
            cat = Category(
                family_id=family_id,
                name=cat_data["name"],
                icon=cat_data.get("icon", "📦"),
                color=cat_data.get("color", "#999999"),
                asset_type=cat_data.get("asset_type", "physical"),
            )
            db.add(cat)
            db.flush()
            category_map[cat.name] = cat.id
            stats["categories"] += 1

    # Import tags
    tag_map: dict[str, str] = {}  # name -> id
    existing_tags = db.query(Tag).filter(Tag.family_id == family_id).all()
    for t in existing_tags:
        tag_map[t.name] = t.id

    for tag_data in data.get("tags", []):
        if tag_data["name"] not in tag_map:
            tag = Tag(
                family_id=family_id,
                name=tag_data["name"],
                color=tag_data.get("color", "#1989fa"),
            )
            db.add(tag)
            db.flush()
            tag_map[tag.name] = tag.id
            stats["tags"] += 1

    # Import assets
    for asset_data in data.get("assets", []):
        cat_id = category_map.get(asset_data.get("category_name", ""))
        if not cat_id:
            cat_id = asset_data.get("category_id")

        asset = Asset(
            user_id=user.id,
            family_id=family_id,
            category_id=cat_id,
            name=asset_data["name"],
            asset_type=asset_data.get("asset_type", "physical"),
            purchase_price=asset_data.get("purchase_price"),
            current_value=asset_data.get("current_value"),
            currency=asset_data.get("currency", "CNY"),
            purchase_date=_parse_date(asset_data.get("purchase_date")),
            status=asset_data.get("status", "in_use"),
            location=asset_data.get("location"),
            institution=asset_data.get("institution"),
            interest_rate=asset_data.get("interest_rate"),
            maturity_date=_parse_date(asset_data.get("maturity_date")),
            expected_lifespan_days=asset_data.get("expected_lifespan_days"),
            annual_maintenance_cost=asset_data.get("annual_maintenance_cost"),
            usage_frequency=asset_data.get("usage_frequency"),
            notes=asset_data.get("notes"),
            is_archived=asset_data.get("is_archived", False),
        )
        # Link tags by name
        tag_names = asset_data.get("tag_names", [])
        if tag_names:
            tag_ids = [tag_map[n] for n in tag_names if n in tag_map]
            if tag_ids:
                tags = db.query(Tag).filter(Tag.id.in_(tag_ids)).all()
                asset.tags = tags
        db.add(asset)
        stats["assets"] += 1

    # Import liabilities
    for liab_data in data.get("liabilities", []):
        liab = Liability(
            user_id=user.id,
            family_id=family_id,
            category=liab_data.get("category", "other"),
            name=liab_data["name"],
            original_amount=liab_data["original_amount"],
            remaining_amount=liab_data["remaining_amount"],
            monthly_payment=liab_data.get("monthly_payment"),
            interest_rate=liab_data.get("interest_rate"),
            start_date=_parse_date(liab_data.get("start_date")),
            end_date=_parse_date(liab_data.get("end_date")),
            institution=liab_data.get("institution"),
            notes=liab_data.get("notes"),
            is_active=liab_data.get("is_active", True),
        )
        db.add(liab)
        stats["liabilities"] += 1

    db.commit()
    return {"detail": "导入成功", "stats": stats}


def _parse_date(val: str | None) -> date | None:
    if not val:
        return None
    try:
        return date.fromisoformat(val)
    except (ValueError, TypeError):
        return None
