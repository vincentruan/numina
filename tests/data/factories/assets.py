"""资产工厂 — 幂等创建，按 (user_id, name) 查重。"""

from datetime import date

from sqlalchemy.orm import Session

from models import Asset, Category
from factories.users import next_id


# System category name → id cache (populated lazily)
_cat_cache: dict[str, int] = {}


def _get_category_id(db: Session, name: str, asset_type: str) -> int:
    key = f"{name}:{asset_type}"
    if key not in _cat_cache:
        cat = db.query(Category).filter(Category.name == name, Category.is_system == True).first()  # noqa: E712
        if not cat:
            raise ValueError(f"系统分类 '{name}' 不存在，请先运行 seed_categories")
        _cat_cache[key] = cat.id
    return _cat_cache[key]


class AssetFactory:
    @staticmethod
    def get_or_create(
        db: Session,
        *,
        user_id: int,
        family_id: int,
        name: str,
        asset_type: str,
        category_name: str,
        purchase_price: float,
        current_value: float,
        purchase_date: date,
        currency: str = "CNY",
        status: str = "in_use",
        location: str | None = None,
        usage_frequency: str | None = None,
        expected_lifespan_days: int | None = None,
        annual_maintenance_cost: float = 0,
        notes: str | None = None,
        institution: str | None = None,
        interest_rate: float | None = None,
        maturity_date: date | None = None,
    ) -> tuple[Asset, bool]:
        existing = (
            db.query(Asset)
            .filter(Asset.user_id == user_id, Asset.name == name, Asset.is_archived == False)  # noqa: E712
            .first()
        )
        if existing:
            return existing, False

        cat_id = _get_category_id(db, category_name, asset_type)
        asset = Asset(
            id=next_id(),
            user_id=user_id,
            family_id=family_id,
            category_id=cat_id,
            name=name,
            asset_type=asset_type,
            purchase_price=purchase_price,
            current_value=current_value,
            currency=currency,
            purchase_date=purchase_date,
            status=status,
            location=location,
            usage_frequency=usage_frequency,
            expected_lifespan_days=expected_lifespan_days,
            annual_maintenance_cost=annual_maintenance_cost,
            notes=notes,
            institution=institution,
            interest_rate=interest_rate,
            maturity_date=maturity_date,
        )
        db.add(asset)
        db.flush()
        return asset, True
