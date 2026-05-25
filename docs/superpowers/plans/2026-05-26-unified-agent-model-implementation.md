# 智能体管理统一模型实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将 Agents 和 Skills 双轨系统统一为单一智能体模型，Skills 变为能力标签而非独立管理实体。

**Architecture:** 在 ai_agents 表添加 agent_type 字段区分 system/builtin/custom，新建 skill_definitions 表作为全局能力定义库，废弃 ai_skills 表。前端统一展示智能体而非能力。

**Tech Stack:** SQLAlchemy + Alembic (backend), Pinia (frontend), Vue 3 + TypeScript

---

## 文件结构

### Phase 1: 数据层改造（Backend）

| 文件 | 操作 | 说明 |
|------|------|------|
| `server/apps/backend/alembic/versions/xxx_unified_agent_model.py` | 创建 | Migration: skill_definitions表、ai_agents改造、ai_skills删除 |
| `server/apps/backend/app/models/skill_definition.py` | 创建 | SkillDefinition SQLAlchemy模型 |
| `server/apps/backend/app/models/ai_agent.py` | 修改 | 添加agent_type字段，移除is_builtin |
| `server/apps/backend/app/schemas/skill_definition.py` | 创建 | SkillDefinitionResponse schema |
| `server/apps/backend/app/schemas/ai_agent.py` | 修改 | 添加agent_type，修改权限计算逻辑 |
| `server/apps/backend/app/routers/ai_skill_definitions.py` | 创建 | GET /ai/skill-definitions endpoint |
| `server/apps/backend/app/routers/ai_agents.py` | 修改 | 添加system智能体处理逻辑 |
| `server/apps/backend/app/routers/ai_skills.py` | 废弃 | 标记为deprecated，返回404或重定向 |
| `server/apps/backend/app/main.py` | 修改 | 注册新router，废弃旧router |

### Phase 2: Agent Service 改造

| 文件 | 操作 | 说明 |
|------|------|------|
| `server/apps/agent/services/capability_registry.py` | 修改 | 从skill_definitions加载能力定义 |
| `server/apps/agent/routers/agent_stream.py` | 保持 | 主入口不变 |

### Phase 3: 前端改造

| 文件 | 操作 | 说明 |
|------|------|------|
| `frontend/apps/main/src/types/agent.ts` | 修改 | 添加agent_type字段 |
| `frontend/apps/main/src/types/skillDefinition.ts` | 创建 | SkillDefinition类型定义 |
| `frontend/apps/main/src/api/agent.ts` | 修改 | 添加getSkillDefinitions方法 |
| `frontend/apps/main/src/stores/agent.ts` | 修改 | 加载所有智能体（含system） |
| `frontend/apps/main/src/stores/capability.ts` | 简化 | 只加载skill definitions |
| `frontend/apps/main/src/pages/AgentsManagePage.vue` | 修改 | 分组展示、权限控制 |
| `frontend/apps/main/src/pages/AIHubPage.vue` | 修改 | 智能体卡片展示 |
| `frontend/apps/main/src/i18n/locales/zh-CN.ts` | 修改 | 添加新UI文本 |

---

## Task 1: 创建 SkillDefinition 数据模型

**Files:**
- Create: `server/apps/backend/app/models/skill_definition.py`
- Modify: `server/apps/backend/app/models/__init__.py`

- [ ] **Step 1: 创建 SkillDefinition 模型文件**

```python
# server/apps/backend/app/models/skill_definition.py
from sqlalchemy import Column, String, Text, Boolean
from sqlalchemy.orm import relationship

from apps.backend.app.models import Base


class SkillDefinition(Base):
    """全局能力定义库，所有家庭共享"""
    __tablename__ = "skill_definitions"

    skill_id = Column(String(50), primary_key=True)
    name = Column(String(100), nullable=False)
    description = Column(Text, nullable=True)
    icon = Column(String(10), nullable=True)  # emoji
    color = Column(String(10), nullable=True)  # hex color
    category = Column(String(20), default="analysis")  # system | analysis | advisor
    is_computation_only = Column(Boolean, default=False)  # true for time_machine

    def __repr__(self) -> str:
        return f"<SkillDefinition(skill_id={self.skill_id}, name={self.name})>"
```

- [ ] **Step 2: 在 models/__init__.py 中注册模型**

在 `server/apps/backend/app/models/__init__.py` 的导入区域添加：

```python
from apps.backend.app.models.skill_definition import SkillDefinition
```

- [ ] **Step 3: Commit**

