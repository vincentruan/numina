---
title: "feat: Teach-Back 扩展 — Fraction-Decimal Equivalents"
type: feat
status: completed
date: 2026-11-17
origin: docs/brainstorms/teachback-expansion-decimals-requirements.md
---

# Teach-Back 扩展 — Fraction-Decimal Equivalents

## Overview

在已落地的 Teach-Back 6-topic 启用集（3 个分数 + 小数位值 + 百分比 + 分数乘法，来自 plan 001 / `f03b8ec7`、`8c6c4d85`）基础上，新增第 7 个 topic `mt_DRlbMok2lT`（Fraction-Decimal Equivalents, age 8+, CONCEPTUAL），并补齐已落地小数/百分比扩展中在 review 时暴露的两个真实缺陷：

1. **小数算术提取**：`extract_expression("1.5 + 0.3 = 1.8")` 当时返回 `"0.3 = 1.8"`（被 `_DECIMAL_EQUATION_PATTERN` 截断为假方程）。
2. **反诘式文本的误伤**：孩子说 `"0.2 is wrong, it's 0.5"` 时，提取器会先取 `"0.2"`，`grade_expression` 判定 False，再由 `teach_back_service.py:338` 的单向 override 把模型给的 `hit` 压成 `miss`——把正确答案记成错误。

本计划**不**再重复 plan 001 已完成的环境变量迁移、百分比/小数位/分数乘法 seed。

---

## Problem Frame

`mt_DRlbMok2lT` 是 os-taxonomy 中 `domain: "Fractions"` 的 CONCEPTUAL topic，描述 "Recognise and write decimal equivalents of 1/4, 1/2, and 3/4"。它并非"首个非分数 topic"（`mt_Fl7b8q9pI1` 小数位值已是小数域）。本次扩展验证的是：

- 同一 Fractions 域内引入 CONCEPTUAL 类型的等价推理题（区别于已有 PROC/META）。
- Teach-back 的反诘文本处理路径在小数等价场景下不被误伤。

---

## Requirements Trace

### Topic 启用 (R1–R3)

- R1. 在 `TEACH_BACK_DEFAULT_TOPIC_KEYS`（`server/packages/core/settings.py:24`）的 6 元素元组末尾追加 `"mt_DRlbMok2lT"`，使启用集变为 7 个 topic。
- R2. `_EXPECTED_DEFAULT_KEYS`（`test_teach_back.py:438`）同步增至 7 项，`test_default_includes_all_seven_topics` 断言默认 7 个键。
- R3. 现有 6 个 topic 行为不变（回归）。

### 小数提取与 grading (R4–R7)

- R4. 新增 `_DECIMAL_ARITHMETIC_PATTERN`，插入到 `_MULTIPLY_PATTERN` 之后、`_DECIMAL_EQUATION_PATTERN` 之前。
- R5. `extract_expression` 增加可选参数 `expected: str | None = None`；小数分支改为在所有匹配中优先选一个等于 `expected` 的数值，否则保持首匹配。
- R6. `_sympy_parse` 改为 `sympy.sympify(normalized, strict=False, rational=True)`，消除 Float 累积误差。
- R7. 现有所有分数/小数/百分比/乘法提取与 grading 测试无回归。

### Confusion 数据 (R8–R10)

- R8. 为 `mt_DRlbMok2lT` 新增 3 条 hand-authored confusions 到 `SAMPLE_CONFUSIONS`。
- R9. 每条包含 `sequence, confusion_text, confusion_text_zh, rubric, expected_expression`；`expected_expression` 按 schema 为 nullable，但本次 3 条均填写。
- R10. 三条覆盖：小数位值误判（1/2 = 0.2）、分母与小数位关系（1/4 = 0.4）、等价概念（0.75 与 3/4 不同）。

### 测试与验证 (R11–R14)

- R11. 新增小数算术测试：`extract_expression("1.5 + 0.3 = 1.8") == "1.5 + 0.3 = 1.8"`。
- R12. 新增反诘式文本测试：`extract_expression("It's not 0.2, it's 0.5", expected="0.5") == "0.5"`。
- R13. 新增 Float 精度回归：`grade_expression("0.3", "0.1 + 0.2 = 0.3") is True`。
- R14. Seed 脚本测试：`pilot_topics` fixture 增补 `mt_DRlbMok2lT`，`test_two_to_four_confusions_per_topic` / `test_expected_expressions_round_trip` / `test_every_row_has_rubric` 覆盖新数据。

---

## Scope Boundaries

