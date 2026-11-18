---
title: "feat: Teach Back 扩展 — 小数、百分比、分数乘法"
type: feat
status: active
date: 2026-11-17
origin: docs/brainstorms/2026-11-17-teachback-expansion-requirements.md
---

# Teach Back 扩展 — 小数、百分比、分数乘法

## Overview

将 Teach Back 功能从 3 个分数试点 topic 扩展到 6 个 topic（原 3 个 + 新增 3 个：小数位值、百分比、分数乘法），同时将 topic 开关从硬编码迁移到环境变量配置。

---

## Problem Frame

当前 Teach Back 仅覆盖分数概念，无法验证"教 AI"模式在更广泛数学概念中的效果。需要将功能扩展到小数、百分比、分数乘法，形成从分数到小数到百分比的自然进阶学习路径。同时将硬编码的 `_PILOT_TOPIC_KEYS` 迁移到环境变量，使未来扩展无需改代码。

(see origin: docs/brainstorms/2026-11-17-teachback-expansion-requirements.md)

---

## Requirements Trace

- R1. 为 3 个新 topic 创建 TopicConfusion seed 数据（每个 2-3 个 confusion）
- R2. 每个 confusion 包含 confusion_text, confusion_text_zh, rubric, expected_expression
- R3. Confusion 覆盖最常见 misconceptions
- R4. `_PILOT_TOPIC_KEYS` 迁移到环境变量 `TEACH_BACK_ENABLED_TOPIC_KEYS`
- R5. 环境变量值为逗号分隔的 topic_key 列表
- R6. 未设置环境变量时默认启用全部 6 个 topic
- R7. 配置在 backend `AppSettings` 中
- R8. SymPy grading 支持小数、百分比、分数乘法表达式
- R9. 扩展 regex patterns 支持新表达式类型
- R10. seed 脚本测试覆盖
- R11. grading 扩展测试覆盖
- R12. 更新 seed 脚本 docstring
- R13. 记录环境变量配置方式

---

## Scope Boundaries

- 不修改前端 UI
- 不修改 Smart Tutor SKILL.md 的 teach-back 流程
- 不新增数据库 migration
- 不添加 admin 管理界面
- 不扩展 SymPy 到非数学 topic

---

## Context & Research

### Relevant Code and Patterns

- `server/scripts/seed_teach_back_confusions.py` — 现有 seed 脚本，按 topic_key 字典组织 confusion 数据
- `server/apps/backend/app/services/learning/teach_back_service.py` — `_PILOT_TOPIC_KEYS` 硬编码位置
- `server/apps/backend/app/services/learning/teach_back_grading.py` — SymPy expression extractor 和 grader
- `server/apps/backend/app/config.py` — `AppSettings` (pydantic-settings)，环境变量配置入口
- `server/tests/backend/scripts/test_seed_teach_back_confusions.py` — 现有 seed 脚本测试

### Institutional Learnings

- 无特定 docs/solutions/ 相关条目 — 这是一个数据扩展 + 配置重构任务

---

## Key Technical Decisions

- **环境变量命名**: `TEACH_BACK_ENABLED_TOPIC_KEYS`，逗号分隔。与现有 `TEACH_BACK_*` 命名风格一致。
- **默认值策略**: Python 代码中定义 `DEFAULT_TEACH_BACK_TOPIC_KEYS` 常量包含全部 6 个 key，环境变量未设置时使用默认值。
- **SymPy 小数支持**: 小数表达式（如 `0.25`）SymPy 原生支持 `sympify`，无需特殊处理；主要需扩展 regex extractor 以匹配小数格式。
- **SymPy 百分比支持**: 百分比（如 `25%`）需转换为分数再比较（`25% → 25/100 → 1/4`）。在 extractor 层处理，而非在 grader 层。

---

## Implementation Units

- U1. **迁移 topic 白名单到环境变量配置**

**Goal:** 将 `_PILOT_TOPIC_KEYS` 从硬编码 frozenset 迁移到 `AppSettings` 环境变量配置

**Requirements:** R4, R5, R6, R7

**Dependencies:** None

**Files:**
- Modify: `server/apps/backend/app/config.py`
- Modify: `server/apps/backend/app/services/learning/teach_back_service.py`

