# Agent-First Architecture Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Upgrade Numina AI from Skill-first to Agent-first architecture — users select Agents (not Skills), Skills become internal capabilities, full DeerFlow harness native execution, family tenant isolation via database.

**Architecture:** DB-driven agent config (`ai_agents` table) + runtime temp directory generation → DeerFlow `make_lead_agent()` → LangGraph streaming. Unified `ai_` prefix naming for all 4 AI tables. Two builtin agents (资产健康顾问, 财务优化师) seeded at migration time. Frontend AIHubPage refactored to Agent card grid.

**Tech Stack:** Python 3.12 / FastAPI / SQLAlchemy / Alembic / LangGraph / DeerFlow harness | Vue 3 / TypeScript / Vite / Vant 4 / Pinia

**Spec:** `docs/superpowers/specs/2026-05-21-agent-first-architecture-design.md`

---

## File Structure

### Backend — New Files

| File | Responsibility |
|------|---------------|
| `server/apps/backend/alembic/versions/x2581y64zqr9_unify_ai_tables_and_add_agents.py` | Alembic migration: rename 3 tables + create `ai_agents` + seed builtin agents |
| `server/apps/backend/app/models/ai_agent.py` | SQLAlchemy model for `ai_agents` table |
| `server/apps/backend/app/schemas/ai_agent.py` | Pydantic schemas: `AgentCreateRequest`, `AgentUpdateRequest`, `AgentResponse`, `AgentListResponse` |
| `server/apps/backend/app/routers/ai_agents.py` | REST API router: CRUD + toggle for agents |
| `server/apps/backend/app/routers/ai_agents_internal.py` | Internal API: `GET /internal/ai/agents/{id}` for agent service |
| `server/tests/backend/test_ai_agents.py` | Tests for Agent CRUD + tenant isolation + permissions |

### Backend — Modified Files

| File | Change |
|------|--------|
| `server/apps/backend/app/models/ai_provider_config.py` | `__tablename__` → `'ai_providers'` |
| `server/apps/backend/app/models/family_mcp_server.py` | `__tablename__` → `'ai_mcp_servers'` |
| `server/apps/backend/app/models/skill_registry.py` | `__tablename__` → `'ai_skills'` |
| `server/apps/backend/app/models/__init__.py` | Add `AIAgent` import |
| `server/apps/backend/alembic/env.py` | Add `AIAgent` import |
| `server/apps/backend/app/main.py` | Register `ai_agents_router` and `ai_agents_internal_router` |

### Agent Service — New Files

| File | Responsibility |
|------|---------------|
| `server/apps/agent/services/agent_temp_cache.py` | LRU cache for agent temp directories (SOUL.md + config.yaml) |
| `server/apps/agent/services/agent_dispatch.py` | `stream_agent_dispatch()` — the new Agent-first execution entry point |

### Agent Service — Modified Files

| File | Change |
|------|--------|
| `server/apps/agent/core/backend_client.py` | Add `get_agent_config(agent_id, family_id)` method |
| `server/apps/agent/app/main.py` | Register new agent stream router |
| `server/apps/agent/services/stream_events.py` | Already has `EventStreamBuilder` — no changes needed |

### Frontend — New Files

| File | Responsibility |
|------|---------------|
| `frontend/apps/main/src/components/agent/AgentCard.vue` | Agent card component (icon + name + desc + action) |
| `frontend/apps/main/src/components/agent/AgentGrid.vue` | Agent card grid layout (builtin + custom sections) |
| `frontend/apps/main/src/stores/agent.ts` | Pinia store: Agent list, CRUD, current agent |
| `frontend/apps/main/src/api/agent.ts` | Agent API: list, create, update, delete, toggle, stream |
| `frontend/apps/main/src/pages/AgentsManagePage.vue` | Settings > Agent management page |
| `frontend/apps/main/src/pages/AgentFormPage.vue` | Create/edit agent form page |
| `frontend/apps/main/src/types/agent.ts` | TypeScript types for Agent |

### Frontend — Modified Files

| File | Change |
|------|--------|
| `frontend/apps/main/src/pages/AIHubPage.vue` | Replace capability grid with Agent card grid |
| `frontend/apps/main/src/pages/SettingsPage.vue` | Add "智能体管理" cell in AI settings group |
| `frontend/apps/main/src/router/index.ts` | Add agent management routes |
| `frontend/apps/main/src/i18n/locales/zh-CN.ts` | Add `agents.*` i18n keys |

---

## Task 1: Alembic Migration — Rename Tables + Create `ai_agents`

**Files:**
- Create: `server/apps/backend/alembic/versions/x2581y64zqr9_unify_ai_tables_and_add_agents.py`

This migration has multiple heads to merge: `v1461w65xpq7` (merge head) and `u1470x53wpq8` (skill_registry). The new migration merges them and applies all table changes.

- [ ] **Step 1: Write the migration file**

```python
# server/apps/backend/alembic/versions/x2581y64zqr9_unify_ai_tables_and_add_agents.py
"""unify AI table names to ai_ prefix and add ai_agents table

Revision ID: x2581y64zqr9
Revises: v1461w65xpq7, u1470x53wpq8
Create Date: 2026-05-22
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision: str = "x2581y64zqr9"
down_revision: Union[str, None] = ("v1461w65xpq7", "u1470x53wpq8")
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Rename existing tables to unified ai_ prefix + plural
    op.rename_table("ai_provider_configs", "ai_providers")
    op.rename_table("family_mcp_servers", "ai_mcp_servers")
    op.rename_table("skill_registry", "ai_skills")

    # 2. Create ai_agents table
    op.create_table(
        "ai_agents",
        sa.Column("id", sa.BigInteger(), nullable=False),
        sa.Column("family_id", sa.BigInteger(), nullable=False),
        sa.Column("agent_name", sa.String(64), nullable=False),
        sa.Column("display_name", sa.String(128), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("icon", sa.String(16), nullable=True),
        sa.Column("color", sa.String(16), nullable=True),
        sa.Column("soul_md", sa.Text(), nullable=False),
        sa.Column("skills", JSONB(), nullable=True),
        sa.Column("model", sa.String(64), nullable=True),
        sa.Column("subagent_enabled", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("tool_groups", JSONB(), nullable=True),
        sa.Column("is_builtin", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("is_enabled", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("display_order", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("created_by", sa.BigInteger(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("family_id", "agent_name", name="uq_ai_agents_family_name"),
        sa.CheckConstraint("agent_name ~ '^[a-z][a-z0-9_-]*$'", name="ck_ai_agents_name_format"),
    )
    op.create_index("ix_ai_agents_family_id", "ai_agents", ["family_id"])
    op.create_index("ix_ai_agents_builtin", "ai_agents", ["is_builtin"], postgresql_where=sa.text("is_builtin = true"))
    op.create_index("ix_ai_agents_enabled", "ai_agents", ["is_enabled"], postgresql_where=sa.text("is_enabled = true"))

    # 3. Seed builtin agents (family_id=0)
    # Use fixed large IDs to avoid collision with snowflake generator
    op.execute("""
        INSERT INTO ai_agents (id, family_id, agent_name, display_name, description,
            icon, color, soul_md, skills, is_builtin, display_order)
        VALUES (
            100000000000001, 0, 'asset-health-advisor', '资产健康顾问',
            '全方位监控家庭资产健康状况，提供体检报告、预警提醒、配置分析和闲置处置建议',
            '🏥', '#10B981',
            '你是一位专业的家庭资产健康顾问。你的职责是帮助用户全面了解家庭资产的健康状况，发现潜在风险，并提供专业的改善建议。

## 核心能力
- **资产体检**：综合评估家庭资产的整体健康度，输出结构化体检报告
- **老化预警**：扫描资产老化、高维护成本、闲置情况，提前预警
- **配置分析**：分析资产配置比例，识别偏离最优配置的资产类别
- **处置建议**：识别闲置资产，提供处置或盘活建议

## 工作原则
1. 数据驱动：所有分析基于用户的实际资产数据，不做无依据的推测
2. 风险优先：优先关注高风险、高老化、高闲置的资产
3. 可操作性：每条建议都要有具体的执行路径
4. 保守表达：对不确定的结论使用"可能"、"建议进一步确认"等措辞

## 禁止事项
- 不提供具体投资建议（如"买入某股票"）
- 不做收益预测或承诺
- 不替用户做出财务决策',
            '["report", "alerts", "allocation", "disposal"]',
            true, 100
        )
    """)

    op.execute("""
        INSERT INTO ai_agents (id, family_id, agent_name, display_name, description,
            icon, color, soul_md, skills, is_builtin, display_order)
        VALUES (
            100000000000002, 0, 'finance-optimizer', '财务优化师',
            '分析家庭负债结构和消费漏洞，提供优化建议和还款策略',
            '💰', '#F59E0B',
            '你是一位专业的财务优化师。你的职责是帮助用户识别财务漏洞，优化负债结构，制定科学的还款策略。

## 核心能力
- **负债分析**：评估负债健康度，识别高利率负债、还款压力过大的负债
- **消费漏洞扫描**：识别重复支出、低价值订阅、可替代的高成本服务

## 工作原则
1. 省钱优先：优先识别可立即削减的无意义支出
2. 利率敏感：高利率负债优先偿还
3. 心理友好：建议循序渐进，不一次性要求用户大幅改变消费习惯
4. 长期视角：关注优化后的长期收益，而非短期节省金额

## 禁止事项
- 不提供具体投资建议
- 不推荐具体金融产品
- 不替用户做出财务决策',
            '["liability", "spending_leak"]',
            true, 200
        )
    """)


def downgrade() -> None:
    op.drop_table("ai_agents")
    op.rename_table("ai_skills", "skill_registry")
    op.rename_table("ai_mcp_servers", "family_mcp_servers")
    op.rename_table("ai_providers", "ai_provider_configs")
```

