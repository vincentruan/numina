---
date: 2026-11-17
topic: teachback-expansion
---

# Teach Back 扩展 — 从分数试点到更多数学概念

## Problem Frame

当前 Teach Back 功能仅限 3 个分数 topic 试点（`_PILOT_TOPIC_KEYS` 硬编码）。这限制了验证"教 AI"模式在更广范围数学概念中的学习效果。需要扩展到 3 个新 topic（小数位值、百分比、分数乘法），同时将 topic 开关机制从硬编码迁移到环境变量配置，为未来扩展打好基础。

---

## Requirements

**Topic 扩展**

- R1. 为 3 个新 topic 创建 TopicConfusion seed 数据，每个 topic 2-3 个 hand-authored confusion：
  - `mt_Fl7b8q9pI1` — Decimal place value (小数位值, age 8-10)
  - `mt_ZM9mhHsyYZ` — Understanding Percentages (百分比, age 9-11)
  - `mt_TgHxujL81r` — Multiplying fractions (分数乘法, age 9-11)
- R2. 每个 confusion 包含：confusion_text (英文), confusion_text_zh (中文), rubric, expected_expression (nullable)
- R3. Confusion 设计应覆盖该 topic 最常见的 2-3 个 misconceptions

**配置迁移**

- R4. 将 `_PILOT_TOPIC_KEYS` 硬编码 frozenset 迁移到环境变量 `TEACH_BACK_ENABLED_TOPIC_KEYS`
- R5. 环境变量值为逗号分隔的 topic_key 列表，解析后与当前 frozenset 行为一致
- R6. 未设置环境变量时，使用默认值（全部 6 个 topic key：原有 3 个 + 新增 3 个）
- R7. 环境变量配置在 `AppSettings`（backend config.py）中，而非 teach_back_service.py 内

**SymPy 验证覆盖**

- R8. 验证 `teach_back_grading.py` 的 expression extractor 能正确处理新 topic 的数学表达式：
  - 小数：`0.25`, `3.14`
  - 百分比：`25%`, `50/100`
  - 分数乘法：`1/2 × 1/3 = 1/6`
- R9. 如有必要，扩展 regex patterns 和 SymPy parsing 以支持小数和百分比

**测试覆盖**

- R10. 为 seed 脚本添加测试：验证 3 个新 topic 的 confusion 数据正确性
- R11. 为 SymPy grading 扩展添加测试：小数、百分比、分数乘法的 expression extraction 和 grading

**文档**

- R12. 更新 seed 脚本 docstring 和注释，记录全部 6 个 topic
- R13. 简要记录环境变量配置方式（可在 code comment 或 AGENTS.md 中）

---

## Success Criteria

- 3 个新 topic 各有 2-3 个 approved confusion 数据
- `TEACH_BACK_ENABLED_TOPIC_KEYS` 环境变量可控制启用哪些 topic
- SymPy grading 能正确处理小数、百分比、分数乘法的表达式
- 现有 3 个分数 pilot topic 行为不受影响（向后兼容）
- 所有新代码有测试覆盖，`pytest tests/backend/` 通过

---

## Scope Boundaries

- 不修改前端 UI — TeachBackPage.vue 已支持通用 topic 展示
- 不修改 Smart Tutor SKILL.md 的 teach-back 流程 — agent 端逻辑 topic-agnostic
- 不新增数据库 migration — TopicConfusion 模型已存在
- 不添加 admin 管理界面 — 环境变量配置足够
- 不扩展 SymPy 到非数学 topic — 仅覆盖小数、百分比、分数乘法

---

## Key Decisions

- **环境变量 vs 数据库配置表**: 选择环境变量，因为当前阶段 topic 数量有限，环境变量足够且简单。未来如需动态管理可迁移到数据库。
- **3 个 topic vs 5 个**: 选择 3 个（小数、百分比、分数乘法），与现有分数 pilot 形成自然进阶路径，工作量可控。
- **默认值包含全部 6 个 topic**: 环境变量未设置时默认启用所有 topic，避免部署后需额外配置。

---

## Dependencies / Assumptions

- 3 个新 topic (`mt_Fl7b8q9pI1`, `mt_ZM9mhHsyYZ`, `mt_TgHxujL81r`) 已存在于 `learning_topics` 表中（由 `seed_learning_topics.py` 导入）
- SymPy 已安装且能处理小数和百分比的数学表达式
- 现有 `TopicConfusion` 模型无需修改

---

## Next Steps

-> `/ce-plan` for structured implementation planning
