"""Castle service — aggregated towers/floors/bricks for the knowledge castle.

Scope (KTD3):
  in-range topics (source_taxonomy + age covered by age_range)
  ∪ topics where child has ``first_mastered_at IS NOT NULL``.

Towers = subject, Floors = domain, bricks = aggregated counts.
Windows = review_due ∩ scope + recommended ∩ scope, dedup + cap ≤ 10.
"""

from dataclasses import dataclass, field
from datetime import UTC, date, datetime
from typing import TYPE_CHECKING

from sqlalchemy.orm import Session

from packages.db.models.learning.progress import LearningProgress
from packages.db.models.learning.topic import LearningTopic

if TYPE_CHECKING:
    from apps.backend.app.schemas.learning import (
        CastleIndexResponse,
        CastleTowerSchema,
        CastleWindowSchema,
    )

# Cap constants (KTD4)
MAX_TOTAL_WINDOWS = 10
MAX_REVIEW_DUE_WINDOWS = 6


# ---------------------------------------------------------------------------
# Internal dataclasses
# ---------------------------------------------------------------------------


@dataclass
class CastleFloorData:
    domain: str
    mastered_count: int = 0
    learning_count: int = 0
    review_due_count: int = 0
    total_count: int = 0


@dataclass
class CastleTowerData:
    subject: str
    mastered_count: int = 0
    learning_count: int = 0
    review_due_count: int = 0
    total_count: int = 0
    floors: list[CastleFloorData] = field(default_factory=list)


@dataclass
class CastleWindowData:
    topic_id: int
    topic_name: str
    topic_name_zh: str
    reason: str  # "复习到期" | "推荐学习"
    subject: str
    domain: str


@dataclass
class CastleIndexData:
    towers: list[CastleTowerData]
    windows: list[CastleWindowData]
    streak_days: int


# ---------------------------------------------------------------------------
# Dataclass -> response schema mapping
# ---------------------------------------------------------------------------


def to_response(data: CastleIndexData) -> "CastleIndexResponse":
    """Map ``CastleIndexData`` onto the API response schema.

    Lives here so the child and parent routers share one mapper — a field added
    to ``CastleTowerData``/``CastleWindowData`` cannot then land on only one of
    the two endpoints.
    """
    from apps.backend.app.schemas.learning import CastleIndexResponse

    return CastleIndexResponse(
        towers=[_tower_to_schema(t) for t in data.towers],
        windows=[_window_to_schema(w) for w in data.windows],
        streak_days=data.streak_days,
    )


def _tower_to_schema(tower: CastleTowerData) -> "CastleTowerSchema":
    from apps.backend.app.schemas.learning import CastleFloorSchema, CastleTowerSchema

    return CastleTowerSchema(
        subject=tower.subject,
        mastered_count=tower.mastered_count,
        learning_count=tower.learning_count,
        review_due_count=tower.review_due_count,
        total_count=tower.total_count,
        floors=[
            CastleFloorSchema(
                domain=f.domain,
                mastered_count=f.mastered_count,
                learning_count=f.learning_count,
                review_due_count=f.review_due_count,
                total_count=f.total_count,
            )
            for f in tower.floors
        ],
    )


