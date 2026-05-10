"""场景: test_rich — 完整数据（多资产 + 负债 + 心愿 + 儿童）。"""

from datetime import date

from sqlalchemy.orm import Session

from factories.assets import AssetFactory
from factories.children import ChoreFactory, CoinFactory
from factories.liabilities import LiabilityFactory
from factories.users import FamilyFactory, UserFactory
from factories.wishes import ChildWishFactory, WishFactory


def seed_full_scenario(db: Session, verbose: bool = False) -> None:
    user, created = UserFactory.get_or_create(
        db,
        username="test_rich",
        display_name="完整数据测试",
        password="DemoPass123",
        family_id=0,
        role="owner",
        avatar_color="#10B981",
    )

    if not created:
        if verbose:
            print("  [skip] test_rich 已存在")
        return

    fam = FamilyFactory.get_or_create(db, name="完整测试家庭", created_by_id=user.id)
    user.family_id = fam.id
    db.flush()

    # ── 实物资产 ──────────────────────────────────────────────────────────────
    laptop, _ = AssetFactory.get_or_create(
        db,
        user_id=user.id, family_id=fam.id,
        name="MacBook Pro", asset_type="physical", category_name="数码",
        purchase_price=19999, current_value=14000,
        purchase_date=date(2022, 9, 1), usage_frequency="daily",
        expected_lifespan_days=1825,
    )
    AssetFactory.get_or_create(
        db,
        user_id=user.id, family_id=fam.id,
        name="本田思域", asset_type="physical", category_name="车辆",
        purchase_price=150000, current_value=110000,
        purchase_date=date(2021, 3, 15), usage_frequency="daily",
        location="地下车库",
    )
    AssetFactory.get_or_create(
        db,
        user_id=user.id, family_id=fam.id,
        name="iPhone 15 Pro", asset_type="physical", category_name="数码",
        purchase_price=8999, current_value=7000,
        purchase_date=date(2023, 10, 1), usage_frequency="daily",
    )

    # ── 金融资产 ──────────────────────────────────────────────────────────────
    AssetFactory.get_or_create(
        db,
        user_id=user.id, family_id=fam.id,
        name="招商银行活期", asset_type="financial", category_name="存款",
        purchase_price=50000, current_value=52000,
        purchase_date=date(2020, 1, 1), institution="招商银行",
    )
    AssetFactory.get_or_create(
        db,
        user_id=user.id, family_id=fam.id,
        name="沪深300指数基金", asset_type="financial", category_name="基金",
        purchase_price=30000, current_value=28500,
        purchase_date=date(2022, 6, 1), institution="支付宝",
    )

    # ── 负债 ──────────────────────────────────────────────────────────────────
    LiabilityFactory.get_or_create(
        db,
        user_id=user.id, family_id=fam.id,
        name="车贷", category="car_loan",
        original_amount=80000, remaining_amount=55000,
        monthly_payment=2500, interest_rate=4.5,
        start_date=date(2021, 3, 15), end_date=date(2027, 3, 15),
        institution="工商银行",
    )
    LiabilityFactory.get_or_create(
        db,
        user_id=user.id, family_id=fam.id,
        name="信用卡账单", category="credit_card",
        original_amount=8000, remaining_amount=8000,
        monthly_payment=8000, interest_rate=18.0,
        start_date=date(2024, 1, 1),
        institution="招商银行",
    )

    # ── 心愿 ──────────────────────────────────────────────────────────────────
    WishFactory.get_or_create(
        db, user_id=user.id, family_id=fam.id,
        name="索尼 A7M4 相机", expected_price=18000, priority="high",
    )
    WishFactory.get_or_create(
        db, user_id=user.id, family_id=fam.id,
        name="家庭旅行 — 日本", expected_price=30000, priority="medium",
        converts_to_asset=False,
    )
    WishFactory.get_or_create(
        db, user_id=user.id, family_id=fam.id,
        name="钢琴", expected_price=12000, priority="low",
    )

    # ── 儿童账号 ──────────────────────────────────────────────────────────────
    child, _ = UserFactory.get_or_create_child(
        db, display_name="小明", family_id=fam.id, avatar_color="#FF6B6B",
        username="xiaoming", pin="🐰🥕🌈⭐",
    )

    # 任务模板
    tmpl, _ = ChoreFactory.get_or_create_template(
        db, family_id=fam.id, created_by=user.id,
        name="整理房间", emoji="🧹", coin_reward=10,
        frequency="daily", assignment_type="assigned",
        assigned_child_ids=[child.id],
    )
    ChoreFactory.get_or_create_instance(
        db, template=tmpl, family_id=fam.id,
        child_user_id=child.id, date_bucket="2024-01-15", status="approved",
    )

    # 初始星星币
    CoinFactory.grant(
        db, family_id=fam.id, child_user_id=child.id,
        amount=50, transaction_type="parent_grant",
        narrative="开学奖励", narrative_emoji="🎒",
    )

    # 儿童心愿
    ChildWishFactory.get_or_create(
        db, child_user_id=child.id, family_id=fam.id,
        name="乐高积木", emoji="🧱", star_coin_cost=100,
        status="active", priority="high",
    )

    print("  [ok] test_rich — 完整数据账号已创建")
