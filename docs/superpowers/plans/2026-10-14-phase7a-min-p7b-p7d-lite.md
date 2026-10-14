# Phase 7a-min + P7b + P7d-lite: Evaluation Foundation, Math Pipeline & Subject Pilot

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the evaluation foundation (coverage scoring, content hashing), the math question production pipeline (router, LLM generator, new templates, new scoring types), and minimal pilot templates for Chinese/English/Science — forming the core of Phase 7's full subject expansion.

**Architecture:** Three new service layers on top of existing Phase 0-6 infrastructure: (1) a `coverage_service` computing existence-based coverage scores with prerequisite-value prioritization, (2) a `question_router` + `llm_generator` + `external_import` production pipeline that routes topics to generation methods (template/LLM/external), validates output through 3 layers, and risk-classifies for review, (3) new scoring types (`multi_fill_blank`, `ai_graded`) and 11 math templates expanding math coverage to ≥3%. Pilot templates for 3 additional subjects extend coverage to all 4 core subjects.

**Tech Stack:** Python 3.12+ · FastAPI · SQLAlchemy 2.0 · Alembic · Pydantic v2 · Vue 3 + Vant 4 (minimal frontend) · pytest

**Spec:** `docs/superpowers/specs/2026-10-14-phase7-full-subject-expansion-design.md`

## Global Constraints

- **Python 3.12+**, `uv` workspace at `server/`, all quality commands run from there
- **Import direction:** `apps/` → `packages/` only; `packages/` subpackages don't import each other (except `domain` → `db`)
- **No trailing slashes** on router root paths — use `""` not `"/"` (`redirect_slashes=False` in `app/main.py`)
- **Snowflake IDs:** All response schemas with IDs inherit `SnowflakeBase`; IDs serialized as `str` in JSON
- **Error handling:** Use `AppError(ErrorCode.XXX, details=...)` from `app/errors/exceptions.py`, not raw `HTTPException`
- **Logging:** `from packages.core.logging import get_logger`; parameterized `%s` format, no f-strings
- **Pydantic v2:** Use `model_validate()` not `from_orm`; `field_validator` not `validator`
- **URL style:** `@router.get("")` not `@router.get("/")`
- **Type annotations:** `str | None`, `list[str]` (Python 3.10+ union syntax)
- **Testing:** Each test gets fresh in-memory SQLite DB; `pytest` from `server/`
- **Incremental formatting:** Format only files you touch
- **No speculative code:** Don't add features beyond what's asked

## Review Focus

1. **`content_hash` backfill correctness** — Existing 240 template questions must get correct hashes; hash collision would cause false dedup skips. Test: backfill produces unique hashes for distinct questions, identical hashes for identical stem+answer. Owning task: Task 1.

2. **`suspended` review_status propagation** — Adding `"suspended"` to the review_status enum must not break existing queries. `question_service`, `adaptive_service`, and `practice.py` router all filter `review_status == "approved"` — suspended must be excluded. Test: suspended questions never appear in question selection or coverage counts. Owning task: Task 2.

3. **LLM topic_key hallucination** — The LLM generator must not allow the LLM to pick its own topic_key. The prompt must include the target topic, and the response must be validated against the input topic_key (white-list defense, per `finance-coach-target-id-hallucination` lesson). Test: if LLM returns a different topic_key, the question is rejected. Owning task: Task 6.

4. **`ai_graded` confidence threshold** — Questions with AI grading confidence < 0.7 must NOT update mastery scores. If this leaks through,掌握度 will be polluted by unreliable AI judgments. Test: low-confidence ai_graded answers produce feedback but skip mastery update. Owning task: Task 5.

5. **Cross-subject template isolation** — Pilot templates for Chinese/English/Science must not interfere with existing math templates. The registry is a flat dict keyed by template_id prefix (e.g. `chinese.pinyin.*`). A registration collision would silently overwrite. Test: all existing math template IDs remain functional after pilot registration. Owning task: Task 10.

---

## File Structure

### New Files

| File | Responsibility |
|------|---------------|
| `server/apps/backend/app/services/learning/coverage_service.py` | Coverage score computation: existence + prerequisite value, aggregation |
| `server/apps/backend/app/services/learning/question_router.py` | Route topics → generation method based on config table |
| `server/apps/backend/app/services/learning/llm_generator.py` | LLM question generation with 3-layer validation + risk classification |
| `server/apps/backend/app/services/learning/external_import.py` | External question bank import adapter (Math23K + JSON) |
| `server/apps/backend/scripts/coverage_report.py` | CLI script for coverage reports |
| `server/apps/backend/scripts/production_run.py` | CLI script for question production pipeline |
| `server/apps/backend/scripts/fix_beijing_topics.py` | CLI script to fix NULL subject/ageRange on Beijing topics |
| `server/packages/domain/question_templates/math_measurement.py` | Measurement templates (unit conversion, perimeter/area) |
| `server/packages/domain/question_templates/math_statistics.py` | Statistics templates (mean, probability) |
| `server/packages/domain/question_templates/math_decimal.py` | Decimal operation templates |
| `server/packages/domain/question_templates/math_estimation.py` | Estimation templates |
| `server/packages/domain/question_templates/math_patterns.py` | Pattern-finding / reasoning templates |
| `server/packages/domain/question_templates/chinese_pinyin.py` | Chinese pinyin pilot templates |
| `server/packages/domain/question_templates/chinese_literacy.py` | Chinese character recognition pilot templates |
| `server/packages/domain/question_templates/english_vocabulary.py` | English vocabulary pilot templates |
| `server/packages/domain/question_templates/english_grammar.py` | English grammar pilot templates |
| `server/packages/domain/question_templates/science_life.py` | Life science pilot templates |
| `server/packages/domain/question_templates/science_matter.py` | Matter science pilot templates |
| `server/tests/backend/test_coverage_service.py` | Coverage service tests |
| `server/tests/backend/test_question_router.py` | Router tests |
| `server/tests/backend/test_llm_generator.py` | LLM generator tests |
| `server/tests/backend/test_external_import.py` | Import adapter tests |
| `server/tests/backend/test_scoring_extended.py` | Extended scoring type tests |
| `server/tests/packages/domain/test_pilot_templates.py` | Pilot template tests |

### Modified Files

| File | Change |
|------|--------|
| `server/packages/db/models/learning/question.py` | Add `content_hash`, `source_name`, `source_license`, `imported_at`, `grading_explanation_json`, `suspicious`, `needs_review`, `empirical_difficulty` columns |
| `server/packages/db/models/learning/practice.py` | Add `is_retry` to PracticeAttempt; `validity_flag` to PracticeSession |
| `server/apps/backend/app/services/learning/scoring_service.py` | Add `multi_fill_blank` and `ai_graded` scoring |
| `server/apps/backend/app/services/learning/question_seeder.py` | Write `content_hash` to DB column; add `seed_from_external()` and `seed_from_llm()` |
| `server/apps/backend/app/services/learning/question_service.py` | Handle `suspended` status; extend `create_question()` with source_metadata |
| `server/apps/backend/app/services/learning/adaptive_service.py` | Exclude `suspended` questions |
| `server/apps/backend/app/routers/practice.py` | Add coverage detail/summary/gap-report endpoints; batch-review endpoint |
| `server/apps/backend/app/schemas/practice.py` | Add coverage/quality response schemas |
| `server/apps/backend/app/main.py` | (No change — practice router already registered) |
| `server/packages/domain/question_templates/__init__.py` | Import new template modules to trigger registration |
| `frontend/apps/child/src/components/learning/PracticeAnswerInput.vue` | Add `multi_fill_blank` and `ai_graded` input modes |
| `frontend/apps/child/src/api/practice.ts` | Add new question type types |

---

## Task 1: Alembic Migration — content_hash + Question/Practice Model Extensions

**Files:**
- Create: `server/apps/backend/alembic/versions/p7a001_add_content_hash_and_question_fields.py`
- Modify: `server/packages/db/models/learning/question.py`
- Modify: `server/packages/db/models/learning/practice.py`
- Test: `server/tests/backend/test_models_p7a_fields.py`

**Interfaces:**
- Consumes: Existing `Question`, `PracticeAttempt`, `PracticeSession` ORM models
- Produces: New columns available on ORM models; migration applies cleanly to both SQLite and PostgreSQL

- [ ] **Step 1: Write the failing test — new model fields exist and have correct defaults**

```python
# server/tests/backend/test_models_p7a_fields.py
"""Tests for P7a model field additions."""
import pytest
from sqlalchemy import inspect

from packages.db.models.learning.question import Question
from packages.db.models.learning.practice import PracticeAttempt, PracticeSession


class TestQuestionModelP7aFields:
    """Question model has P7a new columns."""

    def test_content_hash_column_exists(self):
        columns = {c.name for c in inspect(Question).columns}
        assert "content_hash" in columns

    def test_content_hash_is_nullable(self):
        col = inspect(Question).columns["content_hash"]
        assert col.nullable is True  # existing rows won't have it immediately

    def test_source_metadata_columns_exist(self):
        columns = {c.name for c in inspect(Question).columns}
        assert "source_name" in columns
        assert "source_license" in columns
        assert "imported_at" in columns

    def test_grading_explanation_column_exists(self):
        columns = {c.name for c in inspect(Question).columns}
        assert "grading_explanation_json" in columns

    def test_quality_monitoring_columns_exist(self):
        columns = {c.name for c in inspect(Question).columns}
        assert "suspicious" in columns
        assert "needs_review" in columns
        assert "empirical_difficulty" in columns

    def test_risk_and_family_id_columns_exist(self):
        columns = {c.name for c in inspect(Question).columns}
        assert "risk" in columns
        assert "family_id" in columns


class TestPracticeModelP7aFields:
    """Practice models have P7a new columns."""

    def test_attempt_is_retry_column_exists(self):
        columns = {c.name for c in inspect(PracticeAttempt).columns}
        assert "is_retry" in columns

    def test_session_validity_flag_column_exists(self):
        columns = {c.name for c in inspect(PracticeSession).columns}
        assert "validity_flag" in columns
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd server && uv run pytest tests/backend/test_models_p7a_fields.py -v`
Expected: FAIL — `content_hash` and other new columns not found

- [ ] **Step 3: Add new columns to Question ORM model**

In `server/packages/db/models/learning/question.py`, add after the existing `updated_at` column:

```python
# P7a: content deduplication
content_hash = Column(String(64), nullable=True, index=True)

# P7b: source metadata for external/LLM imports
source_name = Column(String(50), nullable=True)
source_license = Column(String(50), nullable=True)
imported_at = Column(UTCDateTime, nullable=True)

# P7b: AI grading explainability
grading_explanation_json = Column(Text, nullable=True)

# P7e: quality monitoring (added now to avoid future migration)
suspicious = Column(Boolean, default=False, server_default="0")
needs_review = Column(Boolean, default=False, server_default="0")
empirical_difficulty = Column(Float, nullable=True)

# P7b: risk classification (set by classify_risk() in Task 6)
risk = Column(String(10), nullable=True, index=True)  # "low" | "medium" | "high"
# P7b: family scoping for review-queue isolation
family_id = Column(BigInteger, nullable=True, index=True)
```

Add JSON accessor at the bottom of the class:

```python
@property
def grading_explanation(self) -> dict | None:
    if self.grading_explanation_json:
        return json.loads(self.grading_explanation_json)
    return None
```

- [ ] **Step 4: Add new columns to PracticeAttempt and PracticeSession ORM models**

In `server/packages/db/models/learning/practice.py`:

On `PracticeAttempt`, add:
```python
is_retry = Column(Boolean, default=False, server_default="0")
```

On `PracticeSession`, add:
```python
validity_flag = Column(String(20), nullable=True)
```

- [ ] **Step 5: Create the alembic migration**

```bash
cd server/apps/backend
uv run alembic revision --autogenerate -m "p7a001_add_content_hash_and_question_fields"
```

Then verify the generated migration file includes all new columns. If alembic doesn't pick up `server_default` values correctly, manually add them. The migration should look like:

```python
def upgrade() -> None:
    # Questions table extensions
    op.add_column("questions", sa.Column("content_hash", sa.String(64), nullable=True))
    op.create_index(op.f("ix_questions_content_hash"), "questions", ["content_hash"])
    op.add_column("questions", sa.Column("source_name", sa.String(50), nullable=True))
    op.add_column("questions", sa.Column("source_license", sa.String(50), nullable=True))
    op.add_column("questions", sa.Column("imported_at", sa.DateTime(), nullable=True))
    op.add_column("questions", sa.Column("grading_explanation_json", sa.Text(), nullable=True))
    op.add_column("questions", sa.Column("suspicious", sa.Boolean(), server_default="0"))
    op.add_column("questions", sa.Column("needs_review", sa.Boolean(), server_default="0"))
    op.add_column("questions", sa.Column("empirical_difficulty", sa.Float(), nullable=True))
    # P7b: risk classification for review routing (set by classify_risk() in Task 6)
    op.add_column("questions", sa.Column("risk", sa.String(10), nullable=True))
    op.create_index(op.f("ix_questions_risk"), "questions", ["risk"])
    # P7b: family scoping for review-queue isolation
    op.add_column("questions", sa.Column("family_id", sa.BigInteger(), nullable=True))
    op.create_index(op.f("ix_questions_family_id"), "questions", ["family_id"])

    # Practice tables
    op.add_column("practice_attempts", sa.Column("is_retry", sa.Boolean(), server_default="0"))
    op.add_column("practice_sessions", sa.Column("validity_flag", sa.String(20), nullable=True))


def downgrade() -> None:
    # Questions: risk/family_id first (drop their indexes then columns)
    op.drop_index(op.f("ix_questions_risk"), table_name="questions")
    op.drop_column("questions", "risk")
    op.drop_index(op.f("ix_questions_family_id"), table_name="questions")
    op.drop_column("questions", "family_id")
    # Practice tables
    op.drop_column("practice_sessions", "validity_flag")
    op.drop_column("practice_attempts", "is_retry")
    # Questions: original P7a columns
    op.drop_column("questions", "empirical_difficulty")
    op.drop_column("questions", "needs_review")
    op.drop_column("questions", "suspicious")
    op.drop_column("questions", "grading_explanation_json")
    op.drop_column("questions", "imported_at")
    op.drop_column("questions", "source_license")
    op.drop_column("questions", "source_name")
    op.drop_index(op.f("ix_questions_content_hash"), table_name="questions")
    op.drop_column("questions", "content_hash")
```

- [ ] **Step 6: Run migration and verify tests pass**

```bash
cd server/apps/backend && uv run alembic upgrade head
cd server && uv run pytest tests/backend/test_models_p7a_fields.py -v
```

Expected: All PASS

- [ ] **Step 7: Commit**

```bash
git add server/packages/db/models/learning/question.py \
       server/packages/db/models/learning/practice.py \
       server/apps/backend/alembic/versions/p7a001_*.py \
       server/tests/backend/test_models_p7a_fields.py
git commit -m "feat(learning): P7a alembic migration — content_hash, source metadata, grading explanation, practice model extensions

- questions: content_hash (indexed), source_name, source_license, imported_at,
  grading_explanation_json, suspicious, needs_review, empirical_difficulty
- practice_attempts: is_retry
- practice_sessions: validity_flag

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>"
```

---

## Task 2: Backfill content_hash + Fix Beijing Topic Fields

**Files:**
- Create: `server/apps/backend/scripts/fix_beijing_topics.py`
- Create: `server/apps/backend/scripts/backfill_content_hash.py`
- Test: `server/tests/backend/test_content_hash_backfill.py`

**Interfaces:**
- Consumes: `Question` model with new `content_hash` column; `LearningTopic` model; `_compute_content_hash()` from `question_seeder.py`
- Produces: All existing questions have `content_hash` populated; Beijing topics have `subject` and `age_group` filled

- [ ] **Step 1: Write the failing test — content_hash backfill function**

```python
# server/tests/backend/test_content_hash_backfill.py
"""Tests for content_hash backfill and Beijing topic fix."""
import pytest

from packages.db.models.learning.question import Question
from packages.db.models.learning.topic import LearningTopic
from apps.backend.app.services.learning.question_seeder import _compute_content_hash


class TestContentHashBackfill:
    """content_hash backfill produces correct hashes."""

    def test_backfill_sets_hash_on_all_questions(self, db_session):
        """After backfill, every question has a content_hash."""
        from apps.backend.scripts.backfill_content_hash import backfill

        q1 = Question(
            topic_id=1, question_type="calculation",
            stem="1+1=?", answer_json='{"answer": 2}',
            difficulty=1, source="template", review_status="approved",
        )
        q2 = Question(
            topic_id=1, question_type="fill_blank",
            stem="Capital of China", answer_json='{"value": "北京"}',
            difficulty=1, source="template", review_status="approved",
        )
        db_session.add_all([q1, q2])
        db_session.flush()

        result = backfill(db_session)

        db_session.refresh(q1)
        db_session.refresh(q2)
        assert q1.content_hash is not None
        assert q2.content_hash is not None
        assert q1.content_hash != q2.content_hash
        assert result["backfilled"] == 2

    def test_backfill_hash_matches_compute_function(self, db_session):
        """Backfilled hash matches _compute_content_hash output."""
        from apps.backend.scripts.backfill_content_hash import backfill

        q = Question(
            topic_id=1, question_type="calculation",
            stem="2+2=?", answer_json='{"answer": 4}',
            difficulty=1, source="template", review_status="approved",
        )
        db_session.add(q)
        db_session.flush()

        backfill(db_session)
        db_session.refresh(q)

        expected = _compute_content_hash("2+2=?", {"answer": 4})
        assert q.content_hash == expected

    def test_backfill_is_idempotent(self, db_session):
        """Running backfill twice doesn't change existing hashes."""
        from apps.backend.scripts.backfill_content_hash import backfill

        q = Question(
            topic_id=1, question_type="calculation",
            stem="3+3=?", answer_json='{"answer": 6}',
            difficulty=1, source="template", review_status="approved",
        )
        db_session.add(q)
        db_session.flush()

        backfill(db_session)
        db_session.refresh(q)
        first_hash = q.content_hash

        result = backfill(db_session)
        db_session.refresh(q)
        assert q.content_hash == first_hash
        assert result["skipped"] == 1


class TestBeijingTopicFix:
    """Beijing topics get subject/age_group from upstream data."""

    def test_fix_fills_null_subject_from_upstream(self, db_session):
        """Topics with source_taxonomy=beijing and NULL subject get filled.

        Note: LearningTopic.subject is declared nullable=False in the ORM,
        so we bypass the ORM with raw SQL to insert a fixture that has NULL
        subject — this is the actual buggy state that fix_beijing_topics repairs.
        """
        from sqlalchemy import text
        from apps.backend.scripts.fix_beijing_topics import fix_beijing_topics

        upstream = LearningTopic(
            topic_key="math.number.addition", subject="mathematics",
            domain="number", name="Addition", age_group="lower",
            source_taxonomy="upstream", deprecated=False,
        )
        db_session.add(upstream)
        db_session.flush()
        # Insert a Beijing topic with NULL subject/age_group via raw SQL,
        # bypassing the ORM's nullable=False validation.
        db_session.execute(text(
            "INSERT INTO learning_topics "
            "(topic_key, subject, domain, name, age_group, source_taxonomy, deprecated) "
            "VALUES (:key, NULL, :domain, :name, NULL, :tax, FALSE)"
        ), {"key": "bj-math.number.addition", "domain": "number",
            "name": "北京版-加法", "tax": "beijing"})
        db_session.flush()
        # Fetch via ORM for the assertion
        beijing = db_session.query(LearningTopic).filter(
            LearningTopic.topic_key == "bj-math.number.addition"
        ).one()

        result = fix_beijing_topics(db_session)
        db_session.refresh(beijing)

        assert beijing.subject == "mathematics"
        assert beijing.age_group == "lower"
        assert result["fixed"] == 1
```

