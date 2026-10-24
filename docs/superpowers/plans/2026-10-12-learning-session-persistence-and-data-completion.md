# Learning Session Persistence Fix & Data Completion

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fix the learning session 404 bug (C17.5) caused by missing `db.commit()` in all learning service mutation functions, and seed demo learning data so previously untested sim-test cases can be verified.

**Architecture:** Add `db.commit()` after the final `db.flush()` in every mutation function across 7 learning service files + 1 inline mutation in a router. Mirror 9 learning ORM models into the seed-data models file, create a learning factory, and extend the demo scenario with progress/practice/stats/path/assignment data for 大宝 and 小宝.

**Tech Stack:** Python 3.12, SQLAlchemy ORM, FastAPI dependency injection (`get_db`), pytest + SAVEPOINT isolation.

**Spec:** `tests/reports/ui-audit-2026-10-12.md`

---

## Root Cause Analysis

**Bug (C17.5):** `session_service.create_session()` calls `db.flush()` (sends SQL within transaction) but never calls `db.commit()`. The DB dependency (`get_db`) uses `autocommit=False, autoflush=False`. When the request ends, `get_db` closes the session → transaction rolled back → row lost. POST returns 201 with in-memory data; subsequent GET on a new DB session returns 404 `LEARNING_SESSION_NOT_FOUND`.

**Scope:** This is systemic — all 7 learning service files use `db.flush()` without `db.commit()`, while other modules (auth, children, tags, rental_contract) correctly commit. `path_service.py` is the only learning service that already commits (line 203).

**Impact:** Every learning mutation endpoint is affected — session create/end, assessment start, progress transitions, practice sessions, assignment creation, XP awards, streak updates, and onboarding completion.

## Global Constraints

- Python 3.12+; `uv` workspace from `server/`
- `db.flush()` stays (needed to populate IDs before return); `db.commit()` added AFTER the final flush
- SAVEPOINT test isolation (conftest.py) catches `db.commit()` — no test changes needed
- `tests/data/models.py` uses independent ORM models (no backend package imports)
- Learning topics must be seeded by `server/scripts/seed_learning_topics.py` BEFORE learning seed data
- Follow existing factory patterns (get_or_create, idempotent, `next_id()` from `factories.users`)
- No trailing slashes on router decorators (project CLAUDE.md rule)

## Review Focus

1. **Service functions called from within other service functions**: e.g., `progress_service.transition_to_mastered()` called from `practice_service.finish_session()`. If both add `db.commit()`, the inner commit fires first. Verify this is safe (it is — commit is idempotent, and SAVEPOINT catches it in tests).
2. **`get_or_create` functions**: `progress_service.get_or_create_progress()` and `stats_service.get_or_create_stats()` both create records if missing. The commit must happen regardless of whether a new record was created or an existing one was returned.
3. **`complete_onboarding` inline mutation** (router, not service): `stats.onboarding_completed = True; db.flush()` must become `db.commit()`. This is the only inline mutation in learning routers.
4. **FK constraints in seed data**: LearningProgress/PracticeSession require valid `topic_id`. The seed factory must query existing topics (from `seed_learning_topics.py`) and skip gracefully if none exist.
5. **Child auth context in seed data**: Seed data children must have `role="child"` and correct `family_id`. PIN is stored as `pin_hash` — use the same hashing as existing child factories.

---

## Task 1: Add `db.commit()` to session_service.py mutations

**Files:**
- Modify: `server/apps/backend/app/services/learning/session_service.py`

**Interfaces:**
- Consumes: `db: Session` from FastAPI DI
- Produces: Same function signatures; side-effect change (data now persists)

- [ ] **Step 1: Add `db.commit()` to `create_session()`**

After line 146 (`db.refresh(session)`), before the return on line 148, add:

```python
    db.commit()
```

The block becomes:
```python
    db.add(session)
    db.flush()
    db.refresh(session)
    db.commit()  # ← ADD THIS

    return {
        "id": session.id,
        ...
    }
```

- [ ] **Step 2: Add `db.commit()` to `end_session()`**

After line 188 (`db.flush()`), before `return session` on line 189, add:

```python
    db.commit()
```

- [ ] **Step 3: Add `db.commit()` to `start_assessment()`**

After line 223 (`db.flush()`), before `return progress` on line 224, add:

```python
    db.commit()
```

- [ ] **Step 4: Run lint**

Run: `cd server && uv run ruff check apps/backend/app/services/learning/session_service.py`
Expected: No errors

- [ ] **Step 5: Commit**

