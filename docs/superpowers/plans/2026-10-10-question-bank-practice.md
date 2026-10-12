# 儿童题库与自适应练习系统实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 让 8 岁儿童能在知识地图上选择"两位数加法"知识点，完成 5 道参数化计算题，获得即时反馈、XP 奖励和掌握状态推进。

**Architecture:** 新增 4 张表（questions, question_knowledge_points, practice_sessions, practice_attempts），自建参数化题目模板引擎（数学 MVP 4 模板），规则引擎驱动自适应选题（按 mastery_level 匹配难度），与现有 LearningProgress 状态机通过 `completed_via="practice_session"` 打通。

**Tech Stack:** Python 3.12 + SQLAlchemy + FastAPI + Pydantic v2 + Alembic + Vue 3 + TypeScript + Vant 4

**Spec:** [docs/superpowers/specs/2026-10-10-question-bank-adaptive-practice-design.md](../specs/2026-10-10-question-bank-adaptive-practice-design.md)

---

## Global Constraints

- 所有 ID 使用 Snowflake ID（BigInteger），API 响应通过 SnowflakeBase 序列化为 string
- 时间字段使用 `UTCDateTime()` TypeDecorator
- JSON 字段使用 `json_text()` 辅助函数
- 错误使用 `AppError(ErrorCode.XXX)`，HTTP 状态码映射在 codes.py
- 路由无前导斜杠：`@router.get("")` 不用 `@router.get("/")`
- 前端所有字符串走 i18n `t('key')`，不硬编码中文
- 测试使用 in-memory SQLite + SAVEPOINT 隔离（conftest.py db fixture）

## Review Focus

1. **topic_id 不存在** → 创建题目/练习时 404
2. **user_answer JSON 结构不匹配** → 400 而非 500
3. **completed_via 非法值** → progress_service 抛 ValueError
4. **同一题同一会话重复提交** → 只记录第一次
5. **去重 7 天边界** → `now() - 7 days` 精确计算

---

## File Structure

```
server/
├── packages/db/models/learning/
│   ├── question.py                    # Question + QuestionKnowledgePoint
│   └── practice.py                    # PracticeSession + PracticeAttempt
├── packages/domain/question_templates/
│   ├── __init__.py                    # Public API
│   ├── base.py                        # GeneratedQuestion dataclass
│   ├── registry.py                    # 模板注册表
│   └── math_arithmetic.py             # 算术模板 (10+ 个)
├── apps/backend/app/
│   ├── routers/practice.py            # 练习 API 路由
│   ├── schemas/practice.py            # Pydantic schemas
│   ├── services/learning/
│   │   ├── question_service.py        # 题目 CRUD + 质量关卡
│   │   ├── practice_service.py        # 练习会话管理
│   │   ├── scoring_service.py         # 自动评分
│   │   ├── adaptive_service.py        # 选题引擎 + MasteryEstimator
│   │   └── practice_progress_integration.py  # 练习→进度状态机桥接
│   └── errors/codes.py                # PRACTICE_* 错误码
├── apps/backend/alembic/versions/
│   └── prac001_add_questions_and_practice.py
└── tests/
    ├── backend/
    │   ├── routers/test_practice.py
    │   └── services/
    │       ├── test_question_service.py
    │       ├── test_practice_service.py
    │       ├── test_scoring_service.py
    │       └── test_adaptive_service.py
    └── packages/domain/
        └── test_template_registry.py

frontend/apps/child/src/
├── api/practice.ts                    # 练习 API 封装
├── pages/learning/
│   └── PracticeSessionPage.vue        # 练习会话页面
├── components/learning/
│   ├── PracticeQuestionCard.vue       # 题目渲染
│   ├── PracticeAnswerInput.vue        # 答题输入
│   └── PracticeResultSummary.vue      # 结果汇总
└── router/index.ts                    # 新增 PracticeSession 路由
```

---

### Task 1: 数据库模型与迁移

**Files:**
- Create: `server/packages/db/models/learning/question.py`
- Create: `server/packages/db/models/learning/practice.py`
- Modify: `server/packages/db/models/learning/__init__.py`
- Create: `server/apps/backend/alembic/versions/prac001_add_questions_and_practice.py`
- Test: `server/tests/packages/db/test_models_practice.py`

**Interfaces:**
- Consumes: `Base, next_id, UTCDateTime, json_text`
- Produces: `Question, QuestionKnowledgePoint, PracticeSession, PracticeAttempt`

- [ ] **Step 1: Write failing model tests**

```python
# server/tests/packages/db/test_models_practice.py
"""Tests for question and practice ORM models."""
import pytest
from sqlalchemy.orm import Session

from packages.db.models.learning.question import Question, QuestionKnowledgePoint
from packages.db.models.learning.practice import PracticeSession, PracticeAttempt
from packages.db.models.learning.topic import LearningTopic


@pytest.fixture
def topic(db: Session):
    t = LearningTopic(
        topic_key="mt_test_math",
        topic_type="concept",
        subject="mathematics",
        domain="arithmetic",
        name="Two-digit addition",
        name_zh="两位数加法",
        age_group="mid",
        evidence_json="[]",
        standards_json="[]",
    )
    db.add(t)
    db.flush()
    return t


def test_question_creation(db: Session, topic):
    q = Question(
        topic_id=topic.id,
        question_type="calculation",
        stem="37 + 58 = ?",
        stem_zh="计算：37 + 58 = ?",
        answer_json='{"answer": 95}',
        difficulty=1,
        bloom_level="apply",
        source="template",
        review_status="approved",
        age_group="mid",
    )
    db.add(q)
    db.flush()
    assert q.id is not None
    assert q.topic_id == topic.id
    assert q.times_used == 0


def test_question_json_accessors(db: Session, topic):
    q = Question(
        topic_id=topic.id,
        question_type="multiple_choice",
        stem="Which is prime?",
        options_json='[{"key":"A","text":"4"},{"key":"B","text":"7"}]',
        answer_json='{"key": "B"}',
        difficulty=2,
        bloom_level="understand",
        source="human_created",
        review_status="approved",
        age_group="mid",
    )
    db.add(q)
    db.flush()
    assert q.options == [{"key": "A", "text": "4"}, {"key": "B", "text": "7"}]
    assert q.answer == {"key": "B"}


def test_practice_session_creation(db: Session, topic):
    s = PracticeSession(
        child_id=1,
        topic_id=topic.id,
        session_mode="practice",
        question_ids_json="[1,2,3]",
        source="adaptive",
    )
    db.add(s)
    db.flush()
    assert s.id is not None
    assert s.question_ids == [1, 2, 3]


def test_practice_attempt_creation(db: Session, topic):
    s = PracticeSession(
        child_id=1,
        topic_id=topic.id,
        session_mode="practice",
        question_ids_json="[1]",
        source="adaptive",
    )
    db.add(s)
    db.flush()
    a = PracticeAttempt(
        session_id=s.id,
        question_id=1,
        child_id=1,
        topic_id=topic.id,
        user_answer_json='{"answer": 95}',
        is_correct=True,
        time_spent_seconds=15,
        attempt_number=1,
    )
    db.add(a)
    db.flush()
    assert a.id is not None
    assert a.user_answer == {"answer": 95}
```

- [ ] **Step 2: Run test to verify failure**

```bash
cd server && uv run pytest tests/packages/db/test_models_practice.py -v
```

Expected: FAIL — `ModuleNotFoundError: No module named 'packages.db.models.learning.question'`

- [ ] **Step 3: Create Question model**

```python
# server/packages/db/models/learning/question.py
"""Question bank models."""
from datetime import datetime

from sqlalchemy import (
    BigInteger, Float, ForeignKey, Index, Integer, String, Text, UniqueConstraint, func,
)
from sqlalchemy.orm import Mapped, mapped_column

from packages.core.snowflake import next_id
from packages.db.mixins.json_text import json_text
from packages.db.session import Base, UTCDateTime


class Question(Base):
    """A practice question linked to a knowledge point."""
    __tablename__ = "questions"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, default=next_id)
    topic_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("learning_topics.id"), nullable=False, index=True
    )
    question_type: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    stem: Mapped[str] = mapped_column(Text, nullable=False)
    stem_zh: Mapped[str | None] = mapped_column(Text, nullable=True)
    options_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    answer_json: Mapped[str] = mapped_column(Text, nullable=False)
    solution_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    difficulty: Mapped[int] = mapped_column(Integer, nullable=False, default=1, index=True)
    bloom_level: Mapped[str] = mapped_column(String(20), nullable=False, default="apply")
    source: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    source_version: Mapped[str | None] = mapped_column(String(50), nullable=True)
    review_status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="pending", index=True
    )
    review_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    age_group: Mapped[str] = mapped_column(String(10), nullable=False, index=True)
    parameters_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    times_used: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    correct_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        UTCDateTime(), server_default=func.now(), onupdate=func.now()
    )

    # JSON accessors
    options: list | None = json_text("options_json")
    answer: dict = json_text("answer_json")
    solution: dict | None = json_text("solution_json")
    parameters: dict | None = json_text("parameters_json")


class QuestionKnowledgePoint(Base):
    """Many-to-many link between questions and knowledge points."""
    __tablename__ = "question_knowledge_points"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, default=next_id)
    question_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("questions.id"), nullable=False, index=True
    )
    topic_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("learning_topics.id"), nullable=False, index=True
    )
    role: Mapped[str] = mapped_column(String(20), nullable=False, default="primary")

    __table_args__ = (
        UniqueConstraint("question_id", "topic_id", name="uq_question_topic"),
    )
```

- [ ] **Step 4: Create Practice models**

```python
# server/packages/db/models/learning/practice.py
"""Practice session and attempt models."""
from datetime import datetime

from sqlalchemy import (
    BigInteger, Boolean, Float, ForeignKey, Index, Integer, String, Text, func,
)
from sqlalchemy.orm import Mapped, mapped_column

from packages.core.snowflake import next_id
from packages.db.mixins.json_text import json_text
from packages.db.session import Base, UTCDateTime


class PracticeSession(Base):
    """A practice session for a child on a specific topic."""
    __tablename__ = "practice_sessions"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, default=next_id)
    child_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("users.id"), nullable=False, index=True
    )
    topic_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("learning_topics.id"), nullable=False, index=True
    )
    session_mode: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    question_ids_json: Mapped[str] = mapped_column(Text, nullable=False)
    started_at: Mapped[datetime] = mapped_column(UTCDateTime(), server_default=func.now())
    ended_at: Mapped[datetime | None] = mapped_column(UTCDateTime(), nullable=True)
    total_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    completed_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    source: Mapped[str] = mapped_column(String(20), nullable=False, default="adaptive")
    learning_progress_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("learning_progress.id"), nullable=True
    )

    # JSON accessor
    question_ids: list[int] = json_text("question_ids_json")


class PracticeAttempt(Base):
    """Individual answer attempt within a practice session."""
    __tablename__ = "practice_attempts"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, default=next_id)
    session_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("practice_sessions.id"), nullable=False, index=True
    )
    question_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("questions.id"), nullable=False, index=True
    )
    child_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("users.id"), nullable=False, index=True
    )
    topic_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("learning_topics.id"), nullable=False, index=True
    )
    user_answer_json: Mapped[str] = mapped_column(Text, nullable=False)
    is_correct: Mapped[bool] = mapped_column(Boolean, nullable=False)
    time_spent_seconds: Mapped[int | None] = mapped_column(Integer, nullable=True)
    attempt_number: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), server_default=func.now())

    # JSON accessor
    user_answer: dict = json_text("user_answer_json")

    __table_args__ = (
        Index("ix_practice_attempt_child_topic_created", "child_id", "topic_id", "created_at"),
    )
```

- [ ] **Step 5: Update __init__.py**

```python
# server/packages/db/models/learning/__init__.py — replace contents
from packages.db.models.learning.path import LearningPath, LearningPathItem
from packages.db.models.learning.practice import PracticeAttempt, PracticeSession
from packages.db.models.learning.progress import LearningProgress
from packages.db.models.learning.question import Question, QuestionKnowledgePoint
from packages.db.models.learning.stats import ChildLearningStats

__all__ = [
    "LearningPath",
    "LearningPathItem",
    "LearningProgress",
    "PracticeAttempt",
    "PracticeSession",
    "Question",
    "QuestionKnowledgePoint",
    "ChildLearningStats",
]
```

- [ ] **Step 6: Create Alembic migration**

```bash
cd server/apps/backend
uv run alembic revision -m "add_questions_and_practice"
```

Then edit the generated file:

