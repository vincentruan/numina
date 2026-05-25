# 智能体管理统一模型设计

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
4. **简化技术架构**：Skills 变为能力标签而非独立管理实体

---

## 数据模型

### Agent 表（重构 `ai_agents`）

```python
class AIAgent(Base):
    __tablename__ = "ai_agents"

    # 主键和租户
    id: int  # snowflake
    family_id: int  # 0 = 全局/系统智能体

    # 分类
    agent_type: str  # "system" | "builtin" | "custom"

    # 基本信息
    agent_name: str  # slug: "ai-assistant", "time-machine"
    display_name: str  # "AI助手", "资产时光机"
    description: str  # 功能描述
    icon: str  # emoji: "💬", "⏰"
    color: str  # hex: "#3B82F6"

    # 核心
    soul_md: str | None  # 系统提示；system类型可为空
    skills: list[str]  # JSON数组：能力标签

    # 状态
    is_enabled: bool  # 启用/禁用
    display_order: int  # 排序

    # 元数据
    created_by: int | None  # 创建者ID（custom类型）
    created_at: datetime
    updated_at: datetime
```

**权限规则（计算字段）**：

| agent_type | can_edit | can_delete |
|------------|----------|------------|
| system | FALSE | FALSE |
| builtin | 部分（仅icon/color/display_order） | FALSE |
| custom | TRUE | TRUE |

### Skills 定义表（新建 `skill_definitions`）

```python
class SkillDefinition(Base):
    __tablename__ = "skill_definitions"

    skill_id: str  # "chat", "time_machine", "report", ...
    name: str  # "AI问答", "资产时光机"
    description: str  # 功能描述
    icon: str  # emoji
    color: str  # hex
    category: str  # "system" | "analysis" | "advisor"
    is_computation_only: bool  # TRUE for time_machine
```

**说明**：这是全局定义库，所有家庭共享。无 `family_id`、无 `is_enabled`、无 `custom_prompt`。

### 移除/废弃的表

- `ai_skills`（原 FamilySkillConfig）— 合并到 Agent 的 `skills` 字段
- `FamilySkillConfig` (agent service) — 废弃

---

## Seed Data

### 系统智能体（agent_type="system"）

| agent_name | display_name | icon | skills | soul_md | 说明 |
|------------|--------------|------|--------|---------|------|
| `ai-assistant` | AI助手 | 💬 | `["chat"]` | 有完整系统提示 | 通用问答 |
| `time-machine` | 资产时光机 | ⏰ | `["time_machine"]` | 规则说明而非LLM提示 | 纯计算，不调用LLM |

### 内置智能体（agent_type="builtin"）

| agent_name | display_name | icon | skills |
|------------|--------------|------|--------|
| `asset-health-advisor` | 资产健康顾问 | 🏥 | `["report", "alerts", "allocation", "disposal"]` |
| `finance-optimizer` | 财务优化师 | 💰 | `["liability", "spending_leak"]` |

### 能力定义库（skill_definitions）

| skill_id | name | icon | category | is_computation_only |
|----------|------|------|----------|---------------------|
| `chat` | AI问答 | 💬 | system | false |
| `time_machine` | 资产时光机 | ⏰ | system | true |
| `report` | 资产报告 | 📊 | analysis | false |
| `alerts` | 老化预警 | ⚠️ | analysis | false |
| `allocation` | 配置偏离 | 📐 | analysis | false |
| `disposal` | 闲置处置 | 🗑️ | advisor | false |
| `liability` | 负债分析 | 📉 | analysis | false |
| `spending_leak` | 消费漏洞 | 🔍 | advisor | false |

---

## 数据库迁移

### 步骤 1：创建 skill_definitions 表

```sql
CREATE TABLE skill_definitions (
    skill_id VARCHAR(50) PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    description TEXT,
    icon VARCHAR(10),
    color VARCHAR(10),
    category VARCHAR(20) DEFAULT 'analysis',
    is_computation_only BOOLEAN DEFAULT FALSE
);

INSERT INTO skill_definitions (skill_id, name, description, icon, color, category, is_computation_only) VALUES
    ('chat', 'AI问答', '通用AI问答能力，可回答关于净值、配置、负债、趋势等问题', '💬', '#3B82F6', 'system', FALSE),
    ('time_machine', '资产时光机', '资产模拟计算，包括假设分析、趋势预测、购买力计算', '⏰', '#8B5CF6', 'system', TRUE),
    ('report', '资产报告', '家庭资产健康报告，综合分析财务状况', '📊', '#10B981', 'analysis', FALSE),
    ('alerts', '老化预警', '资产老化预警分析，识别即将到期或高维护成本资产', '⚠️', '#F59E0B', 'analysis', FALSE),
    ('allocation', '配置偏离', '资产配置偏离分析，检查是否偏离目标配置', '📐', '#6366F1', 'analysis', FALSE),
    ('disposal', '闲置处置', '闲置资产处置建议，给出处置渠道和预估价值', '🗑️', '#EF4444', 'advisor', FALSE),
    ('liability', '负债分析', '家庭负债分析和还款策略建议', '📉', '#EC4899', 'analysis', FALSE),
    ('spending_leak', '消费漏洞', '消费漏洞识别，发现隐性浪费', '🔍', '#14B8A6', 'advisor', FALSE);
```

### 步骤 2：修改 ai_agents 表