- [ ] **Step 2: Run the migration**

Run: `cd server/apps/backend && uv run alembic upgrade head`
Expected: Migration applies successfully, 3 tables renamed, `ai_agents` created with 2 seed rows.

- [ ] **Step 3: Verify migration applied**

Run: `cd server/apps/backend && uv run alembic current`
Expected: Shows revision `x2581y64zqr9 (head)`

- [ ] **Step 4: Verify downgrade works**

Run: `cd server/apps/backend && uv run alembic downgrade -1`
Expected: `ai_agents` dropped, tables renamed back.

Run: `cd server/apps/backend && uv run alembic upgrade head`
Expected: Re-applies cleanly.

- [ ] **Step 5: Commit**

```bash
git add server/apps/backend/alembic/versions/x2581y64zqr9_unify_ai_tables_and_add_agents.py
git commit -m "feat(db): unify AI table names and create ai_agents table

- Rename ai_provider_configs → ai_providers
- Rename family_mcp_servers → ai_mcp_servers
- Rename skill_registry → ai_skills
- Create ai_agents table with seed data for 2 builtin agents"
```

---

## Task 2: Update `__tablename__` in Existing Models

**Files:**
- Modify: `server/apps/backend/app/models/ai_provider_config.py` (line with `__tablename__`)
- Modify: `server/apps/backend/app/models/family_mcp_server.py` (line with `__tablename__`)
- Modify: `server/apps/backend/app/models/skill_registry.py` (line with `__tablename__`)

- [ ] **Step 1: Update `AIProviderConfig.__tablename__`**

In `server/apps/backend/app/models/ai_provider_config.py`, change:
```python
# old
__tablename__ = "ai_provider_configs"
# new
__tablename__ = "ai_providers"
```

Also in the same file, update `AIProviderTestResult` if it references `ai_provider_configs` in a ForeignKey:
```python
# old (if present)
sa.ForeignKey("ai_provider_configs.id")
# new
sa.ForeignKey("ai_providers.id")
```

- [ ] **Step 2: Update `FamilyMCPServer.__tablename__`**

In `server/apps/backend/app/models/family_mcp_server.py`, change:
```python
# old
__tablename__ = "family_mcp_servers"
# new
__tablename__ = "ai_mcp_servers"
```

- [ ] **Step 3: Update `SkillRegistry.__tablename__`**

In `server/apps/backend/app/models/skill_registry.py`, change:
```python
# old
__tablename__ = "skill_registry"
# new
__tablename__ = "ai_skills"
```

Also update the UniqueConstraint name if it references the old table name:
```python
# old (if present)
UniqueConstraint("family_id", "skill_id", name="uq_skill_registry_family_skill")
# new
UniqueConstraint("family_id", "skill_id", name="uq_ai_skills_family_skill")
```

- [ ] **Step 4: Run tests to verify table name changes are transparent**

Run: `cd server && uv run pytest tests/backend/ -x -q --timeout=30 2>&1 | tail -20`
Expected: All existing tests pass (SQLAlchemy creates tables from models in test DB, names are transparent to test logic).

- [ ] **Step 5: Commit**

```bash
git add server/apps/backend/app/models/ai_provider_config.py \
        server/apps/backend/app/models/family_mcp_server.py \
        server/apps/backend/app/models/skill_registry.py
git commit -m "refactor(models): update __tablename__ to unified ai_ prefix"
```

---

## Task 3: Create `AIAgent` SQLAlchemy Model

**Files:**
- Create: `server/apps/backend/app/models/ai_agent.py`
- Modify: `server/apps/backend/app/models/__init__.py`
- Modify: `server/apps/backend/alembic/env.py`

- [ ] **Step 1: Create the model file**

```python
# server/apps/backend/app/models/ai_agent.py
from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    Column,
    DateTime,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB

from apps.backend.app.database import Base
from packages.db.snowflake import next_id


class AIAgent(Base):
    __tablename__ = "ai_agents"
    __table_args__ = (
        UniqueConstraint("family_id", "agent_name", name="uq_ai_agents_family_name"),
        CheckConstraint("agent_name ~ '^[a-z][a-z0-9_-]*$'", name="ck_ai_agents_name_format"),
    )

    id = Column(BigInteger, primary_key=True, default=next_id)
    family_id = Column(BigInteger, nullable=False, index=True)
    agent_name = Column(String(64), nullable=False)
    display_name = Column(String(128), nullable=False)
    description = Column(Text, nullable=True)
    icon = Column(String(16), nullable=True)
    color = Column(String(16), nullable=True)

    soul_md = Column(Text, nullable=False)
    skills = Column(JSONB, nullable=True)
    model = Column(String(64), nullable=True)
    subagent_enabled = Column(Boolean, nullable=False, default=False)
    tool_groups = Column(JSONB, nullable=True)

    is_builtin = Column(Boolean, nullable=False, default=False)
    is_enabled = Column(Boolean, nullable=False, default=True)
    display_order = Column(Integer, nullable=False, default=0)
    created_by = Column(BigInteger, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
```

- [ ] **Step 2: Register model in `__init__.py`**

Add to `server/apps/backend/app/models/__init__.py` (after the `ai_allocation_drift_result` import, alphabetically):
```python
from apps.backend.app.models.ai_agent import AIAgent  # noqa: F401
```

- [ ] **Step 3: Register model in `alembic/env.py`**

Add to `server/apps/backend/alembic/env.py` (in the model imports section):
```python
from apps.backend.app.models.ai_agent import AIAgent  # noqa: F401
```

- [ ] **Step 4: Verify model loads correctly**

Run: `cd server/apps/backend && uv run python -c "from apps.backend.app.models.ai_agent import AIAgent; print(AIAgent.__tablename__)"`
Expected: `ai_agents`

- [ ] **Step 5: Commit**

```bash
git add server/apps/backend/app/models/ai_agent.py \
        server/apps/backend/app/models/__init__.py \
        server/apps/backend/alembic/env.py
git commit -m "feat(models): add AIAgent model for ai_agents table"
```

---

## Task 4: Create Agent Pydantic Schemas

**Files:**
- Create: `server/apps/backend/app/schemas/ai_agent.py`

- [ ] **Step 1: Write the schema file**

```python
# server/apps/backend/app/schemas/ai_agent.py
import re
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field, field_validator

from apps.backend.app.schemas.base import SnowflakeBase

_AGENT_NAME_RE = re.compile(r"^[a-z][a-z0-9_-]*$")


class AgentCreateRequest(BaseModel):
    agent_name: str = Field(..., min_length=1, max_length=64)
    display_name: str = Field(..., min_length=1, max_length=128)
    description: str | None = None
    icon: str | None = Field(None, max_length=16)
    color: str | None = Field(None, max_length=16)
    soul_md: str = Field(..., min_length=10)
    skills: list[str] | None = None
    model: str | None = None
    subagent_enabled: bool = False
    tool_groups: list[str] | None = None

    @field_validator("agent_name")
    @classmethod
    def validate_agent_name(cls, v: str) -> str:
        if not _AGENT_NAME_RE.match(v):
            raise ValueError("agent_name 必须以小写字母开头，仅包含小写字母、数字、下划线和连字符")
        return v


class AgentUpdateRequest(BaseModel):
    display_name: str | None = None
    description: str | None = None
    icon: str | None = None
    color: str | None = None
    soul_md: str | None = None
    skills: list[str] | None = None
    model: str | None = None
    subagent_enabled: bool | None = None
    tool_groups: list[str] | None = None
    display_order: int | None = None


class AgentResponse(SnowflakeBase):
    id: int
    family_id: int
    agent_name: str
    display_name: str
    description: str | None
    icon: str | None
    color: str | None
    soul_md: str
    skills: list[str] | None
    model: str | None
    subagent_enabled: bool
    tool_groups: list[str] | None
    is_builtin: bool
    is_enabled: bool
    display_order: int
    created_by: int | None
    created_at: datetime
    updated_at: datetime
    can_edit: bool
    can_delete: bool


class AgentListResponse(BaseModel):
    builtin: list[AgentResponse]
    custom: list[AgentResponse]
```

- [ ] **Step 2: Verify schema imports work**

Run: `cd server/apps/backend && uv run python -c "from apps.backend.app.schemas.ai_agent import AgentCreateRequest, AgentResponse, AgentListResponse; print('OK')"`
Expected: `OK`

- [ ] **Step 3: Commit**

```bash
git add server/apps/backend/app/schemas/ai_agent.py
git commit -m "feat(schemas): add Agent Pydantic schemas"
```

---

## Task 5: Create Agent CRUD Router

**Files:**
- Create: `server/apps/backend/app/routers/ai_agents.py`
- Modify: `server/apps/backend/app/main.py`

- [ ] **Step 1: Write the router**

