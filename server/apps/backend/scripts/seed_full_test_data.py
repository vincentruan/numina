"""Seed comprehensive test data: users, families, assets, liabilities, tags, wishes.

Run from server/ directory: uv run python apps/backend/scripts/seed_full_test_data.py
"""
import sys
from pathlib import Path
import random
from datetime import date, datetime, timedelta

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent.parent))

import apps.backend.app.models  # noqa: F401 — registers all ORM models
from apps.backend.app.database import SessionLocal
from apps.backend.app.models.family import Family
from apps.backend.app.models.family_invitation_code import FamilyInvitationCode
from apps.backend.app.models.user import User
from apps.backend.app.models.asset import Asset
from apps.backend.app.models.liability import Liability
from apps.backend.app.models.tag import Tag
from apps.backend.app.models.wish import Wish
from apps.backend.app.models.category import Category
from apps.backend.app.models.ai_provider_config import AIProviderConfig
from apps.backend.app.services.auth import hash_password
from apps.backend.app.services.ai_crypto import encrypt_api_key
from packages.core.snowflake import next_id


def seed_test_users(db):
    """Create test families and users."""
    # Create invitation codes
    codes_data = [
        ("AUTO-TEST", "testuser family"),
        ("AUTO-TEST-2", "testuser2 family"),
        ("DEMO-CODE", "demouser family"),
        ("DEMO-SPOUSE", "demouser spouse"),
    ]

    for code, description in codes_data:
        existing = db.query(FamilyInvitationCode).filter_by(code=code).first()
        if not existing:
            db.add(FamilyInvitationCode(code=code))
            print(f"Created invitation code: {code}")

    db.commit()

    # Create families and users
    users_data = [
        {
            "username": "testuser",
            "display_name": "Test User",
            "password": "TestPass123",
            "family_name": "Test Family",
            "role": "owner",
            "invitation_code": "AUTO-TEST",
        },
        {
            "username": "testuser2",
            "display_name": "Test User 2",
            "password": "TestPass456",
            "family_name": "Test Family 2",
            "role": "owner",
            "invitation_code": "AUTO-TEST-2",
        },
        {
            "username": "demouser",
            "display_name": "Demo User",
            "password": "DemoPass123",
            "family_name": "Demo Family",
            "role": "owner",
            "invitation_code": "DEMO-CODE",
        },
    ]

    for user_data in users_data:
        existing_user = db.query(User).filter_by(username=user_data["username"]).first()
        if existing_user:
            existing_user.password_hash = hash_password(user_data["password"])
            print(f"User {user_data['username']} already exists (family_id={existing_user.family_id}); password resynced")
            continue

        # Create family
        family_id = next_id()
        family = Family(
            id=family_id,
            name=user_data["family_name"],
            created_by=family_id,
        )
        db.add(family)
        db.flush()

        # Create user
        user_id = next_id()
        password_hash = hash_password(user_data["password"])
        user = User(
            id=user_id,
            username=user_data["username"],
            display_name=user_data["display_name"],
            password_hash=password_hash,
            family_id=family.id,
            role=user_data["role"],
            is_active=True,
        )
        db.add(user)
        db.flush()

        family.created_by = user.id
        print(f"Created user: {user_data['username']} (id={user.id}, family_id={family.id})")

    db.commit()


def seed_tags(db, user: User):
    """Create tags for a user's family."""
    tags_data = [
        {"name": "重要", "color": "#EF4444"},
        {"name": "日常", "color": "#22C55E"},
        {"name": "投资", "color": "#3B82F6"},
        {"name": "收藏", "color": "#F97316"},
        {"name": "工作", "color": "#8B5CF6"},
        {"name": "生活", "color": "#14B8A6"},
    ]

    created_tags = []
    for tag_data in tags_data:
        existing = db.query(Tag).filter_by(
            family_id=user.family_id,
            name=tag_data["name"]
        ).first()
        if existing:
            created_tags.append(existing)
            continue

        tag = Tag(
            id=next_id(),
            family_id=user.family_id,
            name=tag_data["name"],
            color=tag_data["color"],
        )
        db.add(tag)
        created_tags.append(tag)

    db.commit()
    print(f"Created/verified {len(created_tags)} tags for family {user.family_id}")
    return created_tags