```python
# server/apps/backend/alembic/versions/prac001_add_questions_and_practice.py
# Generated by: cd server/apps/backend && uv run alembic revision -m "add_questions_and_practice"
# Then edit the generated file to add the table definitions below.
# The down_revision will be auto-filled by alembic revision.
"""add questions and practice tables

Revision ID: prac001
Revises: (auto-filled by alembic revision)
Create Date: 2026-10-10
"""
from collections.abc import Sequence
import sqlalchemy as sa
from alembic import op

revision: str = "prac001"
# down_revision is auto-set by `alembic revision`. Do NOT hardcode.
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    bind = op.get_bind()

    # --- questions ---
    if not bind.dialect.has_table(bind, "questions"):
        op.create_table(
            "questions",
            sa.Column("id", sa.BigInteger(), primary_key=True),
            sa.Column("topic_id", sa.BigInteger(), sa.ForeignKey("learning_topics.id"), nullable=False),
            sa.Column("question_type", sa.String(20), nullable=False),
            sa.Column("stem", sa.Text(), nullable=False),
            sa.Column("stem_zh", sa.Text(), nullable=True),
            sa.Column("options_json", sa.Text(), nullable=True),
            sa.Column("answer_json", sa.Text(), nullable=False),
            sa.Column("solution_json", sa.Text(), nullable=True),
            sa.Column("difficulty", sa.Integer(), nullable=False, server_default="1"),
            sa.Column("bloom_level", sa.String(20), nullable=False, server_default="apply"),
            sa.Column("source", sa.String(20), nullable=False),
            sa.Column("source_version", sa.String(50), nullable=True),
            sa.Column("review_status", sa.String(20), nullable=False, server_default="pending"),
            sa.Column("review_notes", sa.Text(), nullable=True),
            sa.Column("age_group", sa.String(10), nullable=False),
            sa.Column("parameters_json", sa.Text(), nullable=True),
            sa.Column("times_used", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("correct_count", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
            sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        )
        op.create_index("ix_questions_topic_id", "questions", ["topic_id"])
        op.create_index("ix_questions_question_type", "questions", ["question_type"])
        op.create_index("ix_questions_difficulty", "questions", ["difficulty"])
        op.create_index("ix_questions_review_status", "questions", ["review_status"])
        op.create_index("ix_questions_age_group", "questions", ["age_group"])

    # --- question_knowledge_points ---
    if not bind.dialect.has_table(bind, "question_knowledge_points"):
        op.create_table(
            "question_knowledge_points",
            sa.Column("id", sa.BigInteger(), primary_key=True),
            sa.Column("question_id", sa.BigInteger(), sa.ForeignKey("questions.id"), nullable=False),
            sa.Column("topic_id", sa.BigInteger(), sa.ForeignKey("learning_topics.id"), nullable=False),
            sa.Column("role", sa.String(20), nullable=False, server_default="primary"),
            sa.UniqueConstraint("question_id", "topic_id", name="uq_question_topic"),
        )

    # --- practice_sessions ---
    if not bind.dialect.has_table(bind, "practice_sessions"):
        op.create_table(
            "practice_sessions",
            sa.Column("id", sa.BigInteger(), primary_key=True),
            sa.Column("child_id", sa.BigInteger(), sa.ForeignKey("users.id"), nullable=False),
            sa.Column("topic_id", sa.BigInteger(), sa.ForeignKey("learning_topics.id"), nullable=False),
            sa.Column("session_mode", sa.String(20), nullable=False),
            sa.Column("question_ids_json", sa.Text(), nullable=False),
            sa.Column("started_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
            sa.Column("ended_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("total_score", sa.Float(), nullable=True),
            sa.Column("completed_count", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("source", sa.String(20), nullable=False, server_default="adaptive"),
            sa.Column("learning_progress_id", sa.BigInteger(), sa.ForeignKey("learning_progress.id"), nullable=True),
        )
        op.create_index("ix_practice_sessions_child_id", "practice_sessions", ["child_id"])

    # --- practice_attempts ---
    if not bind.dialect.has_table(bind, "practice_attempts"):
        op.create_table(
            "practice_attempts",
            sa.Column("id", sa.BigInteger(), primary_key=True),
            sa.Column("session_id", sa.BigInteger(), sa.ForeignKey("practice_sessions.id"), nullable=False),
            sa.Column("question_id", sa.BigInteger(), sa.ForeignKey("questions.id"), nullable=False),
            sa.Column("child_id", sa.BigInteger(), sa.ForeignKey("users.id"), nullable=False),
            sa.Column("topic_id", sa.BigInteger(), sa.ForeignKey("learning_topics.id"), nullable=False),
            sa.Column("user_answer_json", sa.Text(), nullable=False),
            sa.Column("is_correct", sa.Boolean(), nullable=False),
            sa.Column("time_spent_seconds", sa.Integer(), nullable=True),
            sa.Column("attempt_number", sa.Integer(), nullable=False, server_default="1"),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        )
        op.create_index("ix_practice_attempts_session_id", "practice_attempts", ["session_id"])
        op.create_index(
            "ix_practice_attempt_child_topic_created",
            "practice_attempts",
            ["child_id", "topic_id", "created_at"],
        )


def downgrade() -> None:
    op.drop_table("practice_attempts")
    op.drop_table("practice_sessions")
    op.drop_table("question_knowledge_points")
    op.drop_table("questions")
```

- [ ] **Step 7: Run migration and tests**

```bash
cd server/apps/backend && uv run alembic upgrade head
cd ../.. && uv run pytest tests/packages/db/test_models_practice.py -v
```

Expected: All 4 tests PASS

- [ ] **Step 8: Commit**

```bash
git add server/packages/db/models/learning/question.py \
       server/packages/db/models/learning/practice.py \
       server/packages/db/models/learning/__init__.py \
       server/apps/backend/alembic/versions/prac001_*.py \
       server/tests/packages/db/test_models_practice.py
git commit -m "feat(learning): add question bank and practice session models

- Question + QuestionKnowledgePoint for standardized question bank
- PracticeSession + PracticeAttempt for per-question tracking
- JSON accessor properties (options, answer, solution, parameters)
- Alembic migration prac001 with indexes
- Full test coverage for model creation and JSON round-trip

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>"
```

---

### Task 2: Pydantic Schemas

**Files:**
- Create: `server/apps/backend/app/schemas/practice.py`
- Test: `server/tests/backend/test_schemas_practice.py`

- [ ] **Step 1: Write failing schema tests**

```python
# server/tests/backend/test_schemas_practice.py
"""Tests for practice Pydantic schemas."""
from datetime import datetime, UTC

from apps.backend.app.schemas.practice import QuestionResponse, SessionCreateRequest


def test_question_response_snowflake_serialization():
    q = QuestionResponse(
        id=123456789012345678,
        topic_id=987654321098765432,
        question_type="calculation",
        stem="37 + 58 = ?",
        stem_zh="计算：37 + 58 = ?",
        options=None,
        answer={"answer": 95},
        solution=None,
        difficulty=1,
        bloom_level="apply",
        source="template",
        source_version="v1",
        review_status="approved",
        review_notes=None,
        age_group="mid",
        parameters=None,
        times_used=0,
        correct_count=0,
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )
    data = q.model_dump()
    assert isinstance(data["id"], str)
    assert isinstance(data["topic_id"], str)


def test_session_create_request_defaults():
    req = SessionCreateRequest(topic_id=123)
    assert req.session_mode == "practice"
    assert req.count == 5
```

- [ ] **Step 2: Run to verify failure**

```bash
cd server && uv run pytest tests/backend/test_schemas_practice.py -v
```

Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: Implement schemas**

```python
# server/apps/backend/app/schemas/practice.py
"""Pydantic schemas for practice system."""
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from apps.backend.app.schemas.base import SnowflakeBase


# --- Request schemas ---

class SessionCreateRequest(BaseModel):
    topic_id: int
    session_mode: str = "practice"
    count: int = Field(default=5, ge=1, le=20)


class SubmitAnswerRequest(BaseModel):
    question_id: int
    user_answer: dict
    time_spent_seconds: int | None = None


# --- Response schemas ---

class QuestionResponse(SnowflakeBase):
    id: int
    topic_id: int
    question_type: str
    stem: str
    stem_zh: str | None
    options: list[dict] | None
    answer: dict
    solution: dict | None
    difficulty: int
    bloom_level: str
    source: str
    source_version: str | None
    review_status: str
    review_notes: str | None
    age_group: str
    parameters: dict | None
    times_used: int
    correct_count: int
    created_at: datetime
    updated_at: datetime


class PracticeSessionResponse(SnowflakeBase):
    id: int
    child_id: int
    topic_id: int
    session_mode: str
    question_ids: list[int]
    started_at: datetime
    ended_at: datetime | None
    total_score: float | None
    completed_count: int
    source: str
    learning_progress_id: int | None


class PracticeAttemptResponse(SnowflakeBase):
    id: int
    session_id: int
    question_id: int
    child_id: int
    topic_id: int
    is_correct: bool
    time_spent_seconds: int | None
    attempt_number: int
    created_at: datetime


class PracticeResultResponse(SnowflakeBase):
    """Final result when a practice session is completed."""
    session_id: int
    total_score: float
    correct_count: int
    total_count: int
    xp_earned: int
    coins_earned: int
    mastery_changed: bool
    new_mastery_level: str | None
```

- [ ] **Step 4: Run tests to verify pass**

```bash
cd server && uv run pytest tests/backend/test_schemas_practice.py -v
```

Expected: 2 tests PASS

- [ ] **Step 5: Commit**

```bash
git add server/apps/backend/app/schemas/practice.py \
       server/tests/backend/test_schemas_practice.py
git commit -m "feat(learning): add practice Pydantic schemas

- Request: SessionCreateRequest, SubmitAnswerRequest
- Response: QuestionResponse, PracticeSessionResponse, PracticeAttemptResponse
- PracticeResultResponse for session completion with XP/coin/mastery changes
- All ID fields use SnowflakeBase for string serialization

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>"
```

---

### Task 3: Error Codes

**Files:**
- Modify: `server/apps/backend/app/errors/codes.py`
- Modify: `server/apps/backend/app/errors/locales/zh-CN.json`
- Modify: `server/apps/backend/app/errors/locales/en-US.json`

- [ ] **Step 1: Add error codes**

In `server/apps/backend/app/errors/codes.py`, add after `LEARNING_PATH_INVALID_MILESTONE`:

```python
    # Practice system
    PRACTICE_QUESTION_NOT_FOUND = "PRACTICE_QUESTION_NOT_FOUND"
    PRACTICE_QUESTION_INVALID = "PRACTICE_QUESTION_INVALID"
    PRACTICE_TOPIC_NOT_FOUND = "PRACTICE_TOPIC_NOT_FOUND"
    PRACTICE_SESSION_NOT_FOUND = "PRACTICE_SESSION_NOT_FOUND"
    PRACTICE_SESSION_ALREADY_ENDED = "PRACTICE_SESSION_ALREADY_ENDED"
    PRACTICE_NO_QUESTIONS_AVAILABLE = "PRACTICE_NO_QUESTIONS_AVAILABLE"
    PRACTICE_DUPLICATE_ATTEMPT = "PRACTICE_DUPLICATE_ATTEMPT"
```

Add to `ERROR_META` dict:

```python
    ErrorCode.PRACTICE_QUESTION_NOT_FOUND: 404,
    ErrorCode.PRACTICE_QUESTION_INVALID: 400,
    ErrorCode.PRACTICE_TOPIC_NOT_FOUND: 404,
    ErrorCode.PRACTICE_SESSION_NOT_FOUND: 404,
    ErrorCode.PRACTICE_SESSION_ALREADY_ENDED: 409,
    ErrorCode.PRACTICE_NO_QUESTIONS_AVAILABLE: 404,
    ErrorCode.PRACTICE_DUPLICATE_ATTEMPT: 409,
```

- [ ] **Step 2: Add i18n messages**

In `server/apps/backend/app/errors/locales/zh-CN.json`:

```json
"PRACTICE_QUESTION_NOT_FOUND": "题目不存在",
"PRACTICE_QUESTION_INVALID": "题目数据无效",
"PRACTICE_TOPIC_NOT_FOUND": "知识点不存在",
"PRACTICE_SESSION_NOT_FOUND": "练习会话不存在",
"PRACTICE_SESSION_ALREADY_ENDED": "练习会话已结束",
"PRACTICE_NO_QUESTIONS_AVAILABLE": "该知识点暂无可用题目",
"PRACTICE_DUPLICATE_ATTEMPT": "该题目已作答，不可重复提交"
```

In `server/apps/backend/app/errors/locales/en-US.json`:

```json
"PRACTICE_QUESTION_NOT_FOUND": "Question not found",
"PRACTICE_QUESTION_INVALID": "Question data invalid",
"PRACTICE_TOPIC_NOT_FOUND": "Topic not found",
"PRACTICE_SESSION_NOT_FOUND": "Practice session not found",
"PRACTICE_SESSION_ALREADY_ENDED": "Practice session already ended",
"PRACTICE_NO_QUESTIONS_AVAILABLE": "No questions available for this topic",
"PRACTICE_DUPLICATE_ATTEMPT": "This question has already been answered"
```

- [ ] **Step 3: Commit**

```bash
git add server/apps/backend/app/errors/codes.py \
       server/apps/backend/app/errors/locales/zh-CN.json \
       server/apps/backend/app/errors/locales/en-US.json
git commit -m "feat(learning): add practice error codes with i18n

- PRACTICE_QUESTION_NOT_FOUND (404)
- PRACTICE_SESSION_NOT_FOUND (404)
- PRACTICE_SESSION_ALREADY_ENDED (409)
- PRACTICE_NO_QUESTIONS_AVAILABLE (404)
- PRACTICE_DUPLICATE_ATTEMPT (409)

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>"
```

---

### Task 4: Template Registry

**Files:**
- Create: `server/packages/domain/question_templates/__init__.py`
- Create: `server/packages/domain/question_templates/base.py`
- Create: `server/packages/domain/question_templates/registry.py`
- Test: `server/tests/packages/domain/test_template_registry.py`

- [ ] **Step 1: Write failing tests**

```python
# server/tests/packages/domain/test_template_registry.py
"""Tests for question template registry."""
import pytest

from packages.domain.question_templates.base import GeneratedQuestion
from packages.domain.question_templates.registry import (
    register_template,
    list_templates,
    generate_question,
    TEMPLATE_REGISTRY,
)


@pytest.fixture(autouse=True)
def clean_registry():
    """Save and restore the template registry around each test."""
    saved = dict(TEMPLATE_REGISTRY)
    yield
    TEMPLATE_REGISTRY.clear()
    TEMPLATE_REGISTRY.update(saved)


def test_register_and_generate():
    @register_template("math.test.add")
    def gen(params: dict) -> GeneratedQuestion:
        a, b = params["a"], params["b"]
        return GeneratedQuestion(
            template_id="math.test.add",
            stem=f"{a} + {b} = ?",
            stem_zh=f"计算：{a} + {b} = ?",
            answer={"answer": a + b},
            question_type="calculation",
            difficulty=1,
            bloom_level="apply",
            topic_key="mt_test",
            age_group="mid",
            parameters={"a": a, "b": b},
        )

    result = generate_question("math.test.add", {"a": 3, "b": 4})
    assert result.stem_zh == "计算：3 + 4 = ?"
    assert result.answer == {"answer": 7}


def test_list_templates_by_subject():
    @register_template("math.test.a")
    def a(params): 
        return GeneratedQuestion("t", "s", {"answer": 1}, "calculation", 1, "apply", "mt", "mid")

    @register_template("math.test.b")
    def b(params): 
        return GeneratedQuestion("t", "s", {"answer": 1}, "calculation", 1, "apply", "mt", "mid")

    @register_template("chinese.test.c")
    def c(params): 
        return GeneratedQuestion("t", "s", {"answer": 1}, "fill_blank", 1, "remember", "mt", "mid")

    math = list_templates(subject="math")
    assert len(math) == 2
    assert "math.test.a" in math
    assert "math.test.b" in math

    chinese = list_templates(subject="chinese")
    assert len(chinese) == 1


def test_generate_unknown_template_raises():
    with pytest.raises(ValueError, match="Unknown template"):
        generate_question("nonexistent.template", {})
```

