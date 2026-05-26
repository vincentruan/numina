# 智能体管理统一模型实现计划（单表方案）

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 统一智能体分类管理（agent_type），Skills 保持单表独立管理（ai_skills），Agent 选择调用哪些 Skills。

**Architecture:** 
- `ai_agents`: 添加 `agent_type` 区分 system/builtin/custom，移除 `is_builtin`
- `ai_skills`: 保持现有结构，`family_id=0` 为全局定义，`family_id>0` 为家庭配置
- 用户入口是智能体，Skills 和 MCP 是智能体可使用的能力

**Tech Stack:** SQLAlchemy + Alembic (backend), Pinia (frontend), Vue 3 + TypeScript

---

## 架构关系图

```
┌─────────────────────────────────────────────────────────┐
│ 用户界面                                                  │
│   AI Hub → 智能体卡片 → 点击进入智能体功能页              │
│   Settings → 智能体管理 / 技能管理（独立入口）            │
└─────────────────────────────────────────────────────────┘
                        ↓
┌─────────────────────────────────────────────────────────┐
│ 智能体层 (ai_agents)                                     │
│   - agent_type: system | builtin | custom               │
│   - skills: ["report", "alerts"] ← 可调用哪些能力        │
│   - tool_groups: MCP工具组                               │
│   - soul_md: 系统提示                                    │
└─────────────────────────────────────────────────────────┘
                        ↓ 选择关系
┌─────────────────────────────────────────────────────────┐
│ Skills层 (ai_skills 单表)                                │
│                                                         │
│ family_id = 0 → 全局能力定义                             │
│ family_id > 0 → 家庭级配置                               │
│ skill_type = custom → 家庭自定义能力                     │
└─────────────────────────────────────────────────────────┘
```

---

## 文件结构

### Phase 1: 数据层改造（Backend）

| 文件 | 操作 | 说明 |
|------|------|------|
| `alembic/versions/xxx_unified_agent_model.py` | 创建 | Migration: agent_type字段、系统智能体seed |
| `models/ai_agent.py` | 修改 | 添加agent_type，移除is_builtin |
| `schemas/ai_agent.py` | 修改 | 添加agent_type，分组响应 |
| `routers/ai_agents.py` | 修改 | 分组返回、权限控制 |

### Phase 2: 前端改造

| 文件 | 操作 | 说明 |
|------|------|------|
| `types/agent.ts` | 修改 | 添加agent_type |
| `stores/agent.ts` | 修改 | 分组存储 |
| `pages/AgentsManagePage.vue` | 修改 | 分组展示、权限控制 |
| `pages/AIHubPage.vue` | 修改 | 智能体卡片 |
| `i18n/locales/zh-CN.ts` | 修改 | 新UI文本 |

---

## Task 1: 创建 Alembic Migration

**Files:**
- Create: `server/apps/backend/alembic/versions/<timestamp>_unified_agent_model.py`

- [ ] **Step 1: 生成 migration 文件**

```bash
cd server/apps/backend
uv run alembic revision -m "unified_agent_model"
```

- [ ] **Step 2: 编写 upgrade() 函数**

```python
def upgrade() -> None:
    # 1. 添加 agent_type 字段到 ai_agents
    op.add_column("ai_agents", sa.Column("agent_type", sa.String(20), server_default="builtin"))

    # 2. 更新现有记录的 agent_type
    op.execute("""
        UPDATE ai_agents SET agent_type = 'builtin' WHERE is_builtin = true;
        UPDATE ai_agents SET agent_type = 'custom' WHERE is_builtin = false AND family_id != 0;
    """)

    # 3. 移除 is_builtin 字段
    op.drop_column("ai_agents", "is_builtin")

    # 4. 插入系统智能体
    # ai-assistant
    op.execute("""
        INSERT INTO ai_agents (id, family_id, agent_type, agent_name, display_name, description, icon, color, soul_md, skills, is_enabled, display_order, created_at, updated_at)
        VALUES
            (-- snowflake_id --, 0, 'system', 'ai-assistant', 'AI助手', '通用AI问答能力，可回答关于净值、配置、负债、趋势等问题', '💬', '#3B82F6', 
             '你是Numina家庭资产管理系统的AI助手。你具备专业的财务分析能力，可以帮助用户回答关于家庭净值、资产配置、负债结构的问题。你的回答应该简洁、专业、易懂。使用中文回答。',
             '["chat"]', true, 0, NOW(), NOW());
    """)

    # time-machine
    op.execute("""
        INSERT INTO ai_agents (id, family_id, agent_type, agent_name, display_name, description, icon, color, soul_md, skills, is_enabled, display_order, created_at, updated_at)
        VALUES
            (-- snowflake_id --, 0, 'system', 'time-machine', '资产时光机', '基于规则的资产模拟计算，包括假设分析、趋势预测、购买力计算', '⏰', '#8B5CF6', 
             '纯规则计算，无需LLM。使用数值模拟进行资产预测分析。',
             '["time_machine"]', true, 10, NOW(), NOW());
    """)

    # 5. 调整内置智能体排序
    op.execute("""
        UPDATE ai_agents SET display_order = 100 WHERE agent_name = 'asset-health-advisor';
        UPDATE ai_agents SET display_order = 200 WHERE agent_name = 'finance-optimizer';
    """)

    # 注意：ai_skills 表保持不变，无需修改
```