```python
# server/apps/backend/app/routers/ai_agents.py
from fastapi import APIRouter, Depends
from sqlalchemy import or_
from sqlalchemy.orm import Session

from apps.backend.app.auth.deps import require_adult, require_owner
from apps.backend.app.database import get_db
from apps.backend.app.errors import AppError, ErrorCode
from apps.backend.app.models.ai_agent import AIAgent
from apps.backend.app.models.user import User
from apps.backend.app.schemas.ai_agent import (
    AgentCreateRequest,
    AgentListResponse,
    AgentResponse,
    AgentUpdateRequest,
)

router = APIRouter(prefix="/ai/agents", tags=["ai-agents"])


def _to_response(agent: AIAgent, user: User) -> AgentResponse:
    is_owner = user.role == "owner"
    return AgentResponse.model_validate(
        agent,
        from_attributes=True,
        update={
            "can_edit": is_owner if agent.is_builtin else (is_owner and agent.family_id == user.family_id),
            "can_delete": False if agent.is_builtin else (is_owner and agent.family_id == user.family_id),
        },
    )


@router.get("", response_model=AgentListResponse)
def list_agents(
    current_user: User = Depends(require_adult),
    db: Session = Depends(get_db),
) -> AgentListResponse:
    agents = (
        db.query(AIAgent)
        .filter(
            or_(
                AIAgent.family_id == 0,
                AIAgent.family_id == current_user.family_id,
            )
        )
        .order_by(AIAgent.display_order, AIAgent.created_at)
        .all()
    )
    builtin = [_to_response(a, current_user) for a in agents if a.is_builtin]
    custom = [_to_response(a, current_user) for a in agents if not a.is_builtin]
    return AgentListResponse(builtin=builtin, custom=custom)


@router.get("/{agent_id}", response_model=AgentResponse)
def get_agent(
    agent_id: int,
    current_user: User = Depends(require_adult),
    db: Session = Depends(get_db),
) -> AgentResponse:
    agent = db.query(AIAgent).filter(AIAgent.id == agent_id).first()
    if not agent:
        raise AppError(ErrorCode.NOT_FOUND)
    if agent.family_id != 0 and agent.family_id != current_user.family_id:
        raise AppError(ErrorCode.NOT_FOUND)
    return _to_response(agent, current_user)


@router.post("", response_model=AgentResponse, status_code=201)
def create_agent(
    payload: AgentCreateRequest,
    current_user: User = Depends(require_owner),
    db: Session = Depends(get_db),
) -> AgentResponse:
    existing = (
        db.query(AIAgent)
        .filter(
            AIAgent.family_id == current_user.family_id,
            AIAgent.agent_name == payload.agent_name,
        )
        .first()
    )
    if existing:
        raise AppError(ErrorCode.VALIDATION_ERROR, "agent_name 已存在")

    builtin_conflict = (
        db.query(AIAgent)
        .filter(AIAgent.family_id == 0, AIAgent.agent_name == payload.agent_name)
        .first()
    )
    if builtin_conflict:
        raise AppError(ErrorCode.VALIDATION_ERROR, "不能使用内置智能体的名称")

    agent = AIAgent(
        family_id=current_user.family_id,
        created_by=current_user.id,
        **payload.model_dump(),
    )
    db.add(agent)
    db.commit()
    db.refresh(agent)
    return _to_response(agent, current_user)


@router.put("/{agent_id}", response_model=AgentResponse)
def update_agent(
    agent_id: int,
    payload: AgentUpdateRequest,
    current_user: User = Depends(require_owner),
    db: Session = Depends(get_db),
) -> AgentResponse:
    agent = db.query(AIAgent).filter(AIAgent.id == agent_id).first()
    if not agent:
        raise AppError(ErrorCode.NOT_FOUND)
    if agent.family_id != 0 and agent.family_id != current_user.family_id:
        raise AppError(ErrorCode.NOT_FOUND)

    updates = payload.model_dump(exclude_unset=True)

    if agent.is_builtin:
        allowed = {"icon", "color", "display_order"}
        disallowed = set(updates.keys()) - allowed
        if disallowed:
            raise AppError(ErrorCode.VALIDATION_ERROR, f"内置智能体只允许修改: {', '.join(allowed)}")

    for key, value in updates.items():
        setattr(agent, key, value)

    db.commit()
    db.refresh(agent)
    return _to_response(agent, current_user)


@router.delete("/{agent_id}", status_code=204)
def delete_agent(
    agent_id: int,
    current_user: User = Depends(require_owner),
    db: Session = Depends(get_db),
) -> None:
    agent = db.query(AIAgent).filter(AIAgent.id == agent_id).first()
    if not agent:
        raise AppError(ErrorCode.NOT_FOUND)
    if agent.is_builtin:
        raise AppError(ErrorCode.FAMILY_FORBIDDEN, "内置智能体不可删除")
    if agent.family_id != current_user.family_id:
        raise AppError(ErrorCode.NOT_FOUND)
    db.delete(agent)
    db.commit()


@router.put("/{agent_id}/toggle", response_model=AgentResponse)
def toggle_agent(
    agent_id: int,
    enabled: bool,
    current_user: User = Depends(require_owner),
    db: Session = Depends(get_db),
) -> AgentResponse:
    agent = db.query(AIAgent).filter(AIAgent.id == agent_id).first()
    if not agent:
        raise AppError(ErrorCode.NOT_FOUND)
    if agent.family_id != 0 and agent.family_id != current_user.family_id:
        raise AppError(ErrorCode.NOT_FOUND)
    agent.is_enabled = enabled
    db.commit()
    db.refresh(agent)
    return _to_response(agent, current_user)
```

- [ ] **Step 2: Register the router in `main.py`**

In `server/apps/backend/app/main.py`, add the import and registration near the other AI routers:

```python
# import (add near the other ai_* imports)
from apps.backend.app.routers import ai_agents as ai_agents_router

# registration (add near other AI router registrations)
app.include_router(ai_agents_router.router, prefix="/api/v1")
```

- [ ] **Step 3: Verify router loads**

Run: `cd server/apps/backend && uv run python -c "from apps.backend.app.routers.ai_agents import router; print([r.path for r in router.routes])"`
Expected: Lists the routes: `['', '/{agent_id}', '', '/{agent_id}', '/{agent_id}', '/{agent_id}/toggle']`

- [ ] **Step 4: Commit**

```bash
git add server/apps/backend/app/routers/ai_agents.py \
        server/apps/backend/app/main.py
git commit -m "feat(api): add ai_agents CRUD router"
```

---

## Task 6: Create Internal Agent API

**Files:**
- Create: `server/apps/backend/app/routers/ai_agents_internal.py`
- Modify: `server/apps/backend/app/main.py`

The agent service needs to fetch agent config via an internal API (same pattern as existing `/internal/ai/config`).

- [ ] **Step 1: Write the internal router**

```python
# server/apps/backend/app/routers/ai_agents_internal.py
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from apps.backend.app.auth.ai_deps import verify_agent_token
from apps.backend.app.database import get_db
from apps.backend.app.errors import AppError, ErrorCode
from apps.backend.app.models.ai_agent import AIAgent

router = APIRouter(prefix="/internal/ai/agents", tags=["internal"])


@router.get("/{agent_id}")
def get_agent_config(
    agent_id: int,
    family_id: str = Depends(verify_agent_token),
    db: Session = Depends(get_db),
) -> dict:
    agent = db.query(AIAgent).filter(AIAgent.id == agent_id).first()
    if not agent:
        raise AppError(ErrorCode.NOT_FOUND)
    if agent.family_id != 0 and str(agent.family_id) != family_id:
        raise AppError(ErrorCode.NOT_FOUND)
    return {
        "id": str(agent.id),
        "family_id": str(agent.family_id),
        "agent_name": agent.agent_name,
        "display_name": agent.display_name,
        "description": agent.description,
        "soul_md": agent.soul_md,
        "skills": agent.skills,
        "model": agent.model,
        "subagent_enabled": agent.subagent_enabled,
        "tool_groups": agent.tool_groups,
        "is_builtin": agent.is_builtin,
        "is_enabled": agent.is_enabled,
    }
```

- [ ] **Step 2: Register the internal router in `main.py`**

In `server/apps/backend/app/main.py`:

```python
# import
from apps.backend.app.routers import ai_agents_internal as ai_agents_internal_router

# registration
app.include_router(ai_agents_internal_router.router, prefix="/api/v1")
```

- [ ] **Step 3: Commit**

```bash
git add server/apps/backend/app/routers/ai_agents_internal.py \
        server/apps/backend/app/main.py
git commit -m "feat(api): add internal agent config endpoint for agent service"
```

---

## Task 7: Write Agent CRUD Tests

**Files:**
- Create: `server/tests/backend/test_ai_agents.py`

- [ ] **Step 1: Write the test file**

