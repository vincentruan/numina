# AI 技能管理系统设计

## 概述

将 AI 能力分为三类：固定能力、内置技能、自定义技能。用户可在设置-技能管理中查看/启用/禁用/新增技能。内置技能只读，自定义技能可编辑。技能按家庭租户隔离。

## 核心设计原则

1. **DeerFlow 文件加载机制不变** - 继续扫描 `SKILL.md` 文件，不做改动
2. **数据库表仅用于配置管理** - 启用/禁用状态、排序、自定义 prompt override
3. **元数据存储在数据库** - 不使用额外的 metadata.json 文件
4. **技能发现时过滤** - CapabilityRegistry 查询 skill_registry 表，过滤 is_enabled=false 的技能

## 能力分类

| 类型 | skill_type | 特性 | 示例 |
|------|------------|------|------|
| 固定能力 | `fixed` | 不可禁用、不可编辑、排序固定在最前 | AI问答、资产时光机 |
| 内置技能 | `builtin` | 可禁用、可调整排序、只读 | 资产预警、资产体检、配置分析等 |
| 自定义技能 | `custom` | 可禁用、可调整排序、可编辑、可删除 | 用户创建的技能 |

## 目录结构设计

### 新结构

```
skills/
├── builtin/                          # 内置技能（只读，全局共享）
│   ├── alerts/
│   │   └── SKILL.md                  # DeerFlow 格式（元数据 + prompt）
│   ├── allocation/
│   │   └── SKILL.md
│   ├── chat/
│   │   └── SKILL.md
│   ├── disposal/
│   │   └── SKILL.md
│   ├── liability/
│   │   └── SKILL.md
│   ├── report/
│   │   └── SKILL.md
│   ├── spending_leak/
│   │   └── SKILL.md
│   └── time_machine/
│   │   └── SKILL.md
│
├── custom/                           # 用户自定义技能（按家庭隔离）
│   ├── {family_id}/                  # 家庭租户目录
│   │   ├── my_analysis/
│   │   │   └── SKILL.md              # 家庭专属技能
│   │   ├── my_budget_planner/
│   │   │   └── SKILL.md
│   │   └── ...
│   ├── {another_family_id}/
│   │   └── ...
```

### DeerFlow 配置调整

```yaml
# deerflow_config/base/config.yaml
skills:
  paths:
    - /app/apps/agent/skills/builtin
    # custom/{family_id}/ 动态注入，由 family_adapter_cache 生成临时配置
```

### SKILL.md 文件格式（统一格式）

```markdown
---
name: alerts
description: 资产老化预警分析
trigger_phrases:
  - 老化预警
  - 资产到期
allowed-tools: []
thinking: false
---

## 适用场景
家庭资产老化预警分析...

## 输出格式要求
...

## 边界限制
...
```

**frontmatter 字段**：
- `name`: 技能名称
- `description`: 技能描述
- `trigger_phrases`: 触发短语列表
- `allowed-tools`: 可用工具列表
- `thinking`: 是否启用深度思考
- `mcp_tools`: MCP 工具列表（可选）

## 数据库设计

### skill_registry 表（扩展）

```sql
CREATE TABLE skill_registry (
    id              BIGINT PRIMARY KEY,
    family_id       BIGINT NOT NULL,
    skill_id        VARCHAR(64) NOT NULL,
    skill_type      VARCHAR(16) NOT NULL,  -- 'fixed' | 'builtin' | 'custom'

    -- UI 元数据（从 SKILL.md frontmatter 映射，仅 custom 类型存储）
    name            VARCHAR(128),
    description     VARCHAR(512),
    icon            VARCHAR(32),           -- emoji
    color           VARCHAR(16),
    route           VARCHAR(64),
    input_mode      VARCHAR(16) DEFAULT 'trigger',
    placeholder     VARCHAR(256),
    examples        JSONB,

    -- 配置管理
    is_enabled      BOOLEAN DEFAULT TRUE,
    display_order   INTEGER DEFAULT 0,
    custom_prompt   TEXT,                  -- 仅用于覆盖内置技能 prompt

    -- 审计
    created_at      TIMESTAMP DEFAULT NOW(),
    updated_at      TIMESTAMP DEFAULT NOW(),
    created_by      BIGINT,

    UNIQUE(family_id, skill_id)
);

CREATE INDEX idx_skill_registry_family ON skill_registry(family_id);
CREATE INDEX idx_skill_registry_order ON skill_registry(family_id, display_order);
```