**Approach:**
- 在 `AppSettings` 中添加 `teach_back_enabled_topic_keys: str` 字段，默认值为逗号分隔的 6 个 topic key
- 添加一个 property 或 cached property 将其解析为 `frozenset[str]`
- 在 `teach_back_service.py` 中，用 `settings.teach_back_enabled_topic_keys_set` 替换 `_PILOT_TOPIC_KEYS`
- 移除 `_PILOT_TOPIC_KEYS` 常量

**Patterns to follow:**
- `server/apps/backend/app/config.py` 中其他 `AppSettings` 字段定义模式
- pydantic-settings 的 `Field` 用法

**Test scenarios:**
- Happy path: 环境变量未设置时，`teach_back_enabled_topic_keys_set` 返回全部 6 个默认 key
- Happy path: 环境变量设置为 `"mt_a,mt_b"` 时，解析为 `frozenset({"mt_a", "mt_b"})`
- Edge case: 环境变量为空字符串时，返回空 frozenset
- Edge case: 环境变量值含空格 `"mt_a, mt_b"` 时，正确 strip

**Verification:**
- `uv run pytest tests/backend/ -v -k "teach_back"` 通过
- 现有 3 个 pilot topic 行为不受影响

---

- U2. **为 3 个新 topic 创建 confusion seed 数据**

**Goal:** 在 seed 脚本中添加 Decimal place value、Understanding Percentages、Multiplying fractions 的 confusion 数据

**Requirements:** R1, R2, R3, R12

**Dependencies:** None

**Files:**
- Modify: `server/scripts/seed_teach_back_confusions.py`

**Approach:**
- 在 `SAMPLE_CONFUSIONS` 字典中添加 3 个新 topic 的 confusion 数据
- 每个 topic 设计 2-3 个 hand-authored confusion，包含 misconception、rubric、expected_expression
- 更新脚本顶部 docstring 记录全部 6 个 topic

**Confusion 设计方向：**

Decimal place value (`mt_Fl7b8q9pI1`):
1. "Is 0.5 bigger than 0.25 because 5 > 25?" — 小数位值误解
2. "What does the 3 in 1.32 mean?" — 位值概念
3. "Are 0.5 and 0.50 different numbers?" — 末尾零的理解

Understanding Percentages (`mt_ZM9mhHsyYZ`):
1. "Is 50% the same as 50?" — 百分比 vs 绝对数
2. "If I got 80% on a test, does that mean I got 80 questions right?" — 百分比的含义
3. "Can a percentage be more than 100%?" — 百分比范围

Multiplying fractions (`mt_TgHxujL81r`):
1. "Why do we multiply straight across?" — 分数乘法规则理解
2. "Is 1/2 × 1/3 the same as 1/2 + 1/3?" — 乘法 vs 加法混淆
3. "Does multiplying fractions always make the answer smaller?" — 分数乘法性质

**Patterns to follow:**
- 现有 `SAMPLE_CONFUSIONS` 字典结构
- 每个 confusion 的字段：sequence, confusion_text, confusion_text_zh, rubric, expected_expression

**Test scenarios:**
- Happy path: seed 脚本能为 3 个新 topic 正确创建 confusion 数据
- Happy path: 每个新 topic 有 2-3 个 approved confusion
- Edge case: 重复运行 seed 脚本不产生重复数据（幂等性）

**Verification:**
- `uv run pytest tests/backend/scripts/test_seed_teach_back_confusions.py -v` 通过
- 脚本可无错执行（dry-run 验证）

---

- U3. **扩展 SymPy grading 支持小数和百分比**

**Goal:** 扩展 `teach_back_grading.py` 的 expression extractor 以支持小数、百分比和分数乘法表达式

**Requirements:** R8, R9

**Dependencies:** None

**Files:**
- Modify: `server/apps/backend/app/services/learning/teach_back_grading.py`
- Test: `server/tests/backend/services/learning/test_teach_back_grading.py`

**Approach:**
- 添加 `_DECIMAL_PATTERN` regex 匹配小数（如 `0.25`, `3.14`）
- 添加 `_PERCENT_PATTERN` regex 匹配百分比（如 `25%`, `50%`），提取后转换为分数
- 添加 `_FRACTION_MULTIPLY_PATTERN` regex 匹配分数乘法（如 `1/2 × 1/3 = 1/6`）
- 在 `extract_expression` 中按优先级添加新模式：arithmetic > multiply > fraction_multiply > decimal > percent > fraction > number
- SymPy `sympify` 原生支持小数，百分比在 extractor 层转换为 `X/100`

