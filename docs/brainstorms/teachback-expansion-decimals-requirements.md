---
date: 2026-11-17
topic: teachback-expansion-decimals
---

# Teach-Back 扩展 — 小数 (Fraction-Decimal Equivalents)

## Problem Frame

Teach-back 功能当前硬编码限制为 3 个分数 topic（`_PILOT_TOPIC_KEYS`），无法扩展到其他数学概念。需要移除 pilot 限制，扩展到小数领域，验证 teach-back 模式在非分数 topic 上的可行性。

本次扩展选择 `mt_DRlbMok2lT`（Fraction-Decimal Equivalents, age 8+）作为首个非分数 topic——它与分数试点强关联，CONCEPTUAL 类型适合 teach-back 的概念解释场景。

---

## Requirements

**Topic 启用**

- R1. 将 `_PILOT_TOPIC_KEYS` 重命名为 `_TEACH_BACK_ENABLED_KEYS`，语义从"试点"变为"已启用"。
- R2. 在启用集中加入 `mt_DRlbMok2lT`，总计 4 个 topic。
- R3. 现有 3 个分数 topic 的行为不变（regression-free）。

**Grading 扩展**

- R4. 在 `teach_back_grading.py` 的 `extract_expression()` 中增加小数表达式提取模式：
  - 小数算术：`1.5 + 0.3 = 1.8`
  - 裸小数：`0.25`、`0.75`
  - 小数模式在 bare fraction 之前匹配（优先级：arithmetic > multiply > decimal arithmetic > bare decimal > bare fraction > bare number）
- R5. SymPy 原生支持小数解析（`sympy.sympify("0.5")` → `Float(0.5)`，通过 SymPy 数值等值比较 `Float(0.5) == Rational(1, 2)` 为 True），无需额外转换逻辑。`grade_expression()` 不需要改动。注意：仅限有限小数（0.5, 0.25, 0.75）；非终止小数（如 0.33）不与精确分数等值，不在本次范围内。
- R6. 现有分数提取和 grading 测试全部通过（regression）。

**Confusion 数据**

- R7. 为 `mt_DRlbMok2lT` 编写 2-3 条 hand-authored confusions，加入 `seed_teach_back_confusions.py`。
- R8. 每条 confusion 包含：`confusion_text`（英文）、`confusion_text_zh`（中文）、`rubric`（LLM 评判指南）、`expected_expression`（可选，用于 SymPy 校验）。
- R9. Confusion 内容覆盖 Fraction-Decimal Equivalents 的核心 misconceptions：
  - 小数位值混淆（如 1/2 = 0.2 而非 0.5）
  - 分母与小数位的关系（如 1/4 = 0.4 而非 0.25）
  - 等价概念（如 0.75 和 3/4 是同一个数的不同表示）

**测试**

- R10. 新增小数表达式提取的单元测试（decimal arithmetic、bare decimal）。
- R11. 新增小数 grading 测试（0.5 vs 1/2 等价、0.25 vs 0.5 不等价）。
- R12. 现有 `TestTeachBackService` 测试适配重命名后的常量名。

---

## Success Criteria

- 4 个 topic 全部可通过 teach-back 验证流程（`validate_teach_back_request` 不拒绝新 topic）。
- 小数表达式 `0.5`、`1.5 + 0.3 = 1.8` 可被正确提取和 grading。
- Seed 脚本可为新 topic 写入 approved confusions。
- 所有现有测试通过（regression-free）。
- `ruff check` + `mypy` + `pytest` 全部绿色。

---

## Scope Boundaries

- **不做**：百分比、比例、整数运算 topic（后续迭代）。
- **不做**：DB 配置表或 feature flag（保持 Python 常量）。
- **不做**：前端 UI 变更（teach-back 入口已存在，topic 列表由后端控制）。
- **不做**：Agent SKILL.md 修改（teach-back mode 逻辑是 topic-agnostic 的）。

---

## Key Decisions

- **Python 常量而非 DB 配置**：4 个 topic 无需运行时配置，YAGNI。代码 deploy 即为发布机制。
- **重命名 `_PILOT_TOPIC_KEYS` → `_TEACH_BACK_ENABLED_KEYS`**：消除"试点"的临时语义，反映实际状态。
- **选择 `mt_DRlbMok2lT`**：CONCEPTUAL 类型，与分数试点衔接紧密，centrality 0.083。

---

## Dependencies / Assumptions

- `mt_DRlbMok2lT` 已存在于 `learning_topics` 表中（由 `seed_learning_topics.py` 导入的 os-taxonomy 数据）。
- SymPy 的小数解析精度足以处理 1-2 位小数的等价判断（`0.5 == 1/2`、`0.25 == 1/4`）。
- Teach-back agent skill（`learning-smart-tutor`）的 teach-back mode 不需要修改——它接收 confusions 列表，不感知 topic 内容。

---

## Next Steps

-> `/ce-plan` for structured implementation planning.
