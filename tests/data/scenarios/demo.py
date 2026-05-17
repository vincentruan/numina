"""场景: demouser — 完整仿真数据（19实物+11金融+7负债+9心愿+2儿童+盲盒）。"""

from datetime import date, timedelta

from sqlalchemy.orm import Session

from factories.assets import AssetFactory
from factories.blindbox import BlindBoxFactory
from factories.children import ChoreFactory, CoinFactory
from factories.liabilities import LiabilityFactory
from factories.users import FamilyFactory, UserFactory
from factories.wishes import ChildWishFactory, WishFactory


def seed_demo_scenario(db: Session, verbose: bool = False) -> None:
    user, created = UserFactory.get_or_create(
        db,
        username="demouser",
        display_name="演示用户",
        password="DemoPass123",
        family_id=0,
        role="owner",
        avatar_color="#8B5CF6",
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
    child2, _ = UserFactory.get_or_create_child(
        db, display_name="大宝", family_id=fam.id, avatar_color="#4ADE80",
        username="dabao", pin="🦊🐼🦁🐯",
    )

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

    print("  [ok] demouser — 完整仿真数据已创建（19实物+11金融+7负债+9心愿+2儿童+盲盒）")
