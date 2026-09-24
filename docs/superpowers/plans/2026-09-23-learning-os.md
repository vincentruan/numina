# Learning OS Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a Children's AI Learning OS module — knowledge graph, learning progress tracking, AI tutor, parent dashboard — integrated into Numina's existing family task workflow.

**Architecture:** 7 new SQLAlchemy models (3 global knowledge graph + 4 per-family progress), 3 FastAPI routers (global/parent/child), service layer with state machine, DeerFlow AI skill for tutoring, Vue pages for both child and parent apps. Knowledge graph is global (shared across families); progress is per-family.

**Tech Stack:** Python 3.12 + FastAPI + SQLAlchemy 2.0 (Mapped) + Alembic | Vue 3 + TypeScript + Vant 4 + vue-i18n | DeerFlow AI agent (existing)

**Spec:** `docs/superpowers/specs/2026-09-22-learning-os-design.md`

## Global Constraints

- All IDs are Snowflake BigInteger — serialized as `string` in API responses, typed as `string` in TypeScript
- API endpoints respond directly (no 307 redirects) — root-path decorators use `""` not `"/"`
- Response schemas inherit `SnowflakeBase`; request schemas use plain `BaseModel`
- Auth: `require_adult` for parent endpoints, `get_current_child_user` for child endpoints
- Errors use `AppError(ErrorCode.XXX)` with i18n — add new codes to `errors/codes.py` + locale files
- Child app: `<script setup lang="ts">` only, Vant 4 auto-imported, no `<van-config-provider>`, CSS variables only
- Main app: `<van-config-provider :theme="resolvedTheme">` for dark mode
- All user-facing strings use `t('key')` — no hardcoded Chinese in templates
- `defineOptions({ name: 'Xxx' })` on every page component (KeepAlive requirement)
- `usePageLoading()` with `increment()`/`decrement()` wraps all async mounts
- Models: `from packages.db.session import Base, UTCDateTime` + `from packages.core.snowflake import next_id`
- Tests: SAVEPOINT-isolated `db` fixture, `client` fixture, IDs compared as strings
- Commands from `server/`: `uv run pytest`, `uv run ruff check`, `uv run ruff format`, `uv run alembic`

---

## Task Group A: Data Layer (Models + Migration + Registration)

### Task 1: Learning Topic, Dependency, Cluster Models (Global Knowledge Graph)

**Files:**
- Create: `server/packages/db/models/learning/__init__.py`
- Create: `server/packages/db/models/learning/topic.py`
- Modify: `server/packages/db/models/__init__.py` (register new models)

**Interfaces:**
- Produces: `LearningTopic`, `LearningDependency`, `LearningCluster` ORM classes
- Consumed by: Task 2 (migration), Task 4 (topic service), Task 13 (seed)

- [ ] **Step 1: Create the learning package init**

```python
# server/packages/db/models/learning/__init__.py
```

Empty file.

- [ ] **Step 2: Create topic.py with all 3 global models**

```python
# server/packages/db/models/learning/topic.py
"""Global knowledge graph models — shared across all families."""

from sqlalchemy import BigInteger, Float, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from packages.core.snowflake import next_id
from packages.db.session import Base, UTCDateTime


class LearningTopic(Base):
    __tablename__ = "learning_topics"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, default=next_id)
    topic_key: Mapped[str] = mapped_column(String(50), unique=True, nullable=False, index=True)
    topic_type: Mapped[str] = mapped_column(String(20), nullable=False)
    subject: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    domain: Mapped[str | None] = mapped_column(String(100), nullable=True)
    name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    name_zh: Mapped[str | None] = mapped_column(String(200), nullable=True)
    description: Mapped[str] = mapped_column(Text, nullable=False, default="")
    description_zh: Mapped[str | None] = mapped_column(Text, nullable=True)
    age_range_start: Mapped[int | None] = mapped_column(Integer, nullable=True)
    age_range_end: Mapped[int | None] = mapped_column(Integer, nullable=True)
    centrality: Mapped[float | None] = mapped_column(Float, nullable=True)
    # JSON-in-Text pattern: raw Text column + json_text property
    evidence_json: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    evidence_zh_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    assessment_prompt: Mapped[str | None] = mapped_column(Text, nullable=True)
    assessment_prompt_zh: Mapped[str | None] = mapped_column(Text, nullable=True)
    standards_json: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    ability_dimensions_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    age_group: Mapped[str] = mapped_column(String(10), nullable=False, default="mid")
    deprecated: Mapped[bool] = mapped_column(default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(UTCDateTime(), server_default=func.now(), onupdate=func.now())

    # Add imports: from datetime import datetime; from sqlalchemy import func
    # Add json_text properties after class body:
    # evidence: list = json_text("evidence_json")
    # evidence_zh: list | None = json_text("evidence_zh_json")
    # standards: list = json_text("standards_json")
    # ability_dimensions: list | None = json_text("ability_dimensions_json")
```

**IMPORTANT:** The JSON fields use the `json_text` mixin from `packages.db.mixins.json_text`. Add these property declarations after the class:

```python
from packages.db.mixins.json_text import json_text

class LearningTopic(Base):
    # ... columns as above ...

    # JSON accessor properties
    evidence: list = json_text("evidence_json")
    evidence_zh: list | None = json_text("evidence_zh_json")
    standards: list = json_text("standards_json")
    ability_dimensions: list | None = json_text("ability_dimensions_json")
```

Also add the self-referencing dependency relationship:

```python
class LearningDependency(Base):
    __tablename__ = "learning_dependencies"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, default=next_id)
    topic_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("learning_topics.id"), nullable=False, index=True)
    prerequisite_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("learning_topics.id"), nullable=False, index=True)
    strength: Mapped[str] = mapped_column(String(10), nullable=False)
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)


class LearningCluster(Base):
    __tablename__ = "learning_clusters"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, default=next_id)
    subject: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    domain: Mapped[str] = mapped_column(String(100), nullable=False)
    age_range_start: Mapped[int | None] = mapped_column(Integer, nullable=True)
    age_group: Mapped[str] = mapped_column(String(10), nullable=False, default="mid")
    summary: Mapped[str] = mapped_column(Text, nullable=False, default="")
```

- [ ] **Step 3: Register models in __init__.py**

Add to `server/packages/db/models/__init__.py`:

```python
from packages.db.models.learning.topic import LearningCluster, LearningDependency, LearningTopic
```

Add `"LearningCluster"`, `"LearningDependency"`, `"LearningTopic"` to the `__all__` list.

- [ ] **Step 4: Run linter to verify**

Run: `cd server && uv run ruff check packages/db/models/learning/topic.py`
Expected: No errors