- [ ] **Step 2: Run to verify failure**

```bash
cd server && uv run pytest tests/packages/domain/test_template_registry.py -v
```

Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: Implement GeneratedQuestion**

```python
# server/packages/domain/question_templates/base.py
"""Base types for question template engine."""
from dataclasses import dataclass, field


@dataclass(frozen=True)
class GeneratedQuestion:
    """Output from a question template generator.

    Immutable (frozen) so it can be safely passed around without mutation risk.
    """
    template_id: str
    stem: str
    answer: dict
    question_type: str
    difficulty: int
    bloom_level: str
    topic_key: str
    age_group: str
    stem_zh: str | None = None
    options: list[dict] | None = None
    solution: dict | None = None
    parameters: dict = field(default_factory=dict)
```

- [ ] **Step 4: Implement registry**

```python
# server/packages/domain/question_templates/registry.py
"""Template registration and question generation."""
from packages.domain.question_templates.base import GeneratedQuestion

TEMPLATE_REGISTRY: dict[str, callable] = {}


def register_template(template_id: str):
    """Decorator to register a question template generator.

    Usage:
        @register_template("math.arithmetic.addition_2digit")
        def generate(params: dict) -> GeneratedQuestion:
            ...
    """
    def decorator(func: callable):
        TEMPLATE_REGISTRY[template_id] = func
        return func
    return decorator


def list_templates(subject: str | None = None) -> list[str]:
    """List registered template IDs, optionally filtered by subject prefix."""
    if subject is None:
        return list(TEMPLATE_REGISTRY.keys())
    return [tid for tid in TEMPLATE_REGISTRY if tid.startswith(f"{subject}.")]


def generate_question(template_id: str, params: dict) -> GeneratedQuestion:
    """Generate a question using a registered template.

    Raises:
        ValueError: If template_id is not registered.
    """
    func = TEMPLATE_REGISTRY.get(template_id)
    if func is None:
        raise ValueError(f"Unknown template: {template_id}")
    return func(params)
```

- [ ] **Step 5: Create __init__.py**

```python
# server/packages/domain/question_templates/__init__.py
"""Question template engine — programmatic question generation."""
from packages.domain.question_templates.base import GeneratedQuestion
from packages.domain.question_templates.registry import (
    TEMPLATE_REGISTRY,
    register_template,
    list_templates,
    generate_question,
)
# Bootstrap: import template modules to trigger @register_template decorators
from packages.domain.question_templates import math_arithmetic  # noqa: F401

__all__ = [
    "GeneratedQuestion",
    "TEMPLATE_REGISTRY",
    "register_template",
    "list_templates",
    "generate_question",
]
```

- [ ] **Step 6: Run tests to verify pass**

```bash
cd server && uv run pytest tests/packages/domain/test_template_registry.py -v
```

Expected: 3 tests PASS

- [ ] **Step 7: Commit**

```bash
git add server/packages/domain/question_templates/ \
       server/tests/packages/domain/test_template_registry.py
git commit -m "feat(learning): add question template registry

- GeneratedQuestion frozen dataclass for template output
- register_template decorator + TEMPLATE_REGISTRY global
- list_templates with subject filter, generate_question
- Full test coverage with registry save/restore

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>"
```

---

### Task 5: Math Arithmetic Templates

**Files:**
- Create: `server/packages/domain/question_templates/math_arithmetic.py`
- Test: `server/tests/packages/domain/test_math_arithmetic.py`

- [ ] **Step 1: Write failing tests**

```python
# server/tests/packages/domain/test_math_arithmetic.py
"""Tests for math arithmetic question templates."""
import pytest

from packages.domain.question_templates.registry import (
    generate_question,
    list_templates,
    TEMPLATE_REGISTRY,
)


@pytest.fixture(autouse=True)
def load_templates():
    """Import to trigger template registration."""
    import packages.domain.question_templates.math_arithmetic  # noqa: F401


def test_addition_2digit_generates_valid_question():
    q = generate_question("math.arithmetic.addition_2digit", {})
    assert q.question_type == "calculation"
    assert q.difficulty == 1
    assert q.bloom_level == "apply"
    assert q.age_group == "mid"
    # Answer must be verifiable
    assert "answer" in q.answer
    assert isinstance(q.answer["answer"], int)
    assert q.answer["answer"] >= 20  # min 10+10
    assert q.answer["answer"] <= 198  # max 99+99


def test_subtraction_2digit_generates_valid_question():
    q = generate_question("math.arithmetic.subtraction_2digit", {})
    assert q.question_type == "calculation"
    assert "answer" in q.answer
    assert q.answer["answer"] >= 0  # no negative results


def test_multiplication_table():
    q = generate_question("math.arithmetic.multiplication_table", {})
    assert q.question_type == "calculation"
    assert "answer" in q.answer
    a, b = q.parameters["a"], q.parameters["b"]
    assert 1 <= a <= 9
    assert 1 <= b <= 9
    assert q.answer["answer"] == a * b


def test_division_basic():
    q = generate_question("math.arithmetic.division_basic", {})
    assert q.question_type == "calculation"
    assert "answer" in q.answer
    # Division should produce integer result
    assert isinstance(q.answer["answer"], int)


def test_all_templates_registered():
    templates = list_templates(subject="math")
    assert len(templates) >= 4  # At least our 4 templates
    assert "math.arithmetic.addition_2digit" in templates
    assert "math.arithmetic.subtraction_2digit" in templates
    assert "math.arithmetic.multiplication_table" in templates
    assert "math.arithmetic.division_basic" in templates


def test_templates_have_stem_zh():
    q = generate_question("math.arithmetic.addition_2digit", {})
    assert q.stem_zh is not None
    assert "计算" in q.stem_zh or "+" in q.stem_zh
```

- [ ] **Step 2: Run to verify failure**

```bash
cd server && uv run pytest tests/packages/domain/test_math_arithmetic.py -v
```

Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: Implement arithmetic templates**

```python
# server/packages/domain/question_templates/math_arithmetic.py
"""Math arithmetic question templates — elementary school level."""
import random

from packages.domain.question_templates.base import GeneratedQuestion
from packages.domain.question_templates.registry import register_template


@register_template("math.arithmetic.addition_2digit")
def _gen_addition_2digit(params: dict) -> GeneratedQuestion:
    lo = params.get("min", 10)
    hi = params.get("max", 99)
    a = random.randint(lo, hi)
    b = random.randint(lo, hi)
    return GeneratedQuestion(
        template_id="math.arithmetic.addition_2digit",
        stem=f"Calculate: {a} + {b} = ?",
        stem_zh=f"计算：{a} + {b} = ?",
        answer={"answer": a + b},
        solution={"steps": [f"{a} + {b} = {a + b}"]},
        question_type="calculation",
        difficulty=1,
        bloom_level="apply",
        topic_key="mt_arithmetic_addition",
        age_group="mid",
        parameters={"a": a, "b": b},
    )


@register_template("math.arithmetic.subtraction_2digit")
def _gen_subtraction_2digit(params: dict) -> GeneratedQuestion:
    lo = params.get("min", 10)
    hi = params.get("max", 99)
    a = random.randint(lo, hi)
    b = random.randint(lo, min(a, hi))  # Ensure non-negative result
    return GeneratedQuestion(
        template_id="math.arithmetic.subtraction_2digit",
        stem=f"Calculate: {a} - {b} = ?",
        stem_zh=f"计算：{a} - {b} = ?",
        answer={"answer": a - b},
        solution={"steps": [f"{a} - {b} = {a - b}"]},
        question_type="calculation",
        difficulty=1,
        bloom_level="apply",
        topic_key="mt_arithmetic_subtraction",
        age_group="mid",
        parameters={"a": a, "b": b},
    )


@register_template("math.arithmetic.multiplication_table")
def _gen_multiplication_table(params: dict) -> GeneratedQuestion:
    a = random.randint(1, 9)
    b = random.randint(1, 9)
    return GeneratedQuestion(
        template_id="math.arithmetic.multiplication_table",
        stem=f"Calculate: {a} × {b} = ?",
        stem_zh=f"计算：{a} × {b} = ?",
        answer={"answer": a * b},
        solution={"steps": [f"{a} × {b} = {a * b}"]},
        question_type="calculation",
        difficulty=1,
        bloom_level="apply",
        topic_key="mt_arithmetic_multiplication",
        age_group="mid",
        parameters={"a": a, "b": b},
    )


@register_template("math.arithmetic.division_basic")
def _gen_division_basic(params: dict) -> GeneratedQuestion:
    # Generate division that yields integer result
    divisor = random.randint(2, 9)
    quotient = random.randint(2, 12)
    dividend = divisor * quotient
    return GeneratedQuestion(
        template_id="math.arithmetic.division_basic",
        stem=f"Calculate: {dividend} ÷ {divisor} = ?",
        stem_zh=f"计算：{dividend} ÷ {divisor} = ?",
        answer={"answer": quotient},
        solution={"steps": [f"{dividend} ÷ {divisor} = {quotient}"]},
        question_type="calculation",
        difficulty=1,
        bloom_level="apply",
        topic_key="mt_arithmetic_division",
        age_group="mid",
        parameters={"dividend": dividend, "divisor": divisor, "quotient": quotient},
    )
```

- [ ] **Step 4: Run tests to verify pass**

```bash
cd server && uv run pytest tests/packages/domain/test_math_arithmetic.py -v
```

Expected: 6 tests PASS

- [ ] **Step 5: Commit**

```bash
git add server/packages/domain/question_templates/math_arithmetic.py \
       server/tests/packages/domain/test_math_arithmetic.py
git commit -m "feat(learning): add math arithmetic question templates

- addition_2digit: two-digit addition (10-99)
- subtraction_2digit: two-digit subtraction (non-negative)
- multiplication_table: single-digit multiplication (1-9)
- division_basic: integer division (no remainder)
- All templates produce Chinese stem_zh and verifiable answers
- Full test coverage for generation validity

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>"
```

---

### Task 6: Scoring Service

**Files:**
- Create: `server/apps/backend/app/services/learning/scoring_service.py`
- Test: `server/tests/backend/services/test_scoring_service.py`

- [ ] **Step 1: Write failing tests**

```python
# server/tests/backend/services/test_scoring_service.py
"""Tests for scoring service — auto-grading answers."""
import pytest

from apps.backend.app.services.learning.scoring_service import (
    check_answer,
    calculate_session_score,
)


def test_check_calculation_correct():
    result = check_answer(
        question_type="calculation",
        correct_answer={"answer": 95},
        user_answer={"answer": 95},
    )
    assert result is True


def test_check_calculation_wrong():
    result = check_answer(
        question_type="calculation",
        correct_answer={"answer": 95},
        user_answer={"answer": 96},
    )
    assert result is False


def test_check_multiple_choice_correct():
    result = check_answer(
        question_type="multiple_choice",
        correct_answer={"key": "B"},
        user_answer={"key": "B"},
    )
    assert result is True


def test_check_multiple_choice_wrong():
    result = check_answer(
        question_type="multiple_choice",
        correct_answer={"key": "B"},
        user_answer={"key": "A"},
    )
    assert result is False


def test_check_true_false():
    assert check_answer("true_false", {"value": True}, {"value": True}) is True
    assert check_answer("true_false", {"value": True}, {"value": False}) is False


def test_check_fill_blank():
    assert check_answer("fill_blank", {"value": "分数"}, {"value": "分数"}) is True
    assert check_answer("fill_blank", {"value": "分数"}, {"value": "小数"}) is False


def test_check_answer_missing_key():
    """User answer missing required key returns False, not error."""
    result = check_answer(
        question_type="calculation",
        correct_answer={"answer": 95},
        user_answer={},  # Missing "answer" key
    )
    assert result is False


def test_calculate_session_score():
    score = calculate_session_score(correct=4, total=5)
    assert score == 0.8


def test_calculate_session_score_zero_total():
    score = calculate_session_score(correct=0, total=0)
    assert score == 0.0
```

- [ ] **Step 2: Run to verify failure**

```bash
cd server && uv run pytest tests/backend/services/test_scoring_service.py -v
```

Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: Implement scoring service**

```python
# server/apps/backend/app/services/learning/scoring_service.py
"""Auto-grading service for practice answers."""
from packages.core.logging import get_logger

logger = get_logger(__name__)


def check_answer(
    question_type: str,
    correct_answer: dict,
    user_answer: dict,
) -> bool:
    """Check if user answer matches the correct answer.

    Returns False (not raises) for malformed input — graceful degradation.
    """
    if question_type in ("calculation", "fill_blank"):
        return user_answer.get("answer" if question_type == "calculation" else "value") == \
               correct_answer.get("answer" if question_type == "calculation" else "value")

    if question_type == "multiple_choice":
        return user_answer.get("key") == correct_answer.get("key")

    if question_type == "true_false":
        return user_answer.get("value") == correct_answer.get("value")

    if question_type == "application":
        # Application questions need manual review; auto-check acceptable list
        acceptable = correct_answer.get("acceptable", [])
        return user_answer.get("answer") in acceptable

    logger.warning("Unknown question_type for scoring: %s", question_type)
    return False


def calculate_session_score(correct: int, total: int) -> float:
    """Calculate session score as ratio (0.0-1.0)."""
    if total == 0:
        return 0.0
    return correct / total
```

- [ ] **Step 4: Run tests to verify pass**

```bash
cd server && uv run pytest tests/backend/services/test_scoring_service.py -v
```

Expected: 9 tests PASS

- [ ] **Step 5: Commit**

```bash
git add server/apps/backend/app/services/learning/scoring_service.py \
       server/tests/backend/services/test_scoring_service.py
git commit -m "feat(learning): add scoring service for auto-grading

- check_answer: handles calculation, multiple_choice, true_false, fill_blank, application
- Graceful degradation: malformed input returns False, not exception
- calculate_session_score: correct/total ratio
- Full test coverage for all question types and edge cases

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>"
```

---

### Task 7: Adaptive Service

**Files:**
- Create: `server/apps/backend/app/services/learning/adaptive_service.py`
- Test: `server/tests/backend/services/test_adaptive_service.py`

- [ ] **Step 1: Write failing tests**