```bash
git add server/apps/backend/app/models/skill_definition.py server/apps/backend/app/models/__init__.py
git commit -m "feat(models): add SkillDefinition model for global skill definitions

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Task 2: 创建 Alembic Migration

**Files:**
- Create: `server/apps/backend/alembic/versions/<timestamp>_unified_agent_model.py`

- [ ] **Step 1: 生成 migration 文件**

```bash
cd server/apps/backend
uv run alembic revision -m "unified_agent_model"
```

记下生成的文件名（如 `abc123_unified_agent_model.py`）。

- [ ] **Step 2: 编写 upgrade() 函数**

```python
def upgrade() -> None:
    # 1. 创建 skill_definitions 表
    op.create_table(
        "skill_definitions",
        sa.Column("skill_id", sa.String(50), primary_key=True),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("icon", sa.String(10), nullable=True),
        sa.Column("color", sa.String(10), nullable=True),
        sa.Column("category", sa.String(20), server_default="analysis"),
        sa.Column("is_computation_only", sa.Boolean(), server_default="false"),
    )

    # 2. Seed skill_definitions 数据
    op.execute("""
        INSERT INTO skill_definitions (skill_id, name, description, icon, color, category, is_computation_only) VALUES
            ('chat', 'AI问答', '通用AI问答能力，可回答关于净值、配置、负债、趋势等问题', '💬', '#3B82F6', 'system', false),
            ('time_machine', '资产时光机', '资产模拟计算，包括假设分析、趋势预测、购买力计算', '⏰', '#8B5CF6', 'system', true),
            ('report', '资产报告', '家庭资产健康报告，综合分析财务状况', '📊', '#10B981', 'analysis', false),
            ('alerts', '老化预警', '资产老化预警分析，识别即将到期或高维护成本资产', '⚠️', '#F59E0B', 'analysis', false),
            ('allocation', '配置偏离', '资产配置偏离分析，检查是否偏离目标配置', '📐', '#6366F1', 'analysis', false),
            ('disposal', '闲置处置', '闲置资产处置建议，给出处置渠道和预估价值', '🗑️', '#EF4444', 'advisor', false),
            ('liability', '负债分析', '家庭负债分析和还款策略建议', '📉', '#EC4899', 'analysis', false),
            ('spending_leak', '消费漏洞', '消费漏洞识别，发现隐性浪费', '🔍', '#14B8A6', 'advisor', false);
    """)

    # 3. 添加 agent_type 字段到 ai_agents
    op.add_column("ai_agents", sa.Column("agent_type", sa.String(20), server_default="builtin"))

    # 4. 更新现有记录的 agent_type
    op.execute("""
        UPDATE ai_agents SET agent_type = 'builtin' WHERE is_builtin = true;
        UPDATE ai_agents SET agent_type = 'custom' WHERE is_builtin = false AND family_id != 0;
    """)

    # 5. 移除 is_builtin 字段
    op.drop_column("ai_agents", "is_builtin")

    # 6. 插入系统智能体
    # 使用 snowflake ID 生成（需要从应用层获取）
    # 这里使用固定的负数ID作为占位符，实际需要替换为真实snowflake
    op.execute("""
        INSERT INTO ai_agents (id, family_id, agent_type, agent_name, display_name, description, icon, color, soul_md, skills, is_enabled, display_order, created_at, updated_at)
        SELECT
            next_snowflake_id(),
            0,
            'system',
            'ai-assistant',
            'AI助手',
            '通用AI问答能力，可回答关于净值、配置、负债、趋势等问题',
            '💬',
            '#3B82F6',
            '你是Numina家庭资产管理系统的AI助手。你具备专业的财务分析能力，可以帮助用户：
- 回答关于家庭净值、资产配置、负债结构的问题
- 解释财务概念和分析结果
- 提供财务建议和优化策略

你的回答应该简洁、专业、易懂。使用中文回答。',
            '["chat"]',
            true,
            0,
            NOW(),
            NOW();
    """)

    op.execute("""
        INSERT INTO ai_agents (id, family_id, agent_type, agent_name, display_name, description, icon, color, soul_md, skills, is_enabled, display_order, created_at, updated_at)
        SELECT
            next_snowflake_id(),
            0,
            'system',
            'time-machine',
            '资产时光机',
            '基于规则的资产模拟计算，包括假设分析、趋势预测、购买力计算',
            '⏰',
            '#8B5CF6',
            '纯规则计算，无需LLM。使用数值模拟进行资产预测分析。',
            '["time_machine"]',
            true,
            10,
            NOW(),
            NOW();
    """)

    # 7. 调整内置智能体排序
    op.execute("""
        UPDATE ai_agents SET display_order = 100 WHERE agent_name = 'asset-health-advisor';
        UPDATE ai_agents SET display_order = 200 WHERE agent_name = 'finance-optimizer';
    """)

    # 8. 删除 ai_skills 表
    op.drop_table("ai_skills")
```

- [ ] **Step 3: 编写 downgrade() 函数**

```python
def downgrade() -> None:
    # 1. 恢复 ai_skills 表结构（简化版本，数据已丢失）
    op.create_table(
        "ai_skills",
        sa.Column("id", sa.BigInteger(), primary_key=True),
        sa.Column("family_id", sa.BigInteger(), nullable=False),
        sa.Column("skill_id", sa.String(50), nullable=False),
        sa.Column("skill_type", sa.String(20), server_default="builtin"),
        sa.Column("is_enabled", sa.Boolean(), server_default="true"),
    )

    # 2. 恢复 is_builtin 字段
    op.add_column("ai_agents", sa.Column("is_builtin", sa.Boolean(), server_default="false"))
    op.execute("""
        UPDATE ai_agents SET is_builtin = true WHERE agent_type IN ('system', 'builtin');
        UPDATE ai_agents SET is_builtin = false WHERE agent_type = 'custom';
    """)

    # 3. 删除 agent_type 字段
    op.drop_column("ai_agents", "agent_type")

    # 4. 删除系统智能体
    op.execute("DELETE FROM ai_agents WHERE agent_type = 'system'")

    # 5. 删除 skill_definitions 表
    op.drop_table("skill_definitions")
```

- [ ] **Step 4: Commit migration**

```bash
git add server/apps/backend/alembic/versions/<timestamp>_unified_agent_model.py
git commit -m "feat(migration): unified agent model - add skill_definitions, modify ai_agents

- Create skill_definitions table with seed data
- Add agent_type field to ai_agents (system|builtin|custom)
- Remove is_builtin field (replaced by agent_type)
- Insert system agents: ai-assistant, time-machine
- Drop ai_skills table

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Task 3: 创建 SkillDefinition Schema

**Files:**
- Create: `server/apps/backend/app/schemas/skill_definition.py`

- [ ] **Step 1: 创建 Schema 文件**

```python
# server/apps/backend/app/schemas/skill_definition.py
from pydantic import BaseModel


class SkillDefinitionResponse(BaseModel):
    """能力定义响应"""
    skill_id: str
    name: str
    description: str | None = None
    icon: str | None = None
    color: str | None = None
    category: str = "analysis"
    is_computation_only: bool = False


class SkillDefinitionListResponse(BaseModel):
    """能力定义列表响应"""
    items: list[SkillDefinitionResponse]
    total: int
```

