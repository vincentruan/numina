SYSTEM_CATEGORIES = [
    # Physical assets
    {"name": "房产", "icon": "🏠", "color": "#EF4444", "asset_type": "physical", "sort_order": 1},
    {"name": "车辆", "icon": "🚗", "color": "#F97316", "asset_type": "physical", "sort_order": 2},
    {"name": "数码", "icon": "📱", "color": "#3B82F6", "asset_type": "physical", "sort_order": 3},
    {"name": "家电", "icon": "📺", "color": "#8B5CF6", "asset_type": "physical", "sort_order": 4},
    {"name": "家具", "icon": "🛋️", "color": "#A855F7", "asset_type": "physical", "sort_order": 5},
    {"name": "珠宝", "icon": "💎", "color": "#EC4899", "asset_type": "physical", "sort_order": 6},
    {"name": "服饰", "icon": "👔", "color": "#14B8A6", "asset_type": "physical", "sort_order": 7},
    {"name": "美妆", "icon": "💄", "color": "#F43F5E", "asset_type": "physical", "sort_order": 8},
    {"name": "运动", "icon": "⚽", "color": "#22C55E", "asset_type": "physical", "sort_order": 9},
    {"name": "玩具", "icon": "🎮", "color": "#6366F1", "asset_type": "physical", "sort_order": 10},
    {"name": "宠物", "icon": "🐾", "color": "#D97706", "asset_type": "physical", "sort_order": 11},
    {"name": "乐器", "icon": "🎸", "color": "#7C3AED", "asset_type": "physical", "sort_order": 12},
    {"name": "箱包", "icon": "👜", "color": "#BE185D", "asset_type": "physical", "sort_order": 13},
    # Financial assets
    {"name": "存款", "icon": "🏦", "color": "#0EA5E9", "asset_type": "financial", "sort_order": 14},
    {"name": "基金", "icon": "📊", "color": "#10B981", "asset_type": "financial", "sort_order": 15},
    {"name": "股票", "icon": "📈", "color": "#EF4444", "asset_type": "financial", "sort_order": 16},
    {"name": "债券", "icon": "📜", "color": "#F59E0B", "asset_type": "financial", "sort_order": 17},
    {"name": "保险", "icon": "🛡️", "color": "#6366F1", "asset_type": "financial", "sort_order": 18},
    {"name": "理财产品", "icon": "💰", "color": "#8B5CF6", "asset_type": "financial", "sort_order": 19},
    {"name": "数字货币", "icon": "₿", "color": "#F97316", "asset_type": "financial", "sort_order": 20},
    {"name": "其他金融", "icon": "💳", "color": "#64748B", "asset_type": "financial", "sort_order": 21},
]


def seed_categories(db):
    from app.models.category import Category

    existing = db.query(Category).filter(Category.is_system == True).first()
    if existing:
        return

    for cat_data in SYSTEM_CATEGORIES:
        cat = Category(
            family_id=None,
            is_system=True,
            **cat_data,
        )
        db.add(cat)
    db.commit()