```python
# server/tests/backend/test_ai_agents.py
"""Tests for Agent CRUD API and tenant isolation."""
import pytest


@pytest.fixture
def seed_builtin_agents(db):
    """Seed builtin agents into the test DB."""
    from apps.backend.app.models.ai_agent import AIAgent

    db.add(AIAgent(
        id=100000000000001, family_id=0, agent_name="asset-health-advisor",
        display_name="资产健康顾问", description="test builtin",
        icon="🏥", color="#10B981", soul_md="你是资产健康顾问。" * 2,
        skills=["report", "alerts"], is_builtin=True, display_order=100,
    ))
    db.add(AIAgent(
        id=100000000000002, family_id=0, agent_name="finance-optimizer",
        display_name="财务优化师", description="test builtin",
        icon="💰", color="#F59E0B", soul_md="你是财务优化师。" * 2,
        skills=["liability", "spending_leak"], is_builtin=True, display_order=200,
    ))
    db.commit()


def test_list_agents_returns_builtin(client, auth_headers, seed_builtin_agents):
    resp = client.get("/api/v1/ai/agents", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert len(data["builtin"]) == 2
    assert data["builtin"][0]["agent_name"] == "asset-health-advisor"
    assert data["builtin"][1]["agent_name"] == "finance-optimizer"
    assert data["custom"] == []
    # IDs should be strings (SnowflakeBase serialization)
    assert isinstance(data["builtin"][0]["id"], str)


def test_create_agent_success(client, auth_headers, seed_builtin_agents):
    payload = {
        "agent_name": "my-test-agent",
        "display_name": "我的测试智能体",
        "description": "A test agent",
        "icon": "🎯",
        "color": "#3B82F6",
        "soul_md": "你是一个测试智能体，帮助用户做各种测试。",
    }
    resp = client.post("/api/v1/ai/agents", json=payload, headers=auth_headers)
    assert resp.status_code == 201
    data = resp.json()["data"]
    assert data["agent_name"] == "my-test-agent"
    assert data["display_name"] == "我的测试智能体"
    assert data["is_builtin"] is False
    assert data["can_edit"] is True
    assert data["can_delete"] is True


def test_create_agent_duplicate_name_fails(client, auth_headers, seed_builtin_agents):
    payload = {
        "agent_name": "dup-agent",
        "display_name": "Dup1",
        "soul_md": "你是一个重复名称测试智能体。",
    }
    resp = client.post("/api/v1/ai/agents", json=payload, headers=auth_headers)
    assert resp.status_code == 201

    resp2 = client.post("/api/v1/ai/agents", json=payload, headers=auth_headers)
    assert resp2.status_code == 400


def test_create_agent_builtin_name_conflict(client, auth_headers, seed_builtin_agents):
    payload = {
        "agent_name": "asset-health-advisor",
        "display_name": "冒充内置",
        "soul_md": "你是一个冒充内置智能体的自定义智能体。",
    }
    resp = client.post("/api/v1/ai/agents", json=payload, headers=auth_headers)
    assert resp.status_code == 400


def test_create_agent_invalid_name_format(client, auth_headers, seed_builtin_agents):
    payload = {
        "agent_name": "Invalid-Name",
        "display_name": "Invalid",
        "soul_md": "你是一个名称格式错误的智能体。",
    }
    resp = client.post("/api/v1/ai/agents", json=payload, headers=auth_headers)
    assert resp.status_code == 422


def test_update_custom_agent(client, auth_headers, seed_builtin_agents):
    create_resp = client.post("/api/v1/ai/agents", json={
        "agent_name": "updatable",
        "display_name": "Before",
        "soul_md": "你是一个可更新的测试智能体。",
    }, headers=auth_headers)
    agent_id = create_resp.json()["data"]["id"]

    update_resp = client.put(f"/api/v1/ai/agents/{agent_id}", json={
        "display_name": "After",
        "soul_md": "你是一个已更新的测试智能体。更新后的版本。",
    }, headers=auth_headers)
    assert update_resp.status_code == 200
    assert update_resp.json()["data"]["display_name"] == "After"


def test_update_builtin_agent_limited_fields(client, auth_headers, seed_builtin_agents):
    builtin_id = "100000000000001"
    resp = client.put(f"/api/v1/ai/agents/{builtin_id}", json={
        "icon": "🩺",
        "color": "#059669",
    }, headers=auth_headers)
    assert resp.status_code == 200
    assert resp.json()["data"]["icon"] == "🩺"


def test_update_builtin_agent_disallowed_field(client, auth_headers, seed_builtin_agents):
    builtin_id = "100000000000001"
    resp = client.put(f"/api/v1/ai/agents/{builtin_id}", json={
        "soul_md": "Hacked soul",
    }, headers=auth_headers)
    assert resp.status_code == 400


def test_delete_custom_agent(client, auth_headers, seed_builtin_agents):
    create_resp = client.post("/api/v1/ai/agents", json={
        "agent_name": "deletable",
        "display_name": "Deletable",
        "soul_md": "你是一个可删除的测试智能体。",
    }, headers=auth_headers)
    agent_id = create_resp.json()["data"]["id"]

    del_resp = client.delete(f"/api/v1/ai/agents/{agent_id}", headers=auth_headers)
    assert del_resp.status_code == 204

    get_resp = client.get(f"/api/v1/ai/agents/{agent_id}", headers=auth_headers)
    assert get_resp.status_code == 404


def test_delete_builtin_agent_forbidden(client, auth_headers, seed_builtin_agents):
    builtin_id = "100000000000001"
    resp = client.delete(f"/api/v1/ai/agents/{builtin_id}", headers=auth_headers)
    assert resp.status_code == 403


def test_toggle_agent(client, auth_headers, seed_builtin_agents):
    builtin_id = "100000000000001"
    resp = client.put(f"/api/v1/ai/agents/{builtin_id}/toggle?enabled=false", headers=auth_headers)
    assert resp.status_code == 200
    assert resp.json()["data"]["is_enabled"] is False

    resp2 = client.put(f"/api/v1/ai/agents/{builtin_id}/toggle?enabled=true", headers=auth_headers)
    assert resp2.status_code == 200
    assert resp2.json()["data"]["is_enabled"] is True
```

- [ ] **Step 2: Run the tests**

Run: `cd server && uv run pytest tests/backend/test_ai_agents.py -v --timeout=30 2>&1 | tail -30`
Expected: All tests pass.

- [ ] **Step 3: Commit**

```bash
git add server/tests/backend/test_ai_agents.py
git commit -m "test: add Agent CRUD and tenant isolation tests"
```

---

## Task 8: Add `get_agent_config` to Agent BackendClient

**Files:**
- Modify: `server/apps/agent/core/backend_client.py`

- [ ] **Step 1: Add the method**

In `server/apps/agent/core/backend_client.py`, add the following method to the `BackendClient` class, near the existing `get_family_ai_config` method:

```python
async def get_agent_config(self, agent_id: int) -> dict:
    """Fetch agent configuration from backend internal API."""
    url = f"{self._base_url}/api/v1/internal/ai/agents/{agent_id}"
    resp = await self._pool.get(url, headers=self._headers())
    resp.raise_for_status()
    return resp.json().get("data", resp.json())
```

- [ ] **Step 2: Verify the method is accessible**

Run: `cd server/apps/agent && uv run python -c "from core.backend_client import BackendClient; print('OK')"`
Expected: `OK` (no import errors).

- [ ] **Step 3: Commit**

```bash
git add server/apps/agent/core/backend_client.py
git commit -m "feat(agent): add get_agent_config to BackendClient"
```

---

## Task 9: Create `AgentTempCache`

**Files:**
- Create: `server/apps/agent/services/agent_temp_cache.py`

- [ ] **Step 1: Write the cache module**

```python
# server/apps/agent/services/agent_temp_cache.py
import shutil
import tempfile
import threading
import time
from collections import OrderedDict
from pathlib import Path

import yaml


class AgentTempCache:
    MAX_SIZE = 100
    EXPIRE_SECONDS = 1800

    def __init__(self) -> None:
        self._cache: OrderedDict[tuple[int, int], tuple[Path, float, float]] = OrderedDict()
        self._lock = threading.Lock()

    def get_or_create(
        self,
        agent_id: int,
        family_id: int,
        soul_md: str,
        config_data: dict,
    ) -> Path:
        key = (agent_id, family_id)
        with self._lock:
            if key in self._cache:
                dir_path, created, _ = self._cache[key]
                self._cache[key] = (dir_path, created, time.time())
                self._cache.move_to_end(key)
                return dir_path

            temp_dir = Path(tempfile.mkdtemp(prefix=f"agent_{agent_id}_f{family_id}_"))
            (temp_dir / "SOUL.md").write_text(soul_md, encoding="utf-8")
            (temp_dir / "config.yaml").write_text(yaml.dump(config_data, allow_unicode=True), encoding="utf-8")

            if len(self._cache) >= self.MAX_SIZE:
                oldest_key = next(iter(self._cache))
                oldest_dir = self._cache[oldest_key][0]
                shutil.rmtree(oldest_dir, ignore_errors=True)
                self._cache.pop(oldest_key)

            self._cache[key] = (temp_dir, time.time(), time.time())
            return temp_dir

    def invalidate(self, agent_id: int, family_id: int) -> None:
        key = (agent_id, family_id)
        with self._lock:
            if key in self._cache:
                dir_path = self._cache[key][0]
                shutil.rmtree(dir_path, ignore_errors=True)
                self._cache.pop(key)

    def cleanup_expired(self) -> None:
        now = time.time()
        with self._lock:
            to_remove = [
                key for key, (_, _, last_used) in self._cache.items()
                if now - last_used > self.EXPIRE_SECONDS
            ]
            for key in to_remove:
                dir_path = self._cache[key][0]
                shutil.rmtree(dir_path, ignore_errors=True)
                self._cache.pop(key)


agent_temp_cache = AgentTempCache()
```

- [ ] **Step 2: Write a unit test**

Create `server/tests/agent/unit/test_agent_temp_cache.py`:

```python
# server/tests/agent/unit/test_agent_temp_cache.py
from server.apps.agent.services.agent_temp_cache import AgentTempCache


def test_get_or_create_returns_path():
    cache = AgentTempCache()
    path = cache.get_or_create(
        agent_id=1, family_id=100,
        soul_md="test soul", config_data={"name": "test"},
    )
    assert path.exists()
    assert (path / "SOUL.md").read_text() == "test soul"
    # Cleanup
    cache.invalidate(1, 100)
    assert not path.exists()


def test_get_or_create_returns_cached():
    cache = AgentTempCache()
    path1 = cache.get_or_create(1, 100, "soul", {"name": "test"})
    path2 = cache.get_or_create(1, 100, "soul", {"name": "test"})
    assert path1 == path2
    cache.invalidate(1, 100)


def test_lru_eviction():
    cache = AgentTempCache()
    cache.MAX_SIZE = 2
    p1 = cache.get_or_create(1, 100, "soul1", {"name": "t1"})
    cache.get_or_create(2, 100, "soul2", {"name": "t2"})
    cache.get_or_create(3, 100, "soul3", {"name": "t3"})
    # p1 should be evicted
    assert not p1.exists()
    cache.invalidate(2, 100)
    cache.invalidate(3, 100)
    cache.MAX_SIZE = 100
```

- [ ] **Step 3: Run the test**

Run: `cd server && uv run pytest tests/agent/unit/test_agent_temp_cache.py -v --timeout=10`
Expected: All 3 tests pass.

- [ ] **Step 4: Commit**

```bash
git add server/apps/agent/services/agent_temp_cache.py \
        server/tests/agent/unit/test_agent_temp_cache.py
git commit -m "feat(agent): add AgentTempCache for agent temp directory management"
```

---

## Task 10: Create `stream_agent_dispatch` Entry Point

**Files:**
- Create: `server/apps/agent/services/agent_dispatch.py`

- [ ] **Step 1: Write the dispatch module**