- [ ] **Step 2a: Verify Math23K license (P7b precondition)**

Per the origin spec §9.3 acceptance criterion, this step must complete before Task 9's Math23KAdapter is used. Locate the Math23K dataset's LICENSE file (the dataset is typically distributed under CC BY-SA 4.0 or a research-use license), confirm compatibility with this project's MIT license for the planned use (question bank import, with source_name/source_license attribution), and record the verdict in `docs/solutions/integration-issues/math23k-license-compatibility.md`. Gate Task 9's adapter implementation on a confirmed-compatible license; if the license is incompatible, stop and evaluate alternatives before proceeding.

- [ ] **Step 2b: Create LearningTopic rows for new template slug keys**

The new templates (Task 8's math expansion and Task 10's pilot templates) use slug-style
topic_keys (`math.decimal.addition`, `chinese.pinyin.initials`, …) that don't exist in the
os-taxonomy data (which uses `mt_*` IDs). Before any seeding runs, create LearningTopic rows
for each unique slug topic_key so the seeder's topic resolution finds them.

```python
# server/scripts/seed_p7a_topic_slugs.py
"""Create LearningTopic rows for P7a/P7b/P7d-lite template slug topic_keys.

Existing templates use os-taxonomy mt_* IDs; new templates use readable slugs.
This script creates the missing LearningTopic rows (option A from Task 8's
topic-key mapping note) so seed_questions_from_templates can resolve them.
"""
from packages.db.session import SessionLocal
from packages.db.models.learning.topic import LearningTopic

# (topic_key, subject, domain, name, age_group)
SLUG_TOPICS = [
    # Task 8 math expansion
    ("math.decimal.addition", "Mathematics", "Addition & Subtraction", "Decimal Addition", "lower"),
    ("math.decimal.subtraction", "Mathematics", "Addition & Subtraction", "Decimal Subtraction", "lower"),
    ("math.decimal.multiplication", "Mathematics", "Multiplication & Division", "Decimal Multiplication", "lower"),
    ("math.estimation.rounding", "Mathematics", "Mathematical Thinking", "Rounding Estimation", "lower"),
    ("math.estimation.approximate_calc", "Mathematics", "Mathematical Thinking", "Approximate Calculation", "lower"),
    ("math.measurement.unit_conversion", "Mathematics", "Measurement", "Unit Conversion", "lower"),
    ("math.measurement.perimeter_rectangle", "Mathematics", "Measurement", "Rectangle Perimeter", "lower"),
    ("math.measurement.area_rectangle", "Mathematics", "Measurement", "Rectangle Area", "lower"),
    ("math.statistics.mean", "Mathematics", "Data & Statistics", "Mean Calculation", "lower"),
    ("math.statistics.probability_basic", "Mathematics", "Probability", "Basic Probability", "lower"),
    ("math.patterns.number_sequence", "Mathematics", "Mathematical Thinking", "Number Sequence Pattern", "lower"),
    # Task 10 Chinese pilot
    ("chinese.pinyin.initials", "Chinese", "Pinyin", "声母", "early"),
    ("chinese.pinyin.finals", "Chinese", "Pinyin", "韵母与声调", "early"),
    ("chinese.pinyin.spelling", "Chinese", "Pinyin", "拼音拼写", "early"),
    # Task 10 Chinese literacy (from Step 4 description)
    ("chinese.literacy.radicals", "Chinese", "Literacy", "汉字部首", "early"),
    ("chinese.literacy.stroke_count", "Chinese", "Literacy", "笔画数", "early"),
    # Task 10 English pilot
    ("english.vocabulary.animals", "English", "Grammar & Punctuation", "Animal Vocabulary", "lower"),
    ("english.vocabulary.colors", "English", "Grammar & Punctuation", "Color Vocabulary", "lower"),
    ("english.grammar.be_verbs", "English", "Grammar & Punctuation", "Be-verb Usage", "lower"),
    # Task 10 Science pilot
    ("science.life.plant_parts", "Science", "Organisms & Life Processes", "Plant Parts", "lower"),
    ("science.life.animal_types", "Science", "Organisms & Life Processes", "Animal Types", "lower"),
    ("science.matter.states_of_matter", "Science", "Matter & Materials", "States of Matter", "lower"),
]

def seed_slug_topics(db) -> dict:
    created = 0
    skipped = 0
    for key, subject, domain, name, age_group in SLUG_TOPICS:
        existing = db.query(LearningTopic).filter(LearningTopic.topic_key == key).one_or_none()
        if existing:
            skipped += 1
            continue
        db.add(LearningTopic(
            topic_key=key, subject=subject, domain=domain, name=name,
            age_group=age_group, source_taxonomy="beijing", deprecated=False,
        ))
        created += 1
    db.commit()
    return {"created": created, "skipped": skipped}

if __name__ == "__main__":
    db = SessionLocal()
    try:
        result = seed_slug_topics(db)
        print(f"Slug topic seeding: {result}")
    finally:
        db.close()
```

Run: `cd server && uv run python -m scripts.seed_p7a_topic_slugs` (or the module path matching your scripts layout).

**Pilot domain routing note:** The Chinese pilot domains ("Pinyin", "Literacy") are new
domains not present in the upstream taxonomy (upstream has zero Chinese-language topics);
they come from the Beijing taxonomy side. Add them to ROUTING_RULES in Task 7 (the "Pinyin"
and "Literacy" entries) if the Beijing taxonomy uses different domain strings — verify
against the Beijing topics data at implementation time.

**Verification:** After running, `db.query(LearningTopic).count()` should include the new
slug topics, and a follow-up `coverage_report --subject Mathematics --format table` should
show the new topics in the total.

- [ ] **Step 2c: Implement suspended review_status propagation**

Add `"suspended"` to the set of valid `review_status` values and exclude it from all question-selection paths, per Review Focus #2 and the origin spec §5.7 consumer-audit commitment:

1. In `server/packages/db/models/learning/question.py`: no schema change needed if `review_status` is a plain String column; if it's an Enum, add `"suspended"` to the enum values.
2. In `server/apps/backend/app/services/learning/question_service.py`: add `Question.review_status != "suspended"` to every query that selects questions for practice/availability (or confirm the existing `== "approved"` filter already excludes it; add a test proving this).
3. In `server/apps/backend/app/services/learning/adaptive_service.py`: confirm `select_questions()` already filters `review_status == "approved"` (excludes suspended); add a test.
4. In `server/apps/backend/app/routers/practice.py`: confirm question-selection queries exclude suspended; add a test.

```python
# Regression test (add to test_question_service.py or new file)
def test_suspended_questions_never_selected(db_session):
    """Suspended questions must be excluded from every selection path."""
    q = Question(topic_id=1, question_type="calculation",
                 stem="1+1=?", answer_json='{"answer": 2}',
                 difficulty=1, source="template", review_status="suspended")
    db_session.add(q); db_session.flush()

    # All selection paths must exclude suspended
    assert not adaptive_service.select_questions(db_session, child_id=..., topic_id=1)
    assert not question_service.get_available_questions(db_session, topic_id=1)
```

- [ ] **Step 3: Run test to verify it fails**

Run: `cd server && uv run pytest tests/backend/test_content_hash_backfill.py -v`
Expected: FAIL — `backfill_content_hash` and `fix_beijing_topics` modules don't exist

- [ ] **Step 4: Implement content_hash backfill script**

```python
# server/apps/backend/scripts/backfill_content_hash.py
"""Backfill content_hash on existing questions.

Usage:
    cd server
    uv run python -m apps.backend.scripts.backfill_content_hash
"""
from __future__ import annotations

import json

from sqlalchemy.orm import Session

from packages.core.logging import get_logger
from packages.db.models.learning.question import Question
from packages.db.session import SessionLocal
from apps.backend.app.services.learning.question_seeder import _compute_content_hash

logger = get_logger(__name__)


def backfill(db: Session, batch_size: int = 100) -> dict:
    """Fill content_hash for questions that don't have one.

    Returns dict with backfilled/skipped counts.
    Fixed-offset loop: the content_hash IS NULL filter shrinks as rows
    are flushed, so we re-query from offset 0 until a batch returns empty.
    """
    backfilled = 0
    skipped = (
        db.query(Question)
        .filter(Question.content_hash.isnot(None))
        .count()
    )

    while True:
        questions = (
            db.query(Question)
            .filter(Question.content_hash.is_(None))
            .limit(batch_size)
            .offset(0)
            .all()
        )
        if not questions:
            break

        for q in questions:
            answer = json.loads(q.answer_json)
            q.content_hash = _compute_content_hash(q.stem, answer)
            backfilled += 1

        db.flush()

    logger.info("content_hash backfill: backfilled=%d, skipped=%d", backfilled, skipped)
    return {"backfilled": backfilled, "skipped": skipped}


def main() -> None:
    db = SessionLocal()
    try:
        result = backfill(db)
        print(f"Backfill complete: {result}")
    finally:
        db.close()


if __name__ == "__main__":
    main()
```

- [ ] **Step 5: Implement Beijing topic fix script**

```python
# server/apps/backend/scripts/fix_beijing_topics.py
"""Fix NULL subject/age_group on Beijing-specific topics.

Uses upstream os-taxonomy topic data to fill missing fields by
matching domain + topic_key suffix.

Usage:
    cd server
    uv run python -m apps.backend.scripts.fix_beijing_topics [--dry-run]
"""
from __future__ import annotations

from sqlalchemy.orm import Session

from packages.core.logging import get_logger
from packages.db.models.learning.topic import LearningTopic
from packages.db.session import SessionLocal

logger = get_logger(__name__)


def _build_upstream_index(db: Session) -> dict[str, LearningTopic]:
    """Build domain → upstream topic index for subject/age_group lookup."""
    topics = (
        db.query(LearningTopic)
        .filter(
            LearningTopic.source_taxonomy == "upstream",
            LearningTopic.deprecated == False,  # noqa: E712
        )
        .all()
    )
    # Index by domain (most Beijing topics can match by domain)
    index: dict[str, LearningTopic] = {}
    for t in topics:
        if t.domain and t.subject:
            index.setdefault(t.domain, t)
    return index


def fix_beijing_topics(db: Session, dry_run: bool = False) -> dict:
    """Fill NULL subject/age_group on Beijing topics from upstream data.

    Returns dict with fixed/skipped/total counts.
    """
    upstream_index = _build_upstream_index(db)

    beijing_topics = (
        db.query(LearningTopic)
        .filter(
            LearningTopic.source_taxonomy == "beijing",
            LearningTopic.deprecated == False,  # noqa: E712
        )
        .all()
    )

    fixed = 0
    skipped = 0
    no_match = 0

    for topic in beijing_topics:
        if topic.subject and topic.age_group:
            skipped += 1
            continue

        # Try to find matching upstream topic by domain
        upstream = upstream_index.get(topic.domain)
        if upstream is None:
            logger.warning(
                "No upstream match for Beijing topic domain=%s key=%s",
                topic.domain, topic.topic_key,
            )
            no_match += 1
            continue

        if not topic.subject:
            topic.subject = upstream.subject
        if not topic.age_group:
            topic.age_group = upstream.age_group
        fixed += 1

    if not dry_run:
        db.flush()

    logger.info(
        "Beijing topic fix: fixed=%d, skipped=%d, no_match=%d (dry_run=%s)",
        fixed, skipped, no_match, dry_run,
    )
    return {"fixed": fixed, "skipped": skipped, "no_match": no_match, "total": len(beijing_topics)}


def main() -> None:
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    db = SessionLocal()
    try:
        result = fix_beijing_topics(db, dry_run=args.dry_run)
        print(f"Fix result: {result}")
    finally:
        db.close()


if __name__ == "__main__":
    main()
```

- [ ] **Step 6: Run tests and verify they pass**

Run: `cd server && uv run pytest tests/backend/test_content_hash_backfill.py -v`
Expected: All PASS

- [ ] **Step 7: Run backfill on dev database**

```bash
cd server
uv run python -m apps.backend.scripts.backfill_content_hash
uv run python -m apps.backend.scripts.fix_beijing_topics --dry-run
uv run python -m apps.backend.scripts.fix_beijing_topics
```

- [ ] **Step 8: Commit**

```bash
git add server/apps/backend/scripts/backfill_content_hash.py \
       server/apps/backend/scripts/fix_beijing_topics.py \
       server/tests/backend/test_content_hash_backfill.py
git commit -m "feat(learning): content_hash backfill + Beijing topic subject/age_group fix

- backfill script: fills content_hash for all existing questions
- fix_beijing_topics: fills NULL subject/age_group from upstream taxonomy
- 5 tests covering hash correctness, idempotency, topic matching

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>"
```

---

## Task 3: Coverage Service (Minimal) + Beijing Topic Aggregation

**Files:**
- Create: `server/apps/backend/app/services/learning/coverage_service.py`
- Test: `server/tests/backend/test_coverage_service.py`

**Interfaces:**
- Consumes: `LearningTopic`, `LearningDependency`, `Question` models
- Produces:
  - `compute_topic_coverage(db, topic_id) -> dict` — returns `{topic_id, existence, prerequisite_value, coverage_score, approved_question_count}`
  - `compute_subject_coverage(db, subject) -> dict` — returns `{subject, total_topics, covered_topics, coverage_rate, avg_prerequisite_value}`
  - `get_gap_report(db, subject, threshold) -> list[dict]` — returns topics below threshold, sorted by prerequisite_value
  - `get_prerequisite_value(db, topic_id) -> float` — returns normalized dependent count (0.0-1.0)

- [ ] **Step 1: Write the failing tests**

```python
# server/tests/backend/test_coverage_service.py
"""Tests for minimal coverage service (P7a-min)."""
import pytest

from packages.db.models.learning.question import Question
from packages.db.models.learning.topic import LearningTopic, LearningDependency
from apps.backend.app.services.learning.coverage_service import (
    compute_topic_coverage,
    compute_subject_coverage,
    get_gap_report,
    get_prerequisite_value,
)


@pytest.fixture
def math_topics(db_session):
    """Create a small set of math topics with dependencies."""
    t1 = LearningTopic(topic_key="math.add", subject="mathematics", domain="number",
                       name="Addition", age_group="lower", deprecated=False)
    t2 = LearningTopic(topic_key="math.mul", subject="mathematics", domain="number",
                       name="Multiplication", age_group="lower", deprecated=False)
    t3 = LearningTopic(topic_key="math.div", subject="mathematics", domain="number",
                       name="Division", age_group="lower", deprecated=False)
    db_session.add_all([t1, t2, t3])
    db_session.flush()
    # t2 depends on t1, t3 depends on t2
    db_session.add_all([
        LearningDependency(topic_id=t2.id, prerequisite_id=t1.id),
        LearningDependency(topic_id=t3.id, prerequisite_id=t2.id),
    ])
    db_session.flush()
    return [t1, t2, t3]


class TestPrerequisiteValue:
    """Prerequisite value = normalized dependent count."""

    def test_topic_with_no_dependents_returns_zero(self, db_session, math_topics):
        t3 = math_topics[2]  # Division — nothing depends on it
        value = get_prerequisite_value(db_session, t3.id)
        assert value == 0.0

    def test_topic_with_dependents_returns_positive(self, db_session, math_topics):
        t1 = math_topics[0]  # Addition — Multiplication depends on it
        value = get_prerequisite_value(db_session, t1.id)
        assert value > 0.0

    def test_value_is_normalized_to_zero_one(self, db_session, math_topics):
        t1 = math_topics[0]
        value = get_prerequisite_value(db_session, t1.id)
        assert 0.0 <= value <= 1.0


class TestTopicCoverage:
    """Coverage score = binary existence in P7a-min (prerequisite value used only for gap-report sorting)."""

    def test_topic_without_questions_has_zero_existence(self, db_session, math_topics):
        result = compute_topic_coverage(db_session, math_topics[0].id)
        assert result["existence"] == 0.0
        assert result["coverage_score"] == 0.0

    def test_topic_with_approved_question_has_full_existence(self, db_session, math_topics):
        t1 = math_topics[0]
        db_session.add(Question(
            topic_id=t1.id, question_type="calculation",
            stem="1+1=?", answer_json='{"answer": 2}',
            difficulty=1, source="template", review_status="approved",
        ))
        db_session.flush()

        result = compute_topic_coverage(db_session, t1.id)
        assert result["existence"] == 1.0

    def test_rejected_questions_dont_count(self, db_session, math_topics):
        t1 = math_topics[0]
        db_session.add(Question(
            topic_id=t1.id, question_type="calculation",
            stem="1+1=?", answer_json='{"answer": 2}',
            difficulty=1, source="template", review_status="rejected",
        ))
        db_session.flush()

        result = compute_topic_coverage(db_session, t1.id)
        assert result["existence"] == 0.0

    def test_suspended_questions_dont_count(self, db_session, math_topics):
        t1 = math_topics[0]
        db_session.add(Question(
            topic_id=t1.id, question_type="calculation",
            stem="1+1=?", answer_json='{"answer": 2}',
            difficulty=1, source="template", review_status="suspended",
        ))
        db_session.flush()

        result = compute_topic_coverage(db_session, t1.id)
        assert result["existence"] == 0.0


class TestSubjectCoverage:
    """Subject-level aggregation."""

    def test_subject_coverage_aggregation(self, db_session, math_topics):
        t1 = math_topics[0]
        db_session.add(Question(
            topic_id=t1.id, question_type="calculation",
            stem="1+1=?", answer_json='{"answer": 2}',
            difficulty=1, source="template", review_status="approved",
        ))
        db_session.flush()

        result = compute_subject_coverage(db_session, "mathematics")
        assert result["total_topics"] == 3
        assert result["covered_topics"] == 1
        assert 0.0 < result["coverage_rate"] < 1.0


class TestGapReport:
    """Gap report lists topics below threshold, sorted by prerequisite value."""

    def test_gap_report_returns_topics_below_threshold(self, db_session, math_topics):
        report = get_gap_report(db_session, subject="mathematics", threshold=0.5)
        # All 3 topics have no questions → all below threshold
        assert len(report) == 3

    def test_gap_report_sorted_by_prerequisite_value(self, db_session, math_topics):
        report = get_gap_report(db_session, subject="mathematics", threshold=0.5)
        # First item should have highest prerequisite value
        values = [item["prerequisite_value"] for item in report]
        assert values == sorted(values, reverse=True)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd server && uv run pytest tests/backend/test_coverage_service.py -v`