- [ ] **Step 2: Commit**

```bash
git add server/apps/backend/app/schemas/skill_definition.py
git commit -m "feat(schemas): add SkillDefinitionResponse schema

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Task 4: 创建 SkillDefinitions Router

**Files:**
- Create: `server/apps/backend/app/routers/ai_skill_definitions.py`
- Modify: `server/apps/backend/app/main.py`

- [ ] **Step 1: 创建 Router 文件**

```python
# server/apps/backend/app/routers/ai_skill_definitions.py
from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from apps.backend.app.dependencies import get_db
from apps.backend.app.models.skill_definition import SkillDefinition
from apps.backend.app.schemas.skill_definition import (
    SkillDefinitionResponse,
    SkillDefinitionListResponse,
)

router = APIRouter(prefix="/ai/skill-definitions", tags=["AI Skill Definitions"])


@router.get("", response_model=SkillDefinitionListResponse)
async def list_skill_definitions(db: AsyncSession = Depends(get_db)) -> SkillDefinitionListResponse:
    """获取所有能力定义（全局共享）"""
    result = await db.execute(select(SkillDefinition).order_by(SkillDefinition.category, SkillDefinition.skill_id))
    definitions = result.scalars().all()
    return SkillDefinitionListResponse(
        items=[SkillDefinitionResponse.model_validate(d) for d in definitions],
        total=len(definitions),
    )
```

- [ ] **Step 2: 在 main.py 中注册 router**

在 `server/apps/backend/app/main.py` 的 router 注册区域添加：

```python
from apps.backend.app.routers.ai_skill_definitions import router as skill_definitions_router
# ...
app.include_router(skill_definitions_router, prefix="/api/v1")
```

- [ ] **Step 3: Commit**

```bash
git add server/apps/backend/app/routers/ai_skill_definitions.py server/apps/backend/app/main.py
git commit -m "feat(router): add /ai/skill-definitions endpoint

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Task 5: 修改 AIAgent Model

**Files:**
- Modify: `server/apps/backend/app/models/ai_agent.py`

- [ ] **Step 1: 添加 agent_type 字段，移除 is_builtin**

修改 `server/apps/backend/app/models/ai_agent.py`：

```python
# 在现有字段列表中，找到 is_builtin 字段并替换为 agent_type
# 原代码（约第45行）：
#     is_builtin = Column(Boolean, default=False)

# 替换为：
    agent_type = Column(String(20), default="builtin")  # system | builtin | custom
```

- [ ] **Step 2: 移除 is_builtin 相关的约束检查（如有）**

检查 `__table_args__` 中是否有涉及 `is_builtin` 的约束，如有则移除或替换为 `agent_type`。

- [ ] **Step 3: Commit**

```bash
git add server/apps/backend/app/models/ai_agent.py
git commit -m "refactor(models): replace is_builtin with agent_type in AIAgent

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Task 6: 修改 Agent Schemas

**Files:**
- Modify: `server/apps/backend/app/schemas/ai_agent.py`

- [ ] **Step 1: 添加 agent_type 字段到所有 Agent schemas**

修改 `server/apps/backend/app/schemas/ai_agent.py`：

```python
# AgentResponse（约第44-64行）添加 agent_type 字段
class AgentResponse(SnowflakeBase):
    agent_type: str = "builtin"  # system | builtin | custom
    agent_name: str
    display_name: str
    description: str | None = None
    icon: str | None = None
    color: str | None = None
    soul_md: str | None = None
    skills: list[str] = []
    model: str | None = None
    subagent_enabled: bool = False
    tool_groups: list[str] = []
    is_enabled: bool = True
    display_order: int = 0
    can_edit: bool = False
    can_delete: bool = False

# AgentCreateRequest（约第11-28行）添加 agent_type（但用户创建只能是 custom）
class AgentCreateRequest(BaseModel):
    agent_name: str
    display_name: str
    description: str | None = None
    icon: str | None = None
    color: str | None = None
    soul_md: str | None = None
    skills: list[str] = []
    model: str | None = None
    subagent_enabled: bool = False
    tool_groups: list[str] = []
    # agent_type 不在请求中，由后端设置为 "custom"

# AgentUpdateRequest（约第31-41行）保持不变，但需考虑 agent_type 权限
class AgentUpdateRequest(BaseModel):
    display_name: str | None = None
    description: str | None = None
    icon: str | None = None
    color: str | None = None
    soul_md: str | None = None  # 仅 custom 可修改
    skills: list[str] | None = None  # 仅 custom 可修改
    model: str | None = None  # 仅 custom 可修改
    subagent_enabled: bool | None = None
    tool_groups: list[str] | None = None
    display_order: int | None = None
```

- [ ] **Step 2: 修改 AgentListResponse 结构**

```python
# AgentListResponse（约第67-69行）改为按 agent_type 分组
class AgentListGroupedResponse(BaseModel):
    system: list[AgentResponse] = []
    builtin: list[AgentResponse] = []
    custom: list[AgentResponse] = []
    total: int = 0

# 废弃旧的 AgentListResponse
# class AgentListResponse(BaseModel):
#     builtin: list[AgentResponse] = []
#     custom: list[AgentResponse] = []
```

- [ ] **Step 3: Commit**

```bash
git add server/apps/backend/app/schemas/ai_agent.py
git commit -m "refactor(schemas): add agent_type to Agent schemas, grouped response

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Task 7: 修改 Agents Router

**Files:**
- Modify: `server/apps/backend/app/routers/ai_agents.py`

- [ ] **Step 1: 修改 list_agents 返回分组结构**

修改 `server/apps/backend/app/routers/ai_agents.py` 中的 `list_agents` 函数（约第31-49行）：