- [ ] **Step 5: Commit**

```bash
git add server/packages/db/models/learning/ server/packages/db/models/__init__.py
git commit -m "feat(learning): add global knowledge graph models (topic, dependency, cluster)"
```

---

### Task 2: Learning Progress, Assignment, Session, AssessmentAttempt Models (Per-Family)

**Files:**
- Create: `server/packages/db/models/learning/progress.py`
- Create: `server/packages/db/models/learning/assignment.py`
- Create: `server/packages/db/models/learning/session.py`
- Modify: `server/packages/db/models/__init__.py`

**Interfaces:**
- Produces: `LearningProgress`, `LearningAssignment`, `LearningSession`, `LearningAssessmentAttempt`
- Consumed by: Task 3 (migration), Task 6 (progress service), Task 8 (assignment service)

- [ ] **Step 1: Create progress.py**

```python
# server/packages/db/models/learning/progress.py
"""Per-family learning progress models."""

from datetime import datetime

from sqlalchemy import BigInteger, Float, ForeignKey, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from packages.core.snowflake import next_id
from packages.db.session import Base, UTCDateTime


class LearningProgress(Base):
    __tablename__ = "learning_progress"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, default=next_id)
    child_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id"), nullable=False, index=True)
    topic_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("learning_topics.id"), nullable=False, index=True)
    mastery_level: Mapped[str] = mapped_column(String(20), nullable=False, default="locked", index=True)
    mastery_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    completed_via: Mapped[str | None] = mapped_column(String(20), nullable=True)
    attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    xp_earned: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    last_practice_at: Mapped[datetime | None] = mapped_column(UTCDateTime(), nullable=True)
    first_mastered_at: Mapped[datetime | None] = mapped_column(UTCDateTime(), nullable=True)
    stability: Mapped[float | None] = mapped_column(Float, nullable=True, default=1.0)
    next_review_at: Mapped[datetime | None] = mapped_column(UTCDateTime(), nullable=True)
    ability_dimensions_score_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(UTCDateTime(), server_default=func.now(), onupdate=func.now())

    __table_args__ = (
        UniqueConstraint("child_id", "topic_id", name="uq_learning_progress_child_topic"),
    )

    # JSON accessor
    from packages.db.mixins.json_text import json_text
    ability_dimensions_score: dict | None = json_text("ability_dimensions_score_json")
```

Move the `json_text` import to the top of the file (not inside the class).

- [ ] **Step 2: Create assignment.py**

```python
# server/packages/db/models/learning/assignment.py
from datetime import date, datetime

from sqlalchemy import BigInteger, Date, ForeignKey, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column

from packages.core.snowflake import next_id
from packages.db.session import Base, UTCDateTime


class LearningAssignment(Base):
    __tablename__ = "learning_assignments"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, default=next_id)
    family_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("families.id"), nullable=False, index=True)
    child_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id"), nullable=False, index=True)
    topic_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("learning_topics.id"), nullable=False)
    path_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)  # FK added in Phase 2
    created_by: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id"), nullable=False)
    assignment_type: Mapped[str] = mapped_column(String(20), nullable=False, default="parent_assigned")
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending")
    priority: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    due_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), server_default=func.now())
    completed_at: Mapped[datetime | None] = mapped_column(UTCDateTime(), nullable=True)
```

- [ ] **Step 3: Create session.py**

```python
# server/packages/db/models/learning/session.py
from datetime import datetime

from sqlalchemy import BigInteger, Float, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from packages.core.snowflake import next_id
from packages.db.session import Base, UTCDateTime


class LearningSession(Base):
    __tablename__ = "learning_sessions"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, default=next_id)
    assignment_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("learning_assignments.id"), nullable=True)
    child_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id"), nullable=False, index=True)
    topic_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("learning_topics.id"), nullable=False)
    thread_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    session_type: Mapped[str] = mapped_column(String(20), nullable=False, default="tutorial")
    ai_evaluation_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    score: Mapped[float | None] = mapped_column(Float, nullable=True)
    duration_seconds: Mapped[int | None] = mapped_column(Integer, nullable=True)
    started_at: Mapped[datetime] = mapped_column(UTCDateTime(), server_default=func.now())
    ended_at: Mapped[datetime | None] = mapped_column(UTCDateTime(), nullable=True)

    from packages.db.mixins.json_text import json_text
    ai_evaluation: dict | None = json_text("ai_evaluation_json")


class LearningAssessmentAttempt(Base):
    __tablename__ = "learning_assessment_attempts"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, default=next_id)
    child_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id"), nullable=False, index=True)
    topic_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("learning_topics.id"), nullable=False, index=True)
    session_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("learning_sessions.id"), nullable=True)
    assessment_type: Mapped[str] = mapped_column(String(20), nullable=False)
    score: Mapped[float | None] = mapped_column(Float, nullable=True)
    passed: Mapped[bool] = mapped_column(default=False, nullable=False)
    ai_confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    evidence_results_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    ability_dimensions_delta_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    duration_seconds: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), server_default=func.now())

    from packages.db.mixins.json_text import json_text
    evidence_results: list | None = json_text("evidence_results_json")
    ability_dimensions_delta: dict | None = json_text("ability_dimensions_delta_json")
```

Move `json_text` imports to top of file.

- [ ] **Step 4: Register all new models in __init__.py**

Add to `server/packages/db/models/__init__.py`:

```python
from packages.db.models.learning.progress import LearningProgress
from packages.db.models.learning.assignment import LearningAssignment
from packages.db.models.learning.session import LearningAssessmentAttempt, LearningSession
```

Add `"LearningProgress"`, `"LearningAssignment"`, `"LearningSession"`, `"LearningAssessmentAttempt"` to `__all__`.

- [ ] **Step 5: Verify imports**

Run: `cd server && uv run python -c "from packages.db.models import LearningTopic, LearningProgress, LearningAssignment, LearningSession, LearningAssessmentAttempt, LearningDependency, LearningCluster; print('All 7 models imported OK')"`
Expected: `All 7 models imported OK`

- [ ] **Step 6: Commit**

```bash
git add server/packages/db/models/learning/ server/packages/db/models/__init__.py
git commit -m "feat(learning): add per-family progress models (progress, assignment, session, assessment_attempt)"
```

---

### Task 3: Alembic Migration

**Files:**
- Create: `server/apps/backend/alembic/versions/<auto>_add_learning_os_tables.py`

**Interfaces:**
- Consumes: All 7 model classes from Tasks 1-2
- Produces: Database tables ready for use

- [ ] **Step 1: Generate migration**