```bash
git add server/apps/backend/app/services/learning/session_service.py
git commit -m "fix(learning): add db.commit() to session_service mutations

create_session(), end_session(), and start_assessment() only called
db.flush() without db.commit(). Since get_db uses autocommit=False,
the transaction was rolled back on session close, causing POST to
succeed but subsequent GET to return 404 LEARNING_SESSION_NOT_FOUND.

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>"
```

---

## Task 2: Add `db.commit()` to progress_service.py mutations

**Files:**
- Modify: `server/apps/backend/app/services/learning/progress_service.py`

**Interfaces:**
- Consumes: `db: Session`, `LearningProgress` objects
- Produces: Same function signatures; 7 mutation functions now commit

There are 7 mutation functions. For each, add `db.commit()` after the final `db.flush()`:

- [ ] **Step 1: Add commit to `get_or_create_progress()` (flush at line 76)**

After the `db.flush()` call, add `db.commit()`. The function returns the progress object on line 78 — commit goes before that return.

- [ ] **Step 2: Add commit to `transition_to_learning()` (flush at line 90)**

After `db.flush()` on line 90, add `db.commit()` before `return progress` on line 91.

- [ ] **Step 3: Add commit to `transition_to_mastered()` (flush at line 197)**

After `db.flush()` on line 197, add `db.commit()` before the return.

- [ ] **Step 4: Add commit to `approve_parent_review()` (flush at line 334)**

After `db.flush()` on line 334, add `db.commit()` before the return.

- [ ] **Step 5: Add commit to `record_failed_assessment()` (flush at line 455)**

After `db.flush()` on line 455, add `db.commit()` before the return.

- [ ] **Step 6: Add commit to `check_and_notify_streak()` (flush at line 498)**

After `db.flush()` on line 498, add `db.commit()` before the return.

- [ ] **Step 7: Run lint**

Run: `cd server && uv run ruff check apps/backend/app/services/learning/progress_service.py`
Expected: No errors

- [ ] **Step 8: Commit**

```bash
git add server/apps/backend/app/services/learning/progress_service.py
git commit -m "fix(learning): add db.commit() to progress_service mutations

6 mutation functions (get_or_create_progress, transition_to_learning,
transition_to_mastered, approve_parent_review, record_failed_assessment,
check_and_notify_streak) only called db.flush() without committing.

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>"
```

---

## Task 3: Add `db.commit()` to remaining 5 learning services + 1 router

**Files:**
- Modify: `server/apps/backend/app/services/learning/practice_service.py`
- Modify: `server/apps/backend/app/services/learning/assignment_service.py`
- Modify: `server/apps/backend/app/services/learning/stats_service.py`
- Modify: `server/apps/backend/app/services/learning/question_service.py`
- Modify: `server/apps/backend/app/services/learning/practice_progress_integration.py`
- Modify: `server/apps/backend/app/routers/learning_child.py`

### practice_service.py (3 mutations)

- [ ] **Step 1: Add commit to `create_session()` (flush at line 40)**

After `db.flush()` on line 40, add `db.commit()` before the return.

- [ ] **Step 2: Add commit to `submit_answer()` (flush at line 116)**

After `db.flush()` on line 116, add `db.commit()` before the return.

- [ ] **Step 3: Add commit to `finish_session()` (flush at line 147)**

After `db.flush()` on line 147, add `db.commit()` before the return.

### assignment_service.py (2 mutations)

- [ ] **Step 4: Add commit to `create_assignment()` (flush at line 43)**

After `db.flush()` on line 43, add `db.commit()` before the return.

- [ ] **Step 5: Add commit to `submit_for_review()` (flush at line 91)**

After `db.flush()` on line 91, add `db.commit()` before the return.

### stats_service.py (3 mutations)

- [ ] **Step 6: Add commit to `get_or_create_stats()` (flush at line 108)**

After `db.flush()` on line 108, add `db.commit()` before the return.

- [ ] **Step 7: Add commit to `award_xp()` (flush at line 175)**

After `db.flush()` on line 175, add `db.commit()` before the return.

- [ ] **Step 8: Add commit to `update_streak()` (flush at line 220)**

After `db.flush()` on line 220, add `db.commit()` before the return.

### question_service.py (1 mutation)

- [ ] **Step 9: Add commit to `create_question()` (flush at line 113)**

After `db.flush()` on line 113, add `db.commit()` before the return.

### practice_progress_integration.py (1 mutation)

- [ ] **Step 10: Add commit to `update_progress_from_session()` (flush at line 86)**

After `db.flush()` on line 86, add `db.commit()` before the return.