- 不做：环境变量迁移（已在 plan 001 / `f03b8ec7` 完成，`TEACH_BACK_ENABLED_TOPIC_KEYS` 即运行时开关）。
- 不做：前端 UI 变更（teach-back 入口已存在，topic 由后端 allowlist 控制）。
- 不做：Agent SKILL.md 修改（teach-back mode 逻辑 topic-agnostic，`record_teach_back_turn` 已接收 `expected` 上下文）。
- 不做：百分比/比例/整数运算 topic（已在 plan 001 完成，本次不在范围）。
- 不做：`test_teach_back_e2e.py:40` 的 `PILOT_TOPIC_KEY` 变量名——其字符串值 `"mt_9KmVWCuh5_"` 仍在默认集中，语义未受影响。

---

## Context & Research

### Relevant Code and Patterns

| 位置 | 用途 |
|---|---|
| `server/packages/core/settings.py:24-31` | `TEACH_BACK_DEFAULT_TOPIC_KEYS` 默认元组 |
| `server/packages/core/settings.py:135-144` | `TEACH_BACK_ENABLED_TOPIC_KEYS` 字段 + `teach_back_enabled_topic_keys_set` 属性 |
| `server/apps/backend/app/services/learning/teach_back_service.py:104` | 网关判断 `topic.topic_key not in settings.teach_back_enabled_topic_keys_set` |
| `server/apps/backend/app/services/learning/teach_back_service.py:327-339` | 提取 + 判定 + 单向 override（`computed_verdict is False and verdict == "hit"` → `verdict = "miss"`） |
| `server/apps/backend/app/services/learning/teach_back_grading.py:27-55` | 所有提取正则 |
| `server/apps/backend/app/services/learning/teach_back_grading.py:70-137` | `extract_expression` |
| `server/apps/backend/app/services/learning/teach_back_grading.py:171-193` | `_sympy_parse` |
| `server/scripts/seed_teach_back_confusions.py` | `SAMPLE_CONFUSIONS` 字典结构 |
| `server/tests/backend/services/learning/test_teach_back.py:438-448` | `_EXPECTED_DEFAULT_KEYS` |
| `server/tests/backend/services/learning/test_teach_back.py:458` | `test_default_includes_all_seven_topics` |
| `server/tests/backend/scripts/test_seed_teach_back_confusions.py:45-57` | `pilot_topics` fixture（7 个键） |
| `server/packages/os_taxonomy/topics.json:16697` | `mt_DRlbMok2lT` 元数据 |

### Institutional Learnings

- `mt_DRlbMok2lT` 元数据：`type=CONCEPTUAL`, `domain=Fractions`, `ageRangeStart=8` → `compute_age_group(8) == "mid"`，与 seed 脚本 `age_group="mid"` 一致。
- 已有 `_DECIMAL_PATTERN = re.compile(r"(\d+\.\d+)")` 已处理裸小数提取；不再重复 `_BARE_DECIMAL_PATTERN`。
- `_PERCENT_PATTERN` 必须在 `_DECIMAL_PATTERN` 之前（"12.5%" 读百分比，不是裸小数 12.5）。
- `_DECIMAL_EQUATION_PATTERN` 必须保留，用于捕获 "0.5 = 0.05" 等假方程，使 `require_true` 拒绝假声明。
- SymPy 默认把 `"0.1"` 解析为 `Float(0.1)`，使 `0.1 + 0.2 - 0.3` 残留 `~5.6e-17`，`simplify(...) == 0` 为 False。改用 `rational=True` 后解析为 `Rational(1,10)`，和为精确 0；已对所有现有测试用例（15 对）回归验证通过。
- 提取器对反诘式输入的处理：`extract_expression(child_text, expected=...)` 在小数分支中优先选择等于 `expected` 的数值。当 `expected` 为 None（如 round-trip 测试、模型未提供期望）时回退到首匹配，行为不变。

---

## Key Technical Decisions

- **环境变量而非 Python 常量**：plan 001 已落地 `TEACH_BACK_ENABLED_TOPIC_KEYS`，沿用该机制；本计划仅把新 key 加到默认元组。
- **小数算术模式**：正则 `(\d+\.\d+)\s*([+\-])\s*(\d+\.\d+)\s*=\s*(\d+\.\d+)`，要求两侧都是小数。放在 `_DECIMAL_EQUATION_PATTERN` 之前，使 `"1.5 + 0.3 = 1.8"` 被完整捕获；`"0.5 = 0.05"` 因无算术运算符仍落入 equation 分支。
- **Rational 归一化**：`_sympy_parse` 使用 `rational=True`。副作用："12.5/100" → `1/8`，与现有百分比路径一致；现有所有 15 对 grade 测试全部通过。替代方案（在比较点加容差）被否决——它会把误差吞进 grader，污染后续任何使用相同路径的 topic。
- **反诘感知提取**：把 `expected_expression` 传入 `extract_expression`。在小数分支内优先选匹配 expected 的候选。分数/整数分支保持不变——当前混淆设计未出现分数/整数的反诘形态，不提前泛化。
- **不修改 `grade_expression` 的语义**：判定逻辑未变；只改变 `_sympy_parse` 的字面量精度。`require_true`、单向 override、False-claim guard 行为一致。
- **Seed 设计**：三条 confusion 的 `confusion_text` 都含一个"错误数值"的提问。子回答"1/2 = 0.5 而非 0.2"会先被 decimal 分支命中；`expected="0.5"` 时选 0.5 → True。