Run: `cd server/apps/backend && uv run alembic revision --autogenerate -m "add_learning_os_tables"`

- [ ] **Step 2: Review and fix the generated migration**

The autogenerate should detect all 7 new tables. Verify the migration includes:
- `learning_topics` with all columns + `topic_key` unique index + `subject` index
- `learning_dependencies` with FK to `learning_topics`
- `learning_clusters` with `subject` index
- `learning_progress` with `(child_id, topic_id)` unique constraint
- `learning_assignments` with FK to `families`, `users`, `learning_topics`
- `learning_sessions` with FK to `learning_assignments`, `users`, `learning_topics`
- `learning_assessment_attempts` with FK to `users`, `learning_topics`, `learning_sessions`

Add defensive guards (check if table exists before creating) to match existing pattern.

- [ ] **Step 3: Run migration**

Run: `cd server/apps/backend && uv run alembic upgrade head`
Expected: All 7 tables created

- [ ] **Step 4: Verify tables exist**

Run: `cd server/apps/backend && uv run python -c "from apps.backend.app.database import engine; from sqlalchemy import inspect; tables = inspect(engine).get_table_names(); learning_tables = [t for t in tables if t.startswith('learning_')]; print(f'Found {len(learning_tables)} learning tables:', learning_tables)"`
Expected: `Found 7 learning tables: ['learning_topics', 'learning_dependencies', 'learning_clusters', 'learning_progress', 'learning_assignments', 'learning_sessions', 'learning_assessment_attempts']`

- [ ] **Step 5: Commit**

```bash
git add server/apps/backend/alembic/versions/
git commit -m "feat(learning): alembic migration for 7 learning OS tables"
```

---

### Task 4: Error Codes + Schema Definitions

**Files:**
- Modify: `server/apps/backend/app/errors/codes.py` — add learning error codes
- Modify: `server/apps/backend/app/errors/locales/zh-CN.json` — add Chinese messages
- Modify: `server/apps/backend/app/errors/locales/en-US.json` — add English messages
- Create: `server/apps/backend/app/schemas/learning.py` — all request/response schemas

**Interfaces:**
- Produces: Error codes + Pydantic schemas consumed by Tasks 5-10
- Consumes: Model classes from Tasks 1-2

- [ ] **Step 1: Add error codes**

In `server/apps/backend/app/errors/codes.py`, add to the `ErrorCode` enum:

```python
# Learning OS errors
LEARNING_TOPIC_NOT_FOUND = "learning_topic_not_found"
LEARNING_PROGRESS_NOT_FOUND = "learning_progress_not_found"
LEARNING_ASSIGNMENT_NOT_FOUND = "learning_assignment_not_found"
LEARNING_SESSION_NOT_FOUND = "learning_session_not_found"
LEARNING_TOPIC_LOCKED = "learning_topic_locked"
LEARNING_PREREQUISITE_NOT_MET = "learning_prerequisite_not_met"
LEARNING_ASSESSMENT_NOT_AVAILABLE = "learning_assessment_not_available"
LEARNING_INVALID_STATE_TRANSITION = "learning_invalid_state_transition"
LEARNING_SESSION_ALREADY_ENDED = "learning_session_already_ended"
```

Add corresponding entries in `ERROR_META` dict with appropriate HTTP status codes (404 for NOT_FOUND, 409 for CONFLICT/LOCKED, 403 for NOT_AVAILABLE).

Add locale strings in both `zh-CN.json` and `en-US.json`.

- [ ] **Step 2: Create learning schemas**

```python
# server/apps/backend/app/schemas/learning.py
"""Request/response schemas for Learning OS APIs."""

from __future__ import annotations

from datetime import date, datetime

from pydantic import BaseModel, field_validator

from apps.backend.app.schemas.base import SnowflakeBase


# --- Knowledge Graph (Global) ---

class TopicResponse(SnowflakeBase):
    id: int
    topic_key: str
    topic_type: str
    subject: str
    domain: str | None
    name: str | None
    name_zh: str | None
    description: str
    description_zh: str | None
    age_range_start: int | None
    age_range_end: int | None
    age_group: str
    centrality: float | None
    evidence: list[str] = []
    evidence_zh: list[str] | None
    assessment_prompt: str | None
    assessment_prompt_zh: str | None
    standards: list[str] = []
    ability_dimensions: list[str] | None
    deprecated: bool


class TopicGraphResponse(BaseModel):
    """Local subgraph: prerequisites + dependents of a topic."""
    topic: TopicResponse
    prerequisites: list[TopicResponse]
    dependents: list[TopicResponse]


class ClusterResponse(SnowflakeBase):
    id: int
    subject: str
    domain: str
    age_range_start: int | None
    age_group: str
    summary: str


class SubjectSummary(BaseModel):
    subject: str
    topic_count: int
    mastered_count: int = 0  # filled per-child


# --- Progress (Per-Family) ---

class ProgressResponse(SnowflakeBase):
    id: int
    child_id: int
    topic_id: int
    mastery_level: str
    mastery_score: float | None
    completed_via: str | None
    attempts: int
    xp_earned: int
    last_practice_at: datetime | None
    first_mastered_at: datetime | None
    stability: float | None
    next_review_at: datetime | None
    ability_dimensions_score: dict | None


# --- Assignment ---

class AssignmentCreate(BaseModel):
    child_id: int
    topic_id: int
    assignment_type: str = "parent_assigned"
    priority: int = 0
    due_date: date | None

    @field_validator("assignment_type")
    @classmethod
    def validate_type(cls, v: str) -> str:
        allowed = {"parent_assigned", "ai_recommended", "self_selected"}
        if v not in allowed:
            raise ValueError(f"assignment_type must be one of {allowed}")
        return v


class AssignmentResponse(SnowflakeBase):
    id: int
    family_id: int
    child_id: int
    topic_id: int
    path_id: int | None
    created_by: int
    assignment_type: str
    status: str
    priority: int
    due_date: date | None
    created_at: datetime
    completed_at: datetime | None
    topic: TopicResponse | None = None  # expanded when needed


# --- Session ---

class SessionCreate(BaseModel):
    topic_id: int
    assignment_id: int | None = None
    session_type: str = "tutorial"


class SessionResponse(SnowflakeBase):
    id: int
    assignment_id: int | None
    child_id: int
    topic_id: int
    thread_id: str | None
    session_type: str
    score: float | None
    duration_seconds: int | None
    started_at: datetime
    ended_at: datetime | None


# --- Assessment Attempt ---

class AssessmentAttemptResponse(SnowflakeBase):
    id: int
    child_id: int
    topic_id: int
    session_id: int | None
    assessment_type: str
    score: float | None
    passed: bool
    ai_confidence: float | None
    duration_seconds: int | None
    created_at: datetime


# --- Composite / Dashboard ---

class ChildLearningOverview(SnowflakeBase):
    child_id: int
    child_name: str
    mastered_count: int
    learning_count: int
    available_count: int
    locked_count: int
    review_count: int
    total_study_minutes: int


class ReviewItemResponse(SnowflakeBase):
    """For parent review queue."""
    progress_id: int
    child_id: int
    child_name: str
    topic_id: int
    topic_name: str
    topic_description: str
    evidence: list[str]
    evidence_zh: list[str] | None
    attempts: int
    study_duration_seconds: int
    submitted_at: datetime
```

