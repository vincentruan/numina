"""Coverage 5D service — weighted quality model for topic coverage.

Replaces the binary existence check (P7a-min) with a 5-dimension weighted score:

1. **Existence** (0.20) — whether any approved questions exist (gate dimension)
2. **Difficulty distribution** (0.20) — coverage of difficulty levels 1/2/3
3. **Bloom distribution** (0.20) — coverage of Bloom taxonomy levels
4. **Bilingual completeness** (0.15) — both EN/ZH stems present
5. **Empirical quality** (0.25) — based on empirical_difficulty and accuracy

Output: single coverage score per topic (0–100).
"""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import func
from sqlalchemy.orm import Session

from packages.core.logging import get_logger
from packages.db.models.learning.question import Question
from packages.db.models.learning.topic import LearningDependency, LearningTopic

logger = get_logger(__name__)

# ── Dimension weights ────────────────────────────────────────────────
# Existence is a gate: if 0, the total score is 0 regardless of other dims.
W_EXISTENCE = 0.20
W_DIFFICULTY = 0.20
W_BLOOM = 0.20
W_BILINGUAL = 0.15
W_QUALITY = 0.25

# ── Bloom taxonomy levels ────────────────────────────────────────────
ALL_BLOOM_LEVELS = [
    "remember",
    "understand",
    "apply",
    "analyze",
    "evaluate",
    "create",
]

# Expected difficulty levels
ALL_DIFFICULTY_LEVELS = [1, 2, 3]

# Minimum questions per difficulty/bloom for "full" coverage
MIN_PER_SLOT = 1


@dataclass
class DimensionScores:
    """Individual dimension scores, each 0.0–1.0."""

    existence: float
    difficulty: float
    bloom: float
    bilingual: float
    quality: float


@dataclass
class TopicCoverage5D:
    """Full 5D coverage result for a single topic."""

    topic_id: int
    topic_key: str
    name: str | None
    subject: str
    domain: str | None
    dimensions: DimensionScores
    coverage_score: float  # 0–100
    approved_question_count: int
    prerequisite_value: float
    # Breakdown for diagnostics
    difficulty_levels_present: list[int]
    bloom_levels_present: list[str]
    bilingual_ratio: float
    avg_accuracy: float | None


# ── Batch data loading ───────────────────────────────────────────────


def _batch_load_question_stats(
    db: Session, topic_ids: list[int], family_id: int | None = None
) -> dict[int, dict]:
    """Load question stats per topic in a single batch query.

    Returns {topic_id: {count, difficulties, blooms, bilingual_count, accuracies}}.
    """
    if not topic_ids:
        return {}

    q_filter = [
        Question.review_status == "approved",
        Question.topic_id.in_(topic_ids),
    ]
    if family_id is not None:
        q_filter.append(
            (Question.family_id == family_id) | Question.family_id.is_(None)
        )

    questions = (
        db.query(
            Question.topic_id,
            Question.id,
            Question.difficulty,
            Question.bloom_level,
            Question.stem_zh,
            Question.empirical_difficulty,
            Question.correct_count,
            Question.times_used,
        )
        .filter(*q_filter)
        .all()
    )

    stats: dict[int, dict] = {}
    for row in questions:
        tid = row[0]
        if tid not in stats:
            stats[tid] = {
                "count": 0,
                "difficulties": set(),
                "blooms": set(),
                "bilingual_count": 0,
                "accuracies": [],
            }
        s = stats[tid]
        s["count"] += 1
        s["difficulties"].add(row[2])
        s["blooms"].add(row[3])
        # Bilingual: has both stem (English) and stem_zh
        if row[4]:  # stem_zh is not None/empty
            s["bilingual_count"] += 1
        # Accuracy: correct_count / times_used
        if row[7] and row[7] > 0:
            s["accuracies"].append(row[6] / row[7])

    return stats


