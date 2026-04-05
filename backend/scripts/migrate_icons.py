#!/usr/bin/env python3
"""
One-time migration script to convert emoji icons to SVG icon IDs for system categories.

This script updates the `icon` field in the `categories` table from emoji characters
to icon IDs (e.g., "🏠" → "icon-home") for all system categories (is_system=True).

Custom user categories are preserved and not modified.

Run with: PYTHONPATH=. python scripts/migrate_icons.py
"""

import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from app.config import settings
from app.database import Base

# Emoji-to-IconID mapping for all 21 system categories
EMOJI_TO_ICON_ID = {
    # Physical assets
    "🏠": "icon-home",        # 房产
    "🚗": "icon-car",         # 车辆
    "📱": "icon-digital",     # 数码
    "📺": "icon-appliance",   # 家电
    "🛋️": "icon-furniture",   # 家具
    "💎": "icon-jewelry",     # 珠宝
    "👔": "icon-clothing",    # 服饰
    "💄": "icon-beauty",      # 美妆
    "⚽": "icon-sports",       # 运动
    "🎮": "icon-toys",        # 玩具
    "🐾": "icon-pets",        # 宠物
    "🎸": "icon-music",       # 乐器
    "👜": "icon-bags",        # 箱包
    # Financial assets
    "🏦": "icon-deposit",         # 存款
    "📊": "icon-fund",            # 基金
    "📈": "icon-stock",           # 股票
    "📜": "icon-bond",            # 债券
    "🛡️": "icon-insurance",       # 保险
    "💰": "icon-wealth",          # 理财产品
    "₿": "icon-crypto",           # 数字货币
    "💳": "icon-other-finance",   # 其他金融
}


def migrate_icons():
    """Migrate emoji icons to SVG icon IDs for system categories."""
    engine = create_engine(settings.DATABASE_URL)
    Session = sessionmaker(bind=engine)
    session = Session()

    try:
        # Get all system categories
        result = session.execute(
            text("SELECT id, name, icon FROM categories WHERE is_system = :is_system"),
            {"is_system": True}
        )
        system_categories = result.fetchall()

        if not system_categories:
            print("No system categories found. Nothing to migrate.")
            return

        print(f"Found {len(system_categories)} system categories to check.")

        updated_count = 0
        for cat_id, name, icon in system_categories:
            # Check if icon is an emoji that needs migration
            if icon in EMOJI_TO_ICON_ID:
                new_icon = EMOJI_TO_ICON_ID[icon]
                session.execute(
                    text("UPDATE categories SET icon = :new_icon WHERE id = :id"),
                    {"new_icon": new_icon, "id": cat_id}
                )
                print(f"  Updated '{name}': {icon} → {new_icon}")
                updated_count += 1
            elif icon.startswith("icon-"):
                print(f"  Skipped '{name}': already using icon ID ({icon})")
            else:
                print(f"  Warning: '{name}' has unrecognized icon: {icon}")

        session.commit()
        print(f"\nMigration complete. Updated {updated_count} categories.")

    except Exception as e:
        session.rollback()
        print(f"Migration failed: {e}")
        raise
    finally:
        session.close()


if __name__ == "__main__":
    print("Starting icon migration...")
    print(f"Database: {settings.DATABASE_URL}")
    print()
    migrate_icons()