- [ ] **Step 3: Run linter**

Run: `cd server && uv run ruff check apps/backend/app/schemas/learning.py apps/backend/app/errors/codes.py`
Expected: No errors

- [ ] **Step 4: Commit**

```bash
git add server/apps/backend/app/schemas/learning.py server/apps/backend/app/errors/
git commit -m "feat(learning): add error codes + Pydantic schemas for all learning APIs"
```

---

## Task Group B: Backend Services

### Task 5: Topic Service (Knowledge Graph Queries)

**Files:**
- Create: `server/apps/backend/app/services/learning/__init__.py`
- Create: `server/apps/backend/app/services/learning/topic_service.py`
- Test: `server/tests/backend/test_learning_topic_service.py`

**Interfaces:**
- Consumes: `LearningTopic`, `LearningDependency`, `LearningCluster` models
- Produces: Query functions used by Task 7 (global router)

- [ ] **Step 1: Write failing tests**

```python
# server/tests/backend/test_learning_topic_service.py
import pytest
from sqlalchemy.orm import Session

from packages.db.models.learning.topic import LearningTopic, LearningDependency, LearningCluster
from apps.backend.app.services.learning.topic_service import (
    list_topics,
    get_topic_by_id,
    get_topic_graph,
    list_clusters,
    list_subjects,
)


@pytest.fixture
def sample_topics(db: Session):
    t1 = LearningTopic(topic_key="mt_001", topic_type="CONCEPTUAL", subject="mathematics",
                       domain="Fractions", name="Fraction basics", description="Intro to fractions",
                       age_range_start=8, age_range_end=10, age_group="mid", evidence_json="[]", standards_json="[]")
    t2 = LearningTopic(topic_key="mt_002", topic_type="PROCEDURAL", subject="mathematics",
                       domain="Fractions", name="Fraction addition", description="Adding fractions",
                       age_range_start=9, age_range_end=11, age_group="mid", evidence_json="[]", standards_json="[]")
    db.add_all([t1, t2])
    db.flush()
    dep = LearningDependency(topic_id=t2.id, prerequisite_id=t1.id, strength="hard", reason="Must know basics")
    db.add(dep)
    db.flush()
    return t1, t2


def test_list_topics_by_subject(db: Session, sample_topics):
    results = list_topics(db, subject="mathematics")
    assert len(results) == 2


def test_list_topics_by_age_group(db: Session, sample_topics):
    results = list_topics(db, age_group="mid")
    assert len(results) == 2


def test_get_topic_by_id(db: Session, sample_topics):
    t1, _ = sample_topics
    result = get_topic_by_id(db, t1.id)
    assert result is not None
    assert result.topic_key == "mt_001"


def test_get_topic_graph(db: Session, sample_topics):
    _, t2 = sample_topics
    graph = get_topic_graph(db, t2.id)
    assert len(graph["prerequisites"]) == 1
    assert graph["prerequisites"][0].topic_key == "mt_001"


def test_list_subjects(db: Session, sample_topics):
    subjects = list_subjects(db)
    assert len(subjects) == 1
    assert subjects[0]["subject"] == "mathematics"
    assert subjects[0]["topic_count"] == 2
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd server && uv run pytest tests/backend/test_learning_topic_service.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'apps.backend.app.services.learning'`

- [ ] **Step 3: Implement topic_service.py**

```python
# server/apps/backend/app/services/learning/__init__.py
# empty

# server/apps/backend/app/services/learning/topic_service.py
from sqlalchemy import func as sa_func
from sqlalchemy.orm import Session

from packages.db.models.learning.topic import LearningCluster, LearningDependency, LearningTopic


def list_topics(
    db: Session,
    subject: str | None = None,
    domain: str | None = None,
    age_group: str | None = None,
    deprecated: bool = False,
) -> list[LearningTopic]:
    q = db.query(LearningTopic).filter(LearningTopic.deprecated == deprecated)
    if subject:
        q = q.filter(LearningTopic.subject == subject)
    if domain:
        q = q.filter(LearningTopic.domain == domain)
    if age_group:
        q = q.filter(LearningTopic.age_group == age_group)
    return q.order_by(LearningTopic.subject, LearningTopic.domain, LearningTopic.centrality.desc().nullslast()).all()


def get_topic_by_id(db: Session, topic_id: int) -> LearningTopic | None:
    return db.query(LearningTopic).filter(LearningTopic.id == topic_id).first()


def get_topic_graph(db: Session, topic_id: int) -> dict:
    topic = get_topic_by_id(db, topic_id)
    if not topic:
        return None
    prereq_ids = db.query(LearningDependency.prerequisite_id).filter(
        LearningDependency.topic_id == topic_id
    ).all()
    dep_ids = db.query(LearningDependency.topic_id).filter(
        LearningDependency.prerequisite_id == topic_id
    ).all()
    prerequisites = [db.query(LearningTopic).get(pid[0]) for pid in prereq_ids] if prereq_ids else []
    dependents = [db.query(LearningTopic).get(did[0]) for did in dep_ids] if dep_ids else []
    return {"topic": topic, "prerequisites": prerequisites, "dependents": dependents}


def list_clusters(db: Session, subject: str | None = None) -> list[LearningCluster]:
    q = db.query(LearningCluster)
    if subject:
        q = q.filter(LearningCluster.subject == subject)
    return q.order_by(LearningCluster.subject, LearningCluster.domain).all()


def list_subjects(db: Session) -> list[dict]:
    rows = db.query(
        LearningTopic.subject,
        sa_func.count(LearningTopic.id).label("topic_count"),
    ).filter(
        LearningTopic.deprecated == False
    ).group_by(LearningTopic.subject).order_by(LearningTopic.subject).all()
    return [{"subject": r.subject, "topic_count": r.topic_count} for r in rows]
```

- [ ] **Step 4: Run tests**

Run: `cd server && uv run pytest tests/backend/test_learning_topic_service.py -v`
Expected: All PASS