def _batch_prerequisite_values(
    db: Session, topic_ids: list[int]
) -> dict[int, float]:
    """Batch-compute prerequisite values for topics (same logic as coverage_service)."""
    if not topic_ids:
        return {}

    topics = (
        db.query(LearningTopic.id, LearningTopic.subject)
        .filter(LearningTopic.id.in_(topic_ids))
        .all()
    )
    subjects = {t.subject for t in topics if t.subject}

    result: dict[int, float] = {}
    for subject in subjects:
        subject_topic_ids = [t.id for t in topics if t.subject == subject]

        dep_counts: dict[int, int] = {
            row[0]: row[1]
            for row in db.query(
                LearningDependency.prerequisite_id,
                func.count(LearningDependency.id),
            )
            .filter(LearningDependency.prerequisite_id.in_(subject_topic_ids))
            .group_by(LearningDependency.prerequisite_id)
            .all()
        }

        max_dependents = max(dep_counts.values()) if dep_counts else 0
        for tid in subject_topic_ids:
            count = dep_counts.get(tid, 0)
            result[tid] = count / max_dependents if max_dependents > 0 else 0.0

    return result


# ── Dimension calculations ───────────────────────────────────────────


def _calc_existence(count: int) -> float:
    """Binary: 1.0 if any approved questions exist, else 0.0."""
    return 1.0 if count > 0 else 0.0


def _calc_difficulty(difficulties: set[int]) -> float:
    """Ratio of difficulty levels covered out of all 3 levels."""
    covered = sum(1 for d in ALL_DIFFICULTY_LEVELS if d in difficulties)
    return covered / len(ALL_DIFFICULTY_LEVELS)


def _calc_bloom(blooms: set[str]) -> float:
    """Ratio of Bloom levels covered out of all 6 levels."""
    covered = sum(1 for b in ALL_BLOOM_LEVELS if b in blooms)
    return covered / len(ALL_BLOOM_LEVELS)


def _calc_bilingual(count: int, bilingual_count: int) -> float:
    """Ratio of questions that have both EN and ZH stems."""
    if count == 0:
        return 0.0
    return bilingual_count / count


def _calc_quality(accuracies: list[float]) -> float:
    """Empirical quality score based on answer accuracy.

    Uses average accuracy across all questions for the topic.
    If no usage data, returns 0.5 (neutral — not penalized).
    """
    if not accuracies:
        return 0.5  # neutral when no usage data
    return sum(accuracies) / len(accuracies)


def _compute_weighted_score(dims: DimensionScores) -> float:
    """Compute weighted coverage score (0–100).

    Existence is a gate: if existence == 0, score = 0.
    """
    if dims.existence == 0.0:
        return 0.0

    raw = (
        W_EXISTENCE * dims.existence
        + W_DIFFICULTY * dims.difficulty
        + W_BLOOM * dims.bloom
        + W_BILINGUAL * dims.bilingual
        + W_QUALITY * dims.quality
    )
    return round(raw * 100, 1)


# ── Public API ───────────────────────────────────────────────────────


def compute_topic_coverage_5d(
    db: Session, topic_id: int, family_id: int | None = None
) -> TopicCoverage5D:
    """Compute 5D coverage for a single topic.

    Returns a TopicCoverage5D with score 0–100 and all dimension breakdowns.
    """
    topic = db.get(LearningTopic, topic_id)
    if topic is None:
        raise ValueError(f"Topic {topic_id} not found")

    stats = _batch_load_question_stats(db, [topic_id], family_id)
    s = stats.get(topic_id, {
        "count": 0,
        "difficulties": set(),
        "blooms": set(),
        "bilingual_count": 0,
        "accuracies": [],
    })

    prereq_map = _batch_prerequisite_values(db, [topic_id])

    dims = DimensionScores(
        existence=_calc_existence(s["count"]),
        difficulty=_calc_difficulty(s["difficulties"]),
        bloom=_calc_bloom(s["blooms"]),
        bilingual=_calc_bilingual(s["count"], s["bilingual_count"]),
        quality=_calc_quality(s["accuracies"]),
    )

    score = _compute_weighted_score(dims)
    avg_acc = sum(s["accuracies"]) / len(s["accuracies"]) if s["accuracies"] else None

    return TopicCoverage5D(
        topic_id=topic_id,
        topic_key=topic.topic_key,
        name=topic.name,
        subject=topic.subject,
        domain=topic.domain,
        dimensions=dims,
        coverage_score=score,
        approved_question_count=s["count"],
        prerequisite_value=prereq_map.get(topic_id, 0.0),
        difficulty_levels_present=sorted(s["difficulties"]),
        bloom_levels_present=sorted(s["blooms"]),
        bilingual_ratio=s["bilingual_count"] / s["count"] if s["count"] > 0 else 0.0,
        avg_accuracy=avg_acc,
    )


