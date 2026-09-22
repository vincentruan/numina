"""场景: test_rich — 完整数据（多资产 + 负债 + 心愿 + 儿童 + 旅游）。"""

from datetime import date, datetime, time

from sqlalchemy.orm import Session

from factories.assets import AssetFactory
from factories.children import ChoreFactory, CoinFactory
from factories.liabilities import LiabilityFactory
from factories.rentals import RentalContractFactory
from factories.travel import (
    ExpenseCategoryFactory,
    ExpenseEntryFactory,
    ItineraryItemFactory,
    ItineraryItemTypeFactory,
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
    # 房东：车位出租（不关联资产）
    RentalContractFactory.get_or_create(
        db,
        user_id=user.id, family_id=fam.id,
        role="landlord", monthly_rent=800, deposit=1600,
        start_date=date(2024, 6, 1), end_date=date(2025, 5, 31),
        counterparty="赵先生", notes="地下车位出租，一年期",
    )
    # 租客：公寓承租（不定期）
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

    # 行程项 — 露营行程（active, 3天完整时间线）
    # Day 1: 9月12日 — 出发 + 入住 + 晚餐
    ItineraryItemFactory.get_or_create(
        db, trip_id=camping_trip.id, family_id=fam.id,
        date=date(2026, 9, 12), type="transport", sort_order=0,
        start_time=time(8, 0),
        location="家 → 千岛湖",
        description="自驾出发，约3小时车程",
        type_metadata={"origin": "杭州 home", "destination": "千岛湖"},
    )
    ItineraryItemFactory.get_or_create(
        db, trip_id=camping_trip.id, family_id=fam.id,
        date=date(2026, 9, 12), type="accommodation", sort_order=1,
        start_time=time(14, 0),
        location="千岛湖湖景帐篷营地",
        description="湖景大帐篷，含早",
        cost_amount=800, cost_currency="CNY",
        type_metadata={"check_in_time": "14:00", "check_out_time": "12:00"},
    )
    ItineraryItemFactory.get_or_create(
        db, trip_id=camping_trip.id, family_id=fam.id,
        date=date(2026, 9, 12), type="dining", sort_order=2,
        start_time=time(18, 0),
        location="营地BBQ区",
        description="湖边自助烧烤",
        cost_amount=300, cost_currency="CNY",
        type_metadata={"diners": 4},
    )
    # Day 2: 9月13日 — 皮划艇 + 农家菜
    ItineraryItemFactory.get_or_create(
        db, trip_id=camping_trip.id, family_id=fam.id,
        date=date(2026, 9, 13), type="activity", sort_order=0,
        start_time=time(9, 0), end_time=time(12, 0),
        location="千岛湖水上运动中心",
        description="皮划艇半日游",
        cost_amount=500, cost_currency="CNY",
    )
    ItineraryItemFactory.get_or_create(
        db, trip_id=camping_trip.id, family_id=fam.id,
        date=date(2026, 9, 13), type="dining", sort_order=1,
        start_time=time(12, 30),
        location="湖畔农家菜馆",
        description="千岛湖鱼头汤 + 时蔬",
        cost_amount=300, cost_currency="CNY",
        type_metadata={"diners": 4},
    )
    # Day 3: 9月14日 — 返程
    ItineraryItemFactory.get_or_create(
        db, trip_id=camping_trip.id, family_id=fam.id,
        date=date(2026, 9, 14), type="transport", sort_order=0,
        start_time=time(10, 0),
        location="千岛湖 → 家",
        description="返程，途中服务区休息",
        type_metadata={"origin": "千岛湖", "destination": "杭州 home"},
    )
    # 独立费用（非行程项关联）— 模拟 AE2：timeline 上混合显示
    ExpenseEntryFactory.create_pair(
        db, family_id=fam.id, trip_id=camping_trip.id, user_id=user.id,
        category_id=cat_activity.id, amount=60, expense_date=date(2026, 9, 13),
        description="景区停车费",
    )

    # 行程项 — 日本旅行（planning, 覆盖多种类型 + 自定义类型）
    custom_type_spa, _ = ItineraryItemTypeFactory.get_or_create(
        db, name="温泉", icon="spa", family_id=fam.id, sort_order=1,
    )
    # Day 1: 10月1日 — 抵达 + 入住
    ItineraryItemFactory.get_or_create(
        db, trip_id=japan_trip.id, family_id=fam.id,
        date=date(2026, 10, 1), type="transport", sort_order=0,
        start_time=time(10, 0), end_time=time(14, 0),
        location="浦东机场 → 成田机场",
        description="航班 MU523",
        cost_amount=5800, cost_currency="CNY",
        type_metadata={"origin": "上海浦东", "destination": "东京成田"},
    )
    ItineraryItemFactory.get_or_create(
        db, trip_id=japan_trip.id, family_id=fam.id,
        date=date(2026, 10, 1), type="accommodation", sort_order=1,
        start_time=time(15, 0),
        location="新宿花园酒店",
        description="豪华双床房 6晚",
        cost_amount=4200, cost_currency="CNY",
        type_metadata={"check_in_time": "15:00", "check_out_time": "11:00"},
    )
    # Day 3: 10月3日 — 迪士尼
    ItineraryItemFactory.get_or_create(
        db, trip_id=japan_trip.id, family_id=fam.id,
        date=date(2026, 10, 3), type="activity", sort_order=0,
        start_time=time(8, 0), end_time=time(21, 0),
        location="东京迪士尼海洋",
        description="全家一日游",
        cost_amount=2400, cost_currency="CNY",
        type_metadata={"ticket_price": "600"},
    )
    # Day 5: 10月5日 — 京都 + 温泉（自定义类型）
    ItineraryItemFactory.get_or_create(
        db, trip_id=japan_trip.id, family_id=fam.id,
        date=date(2026, 10, 5), type="activity", sort_order=0,
        start_time=time(9, 0),
        location="伏见稻荷大社",
        description="千本鸟居徒步",
    )
    ItineraryItemFactory.get_or_create(
        db, trip_id=japan_trip.id, family_id=fam.id,
        date=date(2026, 10, 5), type="custom", sort_order=1,
        start_time=time(16, 0),
        location="京都岚山温泉",
        description="露天风吕体验",
        cost_amount=800, cost_currency="CNY",
        custom_type_id=custom_type_spa.id,
    )
    # Day 7: 10月7日 — 返程
    ItineraryItemFactory.get_or_create(
        db, trip_id=japan_trip.id, family_id=fam.id,
        date=date(2026, 10, 7), type="transport", sort_order=0,
        start_time=time(14, 0),
        location="关西机场 → 浦东",
        description="航班 MU728",
        type_metadata={"origin": "大阪关西", "destination": "上海浦东"},
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