- [ ] **Step 5: Commit**

```bash
git add server/apps/backend/app/services/learning/ server/tests/backend/test_learning_topic_service.py
git commit -m "feat(learning): topic service with knowledge graph queries + tests"
```

---

### Task 6: Progress Service (State Machine + Spaced Repetition)

**Files:**
- Create: `server/apps/backend/app/services/learning/progress_service.py`
- Test: `server/tests/backend/test_learning_progress_service.py`

**Interfaces:**
- Consumes: `LearningProgress`, `LearningTopic`, `LearningDependency`, `LearningAssessmentAttempt`
- Produces: State machine functions used by Tasks 8, 9, 10 (routers)

- [ ] **Step 1: Write failing tests**

```python
# server/tests/backend/test_learning_progress_service.py
import pytest
from datetime import datetime, timedelta, timezone
from sqlalchemy.orm import Session

from packages.db.models.learning.topic import LearningTopic
from packages.db.models.learning.progress import LearningProgress
from packages.db.models.learning.assignment import LearningAssignment
from apps.backend.app.services.learning.progress_service import (
    get_or_create_progress,
    get_child_progress_overview,
    can_start_learning,
    transition_to_learning,
    transition_to_mastered,
    compute_next_review,
    update_stability,
)


@pytest.fixture
def topic(db: Session):
    t = LearningTopic(topic_key="mt_test", topic_type="CONCEPTUAL", subject="mathematics",
                      domain="Test", name="Test topic", description="Test",
                      age_group="mid", evidence_json="[]", standards_json="[]")
    db.add(t)
    db.flush()
    return t


@pytest.fixture
def child_user(client, auth_headers):
    resp = client.post("/api/v1/family/children", headers=auth_headers, json={
        "username": "learnchild", "password": "ChildPass1",
        "display_name": "Learner", "avatar_emojis": ["🐱"]
    })
    return resp.json()["data"]


def test_get_or_create_progress_creates_locked(db, child_user, topic):
    p = get_or_create_progress(db, child_user["id"], topic.id)
    assert p.mastery_level == "locked"


def test_transition_to_learning(db, child_user, topic):
    p = get_or_create_progress(db, child_user["id"], topic.id)
    # Manually unlock (no prereqs)
    p.mastery_level = "available"
    db.flush()
    result = transition_to_learning(db, p)
    assert result.mastery_level == "learning"


def test_compute_next_review_first_time():
    p = LearningProgress(stability=1.0)
    dt = compute_next_review(p)
    assert dt > datetime.now(timezone.utc)
    assert (dt - datetime.now(timezone.utc)).days == 3


def test_update_stability_increases_on_high_score():
    p = LearningProgress(stability=1.0)
    new_s = update_stability(p, 0.9)
    assert new_s == 1.3


def test_update_stability_decreases_on_low_score():
    p = LearningProgress(stability=2.0)
    new_s = update_stability(p, 0.5)
    assert new_s == 1.2  # 2.0 * 0.6


def test_update_stability_floor():
    p = LearningProgress(stability=1.0)
    new_s = update_stability(p, 0.3)
    assert new_s == 1.0  # floor at 1.0
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd server && uv run pytest tests/backend/test_learning_progress_service.py -v`
Expected: FAIL — module not found

- [ ] **Step 3: Implement progress_service.py**

Key functions to implement:

```python
# server/apps/backend/app/services/learning/progress_service.py
from datetime import datetime, timedelta, timezone
from sqlalchemy import text as sa_text
from sqlalchemy.orm import Session

from packages.db.models.learning.progress import LearningProgress
from packages.db.models.learning.topic import LearningDependency, LearningTopic
from apps.backend.app.errors import AppError, ErrorCode


VALID_TRANSITIONS = {
    "locked": {"available"},
    "available": {"learning"},
    "learning": {"assessing", "parent_review"},
    "assessing": {"mastered", "review"},
    "parent_review": {"mastered", "learning"},
    "mastered": {"review", "learning"},
    "review": {"learning"},
}


def get_or_create_progress(db: Session, child_id: int, topic_id: int) -> LearningProgress:
    p = db.query(LearningProgress).filter_by(child_id=child_id, topic_id=topic_id).first()
    if p:
        return p
    # Check prerequisites to determine initial state
    hard_prereqs = db.query(LearningDependency).filter_by(topic_id=topic_id, strength="hard").all()
    all_met = all(
        db.query(LearningProgress).filter_by(child_id=child_id, topic_id=hp.prerequisite_id, mastery_level="mastered").first()
        for hp in hard_prereqs
    ) if hard_prereqs else True
    initial_level = "available" if all_met else "locked"
    p = LearningProgress(child_id=child_id, topic_id=topic_id, mastery_level=initial_level)
    db.add(p)
    db.flush()
    return p


def transition_to_learning(db: Session, progress: LearningProgress) -> LearningProgress:
    _validate_transition(progress.mastery_level, "learning")
    progress.mastery_level = "learning"
    progress.last_practice_at = datetime.now(timezone.utc)
    db.flush()
    return progress


def transition_to_mastered(
    db: Session, progress: LearningProgress, score: float, completed_via: str,
) -> LearningProgress:
    _validate_transition(progress.mastery_level, "mastered")
    now = datetime.now(timezone.utc)
    progress.mastery_level = "mastered"
    progress.mastery_score = score
    progress.completed_via = completed_via
    if not progress.first_mastered_at:
        progress.first_mastered_at = now
    progress.stability = update_stability(progress, score)
    progress.next_review_at = compute_next_review(progress)
    db.flush()
    return progress


def compute_next_review(progress: LearningProgress) -> datetime:
    stability = progress.stability or 1.0
    interval_days = max(1, int(3 * stability))
    return datetime.now(timezone.utc) + timedelta(days=interval_days)


def update_stability(progress: LearningProgress, score: float) -> float:
    current = progress.stability or 1.0
    if score >= 0.8:
        return min(current * 1.3, 10.0)
    else:
        return max(current * 0.6, 1.0)


def _validate_transition(from_level: str, to_level: str):
    if to_level not in VALID_TRANSITIONS.get(from_level, set()):
        raise AppError(ErrorCode.LEARNING_INVALID_STATE_TRANSITION)


def get_child_progress_overview(db: Session, child_id: int) -> dict:
    rows = db.query(LearningProgress.mastery_level, db.query.func.count(LearningProgress.id)).filter_by(
        child_id=child_id
    ).group_by(LearningProgress.mastery_level).all()
    counts = {r[0]: r[1] for r in rows}
    return {
        "mastered": counts.get("mastered", 0),
        "learning": counts.get("learning", 0),
        "available": counts.get("available", 0),
        "locked": counts.get("locked", 0),
        "review": counts.get("review", 0),
    }
```