```python
# server/apps/agent/services/agent_dispatch.py
import uuid
from typing import AsyncGenerator

from apps.agent.core.backend_client import BackendClient
from apps.agent.services.agent_temp_cache import agent_temp_cache
from apps.agent.services.deerflow_adapter.adapter import create_family_adapter
from apps.agent.services.deerflow_adapter.skill_loader import skill_loader
from apps.agent.services.stream_events import EventStreamBuilder


async def stream_agent_dispatch(
    agent_id: int,
    family_id: str,
    thread_id: str | None,
    message: str,
    enable_thinking: bool = False,
) -> AsyncGenerator[str, None]:
    """Agent-first execution entry point. Streams NDJSON events."""
    task_id = str(uuid.uuid4())
    builder = EventStreamBuilder(capability_id=f"agent-{agent_id}", task_id=task_id)

    # 1. Fetch agent config from backend
    client = BackendClient(family_id)
    try:
        agent_config = await client.get_agent_config(agent_id)
    except Exception as e:
        yield builder.error(f"获取智能体配置失败: {e}", "AGENT_CONFIG_ERROR").to_ndjson()
        return

    if not agent_config.get("is_enabled", True):
        yield builder.error("智能体已禁用", "AGENT_DISABLED").to_ndjson()
        return

    # 2. Fetch AI provider config for this family
    try:
        ai_config = await client.get_family_ai_config()
    except Exception as e:
        yield builder.error(f"获取 AI 配置失败: {e}", "AI_CONFIG_ERROR").to_ndjson()
        return

    # 3. Build temp directory via cache
    config_data = {
        "name": agent_config["agent_name"],
        "model": agent_config.get("model") or "inherit",
        "skills": agent_config.get("skills") or [],
        "tool_groups": agent_config.get("tool_groups") or [],
        "subagent_enabled": agent_config.get("subagent_enabled", False),
    }
    temp_dir = agent_temp_cache.get_or_create(
        agent_id=agent_id,
        family_id=int(family_id),
        soul_md=agent_config["soul_md"],
        config_data=config_data,
    )

    # 4. Create DeerFlow adapter (reuses existing family adapter cache)
    adapter = create_family_adapter(
        family_id=family_id,
        ai_config=ai_config,
        subagent_enabled=agent_config.get("subagent_enabled", False),
        mcp_servers=None,
    )

    # 5. Determine thread_id
    if not thread_id:
        thread_id = str(uuid.uuid4())

    # 6. Build context from available skills
    skills = agent_config.get("skills") or []
    skill_name = skills[0] if len(skills) == 1 else "agent"

    # 7. Emit session start
    yield builder.phase("connecting", {"agent_name": agent_config["agent_name"]}).to_ndjson()

    # 8. Stream via adapter
    answer_parts: list[str] = []
    thinking_started = False
    answering_started = False

    try:
        async for chunk in adapter.stream_dispatch(
            skill_name=skill_name,
            context=_build_agent_context(message, agent_config),
            thread_id=thread_id,
            enable_thinking=enable_thinking,
        ):
            if chunk.type == "thinking":
                if not thinking_started:
                    yield builder.phase("thinking").to_ndjson()
                    thinking_started = True
                yield builder.token(chunk.content, is_thinking=True).to_ndjson()
            elif chunk.type == "text":
                if not answering_started:
                    yield builder.phase("answering").to_ndjson()
                    answering_started = True
                answer_parts.append(chunk.content)
                yield builder.token(chunk.content, is_thinking=False).to_ndjson()
    except Exception as e:
        yield builder.error(str(e), "STREAM_ERROR").to_ndjson()
        return

    # 9. Emit end
    yield builder.end(
        summary="".join(answer_parts)[:200],
        tokens_used=None,
        execution_time_ms=None,
        tools_used=None,
    ).to_ndjson()


def _build_agent_context(message: str, agent_config: dict) -> dict:
    """Build a minimal context dict for the adapter."""
    return {
        "free_text": message,
        "agent_name": agent_config["agent_name"],
        "agent_display_name": agent_config.get("display_name", ""),
        "soul_md": agent_config["soul_md"],
        "skills": agent_config.get("skills") or [],
    }
```

- [ ] **Step 2: Verify imports**

Run: `cd server/apps/agent && uv run python -c "from services.agent_dispatch import stream_agent_dispatch; print('OK')"`
Expected: `OK`

- [ ] **Step 3: Commit**

```bash
git add server/apps/agent/services/agent_dispatch.py
git commit -m "feat(agent): add stream_agent_dispatch entry point for Agent-first execution"
```

---

## Task 11: Add Agent Stream Router to Agent Service

**Files:**
- Create: `server/apps/agent/app/routers/agent_stream.py`
- Modify: `server/apps/agent/app/main.py`

- [ ] **Step 1: Write the agent stream router**

```python
# server/apps/agent/app/routers/agent_stream.py
from fastapi import APIRouter, Header, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from apps.agent.app.config import settings
from apps.agent.services.agent_dispatch import stream_agent_dispatch

router = APIRouter(prefix="/agent", tags=["agent-stream"])


class AgentStreamRequest(BaseModel):
    message: str
    thread_id: str | None = None
    enable_thinking: bool = False


@router.post("/{agent_id}/stream")
async def stream_agent(
    agent_id: int,
    body: AgentStreamRequest,
    x_family_id: str = Header(..., alias="X-Family-Id"),
    authorization: str = Header(..., alias="Authorization"),
) -> StreamingResponse:
    if not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Invalid token")
    token = authorization[7:]
    import hmac
    if not hmac.compare_digest(token, settings.AGENT_INTERNAL_TOKEN):
        raise HTTPException(status_code=401, detail="Invalid agent token")

    return StreamingResponse(
        stream_agent_dispatch(
            agent_id=agent_id,
            family_id=x_family_id,
            thread_id=body.thread_id,
            message=body.message,
            enable_thinking=body.enable_thinking,
        ),
        media_type="application/x-ndjson",
    )
```

- [ ] **Step 2: Register the router in agent `main.py`**

In `server/apps/agent/app/main.py`, add:

```python
# import
from apps.agent.app.routers import agent_stream

# registration (near the other router registrations)
app.include_router(agent_stream.router)
```

- [ ] **Step 3: Commit**

```bash
git add server/apps/agent/app/routers/agent_stream.py \
        server/apps/agent/app/main.py
git commit -m "feat(agent): add /agent/{id}/stream endpoint for Agent-first execution"
```

---

## Task 12: Frontend — TypeScript Types for Agent

**Files:**
- Create: `frontend/apps/main/src/types/agent.ts`

- [ ] **Step 1: Write the types file**

```typescript
// frontend/apps/main/src/types/agent.ts

export interface Agent {
  id: string
  family_id: string
  agent_name: string
  display_name: string
  description: string | null
  icon: string | null
  color: string | null
  soul_md: string
  skills: string[] | null
  model: string | null
  subagent_enabled: boolean
  tool_groups: string[] | null
  is_builtin: boolean
  is_enabled: boolean
  display_order: number
  created_by: string | null
  created_at: string
  updated_at: string
  can_edit: boolean
  can_delete: boolean
}

export interface AgentListResponse {
  builtin: Agent[]
  custom: Agent[]
}

export interface AgentCreatePayload {
  agent_name: string
  display_name: string
  description?: string
  icon?: string
  color?: string
  soul_md: string
  skills?: string[]
  model?: string
  subagent_enabled?: boolean
  tool_groups?: string[]
}

export interface AgentUpdatePayload {
  display_name?: string
  description?: string
  icon?: string
  color?: string
  soul_md?: string
  skills?: string[]
  model?: string
  subagent_enabled?: boolean
  tool_groups?: string[]
  display_order?: number
}
```

- [ ] **Step 2: Commit**

```bash
git add frontend/apps/main/src/types/agent.ts
git commit -m "feat(types): add Agent TypeScript types"
```

---

## Task 13: Frontend — Agent API Module

**Files:**
- Create: `frontend/apps/main/src/api/agent.ts`

- [ ] **Step 1: Write the API module**

```typescript
// frontend/apps/main/src/api/agent.ts
import api from '@/api'
import type { Agent, AgentCreatePayload, AgentListResponse, AgentUpdatePayload } from '@/types/agent'

export function getAgents(): Promise<AgentListResponse> {
  return api.get('/ai/agents').then(r => r.data)
}

export function getAgent(id: string): Promise<Agent> {
  return api.get(`/ai/agents/${id}`).then(r => r.data)
}

export function createAgent(payload: AgentCreatePayload): Promise<Agent> {
  return api.post('/ai/agents', payload).then(r => r.data)
}

export function updateAgent(id: string, payload: AgentUpdatePayload): Promise<Agent> {
  return api.put(`/ai/agents/${id}`, payload).then(r => r.data)
}

export function deleteAgent(id: string): Promise<void> {
  return api.delete(`/ai/agents/${id}`)
}

export function toggleAgent(id: string, enabled: boolean): Promise<Agent> {
  return api.put(`/ai/agents/${id}/toggle?enabled=${enabled}`).then(r => r.data)
}
```

- [ ] **Step 2: Commit**

```bash
git add frontend/apps/main/src/api/agent.ts
git commit -m "feat(api): add Agent API module"
```

---

## Task 14: Frontend — Agent Pinia Store

**Files:**
- Create: `frontend/apps/main/src/stores/agent.ts`

- [ ] **Step 1: Write the store**