```python
# server/tests/backend/services/test_adaptive_service.py
"""Tests for adaptive question selection service."""
import pytest
from datetime import UTC, datetime, timedelta
from sqlalchemy.orm import Session

from apps.backend.app.services.learning.adaptive_service import (
    select_questions,
    get_difficulty_range,
    RuleBasedMasteryEstimator,
)
from packages.db.models.learning.progress import LearningProgress
from packages.db.models.learning.question import Question
from packages.db.models.learning.topic import LearningTopic


@pytest.fixture
def topic(db: Session):
    t = LearningTopic(
        topic_key="mt_adaptive_test",
        topic_type="concept",
        subject="mathematics",
        domain="arithmetic",
        name="Addition",
        age_group="mid",
        evidence_json="[]",
        standards_json="[]",
    )
    db.add(t)
    db.flush()
    return t


@pytest.fixture
def questions(db: Session, topic):
    """Create 10 questions across difficulties 1-5."""
    qs = []
    for i in range(10):
        q = Question(
            topic_id=topic.id,
            question_type="calculation",
            stem=f"Q{i+1}",
            answer_json='{"answer": 1}',
            difficulty=(i % 5) + 1,  # 1,2,3,4,5,1,2,3,4,5
            bloom_level="apply",
            source="template",
            review_status="approved",
            age_group="mid",
        )
        db.add(q)
        qs.append(q)
    db.flush()
    return qs


def test_get_difficulty_range_for_learning():
    assert get_difficulty_range("learning") == (1, 2)
    assert get_difficulty_range("available") == (1, 2)


def test_get_difficulty_range_for_assessing():
    assert get_difficulty_range("assessing") == (2, 3)


def test_get_difficulty_range_for_mastered():
    assert get_difficulty_range("mastered") == (3, 4)


def test_get_difficulty_range_for_review():
    assert get_difficulty_range("review") == (1, 2)


def test_select_questions_returns_correct_count(db: Session, topic, questions):
    selected = select_questions(
        db=db,
        topic_id=topic.id,
        mastery_level="learning",
        count=3,
        exclude_question_ids=[],
        exclude_recent_days=7,
        child_id=1,
    )
    assert len(selected) == 3
    # All should be difficulty 1-2 (learning range)
    for q in selected:
        assert q.difficulty in (1, 2)


def test_select_questions_excludes_recent(db: Session, topic, questions):
    """Questions answered in last N days are excluded."""
    selected = select_questions(
        db=db,
        topic_id=topic.id,
        mastery_level="learning",
        count=5,
        exclude_question_ids=[q.id for q in questions[:2]],  # Exclude first 2
        exclude_recent_days=7,
        child_id=1,
    )
    assert all(q.id not in [questions[0].id, questions[1].id] for q in selected)


def test_select_questions_returns_empty_when_none_available(db: Session, topic):
    """Returns empty list when no questions match."""
    # Topic with no questions
    empty_topic = LearningTopic(
        topic_key="mt_empty",
        topic_type="concept",
        subject="mathematics",
        domain="empty",
        name="Empty",
        age_group="mid",
        evidence_json="[]",
        standards_json="[]",
    )
    db.add(empty_topic)
    db.flush()

    selected = select_questions(
        db=db,
        topic_id=empty_topic.id,
        mastery_level="learning",
        count=5,
        exclude_question_ids=[],
        exclude_recent_days=7,
        child_id=1,
    )
    assert selected == []


def test_mastery_estimator_basic(db: Session, topic):
    estimator = RuleBasedMasteryEstimator()
    # No attempts → 0.0
    score = estimator.estimate(db=db, child_id=1, topic_id=topic.id)
    assert score == 0.0
```

- [ ] **Step 2: Run to verify failure**

```bash
cd server && uv run pytest tests/backend/services/test_adaptive_service.py -v
```

Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: Implement adaptive service**

```python
# server/apps/backend/app/services/learning/adaptive_service.py
"""Adaptive question selection engine."""
from datetime import UTC, datetime, timedelta
from typing import Protocol

from sqlalchemy.orm import Session

from packages.core.logging import get_logger
from packages.db.models.learning.practice import PracticeAttempt
from packages.db.models.learning.question import Question

logger = get_logger(__name__)

# Mastery level → (min_difficulty, max_difficulty)
DIFFICULTY_MAP: dict[str, tuple[int, int]] = {
    "available": (1, 2),
    "learning": (1, 2),
    "assessing": (2, 3),
    "mastered": (3, 4),
    "review": (1, 2),
}


def get_difficulty_range(mastery_level: str) -> tuple[int, int]:
    """Get (min, max) difficulty for a mastery level."""
    return DIFFICULTY_MAP.get(mastery_level, (1, 3))


def select_questions(
    db: Session,
    topic_id: int,
    mastery_level: str,
    count: int,
    exclude_question_ids: list[int],
    exclude_recent_days: int,
    child_id: int,
) -> list[Question]:
    """Select questions for a practice session.

    Strategy:
    1. Filter by topic, difficulty range, review_status=approved
    2. Exclude recently answered questions (last N days)
    3. Exclude explicitly excluded IDs
    4. Random sample up to count
    """
    min_diff, max_diff = get_difficulty_range(mastery_level)
    cutoff = datetime.now(UTC) - timedelta(days=exclude_recent_days)

    # Recent question IDs for this child
    recent_ids = {
        row.question_id
        for row in db.query(PracticeAttempt.question_id)
        .filter(
            PracticeAttempt.child_id == child_id,
            PracticeAttempt.topic_id == topic_id,
            PracticeAttempt.created_at >= cutoff,
        )
        .all()
    }

    exclude_set = set(exclude_question_ids) | recent_ids

    query = db.query(Question).filter(
        Question.topic_id == topic_id,
        Question.difficulty >= min_diff,
        Question.difficulty <= max_diff,
        Question.review_status == "approved",
    )

    if exclude_set:
        query = query.filter(~Question.id.in_(exclude_set))

    candidates = query.all()

    # Random sample (deterministic for test reproducibility: just take first N)
    import random
    random.shuffle(candidates)
    return candidates[:count]


class MasteryEstimator(Protocol):
    """Protocol for knowledge mastery estimation.

    Implementation queries attempts directly from DB — caller provides db session.
    """

    def estimate(self, db: Session, child_id: int, topic_id: int) -> float:
        """Return 0.0-1.0 mastery estimate."""
        ...


class RuleBasedMasteryEstimator:
    """Simple mastery estimate based on recent attempt accuracy."""

    def estimate(self, db: Session, child_id: int, topic_id: int) -> float:
        """Estimate mastery as ratio of correct attempts in last 10 tries."""
        recent = (
            db.query(PracticeAttempt)
            .filter_by(child_id=child_id, topic_id=topic_id)
            .order_by(PracticeAttempt.created_at.desc())
            .limit(10)
            .all()
        )
        if not recent:
            return 0.0
        correct = sum(1 for a in recent if a.is_correct)
        return correct / len(recent)
```

- [ ] **Step 4: Run tests**

```bash
cd server && uv run pytest tests/backend/services/test_adaptive_service.py -v
```

Expected: 8 tests PASS

- [ ] **Step 5: Commit**

```bash
git add server/apps/backend/app/services/learning/adaptive_service.py \
       server/tests/backend/services/test_adaptive_service.py
git commit -m "feat(learning): add adaptive question selection service

- get_difficulty_range: mastery_level → (min_diff, max_diff) mapping
- select_questions: topic + difficulty + recency + exclusion filtering
- RuleBasedMasteryEstimator: recent accuracy ratio
- MasteryEstimator Protocol for future BKT/DKT replacement
- Full test coverage

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>"
```

---

### Task 8: Practice Service

**Files:**
- Create: `server/apps/backend/app/services/learning/practice_service.py`
- Test: `server/tests/backend/services/test_practice_service.py`

- [ ] **Step 1: Write failing tests**

```python
# server/tests/backend/services/test_practice_service.py
"""Tests for practice session management service."""
import pytest
from datetime import UTC, datetime
from sqlalchemy.orm import Session

from apps.backend.app.errors import AppError
from apps.backend.app.services.learning.practice_service import (
    create_session,
    submit_answer,
    finish_session,
    get_session,
)
from apps.backend.app.services.learning.progress_service import get_or_create_progress
from packages.db.models.learning.progress import LearningProgress
from packages.db.models.learning.question import Question
from packages.db.models.learning.topic import LearningTopic


@pytest.fixture
def topic(db: Session):
    t = LearningTopic(
        topic_key="mt_practice_svc",
        topic_type="concept",
        subject="mathematics",
        domain="arithmetic",
        name="Practice topic",
        age_group="mid",
        evidence_json="[]",
        standards_json="[]",
    )
    db.add(t)
    db.flush()
    return t


@pytest.fixture
def questions(db: Session, topic):
    qs = []
    for i in range(5):
        q = Question(
            topic_id=topic.id,
            question_type="calculation",
            stem=f"Q{i}",
            answer_json=f'{{"answer": {i + 1}}}',
            difficulty=1,
            bloom_level="apply",
            source="template",
            review_status="approved",
            age_group="mid",
        )
        db.add(q)
        qs.append(q)
    db.flush()
    return qs


@pytest.fixture
def progress(db: Session, topic):
    p = LearningProgress(
        child_id=1,
        topic_id=topic.id,
        mastery_level="learning",
    )
    db.add(p)
    db.flush()
    return p


def test_create_session(db: Session, topic, questions):
    session = create_session(
        db=db,
        child_id=1,
        topic_id=topic.id,
        session_mode="practice",
        question_ids=[q.id for q in questions[:3]],
    )
    assert session.id is not None
    assert session.child_id == 1
    assert session.question_ids == [questions[0].id, questions[1].id, questions[2].id]
    assert session.completed_count == 0


def test_submit_answer(db: Session, topic, questions):
    session = create_session(
        db=db, child_id=1, topic_id=topic.id,
        session_mode="practice",
        question_ids=[questions[0].id],
    )
    attempt = submit_answer(
        db=db,
        session_id=session.id,
        question_id=questions[0].id,
        child_id=1,
        topic_id=topic.id,
        user_answer={"answer": questions[0].answer["answer"]},
        time_spent_seconds=10,
    )
    assert attempt.is_correct is True


def test_submit_answer_wrong(db: Session, topic, questions):
    session = create_session(
        db=db, child_id=1, topic_id=topic.id,
        session_mode="practice",
        question_ids=[questions[0].id],
    )
    attempt = submit_answer(
        db=db,
        session_id=session.id,
        question_id=questions[0].id,
        child_id=1,
        topic_id=topic.id,
        user_answer={"answer": 99999},
        time_spent_seconds=10,
    )
    assert attempt.is_correct is False


def test_submit_duplicate_raises(db: Session, topic, questions):
    session = create_session(
        db=db, child_id=1, topic_id=topic.id,
        session_mode="practice",
        question_ids=[questions[0].id],
    )
    submit_answer(
        db=db, session_id=session.id, question_id=questions[0].id,
        child_id=1, topic_id=topic.id,
        user_answer={"answer": 1}, time_spent_seconds=10,
    )
    with pytest.raises(AppError):
        submit_answer(
            db=db, session_id=session.id, question_id=questions[0].id,
            child_id=1, topic_id=topic.id,
            user_answer={"answer": 2}, time_spent_seconds=5,
        )


def test_finish_session_calculates_score(db: Session, topic, questions, progress):
    session = create_session(
        db=db, child_id=1, topic_id=topic.id,
        session_mode="practice",
        question_ids=[q.id for q in questions[:4]],
    )
    # 3 correct, 1 wrong → score = 0.75
    for i in range(4):
        correct_answer = questions[i].answer["answer"]
        user_answer = correct_answer if i < 3 else 99999
        submit_answer(
            db=db, session_id=session.id, question_id=questions[i].id,
            child_id=1, topic_id=topic.id,
            user_answer={"answer": user_answer}, time_spent_seconds=10,
        )

    result = finish_session(db=db, session_id=session.id, child_id=1)
    assert result["total_score"] == 0.75
    assert result["correct_count"] == 3
    assert result["total_count"] == 4
    assert session.ended_at is not None


def test_finish_session_already_ended_raises(db: Session, topic, questions):
    session = create_session(
        db=db, child_id=1, topic_id=topic.id,
        session_mode="practice",
        question_ids=[questions[0].id],
    )
    submit_answer(
        db=db, session_id=session.id, question_id=questions[0].id,
        child_id=1, topic_id=topic.id,
        user_answer={"answer": 1}, time_spent_seconds=10,
    )
    finish_session(db=db, session_id=session.id, child_id=1)
    with pytest.raises(AppError):
        finish_session(db=db, session_id=session.id, child_id=1)
```

- [ ] **Step 2: Run to verify failure**

```bash
cd server && uv run pytest tests/backend/services/test_practice_service.py -v
```

Expected: FAIL

- [ ] **Step 3: Implement practice service**