- [ ] **Step 3: 编写 downgrade() 函数**

```python
def downgrade() -> None:
    # 1. 删除系统智能体
    op.execute("DELETE FROM ai_agents WHERE agent_type = 'system'")

    # 2. 恢复 is_builtin 字段
    op.add_column("ai_agents", sa.Column("is_builtin", sa.Boolean(), server_default="false"))
    op.execute("""
        UPDATE ai_agents SET is_builtin = true WHERE agent_type IN ('system', 'builtin');
        UPDATE ai_agents SET is_builtin = false WHERE agent_type = 'custom';
    """)

    # 3. 删除 agent_type 字段
    op.drop_column("ai_agents", "agent_type")
```

- [ ] **Step 4: Commit migration**

```bash
git add server/apps/backend/alembic/versions/<timestamp>_unified_agent_model.py
git commit -m "feat(migration): add agent_type to ai_agents, seed system agents

- Add agent_type field (system|builtin|custom)
- Remove is_builtin field
- Insert system agents: ai-assistant, time-machine
- Keep ai_skills table unchanged

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Task 2: 修改 AIAgent Model

**Files:**
- Modify: `server/apps/backend/app/models/ai_agent.py`

- [ ] **Step 1: 添加 agent_type，移除 is_builtin**

```python
# 在 ai_agent.py 中找到 is_builtin 字段并替换
# 原：
#     is_builtin = Column(Boolean, default=False)

# 改为：
from sqlalchemy import String
...
    agent_type = Column(String(20), default="builtin")  # system | builtin | custom
```

- [ ] **Step 2: Commit**

```bash
git add server/apps/backend/app/models/ai_agent.py
git commit -m "refactor(models): replace is_builtin with agent_type

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Task 3: 修改 Agent Schemas

**Files:**
- Modify: `server/apps/backend/app/schemas/ai_agent.py`

- [ ] **Step 1: 添加 agent_type 到 AgentResponse**

```python
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
```

- [ ] **Step 2: 添加分组响应结构**

```python
class AgentListGroupedResponse(BaseModel):
    """智能体分组响应"""
    system: list[AgentResponse] = []
    builtin: list[AgentResponse] = []
    custom: list[AgentResponse] = []
    total: int = 0
```

- [ ] **Step 3: Commit**