Fill in remaining functions with full implementations. The `can_start_learning` function checks that the topic is in `available` or `learning` state.

- [ ] **Step 4: Run tests**

Run: `cd server && uv run pytest tests/backend/test_learning_progress_service.py -v`
Expected: All PASS

- [ ] **Step 5: Commit**

```bash
git add server/apps/backend/app/services/learning/progress_service.py server/tests/backend/test_learning_progress_service.py
git commit -m "feat(learning): progress service with state machine + spaced repetition + tests"
```

---

### Task 7: Global Learning Router

**Files:**
- Create: `server/apps/backend/app/routers/learning.py`
- Modify: `server/apps/backend/app/main.py` — register router

**Interfaces:**
- Consumes: topic_service from Task 5
- Produces: `/api/v1/learning/*` endpoints

- [ ] **Step 1: Create router**

```python
# server/apps/backend/app/routers/learning.py
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from apps.backend.app.database import get_db
from apps.backend.app.schemas.learning import (
    ClusterResponse, SubjectSummary, TopicGraphResponse, TopicResponse,
)
from apps.backend.app.services.learning import topic_service

router = APIRouter(prefix="/learning", tags=["learning"])


@router.get("/topics", response_model=list[TopicResponse])
def list_topics(
    subject: str | None = None,
    domain: str | None = None,
    age_group: str | None = None,
    db: Session = Depends(get_db),
):
    return topic_service.list_topics(db, subject=subject, domain=domain, age_group=age_group)


@router.get("/topics/{topic_id}", response_model=TopicResponse)
def get_topic(topic_id: int, db: Session = Depends(get_db)):
    topic = topic_service.get_topic_by_id(db, topic_id)
    if not topic:
        from apps.backend.app.errors import AppError, ErrorCode
        raise AppError(ErrorCode.LEARNING_TOPIC_NOT_FOUND)
    return topic


@router.get("/topics/{topic_id}/graph", response_model=TopicGraphResponse)
def get_topic_graph(topic_id: int, db: Session = Depends(get_db)):
    graph = topic_service.get_topic_graph(db, topic_id)
    if not graph:
        from apps.backend.app.errors import AppError, ErrorCode
        raise AppError(ErrorCode.LEARNING_TOPIC_NOT_FOUND)
    return graph


@router.get("/clusters", response_model=list[ClusterResponse])
def list_clusters(subject: str | None = None, db: Session = Depends(get_db)):
    return topic_service.list_clusters(db, subject=subject)


@router.get("/subjects", response_model=list[SubjectSummary])
def list_subjects(db: Session = Depends(get_db)):
    return topic_service.list_subjects(db)
```

- [ ] **Step 2: Register in main.py**

Add to `server/apps/backend/app/main.py` with other router imports:

```python
from apps.backend.app.routers import learning as learning_router
# ...
app.include_router(learning_router.router, prefix="/api/v1")
```

- [ ] **Step 3: Test endpoints manually or add integration test**

Run: `cd server && uv run pytest tests/backend/test_learning_topic_service.py -v`
Expected: Still passes (service tests unchanged)

- [ ] **Step 4: Commit**

```bash
git add server/apps/backend/app/routers/learning.py server/apps/backend/app/main.py
git commit -m "feat(learning): global knowledge graph API router"
```

---

### Task 8: Assignment + Session Service

**Files:**
- Create: `server/apps/backend/app/services/learning/assignment_service.py`
- Create: `server/apps/backend/app/services/learning/session_service.py`
- Test: `server/tests/backend/test_learning_assignment_service.py`

**Interfaces:**
- Consumes: progress_service, models
- Produces: Service functions for Tasks 9-10 (family + child routers)

- [ ] **Step 1: Write tests for assignment CRUD**

Cover: create assignment, list assignments by child, submit for review.

- [ ] **Step 2: Implement assignment_service.py**

Key functions:
- `create_assignment(db, user, req) -> LearningAssignment` — validates topic exists, creates assignment + progress record
- `list_assignments(db, child_id, status) -> list[LearningAssignment]`
- `submit_for_review(db, assignment_id, child_id) -> LearningProgress` — transitions to `parent_review`
- `get_review_queue(db, family_id) -> list[ReviewItemResponse]` — all `parent_review` progress for family

- [ ] **Step 3: Write tests for session lifecycle**

Cover: create session, end session.

- [ ] **Step 4: Implement session_service.py**

Key functions:
- `create_session(db, child_id, req) -> LearningSession` — creates session record
- `end_session(db, session_id, score, ai_evaluation) -> LearningSession` — updates score, ended_at
- `start_assessment(db, session_id, child_id) -> LearningProgress` — transitions `learning → assessing`

- [ ] **Step 5: Run tests**

Run: `cd server && uv run pytest tests/backend/test_learning_assignment_service.py -v`
Expected: All PASS

- [ ] **Step 6: Commit**

```bash
git add server/apps/backend/app/services/learning/assignment_service.py server/apps/backend/app/services/learning/session_service.py server/tests/backend/test_learning_assignment_service.py
git commit -m "feat(learning): assignment + session services with tests"
```

---

### Task 9: Family Router (Parent Endpoints)

**Files:**
- Create: `server/apps/backend/app/routers/learning_family.py`
- Modify: `server/apps/backend/app/main.py`

- [ ] **Step 1: Create router with all parent endpoints**

Endpoints:
- `GET /family/learning/children` — list children + learning overview
- `GET /family/learning/children/{child_id}/map` — child's knowledge map with mastery levels
- `GET /family/learning/children/{child_id}/progress` — progress details
- `POST /family/learning/assignments` — create assignment (`require_adult`)
- `GET /family/learning/assignments` — list assignments
- `GET /family/learning/reviews` — review queue
- `POST /family/learning/reviews/{id}/approve` — approve mastery (atomic CAS pattern)
- `POST /family/learning/reviews/{id}/reject` — reject, return to learning

Follow exact pattern from `routers/chores.py`: thin pass-through, `require_adult` auth, atomic CAS for approve.

- [ ] **Step 2: Register in main.py**

- [ ] **Step 3: Commit**

```bash
git add server/apps/backend/app/routers/learning_family.py server/apps/backend/app/main.py
git commit -m "feat(learning): family (parent) learning router with review approve/reject"
```

---

### Task 10: Child Router (Child Endpoints)

**Files:**
- Create: `server/apps/backend/app/routers/learning_child.py`
- Modify: `server/apps/backend/app/main.py`