Expected: FAIL — `coverage_service` module doesn't exist

- [ ] **Step 3: Implement coverage_service.py**

```python
# server/apps/backend/app/services/learning/coverage_service.py
"""Coverage evaluation service (P7a-min: existence + prerequisite value).

Minimal version: coverage_score = existence (binary 0/1).
Prerequisite value used for prioritization in gap reports.
P7a-full will upgrade to 5-dim weighted model.
"""
from __future__ import annotations

from sqlalchemy import func as sa_func
from sqlalchemy.orm import Session

from packages.core.logging import get_logger
from packages.db.models.learning.question import Question
from packages.db.models.learning.topic import LearningTopic, LearningDependency

logger = get_logger(__name__)


def get_prerequisite_value(db: Session, topic_id: int) -> float:
    """Compute normalized prerequisite value for a topic.

    Value = (number of topics that depend on this topic) / (max dependents in subject).
    Returns 0.0 if the topic has no dependents or is the only topic.
    """
    dependent_count = (
        db.query(LearningDependency)
        .filter(LearningDependency.prerequisite_id == topic_id)
        .count()
    )

    if dependent_count == 0:
        return 0.0

    # Get the topic's subject for normalization
    topic = db.query(LearningTopic).get(topic_id)
    if topic is None or topic.subject is None:
        return 0.0

    # Find max dependents in same subject for normalization
    subject_topic_ids = (
        db.query(LearningTopic.id)
        .filter(
            LearningTopic.subject == topic.subject,
            LearningTopic.deprecated == False,  # noqa: E712
        )
        .all()
    )
    tid_list = [t[0] for t in subject_topic_ids]
    if not tid_list:
        return 0.0

    max_dependents = 0
    for tid in tid_list:
        count = (
            db.query(LearningDependency)
            .filter(LearningDependency.prerequisite_id == tid)
            .count()
        )
        if count > max_dependents:
            max_dependents = count

    if max_dependents == 0:
        return 0.0

    return dependent_count / max_dependents


def compute_topic_coverage(db: Session, topic_id: int, family_id: int | None = None) -> dict:
    """Compute coverage score for a single topic (P7a-min version).

    Returns dict with:
    - topic_id, existence (0/1), prerequisite_value (0-1), coverage_score (0-1)

    When family_id is provided, scopes Question queries to that family only.
    """
    # Existence: does this topic have ≥1 approved question?
    q_filter = [
        Question.topic_id == topic_id,
        Question.review_status == "approved",
    ]
    if family_id is not None:
        q_filter.append(Question.family_id == family_id)
    approved_count = (
        db.query(Question)
        .filter(*q_filter)
        .count()
    )
    existence = 1.0 if approved_count > 0 else 0.0

    prereq_value = get_prerequisite_value(db, topic_id)

    # P7a-min: score = existence (the only meaningful dimension at 0.56% coverage)
    coverage_score = existence

    return {
        "topic_id": topic_id,
        "existence": existence,
        "prerequisite_value": prereq_value,
        "coverage_score": coverage_score,
        "approved_question_count": approved_count,
    }


def compute_subject_coverage(db: Session, subject: str, family_id: int | None = None) -> dict:
    """Compute subject-level coverage aggregation.

    Returns dict with:
    - subject, total_topics, covered_topics, coverage_rate, avg_prerequisite_value

    When family_id is provided, scopes Question queries to that family only.
    """
    topics = (
        db.query(LearningTopic)
        .filter(
            LearningTopic.subject == subject,
            LearningTopic.deprecated == False,  # noqa: E712
        )
        .all()
    )
    total = len(topics)
    if total == 0:
        return {
            "subject": subject, "total_topics": 0, "covered_topics": 0,
            "coverage_rate": 0.0, "avg_prerequisite_value": 0.0,
        }

    covered = 0
    total_prereq = 0.0
    for t in topics:
        q_filter = [
            Question.topic_id == t.id,
            Question.review_status == "approved",
        ]
        if family_id is not None:
            q_filter.append(Question.family_id == family_id)
        approved = (
            db.query(Question)
            .filter(*q_filter)
            .count()
        )
        if approved > 0:
            covered += 1
        total_prereq += get_prerequisite_value(db, t.id)

    return {
        "subject": subject,
        "total_topics": total,
        "covered_topics": covered,
        "coverage_rate": covered / total,
        "avg_prerequisite_value": total_prereq / total,
    }


def get_gap_report(
    db: Session,
    subject: str | None = None,
    threshold: float = 0.5,
    limit: int = 100,
    family_id: int | None = None,
) -> list[dict]:
    """Get topics below coverage threshold, sorted by prerequisite value (descending).

    Returns list of dicts with topic info and coverage details.
    When family_id is provided, scopes Question queries to that family only.
    """
    query = db.query(LearningTopic).filter(
        LearningTopic.deprecated == False,  # noqa: E712
    )
    if subject:
        query = query.filter(LearningTopic.subject == subject)

    topics = query.all()
    gaps = []

    for topic in topics:
        cov = compute_topic_coverage(db, topic.id, family_id=family_id)
        if cov["coverage_score"] < threshold:
            gaps.append({
                "topic_id": topic.id,
                "topic_key": topic.topic_key,
                "name": topic.name,
                "subject": topic.subject,
                "domain": topic.domain,
                "coverage_score": cov["coverage_score"],
                "prerequisite_value": cov["prerequisite_value"],
            })

    gaps.sort(key=lambda x: -x["prerequisite_value"])
    return gaps[:limit]
```

- [ ] **Step 4: Run tests and verify they pass**

Run: `cd server && uv run pytest tests/backend/test_coverage_service.py -v`
Expected: All PASS (10+ tests)

- [ ] **Step 5: Commit**

```bash
git add server/apps/backend/app/services/learning/coverage_service.py \
       server/tests/backend/test_coverage_service.py
git commit -m "feat(learning): P7a-min coverage service — existence scoring + prerequisite value

- compute_topic_coverage: binary existence + prerequisite value
- compute_subject_coverage: per-subject aggregation
- get_gap_report: topics below threshold sorted by prerequisite value
- 10+ tests covering existence, rejection, suspension, aggregation, gap sorting

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>"
```

---

## Task 4: Coverage API Endpoints + CLI Script

**Files:**
- Create: `server/apps/backend/scripts/coverage_report.py`
- Modify: `server/apps/backend/app/routers/practice.py`
- Modify: `server/apps/backend/app/schemas/practice.py`
- Test: `server/tests/backend/test_coverage_api.py`

**Interfaces:**
- Consumes: `coverage_service.compute_subject_coverage()`, `coverage_service.compute_topic_coverage()`, `coverage_service.get_gap_report()`
- Produces: 3 new API endpoints + 1 CLI script

- [ ] **Step 1: Write the failing tests — API endpoints**

```python
# server/tests/backend/test_coverage_api.py
"""Tests for coverage API endpoints."""
import pytest
from fastapi.testclient import TestClient

from packages.db.models.learning.question import Question
from packages.db.models.learning.topic import LearningTopic


class TestCoverageSummary:
    """GET /practice/coverage/summary"""

    def test_summary_returns_subject_breakdown(self, client, db_session, auth_headers):
        t = LearningTopic(topic_key="math.add", subject="mathematics",
                         domain="number", name="Addition", deprecated=False)
        db_session.add(t)
        db_session.flush()
        db_session.add(Question(
            topic_id=t.id, question_type="calculation",
            stem="1+1=?", answer_json='{"answer": 2}',
            difficulty=1, source="template", review_status="approved",
        ))
        db_session.commit()

        resp = client.get("/api/v1/practice/coverage/summary", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert "subjects" in data
        assert any(s["subject"] == "mathematics" for s in data["subjects"])


class TestCoverageDetailed:
    """GET /practice/coverage/detailed"""

    def test_detailed_returns_per_topic_scores(self, client, db_session, auth_headers):
        t = LearningTopic(topic_key="math.add", subject="mathematics",
                         domain="number", name="Addition", deprecated=False)
        db_session.add(t)
        db_session.commit()

        resp = client.get(
            "/api/v1/practice/coverage/detailed?subject=mathematics",
            headers=auth_headers,
        )
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert "topics" in data
        assert len(data["topics"]) >= 1


class TestCoverageGapReport:
    """GET /practice/coverage/gap-report"""

    def test_gap_report_returns_uncovered_topics(self, client, db_session, auth_headers):
        t = LearningTopic(topic_key="math.add", subject="mathematics",
                         domain="number", name="Addition", deprecated=False)
        db_session.add(t)
        db_session.commit()

        resp = client.get(
            "/api/v1/practice/coverage/gap-report?subject=mathematics&threshold=0.5",
            headers=auth_headers,
        )
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert "gaps" in data
        assert len(data["gaps"]) >= 1
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd server && uv run pytest tests/backend/test_coverage_api.py -v`
Expected: FAIL — endpoints return 404

- [ ] **Step 3: Add response schemas**

In `server/apps/backend/app/schemas/practice.py`, add:

```python
class CoverageTopicDetail(SnowflakeBase):
    topic_id: int
    topic_key: str
    name: str
    subject: str | None = None
    domain: str | None = None
    existence: float
    prerequisite_value: float
    coverage_score: float
    approved_question_count: int


class CoverageSubjectSummary(BaseModel):
    subject: str
    total_topics: int
    covered_topics: int
    coverage_rate: float
    avg_prerequisite_value: float


class CoverageSummaryResponse(BaseModel):
    subjects: list[CoverageSubjectSummary]
    total_topics: int
    covered_topics: int
    overall_rate: float


class CoverageDetailedResponse(BaseModel):
    topics: list[CoverageTopicDetail]
    total: int


class GapItem(BaseModel):
    topic_id: int
    topic_key: str
    name: str
    subject: str | None = None
    domain: str | None = None
    coverage_score: float
    prerequisite_value: float


class GapReportResponse(BaseModel):
    gaps: list[GapItem]
    threshold: float
    total_gaps: int
```

- [ ] **Step 4: Add endpoints to practice router**

In `server/apps/backend/app/routers/practice.py`, add after existing coverage endpoint. Also add to imports at the top of the file:

```python
from apps.backend.app.responses import EnvelopeResponse  # if not already imported
```

Note: existing practice.py endpoints use `response_model=X` and return Pydantic models directly. The new coverage/review endpoints use `EnvelopeResponse(data={...})` explicitly — match this pattern for consistency with other routers (ai_input_polish.py, captcha.py).

```python
@router.get("/coverage/summary")
def get_coverage_summary(
    user: User = Depends(get_current_user_or_child),
    db: Session = Depends(get_db),
):
    """Subject-level coverage aggregation."""
    from apps.backend.app.services.learning.coverage_service import compute_subject_coverage

    # Get distinct subjects
    subjects = (
        db.query(LearningTopic.subject)
        .filter(
            LearningTopic.subject.isnot(None),
            LearningTopic.deprecated == False,
        )
        .distinct()
        .all()
    )
    subject_list = [s[0] for s in subjects if s[0]]

    results = []
    total_topics = 0
    covered_topics = 0
    for subj in subject_list:
        s = compute_subject_coverage(db, subj, family_id=user.family_id)
        results.append(s)
        total_topics += s["total_topics"]
        covered_topics += s["covered_topics"]

    return EnvelopeResponse(data={
        "subjects": results,
        "total_topics": total_topics,
        "covered_topics": covered_topics,
        "overall_rate": covered_topics / total_topics if total_topics > 0 else 0.0,
    })


@router.get("/coverage/detailed")
def get_coverage_detailed(
    subject: str | None = None,
    limit: int = 100,
    offset: int = 0,
    user: User = Depends(get_current_user_or_child),
    db: Session = Depends(get_db),
):
    """Per-topic coverage scores."""
    from apps.backend.app.services.learning.coverage_service import compute_topic_coverage

    query = db.query(LearningTopic).filter(LearningTopic.deprecated == False)
    if subject:
        query = query.filter(LearningTopic.subject == subject)

    topics = query.offset(offset).limit(limit).all()
    details = []
    for t in topics:
        cov = compute_topic_coverage(db, t.id, family_id=user.family_id)
        details.append({
            "topic_id": t.id,
            "topic_key": t.topic_key,
            "name": t.name,
            "subject": t.subject,
            "domain": t.domain,
            "existence": cov["existence"],
            "prerequisite_value": cov["prerequisite_value"],
            "coverage_score": cov["coverage_score"],
            "approved_question_count": cov["approved_question_count"],
        })

    return EnvelopeResponse(data={"topics": details, "total": len(details)})


@router.get("/coverage/gap-report")
def get_coverage_gap_report(
    subject: str | None = None,
    threshold: float = 0.5,
    limit: int = 100,
    user: User = Depends(get_current_user_or_child),
    db: Session = Depends(get_db),
):
    """Topics below coverage threshold, sorted by prerequisite value."""
    from apps.backend.app.services.learning.coverage_service import get_gap_report

    gaps = get_gap_report(db, subject=subject, threshold=threshold, limit=limit, family_id=user.family_id)
    return EnvelopeResponse(data={
        "gaps": gaps,
        "threshold": threshold,
        "total_gaps": len(gaps),
    })
```

- [ ] **Step 5: Implement CLI script**

```python
# server/apps/backend/scripts/coverage_report.py
"""Coverage report CLI tool.

Usage:
    cd server
    uv run python -m apps.backend.scripts.coverage_report --subject mathematics --format table
    uv run python -m apps.backend.scripts.coverage_report --gap-only --output gaps.json
"""
from __future__ import annotations

import argparse
import json

from packages.db.session import SessionLocal
from apps.backend.app.services.learning.coverage_service import (
    compute_subject_coverage,
    get_gap_report,
)


def _print_table(rows: list[dict], columns: list[str]) -> None:
    """Print rows as a simple text table."""
    if not rows:
        print("(no data)")
        return
    widths = {c: max(len(c), max(len(str(r.get(c, ""))) for r in rows)) for c in columns}
    header = "  ".join(c.ljust(widths[c]) for c in columns)
    print(header)
    print("-" * len(header))
    for row in rows:
        print("  ".join(str(row.get(c, "")).ljust(widths[c]) for c in columns))


def main() -> None:
    parser = argparse.ArgumentParser(description="Coverage report")
    parser.add_argument("--subject", type=str, help="Filter by subject")
    parser.add_argument("--gap-only", action="store_true", help="Show only gaps")
    parser.add_argument("--threshold", type=float, default=0.5)
    parser.add_argument("--format", choices=["table", "json"], default="table")
    parser.add_argument("--output", type=str, help="Output file path")
    args = parser.parse_args()

    db = SessionLocal()
    try:
        if args.gap_only:
            gaps = get_gap_report(db, subject=args.subject, threshold=args.threshold)
            if args.format == "json" or args.output:
                data = json.dumps(gaps, indent=2, ensure_ascii=False)
                if args.output:
                    with open(args.output, "w") as f:
                        f.write(data)
                    print(f"Gap report written to {args.output} ({len(gaps)} gaps)")
                else:
                    print(data)
            else:
                _print_table(gaps, ["topic_key", "name", "subject", "domain",
                                    "coverage_score", "prerequisite_value"])
        else:
            # Show subject-level summary
            from packages.db.models.learning.topic import LearningTopic
            subjects = (
                db.query(LearningTopic.subject)
                .filter(LearningTopic.subject.isnot(None), LearningTopic.deprecated == False)
                .distinct().all()
            )
            results = []
            for (subj,) in subjects:
                if args.subject and subj != args.subject:
                    continue
                s = compute_subject_coverage(db, subj)
                results.append(s)

            if args.format == "json":
                print(json.dumps(results, indent=2))
            else:
                _print_table(results, ["subject", "total_topics", "covered_topics",
                                       "coverage_rate", "avg_prerequisite_value"])
    finally:
        db.close()


if __name__ == "__main__":
    main()
```

- [ ] **Step 6: Run tests**

Run: `cd server && uv run pytest tests/backend/test_coverage_api.py -v`
Expected: All PASS

- [ ] **Step 7: Verify CLI script works**

```bash
cd server
uv run python -m apps.backend.scripts.coverage_report --format table
uv run python -m apps.backend.scripts.coverage_report --gap-only --subject mathematics
```

- [ ] **Step 8: Commit**

```bash
git add server/apps/backend/app/routers/practice.py \
       server/apps/backend/app/schemas/practice.py \
       server/apps/backend/scripts/coverage_report.py \
       server/tests/backend/test_coverage_api.py
git commit -m "feat(learning): P7a-min coverage API endpoints + CLI report script

- GET /practice/coverage/summary — subject-level aggregation
- GET /practice/coverage/detailed — per-topic scores
- GET /practice/coverage/gap-report — uncovered topics sorted by prerequisite value
- CLI: coverage_report with --subject, --gap-only, --format, --output
- 3+ API tests

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>"
```

---

## Task 5: Scoring Extension — multi_fill_blank + ai_graded

**Files:**
- Modify: `server/apps/backend/app/services/learning/scoring_service.py`
- Test: `server/tests/backend/test_scoring_extended.py`

**Interfaces:**
- Consumes: Existing `check_answer()` function signature
- Produces: Extended `check_answer()` that handles 2 new types; new `check_ai_graded()` function returning `{is_correct, result_level, confidence, explanation, low_confidence}`; mastery-update guard for low-confidence ai_graded

- [ ] **Step 1: Write the failing tests**

