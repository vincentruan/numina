"""System categories as compile-time constants.

21 system categories (13 physical + 8 financial) seeded on app startup.
These never change at runtime, so using constants eliminates DB queries.
"""

from typing import NamedTuple


class SystemCategory(NamedTuple):
    id: str
    name: str
    icon: str
    color: str
    asset_type: str
    sort_order: int
    is_system: bool


SYSTEM_CATEGORIES: list[SystemCategory] = [
    # Physical assets (13)
    SystemCategory(
        id="sys-cat-001",
        name="房产",
        icon="icon-home",
        color="#EF4444",
        asset_type="physical",
        sort_order=1,
        is_system=True,
    ),
    SystemCategory(
        id="sys-cat-002",
        name="车辆",
        icon="icon-car",
        color="#F97316",
        asset_type="physical",
        sort_order=2,
        is_system=True,
    ),
    SystemCategory(
        id="sys-cat-003",
        name="数码",
        icon="icon-digital",
        color="#3B82F6",
        asset_type="physical",
        sort_order=3,
        is_system=True,
    ),
    SystemCategory(
        id="sys-cat-004",
        name="家电",
        icon="icon-appliance",
        color="#8B5CF6",
        asset_type="physical",
        sort_order=4,
        is_system=True,
    ),
    SystemCategory(
        id="sys-cat-005",
        name="家具",
        icon="icon-furniture",
        color="#A855F7",
        asset_type="physical",
        sort_order=5,
        is_system=True,
    ),
    SystemCategory(
        id="sys-cat-006",
        name="珠宝",
        icon="icon-jewelry",
        color="#EC4899",
        asset_type="physical",
        sort_order=6,
        is_system=True,
    ),
    SystemCategory(
        id="sys-cat-007",
        name="服饰",
        icon="icon-clothing",
        color="#14B8A6",
        asset_type="physical",
        sort_order=7,
        is_system=True,
    ),
    SystemCategory(
        id="sys-cat-008",
        name="美妆",
        icon="icon-beauty",
        color="#F43F5E",
        asset_type="physical",
        sort_order=8,
        is_system=True,
    ),
    SystemCategory(
        id="sys-cat-009",
        name="运动",
        icon="icon-sports",
        color="#22C55E",
        asset_type="physical",
        sort_order=9,
        is_system=True,
    ),
    SystemCategory(
        id="sys-cat-010",
        name="玩具",
        icon="icon-toys",
        color="#6366F1",
        asset_type="physical",
        sort_order=10,
        is_system=True,
    ),
    SystemCategory(
        id="sys-cat-011",
        name="宠物",
        icon="icon-pets",
        color="#D97706",
        asset_type="physical",
        sort_order=11,
        is_system=True,
    ),
    SystemCategory(
        id="sys-cat-012",
        name="乐器",
        icon="icon-music",
        color="#7C3AED",
        asset_type="physical",
        sort_order=12,
        is_system=True,
    ),
    SystemCategory(
        id="sys-cat-013",
        name="箱包",
        icon="icon-bags",
        color="#BE185D",
        asset_type="physical",
        sort_order=13,
        is_system=True,
    ),
    # Financial assets (8)
    SystemCategory(
        id="sys-cat-014",
        name="存款",
        icon="icon-deposit",
        color="#0EA5E9",
        asset_type="financial",
        sort_order=14,
        is_system=True,
    ),
    SystemCategory(
        id="sys-cat-015",
        name="基金",
        icon="icon-fund",
        color="#10B981",
        asset_type="financial",
        sort_order=15,
        is_system=True,
    ),
    SystemCategory(
        id="sys-cat-016",
        name="股票",
        icon="icon-stock",
        color="#EF4444",
        asset_type="financial",
        sort_order=16,
        is_system=True,
    ),
    SystemCategory(
        id="sys-cat-017",
        name="债券",
        icon="icon-bond",
        color="#F59E0B",
        asset_type="financial",
        sort_order=17,
        is_system=True,
    ),
    SystemCategory(
        id="sys-cat-018",
        name="保险",
        icon="icon-insurance",
        color="#6366F1",
        asset_type="financial",
        sort_order=18,
        is_system=True,
    ),
    SystemCategory(
        id="sys-cat-019",
        name="理财产品",
        icon="icon-wealth",
        color="#8B5CF6",
        asset_type="financial",
        sort_order=19,
        is_system=True,
    ),
    SystemCategory(
        id="sys-cat-020",
        name="数字货币",
        icon="icon-crypto",
        color="#F97316",
        asset_type="financial",
        sort_order=20,
        is_system=True,
    ),
    SystemCategory(
        id="sys-cat-021",
        name="其他金融",
        icon="icon-other-finance",
        color="#64748B",
        asset_type="financial",
        sort_order=21,
        is_system=True,
    ),
]


def get_system_categories_by_type(asset_type: str) -> list[SystemCategory]:
    """Filter system categories by asset type.

    Args:
        asset_type: 'physical' or 'financial'

    Returns:
        List of system categories matching the type
    """
    return [cat for cat in SYSTEM_CATEGORIES if cat.asset_type == asset_type]


def get_system_category_by_id(id: str) -> SystemCategory | None:
    """Get a system category by its ID.

    Args:
        id: Category ID (e.g., 'sys-cat-001')

    Returns:
        SystemCategory or None if not found
    """
    for cat in SYSTEM_CATEGORIES:
        if cat.id == id:
            return cat
    return None


def get_system_category_by_name(name: str) -> SystemCategory | None:
    """Get a system category by its name.

    Args:
        name: Category name (e.g., '房产')

    Returns:
        SystemCategory or None if not found
    """
    for cat in SYSTEM_CATEGORIES:
        if cat.name == name:
            return cat
    return None