### 完整提取优先级链

```
_ARITHMETIC_PATTERN           # 1/4 + 2/4 = 3/4
_FRACTION_MULTIPLY_PATTERN    # 1/2 × 1/3 = 1/6  (至少一侧为分数)
_MULTIPLY_PATTERN             # 3 × 2 = 6
_DECIMAL_ARITHMETIC_PATTERN   # 1.5 + 0.3 = 1.8        ← 新增
_DECIMAL_EQUATION_PATTERN     # 0.5 = 0.05 (False-claim guard)
_PERCENT_PATTERN              # 12.5% → 12.5/100
_DECIMAL_PATTERN              # 0.25, 3.14  (反诘感知选择)
_FRACTION_PATTERN             # 3/4
_WHOLE_NUMBER_PATTERN         # 6
```

---

## Open Questions

### Resolved

- **Q: `mt_DRlbMok2lT` 是否存在于 DB？** A: 存在于 `topics.json`，由 `seed_learning_topics.py` 导入；`mt_DRlbMok2lT` 已在 `dependencies.json` 中作为前置被引用。
- **Q: 新增 7 个 topic 是否会与其他 topic 的混淆 seed 重叠？** A: 三条 confusion 与 `mt_Fl7b8q9pI1`（Decimal place value）主题不同：后者侧重"0.5 vs 0.25 哪个大 / 1.32 里各位含义"（位值比较），前者侧重分数 ↔ 小数等价性。
- **Q: `expected_expression` 是否必选？** A: schema 与 seed 脚本用 `c.get(...)` 读取，视为 nullable；本计划 3 条均填写，但不要求未来所有 confusion 都填。
- **Q: 小数 arithmetic regex 是否接受无空格形式？** A: 接受。`(\d+\.\d+)\s*([+\-])\s*(\d+\.\d+)\s*=\s*(\d+\.\d+)` 的 `\s*` 允许 0 个或多个空白；`"0.5+0.3=0.8"` 与 `"0.5 + 0.3 = 0.8"` 都匹配。

---

## Implementation Units

### U1. 启用第 7 个 topic

**Goal:** 在 `TEACH_BACK_DEFAULT_TOPIC_KEYS` 默认元组追加 `mt_DRlbMok2lT`。

**Requirements:** R1, R2, R3

**Dependencies:** 无

**Files:**
- Modify: `server/packages/core/settings.py` — 第 31 行元组末尾加 `"mt_DRlbMok2lT"`。
- Modify: `server/tests/backend/services/learning/test_teach_back.py` — `_EXPECTED_DEFAULT_KEYS` 增为 7 项；`test_default_includes_all_six_topics` 重命名为 `test_default_includes_all_seven_topics`。
- Modify: `server/tests/backend/scripts/test_seed_teach_back_confusions.py` — `pilot_topics` fixture 加入 `"mt_DRlbMok2lT"`，docstring 更新为 7 个 topic。

**Approach:**
- 不改 `teach_back_service.py` 的网关——它已读 `settings.teach_back_enabled_topic_keys_set`，新 key 入默认元组即自动启用。
- 不改 `_PILOT_TOPIC_KEYS`（已不存在；历史常量，plan 001 / `f03b8ec7` 迁移到 `settings.TEACH_BACK_ENABLED_TOPIC_KEYS` 环境变量）。
- 不改 `test_teach_back_e2e.py:40` 的 `PILOT_TOPIC_KEY` 变量名——其字符串值未变，仅名称遗留；本计划不引入改名以避免无谓 diff。

**Test scenarios:**
- Happy path: `settings.teach_back_enabled_topic_keys_set` 包含 7 个 topic key。
- Happy path: 现有 6 个 topic 仍在集合中（回归）。
- Happy path: `mt_DRlbMok2lT` 在集合中。
- Integration: `validate_teach_back_request(db, child, topic_id_of_mt_DRlbMok2lT)` 不再抛出 "not enabled for teach-back"。
- 默认常量与 Settings 字段一致：`test_default_constant_matches_settings_default` 仍通过。