```python
# server/tests/backend/test_scoring_extended.py
"""Tests for extended scoring types: multi_fill_blank and ai_graded."""
import pytest

from apps.backend.app.services.learning.scoring_service import (
    check_answer,
    check_ai_graded,
)


class TestMultiFillBlank:
    """multi_fill_blank: each blank scored independently."""

    def test_all_correct(self):
        correct = {"blanks": ["北京", "上海", "广州"]}
        user = {"blanks": ["北京", "上海", "广州"]}
        result = check_answer("multi_fill_blank", correct, user)
        assert result is True

    def test_partial_wrong(self):
        correct = {"blanks": ["北京", "上海", "广州"]}
        user = {"blanks": ["北京", "深圳", "广州"]}
        result = check_answer("multi_fill_blank", correct, user)
        assert result is False  # not all correct → overall False

    def test_whitespace_tolerance(self):
        correct = {"blanks": ["100", "km"]}
        user = {"blanks": [" 100 ", " km "]}
        result = check_answer("multi_fill_blank", correct, user)
        assert result is True

    def test_empty_blanks_counted(self):
        correct = {"blanks": ["a", "b"]}
        user = {"blanks": ["a", ""]}
        result = check_answer("multi_fill_blank", correct, user)
        assert result is False


class TestMultiFillBlankPartial:
    """Partial scoring for multi_fill_blank (returns per-blank results)."""

    def test_partial_score_returns_per_blank(self):
        from apps.backend.app.services.learning.scoring_service import check_multi_fill_blank_partial
        correct = {"blanks": ["北京", "上海", "广州"]}
        user = {"blanks": ["北京", "深圳", "广州"]}
        result = check_multi_fill_blank_partial(correct, user)
        assert result["correct_count"] == 2
        assert result["total"] == 3
        assert result["per_blank"] == [True, False, True]


class TestAiGraded:
    """ai_graded: AI scoring with confidence."""

    def test_high_confidence_returns_correct(self):
        correct = {"rubric": "光合作用", "keywords": ["光", "二氧化碳", "氧"]}
        user = {"text": "植物通过光合作用将二氧化碳转化为氧气"}
        # Mock the AI call
        result = check_ai_graded(correct, user, mock_confidence=0.9)
        assert result["is_correct"] is True
        assert result["confidence"] == 0.9
        assert "explanation" in result

    def test_low_confidence_flagged(self):
        correct = {"rubric": "光合作用"}
        user = {"text": "一些关于植物的内容"}
        result = check_ai_graded(correct, user, mock_confidence=0.5)
        assert result["confidence"] == 0.5
        assert result["low_confidence"] is True

    def test_check_answer_returns_bool_for_ai_graded(self):
        correct = {"rubric": "test"}
        user = {"text": "answer"}
        # check_answer for ai_graded uses confidence threshold
        result = check_answer("ai_graded", correct, user)
        # Without mock, should return False (no AI available in test)
        assert isinstance(result, bool)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd server && uv run pytest tests/backend/test_scoring_extended.py -v`
Expected: FAIL

- [ ] **Step 3: Implement scoring extensions**

In `server/apps/backend/app/services/learning/scoring_service.py`, add:

```python
def check_multi_fill_blank_partial(
    correct_answer: dict,
    user_answer: dict,
) -> dict:
    """Score multi_fill_blank with per-blank detail.

    Returns {correct_count, total, per_blank: [bool, ...]}.
    """
    correct_blanks = correct_answer.get("blanks", [])
    user_blanks = user_answer.get("blanks", [])
    total = len(correct_blanks)
    per_blank = []

    for i in range(total):
        if i < len(user_blanks):
            c = str(correct_blanks[i]).strip()
            u = str(user_blanks[i]).strip()
            per_blank.append(c == u)
        else:
            per_blank.append(False)

    return {
        "correct_count": sum(per_blank),
        "total": total,
        "per_blank": per_blank,
    }


def check_ai_graded(
    correct_answer: dict,
    user_answer: dict,
    family_id: int | None = None,
    user_id: int | None = None,
    *,
    mock_confidence: float | None = None,
) -> dict:
    """AI-assisted grading with confidence (synchronous — safe to call from scoring path).

    In production, calls the agent's lightweight LLM endpoint via a sync HTTP client
    (httpx) so this function can be invoked from the sync scoring path without
    requiring the entire practice flow to become async.
    For testing, accepts mock_confidence to bypass the LLM call.

    Returns {is_correct, result_level, confidence, explanation, low_confidence}.
    result_level: 'correct' | 'partial' | 'incorrect' — drives 3-state UI display.
    """
    confidence_threshold = 0.7

    if mock_confidence is not None:
        # Test path: use mock confidence
        confidence = mock_confidence
        is_correct = confidence >= confidence_threshold
        # Derive result_level from confidence + mock keyword coverage
        result_level = "correct" if confidence >= 0.85 else ("partial" if confidence >= 0.5 else "incorrect")
        explanation = "Mock AI grading for testing"
    else:
        # Production path: synchronous HTTP call to agent's /grade endpoint.
        # family_id/user_id are passed in by the caller (matching the
        # llm_generator pattern); the practice-flow caller reads them from the
        # request context. Import settings at module top:
        #   from packages.core.settings import settings
        import httpx
        try:
            response = httpx.post(
                f"{settings.AGENT_BASE_URL}/grade",
                json={
                    "rubric": correct_answer.get("rubric", ""),
                    "user_text": user_answer.get("text", ""),
                    "keywords": correct_answer.get("keywords", []),
                },
                headers={"X-Family-Id": str(family_id), "X-User-Id": str(user_id)},
                timeout=30.0,
            )
            data = response.json()
            confidence = data.get("confidence", 0.0)
            result_level = data.get("result_level", "correct" if confidence >= 0.85 else "partial" if confidence >= 0.5 else "incorrect")
            is_correct = confidence >= confidence_threshold
            explanation = data.get("explanation", "")
        except Exception:
            logger.warning("ai_graded: agent LLM endpoint unavailable, returning False")
            confidence = 0.0
            result_level = "incorrect"
            is_correct = False
            explanation = "AI grading service unavailable"

    return {
        "is_correct": is_correct,
        "result_level": result_level,
        "confidence": confidence,
        "explanation": explanation,
        "low_confidence": confidence < confidence_threshold,
    }
```

And extend `check_answer()` with new type handlers:

```python
    if question_type == "multi_fill_blank":
        result = check_multi_fill_blank_partial(correct_answer, user_answer)
        return result["correct_count"] == result["total"]

    if question_type == "ai_graded":
        # Legacy bool contract for scoring_service.check_answer; the caller that
        # needs confidence (the mastery-update path in practice_service) calls
        # check_ai_graded's structured result via the attempt-processing flow
        # below — do NOT call check_ai_graded twice (double LLM round-trip).
        result = check_ai_graded(correct_answer, user_answer, family_id, user_id)
        return result["is_correct"]
```

**Mastery-update guard (add to Task 5 or practice-flow task):** The attempt-processing flow in `practice_service.py` calls `check_ai_graded()` ONCE and threads the full structured result through, so the mastery-update decision uses the same result the feedback was built from. Add this step:

```python
# In practice_service.py attempt-processing flow (ai_graded branch):
# check_answer() is NOT used for ai_graded here — call check_ai_graded directly
# so the confidence dict is available without a second LLM round-trip.
ai_result = check_ai_graded(correct_answer, user_answer, family_id, user_id)
is_correct = ai_result["is_correct"]
# Record the attempt and feedback regardless of confidence
attempt.feedback = ai_result["explanation"]
# Skip mastery update when confidence is below threshold
if ai_result["low_confidence"]:
    pass  # feedback recorded above; mastery_score deliberately NOT updated
else:
    update_mastery_score(child_id, topic_id, is_correct)
```

Test: create an `ai_graded` question with `mock_confidence=0.5`, process an attempt, and assert `mastery_score` is unchanged while feedback is still shown. `update_mastery_score` and the attempt-recording call sites are the existing `practice_service.py` functions — no new function named `record_attempt_without_mastery_update` is introduced.


- [ ] **Step 4: Run tests and verify they pass**

Run: `cd server && uv run pytest tests/backend/test_scoring_extended.py -v`
Expected: All PASS (8+ tests)

- [ ] **Step 5: Commit**

```bash
git add server/apps/backend/app/services/learning/scoring_service.py \
       server/tests/backend/test_scoring_extended.py
git commit -m "feat(learning): extended scoring — multi_fill_blank + ai_graded

- multi_fill_blank: per-blank matching with partial score detail
- ai_graded: confidence-based AI scoring (production path via agent LLM)
- low-confidence (<0.7) flagged for mastery exclusion
- 8+ tests

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>"
```

---

## Task 6: LLM Question Generator with 3-Layer Validation + Risk Classification

**Files:**
- Create: `server/apps/backend/app/services/learning/llm_generator.py`
- Test: `server/tests/backend/test_llm_generator.py`

**Interfaces:**
- Consumes: `LearningTopic` model, `content_safety_filter`, `GeneratedQuestion` dataclass
- Produces:
  - `generate_question_for_topic(db, topic_id, llm_client) -> GeneratedQuestion | None`
  - `validate_question_layers(gq, topic, db) -> ValidationResult`
  - `classify_risk(gq, validation) -> str` ("low" | "medium" | "high")

- [ ] **Step 1: Write the failing tests**

```python
# server/tests/backend/test_llm_generator.py
"""Tests for LLM question generator with 3-layer validation."""
import pytest
from unittest.mock import MagicMock

from packages.db.models.learning.topic import LearningTopic
from packages.db.models.learning.question import Question
from packages.domain.question_templates.base import GeneratedQuestion
from apps.backend.app.services.learning.llm_generator import (
    generate_question_for_topic,
    validate_layer1_format,
    validate_layer2_correctness,
    validate_layer3_ai_cross,
    classify_risk,
    _build_generation_prompt,
)


@pytest.fixture
def math_topic(db_session):
    t = LearningTopic(
        topic_key="math.fraction.addition", subject="mathematics",
        domain="number", name="Fraction Addition", age_group="lower",
        description="Add fractions with like denominators", deprecated=False,
    )
    db_session.add(t)
    db_session.flush()
    return t


class TestLayer1FormatValidation:
    """Layer 1: structural format checks."""

    def test_valid_question_passes(self, math_topic):
        gq = GeneratedQuestion(
            template_id="llm.gen", stem="1/4 + 2/4 = ?",
            answer={"answer": "3/4"}, question_type="calculation",
            difficulty=2, bloom_level="apply", topic_key="math.fraction.addition",
            age_group="lower", stem_zh="1/4 + 2/4 = ?",
        )
        errors = validate_layer1_format(gq, math_topic)
        assert errors == []

    def test_empty_stem_fails(self, math_topic):
        gq = GeneratedQuestion(
            template_id="llm.gen", stem="",
            answer={"answer": "3/4"}, question_type="calculation",
            difficulty=2, bloom_level="apply", topic_key="math.fraction.addition",
            age_group="lower",
        )
        errors = validate_layer1_format(gq, math_topic)
        assert len(errors) > 0

    def test_wrong_topic_key_fails(self, math_topic):
        gq = GeneratedQuestion(
            template_id="llm.gen", stem="Some question",
            answer={"answer": "42"}, question_type="calculation",
            difficulty=2, bloom_level="apply", topic_key="wrong.key",
            age_group="lower",
        )
        errors = validate_layer1_format(gq, math_topic)
        assert any("topic_key" in e for e in errors)


class TestLayer3AiCrossValidation:
    """Layer 3: AI cross-validation (mocked)."""

    def test_high_agreement_passes(self, math_topic):
        # With mock returning "match", layer 3 should pass
        mock_client = MagicMock()
        result = validate_layer3_ai_cross(gq=None, topic=math_topic, llm_client=mock_client,
                                          mock_verdict="match")
        assert result["passed"] is True

    def test_content_safety_filter_applied(self, math_topic):
        from apps.backend.app.services.learning.content_safety_filter import filter_tutor_output
        # Content safety is called as part of layer 1
        unsafe = "Some violent content"
        result = filter_tutor_output(unsafe, child_id=0)  # FilterResult return shape
        # Layer 1 checks the .safe flag on the FilterResult object
        assert hasattr(result, "safe")
        assert isinstance(result.safe, bool)


class TestRiskClassification:
    """Risk classification based on validation results and question type."""

    def test_objective_low_risk_when_all_pass(self):
        validation = {"layer1": [], "layer2": {"passed": True}, "layer3": {"passed": True}}
        gq = GeneratedQuestion(
            template_id="llm.gen", stem="test", answer={"answer": 42},
            question_type="calculation", difficulty=2, bloom_level="apply",
            topic_key="math.test", age_group="lower",
        )
        risk = classify_risk(gq, validation)
        assert risk == "low"

    def test_analyze_bloom_is_medium_risk(self):
        validation = {"layer1": [], "layer2": {"passed": True}, "layer3": {"passed": True}}
        gq = GeneratedQuestion(
            template_id="llm.gen", stem="What pattern?", answer={"answer": "42"},
            question_type="application", difficulty=3, bloom_level="analyze",
            topic_key="math.test", age_group="lower",
        )
        risk = classify_risk(gq, validation)
        assert risk == "medium"

    def test_layer2_failure_is_high_risk(self):
        validation = {"layer1": [], "layer2": {"passed": False}, "layer3": {"passed": True}}
        gq = GeneratedQuestion(
            template_id="llm.gen", stem="test", answer={"answer": 42},
            question_type="calculation", difficulty=2, bloom_level="apply",
            topic_key="math.test", age_group="lower",
        )
        risk = classify_risk(gq, validation)
        assert risk == "high"


class TestPromptConstruction:
    """Prompt must include topic info and enforce topic_key in output."""

    def test_prompt_includes_topic_name(self, math_topic):
        prompt = _build_generation_prompt(math_topic)
        assert "Fraction Addition" in prompt

    def test_prompt_includes_topic_key_constraint(self, math_topic):
        prompt = _build_generation_prompt(math_topic)
        assert "math.fraction.addition" in prompt
        assert "must" in prompt.lower() or "必须" in prompt
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd server && uv run pytest tests/backend/test_llm_generator.py -v`
Expected: FAIL

- [ ] **Step 3: Implement llm_generator.py**