```python
# server/apps/backend/app/services/learning/practice_service.py
"""Practice session management service."""
import json
from datetime import UTC, datetime

from sqlalchemy.orm import Session

from apps.backend.app.errors import AppError, ErrorCode
from apps.backend.app.services.learning.scoring_service import check_answer, calculate_session_score
from packages.core.logging import get_logger
from packages.db.models.learning.practice import PracticeAttempt, PracticeSession
from packages.db.models.learning.question import Question

logger = get_logger(__name__)


def create_session(
    db: Session,
    child_id: int,
    topic_id: int,
    session_mode: str,
    question_ids: list[int],
) -> PracticeSession:
    """Create a new practice session with selected questions."""
    session = PracticeSession(
        child_id=child_id,
        topic_id=topic_id,
        session_mode=session_mode,
        question_ids_json=json.dumps(question_ids),
        source="adaptive",
    )
    db.add(session)
    db.flush()
    logger.info(
        "Practice session created: session_id=%s, child_id=%s, topic_id=%s, count=%d",
        session.id, child_id, topic_id, len(question_ids),
    )
    return session


def submit_answer(
    db: Session,
    session_id: int,
    question_id: int,
    child_id: int,
    topic_id: int,
    user_answer: dict,
    time_spent_seconds: int | None,
) -> PracticeAttempt:
    """Submit an answer for a question in a practice session.

    Raises:
        AppError(PRACTICE_DUPLICATE_ATTEMPT): if question already answered in this session.
    """
    # Check for duplicate
    existing = db.query(PracticeAttempt).filter_by(
        session_id=session_id, question_id=question_id
    ).first()
    if existing:
        raise AppError(ErrorCode.PRACTICE_DUPLICATE_ATTEMPT)

    # Get question for scoring
    question = db.query(Question).filter_by(id=question_id).first()
    if not question:
        raise AppError(ErrorCode.PRACTICE_QUESTION_NOT_FOUND)

    is_correct = check_answer(question.question_type, question.answer, user_answer)

    # Count attempt number for this child+question
    attempt_num = db.query(PracticeAttempt).filter_by(
        child_id=child_id, question_id=question_id
    ).count() + 1

    attempt = PracticeAttempt(
        session_id=session_id,
        question_id=question_id,
        child_id=child_id,
        topic_id=topic_id,
        user_answer_json=json.dumps(user_answer),
        is_correct=is_correct,
        time_spent_seconds=time_spent_seconds,
        attempt_number=attempt_num,
    )
    db.add(attempt)

    # Update session completed_count
    session = db.query(PracticeSession).filter_by(id=session_id).first()
    if session:
        session.completed_count += 1

    db.flush()
    return attempt


def finish_session(
    db: Session,
    session_id: int,
    child_id: int,
) -> dict:
    """Finish a practice session and calculate score.

    Raises:
        AppError(PRACTICE_SESSION_ALREADY_ENDED): if session already ended.
        AppError(PRACTICE_SESSION_NOT_FOUND): if session doesn't exist.
    """
    session = db.query(PracticeSession).filter_by(id=session_id).first()
    if not session:
        raise AppError(ErrorCode.PRACTICE_SESSION_NOT_FOUND)
    if session.ended_at is not None:
        raise AppError(ErrorCode.PRACTICE_SESSION_ALREADY_ENDED)

    # Calculate score
    attempts = db.query(PracticeAttempt).filter_by(session_id=session_id).all()
    correct = sum(1 for a in attempts if a.is_correct)
    total = len(attempts)
    score = calculate_session_score(correct, total)

    session.ended_at = datetime.now(UTC)
    session.total_score = score
    db.flush()

    logger.info(
        "Practice session finished: session_id=%s, score=%.2f, correct=%d/%d",
        session_id, score, correct, total,
    )

    return {
        "session_id": session_id,
        "total_score": score,
        "correct_count": correct,
        "total_count": total,
    }


def get_session(db: Session, session_id: int) -> PracticeSession | None:
    """Get a practice session by ID."""
    return db.query(PracticeSession).filter_by(id=session_id).first()
```

- [ ] **Step 4: Run tests**

```bash
cd server && uv run pytest tests/backend/services/test_practice_service.py -v
```

Expected: 6 tests PASS

- [ ] **Step 5: Commit**

```bash
git add server/apps/backend/app/services/learning/practice_service.py \
       server/tests/backend/services/test_practice_service.py
git commit -m "feat(learning): add practice session management service

- create_session: initialize session with question list
- submit_answer: grade answer + detect duplicates + track attempts
- finish_session: calculate score + update session state
- Duplicate detection prevents same question answered twice
- Full test coverage including error cases

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>"
```

---

### Task 9: Question Service + Quality Gate

**Files:**
- Create: `server/apps/backend/app/services/learning/question_service.py`
- Test: `server/tests/backend/services/test_question_service.py`

- [ ] **Step 1: Write failing tests**

```python
# server/tests/backend/services/test_question_service.py
"""Tests for question CRUD and quality gate."""
import pytest
from sqlalchemy.orm import Session

from apps.backend.app.errors import AppError
from apps.backend.app.services.learning.question_service import (
    create_question,
    list_questions,
    get_question,
    validate_question,
)
from packages.db.models.learning.topic import LearningTopic


@pytest.fixture
def topic(db: Session):
    t = LearningTopic(
        topic_key="mt_q_svc",
        topic_type="concept",
        subject="mathematics",
        domain="arithmetic",
        name="Test",
        age_group="mid",
        evidence_json="[]",
        standards_json="[]",
    )
    db.add(t)
    db.flush()
    return t


def test_create_question(db: Session, topic):
    q = create_question(
        db=db,
        topic_id=topic.id,
        question_type="calculation",
        stem="37 + 58 = ?",
        stem_zh="计算：37 + 58 = ?",
        answer={"answer": 95},
        difficulty=1,
        bloom_level="apply",
        source="template",
        age_group="mid",
    )
    assert q.id is not None
    assert q.review_status == "approved"  # Template auto-approved


def test_create_question_invalid_topic(db: Session):
    with pytest.raises(AppError):
        create_question(
            db=db,
            topic_id=999999,  # Non-existent
            question_type="calculation",
            stem="Test",
            answer={"answer": 1},
            difficulty=1,
            bloom_level="apply",
            source="template",
            age_group="mid",
        )


def test_validate_question_passes(db: Session, topic):
    errors = validate_question(
        topic_id=topic.id,
        question_type="calculation",
        stem="Test",
        answer={"answer": 95},
        age_group="mid",
        db=db,
    )
    assert errors == []


def test_validate_question_empty_stem(db: Session, topic):
    errors = validate_question(
        topic_id=topic.id,
        question_type="calculation",
        stem="",
        answer={"answer": 95},
        age_group="mid",
        db=db,
    )
    assert len(errors) > 0
    assert any("stem" in e.lower() for e in errors)


def test_validate_question_multiple_choice_missing_options(db: Session, topic):
    errors = validate_question(
        topic_id=topic.id,
        question_type="multiple_choice",
        stem="Test",
        answer={"key": "A"},
        options=None,  # Missing!
        age_group="mid",
        db=db,
    )
    assert len(errors) > 0


def test_list_questions_by_topic(db: Session, topic):
    create_question(
        db=db, topic_id=topic.id, question_type="calculation",
        stem="Q1", answer={"answer": 1}, difficulty=1,
        bloom_level="apply", source="template", age_group="mid",
    )
    create_question(
        db=db, topic_id=topic.id, question_type="calculation",
        stem="Q2", answer={"answer": 2}, difficulty=2,
        bloom_level="apply", source="template", age_group="mid",
    )
    qs = list_questions(db=db, topic_id=topic.id)
    assert len(qs) == 2
```

- [ ] **Step 2: Run to verify failure**

```bash
cd server && uv run pytest tests/backend/services/test_question_service.py -v
```

Expected: FAIL

- [ ] **Step 3: Implement question service**

```python
# server/apps/backend/app/services/learning/question_service.py
"""Question CRUD and quality gate service."""
import json

from sqlalchemy.orm import Session

from apps.backend.app.errors import AppError, ErrorCode
from packages.core.logging import get_logger
from packages.db.models.learning.question import Question, QuestionKnowledgePoint
from packages.db.models.learning.topic import LearningTopic

logger = get_logger(__name__)


def validate_question(
    topic_id: int,
    question_type: str,
    stem: str,
    answer: dict,
    age_group: str,
    db: Session,
    options: list[dict] | None = None,
) -> list[str]:
    """Validate question data. Returns list of error messages (empty = valid)."""
    errors = []

    if not stem or not stem.strip():
        errors.append("Stem must not be empty")

    if not answer:
        errors.append("Answer must not be empty")

    # Topic existence check
    topic = db.query(LearningTopic).filter_by(id=topic_id).first()
    if not topic:
        errors.append(f"Topic {topic_id} does not exist")

    # Type-specific validation
    if question_type == "multiple_choice":
        if not options or len(options) < 2:
            errors.append("Multiple choice questions must have at least 2 options")
        if "key" not in answer:
            errors.append("Multiple choice answer must have 'key' field")

    if question_type == "calculation":
        if "answer" not in answer:
            errors.append("Calculation answer must have 'answer' field")

    return errors


def create_question(
    db: Session,
    topic_id: int,
    question_type: str,
    stem: str,
    answer: dict,
    difficulty: int,
    bloom_level: str,
    source: str,
    age_group: str,
    stem_zh: str | None = None,
    options: list[dict] | None = None,
    solution: dict | None = None,
    parameters: dict | None = None,
) -> Question:
    """Create a question with quality gate validation.

    Template-generated questions are auto-approved.
    LLM-generated questions start as 'pending'.
    """
    # Validate
    errors = validate_question(
        topic_id=topic_id, question_type=question_type,
        stem=stem, answer=answer, age_group=age_group,
        db=db, options=options,
    )
    if errors:
        raise AppError(ErrorCode.PRACTICE_QUESTION_INVALID, details="; ".join(errors))

    # Determine review status
    review_status = "approved" if source == "template" else "pending"

    question = Question(
        topic_id=topic_id,
        question_type=question_type,
        stem=stem,
        stem_zh=stem_zh,
        options_json=json.dumps(options) if options else None,
        answer_json=json.dumps(answer),
        solution_json=json.dumps(solution) if solution else None,
        difficulty=difficulty,
        bloom_level=bloom_level,
        source=source,
        review_status=review_status,
        age_group=age_group,
        parameters_json=json.dumps(parameters) if parameters else None,
    )
    db.add(question)
    db.flush()

    # Create primary knowledge point link
    qkp = QuestionKnowledgePoint(
        question_id=question.id,
        topic_id=topic_id,
        role="primary",
    )
    db.add(qkp)
    db.flush()

    logger.info(
        "Question created: id=%s, topic_id=%s, type=%s, source=%s",
        question.id, topic_id, question_type, source,
    )
    return question


def list_questions(
    db: Session,
    topic_id: int | None = None,
    question_type: str | None = None,
    difficulty: int | None = None,
    limit: int = 50,
) -> list[Question]:
    """List questions with optional filters."""
    query = db.query(Question).filter(Question.review_status == "approved")
    if topic_id:
        query = query.filter(Question.topic_id == topic_id)
    if question_type:
        query = query.filter(Question.question_type == question_type)
    if difficulty:
        query = query.filter(Question.difficulty == difficulty)
    return query.limit(limit).all()


def get_question(db: Session, question_id: int) -> Question | None:
    """Get a question by ID."""
    return db.query(Question).filter_by(id=question_id).first()
```

- [ ] **Step 4: Run tests**

```bash
cd server && uv run pytest tests/backend/services/test_question_service.py -v
```

Expected: 6 tests PASS

- [ ] **Step 5: Commit**

```bash
git add server/apps/backend/app/services/learning/question_service.py \
       server/tests/backend/services/test_question_service.py
git commit -m "feat(learning): add question service with quality gate

- validate_question: stem, answer, topic existence, type-specific checks
- create_question: auto-approve template, pending for LLM, primary QKP link
- list_questions: filter by topic, type, difficulty
- Full test coverage

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>"
```

---

### Task 10: Practice Router

**Files:**
- Create: `server/apps/backend/app/routers/practice.py`
- Modify: `server/apps/backend/app/main.py` (register router)
- Test: `server/tests/backend/routers/test_practice.py`

- [ ] **Step 1: Write failing router tests**

```python
# server/tests/backend/routers/test_practice.py
"""Tests for practice API endpoints."""
import pytest
from sqlalchemy.orm import Session

from packages.db.models.learning.topic import LearningTopic
from packages.db.models.learning.question import Question
from packages.db.models.learning.progress import LearningProgress


@pytest.fixture
def topic(db: Session):
    t = LearningTopic(
        topic_key="mt_router_test",
        topic_type="concept",
        subject="mathematics",
        domain="arithmetic",
        name="Router test",
        age_group="mid",
        evidence_json="[]",
        standards_json="[]",
    )
    db.add(t)
    db.flush()
    return t


@pytest.fixture
def questions(db: Session, topic):
    import json
    qs = []
    for i in range(5):
        q = Question(
            topic_id=topic.id,
            question_type="calculation",
            stem=f"Q{i}",
            answer_json=json.dumps({"answer": i + 1}),
            difficulty=1,
            bloom_level="apply",
            source="template",
            review_status="approved",
            age_group="mid",
        )
        db.add(q)
        qs.append(q)
    db.flush()
    return qs


@pytest.fixture
def progress(db: Session, topic):
    p = LearningProgress(child_id=1, topic_id=topic.id, mastery_level="learning")
    db.add(p)
    db.flush()
    return p


def test_create_session_endpoint(client, auth_headers, topic, questions):
    resp = client.post(
        "/api/v1/practice/sessions",
        json={"topic_id": topic.id, "session_mode": "practice", "count": 3},
        headers=auth_headers,
    )
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["session_mode"] == "practice"
    assert len(data["question_ids"]) == 3


def test_submit_answer_endpoint(client, auth_headers, topic, questions):
    # Create session first
    resp = client.post(
        "/api/v1/practice/sessions",
        json={"topic_id": topic.id, "count": 1},
        headers=auth_headers,
    )
    session_id = resp.json()["data"]["id"]

    # Submit answer
    resp = client.post(
        f"/api/v1/practice/sessions/{session_id}/answer",
        json={
            "question_id": questions[0].id,
            "user_answer": {"answer": questions[0].answer["answer"]},
            "time_spent_seconds": 10,
        },
        headers=auth_headers,
    )
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["is_correct"] is True


def test_finish_session_endpoint(client, auth_headers, topic, questions):
    # Create session
    resp = client.post(
        "/api/v1/practice/sessions",
        json={"topic_id": topic.id, "count": 2},
        headers=auth_headers,
    )
    session_id = resp.json()["data"]["id"]
    q_ids = resp.json()["data"]["question_ids"]

    # Answer 2 questions
    for i, qid in enumerate(q_ids):
        client.post(
            f"/api/v1/practice/sessions/{session_id}/answer",
            json={"question_id": qid, "user_answer": {"answer": i + 1}},
            headers=auth_headers,
        )

    # Finish
    resp = client.post(
        f"/api/v1/practice/sessions/{session_id}/finish",
        headers=auth_headers,
    )
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert "total_score" in data
    assert data["total_count"] == 2


def test_no_questions_returns_404(client, auth_headers, topic):
    """Topic with no approved questions returns error."""
    empty_topic = LearningTopic(
        topic_key="mt_empty_topic",
        topic_type="concept",
        subject="mathematics",
        domain="empty",
        name="Empty",
        age_group="mid",
        evidence_json="[]",
        standards_json="[]",
    )
    from apps.backend.app.database import get_db
    db = next(get_db())
    db.add(empty_topic)
    db.commit()
    db.close()

    resp = client.post(
        "/api/v1/practice/sessions",
        json={"topic_id": empty_topic.id, "count": 5},
        headers=auth_headers,
    )
    assert resp.status_code == 404
```