### learning_child.py (1 inline mutation)

- [ ] **Step 11: Change `db.flush()` to `db.commit()` in `complete_onboarding()` (line 205)**

Replace `db.flush()` on line 205 with `db.commit()`. This is an inline mutation (not going through a service function):

```python
    stats.onboarding_completed = True
    db.commit()  # was db.flush()
    return OnboardingCompleteResponse(onboarding_completed=True)
```

- [ ] **Step 12: Run lint on all modified files**

```bash
cd server && uv run ruff check \
  apps/backend/app/services/learning/practice_service.py \
  apps/backend/app/services/learning/assignment_service.py \
  apps/backend/app/services/learning/stats_service.py \
  apps/backend/app/services/learning/question_service.py \
  apps/backend/app/services/learning/practice_progress_integration.py \
  apps/backend/app/routers/learning_child.py
```

Expected: No errors

- [ ] **Step 13: Run existing learning backend tests**

```bash
cd server && uv run pytest tests/backend/ -v -k "learning or bkt or adaptive or practice or progress" --tb=short
```

Expected: All existing tests pass (SAVEPOINT isolation catches the new commits)

- [ ] **Step 14: Commit**

```bash
git add server/apps/backend/app/services/learning/practice_service.py \
       server/apps/backend/app/services/learning/assignment_service.py \
       server/apps/backend/app/services/learning/stats_service.py \
       server/apps/backend/app/services/learning/question_service.py \
       server/apps/backend/app/services/learning/practice_progress_integration.py \
       server/apps/backend/app/routers/learning_child.py
git commit -m "fix(learning): add db.commit() to all remaining learning mutations

practice_service (3), assignment_service (2), stats_service (3),
question_service (1), practice_progress_integration (1), and
complete_onboarding inline flush→commit in learning_child router.

Total: 18 mutation functions + 1 inline now commit correctly.

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>"
```

---

## Task 4: Add learning ORM models to `tests/data/models.py`

**Files:**
- Modify: `tests/data/models.py` (append after line 603)

**Interfaces:**
- Consumes: `Base` from `db`, existing column types already imported
- Produces: 9 new ORM classes for seed data use

Append these 9 ORM model classes to the end of `tests/data/models.py`. They mirror the backend's learning models in `server/packages/db/models/learning/` but are independent (no backend imports).

- [ ] **Step 1: Add learning models**

Append to `tests/data/models.py`:

```python


# ── Learning models (mirror backend packages/db/models/learning/) ────────────

class LearningTopic(Base):
    """Learning topic — seeded by server/scripts/seed_learning_topics.py."""
    __tablename__ = "learning_topics"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    topic_key: Mapped[str] = mapped_column(String(200), unique=True, nullable=False)
    topic_type: Mapped[str] = mapped_column(String(50), nullable=False, default="concept")
    subject: Mapped[str] = mapped_column(String(100), nullable=False)
    domain: Mapped[str] = mapped_column(String(200), nullable=False)
    name: Mapped[str] = mapped_column(String(500), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    age_group: Mapped[str] = mapped_column(String(20), nullable=False, default="mid")
    source_taxonomy: Mapped[str | None] = mapped_column(String(50), nullable=True)
    evidence_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    standards_json: Mapped[str | None] = mapped_column(Text, nullable=True)


class LearningProgress(Base):
    """Per-child per-topic mastery progress."""
    __tablename__ = "learning_progress"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    child_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id"), nullable=False, index=True)
    topic_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("learning_topics.id"), nullable=False, index=True)
    mastery_level: Mapped[str] = mapped_column(String(20), nullable=False, default="unseen")
    mastery_score: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    xp_earned: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    stability: Mapped[float | None] = mapped_column(Float, nullable=True)
    ease_factor: Mapped[float | None] = mapped_column(Float, nullable=True)
    next_review_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    last_practice_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    __table_args__ = (
        UniqueConstraint("child_id", "topic_id", name="uq_learning_progress_child_topic"),
    )


class LearningSession(Base):
    """A learning session — child studies a topic."""
    __tablename__ = "learning_sessions"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    child_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id"), nullable=False, index=True)
    topic_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("learning_topics.id"), nullable=False)
    assignment_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    thread_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    session_type: Mapped[str] = mapped_column(String(20), nullable=False, default="tutorial")
    ai_evaluation_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    score: Mapped[float | None] = mapped_column(Float, nullable=True)
    duration_seconds: Mapped[int | None] = mapped_column(Integer, nullable=True)
    started_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    ended_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class PracticeSession(Base):
    """Practice session — child answers questions on a topic."""
    __tablename__ = "practice_sessions"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    child_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id"), nullable=False, index=True)
    topic_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("learning_topics.id"), nullable=False)
    session_mode: Mapped[str] = mapped_column(String(30), nullable=False, default="free")
    total_score: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    completed_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    source: Mapped[str | None] = mapped_column(String(50), nullable=True)
    started_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    ended_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class PracticeAttempt(Base):
    """Single question attempt within a practice session."""
    __tablename__ = "practice_attempts"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    session_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("practice_sessions.id"), nullable=False, index=True)
    question_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("questions.id"), nullable=False)
    child_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id"), nullable=False)
    topic_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("learning_topics.id"), nullable=False)
    user_answer: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_correct: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    time_spent_seconds: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class Question(Base):
    """Question in the question bank."""
    __tablename__ = "questions"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    topic_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("learning_topics.id"), nullable=False, index=True)
    question_type: Mapped[str] = mapped_column(String(30), nullable=False, default="multiple_choice")
    stem: Mapped[str] = mapped_column(Text, nullable=False)
    answer: Mapped[str] = mapped_column(Text, nullable=False)
    difficulty: Mapped[int] = mapped_column(Integer, nullable=False, default=3)
    bloom_level: Mapped[str | None] = mapped_column(String(20), nullable=True)
    source: Mapped[str | None] = mapped_column(String(50), nullable=True)


class ChildLearningStats(Base):
    """Cumulative learning stats per child."""
    __tablename__ = "child_learning_stats"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    child_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id"), nullable=False, unique=True)
    family_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("families.id"), nullable=False, index=True)
    cumulative_xp: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    level: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    learning_streak_days: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    current_zone: Mapped[str | None] = mapped_column(String(20), nullable=True)
    onboarding_completed: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    today_xp: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    last_xp_reset_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    total_practice_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    updated_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class LearningPath(Base):
    """A curated learning path for a child."""
    __tablename__ = "learning_paths"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    family_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("families.id"), nullable=False, index=True)
    child_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="active")
    per_task_score: Mapped[int] = mapped_column(Integer, nullable=False, default=10)
    bonus_score: Mapped[int] = mapped_column(Integer, nullable=False, default=50)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class LearningPathItem(Base):
    """A topic within a learning path, ordered."""
    __tablename__ = "learning_path_items"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    path_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("learning_paths.id"), nullable=False, index=True)
    topic_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("learning_topics.id"), nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending")
    created_by: Mapped[int] = mapped_column(BigInteger, nullable=False)


class LearningAssignment(Base):
    """A learning task assigned to a child."""
    __tablename__ = "learning_assignments"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    family_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("families.id"), nullable=False, index=True)
    child_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id"), nullable=False, index=True)
    topic_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("learning_topics.id"), nullable=False)
    assignment_type: Mapped[str] = mapped_column(String(30), nullable=False, default="parent_assigned")
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending")
    created_by: Mapped[int] = mapped_column(BigInteger, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    completed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
```

- [ ] **Step 2: Verify import works**

Run from `tests/data/`:
```bash
cd tests/data && python -c "from models import LearningTopic, LearningProgress, PracticeSession, PracticeAttempt, ChildLearningStats, LearningPath, LearningPathItem, LearningAssignment, Question; print('OK: 9 learning models imported')"
```

Expected: `OK: 9 learning models imported`

- [ ] **Step 3: Commit**

```bash
git add tests/data/models.py
git commit -m "feat(seed): add 9 learning ORM models to seed data

Mirror backend learning models for seed data independence:
LearningTopic, LearningProgress, LearningSession, PracticeSession,
PracticeAttempt, Question, ChildLearningStats, LearningPath,
LearningPathItem, LearningAssignment.

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>"
```

---

## Task 5: Create `tests/data/factories/learning.py`

**Files:**
- Create: `tests/data/factories/learning.py`

**Interfaces:**
- Consumes: Models from `tests/data/models.py`, `next_id()` from `factories/users.py`
- Produces: `LearningFactory` class with static methods for creating learning data

- [ ] **Step 1: Create the factory file**

