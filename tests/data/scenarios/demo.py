"""场景: demouser — 完整仿真数据（19实物+11金融+7负债+3租约+9心愿+2儿童+盲盒+旅游）。"""

from datetime import date, datetime, time, timedelta

from sqlalchemy.orm import Session

from factories.assets import AssetFactory
from factories.blindbox import BlindBoxFactory
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
    SplitSettlementFactory,
    TripCoOrganizerFactory,
    TripFactory,
)
from factories.users import FamilyFactory, UserFactory
from factories.wishes import ChildWishFactory, WishFactory
from models import Wish


def seed_demo_scenario(db: Session, verbose: bool = False) -> None:
    user, created = UserFactory.get_or_create(
        db,
        username="demouser",
        display_name="演示用户",
        password="DemoPass123",
        family_id=0,
        role="owner",
        avatar_color="#8B5CF6",
        flush=False,
    )

    if not created:
        if verbose:
            print("  [skip] demouser 已存在")
        return

    fam = FamilyFactory.get_or_create(db, name="演示家庭", created_by_id=user.id)
    user.family_id = fam.id
    db.flush()

    # 配偶账号
    spouse, _ = UserFactory.get_or_create(
        db,
        username="demouser_spouse",
        display_name="演示配偶",
        password="DemoPass123",
        family_id=fam.id,
        role="member",
        avatar_color="#EC4899",
    )

    # ── 19 实物资产 ───────────────────────────────────────────────────────────
    physical_assets = [
        ("上海浦东新区住宅", "房产", 3500000, 4200000, date(2018, 6, 1), "daily", None, "上海浦东"),
        ("宝马 5 系", "车辆", 380000, 280000, date(2020, 8, 15), "daily", 3650, "地下车库"),
        ("MacBook Pro 16寸", "数码", 19999, 14000, date(2022, 9, 1), "daily", 1825, "书房"),
        ("iPhone 15 Pro Max", "数码", 9999, 8500, date(2023, 9, 22), "daily", 730, None),
        ("iPad Pro 12.9寸", "数码", 8999, 7000, date(2023, 3, 1), "daily", 1095, None),
        ("索尼 A7M4 相机", "数码", 18000, 15000, date(2022, 12, 1), "weekly", 3650, "书房"),
        ("LG 65寸 OLED 电视", "家电", 12000, 9000, date(2021, 11, 11), "daily", 3650, "客厅"),
        ("戴森吸尘器 V15", "家电", 4500, 3500, date(2022, 5, 1), "weekly", 1825, "储物间"),
        ("美的空调 3匹", "家电", 6800, 5000, date(2020, 7, 1), "daily", 3650, "主卧"),
        ("宜家沙发三人位", "家具", 5999, 4000, date(2019, 3, 1), "daily", 3650, "客厅"),
        ("实木餐桌六人位", "家具", 8800, 7000, date(2019, 3, 1), "daily", 3650, "餐厅"),
        ("卡地亚戒指", "珠宝", 25000, 28000, date(2018, 2, 14), "rarely", None, "保险柜"),
        ("Hermès 铂金包", "箱包", 80000, 95000, date(2021, 10, 1), "rarely", None, "衣帽间"),
        ("耐克跑步机", "运动", 8000, 5000, date(2021, 1, 1), "weekly", 3650, "健身房"),
        ("雅马哈钢琴", "乐器", 35000, 30000, date(2020, 9, 1), "weekly", 7300, "客厅"),
        ("乐高 42143 法拉利", "玩具", 1299, 800, date(2023, 6, 1), "rarely", None, "书房"),
        ("柯基犬 — 豆豆", "宠物", 5000, 5000, date(2022, 3, 15), "daily", None, None),
        ("Chanel 香水套装", "美妆", 3200, 2000, date(2023, 12, 25), "daily", 365, None),
        ("百达翡丽手表", "珠宝", 120000, 135000, date(2019, 6, 18), "rarely", None, "保险柜"),
    ]

    created_physical: list = []
    for name, cat, pp, cv, pd, freq, lifespan, loc in physical_assets:
        a, _ = AssetFactory.get_or_create(
            db, user_id=user.id, family_id=fam.id,
            name=name, asset_type="physical", category_name=cat,
            purchase_price=pp, current_value=cv, purchase_date=pd,
            usage_frequency=freq, expected_lifespan_days=lifespan, location=loc,
        )
        created_physical.append(a)

    # ── 11 金融资产 ───────────────────────────────────────────────────────────
    financial_assets = [
        ("招商银行活期", "存款", 200000, 202000, date(2020, 1, 1), "招商银行", None, None),
        ("工商银行定期 3年", "存款", 500000, 545000, date(2022, 1, 1), "工商银行", 3.5, date(2025, 1, 1)),
        ("沪深300指数基金", "基金", 100000, 92000, date(2021, 6, 1), "支付宝", None, None),
        ("医疗行业基金", "基金", 50000, 43000, date(2022, 3, 1), "天天基金", None, None),
        ("贵州茅台股票", "股票", 80000, 110000, date(2020, 8, 1), "华泰证券", None, None),
        ("腾讯控股港股", "股票", 60000, 48000, date(2021, 2, 1), "富途证券", None, None),
        ("国债 2024-05", "债券", 100000, 103000, date(2024, 5, 1), "中国银行", 2.8, date(2027, 5, 1)),
        ("平安重疾险", "保险", 30000, 30000, date(2019, 1, 1), "平安保险", None, None),
        ("招商银行理财 R2", "理财产品", 200000, 207000, date(2024, 1, 1), "招商银行", 3.2, date(2025, 1, 1)),
        ("比特币 0.5 BTC", "数字货币", 150000, 220000, date(2023, 1, 1), "欧易", None, None),
        ("以太坊 5 ETH", "数字货币", 60000, 85000, date(2023, 3, 1), "币安", None, None),
    ]

    for name, cat, pp, cv, pd, inst, rate, mat in financial_assets:
        AssetFactory.get_or_create(
            db, user_id=user.id, family_id=fam.id,
            name=name, asset_type="financial", category_name=cat,
            purchase_price=pp, current_value=cv, purchase_date=pd,
            institution=inst, interest_rate=rate, maturity_date=mat,
        )

    # ── 7 负债 ────────────────────────────────────────────────────────────────
    car_asset = created_physical[1]  # 宝马 5 系
    home_asset = created_physical[0]  # 住宅

    liabilities = [
        ("住房贷款", "mortgage", 2000000, 1650000, 9800, 4.1, date(2018, 6, 1), date(2048, 6, 1), "工商银行", home_asset.id),
        ("车贷", "car_loan", 200000, 120000, 4200, 4.5, date(2020, 8, 15), date(2026, 8, 15), "招商银行", car_asset.id),
        ("信用卡 — 招行", "credit_card", 25000, 25000, 25000, 18.0, date(2024, 3, 1), None, "招商银行", None),
        ("信用卡 — 建行", "credit_card", 15000, 8000, 8000, 18.0, date(2024, 2, 1), None, "建设银行", None),
        ("消费贷 — 装修", "consumer_loan", 100000, 65000, 3200, 6.8, date(2022, 1, 1), date(2025, 1, 1), "平安银行", None),
        ("花呗", "consumer_loan", 20000, 12000, 2000, 14.6, date(2024, 1, 1), None, "蚂蚁集团", None),
        ("京东白条", "consumer_loan", 8000, 3000, 1000, 14.6, date(2024, 2, 1), None, "京东金融", None),
    ]

    for name, cat, orig, rem, mp, rate, sd, ed, inst, linked in liabilities:
        LiabilityFactory.get_or_create(
            db, user_id=user.id, family_id=fam.id,
            name=name, category=cat,
            original_amount=orig, remaining_amount=rem,
            monthly_payment=mp, interest_rate=rate,
            start_date=sd, end_date=ed,
            institution=inst, linked_asset_id=linked,
        )

    # ── 3 租约 ────────────────────────────────────────────────────────────────
    # (role, monthly_rent, deposit, start_date, end_date, linked_asset_id, counterparty, notes, is_active)
    rentals = [
        ("landlord", 8500, 17000, date(2023, 6, 1), date(2026, 5, 31), home_asset.id, "张先生", "浦东住宅次卧出租", True),
        ("tenant", 15000, 45000, date(2024, 1, 1), None, None, "万达商管", "办公室承租，不定期租约", True),
        ("landlord", 1500, 3000, date(2022, 1, 1), date(2023, 12, 31), None, "李女士", "车位出租，已结束", False),
    ]

    for role, mr, dep, sd, ed, linked, cp, notes, active in rentals:
        RentalContractFactory.get_or_create(
            db, user_id=user.id, family_id=fam.id,
            role=role, monthly_rent=mr, deposit=dep,
            start_date=sd, end_date=ed,
            linked_asset_id=linked, counterparty=cp,
            notes=notes, is_active=active,
        )

    # ── 9 心愿 ────────────────────────────────────────────────────────────────
    wishes = [
        ("特斯拉 Model Y", 280000, "high", "pending", True),
        ("日本家庭旅行", 50000, "high", "pending", False),
        ("钢琴课程年卡", 12000, "medium", "pending", False),
        ("Dyson 空气净化器", 5000, "medium", "pending", True),
        ("Switch 游戏机", 2500, "low", "pending", True),
        ("家庭健身器材", 15000, "medium", "pending", True),
        ("欧洲蜜月旅行", 80000, "high", "realized", False),
        ("MacBook Air M2", 9000, "medium", "realized", True),
        ("咖啡机", 3000, "low", "cancelled", True),
    ]

    for name, price, priority, status, converts in wishes:
        WishFactory.get_or_create(
            db, user_id=user.id, family_id=fam.id,
            name=name, expected_price=price,
            priority=priority, status=status,
            converts_to_asset=converts,
        )

    # ── 2 儿童账号 ────────────────────────────────────────────────────────────
    child1, _ = UserFactory.get_or_create_child(
        db, display_name="小宝", family_id=fam.id, avatar_color="#FF6B6B",
        username="xiaobao", pin="🐱🐶🌟🌈",
    )
    child1.second_factor_enabled = True
    child1.second_factor_type = "emoji_pin"
    child2, _ = UserFactory.get_or_create_child(
        db, display_name="大宝", family_id=fam.id, avatar_color="#4ADE80",
        username="dabao", pin="🐱🐶🌟🌈",
    )
    child2.second_factor_enabled = True
    child2.second_factor_type = "emoji_pin"

    # 任务模板
    chores = [
        ("整理房间", "🧹", 10, "daily", "pool"),
        ("洗碗", "🍽️", 8, "daily", "pool"),
        ("倒垃圾", "🗑️", 5, "daily", "assigned"),
        ("完成作业", "📚", 15, "daily", "pool"),
        ("浇花", "🌱", 5, "daily", "assigned"),
    ]

    today = date.today()
    for name, emoji, reward, freq, atype in chores:
        tmpl, _ = ChoreFactory.get_or_create_template(
            db, family_id=fam.id, created_by=user.id,
            name=name, emoji=emoji, coin_reward=reward,
            frequency=freq, assignment_type=atype,
        )
        # 最近 3 天已完成实例（小宝）
        for delta in range(3):
            bucket = (today - timedelta(days=delta)).isoformat()
            ChoreFactory.get_or_create_instance(
                db, template=tmpl, family_id=fam.id,
                child_user_id=child1.id, date_bucket=bucket, status="approved",
            )

    # 星星币余额（通过流水累计）
    CoinFactory.grant(
        db, family_id=fam.id, child_user_id=child1.id,
        amount=200, transaction_type="parent_grant",
        narrative="期末考试奖励", narrative_emoji="🏆",
    )
    CoinFactory.grant(
        db, family_id=fam.id, child_user_id=child2.id,
        amount=150, transaction_type="parent_grant",
        narrative="生日礼物", narrative_emoji="🎂",
    )

    # 儿童心愿
    child_wishes = [
        (child1.id, "乐高星球大战", "🧱", 200, "active", "high"),
        (child1.id, "任天堂 Switch", "🎮", 500, "pending_review", "high"),
        (child1.id, "画画课程", "🎨", 150, "active", "medium"),
        (child2.id, "芭比娃娃套装", "🪆", 120, "active", "medium"),
        (child2.id, "迪士尼乐园门票", "🏰", 300, "pending_review", "high"),
    ]

    for cid, name, emoji, cost, status, priority in child_wishes:
        ChildWishFactory.get_or_create(
            db, child_user_id=cid, family_id=fam.id,
            name=name, emoji=emoji, star_coin_cost=cost,
            status=status, priority=priority,
        )

    # ── 盲盒配置 ──────────────────────────────────────────────────────────────
    BlindBoxFactory.get_or_create_config(db, family_id=fam.id, enabled=True)

    gifts = [
        ("冰淇淋", "🍦", 3, "周末下午的惊喜"),
        ("电影票两张", "🎬", 6, "家庭电影之夜"),
        ("披萨外卖", "🍕", 5, "不用做饭的晚餐"),
        ("游乐场一日游", "🎡", 8, "周末大冒险"),
        ("新玩具", "🎁", 7, "神秘礼物"),
    ]

    for name, emoji, score, desc in gifts:
        BlindBoxFactory.get_or_create_gift(
            db, family_id=fam.id, created_by=user.id,
            name=name, emoji=emoji, value_score=score, description=desc,
        )

    # ── 旅游 ──────────────────────────────────────────────────────────────────
    # 支出类别（复用已有的系统预置，或创建）
    ec_food, _ = ExpenseCategoryFactory.get_or_create(db, name="餐饮", icon="food", is_system=True, sort_order=1)
    ec_transport, _ = ExpenseCategoryFactory.get_or_create(db, name="交通", icon="transport", is_system=True, sort_order=2)
    ec_hotel, _ = ExpenseCategoryFactory.get_or_create(db, name="住宿", icon="hotel", is_system=True, sort_order=3)
    ec_activity, _ = ExpenseCategoryFactory.get_or_create(db, name="活动", icon="activity", is_system=True, sort_order=4)
    ec_shopping, _ = ExpenseCategoryFactory.get_or_create(db, name="购物", icon="shopping", is_system=True, sort_order=5)
    ec_misc, _ = ExpenseCategoryFactory.get_or_create(db, name="杂项", icon="label", is_system=True, sort_order=6)

    # 行程1: 日本家庭旅行（planning，从心愿转化）
    japan_wish_ref = db.query(Wish).filter(Wish.name == "日本家庭旅行", Wish.family_id == fam.id).first()
    japan_trip, _ = TripFactory.get_or_create(
        db, user_id=user.id, family_id=fam.id,
        name="日本家庭旅行", destination="东京 · 京都 · 大阪",
        departure_date=date(2026, 10, 1), return_date=date(2026, 10, 7),
        status="planning", planned_budget=50000, initial_funding=8000,
        currency="CNY",
        wish_id=japan_wish_ref.id if japan_wish_ref else None,
        timezone="Asia/Tokyo",
    )
    # 日本旅行费用（提前预订）
    ExpenseEntryFactory.create_pair(
        db, family_id=fam.id, trip_id=japan_trip.id, user_id=user.id,
        category_id=ec_transport.id, amount=12800, expense_date=date(2026, 7, 15),
        description="往返机票（2大2小）",
    )
    ExpenseEntryFactory.create_pair(
        db, family_id=fam.id, trip_id=japan_trip.id, user_id=user.id,
        category_id=ec_hotel.id, amount=9600, expense_date=date(2026, 7, 20),
        description="新宿华盛顿酒店 6晚",
    )
    ExpenseEntryFactory.create_pair(
        db, family_id=fam.id, trip_id=japan_trip.id, user_id=user.id,
        category_id=ec_hotel.id, amount=5400, expense_date=date(2026, 7, 22),
        description="京都町屋民宿 2晚",
    )
    ExpenseEntryFactory.create_pair(
        db, family_id=fam.id, trip_id=japan_trip.id, user_id=spouse.id,
        category_id=ec_activity.id, amount=2400, expense_date=date(2026, 8, 1),
        description="迪士尼海洋门票预订",
    )
    # 配偶作为共同组织者
    TripCoOrganizerFactory.get_or_create(
        db, trip_id=japan_trip.id, user_id=spouse.id,
    )

    # 行程2: 三亚年假（active，正在进行）
    sanya_trip, _ = TripFactory.get_or_create(
        db, user_id=user.id, family_id=fam.id,
        name="三亚年假", destination="三亚湾 · 亚龙湾",
        departure_date=date(2026, 9, 15), return_date=date(2026, 9, 20),
        status="active", planned_budget=15000, actual_spend=11200,
        currency="CNY", timezone="Asia/Shanghai",
    )
    sanya_expenses = [
        (ec_transport.id, 3200, date(2026, 9, 1), "往返机票", user.id),
        (ec_hotel.id, 4800, date(2026, 9, 1), "亚龙湾万豪 5晚", user.id),
        (ec_food.id, 1200, date(2026, 9, 15), "海鲜第一餐", user.id),
        (ec_food.id, 680, date(2026, 9, 16), "椰子鸡 + 清补凉", spouse.id),
        (ec_activity.id, 800, date(2026, 9, 16), "蜈支洲岛一日游", user.id),
        (ec_activity.id, 520, date(2026, 9, 17), "潜水体验", spouse.id),
    ]
    for cat_id, amt, edate, desc, uid in sanya_expenses:
        ExpenseEntryFactory.create_pair(
            db, family_id=fam.id, trip_id=sanya_trip.id, user_id=uid,
            category_id=cat_id, amount=amt, expense_date=edate,
            description=desc,
        )
    # 三亚分摊组（夫妻 AA）
    sanya_split, _ = SplitGroupFactory.get_or_create(
        db, trip_id=sanya_trip.id, created_by_user_id=user.id,
        invite_code="SANYA1",
    )
    SplitParticipantFactory.get_or_create(
        db, group_id=sanya_split.id, name="演示用户", family_id=fam.id,
    )
    SplitParticipantFactory.get_or_create(
        db, group_id=sanya_split.id, name="演示配偶", family_id=fam.id,
    )

    # 行程3: 成都美食之旅（settled，已结束并结算）
    chengdu_trip, _ = TripFactory.get_or_create(
        db, user_id=user.id, family_id=fam.id,
        name="成都美食之旅", destination="成都 · 都江堰",
        departure_date=date(2026, 6, 5), return_date=date(2026, 6, 8),
        status="settled", planned_budget=8000, actual_spend=7350,
        currency="CNY", timezone="Asia/Shanghai",
    )
    chengdu_expenses = [
        (ec_transport.id, 2100, date(2026, 5, 20), "高铁往返", user.id),
        (ec_hotel.id, 1800, date(2026, 5, 22), "太古里亚朵 3晚", user.id),
        (ec_food.id, 680, date(2026, 6, 5), "马路边边火锅", user.id),
        (ec_food.id, 420, date(2026, 6, 6), "小龙坎火锅", spouse.id),
        (ec_food.id, 350, date(2026, 6, 6), "宽窄巷子小吃", user.id),
        (ec_activity.id, 480, date(2026, 6, 7), "都江堰门票", user.id),
        (ec_shopping.id, 520, date(2026, 6, 7), "伴手礼：火锅底料+兔头", spouse.id),
        (ec_food.id, 380, date(2026, 6, 8), "返程前最后一顿串串", user.id),
        (ec_misc.id, 620, date(2026, 6, 8), "打车+行李寄存", user.id),
    ]
    for cat_id, amt, edate, desc, uid in chengdu_expenses:
        ExpenseEntryFactory.create_pair(
            db, family_id=fam.id, trip_id=chengdu_trip.id, user_id=uid,
            category_id=cat_id, amount=amt, expense_date=edate,
            description=desc,
        )
    # 成都分摊组 + 结算
    chengdu_split, _ = SplitGroupFactory.get_or_create(
        db, trip_id=chengdu_trip.id, created_by_user_id=user.id,
        invite_code="CD2026", is_active=False,
    )
    SplitParticipantFactory.get_or_create(
        db, group_id=chengdu_split.id, name="演示用户", family_id=fam.id,
    )
    SplitParticipantFactory.get_or_create(
        db, group_id=chengdu_split.id, name="演示配偶", family_id=fam.id,
    )
    SplitSettlementFactory.get_or_create(
        db, trip_id=chengdu_trip.id,
        from_participant_name="演示配偶", to_participant_name="演示用户",
        amount=480, is_complete=True,
        settled_at=datetime(2026, 6, 10, 15, 30),
        settled_by_user_id=spouse.id,
    )

    # 行程4: 国庆露营（planning，刚创建）
    moganshan_trip, _ = TripFactory.get_or_create(
        db, user_id=user.id, family_id=fam.id,
        name="国庆莫干山露营", destination="莫干山",
        departure_date=date(2026, 10, 3), return_date=date(2026, 10, 5),
        status="planning", planned_budget=3500,
        currency="CNY",
    )

    # 行程5: 已取消的旅行
    TripFactory.get_or_create(
        db, user_id=user.id, family_id=fam.id,
        name="春节东南亚游", destination="曼谷 · 清迈",
        departure_date=date(2026, 1, 25), return_date=date(2026, 2, 1),
        status="cancelled", planned_budget=20000, actual_spend=0,
        currency="CNY", is_active=False,
    )

    # ── 行程项 (Itinerary Items) ─────────────────────────────────────────────

    # 自定义类型
    custom_type_shopping, _ = ItineraryItemTypeFactory.get_or_create(
        db, name="购物", icon="shopping-bag", family_id=fam.id, sort_order=1,
    )
    custom_type_spa, _ = ItineraryItemTypeFactory.get_or_create(
        db, name="温泉", icon="spa", family_id=fam.id, sort_order=2,
    )

    # 三亚年假行程项（active, 6天 — 丰富的时间线数据）
    # Day 1: 9月15日 — 抵达
    ItineraryItemFactory.get_or_create(
        db, trip_id=sanya_trip.id, family_id=fam.id,
        date=date(2026, 9, 15), type="transport", sort_order=0,
        start_time=time(8, 0), end_time=time(11, 30),
        location="凤凰机场",
        description="接机 → 酒店",
        type_metadata={"origin": "上海虹桥", "destination": "三亚凤凰"},
    )
    ItineraryItemFactory.get_or_create(
        db, trip_id=sanya_trip.id, family_id=fam.id,
        date=date(2026, 9, 15), type="accommodation", sort_order=1,
        start_time=time(14, 0),
        location="亚龙湾万豪度假酒店",
        description="海景大床房 5晚",
        cost_amount=4800, cost_currency="CNY",
        type_metadata={"check_in_time": "14:00", "check_out_time": "12:00"},
    )
    ItineraryItemFactory.get_or_create(
        db, trip_id=sanya_trip.id, family_id=fam.id,
        date=date(2026, 9, 15), type="dining", sort_order=2,
        start_time=time(18, 0),
        location="酒店海景餐厅",
        description="海鲜自助晚餐",
        cost_amount=1200, cost_currency="CNY",
        type_metadata={"diners": 4},
    )
    # Day 2: 9月16日 — 椰子鸡 + 蜈支洲岛
    ItineraryItemFactory.get_or_create(
        db, trip_id=sanya_trip.id, family_id=fam.id,
        date=date(2026, 9, 16), type="dining", sort_order=0,
        start_time=time(8, 30),
        location="椰梦长廊椰子鸡",
        description="正宗海南椰子鸡早餐",
        cost_amount=680, cost_currency="CNY",
        type_metadata={"diners": 4},
    )
    ItineraryItemFactory.get_or_create(
        db, trip_id=sanya_trip.id, family_id=fam.id,
        date=date(2026, 9, 16), type="activity", sort_order=1,
        start_time=time(10, 0), end_time=time(17, 0),
        location="蜈支洲岛",
        description="一日游含浮潜",
        cost_amount=800, cost_currency="CNY",
    )
    # Day 3: 9月17日 — 潜水 + spa
    ItineraryItemFactory.get_or_create(
        db, trip_id=sanya_trip.id, family_id=fam.id,
        date=date(2026, 9, 17), type="activity", sort_order=0,
        start_time=time(9, 0), end_time=time(12, 0),
        location="亚龙湾潜水基地",
        description="体验潜水（PADI认证）",
        cost_amount=520, cost_currency="CNY",
    )
    ItineraryItemFactory.get_or_create(
        db, trip_id=sanya_trip.id, family_id=fam.id,
        date=date(2026, 9, 17), type="custom", sort_order=1,
        start_time=time(15, 0),
        location="珠江南田温泉",
        description="家庭温泉套餐",
        cost_amount=480, cost_currency="CNY",
        custom_type_id=custom_type_spa.id,
    )
    # Day 5: 9月19日 — 购物
    ItineraryItemFactory.get_or_create(
        db, trip_id=sanya_trip.id, family_id=fam.id,
        date=date(2026, 9, 19), type="custom", sort_order=0,
        start_time=time(10, 0), end_time=time(14, 0),
        location="三亚国际免税城",
        description="免税购物",
        cost_amount=3500, cost_currency="CNY",
        custom_type_id=custom_type_shopping.id,
    )
    # Day 6: 9月20日 — 返程
    ItineraryItemFactory.get_or_create(
        db, trip_id=sanya_trip.id, family_id=fam.id,
        date=date(2026, 9, 20), type="transport", sort_order=0,
        start_time=time(13, 0),
        location="亚龙湾 → 凤凰机场",
        description="酒店送机",
        type_metadata={"origin": "亚龙湾万豪", "destination": "三亚凤凰机场"},
    )
    # 独立费用（非行程项关联）— timeline 上混合显示
    ExpenseEntryFactory.create_pair(
        db, family_id=fam.id, trip_id=sanya_trip.id, user_id=spouse.id,
        category_id=ec_shopping.id, amount=150, expense_date=date(2026, 9, 18),
        description="海边纪念品",
    )

    # 成都美食之旅行程项（settled, 4天 — 已结束）
    # Day 1: 6月5日
    ItineraryItemFactory.get_or_create(
        db, trip_id=chengdu_trip.id, family_id=fam.id,
        date=date(2026, 6, 5), type="transport", sort_order=0,
        start_time=time(7, 30), end_time=time(15, 0),
        location="成都东站",
        description="高铁到达",
        cost_amount=2100, cost_currency="CNY",
        type_metadata={"origin": "上海虹桥", "destination": "成都东"},
    )
    ItineraryItemFactory.get_or_create(
        db, trip_id=chengdu_trip.id, family_id=fam.id,
        date=date(2026, 6, 5), type="dining", sort_order=1,
        start_time=time(18, 0),
        location="马路边边火锅（春熙路店）",
        description="正宗成都火锅",
        cost_amount=680, cost_currency="CNY",
        type_metadata={"diners": 2},
    )
    # Day 2: 6月6日
    ItineraryItemFactory.get_or_create(
        db, trip_id=chengdu_trip.id, family_id=fam.id,
        date=date(2026, 6, 6), type="dining", sort_order=0,
        start_time=time(12, 0),
        location="小龙坎火锅（宽窄巷子店）",
        description="经典牛油火锅",
        cost_amount=420, cost_currency="CNY",
        type_metadata={"diners": 2},
    )
    ItineraryItemFactory.get_or_create(
        db, trip_id=chengdu_trip.id, family_id=fam.id,
        date=date(2026, 6, 6), type="activity", sort_order=1,
        start_time=time(14, 0), end_time=time(17, 0),
        location="宽窄巷子",
        description="逛吃逛吃",
    )
    ItineraryItemFactory.get_or_create(
        db, trip_id=chengdu_trip.id, family_id=fam.id,
        date=date(2026, 6, 6), type="dining", sort_order=2,
        start_time=time(17, 30),
        location="宽窄巷子小吃街",
        description="三大炮、糖油果子、钵钵鸡",
        cost_amount=350, cost_currency="CNY",
        type_metadata={"diners": 2},
    )
    # Day 3: 6月7日 — 都江堰
    ItineraryItemFactory.get_or_create(
        db, trip_id=chengdu_trip.id, family_id=fam.id,
        date=date(2026, 6, 7), type="activity", sort_order=0,
        start_time=time(8, 0), end_time=time(15, 0),
        location="都江堰景区",
        description="世界文化遗产一日游",
        cost_amount=480, cost_currency="CNY",
    )
    ItineraryItemFactory.get_or_create(
        db, trip_id=chengdu_trip.id, family_id=fam.id,
        date=date(2026, 6, 7), type="custom", sort_order=1,
        start_time=time(16, 0),
        location="春熙路伴手礼店",
        description="火锅底料+兔头+张飞牛肉",
        cost_amount=520, cost_currency="CNY",
        custom_type_id=custom_type_shopping.id,
    )
    # Day 4: 6月8日 — 返程
    ItineraryItemFactory.get_or_create(
        db, trip_id=chengdu_trip.id, family_id=fam.id,
        date=date(2026, 6, 8), type="dining", sort_order=0,
        start_time=time(9, 0),
        location="串串香（太古里店）",
        description="返程前最后一顿",
        cost_amount=380, cost_currency="CNY",
        type_metadata={"diners": 2},
    )
    ItineraryItemFactory.get_or_create(
        db, trip_id=chengdu_trip.id, family_id=fam.id,
        date=date(2026, 6, 8), type="transport", sort_order=1,
        start_time=time(14, 0),
        location="成都东站 → 上海虹桥",
        description="高铁返程",
        type_metadata={"origin": "成都东", "destination": "上海虹桥"},
    )

    # 莫干山露营行程项（planning, 3天）
    ItineraryItemFactory.get_or_create(
        db, trip_id=moganshan_trip.id, family_id=fam.id,
        date=date(2026, 10, 3), type="transport", sort_order=0,
        start_time=time(9, 0),
        location="杭州 → 莫干山",
        description="自驾约1.5小时",
        type_metadata={"origin": "杭州", "destination": "莫干山"},
    )
    ItineraryItemFactory.get_or_create(
        db, trip_id=moganshan_trip.id, family_id=fam.id,
        date=date(2026, 10, 3), type="accommodation", sort_order=1,
        start_time=time(14, 0),
        location="莫干山裸心谷",
        description="山景别墅 2晚",
        cost_amount=2800, cost_currency="CNY",
        type_metadata={"check_in_time": "14:00", "check_out_time": "11:00"},
    )
    ItineraryItemFactory.get_or_create(
        db, trip_id=moganshan_trip.id, family_id=fam.id,
        date=date(2026, 10, 4), type="activity", sort_order=0,
        start_time=time(8, 0), end_time=time(12, 0),
        location="莫干山登山步道",
        description="竹海徒步",
    )
    ItineraryItemFactory.get_or_create(
        db, trip_id=moganshan_trip.id, family_id=fam.id,
        date=date(2026, 10, 5), type="transport", sort_order=0,
        start_time=time(10, 0),
        location="莫干山 → 杭州",
        description="返程",
        type_metadata={"origin": "莫干山", "destination": "杭州"},
    )

    print("  [ok] demouser — 完整仿真数据已创建（19实物+11金融+7负债+3租约+9心愿+2儿童+盲盒+5行程+行程项+21费用+2结算）")
