"""Child learning stats service — XP, level, streak management."""

from datetime import date, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from packages.core.logging import get_logger
from packages.db.models.learning.stats import ChildLearningStats

logger = get_logger(__name__)

# Level thresholds: (level, cumulative_xp_required)
LEVEL_THRESHOLDS = [
    (1, 0),       # 种子 Seed
    (2, 100),     # 幼苗 Sprout
    (3, 300),     # 花蕾 Bud
    (4, 600),     # 花朵 Flower
    (5, 1000),    # 果实 Fruit
    (6, 2000),    # 大树 Tree
    (7, 5000),    # 大师 Master
]

LEVEL_NAMES_ZH = {
    1: "种子",
    2: "幼苗",
    3: "花蕾",
    4: "花朵",
    5: "果实",
    6: "大树",
    7: "大师",
}

LEVEL_NAMES_EN = {
    1: "Seed",
    2: "Sprout",
    3: "Bud",
    4: "Flower",
    5: "Fruit",
    6: "Tree",
    7: "Master",
}

LEVEL_EMOJIS = {
    1: "🌱",
    2: "🌿",
    3: "🌷",
    4: "🌸",
    5: "🍎",
    6: "🌳",
    7: "🏆",
}

# Daily XP cap to prevent reward farming (per Section 6.3)
DAILY_XP_CAP = 100


def get_level_info(level: int) -> dict:
    """Get level name, emoji, and next threshold."""
    level = min(level, max(lv for lv, _ in LEVEL_THRESHOLDS))
    name_zh = LEVEL_NAMES_ZH.get(level, "未知")
    name_en = LEVEL_NAMES_EN.get(level, "Unknown")
    emoji = LEVEL_EMOJIS.get(level, "⭐")

    next_threshold = None
    next_level_name_zh = None
    next_level_name_en = None
    for lv, xp in LEVEL_THRESHOLDS:
        if lv == level + 1:
            next_threshold = xp
            next_level_name_zh = LEVEL_NAMES_ZH.get(lv)
            next_level_name_en = LEVEL_NAMES_EN.get(lv)
            break

    return {
        "level": level,
        "name_zh": name_zh,
        "name_en": name_en,
        "emoji": emoji,
        "next_threshold": next_threshold,
        "next_level_name_zh": next_level_name_zh,
        "next_level_name_en": next_level_name_en,
    }


def _compute_level(cumulative_xp: int) -> int:
    """Compute level from cumulative XP."""
    current_level = 1
    for lv, threshold in LEVEL_THRESHOLDS:
        if cumulative_xp >= threshold:
            current_level = lv
        else:
            break
    return current_level


def get_or_create_stats(db: Session, child_id: int, family_id: int) -> ChildLearningStats:
    """Get existing stats or create with defaults."""
    result = db.execute(
        select(ChildLearningStats).where(ChildLearningStats.child_id == child_id)
    )
    stats = result.scalar_one_or_none()
    if stats:
        return stats

    stats = ChildLearningStats(child_id=child_id, family_id=family_id)
    db.add(stats)
    db.flush()
    return stats


def _reset_xp_today_if_new_day(stats: ChildLearningStats) -> None:
    """Reset xp_today counter if the last XP date is not today."""
    today = date.today()
    if stats.last_xp_date != today:
        stats.xp_today = 0
        stats.last_xp_date = today


def award_xp(
    db: Session,
    child_id: int,
    family_id: int,
    xp_amount: int,
) -> dict:
    """Award XP to a child, check level-up, and update streak.

    Returns dict with xp_awarded (actual, after daily cap), leveled_up, new_level.
    Uses SELECT FOR UPDATE for race safety on the stats row.
    """
    # Atomic get-or-create with lock to prevent race conditions
    result = db.execute(
        select(ChildLearningStats)
        .where(ChildLearningStats.child_id == child_id)
        .with_for_update()
    )
    stats = result.scalar_one_or_none()

    if stats is None:
        # Create new stats record (no lock needed yet since we're creating)
        stats = ChildLearningStats(child_id=child_id, family_id=family_id)
        db.add(stats)
        db.flush()
        # Re-fetch with lock now that it exists
        result = db.execute(
            select(ChildLearningStats)
            .where(ChildLearningStats.child_id == child_id)
            .with_for_update()
        )
        stats = result.scalar_one()

    # Reset daily counter if new day
    _reset_xp_today_if_new_day(stats)

    # Daily XP cap
    remaining_cap = max(0, DAILY_XP_CAP - stats.xp_today)
    actual_xp = min(xp_amount, remaining_cap)

    if actual_xp <= 0:
        return {
            "xp_awarded": 0,
            "leveled_up": False,
            "new_level": stats.level,
            "daily_cap_reached": True,
        }

    old_level = stats.level
    stats.cumulative_xp += actual_xp
    stats.xp_today += actual_xp
    stats.level = _compute_level(stats.cumulative_xp)

    # Update streak
    _update_streak_internal(stats)

    db.flush()

    leveled_up = stats.level > old_level
    return {
        "xp_awarded": actual_xp,
        "leveled_up": leveled_up,
        "new_level": stats.level,
        "daily_cap_reached": actual_xp < xp_amount,
    }


def _update_streak_internal(stats: ChildLearningStats) -> None:
    """Update streak based on last_learning_date. Called within locked context."""
    today = date.today()
    if stats.last_learning_date is None:
        stats.learning_streak_days = 1
        stats.last_learning_date = today
        return

    last = stats.last_learning_date
    if isinstance(last, datetime):
        last = last.date()

    if last == today:
        return  # Already counted today
    elif (today - last).days == 1:
        stats.learning_streak_days += 1
        stats.last_learning_date = today
    elif (today - last).days > 1:
        # More than 1 day gap — reset streak
        stats.learning_streak_days = 1
        stats.last_learning_date = today


def update_streak(db: Session, child_id: int, family_id: int) -> int:
    """Update streak for a child. Returns current streak days."""
    stats = get_or_create_stats(db, child_id, family_id)

    result = db.execute(
        select(ChildLearningStats)
        .where(ChildLearningStats.child_id == child_id)
        .with_for_update()
    )
    stats = result.scalar_one()
    _update_streak_internal(stats)
    db.flush()
    return stats.learning_streak_days