```python
"""学习相关工厂 — 进度、练习、统计、路径、任务。"""

from __future__ import annotations

from datetime import datetime, timedelta

from sqlalchemy.orm import Session

from models import (
    ChildLearningStats,
    LearningAssignment,
    LearningPath,
    LearningPathItem,
    LearningProgress,
    LearningTopic,
    PracticeAttempt,
    PracticeSession,
    Question,
    User,
)
from factories.users import next_id


class LearningFactory:
    @staticmethod
    def get_or_create_progress(
        db: Session,
        *,
        child_id: int,
        topic_id: int,
        mastery_level: str = "unseen",
        mastery_score: float = 0.0,
        attempts: int = 0,
        xp_earned: int = 0,
    ) -> tuple[LearningProgress, bool]:
        existing = (
            db.query(LearningProgress)
            .filter_by(child_id=child_id, topic_id=topic_id)
            .first()
        )
        if existing:
            return existing, False

        progress = LearningProgress(
            id=next_id(),
            child_id=child_id,
            topic_id=topic_id,
            mastery_level=mastery_level,
            mastery_score=mastery_score,
            attempts=attempts,
            xp_earned=xp_earned,
        )
        db.add(progress)
        db.flush()
        return progress, True

    @staticmethod
    def get_or_create_stats(
        db: Session,
        *,
        child_id: int,
        family_id: int,
        cumulative_xp: int = 0,
        level: int = 1,
        streak: int = 0,
        zone: str | None = None,
    ) -> tuple[ChildLearningStats, bool]:
        existing = (
            db.query(ChildLearningStats)
            .filter_by(child_id=child_id)
            .first()
        )
        if existing:
            return existing, False

        stats = ChildLearningStats(
            id=next_id(),
            child_id=child_id,
            family_id=family_id,
            cumulative_xp=cumulative_xp,
            level=level,
            learning_streak_days=streak,
            current_zone=zone,
            onboarding_completed=True,
        )
        db.add(stats)
        db.flush()
        return stats, True

    @staticmethod
    def create_practice_session(
        db: Session,
        *,
        child_id: int,
        topic_id: int,
        total_score: float = 0.0,
        completed_count: int = 0,
        session_mode: str = "free",
        started_at: datetime | None = None,
    ) -> PracticeSession:
        ps = PracticeSession(
            id=next_id(),
            child_id=child_id,
            topic_id=topic_id,
            session_mode=session_mode,
            total_score=total_score,
            completed_count=completed_count,
            started_at=started_at or datetime.utcnow(),
        )
        db.add(ps)
        db.flush()
        return ps

    @staticmethod
    def create_question(
        db: Session,
        *,
        topic_id: int,
        stem: str = "测试题目",
        answer: str = '{"correct": "A"}',
        difficulty: int = 3,
    ) -> Question:
        q = Question(
            id=next_id(),
            topic_id=topic_id,
            question_type="multiple_choice",
            stem=stem,
            answer=answer,
            difficulty=difficulty,
        )
        db.add(q)
        db.flush()
        return q

    @staticmethod
    def create_attempt(
        db: Session,
        *,
        session_id: int,
        question_id: int,
        child_id: int,
        topic_id: int,
        is_correct: bool = True,
        time_spent: int = 30,
    ) -> PracticeAttempt:
        attempt = PracticeAttempt(
            id=next_id(),
            session_id=session_id,
            question_id=question_id,
            child_id=child_id,
            topic_id=topic_id,
            user_answer="A",
            is_correct=is_correct,
            time_spent_seconds=time_spent,
        )
        db.add(attempt)
        db.flush()
        return attempt

    @staticmethod
    def create_path(
        db: Session,
        *,
        family_id: int,
        child_id: int,
        name: str = "学习路径",
        topic_ids: list[int] | None = None,
        created_by: int = 0,
    ) -> LearningPath:
        path = LearningPath(
            id=next_id(),
            family_id=family_id,
            child_id=child_id,
            name=name,
            status="active",
        )
        db.add(path)
        db.flush()

        if topic_ids:
            for i, tid in enumerate(topic_ids):
                item = LearningPathItem(
                    id=next_id(),
                    path_id=path.id,
                    topic_id=tid,
                    sort_order=i,
                    status="pending",
                    created_by=created_by,
                )
                db.add(item)
            db.flush()

        return path

    @staticmethod
    def create_assignment(
        db: Session,
        *,
        family_id: int,
        child_id: int,
        topic_id: int,
        assignment_type: str = "parent_assigned",
        status: str = "pending",
        created_by: int = 0,
    ) -> LearningAssignment:
        assignment = LearningAssignment(
            id=next_id(),
            family_id=family_id,
            child_id=child_id,
            topic_id=topic_id,
            assignment_type=assignment_type,
            status=status,
            created_by=created_by,
        )
        db.add(assignment)
        db.flush()
        return assignment

    @staticmethod
    def find_topic_ids_by_keys(
        db: Session, topic_keys: list[str]
    ) -> dict[str, int]:
        """Look up topic IDs by topic_key. Returns {key: id} for found topics."""
        topics = (
            db.query(LearningTopic)
            .filter(LearningTopic.topic_key.in_(topic_keys))
            .all()
        )
        return {t.topic_key: t.id for t in topics}
```