```python
@router.get("", response_model=AgentListGroupedResponse)
async def list_agents(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> AgentListGroupedResponse:
    """列出所有智能体，按 agent_type 分组"""
    family_id = current_user.family_id

    # 查询所有智能体：系统（family_id=0）+ 当前家庭的自定义
    result = await db.execute(
        select(AIAgent)
        .where(
            or_(AIAgent.family_id == 0, AIAgent.family_id == family_id)
        )
        .order_by(AIAgent.agent_type, AIAgent.display_order)
    )
    agents = result.scalars().all()

    # 分组并计算权限
    system_agents = []
    builtin_agents = []
    custom_agents = []

    for agent in agents:
        agent_resp = AgentResponse.model_validate(agent)
        # 计算 can_edit 和 can_delete
        if agent.agent_type == "system":
            agent_resp.can_edit = False
            agent_resp.can_delete = False
            system_agents.append(agent_resp)
        elif agent.agent_type == "builtin":
            agent_resp.can_edit = True  # 可编辑外观（icon/color/order）
            agent_resp.can_delete = False
            builtin_agents.append(agent_resp)
        else:  # custom
            agent_resp.can_edit = True
            agent_resp.can_delete = (agent.created_by == current_user.id or current_user.role == "owner")
            custom_agents.append(agent_resp)

    return AgentListGroupedResponse(
        system=system_agents,
        builtin=builtin_agents,
        custom=custom_agents,
        total=len(agents),
    )
```

- [ ] **Step 2: 修改 update_agent 权限逻辑**

修改 `update_agent` 函数（约第102-128行），根据 `agent_type` 限制可编辑字段：

```python
@router.put("/{id}", response_model=AgentResponse)
async def update_agent(
    id: int,
    payload: AgentUpdateRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> AgentResponse:
    """更新智能体"""
    agent = await db.get(AIAgent, id)
    if not agent:
        raise HTTPException(status_code=404, detail="智能体不存在")

    # 权限检查
    if agent.agent_type == "system":
        raise HTTPException(status_code=403, detail="系统智能体不可修改")
    if agent.agent_type == "builtin":
        # 仅允许修改外观字段
        if any([
            payload.soul_md is not None,
            payload.skills is not None,
            payload.model is not None,
            payload.subagent_enabled is not None,
            payload.tool_groups is not None,
        ]):
            raise HTTPException(status_code=403, detail="内置智能体仅可修改外观（图标、颜色、排序）")
    if agent.agent_type == "custom":
        if agent.family_id != current_user.family_id:
            raise HTTPException(status_code=403, detail="无权修改此智能体")

    # 更新字段（仅更新非 None 的字段）
    update_data = payload.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(agent, key, value)

    await db.commit()
    await db.refresh(agent)

    return AgentResponse.model_validate(agent)
```

- [ ] **Step 3: 修改 delete_agent 权限逻辑**

修改 `delete_agent` 函数（约第131-145行）：

```python
@router.delete("/{id}")
async def delete_agent(
    id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    """删除智能体（仅 custom 类型）"""
    agent = await db.get(AIAgent, id)
    if not agent:
        raise HTTPException(status_code=404, detail="智能体不存在")

    if agent.agent_type in ("system", "builtin"):
        raise HTTPException(status_code=403, detail="系统智能体和内置智能体不可删除")

    if agent.agent_type == "custom":
        if agent.family_id != current_user.family_id:
            raise HTTPException(status_code=403, detail="无权删除此智能体")
        if agent.created_by != current_user.id and current_user.role != "owner":
            raise HTTPException(status_code=403, detail="仅创建者或家庭管理员可删除")

    await db.delete(agent)
    await db.commit()

    return {"message": "智能体已删除"}
```

- [ ] **Step 4: 修改 create_agent 设置 agent_type**

修改 `create_agent` 函数（约第66-99行），确保新创建的智能体 `agent_type="custom"`：

```python
@router.post("", response_model=AgentResponse, status_code=201)
async def create_agent(
    payload: AgentCreateRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> AgentResponse:
    """创建自定义智能体"""
    # 检查 agent_name 是否已存在
    existing = await db.execute(
        select(AIAgent).where(
            AIAgent.agent_name == payload.agent_name,
            or_(AIAgent.family_id == 0, AIAgent.family_id == current_user.family_id)
        )
    )
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="智能体名称已存在")

    agent = AIAgent(
        id=generate_snowflake_id(),
        family_id=current_user.family_id,
        agent_type="custom",  # 强制为 custom
        agent_name=payload.agent_name,
        display_name=payload.display_name,
        description=payload.description,
        icon=payload.icon,
        color=payload.color,
        soul_md=payload.soul_md,
        skills=payload.skills,
        model=payload.model,
        subagent_enabled=payload.subagent_enabled,
        tool_groups=payload.tool_groups,
        is_enabled=True,
        display_order=1000,  # 自定义智能体排在后面
        created_by=current_user.id,
    )

    db.add(agent)
    await db.commit()
    await db.refresh(agent)

    resp = AgentResponse.model_validate(agent)
    resp.can_edit = True
    resp.can_delete = True
    return resp
```

- [ ] **Step 5: Commit**