def _window_to_schema(window: CastleWindowData) -> "CastleWindowSchema":
    from apps.backend.app.schemas.learning import CastleWindowSchema

    return CastleWindowSchema(
        topic_id=window.topic_id,
        topic_name=window.topic_name,
        topic_name_zh=window.topic_name_zh,
        reason=window.reason,
        subject=window.subject,
        domain=window.domain,
    )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _compute_age(birthday: date | None) -> int | None:
    if birthday is None:
        return None
    today = date.today()
    age = today.year - birthday.year
    if (today.month, today.day) < (birthday.month, birthday.day):
        age -= 1
    return age


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def get_castle_index(
    db: Session,
    child_id: int,
    family_id: int,
    language: str | None,
) -> CastleIndexData:
    """Build the castle index for a child (U1).

    Returns towers (per-subject aggregations), windows (review_due + recommended),
    and ``streak_days`` for the decoration layer.  Zero-progress children get
    empty tower skeletons — never a 404.
    """
    from apps.backend.app.models.user import User
    from apps.backend.app.services.learning.stats_service import get_or_create_stats
    from apps.backend.app.services.learning.topic_service import (
        get_effective_source_taxonomy,
    )

    child = db.query(User).filter(User.id == child_id).first()
    if child is None:
        return CastleIndexData(towers=[], windows=[], streak_days=0)

    taxonomy = get_effective_source_taxonomy(db, language)
    age = _compute_age(child.birthday)

    # ---- 1. scope ---------------------------------------------------------
    scope_ids: set[int] = set()

    if age is not None:
        # In-range topics: age_range_start <= age <= age_range_end
        in_range = (
            db.query(LearningTopic.id)
            .filter(
                LearningTopic.source_taxonomy == taxonomy,
                LearningTopic.deprecated.is_(False),
                LearningTopic.age_range_start.isnot(None),
                LearningTopic.age_range_end.isnot(None),
                LearningTopic.age_range_start <= age,
                LearningTopic.age_range_end >= age,
            )
            .all()
        )
        scope_ids.update(row[0] for row in in_range)
    else:
        # Birthday NULL → fallback to age_group == 'mid' bucket (D1)
        mid_range = (
            db.query(LearningTopic.id)
            .filter(
                LearningTopic.source_taxonomy == taxonomy,
                LearningTopic.deprecated.is_(False),
                LearningTopic.age_group == "mid",
            )
            .all()
        )
        scope_ids.update(row[0] for row in mid_range)

    # UNION: topics where child has first_mastered_at IS NOT NULL
    mastered_rows = (
        db.query(LearningProgress.topic_id)
        .filter(
            LearningProgress.child_id == child_id,
            LearningProgress.first_mastered_at.isnot(None),
        )
        .all()
    )
    scope_ids.update(row[0] for row in mastered_rows)

    # ---- 2. topic details + progress for scope ----------------------------
    topics_map: dict[int, LearningTopic] = {}
    progress_map: dict[int, LearningProgress] = {}
    if scope_ids:
        for t in db.query(LearningTopic).filter(LearningTopic.id.in_(scope_ids)).all():
            topics_map[t.id] = t
        for p in (
            db.query(LearningProgress)
            .filter(
                LearningProgress.child_id == child_id,
                LearningProgress.topic_id.in_(scope_ids),
            )
            .all()
        ):
            progress_map[p.topic_id] = p

    # ---- 3. review_due set ------------------------------------------------
    now_utc = datetime.now(UTC)
    review_due_ids: set[int] = set()
    for tid, prog in progress_map.items():
        if (
            prog.mastery_level == "mastered"
            and prog.next_review_at is not None
            and prog.next_review_at <= now_utc
        ):
            review_due_ids.add(tid)

    # ---- 4. build towers / floors -----------------------------------------
    subject_domain_topics: dict[str, dict[str, list[LearningTopic]]] = {}
    for topic in topics_map.values():
        subject_domain_topics.setdefault(topic.subject, {}).setdefault(
            topic.domain or "", []
        ).append(topic)

    towers: list[CastleTowerData] = []
    for subject in sorted(subject_domain_topics):
        tower = CastleTowerData(subject=subject)
        for domain in sorted(subject_domain_topics[subject]):
            floor = _build_floor(
                subject_domain_topics[subject][domain],
                domain,
                progress_map,
                review_due_ids,
            )
            tower.floors.append(floor)
            tower.total_count += floor.total_count
            tower.mastered_count += floor.mastered_count
            tower.learning_count += floor.learning_count
            tower.review_due_count += floor.review_due_count
        towers.append(tower)

    # ---- 5. windows -------------------------------------------------------
    windows = _build_windows(
        db,
        child_id,
        scope_ids,
        topics_map,
    )

    # ---- 6. streak --------------------------------------------------------
    stats = get_or_create_stats(db, child_id, family_id)

    return CastleIndexData(
        towers=towers,
        windows=windows,
        streak_days=stats.learning_streak_days,
    )