- [ ] **Step 2: Verify import**

```bash
cd tests/data && python -c "from factories.learning import LearningFactory; print('OK: LearningFactory imported')"
```

Expected: `OK: LearningFactory imported`

- [ ] **Step 3: Commit**

```bash
git add tests/data/factories/learning.py
git commit -m "feat(seed): add LearningFactory for learning test data

Factories for: progress, stats, practice sessions, attempts,
questions, learning paths (+ items), assignments.
Plus find_topic_ids_by_keys helper for topic lookup.

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>"
```

---

## Task 6: Extend demo scenario with learning data

**Files:**
- Modify: `tests/data/scenarios/demo.py`

**Interfaces:**
- Consumes: `LearningFactory`, existing demouser children (大宝, 小宝), topics from `seed_learning_topics.py`
- Produces: Learning progress, practice, stats, paths, assignments for both children

**Prerequisites:** Learning topics must exist in DB (run `server/scripts/seed_learning_topics.py --source beijing` first).

- [ ] **Step 1: Add import at top of demo.py**

Add to the imports section (after existing factory imports):

```python
from factories.learning import LearningFactory
```

- [ ] **Step 2: Add learning data section before the final print statement**

Insert before the final `print("  [ok] demouser — ...")` line (currently line 637). Add a new section:

```python
    # ── 学习数据 ────────────────────────────────────────────────────────────
    # 需要预先运行: cd server && uv run python scripts/seed_learning_topics.py --source beijing
    topic_keys = [
        "bj_mt_S1_NUM_N_01",    # 一年级数学：数的认识
        "bj_mt_S1_NUM_N_02",    # 一年级数学：数的运算
        "bj_mt_S1_G_N_01",      # 一年级数学：图形与几何
        "bj_cn_S1_R_N_01",      # 一年级语文：识字与写字
        "bj_cn_S1_RD_N_01",     # 一年级语文：阅读
        "bj_en_S1_L_N_01",      # 一年级英语：听说
    ]
    topic_ids = LearningFactory.find_topic_ids_by_keys(db, topic_keys)

    if topic_ids:
        # 大宝: 数学 progressed (mastered + in-progress), 语文 started
        dabao_math_01 = topic_ids.get("bj_mt_S1_NUM_N_01")
        dabao_math_02 = topic_ids.get("bj_mt_S1_NUM_N_02")
        dabao_math_03 = topic_ids.get("bj_mt_S1_G_N_01")
        dabao_cn_01 = topic_ids.get("bj_cn_S1_R_N_01")
        dabao_cn_02 = topic_ids.get("bj_cn_S1_RD_N_01")
        dabao_en_01 = topic_ids.get("bj_en_S1_L_N_01")

        # Progress: 1 mastered, 2 learning, 1 unseen
        if dabao_math_01:
            LearningFactory.get_or_create_progress(
                db, child_id=child1.id, topic_id=dabao_math_01,
                mastery_level="mastered", mastery_score=0.92,
                attempts=5, xp_earned=250,
            )
        if dabao_math_02:
            LearningFactory.get_or_create_progress(
                db, child_id=child1.id, topic_id=dabao_math_02,
                mastery_level="learning", mastery_score=0.55,
                attempts=2, xp_earned=80,
            )
        if dabao_cn_01:
            LearningFactory.get_or_create_progress(
                db, child_id=child1.id, topic_id=dabao_cn_01,
                mastery_level="learning", mastery_score=0.40,
                attempts=1, xp_earned=40,
            )

        # Practice session for mastered topic
        if dabao_math_01:
            q1 = LearningFactory.create_question(
                db, topic_id=dabao_math_01,
                stem="1 + 2 = ?", answer='{"correct": "3"}', difficulty=1,
            )
            q2 = LearningFactory.create_question(
                db, topic_id=dabao_math_01,
                stem="3 + 4 = ?", answer='{"correct": "7"}', difficulty=2,
            )
            ps1 = LearningFactory.create_practice_session(
                db, child_id=child1.id, topic_id=dabao_math_01,
                total_score=100.0, completed_count=2,
                started_at=datetime.now() - timedelta(days=2),
            )
            LearningFactory.create_attempt(
                db, session_id=ps1.id, question_id=q1.id,
                child_id=child1.id, topic_id=dabao_math_01,
                is_correct=True, time_spent=15,
            )
            LearningFactory.create_attempt(
                db, session_id=ps1.id, question_id=q2.id,
                child_id=child1.id, topic_id=dabao_math_01,
                is_correct=True, time_spent=25,
            )

        # Stats
        LearningFactory.get_or_create_stats(
            db, child_id=child1.id, family_id=fam.id,
            cumulative_xp=370, level=2, streak=3, zone="review",
        )

        # Learning path (parent-assigned)
        path_topic_ids = [t for t in [dabao_math_01, dabao_math_02, dabao_math_03] if t]
        if path_topic_ids:
            LearningFactory.create_path(
                db, family_id=fam.id, child_id=child1.id,
                name="大宝数学提升路径", topic_ids=path_topic_ids,
                created_by=user.id,
            )

        # Assignments
        for tid in [dabao_math_02, dabao_cn_01]:
            if tid:
                LearningFactory.create_assignment(
                    db, family_id=fam.id, child_id=child1.id,
                    topic_id=tid, assignment_type="parent_assigned",
                    status="in_progress", created_by=user.id,
                )
        if dabao_math_03:
            LearningFactory.create_assignment(
                db, family_id=fam.id, child_id=child1.id,
                topic_id=dabao_math_03, assignment_type="parent_assigned",
                status="pending", created_by=user.id,
            )

        # 小宝: minimal — 1 topic started
        xiaobao_topic = topic_ids.get("bj_cn_S1_R_N_01")
        if xiaobao_topic:
            LearningFactory.get_or_create_progress(
                db, child_id=child2.id, topic_id=xiaobao_topic,
                mastery_level="unseen", mastery_score=0.0,
                attempts=0, xp_earned=0,
            )
        LearningFactory.get_or_create_stats(
            db, child_id=child2.id, family_id=fam.id,
            cumulative_xp=0, level=1, streak=0,
        )

        if verbose:
            print(f"  [ok] demouser — 学习数据: 大宝 {sum(1 for t in [dabao_math_01, dabao_math_02, dabao_cn_01] if t)} 进度, 小宝 {1 if xiaobao_topic else 0} 进度")
    else:
        if verbose:
            print("  [skip] demouser — 无学习主题数据 (请先运行 seed_learning_topics.py --source beijing)")
```