def seed_assets(db, user: User, tags: list[Tag]):
    """Create diverse assets for a user."""
    categories = db.query(Category).filter(Category.is_system == True).all()  # noqa: E712
    if not categories:
        print("ERROR: No system categories found. Run seed_categories first.")
        return []

    cat_map = {c.name: c for c in categories}

    # Physical assets
    physical_assets = [
        {
            "name": "北京朝阳区公寓",
            "category": "房产",
            "asset_type": "physical",
            "purchase_price": 3500000,
            "current_value": 4200000,
            "purchase_date": date(2020, 3, 15),
            "status": "in_use",
            "location": "北京市朝阳区",
            "expected_lifespan_days": 36500,  # 100 years
            "annual_maintenance_cost": 12000,
            "usage_frequency": "daily",
            "notes": "三室两厅，交通便利",
        },
        {
            "name": "特斯拉Model 3",
            "category": "车辆",
            "asset_type": "physical",
            "purchase_price": 280000,
            "current_value": 200000,
            "purchase_date": date(2022, 6, 1),
            "status": "in_use",
            "location": "车库",
            "expected_lifespan_days": 3650,  # 10 years
            "annual_maintenance_cost": 5000,
            "usage_frequency": "daily",
            "notes": "续航里程468km",
        },
        {
            "name": "MacBook Pro 16寸",
            "category": "数码",
            "asset_type": "physical",
            "purchase_price": 18999,
            "current_value": 15000,
            "purchase_date": date(2023, 11, 15),
            "status": "in_use",
            "location": "书房",
            "expected_lifespan_days": 1825,  # 5 years
            "annual_maintenance_cost": 0,
            "usage_frequency": "daily",
            "notes": "M3 Pro芯片，18GB内存",
            "warranty_expiry_date": date(2025, 11, 15),
        },
        {
            "name": "iPhone 15 Pro Max",
            "category": "数码",
            "asset_type": "physical",
            "purchase_price": 9999,
            "current_value": 8500,
            "purchase_date": date(2024, 1, 20),
            "status": "in_use",
            "location": "随身",
            "expected_lifespan_days": 1095,  # 3 years
            "annual_maintenance_cost": 0,
            "usage_frequency": "daily",
            "warranty_expiry_date": date(2025, 1, 20),
        },
        {
            "name": "索尼A7M4相机",
            "category": "数码",
            "asset_type": "physical",
            "purchase_price": 16999,
            "current_value": 14000,
            "purchase_date": date(2023, 5, 10),
            "status": "in_use",
            "location": "书房",
            "expected_lifespan_days": 3650,  # 10 years
            "annual_maintenance_cost": 500,
            "usage_frequency": "weekly",
            "notes": "全画幅微单，3300万像素",
        },
        {
            "name": "戴森V15吸尘器",
            "category": "家电",
            "asset_type": "physical",
            "purchase_price": 5490,
            "current_value": 4500,
            "purchase_date": date(2023, 8, 1),
            "status": "in_use",
            "location": "客厅",
            "expected_lifespan_days": 3650,  # 10 years
            "annual_maintenance_cost": 200,
            "usage_frequency": "weekly",
        },
        {
            "name": "美的对开门冰箱",
            "category": "家电",
            "asset_type": "physical",
            "purchase_price": 8999,
            "current_value": 7500,
            "purchase_date": date(2021, 10, 15),
            "status": "in_use",
            "location": "厨房",
            "expected_lifespan_days": 7300,  # 20 years
            "annual_maintenance_cost": 100,
            "usage_frequency": "daily",
        },
        {
            "name": "Herman Miller人体工学椅",
            "category": "家具",
            "asset_type": "physical",
            "purchase_price": 12800,
            "current_value": 10000,
            "purchase_date": date(2022, 4, 1),
            "status": "in_use",
            "location": "书房",
            "expected_lifespan_days": 10950,  # 30 years
            "annual_maintenance_cost": 0,
            "usage_frequency": "daily",
            "notes": "Aeron经典款",
        },
        {
            "name": "卡地亚Love手镯",
            "category": "珠宝",
            "asset_type": "physical",
            "purchase_price": 48000,
            "current_value": 52000,
            "purchase_date": date(2021, 2, 14),
            "status": "in_use",
            "location": "卧室",
            "expected_lifespan_days": 36500,  # 保值品
            "annual_maintenance_cost": 0,
            "usage_frequency": "daily",
            "notes": "18K玫瑰金",
        },
        {
            "name": "LV Neverfull手提包",
            "category": "箱包",
            "asset_type": "physical",
            "purchase_price": 12500,
            "current_value": 14000,
            "purchase_date": date(2022, 8, 10),
            "status": "in_use",
            "location": "卧室",
            "expected_lifespan_days": 18250,  # 50 years
            "annual_maintenance_cost": 500,
            "usage_frequency": "weekly",
            "notes": "经典老花款",
        },
        {
            "name": "优衣库羽绒服",
            "category": "服饰",
            "asset_type": "physical",
            "purchase_price": 799,
            "current_value": 400,
            "purchase_date": date(2023, 12, 1),
            "status": "in_use",
            "location": "衣柜",
            "expected_lifespan_days": 1095,  # 3 years
            "annual_maintenance_cost": 0,
            "usage_frequency": "weekly",
        },
        {
            "name": "海蓝之谜精华霜",
            "category": "美妆",
            "asset_type": "physical",
            "purchase_price": 3150,
            "current_value": 2500,
            "purchase_date": date(2024, 2, 1),
            "status": "in_use",
            "location": "浴室",
            "expected_lifespan_days": 180,  # 6 months
            "annual_maintenance_cost": 0,
            "usage_frequency": "daily",
        },
        {
            "name": "佳明Forerunner 265",
            "category": "运动",
            "asset_type": "physical",
            "purchase_price": 3280,
            "current_value": 2800,
            "purchase_date": date(2023, 9, 15),
            "status": "in_use",
            "location": "随身",
            "expected_lifespan_days": 1825,  # 5 years
            "annual_maintenance_cost": 0,
            "usage_frequency": "daily",
            "notes": "GPS运动手表",
        },
        {
            "name": "乐高星战收藏套装",
            "category": "玩具",
            "asset_type": "physical",
            "purchase_price": 4999,
            "current_value": 6000,
            "purchase_date": date(2021, 5, 20),
            "status": "idle",
            "location": "客厅展示柜",
            "expected_lifespan_days": 36500,  # 收藏保值
            "annual_maintenance_cost": 0,
            "usage_frequency": "rarely",
            "notes": "UCS Millennium Falcon，限量版",
        },
        {
            "name": "雅马哈电钢琴",
            "category": "乐器",
            "asset_type": "physical",
            "purchase_price": 8500,
            "current_value": 7000,
            "purchase_date": date(2022, 1, 10),
            "status": "in_use",
            "location": "客厅",
            "expected_lifespan_days": 7300,  # 20 years
            "annual_maintenance_cost": 200,
            "usage_frequency": "weekly",
        },
        {
            "name": "金毛犬Lucky",
            "category": "宠物",
            "asset_type": "physical",
            "purchase_price": 3000,
            "current_value": 0,  # 宠物通常不计价值
            "purchase_date": date(2020, 6, 1),
            "status": "in_use",
            "location": "家中",
            "expected_lifespan_days": 3650,  # 10 years
            "annual_maintenance_cost": 8000,  # 食物+医疗
            "usage_frequency": "daily",
            "notes": "家庭成员，陪伴价值",
        },
        {
            "name": "Hermès丝巾",
            "category": "奢侈品",
            "asset_type": "physical",
            "purchase_price": 3800,
            "current_value": 4200,
            "purchase_date": date(2023, 4, 15),
            "status": "in_use",
            "location": "衣柜",
            "expected_lifespan_days": 18250,  # 50 years
            "annual_maintenance_cost": 100,
            "usage_frequency": "monthly",
            "notes": "经典橙色90cm款",
        },
    ]

    # Financial assets
    financial_assets = [
        {
            "name": "工商银行活期存款",
            "category": "存款",
            "asset_type": "financial",
            "purchase_price": 50000,
            "current_value": 52000,
            "purchase_date": date(2023, 1, 1),
            "status": "in_use",
            "institution": "工商银行",
            "interest_rate": 0.003,  # 0.3%活期
            "notes": "日常备用金",
        },
        {
            "name": "招商银行定期存款",
            "category": "存款",
            "asset_type": "financial",
            "purchase_price": 200000,
            "current_value": 206000,
            "purchase_date": date(2024, 1, 15),
            "status": "in_use",
            "institution": "招商银行",
            "interest_rate": 0.03,  # 3%三年定存
            "maturity_date": date(2027, 1, 15),
        },
        {
            "name": "沪深300ETF基金",
            "category": "基金",
            "asset_type": "financial",
            "purchase_price": 100000,
            "current_value": 115000,
            "purchase_date": date(2022, 7, 1),
            "status": "in_use",
            "institution": "华泰柏瑞",
            "notes": "指数基金，长期持有",
        },
        {
            "name": "易方达蓝筹精选",
            "category": "基金",
            "asset_type": "financial",
            "purchase_price": 50000,
            "current_value": 42000,
            "purchase_date": date(2023, 3, 10),
            "status": "in_use",
            "institution": "易方达",
            "notes": "主动基金，近期回撤",
        },
        {
            "name": "贵州茅台股票",
            "category": "股票",
            "asset_type": "financial",
            "purchase_price": 80000,  # 100股 @ 800
            "current_value": 150000,  # 100股 @ 1500
            "purchase_date": date(2019, 6, 1),
            "status": "in_use",
            "institution": "上交所",
            "notes": "100股，长期持有",
        },
        {
            "name": "腾讯控股股票",
            "category": "股票",
            "asset_type": "financial",
            "purchase_price": 60000,  # 200股 @ 300港币
            "current_value": 72000,  # 200股 @ 360港币
            "purchase_date": date(2022, 8, 15),
            "status": "in_use",
            "institution": "港交所",
            "notes": "200股，港股通",
        },
        {
            "name": "国债2024-03",
            "category": "债券",
            "asset_type": "financial",
            "purchase_price": 50000,
            "current_value": 51500,
            "purchase_date": date(2024, 3, 1),
            "status": "in_use",
            "institution": "财政部",
            "interest_rate": 0.028,
            "maturity_date": date(2027, 3, 1),
            "notes": "三年期国债",
        },
        {
            "name": "平安福重疾险",
            "category": "保险",
            "asset_type": "financial",
            "purchase_price": 180000,  # 已缴保费总额
            "current_value": 180000,
            "purchase_date": date(2018, 1, 1),
            "status": "in_use",
            "institution": "平安保险",
            "notes": "终身重疾险，保额50万",
        },
        {
            "name": "银行理财产品R2",
            "category": "理财产品",
            "asset_type": "financial",
            "purchase_price": 300000,
            "current_value": 309000,
            "purchase_date": date(2024, 4, 1),
            "status": "in_use",
            "institution": "招商银行",
            "interest_rate": 0.036,
            "maturity_date": date(2025, 4, 1),
            "notes": "低风险理财，一年期",
        },
        {
            "name": "比特币投资",
            "category": "数字货币",
            "asset_type": "financial",
            "purchase_price": 50000,
            "current_value": 85000,
            "purchase_date": date(2023, 1, 15),
            "status": "in_use",
            "institution": "Coinbase",
            "notes": "约0.5 BTC，波动较大",
        },
    ]

    all_assets_data = physical_assets + financial_assets
    created_assets = []

    for asset_data in all_assets_data:
        # Check if asset exists by name and user
        existing = db.query(Asset).filter_by(
            user_id=user.id,
            name=asset_data["name"]
        ).first()
        if existing:
            created_assets.append(existing)
            continue

        cat_name = asset_data["category"]
        category = cat_map.get(cat_name)
        if not category:
            print(f"WARNING: Category '{cat_name}' not found, skipping asset '{asset_data['name']}'")
            continue

        asset = Asset(
            id=next_id(),
            user_id=user.id,
            family_id=user.family_id,
            category_id=category.id,
            name=asset_data["name"],
            asset_type=asset_data["asset_type"],
            purchase_price=asset_data.get("purchase_price"),
            current_value=asset_data.get("current_value"),
            currency="CNY",
            purchase_date=asset_data.get("purchase_date"),
            status=asset_data.get("status", "in_use"),
            location=asset_data.get("location"),
            institution=asset_data.get("institution"),
            interest_rate=asset_data.get("interest_rate"),
            maturity_date=asset_data.get("maturity_date"),
            warranty_expiry_date=asset_data.get("warranty_expiry_date"),
            expected_lifespan_days=asset_data.get("expected_lifespan_days"),
            annual_maintenance_cost=asset_data.get("annual_maintenance_cost", 0),
            usage_frequency=asset_data.get("usage_frequency"),
            notes=asset_data.get("notes"),
        )

        # Add random tags (1-3 per asset)
        if tags:
            num_tags = random.randint(1, min(3, len(tags)))
            selected_tags = random.sample(tags, num_tags)
            asset.tags = selected_tags

        db.add(asset)
        created_assets.append(asset)

    db.commit()
    print(f"Created {len(created_assets)} assets for user {user.username}")
    return created_assets