```bash
git add server/apps/backend/app/schemas/ai_agent.py
git commit -m "refactor(schemas): add agent_type and grouped response

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Task 4: 修改 Agents Router

**Files:**
- Modify: `server/apps/backend/app/routers/ai_agents.py`

- [ ] **Step 1: 修改 list_agents 返回分组结构**

```python
@router.get("", response_model=AgentListGroupedResponse)
async def list_agents(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> AgentListGroupedResponse:
    """列出所有智能体，按 agent_type 分组"""
    family_id = current_user.family_id

    result = await db.execute(
        select(AIAgent)
        .where(or_(AIAgent.family_id == 0, AIAgent.family_id == family_id))
        .order_by(AIAgent.agent_type, AIAgent.display_order)
    )
    agents = result.scalars().all()

    system_agents = []
    builtin_agents = []
    custom_agents = []

    for agent in agents:
        agent_resp = AgentResponse.model_validate(agent)
        if agent.agent_type == "system":
            agent_resp.can_edit = False
            agent_resp.can_delete = False
            system_agents.append(agent_resp)
        elif agent.agent_type == "builtin":
            agent_resp.can_edit = True
            agent_resp.can_delete = False
            builtin_agents.append(agent_resp)
        else:
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

- [ ] **Step 2: 修改 update_agent 权限**

```python
@router.put("/{id}", response_model=AgentResponse)
async def update_agent(
    id: int,
    payload: AgentUpdateRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> AgentResponse:
    agent = await db.get(AIAgent, id)
    if not agent:
        raise HTTPException(status_code=404, detail="智能体不存在")

    if agent.agent_type == "system":
        raise HTTPException(status_code=403, detail="系统智能体不可修改")

    if agent.agent_type == "builtin":
        # 仅允许修改外观和 skills
        if any([payload.soul_md, payload.model, payload.subagent_enabled, payload.tool_groups]):
            raise HTTPException(status_code=403, detail="内置智能体仅可修改外观和调用能力")

    if agent.agent_type == "custom" and agent.family_id != current_user.family_id:
        raise HTTPException(status_code=403, detail="无权修改此智能体")

    update_data = payload.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(agent, key, value)

    await db.commit()
    await db.refresh(agent)
    return AgentResponse.model_validate(agent)
```

- [ ] **Step 3: 修改 delete_agent 权限**

```python
@router.delete("/{id}")
async def delete_agent(
    id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    agent = await db.get(AIAgent, id)
    if not agent:
        raise HTTPException(status_code=404, detail="智能体不存在")

    if agent.agent_type in ("system", "builtin"):
        raise HTTPException(status_code=403, detail="系统智能体和内置智能体不可删除")

    if agent.family_id != current_user.family_id:
        raise HTTPException(status_code=403, detail="无权删除此智能体")

    await db.delete(agent)
    await db.commit()
    return {"message": "智能体已删除"}
```

- [ ] **Step 4: Commit**

```bash
git add server/apps/backend/app/routers/ai_agents.py
git commit -m "refactor(router): agents grouped response with permissions

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Task 5: 运行 Migration 验证

- [ ] **Step 1: 运行 upgrade**

```bash
cd server/apps/backend
uv run alembic upgrade head
```

- [ ] **Step 2: 验证数据**

```bash
uv run python -c "
from sqlalchemy import create_engine, text
from apps.backend.app.config import settings

engine = create_engine(settings.database_url)
with engine.connect() as conn:
    result = conn.execute(text('SELECT agent_type, COUNT(*) FROM ai_agents GROUP BY agent_type'))
    print('ai_agents by type:', list(result.fetchall()))

    result = conn.execute(text('SELECT agent_name FROM ai_agents WHERE agent_type=\"system\"'))
    print('system agents:', list(result.fetchall()))
"
```

Expected:
- agent_type counts: [('system', 2), ('builtin', 2), ('custom', N)]
- system agents: ['ai-assistant', 'time-machine']

---

## Task 6: 前端类型更新

**Files:**
- Modify: `frontend/apps/main/src/types/agent.ts`

- [ ] **Step 1: 添加 agent_type**

```typescript
export interface Agent {
  id: string
  family_id: number
  agent_type: 'system' | 'builtin' | 'custom'
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

export interface AgentListGroupedResponse {
  system: Agent[]
  builtin: Agent[]
  custom: Agent[]
  total: number
}
```

- [ ] **Step 2: Commit**

```bash
git add frontend/apps/main/src/types/agent.ts
git commit -m "feat(frontend): add agent_type to Agent type

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Task 7: 前端 API 更新

**Files:**
- Modify: `frontend/apps/main/src/api/agent.ts`

- [ ] **Step 1: 更新 getAgents**

```typescript
export async function getAgents(): Promise<AgentListGroupedResponse> {
  const resp = await apiClient.get('/ai/agents')
  return resp.data as AgentListGroupedResponse
}
```

- [ ] **Step 2: Commit**

```bash
git add frontend/apps/main/src/api/agent.ts
git commit -m "refactor(frontend): update getAgents for grouped response

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Task 8: 前端 AgentStore 更新

**Files:**
- Modify: `frontend/apps/main/src/stores/agent.ts`

- [ ] **Step 1: 分组存储**

```typescript
import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import type { Agent, AgentListGroupedResponse } from '@/types/agent'
import { getAgents, createAgent, updateAgent, deleteAgent, toggleAgent } from '@/api/agent'

export const useAgentStore = defineStore('agent', () => {
  const systemAgents = ref<Agent[]>([])
  const builtinAgents = ref<Agent[]>([])
  const customAgents = ref<Agent[]>([])

  const allAgents = computed(() => [...systemAgents.value, ...builtinAgents.value, ...customAgents.value])
  const enabledAgents = computed(() => allAgents.value.filter(a => a.is_enabled))

  async function loadAgents() {
    const data = await getAgents()
    systemAgents.value = data.system
    builtinAgents.value = data.builtin
    customAgents.value = data.custom
  }

  async function toggleAgentEnabled(id: string, enabled: boolean) {
    await toggleAgent(id, enabled)
    for (const list of [systemAgents, builtinAgents, customAgents]) {
      const idx = list.value.findIndex(a => a.id === id)
      if (idx !== -1) {
        list.value[idx].is_enabled = enabled
        break
      }
    }
  }

  async function removeAgent(id: string) {
    await deleteAgent(id)
    customAgents.value = customAgents.value.filter(a => a.id !== id)
  }

  async function editAgent(id: string, payload: AgentUpdatePayload) {
    const agent = await updateAgent(id, payload)
    for (const list of [systemAgents, builtinAgents, customAgents]) {
      const idx = list.value.findIndex(a => a.id === id)
      if (idx !== -1) {
        list.value[idx] = agent
        break
      }
    }
  }

  return {
    systemAgents,
    builtinAgents,
    customAgents,
    allAgents,
    enabledAgents,
    loadAgents,
    toggleAgentEnabled,
    removeAgent,
    editAgent,
  }
})
```

- [ ] **Step 2: Commit**

```bash
git add frontend/apps/main/src/stores/agent.ts
git commit -m "refactor(frontend): agentStore with grouped agents

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Task 9: 前端 AgentsManagePage 改造

**Files:**
- Modify: `frontend/apps/main/src/pages/AgentsManagePage.vue`
- Modify: `frontend/apps/main/src/i18n/locales/zh-CN.ts`

- [ ] **Step 1: 添加 i18n**

```typescript
ai: {
  systemAgents: '系统智能体',
  builtinAgents: '内置智能体',
  customAgents: '自定义智能体',
  systemAgentHint: '不可删除，仅可启用/禁用',
  builtinAgentHint: '可调整外观和调用能力',
  customAgentHint: '完全可编辑，可删除',
  createAgent: '创建新智能体',
}
```

- [ ] **Step 2: 改造页面**

关键点：
- 系统智能体分组：仅显示启用/禁用开关
- 内置智能体分组：编辑按钮 + 开关
- 自定义智能体分组：编辑 + 删除按钮

- [ ] **Step 3: Commit**

```bash
git add frontend/apps/main/src/pages/AgentsManagePage.vue frontend/apps/main/src/i18n/locales/zh-CN.ts
git commit -m "feat(frontend): AgentsManagePage with agent_type grouping

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Task 10: 前端 AIHubPage 改造

**Files:**
- Modify: `frontend/apps/main/src/pages/AIHubPage.vue`

- [ ] **Step 1: 展示智能体卡片**

展示 enabledAgents 作为卡片网格，点击路由到对应功能页。

- [ ] **Step 2: Commit**

```bash
git add frontend/apps/main/src/pages/AIHubPage.vue
git commit -m "feat(frontend): AIHubPage with agent cards

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Task 11: 集成测试

- [ ] **Step 1: Backend API 测试**

```bash
curl -H "Authorization: Bearer <token>" http://localhost:8000/api/v1/ai/agents | jq
```

Expected: 返回 { system: [...], builtin: [...], custom: [...], total: N }

- [ ] **Step 2: Frontend UI 测试**

1. `/settings/ai/agents` - 分组展示正确
2. `/settings/ai/skills` - Skills 独立管理正常
3. `/ai` - 智能体卡片展示

- [ ] **Step 3: 类型检查**

```bash
cd frontend/apps/main
npm run typecheck
```

---

## 验收检查清单

- [ ] ai_agents.agent_type 字段正确
- [ ] 系统智能体 ai-assistant、time-machine 存在
- [ ] ai_skills 表功能正常
- [ ] /ai/agents 返回分组结构
- [ ] 前端智能体管理页面分组展示
- [ ] 前端技能管理页面独立功能
- [ ] AI Hub 展示智能体卡片
- [ ] 权限控制正确