### skill_type 与存储策略

| skill_type | 元数据来源 | prompt 来源 | 文件位置 |
|------------|-----------|-------------|---------|
| `fixed` | 不存数据库（硬编码前端 i18n） | `skills/builtin/{id}/SKILL.md` | 固定位置 |
| `builtin` | 从 `SKILL.md` frontmatter 解析，存数据库用于排序 | `skills/builtin/{id}/SKILL.md` | 固定位置 |
| `custom` | 用户表单输入，存数据库 | `skills/custom/{family_id}/{id}/SKILL.md` | 家庭目录 |

### 初始化 display_order

```
fixed:
  - chat: 0
  - time_machine: 1

builtin (默认排序):
  - report: 100
  - alerts: 101
  - allocation: 102
  - disposal: 103
  - liability: 104
  - spending_leak: 105

custom: 从 200 开始递增
```

## 技能加载机制

### CapabilityRegistry 扩展逻辑

```python
class CapabilityRegistry:
    def list_capabilities_for_family(self, family_id: int) -> list[CapabilityDefinition]:
        # 1. 从 backend API 获取家庭的 skill_registry 配置
        db_configs = self.backend_client.get_skill_registry(family_id)

        # 2. 扫描 builtin 目录，合并数据库配置
        builtin_skills = []
        for skill_dir in SKILLS_DIR / "builtin".glob("*"):
            skill_file = skill_dir / "SKILL.md"
            if skill_file.exists():
                meta = self._parse_skill_md(skill_file)
                db_record = db_configs.find(skill_dir.name)
                # 过滤禁用的技能
                if db_record and not db_record.is_enabled:
                    continue
                skill = CapabilityDefinition(
                    id=skill_dir.name,
                    skill_type='builtin',
                    name=meta['name'],
                    description=meta['description'],
                    display_order=db_record.display_order if db_record else default_order,
                    is_enabled=db_record.is_enabled if db_record else True,
                )
                builtin_skills.append(skill)

        # 3. 扫描 custom/{family_id} 目录
        custom_skills = []
        custom_dir = SKILLS_DIR / "custom" / str(family_id)
        if custom_dir.exists():
            for skill_dir in custom_dir.glob("*"):
                skill_file = skill_dir / "SKILL.md"
                if skill_file.exists():
                    meta = self._parse_skill_md(skill_file)
                    db_record = db_configs.find(skill_dir.name)
                    if db_record and not db_record.is_enabled:
                        continue
                    skill = CapabilityDefinition(
                        id=skill_dir.name,
                        skill_type='custom',
                        name=db_record.name or meta['name'],
                        description=db_record.description or meta['description'],
                        display_order=db_record.display_order,
                        is_enabled=db_record.is_enabled,
                    )
                    custom_skills.append(skill)

        # 4. 固定能力（硬编码）
        fixed_skills = [
            CapabilityDefinition(id='chat', skill_type='fixed', display_order=0),
            CapabilityDefinition(id='time_machine', skill_type='fixed', display_order=1),
        ]

        # 5. 按 display_order 排序返回
        return sorted(fixed_skills + builtin_skills + custom_skills, key=lambda s: s.display_order)
```

### DeerFlow 执行机制（不变）

DeerFlow harness 继续按原有逻辑：
1. 扫描 `skills.paths` 配置的目录
2. 加载所有 `SKILL.md` 文件
3. 根据 `trigger_phrases` 或 `[SKILL:{name}]` 触发执行

**关键**：禁用的技能虽然文件存在，但 CapabilityRegistry 不返回给前端，用户无法触发调用。

## API 设计

### Backend 服务