def seed_liabilities(db, user: User, assets: list[Asset]):
    """Create liabilities for a user."""
    liabilities_data = [
        {
            "category": "mortgage",
            "name": "公寓房贷",
            "original_amount": 2100000,
            "remaining_amount": 1800000,
            "monthly_payment": 10500,
            "interest_rate": 0.049,
            "start_date": date(2020, 4, 1),
            "end_date": date(2050, 4, 1),
            "institution": "工商银行",
            "linked_asset_name": "北京朝阳区公寓",
            "notes": "30年期房贷，等额本息",
        },
        {
            "category": "car_loan",
            "name": "特斯拉车贷",
            "original_amount": 200000,
            "remaining_amount": 80000,
            "monthly_payment": 4167,
            "interest_rate": 0.03,
            "start_date": date(2022, 6, 1),
            "end_date": date(2026, 6, 1),
            "institution": "特斯拉金融",
            "linked_asset_name": "特斯拉Model 3",
            "notes": "4年期车贷",
        },
        {
            "category": "credit_card",
            "name": "招商信用卡欠款",
            "original_amount": 15000,
            "remaining_amount": 5000,
            "monthly_payment": 2500,
            "interest_rate": 0.18,  # 信用卡年化利率较高
            "start_date": date(2024, 3, 1),
            "institution": "招商银行",
            "notes": "上月消费分期",
        },
        {
            "category": "personal_loan",
            "name": "装修贷款",
            "original_amount": 50000,
            "remaining_amount": 30000,
            "monthly_payment": 2083,
            "interest_rate": 0.06,
            "start_date": date(2023, 10, 1),
            "end_date": date(2025, 10, 1),
            "institution": "建设银行",
            "notes": "2年期装修分期",
        },
    ]

    # Build asset name map for linking
    asset_map = {a.name: a for a in assets}

    created_liabilities = []
    for liab_data in liabilities_data:
        existing = db.query(Liability).filter_by(
            user_id=user.id,
            name=liab_data["name"]
        ).first()
        if existing:
            created_liabilities.append(existing)
            continue

        linked_asset = None
        if liab_data.get("linked_asset_name"):
            linked_asset = asset_map.get(liab_data["linked_asset_name"])

        liability = Liability(
            id=next_id(),
            user_id=user.id,
            family_id=user.family_id,
            category=liab_data["category"],
            name=liab_data["name"],
            original_amount=liab_data["original_amount"],
            remaining_amount=liab_data["remaining_amount"],
            monthly_payment=liab_data.get("monthly_payment"),
            interest_rate=liab_data.get("interest_rate"),
            start_date=liab_data.get("start_date"),
            end_date=liab_data.get("end_date"),
            institution=liab_data.get("institution"),
            linked_asset_id=linked_asset.id if linked_asset else None,
            notes=liab_data.get("notes"),
            is_active=True,
            currency="CNY",
        )
        db.add(liability)
        created_liabilities.append(liability)

    db.commit()
    print(f"Created {len(created_liabilities)} liabilities for user {user.username}")
    return created_liabilities


