# 智能体管理统一模型设计（修订版）

**日期**: 2026-05-26
**状态**: 待审核
**范围**: AI功能智能体分类、管理、展示重构

---

## 问题背景

当前系统存在两个重叠的概念模型：

1. **Agents** (`ai_agents` 表) — 带有人设的系统提示包装器
2. **Skills/Capabilities** (`ai_skills` 表) — 执行单元

这导致以下问题：

- 设置页面智能体设置未正确显示内置智能体
- AI Hub页面展示概念混乱（展示能力而非智能体）
- `chat` 和 `time_machine` 作为"固定能力"而非智能体管理
- 用户心智模型不清晰：不知道该操作哪个概念
- 分类缺失：无法区分系统智能体、内置智能体、自定义智能体

---

## 设计目标

1. **统一用户心智模型**：一切皆智能体
2. **清晰的分类体系**：system（系统）、builtin（内置）、custom（自定义）
3. **正确的展示**：设置页面和 AI Hub 都展示智能体
4. **Skills 保持独立管理**：用户可独立配置 Skills，Agent 选择调用哪些

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
│   - tool_groups: ["mcp-group-1"] ← 可调用哪些 MCP 工具组 │
│   - soul_md: 系统提示（人设）                             │
└─────────────────────────────────────────────────────────┘
                        ↓ 选择关系
┌─────────────────────────────────────────────────────────┐
│ Skills层 (ai_skills - 单表设计)                          │
│                                                         │
│ family_id = 0 + skill_type = 'fixed'/'builtin'         │
│   → 全局能力定义（所有家庭共享）                          │
│                                                         │
│ family_id > 0                                          │
│   → 家庭级配置（启用/禁用状态）                           │
│                                                         │
│ family_id > 0 + skill_type = 'custom'                  │
│   → 家庭自定义能力                                       │
└─────────────────────────────────────────────────────────┘
```

---

## 数据模型

### Agent 表（重构 `ai_agents`）

```python
class AIAgent(Base):
    __tablename__ = "ai_agents"

    id: int  # snowflake
    family_id: int  # 0 = 全局/系统智能体

    agent_type: str  # "system" | "builtin" | "custom"  ← 新增

    agent_name: str
    display_name: str
    description: str
    icon: str  # emoji
    color: str  # hex

    soul_md: str | None  # 系统提示
    skills: list[str]  # 可调用的能力列表
    tool_groups: list[str]  # 可调用的 MCP 工具组

    model: str | None
    subagent_enabled: bool

    is_enabled: bool
    display_order: int

    created_by: int | None
    created_at: datetime
    updated_at: datetime
```

**移除字段**：`is_builtin` → 替换为 `agent_type`

**权限规则**：

| agent_type | can_edit | can_delete |
|------------|----------|------------|
| system | FALSE | FALSE |
| builtin | 部分（仅icon/color/skills/display_order） | FALSE |
| custom | TRUE | TRUE |

### Skills 表（ai_skills - 保持现有结构）

```python
class SkillRegistry(Base):
    __tablename__ = "ai_skills"

    id: int
    family_id: int  # 0 = 全局定义，>0 = 家庭配置
    skill_id: str
    skill_type: str  # "fixed" | "builtin" | "custom"

    name: str
    description: str
    icon: str
    color: str
    route: str
    input_mode: str
    placeholder: str
    examples: list

    is_enabled: bool
    display_order: int
    custom_prompt: str | None  # 仅 custom 类型使用

    created_by: int | None
    created_at: datetime
    updated_at: datetime
```

**查询逻辑**：

| 查询目的 | 条件 |
|----------|------|
| 全局能力定义 | `family_id = 0 AND skill_type IN ('fixed', 'builtin')` |
| 家庭可用能力 | `family_id = 0 OR family_id = {家庭ID}` |
| 家庭自定义能力 | `family_id = {家庭ID} AND skill_type = 'custom'` |

---

## Seed Data

### 系统智能体（agent_type="system"）

| agent_name | display_name | icon | skills | soul_md |
|------------|--------------|------|--------|---------|
| `ai-assistant` | AI助手 | 💬 | `["chat"]` | 有完整系统提示 |
| `time-machine` | 资产时光机 | ⏰ | `["time_machine"]` | 规则说明 |

### 内置智能体（agent_type="builtin"）

| agent_name | display_name | icon | skills |
|------------|--------------|------|--------|
| `asset-health-advisor` | 资产健康顾问 | 🏥 | `["report", "alerts", "allocation", "disposal"]` |
| `finance-optimizer` | 财务优化师 | 💰 | `["liability", "spending_leak"]` |

### 全局能力定义（ai_skills, family_id=0）

| skill_id | skill_type | name | icon |
|----------|------------|------|------|
| `chat` | fixed | AI问答 | 💬 |
| `time_machine` | fixed | 资产时光机 | ⏰ |
| `report` | builtin | 资产报告 | 📊 |
| `alerts` | builtin | 老化预警 | ⚠️ |
| `allocation` | builtin | 配置偏离 | 📐 |
| `disposal` | builtin | 闲置处置 | 🗑️ |
| `liability` | builtin | 负债分析 | 📉 |
| `spending_leak` | builtin | 消费漏洞 | 🔍 |

---

## 数据库迁移

### 步骤 1：修改 ai_agents 表

```sql
-- 添加 agent_type 字段
ALTER TABLE ai_agents ADD COLUMN agent_type VARCHAR(20) DEFAULT 'builtin';