def compute_subject_coverage_5d(
    db: Session, subject: str, family_id: int | None = None
) -> dict:
    """Compute 5D subject-level coverage aggregation.

    Returns aggregated stats including average score, per-dimension averages,
    and topic count breakdowns.
    """
    topics = (
        db.query(LearningTopic)
        .filter(
            LearningTopic.subject == subject,
            LearningTopic.deprecated.is_(False),
        )
        .all()
    )
    total = len(topics)
    if total == 0:
        return {
            "subject": subject,
            "total_topics": 0,
            "avg_coverage_score": 0.0,
            "avg_dimensions": {
                "existence": 0.0,
                "difficulty": 0.0,
                "bloom": 0.0,
                "bilingual": 0.0,
                "quality": 0.0,
            },
            "topics_above_70": 0,
            "topics_above_40": 0,
            "topics_below_40": 0,
        }

    topic_ids = [t.id for t in topics]
    stats_map = _batch_load_question_stats(db, topic_ids, family_id)

    scores = []
    dim_totals = {
        "existence": 0.0,
        "difficulty": 0.0,
        "bloom": 0.0,
        "bilingual": 0.0,
        "quality": 0.0,
    }
    above_70 = 0
    above_40 = 0
    below_40 = 0

    for tid in topic_ids:
        s = stats_map.get(tid, {
            "count": 0,
            "difficulties": set(),
            "blooms": set(),
            "bilingual_count": 0,
            "accuracies": [],
        })

        dims = DimensionScores(
            existence=_calc_existence(s["count"]),
            difficulty=_calc_difficulty(s["difficulties"]),
            bloom=_calc_bloom(s["blooms"]),
            bilingual=_calc_bilingual(s["count"], s["bilingual_count"]),
            quality=_calc_quality(s["accuracies"]),
        )
        score = _compute_weighted_score(dims)
        scores.append(score)

        dim_totals["existence"] += dims.existence
        dim_totals["difficulty"] += dims.difficulty
        dim_totals["bloom"] += dims.bloom
        dim_totals["bilingual"] += dims.bilingual
        dim_totals["quality"] += dims.quality

        if score >= 70:
            above_70 += 1
        if score >= 40:
            above_40 += 1
        if score < 40:
            below_40 += 1

    avg_score = sum(scores) / total if total > 0 else 0.0
    avg_dims = {k: round(v / total, 3) for k, v in dim_totals.items()}

    return {
        "subject": subject,
        "total_topics": total,
        "avg_coverage_score": round(avg_score, 1),
        "avg_dimensions": avg_dims,
        "topics_above_70": above_70,
        "topics_above_40": above_40,
        "topics_below_40": below_40,
    }