**Verification:**
- `uv run pytest tests/backend/services/learning/test_teach_back.py -v` 全部通过。
- `uv run ruff check packages/core/settings.py tests/backend/services/learning/test_teach_back.py tests/backend/scripts/test_seed_teach_back_confusions.py` 通过。

---

### U2. 小数算术提取 + 反诘感知 + Rational 归一化

**Goal:** 修复三个真实缺陷，使小数/百分比扩展路径在新 topic 上行为正确。

**Requirements:** R4, R5, R6, R7, R11, R12, R13

**Dependencies:** 无

**Files:**
- Modify: `server/apps/backend/app/services/learning/teach_back_grading.py`
- Modify: `server/apps/backend/app/services/learning/teach_back_service.py` — 把 `confusion.expected_expression` 传入 `extract_expression`。

**Approach:**
- 新增 `_DECIMAL_ARITHMETIC_PATTERN = re.compile(r"(\d+\.\d+)\s*([+\-])\s*(\d+\.\d+)\s*=\s*(\d+\.\d+)")`。
- 在 `extract_expression` 中插入到 `_MULTIPLY_PATTERN` 之后、`_DECIMAL_EQUATION_PATTERN` 之前。
- 把 `_DECIMAL_PATTERN` 分支抽成 `_select_decimal(child_text, expected)`：遍历所有小数匹配，返回第一个 `grade_expression(expected, match) is True` 的数值；找不到则返回首匹配。
- `_sympy_parse` 增加 `rational=True`，保持 strict=False 与 free-symbols 检查。
- `teach_back_service.py:327` 改为 `extracted_expression = extract_expression(child_explanation, expected=confusion.expected_expression)`。

**Test scenarios:**
- Happy path: `extract_expression("1.5 + 0.3 = 1.8") == "1.5 + 0.3 = 1.8"`。
- Happy path: `extract_expression("0.5+0.3=0.8") == "0.5+0.3=0.8"`。
- Happy path: `extract_expression("12.5% 就是 1/8") == "12.5/100"`（无回归）。
- Happy path: `extract_expression("0.5 = 0.05") == "0.5 = 0.05"`（False-claim guard 仍在）。
- Happy path: `extract_expression("It's not 0.2, it's 0.5", expected="0.5") == "0.5"`。
- Happy path: `extract_expression("No, 0.4 is wrong, 1/4 is 0.25", expected="0.25") == "0.25"`。
- Happy path: `extract_expression("It's not 0.2, it's 0.5") == "0.2"`（无 expected 时保持首匹配）。
- Regression: `grade_expression("0.3", "0.1 + 0.2 = 0.3") is True`（Rational 归一化）。
- Regression: `grade_expression("1/4", "25/100") is True`、`grade_expression("1/2", "50/100") is True`、`grade_expression("1/6", "1/2 × 1/3 = 1/6") is True`。

**Verification:**
- `uv run pytest tests/backend/services/learning/test_teach_back.py -v` 全部通过。
- 现有 `TestExtractExpression` / `TestGradeExpression` 测试无回归。
- `uv run ruff check apps/backend/app/services/learning/teach_back_grading.py apps/backend/app/services/learning/teach_back_service.py` 通过。

---

### U3. 编写 Fraction-Decimal Equivalents 的 confusion seed

**Goal:** 在 seed 脚本中为 `mt_DRlbMok2lT` 新增 3 条 confusions。

**Requirements:** R8, R9, R10, R14

**Dependencies:** U1

**Files:**
- Modify: `server/scripts/seed_teach_back_confusions.py`

**Approach:**
- 在 `SAMPLE_CONFUSIONS` 中加 `"mt_DRlbMok2lT"` 键。
- 三条 confusion 设计（覆盖 R10）：
  1. **小数位值混淆**："Is 1/2 the same as 0.2? I divided 2 into 1 and got 0.2." 期望 `0.5`。子回答"1/2 = 0.5, not 0.2"。
  2. **分母与小数位关系**："Is 1/4 the same as 0.4? The 4 is in the tenths place, right?" 期望 `0.25`。子回答"1/4 = 0.25, not 0.4"。
  3. **等价概念**："0.75 and 3/4 look completely different. Are they really the same number?" 期望 `3/4`。子回答"0.75 is 75/100, and 3/4 = 75/100, so they are the same"。