| 方法 | 路径 | 说明 | 权限 |
|------|------|------|------|
| GET | `/ai/skills` | 获取当前家庭的技能列表（合并 builtin+custom） | member/admin |
| GET | `/ai/skills/{skill_id}` | 获取单个技能详情 | member/admin |
| POST | `/ai/skills` | 创建自定义技能 | owner only |
| PUT | `/ai/skills/{skill_id}` | 更新自定义技能 | owner only |
| DELETE | `/ai/skills/{skill_id}` | 删除自定义技能 | owner only |
| PUT | `/ai/skills/{skill_id}/toggle` | 启用/禁用技能 | owner only |
| PUT | `/ai/skills/reorder` | 批量调整排序 | owner only |

### 响应结构

```typescript
interface SkillListResponse {
  fixed: SkillDefinition[];      // 固定能力
  builtin: SkillDefinition[];    // 内置技能（已过滤 is_enabled=false）
  custom: SkillDefinition[];     // 自定义技能（已过滤 is_enabled=false）
}

interface SkillDefinition {
  id: string;
  skill_type: 'fixed' | 'builtin' | 'custom';
  name?: string;                 // 仅 custom 类型使用数据库值
  description?: string;          // 仅 custom 类型使用数据库值
  icon: string;
  color: string;
  route: string | null;
  input_mode: 'free_text' | 'trigger';
  examples?: string[];
  is_enabled: boolean;
  display_order: number;
  can_edit: boolean;             // 前端判断：只有 custom 可编辑
  can_delete: boolean;           // 前端判断：只有 custom 可删除
}
```

## 前端设计

### AI Hub 页面展示结构

```
固定能力区域（无标题，固定显示）
├── 💬 AI问答
└── ⏰ 资产时光机

系统能力区域（标题：系统能力）
├── 技能卡片（按 display_order 排序）
└── 禁用的技能不展示（已过滤）

自定义能力区域（标题：自定义能力）
├── 用户创建的技能（按 display_order 排序）
└── 禁用的技能不展示（已过滤）
```

### 技能管理页面结构

```
技能管理
├── 固定能力（只读展示，无开关）
│   ├── 💬 AI问答 - [查看详情]
│   └── ⏰ 资产时光机 - [查看详情]
│
├── 内置技能（可开关，只读）
│   ├── 🔔 资产老化预警 [开关] [查看详情]
│   ├── 📊 家庭资产体检 [开关] [查看详情]
│   └── ...（拖拽排序）
│
├── 自定义技能（可开关，可编辑/删除）
│   ├── 📈 我的分析 [开关] [编辑] [删除]
│   └── ...（拖拽排序）
│
└── [+ 新增技能] 按钮
```

### 新增技能表单

| 字段 | 类型 | 必填 | 校验规则 |
|------|------|------|---------|
| 技能 ID | 文本输入 | 是 | 小写字母/数字/下划线/连字符，不能数字开头，不能与内置冲突，家庭内唯一，即时校验 |
| 技能名称 | 文本输入 | 是 | 最多 128 字符 |
| 描述 | 文本输入 | 否 | 最多 512 字符 |
| 图标 | Emoji 选择器 | 是 | 预设 20 个常用 emoji |
| 颜色 | 颜色选择器 | 是 | 预设 8 种颜色 |
| 输入模式 | 单选 | 是 | `trigger` / `free_text` |
| 示例问题 | 多文本输入 | 否 | 最多 5 个，每个最多 100 字符 |
| 提示词内容 | 多行文本 | 是 | Markdown 格式，有模板提示 |

### 技能 ID 即时校验

```typescript
const validateSkillId = (id: string): { valid: boolean; error?: string } => {
  // 格式校验
  if (!/^[a-z][a-z0-9_-]*$/.test(id)) {
    return { valid: false, error: 'ID 只能包含小写字母、数字、下划线、连字符，且不能数字开头' }
  }
  if (id.length > 64) {
    return { valid: false, error: 'ID 长度不能超过 64 字符' }
  }
  // 内置冲突校验
  const builtinIds = ['alerts', 'allocation', 'chat', 'disposal', 'liability', 'report', 'spending_leak', 'time_machine']
  if (builtinIds.includes(id)) {
    return { valid: false, error: '该 ID 与内置技能冲突' }
  }
  return { valid: true }
}
```

## i18n 设计

内置技能（fixed + builtin）通过 i18n 映射显示文本；自定义技能直接使用用户输入的原始文本。

