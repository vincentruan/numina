"""场景: test_rich — 完整数据（多资产 + 负债 + 心愿 + 儿童 + 旅游）。"""

from datetime import date, datetime

from sqlalchemy.orm import Session

from factories.assets import AssetFactory
from factories.children import ChoreFactory, CoinFactory
from factories.liabilities import LiabilityFactory
from factories.rentals import RentalContractFactory
from factories.travel import (
    ExpenseCategoryFactory,
    ExpenseEntryFactory,
    SplitGroupFactory,
    SplitParticipantFactory,
    TripFactory,
)
from factories.users import FamilyFactory, UserFactory
from factories.wishes import ChildWishFactory, WishFactory


def seed_full_scenario(db: Session, verbose: bool = False) -> None:
    user, created = UserFactory.get_or_create(
        db,
        username="test_rich",
        display_name="完整数据测试",
        password="TestRich123!",
        family_id=0,
        role="owner",
        avatar_color="#10B981",
        flush=False,
    )

    if not created and verbose:
        print("  [info] test_rich 已存在，确保关联数据完整...")

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

    # ── 租约 ──────────────────────────────────────────────────────────────────
    RentalContractFactory.get_or_create(
        db,
        user_id=user.id, family_id=fam.id,
        role="tenant", monthly_rent=6000, deposit=12000,
        start_date=date(2023, 3, 1), end_date=None,
        counterparty="链家地产", notes="公寓承租，不定期租约",
    )

    # ── 心愿 ──────────────────────────────────────────────────────────────────
    WishFactory.get_or_create(
        db, user_id=user.id, family_id=fam.id,
        name="索尼 A7M4 相机", expected_price=18000, priority="high",
    )
    japan_wish, _ = WishFactory.get_or_create(
        db, user_id=user.id, family_id=fam.id,
        name="家庭旅行 — 日本", expected_price=30000, priority="medium",
        converts_to_asset=False,
    )
    WishFactory.get_or_create(
        db, user_id=user.id, family_id=fam.id,
        name="钢琴", expected_price=12000, priority="low",
    )

    # ── 旅游 ──────────────────────────────────────────────────────────────────
    # 支出类别（系统预置）
    cat_food, _ = ExpenseCategoryFactory.get_or_create(db, name="餐饮", icon="food", is_system=True, sort_order=1)
    cat_transport, _ = ExpenseCategoryFactory.get_or_create(db, name="交通", icon="transport", is_system=True, sort_order=2)
    cat_hotel, _ = ExpenseCategoryFactory.get_or_create(db, name="住宿", icon="hotel", is_system=True, sort_order=3)
    cat_activity, _ = ExpenseCategoryFactory.get_or_create(db, name="活动", icon="activity", is_system=True, sort_order=4)
    ExpenseCategoryFactory.get_or_create(db, name="购物", icon="shopping", is_system=True, sort_order=5)

    # 行程1: 日本旅行（planning，从心愿转化）
    japan_trip, _ = TripFactory.get_or_create(
        db, user_id=user.id, family_id=fam.id,
        name="日本家庭旅行", destination="东京 · 大阪",
        departure_date=date(2026, 10, 1), return_date=date(2026, 10, 7),
        status="planning", planned_budget=30000, currency="CNY",
        wish_id=japan_wish.id, timezone="Asia/Tokyo",
    )

    # 为日本旅行添加几笔费用
    ExpenseEntryFactory.create_pair(
        db, family_id=fam.id, trip_id=japan_trip.id, user_id=user.id,
        category_id=cat_transport.id, amount=5800, expense_date=date(2026, 8, 15),
        description="往返机票预订（2大1小）",
    )
    ExpenseEntryFactory.create_pair(
        db, family_id=fam.id, trip_id=japan_trip.id, user_id=user.id,
        category_id=cat_hotel.id, amount=4200, expense_date=date(2026, 8, 20),
        description="新宿花园酒店 6晚",
    )

    # 行程2: 周末露营（active，已有较多费用）
    camping_trip, _ = TripFactory.get_or_create(
        db, user_id=user.id, family_id=fam.id,
        name="周末千岛湖露营", destination="千岛湖",
        departure_date=date(2026, 9, 12), return_date=date(2026, 9, 14),
        status="active", planned_budget=3000, actual_spend=2350,
        currency="CNY",
    )
    ExpenseEntryFactory.create_pair(
        db, family_id=fam.id, trip_id=camping_trip.id, user_id=user.id,
        category_id=cat_transport.id, amount=450, expense_date=date(2026, 9, 12),
        description="油费 + 高速过路费",
    )
    ExpenseEntryFactory.create_pair(
        db, family_id=fam.id, trip_id=camping_trip.id, user_id=user.id,
        category_id=cat_hotel.id, amount=800, expense_date=date(2026, 9, 12),
        description="湖景帐篷营地 2晚",
    )
    ExpenseEntryFactory.create_pair(
        db, family_id=fam.id, trip_id=camping_trip.id, user_id=user.id,
        category_id=cat_food.id, amount=600, expense_date=date(2026, 9, 12),
        description="农家菜 + BBQ食材",
    )
    ExpenseEntryFactory.create_pair(
        db, family_id=fam.id, trip_id=camping_trip.id, user_id=user.id,
        category_id=cat_activity.id, amount=500, expense_date=date(2026, 9, 13),
        description="皮划艇租赁",
    )

    # 分摊组（露营行程，邀请了朋友）
    split_group, _ = SplitGroupFactory.get_or_create(
        db, trip_id=camping_trip.id, created_by_user_id=user.id,
        invite_code="CAMP26",
    )
    SplitParticipantFactory.get_or_create(
        db, group_id=split_group.id, name="完整数据测试", family_id=fam.id,
    )
    SplitParticipantFactory.get_or_create(
        db, group_id=split_group.id, name="老王",
    )
    SplitParticipantFactory.get_or_create(
        db, group_id=split_group.id, name="小李",
    )

    # ── 儿童账号 ──────────────────────────────────────────────────────────────
    child, _ = UserFactory.get_or_create_child(
        db, display_name="test_child", family_id=fam.id, avatar_color="#FF6B6B",
        username="xiaoming", password="TestRich123!", pin="🐱🐶🌟🌈",
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

    # E2E test fixture: 「测试家务」 with today's instance for chore-approval / milestone tests
    test_chore_tmpl, _ = ChoreFactory.get_or_create_template(
        db, family_id=fam.id, created_by=user.id,
        name="测试家务", emoji="🧪", coin_reward=5,
        frequency="daily", assignment_type="assigned",
        assigned_child_ids=[child.id],
    )
    ChoreFactory.get_or_create_instance(
        db, template=test_chore_tmpl, family_id=fam.id,
        child_user_id=child.id,
        date_bucket=datetime.utcnow().strftime("%Y-%m-%d"),
        status="available",
        submitted_at=None, approved_at=None,
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

    print("  [ok] test_rich — 完整数据账号已创建（含旅游 2 行程 + 6 费用 + 1 分摊组）")
