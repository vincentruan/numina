"""场景: test_asset — 单个实物资产（MacBook Pro）。"""

from datetime import date

from sqlalchemy.orm import Session

from factories.assets import AssetFactory
from factories.users import FamilyFactory, UserFactory


def seed_single_asset_scenario(db: Session, verbose: bool = False) -> None:
    user, created = UserFactory.get_or_create(
        db,
        username="test_asset",
        display_name="单资产测试",
        password="TestAsset123!",
        family_id=0,
        role="owner",
        avatar_color="#3B82F6",
        flush=False,
    )

    if not created:
        if verbose:
            print("  [skip] test_asset 已存在")
        return

    fam = FamilyFactory.get_or_create(db, name="单资产家庭", created_by_id=user.id)
    user.family_id = fam.id
    db.flush()

    AssetFactory.get_or_create(
        db,
        user_id=user.id,
        family_id=fam.id,
        name="测试房产",
        asset_type="physical",
        category_name="房产",
        purchase_price=3500000,
        current_value=4000000,
        purchase_date=date(2020, 6, 1),
        usage_frequency="daily",
        location="测试地址",
    )

    print("  [ok] test_asset — 单资产账号已创建")