- [ ] **Step 1: Create router with all child endpoints**

Endpoints:
- `GET /child/learning/map` — child's knowledge map
- `GET /child/learning/assignments` — my assignments
- `GET /child/learning/topics/{id}` — topic detail with my progress
- `POST /child/learning/sessions` — create learning session
- `GET /child/learning/sessions/{id}` — get session
- `POST /child/learning/sessions/{id}/start-assessment` — `learning → assessing`
- `POST /child/learning/assignments/{id}/submit` — submit for parent review
- `GET /child/learning/progress` — overall progress overview

Use `get_current_child_user` auth.

- [ ] **Step 2: Register in main.py**

- [ ] **Step 3: Commit**

```bash
git add server/apps/backend/app/routers/learning_child.py server/apps/backend/app/main.py
git commit -m "feat(learning): child learning router with session + assessment endpoints"
```

---

## Task Group C: AI Integration

### Task 11: Learning Tutor Skill + MCP Tools

**Files:**
- Create: `server/apps/agent/skills/builtin/public/learning-tutor/SKILL.md`
- Create: `server/apps/backend/app/services/learning/mcp_tools.py` (or register in existing MCP tool registry)

- [ ] **Step 1: Create SKILL.md**

Follow the exact spec from Section 5.1 of the design doc. Include YAML frontmatter with `name`, `description`, `trigger_phrases`, `allowed-tools`, `thinking`, `max_tokens`. Body includes Role, Behavior, Output Format, Tone sections.

- [ ] **Step 2: Register skill in RESERVED_NAMES**

Check `server/apps/agent/` for the skill registration mechanism. Add `"learning-tutor"` to the appropriate registry.

- [ ] **Step 3: Implement MCP tools**

Three tools:
- `get_learning_topic(topic_id, child_id)` — returns topic detail + child's mastery
- `get_child_learning_profile(child_id, subject)` — returns progress stats
- `record_learning_result(session_id, evaluation)` — updates progress, creates attempt, triggers coin reward

Follow existing MCP tool registration pattern in the agent app.

- [ ] **Step 4: Verify skill loads**

- [ ] **Step 5: Commit**

```bash
git add server/apps/agent/skills/builtin/public/learning-tutor/
git commit -m "feat(learning): add learning-tutor AI skill + MCP tools"
```

---

## Task Group D: Seed Data

### Task 12: Translation Service

**Files:**
- Create: `server/apps/backend/app/services/learning/translation.py`

- [ ] **Step 1: Implement LLM-assisted translation**

Function `translate_topic(topic_dict) -> dict` that calls DashScope/OpenAI to translate name, description, evidence, assessment_prompt to Chinese. Preserve technical terms in English.

- [ ] **Step 2: Implement `derive_ability_dimensions(topic_dict) -> list[str]`**

LLM-based derivation of ability dimensions from topic metadata.

- [ ] **Step 3: Commit**

---

### Task 13: Seed Script

**Files:**
- Create: `server/scripts/seed_learning_topics.py`

- [ ] **Step 1: Implement seed script**

Follow the pseudocode from spec Section 8.1. Key steps:
1. Load `os-taxonomy/data/topics.json` (1,590 topics)
2. Batch translate via LLM (50 per batch, rate limit protection)
3. Derive ability dimensions via LLM
4. Upsert `LearningTopic` records
5. Load + insert `LearningDependency` (3,221 edges)
6. Load + insert `LearningCluster` (183 clusters)

- [ ] **Step 2: Add quality validation (spec Section 8.2)**

- Orphan edge detection
- Age range spot check

- [ ] **Step 3: Add version tracking**

Record os-taxonomy version (commit hash or tag). Implement `reseed_learning_topics --version <tag>`.

- [ ] **Step 4: Run seed**

- [ ] **Step 5: Commit**

---

### Task 14: Gamification — Coin Reward + Badge Definitions

**Files:**
- Modify: `server/apps/backend/app/services/learning/progress_service.py` — add coin reward on mastery
- Create: `server/scripts/seed_learning_badges.py`

- [ ] **Step 1: Add coin reward logic**

In `transition_to_mastered`, after DB flush, create `CoinTransaction(type="learning_earn", ref_id=attempt_id)`. Follow chore approval pattern.

- [ ] **Step 2: Extend CoinTransaction.ref_type property**

Add `"learning_earn" -> "learning_assessment_attempt"` mapping.

- [ ] **Step 3: Create badge seed script**

Create all 30 badge definitions from spec Section 7.2 (9 subjects × 3 levels + 3 comprehensive). The 9th subject is `learning_to_learn` (学习力), added during implementation as a meaningful pedagogical category.

- [ ] **Step 4: Run seed**

- [ ] **Step 5: Commit**

```bash
git commit -m "feat(learning): coin rewards + badge definitions seed"
```

---

## Task Group E: Frontend — Child App

### Task 15: Child App API Layer + Types

**Files:**
- Create: `frontend/apps/child/src/api/learning.ts`

- [ ] **Step 1: Define TypeScript interfaces**

Match all response schemas from Task 4. IDs as `string`.

- [ ] **Step 2: Implement API functions**

```typescript
import http from './index'
// ... interfaces ...

export async function getMyLearningMap(): Promise<ProgressWithTopic[]> { ... }
export async function getMyAssignments(): Promise<AssignmentResponse[]> { ... }
export async function getTopicDetail(topicId: string): Promise<TopicWithProgress> { ... }
export async function createSession(req: SessionCreate): Promise<SessionResponse> { ... }
export async function startAssessment(sessionId: string): Promise<ProgressResponse> { ... }
export async function submitAssignment(assignmentId: string): Promise<ProgressResponse> { ... }
export async function getMyProgress(): Promise<ChildLearningOverview> { ... }
```

- [ ] **Step 3: Commit**

---

### Task 16: LearningMapPage (Child App)

**Files:**
- Create: `frontend/apps/child/src/pages/learning/LearningMapPage.vue`
- Create: `frontend/apps/child/src/components/learning/SubjectTabs.vue`
- Create: `frontend/apps/child/src/components/learning/TopicGrid.vue`
- Modify: `frontend/apps/child/src/router/index.ts` — add route
- Modify: `frontend/apps/child/src/pages/ChildHomePage.vue` — add "today learning" card

- [ ] **Step 1: Create route**

Add `/learning` route pointing to `LearningMapPage.vue`.

- [ ] **Step 2: Create SubjectTabs component**

Horizontal scrolling tabs. Hide subjects with no available/learning/mastered topics. Show count badge.

- [ ] **Step 3: Create TopicGrid component**