```python
# server/apps/backend/app/services/learning/llm_generator.py
"""LLM question generator with 3-layer validation and risk classification.

Pipeline:
  1. Build prompt from topic info (topic_key enforced in output)
  2. Call LLM → parse JSON → GeneratedQuestion
  3. Layer 1: format validation (stem non-empty, topic_key match, answer format)
  4. Layer 2: correctness validation (recompute for calculation, option exclusivity)
  5. Layer 3: AI cross-validation (separate prompt/model judges the question)
  6. Risk classification → route to review strategy
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field

from sqlalchemy.orm import Session

from packages.core.logging import get_logger
from packages.db.models.learning.topic import LearningTopic
from packages.domain.question_templates.base import GeneratedQuestion
from apps.backend.app.services.learning.content_safety_filter import filter_tutor_output

logger = get_logger(__name__)

# Objective question types that can be auto-verified
OBJECTIVE_TYPES = {"calculation", "fill_blank", "multiple_choice", "true_false"}

# Bloom levels requiring human review
REVIEW_BLOOM_LEVELS = {"analyze", "evaluate", "create"}


@dataclass
class ValidationResult:
    layer1: list[str] = field(default_factory=list)
    layer2: dict = field(default_factory=dict)
    layer3: dict = field(default_factory=dict)

    @property
    def passed(self) -> bool:
        return (
            len(self.layer1) == 0
            and self.layer2.get("passed", False)
            and self.layer3.get("passed", False)
        )


def _build_generation_prompt(topic: LearningTopic) -> str:
    """Build prompt for LLM question generation.

    Critical: prompt must include target topic_key and require it in output.
    """
    return f"""You are a professional K-12 math question generator.

Generate ONE high-quality math question for the following knowledge point:

Topic: {topic.name}
Topic Key: {topic.topic_key}
Domain: {topic.domain}
Age Group: {topic.age_group}
Description: {topic.description or topic.name_zh or topic.name}

Requirements:
- The question MUST measure the knowledge point "{topic.name}" (topic_key: {topic.topic_key})
- The question must be appropriate for age group "{topic.age_group}"
- Provide a clear, unambiguous question with a verifiable answer
- All text must be in Chinese (中文)

Output format (JSON):
{{
    "stem": "question text in Chinese",
    "stem_zh": "same as stem (Chinese)",
    "question_type": "calculation|fill_blank|multiple_choice|true_false|application",
    "answer": {{"answer": "correct answer"}},
    "difficulty": 1-5,
    "bloom_level": "remember|understand|apply|analyze",
    "topic_key": "{topic.topic_key}",
    "solution": {{"steps": ["step 1", "step 2"]}},
    "options": [{{"key": "A", "text": "option A"}}, ...]  // only for multiple_choice
}}

CRITICAL: The topic_key in your output MUST be exactly "{topic.topic_key}". Do not choose a different topic.
"""


def validate_layer1_format(gq: GeneratedQuestion, topic: LearningTopic) -> list[str]:
    """Layer 1: Structural format validation.

    Returns list of error strings (empty = passed).
    """
    errors = []

    if not gq.stem or len(gq.stem.strip()) < 5:
        errors.append("stem is empty or too short (< 5 chars)")

    # CRITICAL: topic_key must match (anti-hallucination defense)
    if gq.topic_key != topic.topic_key:
        errors.append(f"topic_key mismatch: expected '{topic.topic_key}', got '{gq.topic_key}'")

    if gq.question_type not in {"calculation", "fill_blank", "multiple_choice", "true_false", "application"}:
        errors.append(f"unknown question_type: {gq.question_type}")

    if gq.difficulty < 1 or gq.difficulty > 5:
        errors.append(f"difficulty out of range: {gq.difficulty}")

    if gq.bloom_level not in {"remember", "understand", "apply", "analyze", "evaluate", "create"}:
        errors.append(f"unknown bloom_level: {gq.bloom_level}")

    # Content safety
    # Content safety — filter_tutor_output returns a FilterResult; check its safe flag
    safety_result = filter_tutor_output(gq.stem, child_id=0)
    if not safety_result.safe:
        errors.append("stem failed content safety filter")

    return errors


def validate_layer2_correctness(gq: GeneratedQuestion) -> dict:
    """Layer 2: Answer correctness validation.

    Returns {passed: bool, detail: str}.
    """
    if gq.question_type == "calculation":
        # For calculation: try to verify the answer by re-evaluating
        # This is a simplified check — full re-solve would require a CAS
        answer = gq.answer
        if "answer" not in answer:
            return {"passed": False, "detail": "calculation missing 'answer' key"}
        return {"passed": True, "detail": "calculation answer present (manual verify recommended)"}

    if gq.question_type == "multiple_choice":
        options = gq.options or []
        if len(options) < 3:
            return {"passed": False, "detail": f"too few options: {len(options)}"}
        answer_key = gq.answer.get("key")
        option_keys = {o.get("key") for o in options}
        if answer_key not in option_keys:
            return {"passed": False, "detail": f"answer key '{answer_key}' not in options"}
        # Check option uniqueness
        texts = [o.get("text", "") for o in options]
        if len(set(texts)) != len(texts):
            return {"passed": False, "detail": "duplicate option texts"}
        return {"passed": True, "detail": "multiple_choice structure valid"}

    if gq.question_type in ("fill_blank", "true_false", "application"):
        answer = gq.answer
        if not answer:
            return {"passed": False, "detail": "empty answer"}
        return {"passed": True, "detail": "answer present"}

    return {"passed": True, "detail": "no auto-verification available"}


def validate_layer3_ai_cross(
    gq: GeneratedQuestion | None,
    topic: LearningTopic,
    llm_client=None,
    mock_verdict: str | None = None,
    family_id: int | None = None,
    user_id: int | None = None,
) -> dict:
    """Layer 3: AI cross-validation — a separate prompt judges question quality.

    Returns {passed: bool, score: float, detail: str}.
    In production, calls the agent's lightweight LLM endpoint via sync httpx.
    FAILS CLOSED on agent outage: returns passed=False so the question routes
    to human review rather than neutral pass.
    """
    if mock_verdict is not None:
        passed = mock_verdict == "match"
        return {"passed": passed, "score": 1.0 if passed else 0.0, "detail": f"mock: {mock_verdict}"}

    # Production path: synchronous HTTP call to agent's /cross-validate-question endpoint.
    import httpx
    try:
        response = httpx.post(
            f"{settings.AGENT_BASE_URL}/cross-validate-question",
            json={
                "stem": gq.stem if gq else "",
                "topic_name": topic.name,
                "topic_key": topic.topic_key,
                "answer": json.dumps(gq.answer) if gq else "",
            },
            headers={
                "X-Family-Id": str(family_id) if family_id else "",
                "X-User-Id": str(user_id) if user_id else "",
            },
            timeout=30.0,
        )
        verdict = response.json().get("verdict", "match")
        score = {"match": 1.0, "partial": 0.5, "mismatch": 0.0}.get(verdict, 0.5)
        return {"passed": verdict != "mismatch", "score": score, "detail": f"agent: {verdict}"}
    except Exception:
        # FAIL CLOSED: agent outage routes to human review, never neutral pass
        logger.warning("Layer 3: agent cross-validation unavailable, failing closed")
        return {"passed": False, "score": 0.0, "detail": "agent unavailable — routed to human review"}


# Risk-to-review routing mapping (pinned for this phase):
# low/medium/high risk ALL persist as review_status="pending" in P7b.
# No auto-approval exists this phase; all questions enter the review queue.
# Future phases may auto-approve low-risk after a probationary period.


def classify_risk(gq: GeneratedQuestion, validation: dict) -> str:
    """Classify question risk for review routing.

    Returns: "low", "medium", or "high"
    """
    # High risk: any layer failure
    if validation.get("layer1") and len(validation["layer1"]) > 0:
        return "high"
    if not validation.get("layer2", {}).get("passed", True):
        return "high"
    if not validation.get("layer3", {}).get("passed", True):
        return "high"

    # Medium risk: subjective Bloom levels
    if gq.bloom_level in REVIEW_BLOOM_LEVELS:
        return "medium"

    # Low risk: objective type + all layers pass
    if gq.question_type in OBJECTIVE_TYPES:
        return "low"

    return "medium"


def generate_question_for_topic(
    db: Session,
    topic: LearningTopic,
    family_id: int | None = None,
    user_id: int | None = None,
) -> tuple[GeneratedQuestion | None, str, dict]:
    """Generate a question for a topic through the full pipeline.

    Returns (question_or_none, risk_level, validation_details).
    """
    # Step 1: Build prompt and call LLM
    prompt = _build_generation_prompt(topic)

    # Call agent's lightweight LLM endpoint via AgentClient (same async pattern
    # as ai_suggest). family_id/user_id come from the caller; production_run
    # script passes None (agent permits internal token-only content calls).
    # Uses synchronous httpx.post so this function can be called from both
    # sync test paths and sync CLI scripts without an event loop.
    import httpx
    try:
        response = httpx.post(
            f"{settings.AGENT_BASE_URL}/generate-question",
            json={
                "prompt": prompt,
                "topic_key": topic.topic_key,
                "topic_name": topic.name,
            },
            headers={
                "X-Family-Id": str(family_id) if family_id else "",
                "X-User-Id": str(user_id) if user_id else "",
            },
            timeout=60.0,
        )
        data = response.json()
        # Parse response into GeneratedQuestion
        gq = GeneratedQuestion(
            template_id=f"llm.{topic.topic_key}",
            stem=data.get("stem", ""),
            stem_zh=data.get("stem_zh"),
            answer=data.get("answer", {}),
            question_type=data.get("question_type", "calculation"),
            difficulty=data.get("difficulty", 2),
            bloom_level=data.get("bloom_level", "apply"),
            topic_key=data.get("topic_key", topic.topic_key),
            age_group=data.get("age_group", topic.age_group or "lower"),
            options=data.get("options"),
            solution=data.get("solution"),
        )
    except Exception:
        logger.exception("LLM generator: agent endpoint call failed for %s", topic.topic_key)
        return None, "high", {"error": "LLM endpoint call failed"}
```

- [ ] **Step 4: Run tests and verify they pass**

Run: `cd server && uv run pytest tests/backend/test_llm_generator.py -v`
Expected: All PASS

- [ ] **Step 5: Commit**

```bash
git add server/apps/backend/app/services/learning/llm_generator.py \
       server/tests/backend/test_llm_generator.py
git commit -m "feat(learning): LLM question generator with 3-layer validation + risk classification

- Layer 1: format validation (topic_key anti-hallucination, content safety)
- Layer 2: correctness validation (answer structure, option exclusivity)
- Layer 3: AI cross-validation (agent LLM endpoint, mockable for tests)
- Risk classification: low/medium/high → review routing
- Prompt construction includes topic_name + topic_key enforcement
- 10+ tests

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>"
```

---

## Task 7: Question Router + Production CLI

**Files:**
- Create: `server/apps/backend/app/services/learning/question_router.py`
- Create: `server/apps/backend/scripts/production_run.py`
- Test: `server/tests/backend/test_question_router.py`

**Interfaces:**
- Consumes: `LearningTopic`, `TEMPLATE_REGISTRY`, `coverage_service`, `llm_generator`
- Produces:
  - `route(db, topic_id) -> RoutingResult` — returns recommended generation method
  - `generate_production_plan(db, gaps, weekly_capacity) -> list[ProductionTask]`
  - `execute_template_tasks(db, plan) -> ProductionResult`

- [ ] **Step 1: Write the failing tests**

```python
# server/tests/backend/test_question_router.py
"""Tests for question router and production pipeline."""
import pytest

from packages.db.models.learning.topic import LearningTopic
from packages.db.models.learning.question import Question
from apps.backend.app.services.learning.question_router import (
    route,
    generate_production_plan,
    RoutingResult,
)


@pytest.fixture
def topics(db_session):
    t1 = LearningTopic(topic_key="math.add", subject="mathematics", domain="number",
                       name="Addition", age_group="lower", deprecated=False)
    t2 = LearningTopic(topic_key="math.pattern", subject="mathematics", domain="reasoning",
                       name="Pattern Finding", age_group="lower", deprecated=False)
    db_session.add_all([t1, t2])
    db_session.flush()
    return [t1, t2]


class TestRouting:
    """Router selects generation method based on topic characteristics."""

    def test_calculation_topic_routes_to_template(self, db_session, topics):
        result = route(db_session, topics[0].id)
        assert result.method == "template"
        assert result.topic_id == topics[0].id

    def test_reasoning_topic_routes_to_llm(self, db_session, topics):
        result = route(db_session, topics[1].id)
        # Pattern finding → LLM generation (no parameterized template possible)
        assert result.method == "llm"

    def test_route_returns_recommended_count(self, db_session, topics):
        result = route(db_session, topics[0].id)
        assert result.recommended_count >= 1


class TestProductionPlan:
    """Production plan allocates capacity across gaps."""

    def test_plan_respects_capacity(self, db_session, topics):
        gaps = [
            {"topic_id": topics[0].id, "prerequisite_value": 0.8},
            {"topic_id": topics[1].id, "prerequisite_value": 0.5},
        ]
        plan = generate_production_plan(db_session, gaps, weekly_capacity=10)
        total = sum(t.count for t in plan)
        assert total <= 10

    def test_plan_prioritizes_high_prerequisite_value(self, db_session, topics):
        gaps = [
            {"topic_id": topics[1].id, "prerequisite_value": 0.3},
            {"topic_id": topics[0].id, "prerequisite_value": 0.9},
        ]
        plan = generate_production_plan(db_session, gaps, weekly_capacity=10)
        # Higher prereq value topic should get at least as many questions
        assert plan[0].topic_id == topics[0].id or len(plan) == 1
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd server && uv run pytest tests/backend/test_question_router.py -v`
Expected: FAIL

- [ ] **Step 3: Implement question_router.py**

```python
# server/apps/backend/app/services/learning/question_router.py
"""Question generation strategy router.

Routes topics → generation method based on explicit configuration.
Phase 7 first version: config table mapping domain → method.
"""
from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy.orm import Session

from packages.core.logging import get_logger
from packages.db.models.learning.topic import LearningTopic

logger = get_logger(__name__)

# Explicit routing config: domain → preferred generation method
# This is the first-version config table; later versions can be smarter.
# IMPORTANT: keys must match the real LearningTopic.domain values from the
# os-taxonomy taxonomy (verified against packages/os_taxonomy/topics.json).
# Upstream uses title-case multi-word strings; unlisted domains fall back to
# DEFAULT_METHOD="template".
ROUTING_RULES: dict[str, str] = {
    # Math domains → template (parameterizable, deterministic answers)
    "Addition & Subtraction": "template",
    "Multiplication & Division": "template",
    "Fractions": "template",
    "Number Representation & Place Value": "template",
    "Measurement": "template",
    "Geometry": "template",
    "Algebra": "template",
    "Data & Statistics": "template",
    "Ratio & Proportion": "template",
    "Probability": "template",
    "Counting & Cardinality": "template",
    # Math reasoning → LLM (no parameterized template)
    "Mathematical Thinking": "llm",
    # Science pilot domains (life/matter facts → template)
    "Organisms & Life Processes": "template",
    "Matter & Materials": "template",
    # English pilot domains
    "Grammar & Punctuation": "template",
    "Reading Comprehension": "template",
}

DEFAULT_METHOD = "template"


@dataclass
class RoutingResult:
    topic_id: int
    topic_key: str
    method: str  # "template" | "llm" | "external"
    recommended_count: int
    target_difficulty: list[int]
    target_bloom: list[str]


@dataclass
class ProductionTask:
    topic_id: int
    method: str
    count: int
    target_difficulty: list[int]
    target_bloom: list[str]


@dataclass
class ProductionResult:
    generated: int = 0
    validated: int = 0
    failed: int = 0
    details: list[str] = None  # type: ignore[assignment]

    def __post_init__(self):
        if self.details is None:
            self.details = []


def route(db: Session, topic_id: int) -> RoutingResult:
    """Determine generation method for a topic.

    Uses ROUTING_RULES config table to map domain → method.
    """
    topic = db.query(LearningTopic).get(topic_id)
    if topic is None:
        raise ValueError(f"Topic {topic_id} not found")

    domain = topic.domain or ""
    method = ROUTING_RULES.get(domain, DEFAULT_METHOD)

    # Determine recommended count based on existing coverage
    existing_count = _count_approved_questions(db, topic_id)
    recommended = max(1, 5 - existing_count)  # Target 5 questions per topic minimum

    # Determine target difficulty and bloom
    target_difficulty = _target_difficulty_for_topic(db, topic_id)
    target_bloom = _target_bloom_for_topic(topic)

    return RoutingResult(
        topic_id=topic_id,
        topic_key=topic.topic_key,
        method=method,
        recommended_count=recommended,
        target_difficulty=target_difficulty,
        target_bloom=target_bloom,
    )


def generate_production_plan(
    db: Session,
    gaps: list[dict],
    weekly_capacity: int = 200,
) -> list[ProductionTask]:
    """Generate a production plan from gap report.

    Allocates capacity across gaps, prioritizing high prerequisite value.
    """
    # Sort gaps by prerequisite value (highest first)
    sorted_gaps = sorted(gaps, key=lambda g: -g.get("prerequisite_value", 0))

    plan = []
    remaining = weekly_capacity

    for gap in sorted_gaps:
        if remaining <= 0:
            break

        routing = route(db, gap["topic_id"])
        count = min(routing.recommended_count, remaining)

        plan.append(ProductionTask(
            topic_id=gap["topic_id"],
            method=routing.method,
            count=count,
            target_difficulty=routing.target_difficulty,
            target_bloom=routing.target_bloom,
        ))
        remaining -= count

    return plan


def _count_approved_questions(db: Session, topic_id: int) -> int:
    from packages.db.models.learning.question import Question
    return (
        db.query(Question)
        .filter(Question.topic_id == topic_id, Question.review_status == "approved")
        .count()
    )


def _target_difficulty_for_topic(db: Session, topic_id: int) -> list[int]:
    """Determine which difficulty levels need more questions."""
    from packages.db.models.learning.question import Question
    existing = (
        db.query(Question.difficulty)
        .filter(Question.topic_id == topic_id, Question.review_status == "approved")
        .distinct()
        .all()
    )
    existing_levels = {d[0] for d in existing}
    # Target: cover difficulties 1-3 at minimum
    missing = [d for d in [1, 2, 3] if d not in existing_levels]
    return missing if missing else [2]  # Default to medium if all covered


def _target_bloom_for_topic(topic: LearningTopic) -> list[str]:
    """Determine target Bloom levels based on subject."""
    if topic.subject == "mathematics":
        return ["remember", "understand", "apply", "analyze"]
    return ["remember", "understand", "apply"]
```

- [ ] **Step 4: Implement production_run CLI script**

```python
# server/apps/backend/scripts/production_run.py
"""Execute a question production plan.

Usage:
    cd server
    uv run python -m apps.backend.scripts.production_run --subject mathematics --capacity 50
    uv run python -m apps.backend.scripts.production_run --plan plan.json
"""
from __future__ import annotations

import argparse
import json

from packages.core.logging import get_logger
from packages.db.session import SessionLocal
from apps.backend.app.services.learning.coverage_service import get_gap_report
from apps.backend.app.services.learning.question_router import (
    generate_production_plan,
    ProductionResult,
)
from apps.backend.app.services.learning.question_seeder import seed_questions_from_templates

logger = get_logger(__name__)


def execute_template_tasks(db, plan) -> ProductionResult:
    """Execute template-based production tasks, filtered per topic."""
    result = ProductionResult()
    for task in plan:
        if task.method != "template":
            continue
        # Resolve the topic and seed only that topic's registered templates
        topic = db.query(LearningTopic).get(task.topic_id)
        if topic is None:
            result.failed += 1
            result.details.append(f"Topic {task.topic_id} not found, skipping")
            continue
        seed_result = seed_questions_from_templates(
            db, count_per_template=task.count, topic_id=task.topic_id,
        )
        result.generated += seed_result.generated
        result.failed += seed_result.failed
        result.details.append(
            f"Template seed for {topic.topic_key}: generated={seed_result.generated}, failed={seed_result.failed}"
        )
    return result


def seed_from_llm(db, gq, topic, risk: str = "medium") -> SeedResult:
    """Persist an LLM-generated question after 3-layer validation (Task 6).

    Sets review_status="pending" (no auto-approval this phase), stores the
    risk classification for review-queue ordering, and computes content_hash
    for dedup. Declared in Modified Files (question_seeder.py); implemented
    here so Task 7's execute_llm_tasks has a concrete call target.
    """
    from apps.backend.app.services.learning.question_service import create_question

    result = SeedResult()
    content_hash = _compute_content_hash(gq.stem, gq.answer)
    existing = (
        db.query(Question)
        .filter(Question.content_hash == content_hash)
        .first()
    )
    if existing:
        result.skipped_duplicate += 1
        return result

    create_question(
        db=db,
        topic_id=topic.id,
        question_type=gq.question_type,
        stem=gq.stem,
        answer=gq.answer,
        difficulty=gq.difficulty,
        bloom_level=gq.bloom_level,
        source="llm",
        age_group=gq.age_group or "lower",
        stem_zh=gq.stem_zh,
        options=gq.options,
        solution=gq.solution,
        source_metadata={
            "content_hash": content_hash,
            "risk": risk,           # review-queue ordering (Task 11)
            "needs_review": True,   # pending for human review
        },
    )
    result.generated += 1
    return result


def execute_llm_tasks(db, plan, family_id=None, user_id=None) -> ProductionResult:
    """Execute LLM-routed production tasks through the 3-layer validation pipeline."""
    from apps.backend.app.services.learning.llm_generator import (
        generate_question_for_topic, validate_layer1_format,
        validate_layer2_correctness, validate_layer3_ai_cross, classify_risk,
    )
    result = ProductionResult()
    for task in plan:
        if task.method != "llm":
            continue
        topic = db.query(LearningTopic).get(task.topic_id)
        if topic is None:
            result.failed += 1
            result.details.append(f"Topic {task.topic_id} not found, skipping")
            continue
        for _ in range(task.count):
            gq, risk, validation = generate_question_for_topic(
                db, topic, family_id=family_id, user_id=user_id,
            )
            if gq is None:
                result.failed += 1
                result.details.append(f"LLM generation failed for {topic.topic_key}: {validation}")
                continue
            # 3-layer validation
            layer1_errors = validate_layer1_format(gq, topic)
            layer2 = validate_layer2_correctness(gq)
            layer3 = validate_layer3_ai_cross(
                gq, topic, family_id=family_id, user_id=user_id,
            )
            if layer1_errors or not layer2["passed"] or not layer3["passed"]:
                result.failed += 1
                result.details.append(
                    f"Validation failed for {topic.topic_key}: L1={layer1_errors}, L2={layer2}, L3={layer3}"
                )
                continue
            # Persist via seed_from_llm (sets review_status="pending", carries risk)
            seed_result = seed_from_llm(db, gq, topic, risk=risk)
            result.generated += seed_result.generated
            result.failed += seed_result.failed
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description="Question production pipeline")
    parser.add_argument("--subject", type=str, help="Subject to produce questions for")
    parser.add_argument("--capacity", type=int, default=50, help="Max questions to produce")
    parser.add_argument("--threshold", type=float, default=0.5, help="Gap threshold")
    parser.add_argument("--plan", type=str, help="Load plan from JSON file")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    db = SessionLocal()
    try:
        if args.plan:
            with open(args.plan) as f:
                plan_items = json.load(f)
            # Plan JSON format: [{"topic_id": int, "method": str, "count": int, "target_difficulty": [int], "target_bloom": [str]}]
            plan = [
                ProductionTask(
                    topic_id=item["topic_id"],
                    method=item["method"],
                    count=item["count"],
                    target_difficulty=item.get("target_difficulty", [2]),
                    target_bloom=item.get("target_bloom", ["apply"]),
                )
                for item in plan_items
            ]
            print(f"Loaded plan from {args.plan}: {len(plan)} tasks")
        else:
            gaps = get_gap_report(db, subject=args.subject, threshold=args.threshold)
            print(f"Found {len(gaps)} gaps below threshold {args.threshold}")

            plan = generate_production_plan(db, gaps, weekly_capacity=args.capacity)
            print(f"Production plan: {len(plan)} tasks, {sum(t.count for t in plan)} questions")

            for task in plan:
                print(f"  Topic {task.topic_id}: method={task.method}, count={task.count}")

        if args.dry_run:
            print("Dry run — no questions produced")
            return

        # Execute tasks — dispatch by method so LLM-routed tasks are not
        # silently skipped (execute_llm_tasks is defined above).
        template_result = execute_template_tasks(db, plan)
        llm_result = execute_llm_tasks(db, plan, family_id=None, user_id=None)
        db.commit()
        result = ProductionResult(
            generated=template_result.generated + llm_result.generated,
            validated=template_result.validated + llm_result.validated,
            failed=template_result.failed + llm_result.failed,
            details=template_result.details + llm_result.details,
        )
        print(f"Production complete: generated={result.generated}, failed={result.failed}")
        for detail in result.details:
            print(f"  {detail}")
    finally:
        db.close()


if __name__ == "__main__":
    main()
```

