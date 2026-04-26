"""种子数据：每个系统分类的默认财务参数。"""

# category_name -> (annual_depreciation, annual_return, lifespan_years)
DEFAULTS: dict[str, tuple[float, float, int | None]] = {
    "房产": (0.02, 0.03, 50),
    "车辆": (0.15, 0.0, 10),
    "数码": (0.25, 0.0, 4),
    "家电": (0.10, 0.0, 10),
    "家具": (0.08, 0.0, 15),
    "珠宝": (0.01, 0.02, 50),
    "服饰": (0.30, 0.0, 3),
    "美妆": (0.50, 0.0, 2),
    "运动": (0.15, 0.0, 8),
    "玩具": (0.20, 0.0, 5),
    "宠物": (0.20, 0.0, 5),
    "乐器": (0.05, 0.0, 20),
    "箱包": (0.15, 0.0, 8),
    "存款": (0.0, 0.02, None),
    "基金": (0.0, 0.06, None),
    "股票": (0.0, 0.08, None),
    "债券": (0.0, 0.04, None),
    "保险": (0.0, 0.03, None),
    "理财产品": (0.0, 0.035, None),
    "数字货币": (0.0, 0.10, None),
    "其他金融": (0.0, 0.03, None),
}


def seed_category_financial_defaults(db):
    from app.models.category import Category
    from app.models.category_financial_default import CategoryFinancialDefault

    existing = db.query(CategoryFinancialDefault).first()
    if existing:
        return

    categories = db.query(Category).filter(Category.is_system.is_(True)).all()
    name_to_id = {c.name: c.id for c in categories}

    for name, (depreciation, annual_return, lifespan) in DEFAULTS.items():
        cat_id = name_to_id.get(name)
        if cat_id is None:
            continue
        db.add(
            CategoryFinancialDefault(
                category_id=cat_id,
                default_annual_depreciation=depreciation,
                default_annual_return=annual_return,
                default_lifespan_years=lifespan,
            )
        )
    db.commit()