```sql
-- 添加 agent_type 字段
ALTER TABLE ai_agents ADD COLUMN agent_type VARCHAR(20) DEFAULT 'builtin';

-- 更新现有记录类型
UPDATE ai_agents SET agent_type = 'builtin' WHERE is_builtin = TRUE;
UPDATE ai_agents SET agent_type = 'custom' WHERE is_builtin = FALSE AND family_id != 0;

-- 移除 is_builtin 字段（agent_type 替代）
ALTER TABLE ai_agents DROP COLUMN is_builtin;

-- 添加系统智能体
INSERT INTO ai_agents (id, family_id, agent_type, agent_name, display_name, description, icon, color, soul_md, skills, is_enabled, display_order, created_at, updated_at) VALUES
    (--snowflake_id--, 0, 'system', 'ai-assistant', 'AI助手', '通用AI问答能力，可回答关于净值、配置、负债、趋势等问题', '💬', '#3B82F6', --soul_md_content--, '["chat"]', TRUE, 0, NOW(), NOW()),
    (--snowflake_id--, 0, 'system', 'time-machine', '资产时光机', '基于规则的资产模拟计算，包括假设分析、趋势预测、购买力计算', '⏰', '#8B5CF6', '纯规则计算，无需LLM', '["time_machine"]', TRUE, 10, NOW(), NOW());

-- 调整内置智能体排序
UPDATE ai_agents SET display_order = 100 WHERE agent_name = 'asset-health-advisor';
UPDATE ai_agents SET display_order = 200 WHERE agent_name = 'finance-optimizer';
```

### 步骤 3：废弃 ai_skills 表

```sql
-- 数据已迁移到 Agent 的 skills 字段，删除表
DROP TABLE IF EXISTS ai_skills;
```

---

## API 变化

### 后端 API（Backend `/api/v1/ai/`）

**Agents API**：

| Endpoint | Method | 变化 |
|----------|--------|------|
| `/agents` | GET | 返回所有智能体，含 `agent_type` 字段 |
| `/agents/{id}` | GET | 无变化 |
| `/agents` | POST | 创建 `custom` 类型，需指定 `skills` 数组 |
| `/agents/{id}` | PUT | 根据 `agent_type` 限制可编辑字段 |
| `/agents/{id}` | DELETE | 仅允许删除 `custom` 类型 |
| `/agents/{id}/toggle` | PUT | 无变化 |

**新增 Skill Definitions API**：

| Endpoint | Method | 说明 |
|----------|--------|------|
| `/skill-definitions` | GET | 获取所有能力定义（创建自定义智能体时选择） |

**移除 Skills API**：

- `/skills` → 废弃
- `/skills/grouped` → 废弃
- `/skills/custom` → 废弃

### 代理服务 API（Agent Service）

| Endpoint | 变化 |
|----------|------|
| `/agent/{agent_id}/stream` | 主入口，保持不变 |
| `/chat/ask` | 内部重定向到 `ai-assistant` 智能体 |
| `/time_machine/...` | 保持独立（纯计算路径） |

---

## 前端 UI 变化

### 设置页面 —智能体管理 (`/settings/ai/agents`)

**列表结构**：

```
┌─ 系统智能体（不可删除）─────────────────┐
│ 💬 AI助手          [启用/禁用]          │
│ ⏰ 资产时光机        [启用/禁用]          │
├─ 内置智能体（可调整外观）───────────────┤
│ 🏥 资产健康顾问      [编辑外观] [启用]   │
│ 💰 财务优化师        [编辑外观] [启用]   │
├─ 自定义智能体─────────────────────────┤
│ (用户创建的智能体列表)                   │
│ [+ 创建新智能体]                         │
└─────────────────────────────────────────┘
```

**权限控制**：
- 系统智能体：仅显示启用/禁用开关
- 内置智能体：可编辑 icon、color、display_order
- 自定义智能体：完全可编辑，可删除

### AI Hub 页面 (`/ai`)

**改造**：展示智能体卡片网格而非能力卡片

```
┌────────────┬────────────┬────────────┐
│ 💬 AI助手  │ ⏰ 资产时光机│ 🏥 资产健康 │
│            │            │ 顾问        │
├────────────┼────────────┼────────────┤
│ 💰 财务    │ (自定义1)  │ (自定义2)   │
│ 优化师     │            │            │
└────────────┴────────────┴────────────┘
```

**交互**：点击卡片进入对应智能体功能页

### 移除/简化

- `/settings/ai/skills` 页面废弃或重定向到 `/settings/ai/agents`
- `capabilityStore` 简化为只加载 skill definitions（用于创建自定义智能体时选择能力）

---

## 实现计划

### Phase 1：数据层改造（后端优先）

1. 创建 Alembic migration
2. 重构 Backend schemas 和 CRUD
3. 新增 `/skill-definitions` endpoint

### Phase 2：Agent Service 改造

1. 简化 `capability_registry.py`
2. 调整 `orchestrator.py` 调用路径

### Phase 3：前端改造

1. 更新 `agentStore`
2. 改造 `AgentsManagePage.vue`
3. 改造 `AIHubPage.vue`
4. 简化/移除 `capabilityStore`

---

## 验收标准

1. 设置页面正确显示所有智能体（系统、内置、自定义）
2. AI Hub 页面展示智能体卡片而非能力卡片
3. 系统智能体不可删除、不可编辑核心字段
4. 内置智能体可调整外观（图标、颜色、排序）
5. 自定义智能体完全可编辑、可删除
6. 创建自定义智能体时可选择能力标签
7. 现有功能（AI问答、时光机、资产报告等）正常工作