- [ ] **Step 2: Run to verify failure**

```bash
cd server && uv run pytest tests/backend/routers/test_practice.py -v
```

Expected: FAIL — 404 on all endpoints (router not registered)

- [ ] **Step 3: Implement practice router**

```python
# server/apps/backend/app/routers/practice.py
"""Practice system API endpoints."""
import json

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from apps.backend.app.auth.deps import get_current_user_or_child
from apps.backend.app.database import get_db
from apps.backend.app.errors import AppError, ErrorCode
from apps.backend.app.models.user import User
from apps.backend.app.schemas.practice import (
    PracticeAttemptResponse,
    PracticeResultResponse,
    PracticeSessionResponse,
    QuestionResponse,
    SessionCreateRequest,
    SubmitAnswerRequest,
)
from apps.backend.app.services.learning.adaptive_service import select_questions
from apps.backend.app.services.learning.practice_service import (
    create_session,
    finish_session,
    get_session,
    submit_answer,
)
from apps.backend.app.services.learning.progress_service import get_or_create_progress
from packages.core.logging import get_logger
from packages.db.models.learning.progress import LearningProgress
from packages.db.models.learning.topic import LearningTopic

logger = get_logger(__name__)

router = APIRouter(prefix="/practice", tags=["practice"])


@router.post("/sessions", response_model=PracticeSessionResponse)
def create_practice_session(
    req: SessionCreateRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user_or_child),
):
    """Create a new practice session with adaptive question selection."""
    # Verify topic exists
    topic = db.query(LearningTopic).filter_by(id=req.topic_id).first()
    if not topic:
        raise AppError(ErrorCode.PRACTICE_TOPIC_NOT_FOUND)

    # Get child's mastery level for adaptive selection
    progress = get_or_create_progress(db, user.id, req.topic_id)

    # Select questions
    questions = select_questions(
        db=db,
        topic_id=req.topic_id,
        mastery_level=progress.mastery_level,
        count=req.count,
        exclude_question_ids=[],
        exclude_recent_days=7,
        child_id=user.id,
    )

    if not questions:
        raise AppError(ErrorCode.PRACTICE_NO_QUESTIONS_AVAILABLE)

    session = create_session(
        db=db,
        child_id=user.id,
        topic_id=req.topic_id,
        session_mode=req.session_mode,
        question_ids=[q.id for q in questions],
    )
    return session


@router.post("/sessions/{session_id}/answer", response_model=PracticeAttemptResponse)
def submit_practice_answer(
    session_id: int,
    req: SubmitAnswerRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user_or_child),
):
    """Submit an answer for a question in a practice session."""
    session = get_session(db, session_id)
    if not session or session.child_id != user.id:
        raise AppError(ErrorCode.PRACTICE_SESSION_NOT_FOUND)
    if session.ended_at is not None:
        raise AppError(ErrorCode.PRACTICE_SESSION_ALREADY_ENDED)

    attempt = submit_answer(
        db=db,
        session_id=session_id,
        question_id=req.question_id,
        child_id=user.id,
        topic_id=session.topic_id,
        user_answer=req.user_answer,
        time_spent_seconds=req.time_spent_seconds,
    )
    return attempt


@router.post("/sessions/{session_id}/finish", response_model=PracticeResultResponse)
def finish_practice_session(
    session_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user_or_child),
):
    """Finish a practice session and calculate final score."""
    # Verify ownership BEFORE modifying session
    session = get_session(db, session_id)
    if not session or session.child_id != user.id:
        raise AppError(ErrorCode.PRACTICE_SESSION_NOT_FOUND)

    result = finish_session(db=db, session_id=session_id, child_id=user.id)

    # TODO Phase 2: trigger progress state machine update + XP/coin rewards
    return PracticeResultResponse(
        session_id=session_id,
        total_score=result["total_score"],
        correct_count=result["correct_count"],
        total_count=result["total_count"],
        xp_earned=0,       # Phase 2
        coins_earned=0,    # Phase 2
        mastery_changed=False,  # Phase 2
        new_mastery_level=None,  # Phase 2
    )
```

- [ ] **Step 4: Register router in main.py**

In `server/apps/backend/app/main.py`, add the import and registration:

```python
# Add import (around line 149, near other learning routers)
from apps.backend.app.routers import practice as practice_router

# Add router registration (around line 650, near other learning routers)
app.include_router(practice_router.router, prefix="/api/v1")
```

- [ ] **Step 5: Run tests**

```bash
cd server && uv run pytest tests/backend/routers/test_practice.py -v
```

Expected: 4 tests PASS

- [ ] **Step 6: Run full backend test suite to ensure no regressions**

```bash
cd server && uv run pytest tests/backend/ -v --tb=short 2>&1 | tail -30
```

Expected: All tests pass (existing tests unaffected)

- [ ] **Step 7: Commit**

```bash
git add server/apps/backend/app/routers/practice.py \
       server/apps/backend/app/main.py \
       server/tests/backend/routers/test_practice.py
git commit -m "feat(learning): add practice API router

- POST /practice/sessions: create session with adaptive selection
- POST /practice/sessions/{id}/answer: submit answer with auto-grading
- POST /practice/sessions/{id}/finish: calculate score + result
- Router registered in main.py
- Full integration test coverage

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>"
```

---

### Task 11: Progress Service Integration

**Files:**
- Modify: `server/apps/backend/app/services/learning/progress_service.py`
- Modify: `server/apps/backend/app/routers/practice.py` (fill in Phase 2 TODO)
- Test: `server/tests/backend/services/test_practice_progress_integration.py`

> **⚠️ Prerequisite:** Before implementing this task, add `'practice_session'` to the allowed `completed_via` values in `progress_service.py`'s `transition_to_mastered` function (currently validates against `('ai_assessment', 'parent_approval')`). Without this, the integration will silently bypass canonical validation.

- [ ] **Step 1: Write integration test**

```python
# server/tests/backend/services/test_practice_progress_integration.py
"""Tests for practice → progress state machine integration."""
import pytest
from sqlalchemy.orm import Session

from apps.backend.app.services.learning.practice_service import (
    create_session, submit_answer, finish_session,
)
from apps.backend.app.services.learning.practice_progress_integration import (
    update_progress_from_session,
)
from packages.db.models.learning.progress import LearningProgress
from packages.db.models.learning.question import Question
from packages.db.models.learning.topic import LearningTopic


@pytest.fixture
def topic(db: Session):
    t = LearningTopic(
        topic_key="mt_integration",
        topic_type="concept",
        subject="mathematics",
        domain="arithmetic",
        name="Integration test",
        age_group="mid",
        evidence_json="[]",
        standards_json="[]",
    )
    db.add(t)
    db.flush()
    return t


@pytest.fixture
def questions(db: Session, topic):
    import json
    qs = []
    for i in range(5):
        q = Question(
            topic_id=topic.id,
            question_type="calculation",
            stem=f"Q{i}",
            answer_json=json.dumps({"answer": i + 1}),
            difficulty=1,
            bloom_level="apply",
            source="template",
            review_status="approved",
            age_group="mid",
        )
        db.add(q)
        qs.append(q)
    db.flush()
    return qs


def test_high_score_transitions_learning_to_assessing(db: Session, topic, questions):
    """Score >= 0.8: learning → assessing."""
    progress = LearningProgress(child_id=1, topic_id=topic.id, mastery_level="learning")
    db.add(progress)
    db.flush()

    session = create_session(
        db=db, child_id=1, topic_id=topic.id,
        session_mode="practice",
        question_ids=[q.id for q in questions[:5]],
    )
    # All correct → score 1.0
    for q in questions[:5]:
        submit_answer(
            db=db, session_id=session.id, question_id=q.id,
            child_id=1, topic_id=topic.id,
            user_answer={"answer": q.answer["answer"]},
            time_spent_seconds=10,
        )
    finish_session(db=db, session_id=session.id, child_id=1)

    result = update_progress_from_session(db=db, session_id=session.id, child_id=1)
    assert result["mastery_changed"] is True
    assert result["new_mastery_level"] == "assessing"
    assert progress.mastery_level == "assessing"


def test_low_score_does_not_transition(db: Session, topic, questions):
    """Score < 0.5: no state transition, mastery_score updated."""
    progress = LearningProgress(child_id=1, topic_id=topic.id, mastery_level="learning")
    db.add(progress)
    db.flush()

    session = create_session(
        db=db, child_id=1, topic_id=topic.id,
        session_mode="practice",
        question_ids=[q.id for q in questions[:4]],
    )
    # All wrong
    for q in questions[:4]:
        submit_answer(
            db=db, session_id=session.id, question_id=q.id,
            child_id=1, topic_id=topic.id,
            user_answer={"answer": 99999},
            time_spent_seconds=10,
        )
    finish_session(db=db, session_id=session.id, child_id=1)

    result = update_progress_from_session(db=db, session_id=session.id, child_id=1)
    assert result["mastery_changed"] is False
    assert progress.mastery_level == "learning"  # Unchanged
```

- [ ] **Step 2: Implement integration**

```python
# server/apps/backend/app/services/learning/practice_progress_integration.py
"""Bridge between practice sessions and the learning progress state machine."""
from sqlalchemy.orm import Session

from apps.backend.app.services.learning.progress_service import (
    validate_transition,
    unlock_dependent_topics,
)
from packages.core.logging import get_logger
from packages.db.models.learning.practice import PracticeSession
from packages.db.models.learning.progress import LearningProgress

logger = get_logger(__name__)


def update_progress_from_session(
    db: Session,
    session_id: int,
    child_id: int,
) -> dict:
    """Update learning progress based on practice session results.

    Rules:
    - score >= 0.8: advance state (learning→assessing, assessing→mastered)
    - score < 0.5: no state change, update mastery_score
    - 0.5 <= score < 0.8: no state change, update mastery_score

    Returns dict with mastery_changed, new_mastery_level.
    """
    session = db.query(PracticeSession).filter_by(id=session_id).first()
    if not session or session.total_score is None:
        return {"mastery_changed": False, "new_mastery_level": None}

    progress = db.query(LearningProgress).filter_by(
        child_id=child_id, topic_id=session.topic_id
    ).first()
    if not progress:
        return {"mastery_changed": False, "new_mastery_level": None}

    score = session.total_score
    old_level = progress.mastery_level
    mastery_changed = False

    if score >= 0.8:
        # Determine target state
        if old_level == "learning":
            target = "assessing"
        elif old_level == "assessing":
            target = "mastered"
        else:
            target = None

        if target:
            try:
                validate_transition(old_level, target)
                progress.mastery_level = target
                progress.mastery_score = score
                progress.completed_via = "practice_session"
                db.flush()
                mastery_changed = True
                logger.info(
                    "Progress transition via practice: child=%s topic=%s %s→%s score=%.2f",
                    child_id, session.topic_id, old_level, target, score,
                )
                if target == "mastered":
                    unlock_dependent_topics(db, child_id, session.topic_id)
            except AppError:
                # Invalid transition per VALID_TRANSITIONS — log and skip
                logger.warning("Transition %s→%s not valid", old_level, target)
    else:
        # Update score without state change
        progress.mastery_score = score
        db.flush()

    return {
        "mastery_changed": mastery_changed,
        "new_mastery_level": progress.mastery_level,
    }
```

- [ ] **Step 3: Update finish_session in router to call integration**

In `server/apps/backend/app/routers/practice.py`, update `finish_practice_session`:

```python
from apps.backend.app.services.learning.practice_progress_integration import (
    update_progress_from_session,
)

# Replace the TODO section in finish_practice_session:
result = finish_session(db=db, session_id=session_id, child_id=user.id)
progress_result = update_progress_from_session(
    db=db, session_id=session_id, child_id=user.id,
)

return PracticeResultResponse(
    session_id=session_id,
    total_score=result["total_score"],
    correct_count=result["correct_count"],
    total_count=result["total_count"],
    xp_earned=10 if progress_result["mastery_changed"] else 0,
    coins_earned=10 if progress_result["mastery_changed"] else 0,
    mastery_changed=progress_result["mastery_changed"],
    new_mastery_level=progress_result["new_mastery_level"],
)
```

- [ ] **Step 4: Run tests**

```bash
cd server && uv run pytest tests/backend/services/test_practice_progress_integration.py -v
```

Expected: 2 tests PASS

- [ ] **Step 5: Commit**

```bash
git add server/apps/backend/app/services/learning/practice_progress_integration.py \
       server/apps/backend/app/routers/practice.py \
       server/tests/backend/services/test_practice_progress_integration.py
git commit -m "feat(learning): integrate practice with progress state machine

- update_progress_from_session: score>=0.8 advances state
- learning→assessing→mastered transitions via practice
- unlock_dependent_topics on mastery
- XP/coin rewards on mastery change
- Full integration test coverage

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>"
```

---

**Backend MVP complete.** Remaining tasks (12-16) are frontend implementation. Due to plan length, I'll summarize the remaining tasks with key files and acceptance criteria.

---

### Task 12-16: Frontend Implementation (Summary)

**Task 12: Frontend API + Types**
- Create: `frontend/apps/child/src/api/practice.ts`
- API functions: `createPracticeSession`, `submitAnswer`, `finishSession`
- TypeScript interfaces matching backend schemas (IDs as string)

**Task 13: PracticeSessionPage**
- Create: `frontend/apps/child/src/pages/learning/PracticeSessionPage.vue`
- Three phases: mode selection → question-by-question answering → result summary
- Uses Vant components: `van-button`, `van-field`, `van-progress`
- Route: `/learning/practice/:topicId`

**Task 14: Practice Components**
- Create: `PracticeQuestionCard.vue`, `PracticeAnswerInput.vue`, `PracticeResultSummary.vue`
- Question rendering by type, input switching, result display

**Task 15: LearningMapPage Integration**
- Modify: `frontend/apps/child/src/pages/learning/LearningMapPage.vue`
- Add "Start Practice" button on topic cards
- Navigate to PracticeSessionPage with topic_id

**Task 16: i18n + Router**
- Modify: `frontend/apps/child/src/i18n/locales/zh-CN.ts`, `en-US.ts`
- Modify: `frontend/apps/child/src/router/index.ts` — add PracticeSession route