def seed_wishes(db, user: User):
    """Create wishes for a user."""
    wishes_data = [
        {
            "name": "Switch 2游戏机",
            "expected_price": 3000,
            "description": "任天堂下一代主机",
            "priority": "high",
            "status": "pending",
        },
        {
            "name": "日本东京旅行",
            "expected_price": 20000,
            "description": "一周东京深度游",
            "priority": "medium",
            "status": "pending",
        },
        {
            "name": "索尼PS5",
            "expected_price": 4500,
            "description": "PS5游戏主机",
            "priority": "low",
            "status": "realized",
        },
        {
            "name": "戴森吹风机",
            "expected_price": 3200,
            "description": "Supersonic款",
            "priority": "medium",
            "status": "pending",
        },
        {
            "name": "Apple Watch Ultra",
            "expected_price": 6299,
            "description": "户外运动手表",
            "priority": "medium",
            "status": "pending",
        },
        {
            "name": "家庭影院系统",
            "expected_price": 50000,
            "description": "投影仪+音响+幕布",
            "priority": "low",
            "status": "pending",
        },
    ]

    created_wishes = []
    for wish_data in wishes_data:
        existing = db.query(Wish).filter_by(
            user_id=user.id,
            name=wish_data["name"]
        ).first()
        if existing:
            created_wishes.append(existing)
            continue

        wish = Wish(
            id=next_id(),
            user_id=user.id,
            family_id=user.family_id,
            name=wish_data["name"],
            expected_price=wish_data["expected_price"],
            description=wish_data.get("description"),
            priority=wish_data.get("priority", "medium"),
            status=wish_data.get("status", "pending"),
            converts_to_asset=True,
        )
        db.add(wish)
        created_wishes.append(wish)

    db.commit()
    print(f"Created {len(created_wishes)} wishes for user {user.username}")
    return created_wishes


