"""Seed preset learning paths from topics with curriculum standards.

Generates PresetLearningPath records grouped by (grade, subject, semester).
Clears existing presets before regeneration.

Usage:
    cd server
    uv run python scripts/seed_preset_paths.py
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


def main():
    from apps.backend.app.database import SessionLocal
    from apps.backend.app.services.learning.preset_path_service import (
        generate_preset_paths,
    )

    session = SessionLocal()
    try:
        print("Generating preset learning paths...")
        paths = generate_preset_paths(session)
        print(f"Done! {len(paths)} preset learning paths generated.")
        for p in paths:
            print(f"  - [{p.grade}年级 {p.semester}] {p.name} ({p.topic_count} topics)")
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


if __name__ == "__main__":
    main()