**Frontend acceptance criteria:**
- Child can tap topic card → practice mode selection → answer 5 questions → see results
- Correct answer shows green feedback, wrong shows red + solution
- Result page shows score, XP earned, mastery change
- All strings via i18n `t()` function
- Snowflake IDs typed as `string` in TypeScript

---

## Phase 5: Weak Points API + Prerequisite Practice + Progress Page Enhancement

> **Phase 5 目标**: 让儿童和家长能看到薄弱环节、查看练习历史，并在练习后获得先修知识点复习推荐。
>
> **进入条件**: Phase 1 (Tasks 1-16) 已完成，51 tests pass。
>
> **执行顺序**: 5a → 5b → 5c（严格顺序，5b 依赖 5a 的 API，5c 依赖 5a+5b 的接口）。

### Phase 5 File Structure (新增/修改)

```
server/
├── apps/backend/app/
│   ├── routers/practice.py                    # MODIFY: 新增 3 个 GET endpoints + 1 个 recommend
│   ├── schemas/practice.py                    # MODIFY: 新增 response schemas
│   ├── services/learning/
│   │   ├── practice_service.py                # MODIFY: 新增 list_sessions, get_session_detail, get_weak_topics
│   │   └── adaptive_service.py                # MODIFY: 新增 find_weak_prerequisites, remedial select_questions
│   └── errors/codes.py                        # MODIFY: 新增 PRACTICE_SESSION_NOT_FOUND 复用
└── tests/backend/
    ├── routers/test_practice_phase5.py        # CREATE: GET endpoint tests
    └── services/
        ├── test_practice_service_phase5.py    # CREATE: weak topics + history tests
        └── test_adaptive_service_phase5.py    # CREATE: prerequisite weak tests

frontend/apps/child/src/
├── api/practice.ts                            # MODIFY: 新增 weak/sessions/recommend API
├── pages/learning/
│   ├── LearningProgressPage.vue               # MODIFY: 替换 "Coming soon" 为薄弱知识点卡片
│   └── PracticeSessionPage.vue                # MODIFY: 练习后推荐先修复习卡片
└── i18n/locales/zh-CN.ts, en-US.ts            # MODIFY: 新增 Phase 5 i18n keys
```

---

### Task 5a: Weak Points + History API (Backend)

**Goal**: 提供薄弱知识点发现、练习历史列表、练习详情查询能力。

**Files:**
- Modify: `server/apps/backend/app/schemas/practice.py`
- Modify: `server/apps/backend/app/services/learning/practice_service.py`
- Modify: `server/apps/backend/app/routers/practice.py`
- Create: `server/tests/backend/routers/test_practice_phase5.py`
- Create: `server/tests/backend/services/test_practice_service_phase5.py`

**Interfaces:**
- Consumes: `PracticeSession, PracticeAttempt, Question, LearningTopic, LearningProgress`
- Produces: `WeakTopicResponse, SessionListResponse, SessionDetailResponse`

- [ ] **Step 1: Add response schemas**

```python
# server/apps/backend/app/schemas/practice.py — 追加

class WeakTopicResponse(SnowflakeBase):
    """A topic where the child has low accuracy."""
    topic_id: int
    topic_name: str
    topic_name_zh: str | None
    total_attempts: int
    correct_attempts: int
    accuracy: float            # 0.0-1.0
    last_practice_at: datetime | None
    mastery_level: str

    model_config = ConfigDict(from_attributes=True)


class SessionListItem(SnowflakeBase):
    """Summary of a practice session for list view."""
    id: int
    topic_id: int
    topic_name: str
    topic_name_zh: str | None
    session_mode: str
    total_score: float | None
    completed_count: int
    total_count: int
    started_at: datetime
    ended_at: datetime | None

    model_config = ConfigDict(from_attributes=True)


class AttemptDetail(SnowflakeBase):
    """Single attempt with question context."""
    id: int
    question_id: int
    question_stem: str
    question_type: str
    user_answer: dict
    is_correct: bool
    time_spent_seconds: int | None
    attempt_number: int
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class SessionDetailResponse(SnowflakeBase):
    """Full session detail with attempts."""
    id: int
    topic_id: int
    topic_name: str
    topic_name_zh: str | None
    session_mode: str
    total_score: float | None
    completed_count: int
    total_count: int
    started_at: datetime
    ended_at: datetime | None
    attempts: list[AttemptDetail]
```

- [ ] **Step 2: Write failing tests**

```python
# server/tests/backend/services/test_practice_service_phase5.py
"""Tests for Phase 5 practice service additions."""
import json
import pytest
from datetime import UTC, datetime, timedelta
from sqlalchemy.orm import Session

from packages.db.models.learning.topic import LearningTopic
from packages.db.models.learning.question import Question
from packages.db.models.learning.practice import PracticeSession, PracticeAttempt
from packages.db.models.learning.progress import LearningProgress
from apps.backend.app.services.learning.practice_service import (
    get_weak_topics,
    list_sessions,
    get_session_detail,
)


@pytest.fixture
def topic(db: Session):
    t = LearningTopic(
        topic_key="mt_test_add", topic_type="concept", subject="mathematics",
        domain="arithmetic", name="Addition", name_zh="加法",
        age_group="mid", evidence_json="[]", standards_json="[]",
    )
    db.add(t)
    db.flush()
    return t


@pytest.fixture
def question(db: Session, topic):
    q = Question(
        topic_id=topic.id, question_type="calculation",
        stem="1 + 1 = ?", answer_json='{"answer": 2}',
        difficulty=1, bloom_level="apply", source="template",
        review_status="approved", age_group="mid",
    )
    db.add(q)
    db.flush()
    return q


@pytest.fixture
def session_with_attempts(db: Session, topic, question):
    """Create a completed session with mixed correct/wrong attempts."""
    s = PracticeSession(
        child_id=1, topic_id=topic.id, session_mode="practice",
        question_ids_json=json.dumps([question.id]),
        source="adaptive",
        started_at=datetime.now(UTC) - timedelta(hours=1),
        ended_at=datetime.now(UTC),
        total_score=0.5, completed_count=2,
    )
    db.add(s)
    db.flush()
    # Correct attempt
    db.add(PracticeAttempt(
        session_id=s.id, question_id=question.id, child_id=1,
        topic_id=topic.id, user_answer_json='{"answer": 2}',
        is_correct=True, time_spent_seconds=10, attempt_number=1,
    ))
    db.flush()
    return s


def test_get_weak_topics_returns_accuracy(db: Session, topic, session_with_attempts):
    weak = get_weak_topics(db, child_id=1, limit=10)
    assert len(weak) >= 1
    w = weak[0]
    assert w["topic_id"] == topic.id
    assert w["total_attempts"] == 1
    assert w["accuracy"] == 1.0  # 1 correct out of 1


def test_list_sessions_returns_ordered(db: Session, topic, session_with_attempts):
    sessions = list_sessions(db, child_id=1, limit=10)
    assert len(sessions) >= 1
    assert sessions[0].id == session_with_attempts.id


def test_get_session_detail_includes_attempts(db: Session, topic, session_with_attempts):
    detail = get_session_detail(db, session_id=session_with_attempts.id, child_id=1)
    assert detail is not None
    assert len(detail["attempts"]) == 1
    assert detail["attempts"][0]["is_correct"] is True
```

- [ ] **Step 3: Implement service functions**

```python
# server/apps/backend/app/services/learning/practice_service.py — 追加

from sqlalchemy import func as sa_func

from packages.db.models.learning.topic import LearningTopic
from packages.db.models.learning.progress import LearningProgress


def get_weak_topics(db: Session, child_id: int, limit: int = 10, min_attempts: int = 3) -> list[dict]:
    """Find topics where the child has low accuracy (sorted by accuracy ASC).

    Only includes topics with >= min_attempts total attempts.
    """
    rows = (
        db.query(
            PracticeAttempt.topic_id,
            sa_func.count(PracticeAttempt.id).label("total"),
            sa_func.sum(sa_func.cast(PracticeAttempt.is_correct, sa_Integer)).label("correct"),
            sa_func.max(PracticeAttempt.created_at).label("last_at"),
        )
        .filter(PracticeAttempt.child_id == child_id)
        .group_by(PracticeAttempt.topic_id)
        .having(sa_func.count(PracticeAttempt.id) >= min_attempts)
        .all()
    )

    results = []
    for row in rows:
        topic = db.query(LearningTopic).filter_by(id=row.topic_id).first()
        progress = (
            db.query(LearningProgress)
            .filter_by(child_id=child_id, topic_id=row.topic_id)
            .first()
        )
        accuracy = row.correct / row.total if row.total > 0 else 0.0
        results.append({
            "topic_id": row.topic_id,
            "topic_name": topic.name if topic else "",
            "topic_name_zh": topic.name_zh if topic else None,
            "total_attempts": row.total,
            "correct_attempts": row.correct,
            "accuracy": accuracy,
            "last_practice_at": row.last_at,
            "mastery_level": progress.mastery_level if progress else "available",
        })

    results.sort(key=lambda r: r["accuracy"])
    return results[:limit]


def list_sessions(db: Session, child_id: int, limit: int = 20, offset: int = 0) -> list[PracticeSession]:
    """List practice sessions for a child, most recent first."""
    return (
        db.query(PracticeSession)
        .filter(PracticeSession.child_id == child_id)
        .order_by(PracticeSession.started_at.desc())
        .offset(offset)
        .limit(limit)
        .all()
    )


def get_session_detail(db: Session, session_id: int, child_id: int) -> dict | None:
    """Get full session detail with attempts and question context."""
    session = (
        db.query(PracticeSession)
        .filter_by(id=session_id, child_id=child_id)
        .first()
    )
    if not session:
        return None

    topic = db.query(LearningTopic).filter_by(id=session.topic_id).first()
    attempts = (
        db.query(PracticeAttempt)
        .filter_by(session_id=session_id)
        .order_by(PracticeAttempt.created_at.asc())
        .all()
    )

    attempt_details = []
    for a in attempts:
        q = db.query(Question).filter_by(id=a.question_id).first()
        attempt_details.append({
            "id": a.id,
            "question_id": a.question_id,
            "question_stem": q.stem if q else "",
            "question_type": q.question_type if q else "",
            "user_answer": a.user_answer,
            "is_correct": a.is_correct,
            "time_spent_seconds": a.time_spent_seconds,
            "attempt_number": a.attempt_number,
            "created_at": a.created_at,
        })

    return {
        "id": session.id,
        "topic_id": session.topic_id,
        "topic_name": topic.name if topic else "",
        "topic_name_zh": topic.name_zh if topic else None,
        "session_mode": session.session_mode,
        "total_score": session.total_score,
        "completed_count": session.completed_count,
        "total_count": len(session.question_ids),
        "started_at": session.started_at,
        "ended_at": session.ended_at,
        "attempts": attempt_details,
    }
```

- [ ] **Step 4: Add GET endpoints to router**

```python
# server/apps/backend/app/routers/practice.py — 追加

from apps.backend.app.schemas.practice import (
    WeakTopicResponse,
    SessionListItem,
    SessionDetailResponse,
)
from apps.backend.app.services.learning.practice_service import (
    get_weak_topics,
    list_sessions,
    get_session_detail,
)


@router.get("/weak-topics", response_model=list[WeakTopicResponse])
def get_weak_topics_endpoint(
    limit: int = 10,
    min_attempts: int = 3,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user_or_child),
):
    """Get topics where the child has low accuracy, sorted weakest first."""
    return get_weak_topics(db, child_id=user.id, limit=limit, min_attempts=min_attempts)


@router.get("/sessions", response_model=list[SessionListItem])
def list_practice_sessions(
    limit: int = 20,
    offset: int = 0,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user_or_child),
):
    """List practice sessions for the current child."""
    sessions = list_sessions(db, child_id=user.id, limit=limit, offset=offset)
    results = []
    for s in sessions:
        topic = db.query(LearningTopic).filter_by(id=s.topic_id).first()
        question_ids = json.loads(s.question_ids_json) if s.question_ids_json else []
        results.append(SessionListItem(
            id=s.id,
            topic_id=s.topic_id,
            topic_name=topic.name if topic else "",
            topic_name_zh=topic.name_zh if topic else None,
            session_mode=s.session_mode,
            total_score=s.total_score,
            completed_count=s.completed_count,
            total_count=len(question_ids),
            started_at=s.started_at,
            ended_at=s.ended_at,
        ))
    return results


@router.get("/sessions/{session_id}", response_model=SessionDetailResponse)
def get_practice_session_detail(
    session_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user_or_child),
):
    """Get full practice session detail with question-level attempts."""
    detail = get_session_detail(db, session_id=session_id, child_id=user.id)
    if not detail:
        raise AppError(ErrorCode.PRACTICE_SESSION_NOT_FOUND)
    return SessionDetailResponse(**detail)
```

- [ ] **Step 5: Run tests and commit**

```bash
cd server && uv run pytest tests/backend/services/test_practice_service_phase5.py tests/backend/routers/test_practice_phase5.py -v
```

```bash
git add -A
git commit -m "feat(learning): add weak points, session history, and detail APIs (Phase 5a)

- GET /practice/weak-topics: topics sorted by accuracy ASC
- GET /practice/sessions: paginated session history
- GET /practice/sessions/{id}: full detail with per-question attempts
- get_weak_topics: GROUP BY topic_id HAVING min_attempts
- list_sessions: ordered by started_at DESC
- get_session_detail: session + attempts + question context
- Full test coverage

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>"
```

---

### Task 5b: Prerequisite Weak Practice (Backend)

**Goal**: 当儿童在某知识点表现不佳时，检测先修知识点是否也存在薄弱环节，推荐针对性复习。

**Files:**
- Modify: `server/apps/backend/app/services/learning/adaptive_service.py`
- Modify: `server/apps/backend/app/services/learning/practice_service.py`
- Modify: `server/apps/backend/app/routers/practice.py`
- Create: `server/tests/backend/services/test_adaptive_service_phase5.py`

**Interfaces:**
- Consumes: `LearningDependency, LearningProgress, PracticeAttempt, get_unmet_prerequisites()`
- Produces: `PrerequisiteRecommendation, remedial select_questions mode`

- [ ] **Step 1: Write failing tests**