```typescript
// frontend/apps/main/src/stores/agent.ts
import { ref, computed } from 'vue'
import { defineStore } from 'pinia'
import { getAgents, createAgent, updateAgent, deleteAgent, toggleAgent } from '@/api/agent'
import type { Agent, AgentCreatePayload, AgentUpdatePayload } from '@/types/agent'

export const useAgentStore = defineStore('agent', () => {
  const builtinAgents = ref<Agent[]>([])
  const customAgents = ref<Agent[]>([])
  const loading = ref(false)

  const allAgents = computed(() => [...builtinAgents.value, ...customAgents.value])
  const enabledAgents = computed(() => allAgents.value.filter(a => a.is_enabled))

  async function loadAgents() {
    loading.value = true
    try {
      const data = await getAgents()
      builtinAgents.value = data.builtin
      customAgents.value = data.custom
    } finally {
      loading.value = false
    }
  }

  async function addAgent(payload: AgentCreatePayload): Promise<Agent> {
    const agent = await createAgent(payload)
    customAgents.value.push(agent)
    return agent
  }

  async function editAgent(id: string, payload: AgentUpdatePayload): Promise<Agent> {
    const agent = await updateAgent(id, payload)
    const idx = customAgents.value.findIndex(a => a.id === id)
    if (idx >= 0) customAgents.value[idx] = agent
    const bIdx = builtinAgents.value.findIndex(a => a.id === id)
    if (bIdx >= 0) builtinAgents.value[bIdx] = agent
    return agent
  }

  async function removeAgent(id: string): Promise<void> {
    await deleteAgent(id)
    customAgents.value = customAgents.value.filter(a => a.id !== id)
  }

  async function toggleAgentEnabled(id: string, enabled: boolean): Promise<void> {
    const agent = await toggleAgent(id, enabled)
    const idx = customAgents.value.findIndex(a => a.id === id)
    if (idx >= 0) customAgents.value[idx] = agent
    const bIdx = builtinAgents.value.findIndex(a => a.id === id)
    if (bIdx >= 0) builtinAgents.value[bIdx] = agent
  }

  return {
    builtinAgents,
    customAgents,
    allAgents,
    enabledAgents,
    loading,
    loadAgents,
    addAgent,
    editAgent,
    removeAgent,
    toggleAgentEnabled,
  }
})
```

- [ ] **Step 2: Commit**

```bash
git add frontend/apps/main/src/stores/agent.ts
git commit -m "feat(stores): add Agent Pinia store"
```

---

## Task 15: Frontend — i18n Keys for Agents

**Files:**
- Modify: `frontend/apps/main/src/i18n/locales/zh-CN.ts`

- [ ] **Step 1: Add agent i18n keys**

Find the `skills:` section in `zh-CN.ts` and add an `agents:` section after it:

```typescript
  agents: {
    title: '智能体管理',
    builtinAgents: '内置智能体',
    customAgents: '我的智能体',
    createAgent: '创建智能体',
    editAgent: '编辑智能体',
    noCustomAgents: '还没有自定义智能体',
    noCustomAgentsSub: '点击下方按钮创建你的第一个智能体',
    consult: '立即咨询',
    chat: '对话',
    edit: '编辑',
    form: {
      agentName: '标识名',
      agentNameHint: '小写字母开头，仅含小写字母、数字、下划线和连字符',
      displayName: '显示名称',
      description: '描述',
      icon: '图标',
      color: '主题色',
      soulMd: '人格定义 (SOUL.md)',
      soulMdHint: '定义智能体的性格、价值观、工作原则',
      skills: '可用技能',
      model: '模型选择',
      modelInherit: '继承家庭默认',
      subagentEnabled: '子智能体',
      subagentHint: '允许智能体创建子任务并行处理',
      createBtn: '创建',
      updateBtn: '保存',
      deleteConfirm: '确定删除此智能体？删除后不可恢复。',
      createSuccess: '🎉 智能体创建成功',
      updateSuccess: '✅ 智能体更新成功',
      deleteSuccess: '🗑️ 智能体已删除',
    },
    templateFinanceAdvisor: '财务顾问模板',
    templateBudgetTracker: '预算追踪模板',
    templateBlank: '空白模板',
  },
```

Also add to `settings:` section:
```typescript
    agentsManage: '智能体管理',
```

Also add to `toast:` section:
```typescript
    agentToggleEnabled: '✅ 智能体已启用',
    agentToggleDisabled: '⏸️ 智能体已禁用',
```

- [ ] **Step 2: Verify no TypeScript errors**

Run: `cd frontend/apps/main && npx vue-tsc --noEmit 2>&1 | tail -5`
Expected: No errors related to i18n keys.

- [ ] **Step 3: Commit**

```bash
git add frontend/apps/main/src/i18n/locales/zh-CN.ts
git commit -m "feat(i18n): add agent management i18n keys"
```

---

## Task 16: Frontend — AgentCard Component

**Files:**
- Create: `frontend/apps/main/src/components/agent/AgentCard.vue`

- [ ] **Step 1: Write the component**

```vue
<!-- frontend/apps/main/src/components/agent/AgentCard.vue -->
<script setup lang="ts">
import type { Agent } from '@/types/agent'
import { useI18n } from 'vue-i18n'

const { t } = useI18n()

defineProps<{
  agent: Agent
  showActions?: boolean
}>()

const emit = defineEmits<{
  consult: [agent: Agent]
  edit: [agent: Agent]
}>()
</script>

<template>
  <div
    class="agent-card"
    :style="{ '--agent-color': agent.color || '#6366F1' }"
    @click="emit('consult', agent)"
  >
    <div class="agent-card__icon">{{ agent.icon || '🤖' }}</div>
    <div class="agent-card__body">
      <div class="agent-card__name">{{ agent.display_name }}</div>
      <div class="agent-card__desc">{{ agent.description || '' }}</div>
    </div>
    <div v-if="showActions" class="agent-card__actions" @click.stop>
      <van-button
        size="small"
        type="primary"
        plain
        @click="emit('consult', agent)"
      >
        {{ agent.is_builtin ? t('agents.consult') : t('agents.chat') }}
      </van-button>
      <van-button
        v-if="agent.can_edit"
        size="small"
        plain
        @click="emit('edit', agent)"
      >
        {{ t('agents.edit') }}
      </van-button>
    </div>
  </div>
</template>

<style scoped>
.agent-card {
  display: flex;
  flex-direction: column;
  gap: 8px;
  padding: 16px;
  border-radius: 12px;
  background: var(--van-background-2);
  border: 1px solid var(--van-border-color);
  cursor: pointer;
  transition: transform 0.15s, box-shadow 0.15s;
}

.agent-card:active {
  transform: scale(0.97);
}

.agent-card__icon {
  font-size: 32px;
  line-height: 1;
}

.agent-card__name {
  font-size: 15px;
  font-weight: 600;
  color: var(--van-text-color);
}

.agent-card__desc {
  font-size: 12px;
  color: var(--van-text-color-2);
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}

.agent-card__actions {
  display: flex;
  gap: 8px;
  margin-top: 4px;
}
</style>
```

- [ ] **Step 2: Commit**

```bash
git add frontend/apps/main/src/components/agent/AgentCard.vue
git commit -m "feat(ui): add AgentCard component"
```

---

## Task 17: Frontend — AgentGrid Component

**Files:**
- Create: `frontend/apps/main/src/components/agent/AgentGrid.vue`

- [ ] **Step 1: Write the component**

```vue
<!-- frontend/apps/main/src/components/agent/AgentGrid.vue -->
<script setup lang="ts">
import type { Agent } from '@/types/agent'
import AgentCard from './AgentCard.vue'
import { useI18n } from 'vue-i18n'

const { t } = useI18n()

defineProps<{
  builtinAgents: Agent[]
  customAgents: Agent[]
  showCreate?: boolean
}>()

const emit = defineEmits<{
  consult: [agent: Agent]
  edit: [agent: Agent]
  create: []
}>()
</script>

<template>
  <!-- Builtin agents section -->
  <div v-if="builtinAgents.length" class="agent-section">
    <div class="agent-section__title">{{ t('agents.builtinAgents') }}</div>
    <div class="agent-grid">
      <AgentCard
        v-for="agent in builtinAgents"
        :key="agent.id"
        :agent="agent"
        :show-actions="true"
        @consult="emit('consult', $event)"
        @edit="emit('edit', $event)"
      />
    </div>
  </div>

  <!-- Custom agents section -->
  <div class="agent-section">
    <div class="agent-section__title">{{ t('agents.customAgents') }}</div>
    <div class="agent-grid">
      <AgentCard
        v-for="agent in customAgents"
        :key="agent.id"
        :agent="agent"
        :show-actions="true"
        @consult="emit('consult', $event)"
        @edit="emit('edit', $event)"
      />
      <div
        v-if="showCreate"
        class="agent-card agent-card--create"
        @click="emit('create')"
      >
        <div class="agent-card__icon">＋</div>
        <div class="agent-card__body">
          <div class="agent-card__name">{{ t('agents.createAgent') }}</div>
        </div>
      </div>
    </div>
    <van-empty
      v-if="!customAgents.length && !showCreate"
      :description="t('agents.noCustomAgents')"
    />
  </div>
</template>

<style scoped>
.agent-section {
  margin-bottom: 16px;
}

.agent-section__title {
  font-size: 14px;
  font-weight: 600;
  color: var(--van-text-color-2);
  padding: 0 4px 8px;
}

.agent-grid {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 12px;
}

.agent-card--create {
  border: 2px dashed var(--van-border-color);
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  min-height: 100px;
  cursor: pointer;
}

.agent-card--create .agent-card__icon {
  font-size: 28px;
  color: var(--van-text-color-3);
}

.agent-card--create .agent-card__name {
  color: var(--van-text-color-3);
  font-size: 13px;
}
</style>
```

- [ ] **Step 2: Commit**

```bash
git add frontend/apps/main/src/components/agent/AgentGrid.vue
git commit -m "feat(ui): add AgentGrid layout component"
```

---

## Task 18: Frontend — Refactor AIHubPage to Use Agent Grid

**Files:**
- Modify: `frontend/apps/main/src/pages/AIHubPage.vue`

This is the core frontend change. Replace the capability grid with the Agent card grid while preserving the health score header and chat input bar.

- [ ] **Step 1: Add agent store import and load**