def get_worklist(
    db: Session,
    subject: str | None = None,
    threshold: float = 50.0,
    limit: int = 100,
    family_id: int | None = None,
) -> list[dict]:
    """Get topics below coverage threshold, sorted by priority.

    Priority = coverage_score (ascending) * prerequisite_value (descending).
    Topics with low coverage AND high prerequisite value are highest priority.

    Returns a list of dicts suitable for question_router consumption.
    """
    query = db.query(LearningTopic).filter(
        LearningTopic.deprecated.is_(False),
    )
    if subject:
        query = query.filter(LearningTopic.subject == subject)

    topics = query.all()
    if not topics:
        return []

    topic_ids = [t.id for t in topics]
    stats_map = _batch_load_question_stats(db, topic_ids, family_id)
    prereq_map = _batch_prerequisite_values(db, topic_ids)

    worklist = []
    for topic in topics:
        s = stats_map.get(topic.id, {
            "count": 0,
            "difficulties": set(),
            "blooms": set(),
            "bilingual_count": 0,
            "accuracies": [],
        })

        dims = DimensionScores(
            existence=_calc_existence(s["count"]),
            difficulty=_calc_difficulty(s["difficulties"]),
            bloom=_calc_bloom(s["blooms"]),
            bilingual=_calc_bilingual(s["count"], s["bilingual_count"]),
            quality=_calc_quality(s["accuracies"]),
        )
        score = _compute_weighted_score(dims)

        if score < threshold:
            prereq = prereq_map.get(topic.id, 0.0)
            # Priority: low score + high prereq = most important
            priority = (100 - score) * 0.7 + prereq * 100 * 0.3
            worklist.append({
                "topic_id": topic.id,
                "topic_key": topic.topic_key,
                "name": topic.name,
                "subject": topic.subject,
                "domain": topic.domain,
                "coverage_score": score,
                "prerequisite_value": prereq,
                "priority": round(priority, 1),
                "dimensions": {
                    "existence": round(dims.existence, 2),
                    "difficulty": round(dims.difficulty, 2),
                    "bloom": round(dims.bloom, 2),
                    "bilingual": round(dims.bilingual, 2),
                    "quality": round(dims.quality, 2),
                },
                # Actionable info for generation
                "missing_difficulties": [
                    d for d in ALL_DIFFICULTY_LEVELS if d not in s["difficulties"]
                ],
                "missing_blooms": [
                    b for b in ALL_BLOOM_LEVELS if b not in s["blooms"]
                ],
                "needs_bilingual": s["bilingual_count"] < s["count"],
            })

    worklist.sort(key=lambda x: -x["priority"])
    return worklist[:limit]


def get_coverage_report(
    db: Session,
    subject: str | None = None,
    family_id: int | None = None,
) -> dict:
    """Generate a full coverage report for all subjects or a specific one.

    Returns subject-level aggregations plus a worklist of low-coverage topics.
    """
    # Get distinct subjects
    query = db.query(LearningTopic.subject).filter(
        LearningTopic.subject.isnot(None),
        LearningTopic.deprecated.is_(False),
    )
    if subject:
        query = query.filter(LearningTopic.subject == subject)
    subjects = [s[0] for s in query.distinct().all() if s[0]]

    subject_reports = []
    total_topics = 0
    total_above_70 = 0
    total_above_40 = 0
    total_below_40 = 0
    weighted_score_sum = 0.0

    for subj in subjects:
        report = compute_subject_coverage_5d(db, subj, family_id)
        subject_reports.append(report)
        total_topics += report["total_topics"]
        total_above_70 += report["topics_above_70"]
        total_above_40 += report["topics_above_40"]
        total_below_40 += report["topics_below_40"]
        weighted_score_sum += report["avg_coverage_score"] * report["total_topics"]

    overall_score = (
        round(weighted_score_sum / total_topics, 1) if total_topics > 0 else 0.0
    )

    # Worklist: all topics below 50
    worklist = get_worklist(
        db, subject=subject, threshold=50.0, limit=50, family_id=family_id
    )
    # Convert Snowflake IDs to strings for JSON
    for w in worklist:
        w["topic_id"] = str(w["topic_id"])

    return {
        "overall_score": overall_score,
        "total_topics": total_topics,
        "topics_above_70": total_above_70,
        "topics_above_40": total_above_40,
        "topics_below_40": total_below_40,
        "subjects": subject_reports,
        "worklist": worklist,
    }