```python
# server/tests/backend/services/test_adaptive_service_phase5.py
"""Tests for Phase 5b: prerequisite weak practice."""
import pytest
from sqlalchemy.orm import Session

from packages.db.models.learning.topic import LearningTopic
from packages.db.models.learning.progress import LearningProgress
from packages.db.models.learning.dependency import LearningDependency
from apps.backend.app.services.learning.adaptive_service import (
    find_weak_prerequisites,
)


@pytest.fixture
def parent_topic(db: Session):
    t = LearningTopic(
        topic_key="mt_parent", topic_type="concept", subject="mathematics",
        domain="arithmetic", name="Multi-digit Addition", name_zh="多位数加法",
        age_group="mid", evidence_json="[]", standards_json="[]",
    )
    db.add(t)
    db.flush()
    return t


@pytest.fixture
def prereq_topic(db: Session):
    t = LearningTopic(
        topic_key="mt_prereq", topic_type="concept", subject="mathematics",
        domain="arithmetic", name="Single-digit Addition", name_zh="一位数加法",
        age_group="mid", evidence_json="[]", standards_json="[]",
    )
    db.add(t)
    db.flush()
    return t


@pytest.fixture
def dependency(db: Session, parent_topic, prereq_topic):
    d = LearningDependency(
        topic_id=parent_topic.id,
        prerequisite_id=prereq_topic.id,
        dependency_type="hard",
    )
    db.add(d)
    db.flush()
    return d


def test_find_weak_prerequisites_returns_unmet(db, parent_topic, prereq_topic, dependency):
    # Child has progress on prereq but not mastered
    progress = LearningProgress(
        child_id=1, topic_id=prereq_topic.id,
        mastery_level="learning",
    )
    db.add(progress)
    db.flush()

    weak_prereqs = find_weak_prerequisites(db, topic_id=parent_topic.id, child_id=1)
    assert len(weak_prereqs) == 1
    assert weak_prereqs[0]["topic_id"] == prereq_topic.id
```

- [ ] **Step 2: Implement find_weak_prerequisites**

```python
# server/apps/backend/app/services/learning/adaptive_service.py — 追加

from packages.db.models.learning.progress import LearningProgress
from packages.db.models.learning.topic import LearningTopic
from apps.backend.app.services.learning.progress_service import get_unmet_prerequisites


def find_weak_prerequisites(
    db: Session, topic_id: int, child_id: int
) -> list[dict]:
    """Find prerequisite topics that are weak (not mastered) for the child.

    Uses existing get_unmet_prerequisites() to find unmet prereqs,
    then enriches with accuracy data from PracticeAttempt.
    """
    unmet = get_unmet_prerequisites(db, topic_id=topic_id, child_id=child_id)

    results = []
    for prereq in unmet:
        # Get accuracy for this prereq
        attempts = (
            db.query(PracticeAttempt)
            .filter_by(child_id=child_id, topic_id=prereq.id)
            .all()
        )
        total = len(attempts)
        correct = sum(1 for a in attempts if a.is_correct) if attempts else 0
        accuracy = correct / total if total > 0 else 0.0

        progress = (
            db.query(LearningProgress)
            .filter_by(child_id=child_id, topic_id=prereq.id)
            .first()
        )

        results.append({
            "topic_id": prereq.id,
            "topic_name": prereq.name,
            "topic_name_zh": prereq.name_zh,
            "mastery_level": progress.mastery_level if progress else "available",
            "total_attempts": total,
            "accuracy": accuracy,
        })

    # Sort by accuracy ASC (weakest first)
    results.sort(key=lambda r: r["accuracy"])
    return results
```

- [ ] **Step 3: Add recommend endpoint**

```python
# server/apps/backend/app/routers/practice.py — 追加

from apps.backend.app.services.learning.adaptive_service import find_weak_prerequisites


class RecommendResponse(SnowflakeBase):
    topic_id: int
    topic_name: str
    topic_name_zh: str | None
    mastery_level: str
    accuracy: float
    is_prerequisite: bool
    prerequisite_of_topic_id: int | None


@router.get("/recommend", response_model=list[RecommendResponse])
def get_practice_recommendations(
    topic_id: int | None = None,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user_or_child),
):
    """Recommend topics for practice — weak prerequisites or weak topics.

    If topic_id is provided, checks for weak prerequisites of that topic.
    Otherwise, returns the child's overall weakest topics.
    """
    if topic_id:
        # Check weak prerequisites
        weak_prereqs = find_weak_prerequisites(db, topic_id=topic_id, child_id=user.id)
        return [
            RecommendResponse(
                topic_id=r["topic_id"],
                topic_name=r["topic_name"],
                topic_name_zh=r["topic_name_zh"],
                mastery_level=r["mastery_level"],
                accuracy=r["accuracy"],
                is_prerequisite=True,
                prerequisite_of_topic_id=topic_id,
            )
            for r in weak_prereqs
        ]
    else:
        # Overall weak topics
        from apps.backend.app.services.learning.practice_service import get_weak_topics
        weak = get_weak_topics(db, child_id=user.id, limit=5, min_attempts=1)
        return [
            RecommendResponse(
                topic_id=r["topic_id"],
                topic_name=r["topic_name"],
                topic_name_zh=r["topic_name_zh"],
                mastery_level=r["mastery_level"],
                accuracy=r["accuracy"],
                is_prerequisite=False,
                prerequisite_of_topic_id=None,
            )
            for r in weak
        ]
```

- [ ] **Step 4: Run tests and commit**

```bash
cd server && uv run pytest tests/backend/services/test_adaptive_service_phase5.py -v
```

```bash
git add -A
git commit -m "feat(learning): add prerequisite weak practice and recommend API (Phase 5b)

- find_weak_prerequisites: unmet prereqs enriched with accuracy data
- GET /practice/recommend: weak prereqs or overall weak topics
- Reuses existing get_unmet_prerequisites() from progress_service
- Full test coverage

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>"
```

---

### Task 5c: Frontend Progress Page Enhancement

**Goal**: 将 LearningProgressPage 的 "Coming soon" 占位符替换为薄弱知识点卡片、练习历史列表、以及练习后先修复习推荐。

**Files:**
- Modify: `frontend/apps/child/src/api/practice.ts`
- Modify: `frontend/apps/child/src/pages/learning/LearningProgressPage.vue`
- Modify: `frontend/apps/child/src/pages/learning/PracticeSessionPage.vue`
- Modify: `frontend/apps/child/src/i18n/locales/zh-CN.ts`, `en-US.ts`

- [ ] **Step 1: Add API functions to practice.ts**

```typescript
// frontend/apps/child/src/api/practice.ts — 追加

export interface WeakTopicResponse {
  topic_id: string
  topic_name: string
  topic_name_zh: string | null
  total_attempts: number
  correct_attempts: number
  accuracy: number
  last_practice_at: string | null
  mastery_level: string
}

export interface SessionListItem {
  id: string
  topic_id: string
  topic_name: string
  topic_name_zh: string | null
  session_mode: string
  total_score: number | null
  completed_count: number
  total_count: number
  started_at: string
  ended_at: string | null
}

export interface SessionDetailResponse {
  id: string
  topic_id: string
  topic_name: string
  topic_name_zh: string | null
  session_mode: string
  total_score: number | null
  completed_count: number
  total_count: number
  started_at: string
  ended_at: string | null
  attempts: Array<{
    id: string
    question_id: string
    question_stem: string
    question_type: string
    user_answer: Record<string, unknown>
    is_correct: boolean
    time_spent_seconds: number | null
    attempt_number: number
    created_at: string
  }>
}

export interface RecommendResponse {
  topic_id: string
  topic_name: string
  topic_name_zh: string | null
  mastery_level: string
  accuracy: number
  is_prerequisite: boolean
  prerequisite_of_topic_id: string | null
}

export async function getWeakTopics(
  limit = 10,
  minAttempts = 3,
): Promise<WeakTopicResponse[]> {
  const resp = await http.get('/api/v1/practice/weak-topics', {
    params: { limit, min_attempts: minAttempts },
  })
  return resp.data.data
}

export async function listPracticeSessions(
  limit = 20,
  offset = 0,
): Promise<SessionListItem[]> {
  const resp = await http.get('/api/v1/practice/sessions', {
    params: { limit, offset },
  })
  return resp.data.data
}

export async function getPracticeSessionDetail(
  sessionId: string,
): Promise<SessionDetailResponse> {
  const resp = await http.get(`/api/v1/practice/sessions/${sessionId}`)
  return resp.data.data
}

export async function getPracticeRecommendations(
  topicId?: string,
): Promise<RecommendResponse[]> {
  const params = topicId ? { topic_id: topicId } : {}
  const resp = await http.get('/api/v1/practice/recommend', { params })
  return resp.data.data
}
```

- [ ] **Step 2: Replace "Coming soon" in LearningProgressPage.vue**

在 `LearningProgressPage.vue` 的 `<!-- Coming soon placeholder -->` 处替换为：

```vue
<!-- Weak topics card -->
<div v-if="weakTopics.length > 0" class="weak-topics-section">
  <h2 class="section-title">{{ t('learning.progress.weakTopics') }}</h2>
  <div class="weak-topics-list">
    <div
      v-for="topic in weakTopics"
      :key="topic.topic_id"
      class="weak-topic-card"
      @click="navigateToPractice(topic.topic_id)"
    >
      <div class="weak-topic-card__header">
        <span class="weak-topic-card__name">{{ getTopicDisplayName(topic) }}</span>
        <span class="weak-topic-card__accuracy">{{ Math.round(topic.accuracy * 100) }}%</span>
      </div>
      <div class="weak-topic-card__footer">
        <span class="weak-topic-card__attempts">
          {{ topic.total_attempts }} {{ t('learning.progress.attempts') }}
        </span>
        <span :class="['weak-topic-card__mastery', `mastery--${topic.mastery_level}`]">
          {{ t(`learning.status.${topic.mastery_level}`) }}
        </span>
      </div>
    </div>
  </div>
</div>

<!-- Recent practice sessions -->
<div v-if="recentSessions.length > 0" class="sessions-section">
  <h2 class="section-title">{{ t('learning.progress.recentSessions') }}</h2>
  <div class="sessions-list">
    <div
      v-for="session in recentSessions"
      :key="session.id"
      class="session-card"
      @click="navigateToSessionDetail(session.id)"
    >
      <div class="session-card__header">
        <span class="session-card__topic">{{ getTopicDisplayName(session) }}</span>
        <span v-if="session.total_score != null" class="session-card__score">
          {{ Math.round(session.total_score * 100) }}%
        </span>
      </div>
      <div class="session-card__meta">
        <span>{{ session.completed_count }}/{{ session.total_count }}</span>
        <span>{{ formatDate(session.started_at) }}</span>
      </div>
    </div>
  </div>
</div>
```

Script 部分新增：

```typescript
import { getWeakTopics, listPracticeSessions, type WeakTopicResponse, type SessionListItem } from '@/api/practice'

const weakTopics = ref<WeakTopicResponse[]>([])
const recentSessions = ref<SessionListItem[]>([])

onMounted(async () => {
  const [weak, sessions] = await Promise.all([
    getWeakTopics(10, 1),  // min_attempts=1 以显示更多
    listPracticeSessions(10),
  ])
  weakTopics.value = weak
  recentSessions.value = sessions
})

function getTopicDisplayName(item: { topic_name: string; topic_name_zh: string | null }) {
  return locale.value === 'en-US' ? item.topic_name : (item.topic_name_zh || item.topic_name)
}

function navigateToPractice(topicId: string) {
  router.push(`/learning/practice/${topicId}`)
}

function navigateToSessionDetail(sessionId: string) {
  // Phase 5c: navigate to session detail page or modal
  router.push(`/learning/practice/sessions/${sessionId}`)
}
```

- [ ] **Step 3: Add post-practice recommendation in PracticeSessionPage.vue**

在练习结果汇总后添加先修复习推荐卡片：

```vue
<!-- Post-practice prerequisite recommendation -->
<div v-if="score < 0.8 && recommendations.length > 0" class="prereq-recommend">
  <h3>{{ t('learning.practice.prereqReview') }}</h3>
  <div
    v-for="rec in recommendations"
    :key="rec.topic_id"
    class="prereq-card"
    @click="startPrereqPractice(rec.topic_id)"
  >
    <span class="prereq-card__name">{{ getRecDisplayName(rec) }}</span>
    <span class="prereq-card__reason">
      {{ t('learning.practice.prereqReason', { accuracy: Math.round(rec.accuracy * 100) }) }}
    </span>
  </div>
</div>
```

- [ ] **Step 4: Add i18n keys**

```typescript
// zh-CN.ts 追加
'learning.progress.weakTopics': '薄弱知识点',
'learning.progress.attempts': '次练习',
'learning.progress.recentSessions': '最近练习',
'learning.practice.prereqReview': '建议复习先修知识点',
'learning.practice.prereqReason': '正确率 {accuracy}%，建议先巩固',

// en-US.ts 追加
'learning.progress.weakTopics': 'Weak Topics',
'learning.progress.attempts': 'attempts',
'learning.progress.recentSessions': 'Recent Sessions',
'learning.practice.prereqReview': 'Recommended Prerequisite Review',
'learning.practice.prereqReason': '{accuracy}% accuracy — review first',
```

- [ ] **Step 5: Verify and commit**

```bash
cd frontend && pnpm -r typecheck && pnpm -r lint
```

```bash
git add -A
git commit -m "feat(learning): enhance progress page with weak topics and session history (Phase 5c)

- Replace 'Coming soon' placeholder with weak topics card
- Add recent practice sessions list
- Add post-practice prerequisite review recommendation
- API functions: getWeakTopics, listPracticeSessions, getPracticeRecommendations
- Full i18n coverage (zh-CN + en-US)

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>"
```

---

### Phase 5 Verification

**Acceptance criteria:**
- [ ] 儿童在 LearningProgressPage 能看到薄弱知识点卡片（按正确率升序）
- [ ] 儿童能查看练习历史列表（时间倒序）
- [ ] 练习得分 < 80% 时，结果页显示先修知识点复习推荐
- [ ] `GET /practice/weak-topics` 返回正确的准确率统计
- [ ] `GET /practice/sessions` 返回分页会话列表
- [ ] `GET /practice/sessions/{id}` 返回完整作答详情
- [ ] `GET /practice/recommend?topic_id=X` 返回薄弱先修知识点
- [ ] 所有新增 API 测试通过
- [ ] 前端 typecheck + lint 通过
- [ ] i18n 全覆盖，无硬编码中文