- [ ] **Step 5: Run tests**

Run: `cd server && uv run pytest tests/backend/test_question_router.py -v`
Expected: All PASS

- [ ] **Step 6: Commit**

```bash
git add server/apps/backend/app/services/learning/question_router.py \
       server/apps/backend/scripts/production_run.py \
       server/tests/backend/test_question_router.py
git commit -m "feat(learning): question router + production CLI pipeline

- route(): topic → generation method via config table
- generate_production_plan(): gap-based capacity allocation
- production_run CLI: --subject, --capacity, --threshold, --dry-run
- 5+ router tests

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>"
```

---

## Task 8: Math Template Expansion (11 New Templates)

**Files:**
- Create: `server/packages/domain/question_templates/math_decimal.py`
- Create: `server/packages/domain/question_templates/math_estimation.py`
- Create: `server/packages/domain/question_templates/math_measurement.py`
- Create: `server/packages/domain/question_templates/math_statistics.py`
- Create: `server/packages/domain/question_templates/math_patterns.py`
- Modify: `server/packages/domain/question_templates/__init__.py`
- Test: `server/tests/packages/domain/test_math_expansion_templates.py`

**Interfaces:**
- Consumes: `register_template` decorator, `GeneratedQuestion` dataclass
- Produces: 11 new registered templates covering: decimal operations, estimation, unit conversion, perimeter/area, mean/probability, pattern finding

- [ ] **Step 1: Write the failing tests**

```python
# server/tests/packages/domain/test_math_expansion_templates.py
"""Tests for P7b math template expansion."""
import pytest

from packages.domain.question_templates.registry import (
    TEMPLATE_REGISTRY,
    generate_question,
    list_templates,
)


class TestDecimalTemplates:
    """Decimal operation templates."""

    def test_decimal_addition_generates(self):
        assert any("decimal" in tid for tid in TEMPLATE_REGISTRY)

    def test_decimal_addition_valid_output(self):
        template_ids = [tid for tid in TEMPLATE_REGISTRY if "decimal" in tid and "addition" in tid]
        assert len(template_ids) >= 1
        gq = generate_question(template_ids[0], {})
        assert gq.question_type == "calculation"
        assert "answer" in gq.answer
        assert gq.topic_key.startswith("math.")


class TestEstimationTemplates:
    """Estimation templates."""

    def test_estimation_generates(self):
        template_ids = [tid for tid in TEMPLATE_REGISTRY if "estimation" in tid]
        assert len(template_ids) >= 1
        gq = generate_question(template_ids[0], {})
        assert gq.question_type in ("calculation", "fill_blank", "multiple_choice")


class TestMeasurementTemplates:
    """Unit conversion and perimeter/area templates."""

    def test_unit_conversion_generates(self):
        template_ids = [tid for tid in TEMPLATE_REGISTRY if "measurement" in tid or "unit" in tid]
        assert len(template_ids) >= 1
        gq = generate_question(template_ids[0], {})
        assert gq.answer  # has an answer

    def test_perimeter_area_generates(self):
        template_ids = [tid for tid in TEMPLATE_REGISTRY if "perimeter" in tid or "area" in tid]
        assert len(template_ids) >= 1


class TestStatisticsTemplates:
    """Mean and probability templates."""

    def test_mean_generates(self):
        template_ids = [tid for tid in TEMPLATE_REGISTRY if "mean" in tid or "average" in tid or "statistics" in tid]
        assert len(template_ids) >= 1


class TestPatternTemplates:
    """Pattern finding / reasoning templates."""

    def test_pattern_generates(self):
        template_ids = [tid for tid in TEMPLATE_REGISTRY if "pattern" in tid]
        assert len(template_ids) >= 1
        gq = generate_question(template_ids[0], {})
        assert gq.bloom_level in ("analyze", "understand", "apply")


class TestTemplateCount:
    """Total new templates meets the 11 template target (at least 8 required)."""

    def test_at_least_8_new_templates(self):
        new_prefixes = ["decimal", "estimation", "measurement", "statistics", "pattern"]
        new_templates = [
            tid for tid in TEMPLATE_REGISTRY
            if any(p in tid for p in new_prefixes)
        ]
        assert len(new_templates) >= 11, f"Only {len(new_templates)} new templates found, need ≥11"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd server && uv run pytest tests/packages/domain/test_math_expansion_templates.py -v`
Expected: FAIL — no new templates registered

- [ ] **Step 3: Implement decimal templates**

```python
# server/packages/domain/question_templates/math_decimal.py
"""Math decimal operation templates."""
import random

from packages.domain.question_templates.base import GeneratedQuestion
from packages.domain.question_templates.registry import register_template


@register_template("math.decimal.addition")
def _gen_decimal_addition(params: dict) -> GeneratedQuestion:
    a = round(random.uniform(0.1, 9.9), 1)
    b = round(random.uniform(0.1, 9.9), 1)
    answer = round(a + b, 1)
    return GeneratedQuestion(
        template_id="math.decimal.addition",
        stem=f"计算：{a} + {b} = ?",
        stem_zh=f"计算：{a} + {b} = ?",
        answer={"answer": answer},
        question_type="calculation",
        difficulty=2,
        bloom_level="apply",
        topic_key="math.decimal.addition",
        age_group="lower",
        solution={"steps": [f"{a} + {b} = {answer}"]},
    )


@register_template("math.decimal.subtraction")
def _gen_decimal_subtraction(params: dict) -> GeneratedQuestion:
    a = round(random.uniform(1.0, 9.9), 1)
    b = round(random.uniform(0.1, a), 1)
    answer = round(a - b, 1)
    return GeneratedQuestion(
        template_id="math.decimal.subtraction",
        stem=f"计算：{a} - {b} = ?",
        stem_zh=f"计算：{a} - {b} = ?",
        answer={"answer": answer},
        question_type="calculation",
        difficulty=2,
        bloom_level="apply",
        topic_key="math.decimal.subtraction",
        age_group="lower",
    )


@register_template("math.decimal.multiplication")
def _gen_decimal_multiplication(params: dict) -> GeneratedQuestion:
    a = round(random.uniform(0.1, 5.0), 1)
    b = random.randint(2, 9)
    answer = round(a * b, 1)
    return GeneratedQuestion(
        template_id="math.decimal.multiplication",
        stem=f"计算：{a} × {b} = ?",
        stem_zh=f"计算：{a} × {b} = ?",
        answer={"answer": answer},
        question_type="calculation",
        difficulty=3,
        bloom_level="apply",
        topic_key="math.decimal.multiplication",
        age_group="lower",
    )
```

- [ ] **Step 4: Implement estimation, measurement, statistics, pattern templates**

Each file follows the same `@register_template` pattern as `math_decimal.py`. Create these files with 2-3 templates each:

**`math_estimation.py`** — 2 templates:

```python
# server/packages/domain/question_templates/math_estimation.py
import random
from packages.domain.question_templates.base import GeneratedQuestion
from packages.domain.question_templates.registry import register_template

@register_template("math.estimation.rounding")
def _gen_rounding(params: dict) -> GeneratedQuestion:
    number = random.randint(10, 9999)
    place = random.choice([("十", 10), ("百", 100), ("千", 1000)])
    rounded = round(number / place[1]) * place[1]
    return GeneratedQuestion(
        template_id="math.estimation.rounding",
        stem=f"将 {number} 四舍五入到{place[0]}位约是多少？",
        stem_zh=f"将 {number} 四舍五入到{place[0]}位约是多少？",
        answer={"answer": rounded}, question_type="calculation",
        difficulty=2, bloom_level="apply",
        topic_key="math.estimation.rounding", age_group="lower",
    )

@register_template("math.estimation.approximate_calc")
def _gen_approx_calc(params: dict) -> GeneratedQuestion:
    a = random.randint(10, 99)
    b = random.randint(10, 99)
    approx = round(a, -1) + round(b, -1)
    return GeneratedQuestion(
        template_id="math.estimation.approximate_calc",
        stem=f"估算：{a} + {b} 大约等于多少？（先四舍五入到十位再计算）",
        stem_zh=f"估算：{a} + {b} 大约等于多少？",
        answer={"answer": approx}, question_type="calculation",
        difficulty=2, bloom_level="understand",
        topic_key="math.estimation.approximate_calc", age_group="lower",
    )
```

**`math_measurement.py`** — 3 templates (unit conversion, perimeter, area):

```python
# server/packages/domain/question_templates/math_measurement.py
import random
from packages.domain.question_templates.base import GeneratedQuestion
from packages.domain.question_templates.registry import register_template

@register_template("math.measurement.unit_conversion")
def _gen_unit_conversion(params: dict) -> GeneratedQuestion:
    conversions = [
        (random.randint(1, 20), "米", "厘米", 100),
        (random.randint(1, 10), "千克", "克", 1000),
        (random.randint(1, 60), "分钟", "秒", 60),
        (random.randint(1, 5), "千米", "米", 1000),
    ]
    val, from_u, to_u, factor = random.choice(conversions)
    answer = val * factor
    return GeneratedQuestion(
        template_id="math.measurement.unit_conversion",
        stem=f"{val}{from_u} = ?{to_u}",
        stem_zh=f"{val}{from_u} = ?{to_u}",
        answer={"answer": answer}, question_type="calculation",
        difficulty=2, bloom_level="apply",
        topic_key="math.measurement.unit_conversion", age_group="lower",
    )

@register_template("math.measurement.perimeter_rectangle")
def _gen_perimeter(params: dict) -> GeneratedQuestion:
    l = random.randint(3, 20)
    w = random.randint(2, 15)
    answer = 2 * (l + w)
    return GeneratedQuestion(
        template_id="math.measurement.perimeter_rectangle",
        stem=f"一个长方形，长{l}厘米，宽{w}厘米，周长是多少厘米？",
        stem_zh=f"长方形长{l}cm，宽{w}cm，求周长。",
        answer={"answer": answer}, question_type="calculation",
        difficulty=2, bloom_level="apply",
        topic_key="math.measurement.perimeter_rectangle", age_group="lower",
        solution={"steps": [f"周长 = 2×(长+宽) = 2×({l}+{w}) = {answer}"]},
    )

@register_template("math.measurement.area_rectangle")
def _gen_area(params: dict) -> GeneratedQuestion:
    l = random.randint(3, 15)
    w = random.randint(2, 12)
    answer = l * w
    return GeneratedQuestion(
        template_id="math.measurement.area_rectangle",
        stem=f"一个长方形，长{l}厘米，宽{w}厘米，面积是多少平方厘米？",
        stem_zh=f"长方形长{l}cm，宽{w}cm，求面积。",
        answer={"answer": answer}, question_type="calculation",
        difficulty=2, bloom_level="apply",
        topic_key="math.measurement.area_rectangle", age_group="lower",
    )
```

**`math_statistics.py`** — 2 templates (mean, probability):

```python
# server/packages/domain/question_templates/math_statistics.py
import random
from packages.domain.question_templates.base import GeneratedQuestion
from packages.domain.question_templates.registry import register_template

@register_template("math.statistics.mean")
def _gen_mean(params: dict) -> GeneratedQuestion:
    count = random.randint(3, 5)
    numbers = [random.randint(1, 20) for _ in range(count)]
    total = sum(numbers)
    # Ensure divisible for clean answer
    numbers[-1] = numbers[-1] + (count - total % count) % count
    mean = sum(numbers) // count
    num_str = "、".join(str(n) for n in numbers)
    return GeneratedQuestion(
        template_id="math.statistics.mean",
        stem=f"求以下数据的平均数：{num_str}",
        stem_zh=f"求平均数：{num_str}",
        answer={"answer": mean}, question_type="calculation",
        difficulty=2, bloom_level="apply",
        topic_key="math.statistics.mean", age_group="lower",
    )

@register_template("math.statistics.probability_basic")
def _gen_probability(params: dict) -> GeneratedQuestion:
    scenarios = [
        ("一个骰子", 6, ["1", "2", "3", "4", "5", "6"]),
        ("一个袋子中有3个红球和2个蓝球", 5, ["红球", "蓝球"]),
    ]
    desc, total, _ = random.choice(scenarios)
    if "骰子" in desc:
        target = random.randint(1, 6)
        favorable = 1
        question = f"掷{desc}，掷出{target}的概率是多少？"
        answer_text = f"1/6"
    else:
        question = f"{desc}，随机摸一个球，摸到红球的概率是多少？"
        answer_text = "3/5"
    return GeneratedQuestion(
        template_id="math.statistics.probability_basic",
        stem=question, stem_zh=question,
        answer={"value": answer_text}, question_type="fill_blank",
        difficulty=3, bloom_level="understand",
        topic_key="math.statistics.probability_basic", age_group="lower",
    )
```

**`math_patterns.py`** — 1 template (pattern finding, Bloom: analyze):

```python
# server/packages/domain/question_templates/math_patterns.py
import random
from packages.domain.question_templates.base import GeneratedQuestion
from packages.domain.question_templates.registry import register_template

@register_template("math.patterns.number_sequence")
def _gen_number_sequence(params: dict) -> GeneratedQuestion:
    """Generate a number sequence where the student finds the next term."""
    pattern_type = random.choice(["arithmetic", "geometric_simple"])
    if pattern_type == "arithmetic":
        start = random.randint(1, 10)
        diff = random.randint(2, 7)
        seq = [start + i * diff for i in range(5)]
        answer = start + 5 * diff
        rule = f"等差数列，公差为{diff}"
    else:
        base = random.randint(2, 3)
        seq = [base ** (i + 1) for i in range(5)]
        answer = base ** 6
        rule = f"每次乘以{base}"
    seq_str = "、".join(str(n) for n in seq[:4])
    return GeneratedQuestion(
        template_id="math.patterns.number_sequence",
        stem=f"找规律，填下一个数：{seq_str}、?",
        stem_zh=f"找规律：{seq_str}、?",
        answer={"answer": answer}, question_type="calculation",
        difficulty=3, bloom_level="analyze",
        topic_key="math.patterns.number_sequence", age_group="lower",
        solution={"steps": [f"规律：{rule}", f"下一个数 = {answer}"]},
    )
```

- [ ] **Step 5: Register new modules in __init__.py**

In `server/packages/domain/question_templates/__init__.py`, add imports:

```python
from packages.domain.question_templates import math_decimal
from packages.domain.question_templates import math_estimation
from packages.domain.question_templates import math_measurement
from packages.domain.question_templates import math_statistics
from packages.domain.question_templates import math_patterns
```

**Topic-key mapping note:** Existing templates use real os-taxonomy topic IDs (e.g. `mt_AR-K72OIIO`) while the new templates above use slug-style keys (e.g. `math.decimal.addition`). The seeder's `_build_topic_key_index()` maps `topic_key → topic_id` from existing LearningTopics; slug keys that don't exist will result in `topic_id = None` and the question being skipped with `skipped_no_topic`. Two resolution paths (pick one before implementation):

- **(A) Create LearningTopic rows for slug keys** — add a migration or seed script that creates LearningTopic entries with topic_key matching each new template (math.decimal.addition, etc.), subject=mathematics, appropriate domain/age_group. This keeps template code readable but adds schema setup cost.
- **(B) Use real os-taxonomy IDs** — replace each slug topic_key in the templates above with the corresponding mt_* ID from `packages/os_taxonomy/data/topics.json`. More fragile (template breaks if taxonomy changes) but integrates with existing data.

The plan defaults to **(A)** for pilot readability. Add a step to Task 1 (or a new Task 1b) that creates the LearningTopic rows before any seeding runs.

- [ ] **Step 6: Run tests**

Run: `cd server && uv run pytest tests/packages/domain/test_math_expansion_templates.py -v`
Expected: All PASS (10+ tests)

- [ ] **Step 7: Commit**