- 更新脚本顶部 docstring（"Topics (7 math, ...)"，新增 "Equivalence (fraction/decimal notation): mt_DRlbMok2lT  Fraction-Decimal Equivalents"）。
- 更新 `seed_confusions()` 的 docstring，移除"pilot topics"措辞。

**Test scenarios:**
- Happy path: seed 脚本为 `mt_DRlbMok2lT` 创建 3 条 `review_status='approved'` 的 confusion。
- Happy path: 重复运行幂等（`test_seed_twice_is_stable`）。
- Edge case: 每条 `confusion_text` / `rubric` 非空。
- Round-trip: `grade_expression(expected, extract_expression(expected))` 对每条均 True。
- Expansion 覆盖: `test_expansion_topics_have_expected_expressions` 保留原有 3 个 expansion key 不变（`mt_DRlbMok2lT` 是等价题，不属于同一维度）。

**Verification:**
- `uv run python scripts/seed_teach_back_confusions.py` 无错执行，输出 "Seeded 3 confusions for topic 'Fraction-Decimal Equivalents (mt_DRlbMok2lT)'"。
- `uv run pytest tests/backend/scripts/test_seed_teach_back_confusions.py -v` 全部通过。

---

## System-Wide Impact

- **Interaction graph:** `teach_back_service.py` 的提取调用从 `extract_expression(child_text)` 变为 `extract_expression(child_text, expected=confusion.expected_expression)`。签名向后兼容——新参数有默认值，所有现有调用方（`record_teach_back_turn`、round-trip 测试、`test_expected_expressions_round_trip`）仍通过。
- **Error propagation:** 不变——validation 错误仍通过 `AppError` 抛出。
- **False-claim guard:** `_DECIMAL_EQUATION_PATTERN` 保留，`"0.5 = 0.05"` 等假方程仍走 `require_true` 路径被拒。新算术模式不匹配纯等式形式（无 `+/-`），不干扰。
- **SymPy 精度:** Rational 归一化改变所有字面量的解析方式；15 个现有 grade 用例回归验证全部通过。

## Unchanged invariants

- 现有 6 个 enabled topic 的行为完全不变。
- TopicConfusion 模型与数据库表不变。
- Smart Tutor agent 端逻辑不变（teach-back mode topic-agnostic）。
- 新正则不影响现有分数/百分比/乘法提取。
- `_DECIMAL_EQUATION_PATTERN` 行为不变。
- `_FRACTION_MULTIPLY_PATTERN` 与 `_MULTIPLY_PATTERN` 的先后顺序不变。

---

## Risks & Dependencies

| Risk | Mitigation |
|------|------------|
| `mt_DRlbMok2lT` 在某些环境未 seed | `seed_learning_topics.py` 已包含该 topic（os-taxonomy 数据）；部署前确认 topic 数据已导入 |
| `TEACH_BACK_ENABLED_TOPIC_KEYS` 被显式设置在 `.env` 中且未包含新 key | grep 仓库无显式设置（仅 `settings.py` 默认值）；若部署已设环境变量，需把 `mt_DRlbMok2lT` 一并加入 |
| SymPy 精度对非有限小数的影响 | 本次仅涉及 0.5/0.25/0.75（均可精确表示）；Rational 归一化使有限小数一律精确 |
| 新正则与现有 bare number regex 冲突 | `_DECIMAL_ARITHMETIC_PATTERN` 要求运算符与等号；纯 `"0.5 和 1/2 是一样的"` 仍走 `_DECIMAL_PATTERN` |
| `test_teach_back_e2e.py:40` 的 `PILOT_TOPIC_KEY` 命名遗留 | 字符串值 `"mt_9KmVWCuh5_"` 在默认集中；不在本计划范围改名 |
| 误解构 catalog 覆盖度 | `seed_misconceptions.py` 仅覆盖 1/6 teach-back topic；本计划未扩展——属于后续迭代 |

---

## Sources & References

- **Origin document:** docs/brainstorms/teachback-expansion-decimals-requirements.md
- **前置 plan:** docs/plans/2026-11-17-001-feat-teachback-expansion-plan.md（已完成的部分）
- **相关 commit:**
  - `f03b8ec7` — 迁移 topic allowlist 到环境变量配置
  - `8c6c4d85` — SymPy grading 扩展到小数/百分比/分数乘法
  - `c42932a2` — seed 新增小数/百分比/分数乘法 confusion
- Related code: `server/packages/core/settings.py`
- Related code: `server/apps/backend/app/services/learning/teach_back_service.py`
- Related code: `server/apps/backend/app/services/learning/teach_back_grading.py`
- Related code: `server/scripts/seed_teach_back_confusions.py`
- Related issue: #234