```bash
git add server/apps/backend/app/routers/ai_agents.py
git commit -m "refactor(router): update agents router for unified agent_type model

- List agents grouped by system/builtin/custom
- Enforce edit/delete permissions by agent_type
- Force new agents to agent_type=custom

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Task 8: 废弃 Skills Router

**Files:**
- Modify: `server/apps/backend/app/routers/ai_skills.py`
- Modify: `server/apps/backend/app/main.py`

- [ ] **Step 1: 在 ai_skills.py 添加废弃标记**

在 `server/apps/backend/app/routers/ai_skills.py` 文件顶部添加：

```python
"""
DEPRECATED: This router is deprecated and will be removed.
Use /ai/skill-definitions for skill definitions.
Use /ai/agents for agent management (agents now contain skills as tags).
"""
```

并在每个 endpoint 上添加 `deprecated=True` 参数：

```python
@router.get("", response_model=..., deprecated=True)
@router.get("/grouped", response_model=..., deprecated=True)
# ... 所有 endpoints
```

- [ ] **Step 2: 在 main.py 中移除 skills router 注册（或保留但标记废弃）**

选择 A（完全移除）或 B（保留但废弃）：

方案 A - 移除注册：
```python
# 删除或注释掉：
# from apps.backend.app.routers.ai_skills import router as skills_router
# app.include_router(skills_router, prefix="/api/v1")
```

方案 B - 保留但废弃（允许过渡期）：
```python
# 保留注册，OpenAPI 会显示 deprecated 标记
```

推荐方案 B，保留过渡期。

- [ ] **Step 3: Commit**

```bash
git add server/apps/backend/app/routers/ai_skills.py server/apps/backend/app/main.py
git commit -m "deprecated(router): mark ai_skills router as deprecated

Use /ai/skill-definitions and /ai/agents instead.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Task 9: 运行 Migration 并验证

**Files:**
- 无文件修改，运行验证

- [ ] **Step 1: 运行 Alembic upgrade**

```bash
cd server/apps/backend
uv run alembic upgrade head
```

Expected: Migration 成功执行，无错误。

- [ ] **Step 2: 验证数据库结构**

```bash
cd server/apps/backend
uv run python -c "
from sqlalchemy import create_engine, text
from apps.backend.app.config import settings

engine = create_engine(settings.database_url)
with engine.connect() as conn:
    # 检查 skill_definitions 表
    result = conn.execute(text('SELECT COUNT(*) FROM skill_definitions'))
    print(f'skill_definitions count: {result.scalar()}')

    # 检查 ai_agents.agent_type
    result = conn.execute(text('SELECT agent_type, COUNT(*) FROM ai_agents GROUP BY agent_type'))
    print('ai_agents by type:', list(result.fetchall()))

    # 检查系统智能体
    result = conn.execute(text('SELECT agent_name, display_name FROM ai_agents WHERE agent_type = \"system\"'))
    print('system agents:', list(result.fetchall()))
"
```

Expected:
- skill_definitions count: 8
- ai_agents by type: [('system', 2), ('builtin', 2), ('custom', N)]
- system agents: [('ai-assistant', 'AI助手'), ('time-machine', '资产时光机')]

- [ ] **Step 3: 运行 Backend tests**

```bash
cd server/apps/backend
uv run pytest tests/ -v -k "agent"
```

Expected: 所有 agent 相关测试通过。如有失败，分析原因并修复。

---

## Task 10: 修改 Agent Service Capability Registry

**Files:**
- Modify: `server/apps/agent/services/capability_registry.py`

- [ ] **Step 1: 简化 CapabilityRegistry 从 skill_definitions 加载**

修改 `server/apps/agent/services/capability_registry.py`：

```python
# 移除或简化 FIXED_CAPABILITIES 和 _fetch_ai_skills
# 从 backend 的 skill_definitions 表加载能力定义

class CapabilityRegistry:
    """能力注册表 - 从 skill_definitions 加载"""

    def __init__(self, backend_url: str):
        self.backend_url = backend_url
        self._definitions_cache: dict[str, SkillDefinition] = {}
        self._cache_ttl = 300  # 5分钟缓存

    async def list_definitions(self) -> list[SkillDefinition]:
        """获取所有能力定义"""
        if self._definitions_cache:
            return list(self._definitions_cache.values())

        # 从 backend API 获取
        async with httpx.AsyncClient() as client:
            resp = await client.get(f"{self.backend_url}/api/v1/ai/skill-definitions")
            data = resp.json()
            definitions = [SkillDefinition(**d) for d in data["items"]]
            self._definitions_cache = {d.skill_id: d for d in definitions}
            return definitions

    async def get_definition(self, skill_id: str) -> SkillDefinition | None:
        """获取单个能力定义"""
        definitions = await self.list_definitions()
        return self._definitions_cache.get(skill_id)

    def is_computation_only(self, skill_id: str) -> bool:
        """检查是否为纯计算能力"""
        defn = self._definitions_cache.get(skill_id)
        return defn and defn.is_computation_only
```

- [ ] **Step 2: 移除 FamilySkillConfig 依赖**

移除 `_fetch_ai_skills` 方法（约第193-211行），因为启用/禁用现在由 Agent 控制。

- [ ] **Step 3: Commit**

```bash
git add server/apps/agent/services/capability_registry.py
git commit -m "refactor(agent-service): simplify CapabilityRegistry to load from skill_definitions

Remove FamilySkillConfig dependency, enable/disable now controlled by Agent.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Task 11: 前端类型定义更新

**Files:**
- Modify: `frontend/apps/main/src/types/agent.ts`
- Create: `frontend/apps/main/src/types/skillDefinition.ts`

- [ ] **Step 1: 更新 Agent 类型**

修改 `frontend/apps/main/src/types/agent.ts`：

```typescript
// 在 Agent interface 中添加 agent_type
export interface Agent {
  id: string
  family_id: number
  agent_type: 'system' | 'builtin' | 'custom'  // 新增
  agent_name: string
  display_name: string
  description: string | null
  icon: string | null
  color: string | null
  soul_md: string | null
  skills: string[]
  model: string | null
  subagent_enabled: boolean
  tool_groups: string[]
  is_enabled: boolean
  display_order: number
  can_edit: boolean
  can_delete: boolean
}

// 更新 AgentListResponse 为分组结构
export interface AgentListGroupedResponse {
  system: Agent[]
  builtin: Agent[]
  custom: Agent[]
  total: number
}