Domain-grouped grid of topic cards. Status icons: ✅available 🔵learning ⭐mastered 🔒locked 🟡review.

- [ ] **Step 4: Create LearningMapPage**

Wire SubjectTabs + TopicGrid + "today recommendation" card. Add empty state, skeleton loading, error state.

- [ ] **Step 5: Add "today learning" card to ChildHomePage**

- [ ] **Step 6: Add i18n strings**

Add all learning-related keys to `zh-CN.ts` and `en-US.ts`.

- [ ] **Step 7: Commit**

---

### Task 17: LearningTopicPage + LearningSessionPage (Child App)

**Files:**
- Create: `frontend/apps/child/src/pages/learning/LearningTopicPage.vue`
- Create: `frontend/apps/child/src/pages/learning/LearningSessionPage.vue`
- Modify: `frontend/apps/child/src/router/index.ts`

- [ ] **Step 1: Create LearningTopicPage**

Show topic detail, prerequisites, mastery progress bar, [开始学习] and [提交审核] buttons.

- [ ] **Step 2: Create LearningSessionPage — AI chat integration**

**Key work item:** Adapt/extract `useThreadChat` from main app for child app use. This composable manages DeerFlow SSE streaming.

Two approaches:
1. **Extract to shared package** (`@numina/ai-chat`) — preferred for reuse
2. **Copy to child app** — simpler but duplicates code

For Phase 1, create a simplified version in child app that handles:
- SSE connection to DeerFlow thread
- Message rendering (text bubbles)
- Tutorial→assessment mode transition UI (blue→orange header)
- Result display

- [ ] **Step 3: Add routes**

`/learning/topic/:id` and `/learning/session/:id`.

- [ ] **Step 4: Commit**

---

### Task 18: LearningProgressPage (Child App)

**Files:**
- Create: `frontend/apps/child/src/pages/learning/LearningProgressPage.vue`

- [ ] **Step 1: Create page**

Show overall stats: mastered/learning/available counts, recent activity, streak.

- [ ] **Step 2: Add route**

`/learning/progress`.

- [ ] **Step 3: Commit**

---

## Task Group F: Frontend — Main App (Parent)

### Task 19: Main App API Layer + BabyLearningPage

**Files:**
- Create: `frontend/apps/main/src/api/learning.ts`
- Create: `frontend/apps/main/src/pages/BabyLearningPage.vue`
- Modify: `frontend/apps/main/src/router/index.ts`

- [ ] **Step 1: Create parent API layer**

Functions: `getLearningChildren`, `getChildMap`, `getChildProgress`, `createAssignment`, `getAssignments`, `getReviews`, `approveReview`, `rejectReview`.

- [ ] **Step 2: Create BabyLearningPage**

Show all children with learning stats + pending review queue. Follow BabyPage.vue pattern.

- [ ] **Step 3: Add route + navigation entry**

- [ ] **Step 4: Add i18n strings**

- [ ] **Step 5: Commit**

---

### Task 20: ChildLearningMapPage + LearningAssignPage + LearningReviewsPage (Main App)

**Files:**
- Create: `frontend/apps/main/src/pages/ChildLearningMapPage.vue`
- Create: `frontend/apps/main/src/pages/LearningAssignPage.vue`
- Create: `frontend/apps/main/src/pages/LearningReviewsPage.vue`

- [ ] **Step 1: Create ChildLearningMapPage**

Parent view of child's knowledge map. Shows mastery levels per topic.

- [ ] **Step 2: Create LearningAssignPage**

Form to assign a topic to a child. Topic search/selection, due date, priority.

- [ ] **Step 3: Create LearningReviewsPage**

Review queue with evidence details, reference questions, anti-rubber-stamp UI (collapsed approve button).

- [ ] **Step 4: Add routes**

- [ ] **Step 5: Commit**

---

## Task Group G: Integration + Polish

### Task 21: Notifications

**Files:**
- Modify: `server/apps/backend/app/services/learning/` — add notification triggers
- Modify: notification event registry (if exists)

- [ ] **Step 1: Add notification events**

Events: `learning_assignment_created`, `learning_submitted_for_review`, `learning_approved`, `learning_rejected`, `learning_streak_3_failures`.

- [ ] **Step 2: Wire into service functions**

After each state transition, fire appropriate notification.

- [ ] **Step 3: Commit**

---

### Task 22: Integration Test + E2E Smoke

**Files:**
- Create: `server/tests/backend/test_learning_integration.py`

- [ ] **Step 1: Write end-to-end flow test**

Test the complete happy path:
1. Parent creates assignment
2. Child sees assignment
3. Child creates session
4. Child submits for review
5. Parent approves
6. Verify: mastery_level = "mastered", coin transaction created, progress updated

- [ ] **Step 2: Run all backend tests**

Run: `cd server && uv run pytest tests/backend/ -v -k learning`
Expected: All pass

- [ ] **Step 3: Run linter + typecheck**

Run: `cd server && uv run ruff check apps/backend/app/routers/learning*.py apps/backend/app/services/learning/ apps/backend/app/schemas/learning.py`
Run: `cd server && uv run mypy apps/backend/app/services/learning/`
Expected: No errors

- [ ] **Step 4: Commit**

```bash
git commit -m "test(learning): integration test for full learning flow"
```

---

## Summary: Task Dependency Graph

```
Task 1 (topic models) ─┐
Task 2 (progress models)─┤
                          ├→ Task 3 (migration) → Task 13 (seed) → Task 14 (gamification)
Task 4 (schemas+errors) ─┤
                          ├→ Task 5 (topic service) → Task 7 (global router)
                          ├→ Task 6 (progress service) → Task 8 (assignment/session service)
                          │                              → Task 9 (family router)
                          │                              → Task 10 (child router)
                          ├→ Task 11 (AI skill)
                          ├→ Task 12 (translation) → Task 13 (seed)
                          │
Task 15 (child API) ──→ Task 16 (map page) → Task 17 (topic+session pages) → Task 18 (progress page)
Task 19 (parent API+page) → Task 20 (parent detail pages)
Task 21 (notifications) — after Tasks 9-10
Task 22 (integration test) — after all backend tasks
```

**Recommended execution order:**
1. Tasks 1-4 (data layer) — can be parallelized across 2 agents
2. Tasks 5-6 (core services) — after data layer
3. Tasks 7-10 (routers) — after services, can parallelize family + child
4. Tasks 11-12 (AI + translation) — independent, can run parallel with routers
5. Task 13-14 (seed + gamification) — after models
6. Tasks 15-18 (child frontend) — after child API is ready
7. Tasks 19-20 (parent frontend) — after family API is ready
8. Tasks 21-22 (integration) — last
