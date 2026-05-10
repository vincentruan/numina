"""CLI: seed system categories into the database.

Usage:
    uv run python scripts/seed_categories.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from app.database import SessionLocal
from app.seed.categories import seed_categories

if __name__ == "__main__":
    db = SessionLocal()
    try:
        seed_categories(db)
        print("系统分类初始化完成")
    finally:
        db.close()