### zh-CN.ts 结构

```typescript
skills: {
  title: '技能管理',
  builtinSkills: '内置技能',
  customSkills: '自定义技能',
  fixedSkills: '固定能力',

  capability: {
    chat: {
      name: '💬 智能问答',
      description: '回答关于净资产、资产配置、负债、趋势等问题',
    },
    time_machine: {
      name: '⏰ 资产时光机',
      description: '模拟 What-if 消费场景和财务推演',
    },
    alerts: {
      name: '🔔 资产老化预警',
      description: '扫描即将到期或老化的资产，给出处置建议',
    },
    allocation: {
      name: '⚖️ 资产配置分析',
      description: '评估当前资产配置与目标配置的偏差，给出调整建议',
    },
    report: {
      name: '📊 家庭资产体检',
      description: '对家庭整体资产状况进行结构化分析',
    },
    disposal: {
      name: '🗑️ 闲置资产处置',
      description: '识别低效闲置资产，给出处置渠道和建议',
    },
    liability: {
      name: '💳 负债健康分析',
      description: '分析负债结构、还款压力和利率风险',
    },
    spending_leak: {
      name: '🔍 消费漏洞扫描',
      description: '识别低效消费和资产浪费，给出节省建议',
    },
  },
}
```

### 前端显示逻辑

```vue
<!-- 内置技能：使用 i18n -->
<span v-if="cap.skill_type !== 'custom'" class="feature-title">
  {{ t(`skills.capability.${cap.id}.name`) }}
</span>
<span v-if="cap.skill_type !== 'custom'" class="feature-desc">
  {{ t(`skills.capability.${cap.id}.description`) }}
</span>

<!-- 自定义技能：使用数据库值 -->
<span v-else class="feature-title">{{ cap.name }}</span>
<span v-else class="feature-desc">{{ cap.description }}</span>
```

## 文件迁移计划

### 从旧结构迁移

| 旧路径 | 新路径 | 操作 |
|--------|--------|------|
| `skills/*.md` (alerts.md 等) | 删除 | 元数据合并到 builtin/*/SKILL.md |
| `skills/custom/alerts/SKILL.md` | `skills/builtin/alerts/SKILL.md` | 移动到 builtin 目录 |
| `skills/custom/family-asset-checkup/SKILL.md` | 删除或保留为示例 | 非内置技能，清理或归档 |

### 迁移脚本

```python
# scripts/migrate_skills.py
import shutil
from pathlib import Path

OLD_SKILLS_DIR = Path("skills")
NEW_BUILTIN_DIR = Path("skills/builtin")

BUILTIN_SKILLS = ["alerts", "allocation", "chat", "disposal", "liability", "report", "spending_leak", "time_machine"]

for skill_id in BUILTIN_SKILLS:
    # 创建新目录
    new_dir = NEW_BUILTIN_DIR / skill_id
    new_dir.mkdir(parents=True, exist_ok=True)

    # 移动 SKILL.md
    old_file = OLD_SKILLS_DIR / "custom" / skill_id / "SKILL.md"
    if old_file.exists():
        shutil.move(str(old_file), str(new_dir / "SKILL.md"))

    # 删除旧元数据文件
    old_meta = OLD_SKILLS_DIR / f"{skill_id}.md"
    if old_meta.exists():
        old_meta.unlink()

# 清理空目录
shutil.rmtree(OLD_SKILLS_DIR / "custom", ignore_errors=True)
```

## 实现优先级

1. **P0 - 目录迁移与数据初始化**
   - 迁移 skill 目录结构到 builtin/
   - 创建 skill_registry 数据库表
   - 初始化 builtin 技能的数据库记录

2. **P1 - Backend API 实现**
   - 扩展 `ai_skills.py` router 支持 custom 技能 CRUD
   - 实现 skill 文件写入 `skills/custom/{family_id}/{id}/SKILL.md`

3. **P2 - CapabilityRegistry 扩展**
   - 合并扫描 builtin + custom/{family_id}
   - 查询数据库过滤 is_enabled=false

4. **P3 - 前端改造**
   - AIHubPage 三段展示
   - SkillsManagePage 改造（排序、新增、编辑、删除）
   - i18n 配置