def seed_ai_config(db, user: User):
    """Create AI provider config for test family."""
    import os
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        print("WARNING: ANTHROPIC_API_KEY not set, skipping AI config")
        return None

    existing_config = db.query(AIProviderConfig).filter_by(family_id=user.family_id).first()
    if existing_config:
        print(f"AI config already exists for family {user.family_id}: provider={existing_config.provider}, model={existing_config.model_id}")
        return existing_config

    encrypted_key = encrypt_api_key(api_key)
    config = AIProviderConfig(
        id=next_id(),
        family_id=user.family_id,
        name="Claude Sonnet 4.6",
        provider="anthropic",
        api_key_encrypted=encrypted_key,
        model_id="claude-sonnet-4-6",
        vision_model_id="claude-sonnet-4-6",
        timeout_seconds=120,
        is_active=True,
    )
    db.add(config)
    db.commit()

    print(f"Created AI config for family {user.family_id}: provider={config.provider}, model={config.model_id}")
    return config


def main():
    """Run full seeding."""
    print("=" * 60)
    print("Seeding full test data...")
    print("=" * 60)

    db = SessionLocal()
    try:
        # Step 1: Create users and families
        print("\n[1] Creating test users and families...")
        seed_test_users(db)

        # Find demouser
        demouser = db.query(User).filter_by(username="demouser").first()
        if not demouser:
            print("ERROR: demouser not found after seeding")
            return

        # Step 2: Create tags
        print("\n[2] Creating tags...")
        tags = seed_tags(db, demouser)

        # Step 3: Create assets
        print("\n[3] Creating assets...")
        assets = seed_assets(db, demouser, tags)

        # Step 4: Create liabilities
        print("\n[4] Creating liabilities...")
        liabilities = seed_liabilities(db, demouser, assets)

        # Step 5: Create wishes
        print("\n[5] Creating wishes...")
        wishes = seed_wishes(db, demouser)

        # Step 6: Create AI config
        print("\n[6] Creating AI config...")
        seed_ai_config(db, demouser)

        print("\n" + "=" * 60)
        print("Seeding complete!")
        print("=" * 60)
        print("\nTest account credentials:")
        print("  Username: demouser")
        print("  Password: DemoPass123")
        print("\nData summary:")
        print(f"  Assets: {len(assets)}")
        print(f"  Liabilities: {len(liabilities)}")
        print(f"  Tags: {len(tags)}")
        print(f"  Wishes: {len(wishes)}")

    finally:
        db.close()


if __name__ == "__main__":
    main()