def _build_floor(
    topics: list[LearningTopic],
    domain: str,
    progress_map: dict[int, LearningProgress],
    review_due_ids: set[int],
) -> CastleFloorData:
    floor = CastleFloorData(domain=domain, total_count=len(topics))
    for topic in topics:
        prog = progress_map.get(topic.id)
        if prog is None:
            continue
        if prog.mastery_level == "mastered":
            # Counted as mastered even when decayed: buildings never regress
            # (R3). review_due_count is an overlay flag for cracks/fading, not
            # a separate bucket, so the brick stays on the floor.
            floor.mastered_count += 1
            if topic.id in review_due_ids:
                floor.review_due_count += 1
        elif prog.mastery_level in ("available", "learning"):
            floor.learning_count += 1
    return floor


def _build_windows(
    db: Session,
    child_id: int,
    scope_ids: set[int],
    topics_map: dict[int, LearningTopic],
) -> list[CastleWindowData]:
    """Build window list: review_due ∩ scope + recommended ∩ scope, dedup + cap."""
    from apps.backend.app.services.learning.recommendation_service import (
        generate_recommendation_path,
    )
    from apps.backend.app.services.learning.zone_service import (
        find_review_due_topics,
    )

    seen: set[int] = set()
    windows: list[CastleWindowData] = []

    # -- review due (most-overdue-first; zone_service sorts by centrality desc) -
    review_due = find_review_due_topics(db, child_id)
    for r in review_due:
        if len(windows) >= MAX_REVIEW_DUE_WINDOWS:
            break
        if r.topic_id in seen or r.topic_id not in scope_ids:
            continue
        topic = topics_map.get(r.topic_id)
        if topic is None:
            continue
        seen.add(r.topic_id)
        windows.append(
            CastleWindowData(
                topic_id=r.topic_id,
                topic_name=topic.name or "",
                topic_name_zh=topic.name_zh or topic.name or "",
                reason="复习到期",
                subject=topic.subject,
                domain=topic.domain or "",
            )
        )

    # -- recommended (from recommendation path) -----------------------------
    rec_path = generate_recommendation_path(db, child_id, limit=5)
    for t in rec_path.topics:
        if len(windows) >= MAX_TOTAL_WINDOWS:
            break
        if t.topic_id in seen or t.topic_id not in scope_ids:
            continue
        topic = topics_map.get(t.topic_id)
        if topic is None:
            continue
        seen.add(t.topic_id)
        windows.append(
            CastleWindowData(
                topic_id=t.topic_id,
                topic_name=topic.name or "",
                topic_name_zh=topic.name_zh or topic.name or "",
                reason="推荐学习",
                subject=topic.subject,
                domain=topic.domain or "",
            )
        )

    # -- fallback: when still under the total cap, fill from in-scope available/learning
    if len(windows) < MAX_TOTAL_WINDOWS:
        remaining_ids = scope_ids - seen
        if remaining_ids:
            fallback_progresss = (
                db.query(LearningProgress)
                .filter(
                    LearningProgress.child_id == child_id,
                    LearningProgress.topic_id.in_(remaining_ids),
                    LearningProgress.mastery_level.in_(["available", "learning"]),
                )
                .all()
            )
            fallback_topic_ids = [p.topic_id for p in fallback_progresss]
            if fallback_topic_ids:
                fallback_topics = (
                    db.query(LearningTopic)
                    .filter(LearningTopic.id.in_(fallback_topic_ids))
                    .order_by(LearningTopic.centrality.desc())
                    .all()
                )
                for topic in fallback_topics:
                    if len(windows) >= MAX_TOTAL_WINDOWS:
                        break
                    if topic.id in seen:
                        continue
                    seen.add(topic.id)
                    windows.append(
                        CastleWindowData(
                            topic_id=topic.id,
                            topic_name=topic.name or "",
                            topic_name_zh=topic.name_zh or topic.name or "",
                            reason="推荐学习",
                            subject=topic.subject,
                            domain=topic.domain or "",
                        )
                    )

    return windows