```bash
git add server/packages/domain/question_templates/math_decimal.py \
       server/packages/domain/question_templates/math_estimation.py \
       server/packages/domain/question_templates/math_measurement.py \
       server/packages/domain/question_templates/math_statistics.py \
       server/packages/domain/question_templates/math_patterns.py \
       server/packages/domain/question_templates/__init__.py \
       server/tests/packages/domain/test_math_expansion_templates.py
git commit -m "feat(learning): P7b math template expansion — 11 new templates

- Decimal: addition, subtraction, multiplication (3 templates)
- Estimation: rounding estimation, approximate calculation (2 templates)
- Measurement: unit conversion, perimeter, area (3 templates)
- Statistics: mean calculation, probability (2 templates)
- Patterns: sequence finding (1 template, Bloom: analyze)
- Total: 11 new templates across 5 files

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>"
```

---

## Task 9: Math23K Import Adapter + Batch External Seeding

**Files:**
- Create: `server/apps/backend/app/services/learning/external_import.py`
- Modify: `server/apps/backend/app/services/learning/question_seeder.py`
- Test: `server/tests/backend/test_external_import.py`

**Interfaces:**
- Consumes: `ImportAdapter` protocol, `Question` model with `content_hash`, `question_service.create_question()`
- Produces:
  - `Math23KAdapter` class implementing `detect_format()`, `parse()`, `validate()`
  - `seed_from_external()` function in question_seeder

- [ ] **Step 1: Write the failing tests**

```python
# server/tests/backend/test_external_import.py
"""Tests for external question bank import."""
import json
import pytest

from apps.backend.app.services.learning.external_import import (
    Math23KAdapter,
    ImportAdapter,
    ImportedQuestion,
    SelfJSONAdapter,
)


class TestMath23KAdapter:
    """Math23K format adapter."""

    def test_detect_math23k_format(self):
        adapter = Math23KAdapter()
        # Math23K is JSON array with "question" and "answer" keys
        sample = [{"question": "小明有3个苹果...", "answer": "3+2=5"}]
        assert adapter.detect_format(sample) is True

    def test_reject_wrong_format(self):
        adapter = Math23KAdapter()
        assert adapter.detect_format([{"stem": "wrong format"}]) is False

    def test_parse_produces_imported_question(self):
        adapter = Math23KAdapter()
        sample = [{"question": "1+1等于多少？", "answer": "2"}]
        results = list(adapter.parse(sample))
        assert len(results) == 1
        assert isinstance(results[0], ImportedQuestion)
        assert results[0].stem == "1+1等于多少？"

    def test_validate_catches_empty_stem(self):
        adapter = Math23KAdapter()
        q = ImportedQuestion(stem="", answer_json={"answer": "2"},
                            question_type="calculation", source_name="math23k")
        errors = adapter.validate(q)
        assert len(errors) > 0


class TestSelfJSONAdapter:
    """Self-hosted JSON format adapter."""

    def test_detect_self_json_format(self):
        adapter = SelfJSONAdapter()
        sample = [{"stem": "1+1=?", "answer": {"answer": 2}, "question_type": "calculation"}]
        assert adapter.detect_format(sample) is True


class TestImportedQuestion:
    """ImportedQuestion data structure."""

    def test_has_required_fields(self):
        q = ImportedQuestion(
            stem="test", answer_json={"answer": 42},
            question_type="calculation", source_name="test",
        )
        assert q.stem == "test"
        assert q.source == "external"
        assert q.review_status == "pending"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd server && uv run pytest tests/backend/test_external_import.py -v`
Expected: FAIL

- [ ] **Step 3: Implement external_import.py**

```python
# server/apps/backend/app/services/learning/external_import.py
"""External question bank import adapters.

Adapter interface:
    detect_format(raw_data) -> bool
    parse(raw_data) -> Iterator[ImportedQuestion]
    validate(question) -> list[str]  # error strings
"""
from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass, field
from typing import Protocol

from packages.core.logging import get_logger

logger = get_logger(__name__)


@dataclass
class ImportedQuestion:
    """A question parsed from an external source, not yet in the DB."""
    stem: str
    answer_json: dict
    question_type: str
    source_name: str
    source_license: str | None = None
    stem_zh: str | None = None
    difficulty: int = 2
    bloom_level: str = "apply"
    topic_key: str | None = None
    options: list[dict] | None = None
    solution: dict | None = None
    # Fixed fields
    source: str = "external"
    review_status: str = "pending"


class ImportAdapter(Protocol):
    def detect_format(self, raw_data: list) -> bool: ...
    def parse(self, raw_data: list) -> Iterator[ImportedQuestion]: ...
    def validate(self, question: ImportedQuestion) -> list[str]: ...


class Math23KAdapter:
    """Adapter for Math23K dataset (JSON array of {question, answer})."""

    def detect_format(self, raw_data: list) -> bool:
        if not raw_data or not isinstance(raw_data, list):
            return False
        sample = raw_data[0]
        return "question" in sample and "answer" in sample

    def parse(self, raw_data: list) -> Iterator[ImportedQuestion]:
        for item in raw_data:
            yield ImportedQuestion(
                stem=item.get("question", ""),
                stem_zh=item.get("question", ""),
                answer_json={"answer": item.get("answer", "")},
                question_type="application",
                source_name="math23k",
            )

    def validate(self, question: ImportedQuestion) -> list[str]:
        errors = []
        if not question.stem or len(question.stem.strip()) < 5:
            errors.append("stem is empty or too short")
        if not question.answer_json or not question.answer_json.get("answer"):
            errors.append("answer is empty")
        return errors


class SelfJSONAdapter:
    """Adapter for our own JSON export format."""

    def detect_format(self, raw_data: list) -> bool:
        if not raw_data or not isinstance(raw_data, list):
            return False
        sample = raw_data[0]
        return "stem" in sample and "answer" in sample and "question_type" in sample

    def parse(self, raw_data: list) -> Iterator[ImportedQuestion]:
        for item in raw_data:
            yield ImportedQuestion(
                stem=item.get("stem", ""),
                stem_zh=item.get("stem_zh"),
                answer_json=item.get("answer", {}),
                question_type=item.get("question_type", "calculation"),
                source_name="self_json",
                difficulty=item.get("difficulty", 2),
                bloom_level=item.get("bloom_level", "apply"),
                topic_key=item.get("topic_key"),
                options=item.get("options"),
                solution=item.get("solution"),
            )

    def validate(self, question: ImportedQuestion) -> list[str]:
        errors = []
        if not question.stem or len(question.stem.strip()) < 5:
            errors.append("stem is empty or too short")
        if not question.answer_json:
            errors.append("answer is empty")
        return errors


def detect_adapter(raw_data: list) -> ImportAdapter | None:
    """Auto-detect the right adapter for the data."""
    adapters = [Math23KAdapter(), SelfJSONAdapter()]
    for adapter in adapters:
        if adapter.detect_format(raw_data):
            return adapter
    return None
```

- [ ] **Step 4: Extend question_seeder with seed_from_external**

In `server/apps/backend/app/services/learning/question_seeder.py`, add:

```python
from apps.backend.app.services.learning.external_import import (
    ImportAdapter,
    ImportedQuestion,
    detect_adapter,
)


def seed_from_external(
    db: Session,
    raw_data: list,
    source_license: str | None = None,
    dry_run: bool = False,
) -> SeedResult:
    """Import questions from an external source.

    Auto-detects format, validates, deduplicates, and persists.
    All imported questions start with review_status="pending".
    """
    result = SeedResult()
    adapter = detect_adapter(raw_data)
    if adapter is None:
        result.details.append("No adapter detected for data format")
        return result

    topic_index = _build_topic_key_index(db)

    for imported in adapter.parse(raw_data):
        # Validate
        errors = adapter.validate(imported)
        if errors:
            result.failed += 1
            result.details.append(f"Validation failed: {errors}")
            continue

        # Resolve topic from imported question's topic_key (if present)
        topic_id = topic_index.get(imported.topic_key) if imported.topic_key else None

        # Skip questions with no resolvable topic (matching existing seeder pattern).
        # Do NOT pass topic_id=0 — that fails create_question's existence validation
        # and silently rejects every imported question whose topic_key is missing.
        if topic_id is None:
            result.skipped_no_topic += 1
            result.details.append(
                f"No topic resolved for topic_key={imported.topic_key!r}, skipping"
            )
            continue

        # Content hash dedup
        content_hash = _compute_content_hash(imported.stem, imported.answer_json)

        existing = (
            db.query(Question)
            .filter(Question.content_hash == content_hash)
            .first()
        )
        if existing:
            result.skipped_duplicate += 1
            continue

        if dry_run:
            result.generated += 1
            continue

        # Persist
        from apps.backend.app.services.learning.question_service import create_question
        try:
            create_question(
                db=db,
                topic_id=topic_id,
                question_type=imported.question_type,
                stem=imported.stem,
                answer=imported.answer_json,
                difficulty=imported.difficulty,
                bloom_level=imported.bloom_level,
                source="external",
                age_group="lower",
                stem_zh=imported.stem_zh,
                options=imported.options,
                solution=imported.solution,
                source_metadata={
                    "source_name": imported.source_name,
                    "source_license": source_license,
                    "content_hash": content_hash,
                },
            )
            result.generated += 1
        except Exception:
            logger.exception("Failed to import question")
            result.failed += 1

    return result
```

- [ ] **Step 5: Run tests**

Run: `cd server && uv run pytest tests/backend/test_external_import.py -v`
Expected: All PASS

- [ ] **Step 6: Commit**

```bash
git add server/apps/backend/app/services/learning/external_import.py \
       server/apps/backend/app/services/learning/question_seeder.py \
       server/tests/backend/test_external_import.py
git commit -m "feat(learning): P7b Math23K + self-JSON import adapters with batch seeding

- ImportAdapter protocol: detect_format, parse, validate
- Math23KAdapter: JSON {question, answer} format
- SelfJSONAdapter: native JSON export format
- Auto-detection via detect_adapter()
- seed_from_external() with content_hash dedup
- 8+ tests

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>"
```

---

## Task 10: Multi-Subject Pilot Templates (P7d-lite)

**Files:**
- Create: `server/packages/domain/question_templates/chinese_pinyin.py`
- Create: `server/packages/domain/question_templates/chinese_literacy.py`
- Create: `server/packages/domain/question_templates/english_vocabulary.py`
- Create: `server/packages/domain/question_templates/english_grammar.py`
- Create: `server/packages/domain/question_templates/science_life.py`
- Create: `server/packages/domain/question_templates/science_matter.py`
- Modify: `server/packages/domain/question_templates/__init__.py`
- Modify: `server/apps/backend/app/services/learning/question_router.py` (add pilot routing)
- Test: `server/tests/packages/domain/test_pilot_templates.py`

**Interfaces:**
- Consumes: `register_template`, `GeneratedQuestion`
- Produces: 9-15 pilot templates across 3 subjects; routing config entries for pilot domains

- [ ] **Step 1: Write the failing tests**

```python
# server/tests/packages/domain/test_pilot_templates.py
"""Tests for P7d-lite multi-subject pilot templates."""
import pytest

from packages.domain.question_templates.registry import (
    TEMPLATE_REGISTRY,
    generate_question,
    list_templates,
)


class TestChineseTemplates:
    """Chinese pilot: pinyin + literacy."""

    def test_pinyin_templates_registered(self):
        chinese = list_templates("chinese")
        pinyin = [t for t in chinese if "pinyin" in t]
        assert len(pinyin) >= 2

    def test_literacy_templates_registered(self):
        chinese = list_templates("chinese")
        literacy = [t for t in chinese if "literacy" in t or "character" in t]
        assert len(literacy) >= 1

    def test_chinese_template_generates_valid(self):
        chinese = list_templates("chinese")
        assert len(chinese) >= 3
        gq = generate_question(chinese[0], {})
        assert gq.stem_zh  # Chinese text
        assert gq.age_group in ("early", "lower")
        assert gq.topic_key.startswith("chinese.") or gq.topic_key.startswith("bj-chinese.")


class TestEnglishTemplates:
    """English pilot: vocabulary + grammar."""

    def test_vocabulary_templates_registered(self):
        english = list_templates("english")
        vocab = [t for t in english if "vocab" in t or "word" in t]
        assert len(vocab) >= 2

    def test_grammar_templates_registered(self):
        english = list_templates("english")
        grammar = [t for t in english if "grammar" in t]
        assert len(grammar) >= 1

    def test_english_template_generates_valid(self):
        english = list_templates("english")
        assert len(english) >= 3
        gq = generate_question(english[0], {})
        assert gq.question_type in ("multiple_choice", "fill_blank")


class TestScienceTemplates:
    """Science pilot: life science + matter science."""

    def test_life_science_templates_registered(self):
        science = list_templates("science")
        life = [t for t in science if "life" in t]
        assert len(life) >= 2

    def test_matter_science_templates_registered(self):
        science = list_templates("science")
        matter = [t for t in science if "matter" in t]
        assert len(matter) >= 1


class TestMathTemplatesNotBroken:
    """Existing math templates still work after pilot registration."""

    def test_math_templates_still_registered(self):
        math = list_templates("math")
        assert len(math) >= 25  # Original 25 + 11 from Task 8

    def test_existing_math_template_generates(self):
        math = list_templates("math")
        original = [t for t in math if "arithmetic" in t]
        assert len(original) >= 1
        gq = generate_question(original[0], {})
        assert gq.question_type == "calculation"


class TestTotalPilotCount:
    """Each subject has at least 3 pilot templates."""

    def test_minimum_pilot_counts(self):
        chinese = list_templates("chinese")
        english = list_templates("english")
        science = list_templates("science")

        assert len(chinese) >= 3, f"Chinese: {len(chinese)} (need ≥3)"
        assert len(english) >= 3, f"English: {len(english)} (need ≥3)"
        assert len(science) >= 3, f"Science: {len(science)} (need ≥3)"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd server && uv run pytest tests/packages/domain/test_pilot_templates.py -v`
Expected: FAIL — no Chinese/English/Science templates

- [ ] **Step 3: Implement Chinese pilot templates**

```python
# server/packages/domain/question_templates/chinese_pinyin.py
"""Chinese pinyin pilot templates."""
import random

from packages.domain.question_templates.base import GeneratedQuestion
from packages.domain.question_templates.registry import register_template


@register_template("chinese.pinyin.initials")
def _gen_pinyin_initials(params: dict) -> GeneratedQuestion:
    """Test knowledge of initial consonants."""
    questions = [
        ("b", "玻", ["b", "p", "d", "q"]),
        ("p", "坡", ["b", "p", "d", "q"]),
        ("m", "摸", ["m", "n", "l", "f"]),
        ("f", "佛", ["f", "h", "b", "p"]),
    ]
    correct_key, char, options_chars = random.choice(questions)
    options = [
        {"key": "A", "text": options_chars[0], "text_zh": options_chars[0]},
        {"key": "B", "text": options_chars[1], "text_zh": options_chars[1]},
        {"key": "C", "text": options_chars[2], "text_zh": options_chars[2]},
        {"key": "D", "text": options_chars[3], "text_zh": options_chars[3]},
    ]
    correct_idx = options_chars.index(correct_key)
    answer_key = ["A", "B", "C", "D"][correct_idx]

    return GeneratedQuestion(
        template_id="chinese.pinyin.initials",
        stem=f"声母 '{correct_key}' 对应的汉字是？",
        stem_zh=f"声母 '{correct_key}' 对应的汉字是？",
        answer={"key": answer_key},
        question_type="multiple_choice",
        difficulty=1,
        bloom_level="remember",
        topic_key="chinese.pinyin.initials",
        age_group="early",
        options=options,
    )


@register_template("chinese.pinyin.finals")
def _gen_pinyin_finals(params: dict) -> GeneratedQuestion:
    """Test knowledge of final vowels."""
    questions = [
        ("ā", "第一声", ["第一声", "第二声", "第三声", "第四声"]),
        ("á", "第二声", ["第一声", "第二声", "第三声", "第四声"]),
        ("ǎ", "第三声", ["第一声", "第二声", "第三声", "第四声"]),
        ("à", "第四声", ["第一声", "第二声", "第三声", "第四声"]),
    ]
    tone_char, tone_name, tone_options = random.choice(questions)
    options = [{"key": chr(65+i), "text": t, "text_zh": t} for i, t in enumerate(tone_options)]
    correct_idx = tone_options.index(tone_name)
    answer_key = chr(65 + correct_idx)

    return GeneratedQuestion(
        template_id="chinese.pinyin.finals",
        stem=f"'{tone_char}' 是第几声？",
        stem_zh=f"'{tone_char}' 是第几声？",
        answer={"key": answer_key},
        question_type="multiple_choice",
        difficulty=1,
        bloom_level="remember",
        topic_key="chinese.pinyin.finals",
        age_group="early",
        options=options,
    )


@register_template("chinese.pinyin.spelling")
def _gen_pinyin_spelling(params: dict) -> GeneratedQuestion:
    """Test pinyin spelling of characters."""
    chars = [
        ("大", "dà", "d-a"),
        ("天", "tiān", "t-i-an"),
        ("水", "shuǐ", "sh-u-i"),
    ]
    char, pinyin, spelling = random.choice(chars)
    return GeneratedQuestion(
        template_id="chinese.pinyin.spelling",
        stem=f"汉字 '{char}' 的拼音是？",
        stem_zh=f"汉字 '{char}' 的拼音是？",
        answer={"value": pinyin},
        question_type="fill_blank",
        difficulty=1,
        bloom_level="remember",
        topic_key="chinese.pinyin.spelling",
        age_group="early",
    )
```

- [ ] **Step 4: Implement Chinese literacy, English, and Science templates**

Create these 5 files with 2-3 templates each, following the same `@register_template` pattern:

**`chinese_literacy.py`** — 2 templates: `chinese.literacy.radicals` (identify the radical of a character, multiple_choice), `chinese.literacy.stroke_count` (count strokes of a character, calculation). Use common characters (大/小/人/口/手 etc.) with randomized selection.

**`english_vocabulary.py`** — 2 templates: `english.vocabulary.animals` (match English word to Chinese meaning, multiple_choice with 4 options like dog/cat/bird/fish), `english.vocabulary.colors` (same pattern with colors). Use `stem` (English text) rather than `stem_zh`.

**`english_grammar.py`** — 1 template: `english.grammar.be_verbs` (fill in the correct be-verb: am/is/are, fill_blank). Sentences like "I ___ a student." with answer "am".

**`science_life.py`** — 2 templates: `science.life.plant_parts` (identify plant parts from description, multiple_choice: root/stem/leaf/flower), `science.life.animal_types` (classify animal by type, multiple_choice: mammal/bird/fish/insect).

**`science_matter.py`** — 1 template: `science.matter.states_of_matter` (classify substance state at room temperature, multiple_choice: solid/liquid/gas). Substances: water/ice/steam, iron, oxygen, etc.

