"""Seed literacy badge definitions for the Learning OS gamification system.

Creates 27 badge definitions: 8 subjects x 3 levels + 1 comprehensive x 3 levels.

Thresholds by subject size:
  Large (>200 topics):  mathematics (503), science (547), english (286) -> 10/30/60
  Medium (50-200):      history (90), personal_social (88) -> 5/15/30
  Small (<50):          life_skills (37), computing (21), learning_to_learn (18) -> 3/8/15
  Comprehensive:        20/50/100

Usage:
    cd server
    uv run python scripts/seed_learning_badges.py
"""

from packages.db.models.literacy_badge import LiteracyBadgeDefinition

# 27 badge definitions: (dimension, level, name, description, criteria_summary)
BADGE_DEFINITIONS = [
    # === Large subjects: thresholds 10/30/60 ===
    # Mathematics (503 topics)
    ("mathematics", 1, "小数学家", "开始探索数学世界", "掌握 10 个数学 topic"),
    ("mathematics", 2, "数学达人", "数学能力稳步提升", "掌握 30 个数学 topic"),
    ("mathematics", 3, "数学大师", "数学领域的佼佼者", "掌握 60 个数学 topic"),

    # Science (547 topics)
    ("science", 1, "小科学家", "开始探索科学世界", "掌握 10 个科学 topic"),
    ("science", 2, "科学达人", "科学能力稳步提升", "掌握 30 个科学 topic"),
    ("science", 3, "科学大师", "科学领域的佼佼者", "掌握 60 个科学 topic"),

    # English (286 topics)
    ("english", 1, "小文学家", "开始探索英语世界", "掌握 10 个英语 topic"),
    ("english", 2, "英语达人", "英语能力稳步提升", "掌握 25 个英语 topic"),
    ("english", 3, "英语大师", "英语领域的佼佼者", "掌握 50 个英语 topic"),

    # === Medium subjects: thresholds 5/15/30 ===
    # History (90 topics)
    ("history", 1, "小历史学家", "开始探索历史世界", "掌握 5 个历史 topic"),
    ("history", 2, "历史达人", "历史知识稳步积累", "掌握 15 个历史 topic"),
    ("history", 3, "历史大师", "历史领域的佼佼者", "掌握 30 个历史 topic"),

    # Personal & Social Development (88 topics)
    ("personal_social", 1, "社交小达人", "开始学习社交技能", "掌握 5 个社交 topic"),
    ("personal_social", 2, "社交达人", "社交能力稳步提升", "掌握 15 个社交 topic"),
    ("personal_social", 3, "社交大师", "社交领域的佼佼者", "掌握 30 个社交 topic"),

    # === Small subjects: thresholds 3/8/15 ===
    # Life Skills (37 topics)
    ("life_skills", 1, "生活小能手", "开始学习生活技能", "掌握 3 个生活技能 topic"),
    ("life_skills", 2, "生活达人", "生活能力稳步提升", "掌握 8 个生活技能 topic"),
    ("life_skills", 3, "生活大师", "生活技能的佼佼者", "掌握 15 个生活技能 topic"),

    # Computing (21 topics)
    ("computing", 1, "小编程师", "开始探索编程世界", "掌握 3 个计算 topic"),
    ("computing", 2, "编程达人", "编程能力稳步提升", "掌握 8 个计算 topic"),
    ("computing", 3, "编程大师", "编程领域的佼佼者", "掌握 15 个计算 topic"),

    # Learning to Learn (18 topics)
    ("learning_to_learn", 1, "学习新手", "开始掌握学习方法", "掌握 3 个学习方法 topic"),
    ("learning_to_learn", 2, "学习达人", "学习能力稳步提升", "掌握 8 个学习方法 topic"),
    ("learning_to_learn", 3, "学习大师", "学习方法的佼佼者", "掌握 15 个学习方法 topic"),

    # === Comprehensive: thresholds 20/50/100 ===
    ("comprehensive", 1, "学习新星", "学习之旅刚刚起步", "总掌握 20 个 topic"),
    ("comprehensive", 2, "学习之星", "学习能力全面提升", "总掌握 50 个 topic"),
    ("comprehensive", 3, "学习之王", "知识领域的全面王者", "总掌握 100 个 topic"),
]


def seed_badges(session) -> int:
    """Insert all badge definitions. Idempotent via (dimension, level) unique constraint."""
    created = 0
    for dimension, level, name, description, criteria_summary in BADGE_DEFINITIONS:
        existing = (
            session.query(LiteracyBadgeDefinition)
            .filter_by(dimension=dimension, level=level)
            .first()
        )
        if existing:
            # Update in case definitions changed
            existing.name = name
            existing.description = description
            existing.criteria_summary = criteria_summary
        else:
            badge = LiteracyBadgeDefinition(
                dimension=dimension,
                level=level,
                name=name,
                description=description,
                criteria_summary=criteria_summary,
            )
            session.add(badge)
            created += 1

    session.flush()
    print(f"  Badge definitions: {created} created, {len(BADGE_DEFINITIONS) - created} updated")
    return len(BADGE_DEFINITIONS)


def main():
    from apps.backend.app.database import SessionLocal

    session = SessionLocal()
    try:
        print("Seeding literacy badge definitions...")
        total = seed_badges(session)
        session.commit()
        print(f"Done! {total} badge definitions seeded.")
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


if __name__ == "__main__":
    main()