// 废弃旧的 AgentListResponse
// export interface AgentListResponse { ... }
```

- [ ] **Step 2: 创建 SkillDefinition 类型**

创建 `frontend/apps/main/src/types/skillDefinition.ts`：

```typescript
export interface SkillDefinition {
  skill_id: string
  name: string
  description: string | null
  icon: string | null
  color: string | null
  category: 'system' | 'analysis' | 'advisor'
  is_computation_only: boolean
}

export interface SkillDefinitionListResponse {
  items: SkillDefinition[]
  total: number
}
```

- [ ] **Step 3: Commit**

```bash
git add frontend/apps/main/src/types/agent.ts frontend/apps/main/src/types/skillDefinition.ts
git commit -m "feat(frontend): add agent_type to Agent type, add SkillDefinition type

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Task 12: 前端 API 更新

**Files:**
- Modify: `frontend/apps/main/src/api/agent.ts`

- [ ] **Step 1: 更新 getAgents 返回类型**

修改 `frontend/apps/main/src/api/agent.ts`：

```typescript
import type { Agent, AgentListGroupedResponse, AgentCreatePayload, AgentUpdatePayload } from '@/types/agent'
import type { SkillDefinitionListResponse } from '@/types/skillDefinition'

// 修改 getAgents 返回分组结构
export async function getAgents(): Promise<AgentListGroupedResponse> {
  const resp = await apiClient.get('/ai/agents')
  return resp.data as AgentListGroupedResponse
}

// 新增 getSkillDefinitions
export async function getSkillDefinitions(): Promise<SkillDefinitionListResponse> {
  const resp = await apiClient.get('/ai/skill-definitions')
  return resp.data as SkillDefinitionListResponse
}

// 其他函数保持不变
export async function getAgent(id: string): Promise<Agent> { ... }
export async function createAgent(payload: AgentCreatePayload): Promise<Agent> { ... }
export async function updateAgent(id: string, payload: AgentUpdatePayload): Promise<Agent> { ... }
export async function deleteAgent(id: string): Promise<void> { ... }
export async function toggleAgent(id: string, enabled: boolean): Promise<void> { ... }
```

- [ ] **Step 2: Commit**

```bash
git add frontend/apps/main/src/api/agent.ts
git commit -m "refactor(frontend): update getAgents for grouped response, add getSkillDefinitions

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Task 13: 前端 AgentStore 更新

**Files:**
- Modify: `frontend/apps/main/src/stores/agent.ts`

- [ ] **Step 1: 更新 agentStore 处理分组结构**

修改 `frontend/apps/main/src/stores/agent.ts`：

```typescript
import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import type { Agent, AgentListGroupedResponse } from '@/types/agent'
import type { SkillDefinition } from '@/types/skillDefinition'
import { getAgents, getSkillDefinitions, createAgent, updateAgent, deleteAgent, toggleAgent } from '@/api/agent'