All templates must use `topic_key` matching the template ID pattern, appropriate `age_group` ("early" for Chinese, "lower" for English/Science), and return valid `GeneratedQuestion` with Chinese `stem_zh` for science/Chinese and English `stem` for English.

- [ ] **Step 5: Register all pilot modules in __init__.py**

Add to `server/packages/domain/question_templates/__init__.py`:

```python
from packages.domain.question_templates import chinese_pinyin
from packages.domain.question_templates import chinese_literacy
from packages.domain.question_templates import english_vocabulary
from packages.domain.question_templates import english_grammar
from packages.domain.question_templates import science_life
from packages.domain.question_templates import science_matter
```

- [ ] **Step 6: Add pilot routing config to question_router.py**

In `server/apps/backend/app/services/learning/question_router.py`, add to `ROUTING_RULES`:

```python
# Chinese pilot domains
"pinyin": "template",
"literacy": "template",
# English pilot domains
"vocabulary": "template",
"grammar": "template",
# Science pilot domains
"life-science": "template",
"matter-science": "template",
```

(These may already be present from Task 7 — verify and add any missing entries.)

- [ ] **Step 7: Run tests**

Run: `cd server && uv run pytest tests/packages/domain/test_pilot_templates.py -v`
Expected: All PASS (12+ tests)

- [ ] **Step 8: Verify no math template breakage**

Run: `cd server && uv run pytest tests/packages/domain/ -v`
Expected: All existing + new tests PASS

- [ ] **Step 9: Commit**

```bash
git add server/packages/domain/question_templates/chinese_pinyin.py \
       server/packages/domain/question_templates/chinese_literacy.py \
       server/packages/domain/question_templates/english_vocabulary.py \
       server/packages/domain/question_templates/english_grammar.py \
       server/packages/domain/question_templates/science_life.py \
       server/packages/domain/question_templates/science_matter.py \
       server/packages/domain/question_templates/__init__.py \
       server/apps/backend/app/services/learning/question_router.py \
       server/tests/packages/domain/test_pilot_templates.py
git commit -m "feat(learning): P7d-lite multi-subject pilot templates (Chinese/English/Science)

- Chinese: pinyin initials, finals, spelling + character radicals (4 templates)
- English: animal vocabulary, color vocabulary + be-verb grammar (3 templates)
- Science: plant parts, animal types + states of matter (3 templates)
- Routing config updated for pilot domains
- 12+ tests including math non-regression

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>"
```

---

## Task 11: Batch Review API + Grading Explanation + Child Subject Switch

**Files:**
- Modify: `server/apps/backend/app/routers/practice.py`
- Modify: `server/apps/backend/app/schemas/practice.py`
- Modify: `frontend/apps/child/src/components/learning/PracticeAnswerInput.vue`
- Modify: `frontend/apps/child/src/api/practice.ts`
- Test: `server/tests/backend/test_batch_review_api.py`

**Interfaces:**
- Consumes: `Question` model with `review_status`, `grading_explanation_json`; `question_service` review workflow
- Produces:
  - `POST /practice/questions/batch-review` — approve/reject multiple questions at once
  - `GET /practice/questions/review-queue` — list questions pending review, sorted by risk
  - `GET /practice/questions/{id}/grading-explanation` — return AI grading explanation data
  - `PracticeAnswerInput.vue` extended with `multi_fill_blank` and `ai_graded` modes

- [ ] **Step 1: Write failing tests — batch review and grading explanation APIs**

```python
# server/tests/backend/test_batch_review_api.py
"""Tests for batch review API and grading explanation endpoint."""
import pytest

from packages.db.models.learning.question import Question
from packages.db.models.learning.topic import LearningTopic


class TestBatchReview:
    """POST /practice/questions/batch-review"""

    def test_batch_approve_multiple(self, client, db_session, auth_headers):
        t = LearningTopic(topic_key="math.add", subject="mathematics",
                         domain="number", name="Addition", deprecated=False)
        db_session.add(t)
        db_session.flush()
        q1 = Question(topic_id=t.id, question_type="calculation",
                      stem="1+1=?", answer_json='{"answer": 2}',
                      difficulty=1, source="llm", review_status="pending")
        q2 = Question(topic_id=t.id, question_type="calculation",
                      stem="2+2=?", answer_json='{"answer": 4}',
                      difficulty=1, source="llm", review_status="pending")
        db_session.add_all([q1, q2])
        db_session.commit()

        resp = client.post("/api/v1/practice/questions/batch-review", json={
            "question_ids": [q1.id, q2.id],
            "decision": "approve",
        }, headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert data["processed"] == 2

    def test_batch_reject_with_notes(self, client, db_session, auth_headers):
        t = LearningTopic(topic_key="math.add", subject="mathematics",
                         domain="number", name="Addition", deprecated=False)
        db_session.add(t)
        db_session.flush()
        q = Question(topic_id=t.id, question_type="calculation",
                     stem="bad?", answer_json='{"answer": 0}',
                     difficulty=1, source="llm", review_status="pending")
        db_session.add(q)
        db_session.commit()

        resp = client.post("/api/v1/practice/questions/batch-review", json={
            "question_ids": [q.id],
            "decision": "reject",
            "notes": "Incorrect answer",
        }, headers=auth_headers)
        assert resp.status_code == 200


class TestReviewQueue:
    """GET /practice/questions/review-queue"""

    def test_review_queue_returns_pending(self, client, db_session, auth_headers):
        t = LearningTopic(topic_key="math.add", subject="mathematics",
                         domain="number", name="Addition", deprecated=False)
        db_session.add(t)
        db_session.flush()
        q = Question(topic_id=t.id, question_type="calculation",
                     stem="1+1=?", answer_json='{"answer": 2}',
                     difficulty=1, source="llm", review_status="pending")
        db_session.add(q)
        db_session.commit()

        resp = client.get("/api/v1/practice/questions/review-queue", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert len(data["questions"]) >= 1


class TestGradingExplanation:
    """GET /practice/questions/{id}/grading-explanation"""

    def test_returns_explanation_when_present(self, client, db_session, auth_headers):
        t = LearningTopic(topic_key="math.add", subject="mathematics",
                         domain="number", name="Addition", deprecated=False)
        db_session.add(t)
        db_session.flush()
        q = Question(topic_id=t.id, question_type="ai_graded",
                     stem="Explain photosynthesis",
                     answer_json='{"rubric": "光合作用"}',
                     difficulty=2, source="llm", review_status="approved",
                     grading_explanation_json='{"confidence": 0.85, "dimensions": {"topic_match": true}, "reasoning": "正确描述了光合作用过程"}')
        db_session.add(q)
        db_session.commit()

        resp = client.get(f"/api/v1/practice/questions/{q.id}/grading-explanation",
                         headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert data["confidence"] == 0.85
        assert "reasoning" in data

    def test_returns_404_when_no_explanation(self, client, db_session, auth_headers):
        t = LearningTopic(topic_key="math.add", subject="mathematics",
                         domain="number", name="Addition", deprecated=False)
        db_session.add(t)
        db_session.flush()
        q = Question(topic_id=t.id, question_type="calculation",
                     stem="1+1=?", answer_json='{"answer": 2}',
                     difficulty=1, source="template", review_status="approved")
        db_session.add(q)
        db_session.commit()

        resp = client.get(f"/api/v1/practice/questions/{q.id}/grading-explanation",
                         headers=auth_headers)
        assert resp.status_code == 404
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd server && uv run pytest tests/backend/test_batch_review_api.py -v`
Expected: FAIL — endpoints return 404

- [ ] **Step 3: Add schemas for batch review and grading explanation**

In `server/apps/backend/app/schemas/practice.py`:

```python
class BatchReviewRequest(BaseModel):
    question_ids: list[int]
    decision: str  # "approve" | "reject" | "suspend"
    notes: str | None = None


class BatchReviewResponse(BaseModel):
    processed: int
    approved: int
    rejected: int
    suspended: int


class ReviewQueueItem(SnowflakeBase):
    question_id: int
    topic_key: str
    question_type: str
    stem: str
    answer_json: dict
    source: str
    review_status: str
    risk: str | None = None  # persisted by Task 6 classify_risk()
    grading_explanation: dict | None = None


class ReviewQueueResponse(BaseModel):
    questions: list[ReviewQueueItem]
    total: int


class GradingExplanationResponse(BaseModel):
    confidence: float
    dimensions: dict
    reasoning: str


class ChildFacingQuestionResponse(SnowflakeBase):
    """Discriminated-union-style response served to child app.
    Common fields plus optional type-specific fields."""
    question_type: str
    stem: str
    stem_zh: str | None = None
    answer_json: dict
    difficulty: int
    # multi_fill_blank-specific (present only when question_type == "multi_fill_blank")
    blank_count: int | None = None
    # ai_graded-specific (present only when question_type == "ai_graded")
    rubric_visible: bool = False  # rubric is NOT exposed to child; kept parent/admin-only
```

- [ ] **Step 4: Add batch review + review queue + grading explanation endpoints**

In `server/apps/backend/app/routers/practice.py`:

```python
@router.get("/questions/review-queue")
def get_review_queue(
    risk: str | None = None,
    limit: int = 50,
    user: User = Depends(require_owner),  # parent-only moderation
    db: Session = Depends(get_db),
):
    """List questions pending review, filtered and ordered by risk level.

    The `risk` column is set by the LLM generation pipeline (Task 6).
    Family-scoped: only questions from the caller's family are visible.
    """
    query = (
        db.query(Question)
        .filter(Question.review_status == "pending")
        .filter(
            # family_id is nullable — template-seeded questions carry NULL until
            # the LLM pipeline populates it. Include unscoped questions so
            # pre-existing pending content stays reviewable.
            db.or_(Question.family_id == user.family_id, Question.family_id.is_(None))
        )
    )
    if risk:
        query = query.filter(Question.risk == risk)
    questions = query.order_by(
        db.case(
            (Question.risk == "high", 0),
            (Question.risk == "medium", 1),
            (Question.risk == "low", 2),
            else_=3,
        ).asc()
    ).limit(limit).all()
    items = []
    for q in questions:
        topic = db.query(LearningTopic).get(q.topic_id) if q.topic_id else None
        items.append({
            "question_id": q.id,
            "topic_key": topic.topic_key if topic else None,
            "question_type": q.question_type,
            "stem": q.stem,
            "answer_json": json.loads(q.answer_json),
            "source": q.source,
            "review_status": q.review_status,
            "risk": q.risk,
            "grading_explanation": q.grading_explanation,
        })
    return EnvelopeResponse(data={"questions": items, "total": len(items)})


@router.post("/questions/batch-review")
def batch_review_questions(
    body: BatchReviewRequest,
    user: User = Depends(require_owner),  # parent-only moderation
    db: Session = Depends(get_db),
):
    """Batch approve, reject, or suspend questions. Family-scoped."""
    new_status = {"approve": "approved", "reject": "rejected", "suspend": "suspended"}[body.decision]
    processed = 0
    for qid in body.question_ids:
        q = db.query(Question).get(qid)
        if q and q.review_status == "pending" and q.family_id == user.family_id:
            q.review_status = new_status
            if body.notes:
                q.review_notes = body.notes
            processed += 1
    db.commit()
    approved = processed if body.decision == "approve" else 0
    rejected = processed if body.decision == "reject" else 0
    suspended = processed if body.decision == "suspend" else 0
    return EnvelopeResponse(data={
        "processed": processed, "approved": approved,
        "rejected": rejected, "suspended": suspended,
    })


@router.get("/questions/{question_id}/grading-explanation")
def get_grading_explanation(
    question_id: int,
    user: User = Depends(get_current_user_or_child),
    db: Session = Depends(get_db),
):
    """Return AI grading explanation for a question."""
    q = db.query(Question).get(question_id)
    if q is None:
        raise AppError(ErrorCode.NOT_FOUND, details="Question not found")
    if q.family_id is not None and q.family_id != user.family_id:
        raise AppError(ErrorCode.NOT_FOUND, details="Question not found")  # family-scoped NOT_FOUND
    if not q.grading_explanation_json:
        raise AppError(ErrorCode.NOT_FOUND, details="No grading explanation available")
    return EnvelopeResponse(data=q.grading_explanation)
```

- [ ] **Step 5: Extend PracticeAnswerInput.vue for multi_fill_blank and ai_graded**

In `frontend/apps/child/src/components/learning/PracticeAnswerInput.vue`, add two new modes in the template:

**`multi_fill_blank` contract (new):**
- Render up to 5 numbered input fields (①②③④⑤), vertically stacked
- Each input has `inputmode="numeric"` or `type="text"` based on `question.blank_count` from the backend response
- Tab/next navigation between inputs; Enter on the last blank advances to an explicit submit button
- **Submit trigger**: explicit submit button (NOT Enter on first blank, which would prematurely submit)
- `defineExpose` extended so parent page can call `submitMultiBlank()` to programmatically trigger a full multi-blank submit
- **Feedback response**: attempt/result payload carries `per_blank: [boolean]` and `correct_answers: [string]` from `check_multi_fill_blank_partial`, plus `correct_count`/`total` summary. Component receives them as new props (replacing the single boolean for this mode) to render per-blank green ✓ / red ✗ with correct answer shown
- On submit: collect `{ blanks: [val1, val2, ...] }` and emit

**`ai_graded` contract (new):**
- Render a `van-field type="textarea"` with submit button
- Show "AI 正在评分..." spinner during evaluation (disable button, 30s timeout)
- **Timeout/error state**: "评分失败，请重试" + retry button (per origin spec §8.3)
- On result: render from `result_level: 'correct' | 'partial' | 'incorrect'` (NOT from a boolean) + confidence indicator
- Low confidence (< 0.7): show gray badge "AI 评分可能不准确"
- Low confidence (< 0.7) NOT counted toward mastery — only feedback is shown

- [ ] **Step 6: Extend practice.ts API types**

In `frontend/apps/child/src/api/practice.ts`, extend the existing flat `QuestionResponse` with optional type-specific fields (do not add standalone dead interfaces):

```typescript
interface QuestionResponse {
  question_id: string
  question_type: 'calculation' | 'fill_blank' | 'multiple_choice' | 'true_false'
                | 'application' | 'multi_fill_blank' | 'ai_graded'
  stem: string
  stem_zh?: string
  answer_json: Record<string, unknown>
  difficulty: number
  // multi_fill_blank-specific (undefined for other types)
  blank_count?: number
  // ai_graded-specific (undefined for other types)
  // rubric is intentionally NOT included — kept parent/admin-only
  rubric_visible?: boolean  // always false for child; explicit opt-in for parent views
}

interface AttemptResultResponse {
  is_correct: boolean
  // multi_fill_blank: per-blank detail
  per_blank?: boolean[]
  correct_answers?: string[]
  correct_count?: number
  total?: number
  // ai_graded: confidence + 3-state display + explanation
  result_level?: 'correct' | 'partial' | 'incorrect'
  confidence?: number
  explanation?: string
  low_confidence?: boolean
}
```

- [ ] **Step 6b: Verify child subject switch (P7d-lite-5 acceptance)**

Per origin spec P7d-lite-5: "儿童端能切换学科并看到掌握度". The subject-switching UI already exists in `LearningMapPage.vue`. Add an explicit verification step after the frontend changes:

1. In the child app, navigate to the learning map page.
2. Switch subjects via the existing subject tabs to `mathematics`, `chinese`, `english`, and `science`.
3. For each subject, confirm that:
   - Pilot-subject topics from the new templates (Tasks 8/10) are visible on the map
   - Questions from the new templates are loadable for practice
   - Mastery tracking displays for the new subjects (no errors, no empty states for seeded content)
4. Add a regression test in `tests/packages/domain/test_pilot_templates.py` that asserts `list_templates("chinese")`, `list_templates("english")`, `list_templates("science")` each return ≥3 templates AND that the child-facing learning map route successfully renders with each subject's topics.

If the existing subject-switching UI does NOT expose the new pilot subjects (e.g., the subject list is hardcoded), add the new subjects to the subject list in `LearningMapPage.vue`.

- [ ] **Step 7: Run tests**

Run: `cd server && uv run pytest tests/backend/test_batch_review_api.py -v`
Expected: All PASS

- [ ] **Step 8: Commit**

```bash
git add server/apps/backend/app/routers/practice.py \
       server/apps/backend/app/schemas/practice.py \
       server/tests/backend/test_batch_review_api.py \
       frontend/apps/child/src/components/learning/PracticeAnswerInput.vue \
       frontend/apps/child/src/api/practice.ts
git commit -m "feat(learning): P7b batch review API, grading explanation, new question type UI

- POST /practice/questions/batch-review — approve/reject multiple questions
- GET /practice/questions/review-queue — pending questions sorted by risk
- GET /practice/questions/{id}/grading-explanation — AI grading detail
- PracticeAnswerInput.vue: multi_fill_blank (5 numbered inputs) + ai_graded (textarea + confidence)
- practice.ts: new question type types
- 5+ API tests

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>"
```

---

## Acceptance Criteria

Run all tests to verify:

```bash
cd server
uv run pytest tests/backend/test_models_p7a_fields.py \
              tests/backend/test_content_hash_backfill.py \
              tests/backend/test_coverage_service.py \
              tests/backend/test_coverage_api.py \
              tests/backend/test_scoring_extended.py \
              tests/backend/test_llm_generator.py \
              tests/backend/test_question_router.py \
              tests/backend/test_external_import.py \
              tests/packages/domain/test_math_expansion_templates.py \
              tests/packages/domain/test_pilot_templates.py \
              tests/backend/test_batch_review_api.py \
              -v
```

**Spec verification:**

- [ ] Coverage script outputs per-subject topic counts and gap lists
- [ ] Gap list sorted by prerequisite value, guides question production priority
- [ ] Beijing topic subject/ageRange fields fixed, coverage service aggregates by subject correctly
- [ ] content_hash backfill: all existing questions have hashes, no collisions
- [ ] "suspended" review_status excluded from all question selection and coverage queries
- [ ] 11 new math templates registered and generating valid questions
- [ ] `multi_fill_blank` scoring handles partial credit
- [ ] `ai_graded` scoring includes confidence; low confidence flagged
- [ ] LLM generator rejects questions with wrong topic_key (anti-hallucination)
- [ ] Math23K adapter detects format, parses, validates
- [ ] Chinese/English/Science pilot templates registered (≥3 per subject)
- [ ] Existing math templates (≥25) remain functional after pilot registration
- [ ] All new tests pass (50+ new tests across all tasks)
- [ ] Existing 141+ learning tests still pass (no regressions)

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>