In the `<script setup>` section of `AIHubPage.vue`, add:

```typescript
import AgentGrid from '@/components/agent/AgentGrid.vue'
import { useAgentStore } from '@/stores/agent'
import type { Agent } from '@/types/agent'

const agentStore = useAgentStore()
```

In the `onMounted` (or wherever capabilities are currently loaded), add:
```typescript
agentStore.loadAgents()
```

- [ ] **Step 2: Replace capability grid with AgentGrid**

Find the section that renders the capability grid (the `<div>` with 3-column grid of `<button>` cards iterating over `SkillDefinition` items). Replace it with:

```vue
<AgentGrid
  :builtin-agents="agentStore.builtinAgents.filter(a => a.is_enabled)"
  :custom-agents="agentStore.customAgents.filter(a => a.is_enabled)"
  :show-create="isOwner"
  @consult="handleAgentConsult"
  @edit="handleAgentEdit"
  @create="router.push({ name: 'AgentCreate' })"
/>
```

- [ ] **Step 3: Add event handlers**

Add to the `<script setup>`:

```typescript
function handleAgentConsult(agent: Agent) {
  if (agent.is_builtin) {
    // Builtin agents: navigate to dedicated result page (future Task)
    // For now, route to chat with agent context
    router.push({ name: 'AIChat', query: { agentId: agent.id } })
  } else {
    router.push({ name: 'AIChat', query: { agentId: agent.id } })
  }
}

function handleAgentEdit(agent: Agent) {
  router.push({ name: 'AgentEdit', params: { id: agent.id } })
}
```

- [ ] **Step 4: Remove old capability grid imports and state**

Remove or comment out:
- Import of `getSkillsGrouped` (if only used for the grid)
- The `CAP_POLL_CAPABILITIES` polling logic (will be re-implemented for agents later)
- The capability grid `<div>` markup

Keep: health score header, stats bar, report card, chat input bar.

- [ ] **Step 5: Run typecheck**

Run: `cd frontend/apps/main && npx vue-tsc --noEmit 2>&1 | tail -10`
Expected: No errors.

- [ ] **Step 6: Visual verification**

Run dev server (`npm run dev` in a separate terminal) and verify:
- AIHub shows health score header (unchanged)
- Below it shows "内置智能体" section with 2 agent cards
- Below it shows "我的智能体" section (empty + create button for owner)
- Chat input bar still present at bottom

- [ ] **Step 7: Commit**

```bash
git add frontend/apps/main/src/pages/AIHubPage.vue
git commit -m "feat(ui): refactor AIHubPage to Agent card grid"
```

---

## Task 19: Frontend — Add Agent Routes

**Files:**
- Modify: `frontend/apps/main/src/router/index.ts`

- [ ] **Step 1: Add agent management routes**

In `frontend/apps/main/src/router/index.ts`, add the following routes inside the authenticated children array, near the existing `/settings/ai/skills` route:

```typescript
        {
          path: 'settings/ai/agents',
          name: 'AgentsManage',
          component: () => import('@/pages/AgentsManagePage.vue')
        },
        {
          path: 'settings/ai/agents/new',
          name: 'AgentCreate',
          component: () => import('@/pages/AgentFormPage.vue')
        },
        {
          path: 'settings/ai/agents/:id/edit',
          name: 'AgentEdit',
          component: () => import('@/pages/AgentFormPage.vue')
        },
```

- [ ] **Step 2: Commit**

```bash
git add frontend/apps/main/src/router/index.ts
git commit -m "feat(router): add agent management routes"
```

---

## Task 20: Frontend — Add Settings Navigation Cell

**Files:**
- Modify: `frontend/apps/main/src/pages/SettingsPage.vue`

- [ ] **Step 1: Add agent management cell**

In `SettingsPage.vue`, inside the AI settings `<van-cell-group>`, after the Skills manage cell, add:

```vue
<van-cell
  :title="t('settings.agentsManage')"
  is-link
  to="/settings/ai/agents"
/>
```

- [ ] **Step 2: Run typecheck**

Run: `cd frontend/apps/main && npx vue-tsc --noEmit 2>&1 | tail -5`
Expected: No errors.

- [ ] **Step 3: Commit**

```bash
git add frontend/apps/main/src/pages/SettingsPage.vue
git commit -m "feat(ui): add agent management entry in settings page"
```

---

## Task 21: Frontend — AgentsManagePage

**Files:**
- Create: `frontend/apps/main/src/pages/AgentsManagePage.vue`

- [ ] **Step 1: Write the management page**

```vue
<!-- frontend/apps/main/src/pages/AgentsManagePage.vue -->
<script setup lang="ts">
import { onMounted } from 'vue'
import { useI18n } from 'vue-i18n'
import { useRouter } from 'vue-router'
import { showConfirmDialog, showToast } from 'vant'
import { useAgentStore } from '@/stores/agent'
import { useAuthStore } from '@/stores/auth'
import type { Agent } from '@/types/agent'

const { t } = useI18n()
const router = useRouter()
const agentStore = useAgentStore()
const authStore = useAuthStore()
const isOwner = authStore.user?.role === 'owner'

onMounted(() => {
  agentStore.loadAgents()
})

async function handleToggle(agent: Agent, enabled: boolean) {
  await agentStore.toggleAgentEnabled(agent.id, enabled)
  showToast(enabled ? t('toast.agentToggleEnabled') : t('toast.agentToggleDisabled'))
}

async function handleDelete(agent: Agent) {
  await showConfirmDialog({
    title: t('agents.form.deleteConfirm'),
  })
  await agentStore.removeAgent(agent.id)
  showToast(t('agents.form.deleteSuccess'))
}
</script>

<template>
  <div class="page">
    <van-nav-bar :title="t('agents.title')" left-arrow @click-left="router.back()" />

    <van-cell-group inset :title="t('agents.builtinAgents')">
      <van-cell
        v-for="agent in agentStore.builtinAgents"
        :key="agent.id"
        :title="agent.display_name"
        :label="agent.description || ''"
        :icon="agent.icon || '🤖'"
      >
        <template #value>
          <van-switch
            :model-value="agent.is_enabled"
            size="20"
            :disabled="!isOwner"
            @update:model-value="(v: boolean) => handleToggle(agent, v)"
          />
        </template>
      </van-cell>
    </van-cell-group>

    <van-cell-group inset :title="t('agents.customAgents')">
      <van-cell
        v-for="agent in agentStore.customAgents"
        :key="agent.id"
        :title="agent.display_name"
        :label="agent.description || ''"
        :icon="agent.icon || '🤖'"
        is-link
        @click="router.push({ name: 'AgentEdit', params: { id: agent.id } })"
      >
        <template #value>
          <div class="cell-actions" @click.stop>
            <van-switch
              :model-value="agent.is_enabled"
              size="20"
              :disabled="!isOwner"
              @update:model-value="(v: boolean) => handleToggle(agent, v)"
            />
            <van-icon
              v-if="agent.can_delete"
              name="delete-o"
              size="18"
              color="var(--van-danger-color)"
              @click="handleDelete(agent)"
            />
          </div>
        </template>
      </van-cell>
      <van-empty
        v-if="!agentStore.customAgents.length"
        :description="t('agents.noCustomAgents')"
      >
        <van-button
          v-if="isOwner"
          type="primary"
          size="small"
          @click="router.push({ name: 'AgentCreate' })"
        >
          {{ t('agents.createAgent') }}
        </van-button>
      </van-empty>
    </van-cell-group>

    <div v-if="isOwner && agentStore.customAgents.length" class="bottom-bar">
      <van-button
        type="primary"
        block
        round
        @click="router.push({ name: 'AgentCreate' })"
      >
        {{ t('agents.createAgent') }}
      </van-button>
    </div>
  </div>
</template>

<style scoped>
.page {
  padding-bottom: 80px;
}

.cell-actions {
  display: flex;
  align-items: center;
  gap: 12px;
}

.bottom-bar {
  position: fixed;
  bottom: 0;
  left: 0;
  right: 0;
  padding: 12px 16px;
  padding-bottom: calc(12px + env(safe-area-inset-bottom));
  background: var(--van-background);
}
</style>
```

- [ ] **Step 2: Commit**

```bash
git add frontend/apps/main/src/pages/AgentsManagePage.vue
git commit -m "feat(ui): add AgentsManagePage for agent management"
```

---

## Task 22: Frontend — AgentFormPage (Create/Edit)

**Files:**
- Create: `frontend/apps/main/src/pages/AgentFormPage.vue`

- [ ] **Step 1: Write the form page**