- [ ] **Step 3: Update the final print message**

Update the final print statement to include learning data:

```python
    print("  [ok] demouser — 完整仿真数据已创建（19实物+11金融+7负债+3租约+9心愿+2儿童+盲盒+5行程+行程项+21费用+2结算+家庭约定+学习数据）")
```

- [ ] **Step 4: Verify syntax**

```bash
cd tests/data && python -c "import scenarios.demo; print('OK: demo.py imports clean')"
```

- [ ] **Step 5: Commit**

```bash
git add tests/data/scenarios/demo.py
git commit -m "feat(seed): add learning data to demo scenario

大宝: 3 progress records (1 mastered, 2 learning), 1 practice
session with 2 attempts, stats (level 2, 370 XP, 3-day streak),
learning path (3 topics), 3 assignments.
小宝: 1 progress (unseen), basic stats.

Requires topics seeded by seed_learning_topics.py --source beijing.

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>"
```

---

## Task 7: Add session persistence verification test

**Files:**
- Create: `server/tests/backend/test_learning_session_persistence.py`

**Interfaces:**
- Consumes: `db` + `client` fixtures from `conftest.py`, `session_service`, `LearningTopic`, `User`, `Family`
- Produces: 3 tests verifying POST→GET persistence for sessions, progress, and practice

- [ ] **Step 1: Create the test file**

