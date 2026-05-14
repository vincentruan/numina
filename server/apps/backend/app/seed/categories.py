"""Seed system categories from YAML config + hardcoded identity list."""
from pathlib import Path

import yaml

from apps.backend.app.core.logging_config import get_logger

logger = get_logger(__name__)

_CONFIG_FILE = Path(__file__).parent.parent / "config" / "categories.yaml"

# Stable identity: (name, asset_type). Never rename or reorder — these are the
# source of truth for what categories exist. Presentation attrs live in categories.yaml.
_CATEGORY_IDENTITIES: list[tuple[str, str]] = [
    # Physical assets
    ("房产", "physical"),
    ("车辆", "physical"),
    ("数码", "physical"),
    ("家电", "physical"),
    ("家具", "physical"),
    ("珠宝", "physical"),
    ("服饰", "physical"),
    ("美妆", "physical"),
    ("运动", "physical"),
    ("玩具", "physical"),
    ("宠物", "physical"),
    ("乐器", "physical"),
    ("箱包", "physical"),
    ("奢侈品", "physical"),
    ("其他", "physical"),
    # Financial assets
    ("存款", "financial"),
    ("基金", "financial"),
    ("股票", "financial"),
    ("债券", "financial"),
    ("保险", "financial"),
    ("理财产品", "financial"),
    ("数字货币", "financial"),
    ("其他金融", "financial"),
]

# Fallback presentation attrs used when categories.yaml is absent or unreadable.
_FALLBACK_PRESENTATION: dict[str, dict] = {
    "房产":     {"icon": "icon-home",          "color": "#EF4444", "sort_order": 1},
    "车辆":     {"icon": "icon-car",           "color": "#F97316", "sort_order": 2},
    "数码":     {"icon": "icon-digital",       "color": "#3B82F6", "sort_order": 3},
    "家电":     {"icon": "icon-appliance",     "color": "#8B5CF6", "sort_order": 4},
    "家具":     {"icon": "icon-furniture",     "color": "#A855F7", "sort_order": 5},
    "珠宝":     {"icon": "icon-jewelry",       "color": "#EC4899", "sort_order": 6},
    "服饰":     {"icon": "icon-clothing",      "color": "#14B8A6", "sort_order": 7},
    "美妆":     {"icon": "icon-beauty",        "color": "#F43F5E", "sort_order": 8},
    "运动":     {"icon": "icon-sports",        "color": "#22C55E", "sort_order": 9},
    "玩具":     {"icon": "icon-toys",          "color": "#6366F1", "sort_order": 10},
    "宠物":     {"icon": "icon-pets",          "color": "#D97706", "sort_order": 11},
    "乐器":     {"icon": "icon-music",         "color": "#7C3AED", "sort_order": 12},
    "箱包":     {"icon": "icon-bags",          "color": "#BE185D", "sort_order": 13},
    "奢侈品":   {"icon": "icon-luxury",        "color": "#B45309", "sort_order": 14},
    "其他":     {"icon": "icon-other",         "color": "#64748B", "sort_order": 15},
    "存款":     {"icon": "icon-deposit",       "color": "#0EA5E9", "sort_order": 16},
    "基金":     {"icon": "icon-fund",          "color": "#10B981", "sort_order": 17},
    "股票":     {"icon": "icon-stock",         "color": "#EF4444", "sort_order": 18},
    "债券":     {"icon": "icon-bond",          "color": "#F59E0B", "sort_order": 19},
    "保险":     {"icon": "icon-insurance",     "color": "#6366F1", "sort_order": 20},
    "理财产品": {"icon": "icon-wealth",        "color": "#8B5CF6", "sort_order": 21},
    "数字货币": {"icon": "icon-crypto",        "color": "#F97316", "sort_order": 22},
    "其他金融": {"icon": "icon-other-finance", "color": "#64748B", "sort_order": 23},
}


def _load_presentation() -> dict[str, dict]:
    """Load presentation attrs from YAML; fall back to hardcoded defaults."""
    if not _CONFIG_FILE.exists():
        logger.info("categories.yaml 不存在，使用内置默认值")
        return _FALLBACK_PRESENTATION
    try:
        with open(_CONFIG_FILE, encoding="utf-8") as f:
            data = yaml.safe_load(f)
        if not isinstance(data, dict):
            raise ValueError("顶层结构必须是映射")
        return data
    except Exception as e:
        logger.warning(f"categories.yaml 解析失败: {e}，使用内置默认值")
        return _FALLBACK_PRESENTATION


def _build_system_categories() -> list[dict]:
    presentation = _load_presentation()
    result = []
    for name, asset_type in _CATEGORY_IDENTITIES:
        p = presentation.get(name, _FALLBACK_PRESENTATION.get(name, {}))
        result.append({
            "name": name,
            "asset_type": asset_type,
            "icon": p.get("icon", "icon-other"),
            "color": p.get("color", "#64748B"),
            "sort_order": p.get("sort_order", 99),
        })
    return result


SYSTEM_CATEGORIES: list[dict] = _build_system_categories()


def seed_categories(db) -> None:
    from apps.backend.app.models.category import Category

    existing = db.query(Category).filter(Category.is_system == True).first()  # noqa: E712
    if existing:
        # Migrate any system categories still using emoji icons to sprite IDs
        icon_map = {cat["name"]: cat["icon"] for cat in SYSTEM_CATEGORIES}
        rows = db.query(Category).filter(
            Category.is_system == True,  # noqa: E712
            ~Category.icon.like("icon-%"),
        ).all()
        for cat in rows:
            if cat.name in icon_map:
                cat.icon = icon_map[cat.name]
        if rows:
            db.commit()
        return

    for cat_data in SYSTEM_CATEGORIES:
        cat = Category(
            family_id=None,
            is_system=True,
            **cat_data,
        )
        db.add(cat)
    db.commit()