-- 更新现有记录
UPDATE ai_agents SET agent_type = 'builtin' WHERE is_builtin = TRUE;
UPDATE ai_agents SET agent_type = 'custom' WHERE is_builtin = FALSE AND family_id != 0;

-- 移除 is_builtin 字段
ALTER TABLE ai_agents DROP COLUMN is_builtin;
```

### 步骤 2：插入系统智能体

```sql
INSERT INTO ai_agents (id, family_id, agent_type, agent_name, display_name, description, icon, color, soul_md, skills, is_enabled, display_order, created_at, updated_at) VALUES
    (--snowflake_id--, 0, 'system', 'ai-assistant', 'AI助手', '通用AI问答能力', '💬', '#3B82F6', --soul_md--, '["chat"]', TRUE, 0, NOW(), NOW()),
    (--snowflake_id--, 0, 'system', 'time-machine', '资产时光机', '基于规则的资产模拟计算', '⏰', '#8B5CF6', '纯规则计算', '["time_machine"]', TRUE, 10, NOW(), NOW());
```

### 步骤 3：调整内置智能体排序

```sql
UPDATE ai_agents SET display_order = 100 WHERE agent_name = 'asset-health-advisor';
UPDATE ai_agents SET display_order = 200 WHERE agent_name = 'finance-optimizer';
```

### 步骤 4：确保 ai_skills 全局定义存在

检查并补充 family_id=0 的全局能力定义记录。

---

## API 变化

### 后端 API（Backend `/api/v1/ai/`）

**Agents API**：

| Endpoint | 变化 |
|----------|------|
| `GET /agents` | 返回分组结构（system/builtin/custom） |
| `PUT /agents/{id}` | 根据 agent_type 限制可编辑字段 |
| `DELETE /agents/{id}` | 仅允许删除 custom 类型 |

**Skills API**（保持不变）：

| Endpoint | 说明 |
|----------|------|
| `GET /skills` | 返回家庭可用能力（全局定义 + 家庭配置） |
| `GET /skills/grouped` | 按 skill_type 分组返回 |
| `PUT /skills/{capability}` | 更新家庭级配置 |
| `POST /skills/custom` | 创建家庭自定义能力 |
| `DELETE /skills/custom/{id}` | 删除家庭自定义能力 |

---

## 前端 UI 变化

### 设置页面 —智能体管理 (`/settings/ai/agents`)

分组展示智能体：
- 系统智能体：仅启用/禁用
- 内置智能体：编辑外观 + 选择可调用能力
- 自定义智能体：完全可编辑，可删除

### 设置页面 —技能管理 (`/settings/ai/skills`)

保持独立入口，管理家庭级技能配置：
- 固定能力：仅启用/禁用
- 内置能力：配置 + 启用/禁用
- 自定义能力：完全可编辑，可删除

### AI Hub 页面 (`/ai`)

展示智能体卡片网格，点击进入对应功能页。

---

## 实现计划概要

### Phase 1：数据层改造

1. Alembic migration：ai_agents 添加 agent_type，移除 is_builtin，seed 系统智能体
2. 修改 Agent schemas
3. 修改 Agents router

### Phase 2：前端改造

1. 更新 Agent 类型定义
2. 更新 agentStore 分组存储
3. 改造 AgentsManagePage
4. 改造 AIHubPage
5. SkillsManagePage 保持独立

---

## 验收标准

1. ai_agents.agent_type 字段正确区分 system/builtin/custom
2. 系统智能体 ai-assistant 和 time-machine 存在
3. ai_skills 表功能正常，全局定义和家庭配置共存
4. 设置页面智能体管理分组展示
5. 设置页面技能管理独立功能正常
6. AI Hub 展示智能体卡片
7. 创建智能体时可选择调用哪些 Skills