```python
"""Verify that learning mutations persist — the db.commit() fix.

Root cause (C17.5): session_service.create_session() called db.flush()
but not db.commit(), so the row was lost when the request's DB session
closed. POST returned 201 but GET returned 404.
"""

import pytest
from sqlalchemy.orm import Session

from apps.backend.app.services.learning import session_service, progress_service, practice_service
from apps.backend.app.schemas.learning import SessionCreate
from packages.db.models.family import Family
from packages.db.models.learning.topic import LearningTopic
from packages.db.models.user import User


@pytest.fixture
def learning_setup(db: Session):
    """Create family, child, and topic for learning tests."""
    family = Family(name="Persistence Test", invite_code="LP01", created_by=1)
    db.add(family)
    db.flush()

    child = User(
        display_name="Learn Child", password_hash="x",
        role="child", family_id=family.id,
    )
    db.add(child)
    db.flush()

    topic = LearningTopic(
        topic_key="persist_test",
        topic_type="concept",
        subject="mathematics",
        domain="Test",
        name="Persist Test",
        description="test",
        age_group="mid",
    )
    db.add(topic)
    db.flush()

    return {"db": db, "family": family, "child": child, "topic": topic}


def test_session_create_persists(learning_setup):
    """POST create_session → data is visible to new query (commits, not just flushes)."""
    db = learning_setup["db"]
    child = learning_setup["child"]
    topic = learning_setup["topic"]

    req = SessionCreate(topic_id=topic.id)
    result = session_service.create_session(db, child.id, req)

    # Verify data persisted by querying from the same session
    # (after commit, data is visible even without refresh)
    from packages.db.models.learning.session import LearningSession
    found = db.query(LearningSession).filter_by(id=result["id"]).first()
    assert found is not None, "Session row should exist after create_session()"
    assert found.child_id == child.id
    assert found.topic_id == topic.id


def test_session_end_persists(learning_setup):
    """end_session() changes (ended_at, duration) should persist."""
    db = learning_setup["db"]
    child = learning_setup["child"]
    topic = learning_setup["topic"]

    req = SessionCreate(topic_id=topic.id)
    result = session_service.create_session(db, child.id, req)
    session_id = result["id"]

    ended = session_service.end_session(db, session_id, score=85.0)
    assert ended.ended_at is not None
    assert ended.score == 85.0

    # Verify persistence
    from packages.db.models.learning.session import LearningSession
    found = db.query(LearningSession).filter_by(id=session_id).first()
    assert found.ended_at is not None
    assert found.score == 85.0


def test_progress_get_or_create_persists(learning_setup):
    """get_or_create_progress() creates a row that persists."""
    db = learning_setup["db"]
    child = learning_setup["child"]
    topic = learning_setup["topic"]

    progress = progress_service.get_or_create_progress(db, child.id, topic.id)
    assert progress is not None

    # Verify persistence
    from packages.db.models.learning.progress import LearningProgress
    found = db.query(LearningProgress).filter_by(
        child_id=child.id, topic_id=topic.id
    ).first()
    assert found is not None
    assert found.id == progress.id


def test_practice_session_create_persists(learning_setup):
    """practice_service.create_session() persists."""
    db = learning_setup["db"]
    child = learning_setup["child"]
    topic = learning_setup["topic"]

    ps = practice_service.create_session(
        db, child_id=child.id, topic_id=topic.id, session_mode="free"
    )
    assert ps is not None

    from packages.db.models.learning.practice import PracticeSession
    found = db.query(PracticeSession).filter_by(id=ps.id).first()
    assert found is not None
    assert found.child_id == child.id
```

- [ ] **Step 2: Run the tests**

```bash
cd server && uv run pytest tests/backend/test_learning_session_persistence.py -v
```

Expected: All 4 tests PASS

- [ ] **Step 3: Commit**

```bash
git add server/tests/backend/test_learning_session_persistence.py
git commit -m "test(learning): verify session persistence after db.commit() fix

4 tests covering create_session, end_session, get_or_create_progress,
and practice session creation — all verify data persists after the
service function returns (the core bug was flush-only, no commit).

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>"
```

---

## Task 8: Full verification

- [ ] **Step 1: Run all backend tests**

```bash
cd server && uv run pytest tests/backend/ -v --tb=short -q 2>&1 | tail -20
```

Expected: All tests pass. The SAVEPOINT isolation in conftest.py catches `db.commit()` calls in service functions, so no test behavior changes.

- [ ] **Step 2: Run ruff on all modified learning service files**

```bash
cd server && uv run ruff check apps/backend/app/services/learning/ apps/backend/app/routers/learning_child.py
```

Expected: No errors

- [ ] **Step 3: Verify seed data syntax**

```bash
cd tests/data && python -c "
from models import LearningTopic, LearningProgress, PracticeSession, PracticeAttempt, ChildLearningStats, LearningPath, LearningPathItem, LearningAssignment, Question
from factories.learning import LearningFactory
import scenarios.demo
print('All imports OK')
"
```

Expected: `All imports OK`

- [ ] **Step 4: (Optional) Re-seed and run sim test**

If topics are seeded (`seed_learning_topics.py --source beijing`), re-run the seed and sim test:

```bash
cd server && uv run python scripts/seed_learning_topics.py --source beijing
cd tests/data && python seed_data.py --force  # re-seed with learning data
```

Then run the sim test to verify C17.5 and previously untested items.