**Patterns to follow:**
- 现有 regex pattern 定义风格（`_FRACTION_PATTERN`, `_ARITHMETIC_PATTERN` 等）
- `extract_expression` 的优先级匹配链

**Test scenarios:**
- Happy path: 提取小数表达式 `"0.25"` → `"0.25"`
- Happy path: 提取百分比 `"25%"` → `"25/100"`
- Happy path: 提取分数乘法 `"1/2 × 1/3 = 1/6"` → `"1/2 × 1/3 = 1/6"`
- Happy path: grade `"0.25"` vs expected `"1/4"` → True（SymPy 等价）
- Happy path: grade `"25%"` (converted to `"25/100"`) vs expected `"1/4"` → True
- Edge case: 文本中同时含小数和分数，优先匹配更具体的模式
- Edge case: `"0.50"` 和 `"0.5"` 应视为等价

**Verification:**
- `uv run pytest tests/backend/services/learning/test_teach_back_grading.py -v` 通过
- SymPy 能正确比较小数/百分比与分数的等价性

---

- U4. **更新测试覆盖**

**Goal:** 为 seed 脚本和 grading 扩展添加/更新测试

**Requirements:** R10, R11

**Dependencies:** U2, U3

**Files:**
- Modify: `server/tests/backend/scripts/test_seed_teach_back_confusions.py`
- Modify: `server/tests/backend/services/learning/test_teach_back_grading.py`

**Approach:**
- 在 seed 测试中添加 3 个新 topic 的验证
- 在 grading 测试中添加小数、百分比、分数乘法的测试用例

**Patterns to follow:**
- 现有测试文件结构和 fixture 模式

**Test scenarios:**
- Seed: 验证新 topic confusion 数据的完整性（字段非空、sequence 正确）
- Seed: 验证 6 个 topic 全部被 seed
- Grading: 小数提取和比较
- Grading: 百分比提取和比较
- Grading: 分数乘法提取和比较

**Verification:**
- `uv run pytest tests/backend/ -v -k "teach_back or seed_teach_back"` 全部通过

---

- U5. **记录环境变量配置**

**Goal:** 在代码注释和/或 AGENTS.md 中记录新的环境变量配置方式

**Requirements:** R13

**Dependencies:** U1

**Files:**
- Modify: `server/apps/backend/app/config.py` (comment)

**Approach:**
- 在 `AppSettings.teach_back_enabled_topic_keys` 字段添加 docstring 说明用法
- 可选：在 `server/apps/backend/AGENTS.md` 的环境变量表中添加条目

**Test scenarios:**
- Test expectation: none — 文档变更

**Verification:**
- 配置字段有清晰的 docstring
- 开发者能从文档理解如何配置

---

## System-Wide Impact

- **Interaction graph:** `teach_back_service.py` → `config.py` 的依赖方向不变（service reads config）
- **Error propagation:** 环境变量解析失败应 fail-fast（pydantic-settings 默认行为）
- **State lifecycle risks:** 无 — 配置是启动时读取的，运行时不变
- **Unchanged invariants:**
  - 现有 3 个 pilot topic 的行为完全不变
  - TopicConfusion 模型和数据库表不变
  - Smart Tutor agent 端逻辑不变

---

## Risks & Dependencies

| Risk | Mitigation |
|------|------------|
| 3 个新 topic 未在数据库中（未 seed） | seed 脚本会 warning 并跳过；部署前需先运行 `seed_learning_topics.py` |
| SymPy 百分比解析边界情况 | 在 extractor 层做转换，grader 层只看到分数；测试覆盖边界值 |
| 环境变量配置错误导致 teach-back 不可用 | 默认值包含全部 6 个 topic，不设置也能工作 |

---

## Sources & References

- **Origin document:** docs/brainstorms/2026-11-17-teachback-expansion-requirements.md
- Related code: `server/apps/backend/app/services/learning/teach_back_service.py`
- Related code: `server/scripts/seed_teach_back_confusions.py`
- Related issue: #234