export const useAgentStore = defineStore('agent', () => {
  // 分组存储
  const systemAgents = ref<Agent[]>([])
  const builtinAgents = ref<Agent[]>([])
  const customAgents = ref<Agent[]>([])
  const skillDefinitions = ref<SkillDefinition[]>([])

  // 计算属性
  const allAgents = computed(() => [...systemAgents.value, ...builtinAgents.value, ...customAgents.value])
  const enabledAgents = computed(() => allAgents.value.filter(a => a.is_enabled))
  const total = computed(() => allAgents.value.length)

  // 加载智能体
  async function loadAgents() {
    const data = await getAgents()
    systemAgents.value = data.system
    builtinAgents.value = data.builtin
    customAgents.value = data.custom
  }

  // 加载能力定义（用于创建自定义智能体时选择）
  async function loadSkillDefinitions() {
    const data = await getSkillDefinitions()
    skillDefinitions.value = data.items
  }

  // CRUD 操作
  async function addAgent(payload: AgentCreatePayload) {
    const agent = await createAgent(payload)
    customAgents.value.push(agent)
    customAgents.value.sort((a, b) => a.display_order - b.display_order)
  }

  async function editAgent(id: string, payload: AgentUpdatePayload) {
    const agent = await updateAgent(id, payload)
    // 更新对应列表中的智能体
    const lists = [systemAgents, builtinAgents, customAgents]
    for (const list of lists) {
      const idx = list.value.findIndex(a => a.id === id)
      if (idx !== -1) {
        list.value[idx] = agent
        break
      }
    }
  }

  async function removeAgent(id: string) {
    await deleteAgent(id)
    customAgents.value = customAgents.value.filter(a => a.id !== id)
  }

  async function toggleAgentEnabled(id: string, enabled: boolean) {
    await toggleAgent(id, enabled)
    const lists = [systemAgents, builtinAgents, customAgents]
    for (const list of lists) {
      const idx = list.value.findIndex(a => a.id === id)
      if (idx !== -1) {
        list.value[idx].is_enabled = enabled
        break
      }
    }
  }

  return {
    systemAgents,
    builtinAgents,
    customAgents,
    skillDefinitions,
    allAgents,
    enabledAgents,
    total,
    loadAgents,
    loadSkillDefinitions,
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
git commit -m "refactor(frontend): update agentStore for grouped agents and skill definitions

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Task 14: 前端 AgentsManagePage 改造

**Files:**
- Modify: `frontend/apps/main/src/pages/AgentsManagePage.vue`
- Modify: `frontend/apps/main/src/i18n/locales/zh-CN.ts`

- [ ] **Step 1: 添加 i18n 文本**

在 `frontend/apps/main/src/i18n/locales/zh-CN.ts` 的 AI 相关区域添加：

```typescript
// 在 ai 相关的 messages 中添加
ai: {
  // ... 现有文本
  systemAgents: '系统智能体',
  builtinAgents: '内置智能体',
  customAgents: '自定义智能体',
  systemAgentHint: '不可删除，仅可启用/禁用',
  builtinAgentHint: '可调整外观（图标、颜色）',
  customAgentHint: '完全可编辑，可删除',
  editAppearance: '编辑外观',
  createAgent: '创建新智能体',
  deleteAgentConfirm: '确定要删除此智能体吗？',
}
```

- [ ] **Step 2: 改造 AgentsManagePage.vue**

修改 `frontend/apps/main/src/pages/AgentsManagePage.vue`：

```vue
<script setup lang="ts">
import { onMounted } from 'vue'
import { showToast } from 'vant'
import { useRouter } from 'vue-router'
import { useAgentStore } from '@/stores/agent'
import { useI18n } from 'vue-i18n'

const router = useRouter()
const agentStore = useAgentStore()
const { t } = useI18n()

onMounted(async () => {
  await agentStore.loadAgents()
})

async function handleToggle(agent: Agent) {
  try {
    await agentStore.toggleAgentEnabled(agent.id, !agent.is_enabled)
    showToast({
      message: agent.is_enabled ? t('ai.agentDisabled') : t('ai.agentEnabled'),
      icon: agent.is_enabled ? '❌' : '✅',
    })
  } catch (e) {
    showToast({ message: t('common.operationFailed'), icon: '❌' })
  }
}

function handleEdit(agent: Agent) {
  if (agent.agent_type === 'system') {
    showToast({ message: t('ai.systemAgentNotEditable'), icon: '⚠️' })
    return
  }
  router.push(`/settings/ai/agents/${agent.id}/edit`)
}

async function handleDelete(agent: Agent) {
  if (!agent.can_delete) {
    showToast({ message: t('ai.agentCannotDelete'), icon: '⚠️' })
    return
  }
  // 使用 Vant Dialog 确认
  // ... 确认后调用 agentStore.removeAgent(agent.id)
}
</script>

<template>
  <div class="agents-manage-page">
    <!-- 系统智能体 -->
    <van-cell-group :title="t('ai.systemAgents')">
      <van-cell
        v-for="agent in agentStore.systemAgents"
        :key="agent.id"
        :title="`${agent.icon || '🤖'} ${agent.display_name}`"
        :label="agent.description || t('ai.systemAgentHint')"
      >
        <template #right-icon>
          <van-switch
            :model-value="agent.is_enabled"
            @update:model-value="handleToggle(agent)"
            size="24"
          />
        </template>
      </van-cell>
    </van-cell-group>

    <!-- 内置智能体 -->
    <van-cell-group :title="t('ai.builtinAgents')">
      <van-cell
        v-for="agent in agentStore.builtinAgents"
        :key="agent.id"
        :title="`${agent.icon || '🤖'} ${agent.display_name}`"
        :label="agent.description || t('ai.builtinAgentHint')"
        is-link
        @click="handleEdit(agent)"
      >
        <template #right-icon>
          <van-switch
            :model-value="agent.is_enabled"
            @update:model-value="handleToggle(agent)"
            size="24"
          />
        </template>
      </van-cell>
    </van-cell-group>

    <!-- 自定义智能体 -->
    <van-cell-group :title="t('ai.customAgents')">
      <van-cell
        v-for="agent in agentStore.customAgents"
        :key="agent.id"
        :title="`${agent.icon || '🤖'} ${agent.display_name}`"
        :label="agent.description || ''"
        is-link
        @click="handleEdit(agent)"
      >
        <template #right-icon>
          <van-button
            size="small"
            type="danger"
            plain
            @click.stop="handleDelete(agent)"
            :disabled="!agent.can_delete"
          >
            {{ t('common.delete') }}
          </van-button>
        </template>
      </van-cell>
    </van-cell-group>

    <!-- 创建按钮 -->
    <div class="create-bar">
      <van-button
        type="primary"
        block
        @click="router.push('/settings/ai/agents/new')"
      >
        {{ t('ai.createAgent') }}
      </van-button>
    </div>
  </div>
</template>

<style scoped>
.agents-manage-page {
  padding: 16px;
}
.create-bar {
  margin-top: 24px;
}
</style>
```

- [ ] **Step 3: Commit**

```bash
git add frontend/apps/main/src/pages/AgentsManagePage.vue frontend/apps/main/src/i18n/locales/zh-CN.ts
git commit -m "feat(frontend): redesign AgentsManagePage with agent_type grouping

- System agents: only enable/disable switch
- Builtin agents: edit appearance + enable/disable
- Custom agents: full edit + delete

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Task 15: 前端 AIHubPage 改造

**Files:**
- Modify: `frontend/apps/main/src/pages/AIHubPage.vue`

- [ ] **Step 1: 改造 AIHubPage 展示智能体卡片**

修改 `frontend/apps/main/src/pages/AIHubPage.vue` 的智能体网格部分：

```vue
<template>
  <!-- ... 其他部分保持不变 -->

  <!-- 智能体网格 -->
  <div class="agent-grid">
    <div
      v-for="agent in enabledAgents"
      :key="agent.id"
      class="agent-card"
      :style="{ backgroundColor: agent.color || '#f5f5f5' }"
      @click="handleAgentClick(agent)"
    >
      <div class="agent-icon">{{ agent.icon || '🤖' }}</div>
      <div class="agent-name">{{ agent.display_name }}</div>
      <div class="agent-desc">{{ agent.description }}</div>
    </div>
  </div>

  <!-- ... -->
</template>

<script setup lang="ts">
import { computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { useAgentStore } from '@/stores/agent'
import type { Agent } from '@/types/agent'

const router = useRouter()
const agentStore = useAgentStore()

// 只显示启用的智能体
const enabledAgents = computed(() => agentStore.enabledAgents)

onMounted(async () => {
  await agentStore.loadAgents()
})

function handleAgentClick(agent: Agent) {
  // 根据智能体类型路由到不同页面
  if (agent.agent_name === 'ai-assistant') {
    router.push('/ai/chat')
  } else if (agent.agent_name === 'time-machine') {
    router.push('/ai/time-machine')
  } else if (agent.skills.includes('report')) {
    router.push('/ai/report')
  } else if (agent.skills.includes('alerts')) {
    router.push('/ai/alerts')
  } else if (agent.skills.includes('allocation')) {
    router.push('/ai/allocation')
  } else if (agent.skills.includes('disposal')) {
    router.push('/ai/disposal')
  } else if (agent.skills.includes('liability')) {
    router.push('/ai/liability')
  } else if (agent.skills.includes('spending_leak')) {
    router.push('/ai/spending-leaks')
  } else {
    // 自定义智能体 -> agent stream 页面
    router.push(`/ai/agent/${agent.id}`)
  }
}
</script>

<style scoped>
.agent-grid {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 12px;
  padding: 16px;
}

.agent-card {
  border-radius: 12px;
  padding: 16px;
  display: flex;
  flex-direction: column;
  align-items: center;
  cursor: pointer;
  transition: transform 0.2s;
}

.agent-card:hover {
  transform: scale(1.05);
}

.agent-icon {
  font-size: 32px;
  margin-bottom: 8px;
}

.agent-name {
  font-size: 14px;
  font-weight: 500;
  text-align: center;
}

.agent-desc {
  font-size: 12px;
  color: #666;
  text-align: center;
  margin-top: 4px;
}
</style>
```

- [ ] **Step 2: Commit**

```bash
git add frontend/apps/main/src/pages/AIHubPage.vue
git commit -m "feat(frontend): redesign AIHubPage to show agent cards

- Display enabled agents as clickable cards
- Route to appropriate page based on agent skills

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Task 16: 简化 capabilityStore

**Files:**
- Modify: `frontend/apps/main/src/stores/capability.ts`

- [ ] **Step 1: 简化 capabilityStore 只加载 skill definitions**

修改 `frontend/apps/main/src/stores/capability.ts`：

```typescript
import { defineStore } from 'pinia'
import { ref } from 'vue'
import type { SkillDefinition } from '@/types/skillDefinition'
import { getSkillDefinitions } from '@/api/agent'

/**
 * 简化后的 capability store
 * 只用于加载 skill definitions（创建自定义智能体时选择能力）
 * 智能体管理已迁移到 agentStore
 */
export const useCapabilityStore = defineStore('capability', () => {
  const skillDefinitions = ref<SkillDefinition[]>([])

  async function loadSkillDefinitions() {
    const data = await getSkillDefinitions()
    skillDefinitions.value = data.items
  }

  return {
    skillDefinitions,
    loadSkillDefinitions,
  }
})
```

- [ ] **Step 2: Commit**

```bash
git add frontend/apps/main/src/stores/capability.ts
git commit -m "refactor(frontend): simplify capabilityStore to only load skill definitions

Agent management moved to agentStore.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Task 17: 集成测试验证

**Files:**
- 无文件修改，运行验证

- [ ] **Step 1: 启动 Backend 服务**

```bash
cd server/apps/backend
uv run uvicorn app.main:app --port 8000 &
```

- [ ] **Step 2: 测试 API endpoints**

```bash
# 测试 skill-definitions
curl http://localhost:8000/api/v1/ai/skill-definitions | jq

# 测试 agents（需要认证，使用测试 token）
curl -H "Authorization: Bearer <test_token>" http://localhost:8000/api/v1/ai/agents | jq
```

Expected:
- skill-definitions 返回 8 个能力定义
- agents 返回 system、builtin、custom 分组

- [ ] **Step 3: 启动 Frontend 服务**

```bash
cd frontend/apps/main
npm run dev &
```

- [ ] **Step 4: 手动 UI 测试**

1. 打开 http://localhost:5173/settings/ai/agents
2. 验证显示系统智能体、内置智能体、自定义智能体分组
3. 验证系统智能体只有启用/禁用开关
4. 验证内置智能体有编辑按钮
5. 验证自定义智能体有删除按钮

6. 打开 http://localhost:5173/ai
7. 验证显示智能体卡片网格
8. 点击卡片验证路由正确

- [ ] **Step 5: 前端类型检查**

```bash
cd frontend/apps/main
npm run typecheck
```

Expected: 无类型错误。

---

## Task 18: 最终 Commit 和总结

**Files:**
- 无文件修改，总结提交

- [ ] **Step 1: 检查所有更改已提交**

```bash
git status
```

Expected: 无未提交的更改。

- [ ] **Step 2: 查看完整提交历史**

```bash
git log --oneline -20
```

- [ ] **Step 3: 推送到远程（如需要）**

```bash
git push origin feat/agent-streaming
```

---

## 验收检查清单

- [ ] Backend: `skill_definitions` 表创建并 seed 8 条数据
- [ ] Backend: `ai_agents` 表有 `agent_type` 字段，无 `is_builtin`
- [ ] Backend: 系统智能体 `ai-assistant` 和 `time-machine` 存在
- [ ] Backend: `/ai/skill-definitions` endpoint 正常工作
- [ ] Backend: `/ai/agents` 返回分组结构
- [ ] Backend: 权限控制正确（system不可编辑，builtin部分可编辑，custom完全可编辑）
- [ ] Frontend: `agent_type` 类型定义正确
- [ ] Frontend: `AgentListGroupedResponse` 类型定义正确
- [ ] Frontend: `agentStore` 加载分组智能体
- [ ] Frontend: `AgentsManagePage` 分组展示并权限控制
- [ ] Frontend: `AIHubPage` 展示智能体卡片
- [ ] 所有测试通过