```vue
<!-- frontend/apps/main/src/pages/AgentFormPage.vue -->
<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useI18n } from 'vue-i18n'
import { useRouter, useRoute } from 'vue-router'
import { showToast } from 'vant'
import { useAgentStore } from '@/stores/agent'
import { getAgent } from '@/api/agent'
import { getSkillsGrouped } from '@/api/ai'
import type { AgentCreatePayload, AgentUpdatePayload } from '@/types/agent'
import type { SkillDefinition } from '@/api/ai'

const { t } = useI18n()
const router = useRouter()
const route = useRoute()
const agentStore = useAgentStore()

const isEdit = computed(() => !!route.params.id)
const agentId = computed(() => route.params.id as string)

const form = ref<AgentCreatePayload>({
  agent_name: '',
  display_name: '',
  description: '',
  icon: '🤖',
  color: '#6366F1',
  soul_md: '',
  skills: [],
  model: undefined,
  subagent_enabled: false,
})

const isBuiltin = ref(false)
const availableSkills = ref<SkillDefinition[]>([])
const submitting = ref(false)

const ICON_OPTIONS = ['🤖', '🏥', '💰', '🎯', '📊', '🔍', '💡', '🛡️', '📈', '🧮',
  '🏠', '💳', '🎓', '🌟', '⚡', '🔧', '📋', '🎯', '🧠', '✨']

const COLOR_OPTIONS = [
  '#6366F1', '#10B981', '#F59E0B', '#EF4444',
  '#3B82F6', '#8B5CF6', '#EC4899', '#14B8A6',
]

onMounted(async () => {
  const skillData = await getSkillsGrouped()
  availableSkills.value = [...skillData.builtin.filter(s => s.is_enabled), ...skillData.custom.filter(s => s.is_enabled)]

  if (isEdit.value) {
    const agent = await getAgent(agentId.value)
    isBuiltin.value = agent.is_builtin
    form.value = {
      agent_name: agent.agent_name,
      display_name: agent.display_name,
      description: agent.description || '',
      icon: agent.icon || '🤖',
      color: agent.color || '#6366F1',
      soul_md: agent.soul_md,
      skills: agent.skills || [],
      model: agent.model || undefined,
      subagent_enabled: agent.subagent_enabled,
    }
  }
})

async function handleSubmit() {
  submitting.value = true
  try {
    if (isEdit.value) {
      const payload: AgentUpdatePayload = {}
      if (isBuiltin.value) {
        payload.icon = form.value.icon
        payload.color = form.value.color
      } else {
        payload.display_name = form.value.display_name
        payload.description = form.value.description
        payload.icon = form.value.icon
        payload.color = form.value.color
        payload.soul_md = form.value.soul_md
        payload.skills = form.value.skills
        payload.model = form.value.model
        payload.subagent_enabled = form.value.subagent_enabled
      }
      await agentStore.editAgent(agentId.value, payload)
      showToast(t('agents.form.updateSuccess'))
    } else {
      await agentStore.addAgent(form.value)
      showToast(t('agents.form.createSuccess'))
    }
    router.back()
  } finally {
    submitting.value = false
  }
}

function toggleSkill(skillId: string) {
  const skills = form.value.skills || []
  const idx = skills.indexOf(skillId)
  if (idx >= 0) {
    skills.splice(idx, 1)
  } else {
    skills.push(skillId)
  }
  form.value.skills = [...skills]
}
</script>

<template>
  <div class="page">
    <van-nav-bar
      :title="isEdit ? t('agents.editAgent') : t('agents.createAgent')"
      left-arrow
      @click-left="router.back()"
    />

    <van-cell-group inset>
      <van-field
        v-if="!isEdit"
        v-model="form.agent_name"
        :label="t('agents.form.agentName')"
        :placeholder="t('agents.form.agentNameHint')"
        :rules="[{ pattern: /^[a-z][a-z0-9_-]*$/, message: t('agents.form.agentNameHint') }]"
      />
      <van-field
        v-model="form.display_name"
        :label="t('agents.form.displayName')"
        required
      />
      <van-field
        v-model="form.description"
        :label="t('agents.form.description')"
        type="textarea"
        rows="2"
        autosize
      />
    </van-cell-group>

    <!-- Icon picker -->
    <van-cell-group inset :title="t('agents.form.icon')">
      <div class="icon-grid">
        <div
          v-for="icon in ICON_OPTIONS"
          :key="icon"
          class="icon-option"
          :class="{ 'icon-option--active': form.icon === icon }"
          @click="form.icon = icon"
        >
          {{ icon }}
        </div>
      </div>
    </van-cell-group>

    <!-- Color picker -->
    <van-cell-group inset :title="t('agents.form.color')">
      <div class="color-grid">
        <div
          v-for="color in COLOR_OPTIONS"
          :key="color"
          class="color-option"
          :class="{ 'color-option--active': form.color === color }"
          :style="{ background: color }"
          @click="form.color = color"
        />
      </div>
    </van-cell-group>

    <!-- SOUL.md editor (hidden for builtin) -->
    <van-cell-group v-if="!isBuiltin" inset :title="t('agents.form.soulMd')">
      <van-field
        v-model="form.soul_md"
        type="textarea"
        rows="8"
        autosize
        :placeholder="t('agents.form.soulMdHint')"
      />
    </van-cell-group>

    <!-- Skill selector (hidden for builtin) -->
    <van-cell-group v-if="!isBuiltin" inset :title="t('agents.form.skills')">
      <van-cell
        v-for="skill in availableSkills"
        :key="skill.id"
        :title="skill.name || skill.id"
        :label="skill.description || ''"
      >
        <template #right-icon>
          <van-checkbox
            :model-value="(form.skills || []).includes(skill.id)"
            @update:model-value="toggleSkill(skill.id)"
          />
        </template>
      </van-cell>
    </van-cell-group>

    <!-- Model selector (hidden for builtin) -->
    <van-cell-group v-if="!isBuiltin" inset>
      <van-field
        v-model="form.model"
        :label="t('agents.form.model')"
        :placeholder="t('agents.form.modelInherit')"
      />
      <van-cell :title="t('agents.form.subagentEnabled')">
        <template #value>
          <van-switch v-model="form.subagent_enabled" size="20" />
        </template>
      </van-cell>
    </van-cell-group>

    <div class="bottom-bar">
      <van-button
        type="primary"
        block
        round
        :loading="submitting"
        @click="handleSubmit"
      >
        {{ isEdit ? t('agents.form.updateBtn') : t('agents.form.createBtn') }}
      </van-button>
    </div>
  </div>
</template>

<style scoped>
.page {
  padding-bottom: 80px;
}

.icon-grid {
  display: grid;
  grid-template-columns: repeat(10, 1fr);
  gap: 4px;
  padding: 12px 16px;
}

.icon-option {
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 24px;
  height: 40px;
  border-radius: 8px;
  cursor: pointer;
  border: 2px solid transparent;
}

.icon-option--active {
  border-color: var(--van-primary-color);
  background: var(--van-primary-color-light);
}

.color-grid {
  display: flex;
  gap: 8px;
  padding: 12px 16px;
}

.color-option {
  width: 32px;
  height: 32px;
  border-radius: 50%;
  cursor: pointer;
  border: 3px solid transparent;
}

.color-option--active {
  border-color: var(--van-text-color);
}

.bottom-bar {
  position: fixed;
  bottom: 0;
  left: 0;
  right: 0;
  padding: 12px 16px;
  padding-bottom: calc(12px + env(safe-area-inset-bottom));
  background: var(--van-background);
}
</style>
```

- [ ] **Step 2: Run typecheck**

Run: `cd frontend/apps/main && npx vue-tsc --noEmit 2>&1 | tail -10`
Expected: No errors.

- [ ] **Step 3: Visual verification**

Open `http://localhost:5173/settings/ai/agents/new` in browser and verify:
- Form renders with all fields
- Icon/color pickers work
- Skill checkboxes load from API
- Submit creates agent and navigates back

- [ ] **Step 4: Commit**

```bash
git add frontend/apps/main/src/pages/AgentFormPage.vue
git commit -m "feat(ui): add AgentFormPage for create/edit agent"
```

---

## Task 23: Run Full Backend Test Suite

**Files:** None (verification only)

- [ ] **Step 1: Run all backend tests**

Run: `cd server && uv run pytest tests/backend/ -x -q --timeout=60 2>&1 | tail -20`
Expected: All existing tests pass. Table renames are transparent to tests since tests use in-memory SQLite with `create_all()`.

- [ ] **Step 2: Run agent tests**

Run: `cd server && uv run pytest tests/agent/ -x -q --timeout=60 2>&1 | tail -20`
Expected: All existing agent tests pass.

- [ ] **Step 3: Fix any failures**

If tests fail due to table name changes (e.g., test fixtures that hard-code table names), update them to use the new names.

---

## Task 24: Run Full Frontend Typecheck

**Files:** None (verification only)

- [ ] **Step 1: Run typecheck**

Run: `cd frontend/apps/main && npx vue-tsc --noEmit 2>&1 | tail -20`
Expected: No errors.

- [ ] **Step 2: Fix any type errors**

If type errors appear, fix them in the relevant files.

---

## Summary of Phases

| Phase | Tasks | Description |
|-------|-------|-------------|
| **P-1: Table Rename** | 1–2 | Alembic migration + `__tablename__` updates |
| **P0: Data Layer** | 3–7 | Model, schemas, router, internal API, tests |
| **P1: Agent Execution** | 8–11 | BackendClient method, AgentTempCache, stream_agent_dispatch, stream router |
| **P2: Frontend Hub** | 12–18 | Types, API, store, i18n, AgentCard, AgentGrid, AIHubPage refactor |
| **P3: Agent Management** | 19–22 | Routes, settings nav, AgentsManagePage, AgentFormPage |
| **P4: Verification** | 23–24 | Backend tests, frontend typecheck |

**Total: 24 tasks**

Future tasks (not in this plan, to be planned separately):
- `AgentResultPage.vue` — structured result page for builtin agents (spec §6.2)
- `AgentChatSection.vue` — conversation follow-up embedded in result page
- `AgentResultPanel.vue` — per-agent-type structured result renderer
- `agentEventStore.ts` / `agentStream.ts` — NDJSON event stream parsing for agent execution UI
- `AIChatPage.vue` modification — custom Agent dialog entry point (spec §6.4)
- `ModelSelector.vue` — dropdown with family provider list (currently plain text field)
- `SoulMdEditor.vue` — Markdown editor with preview (currently plain textarea)
- SOUL.md template system — "从模板创建" with preset templates (spec §12, §13)
- MCP server injection into agent temp config (spec §8.4)
- `make_lead_agent()` direct integration — current plan uses existing adapter as pragmatic first step; full harness-native path (ThreadState, middleware chain, subagent) requires deeper refactoring
- Removal of old skill routers (alerts.py, allocation.py, disposal.py, liability.py, report.py, spending_leak.py)
- Removal of old frontend pages (AIAlertsPage, AIDisposalPage, AIAllocationPage, SpendingLeaksPage)
- P4 cleanup: remove deprecated routes, update CLAUDE.md docs
