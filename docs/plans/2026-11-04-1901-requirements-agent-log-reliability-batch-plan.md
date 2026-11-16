---
artifact_contract: ce-unified-plan/v1
product_contract_source: ce-brainstorm
date: 2026-11-04
execution: code
---

# Agent Log 可靠性批量修复

## Goal Capsule

**Objective**: 消除 agent 模块日志中的 P1/P2 警告，修复两个隐藏 bug（error-publish-on-success、空结果 verify 失败），使 finance-coach 任务可靠完成、summarization 正常工作、日志噪音降至最低。

**Means**: SKILL.md prompt 强化 + worker.py bug 修复 + callback 空结果持久化 + summarization 触发器改绝对值 + 上游 DeerFlow 降级行为接受 (KTD2, KTD5)。

**执行方式**: 单个 PR，按 Implementation Units 依赖顺序实施。

---

## Product Contract

> Product Contract unchanged from brainstorm — R/AE/F IDs preserved. One correction: R3 root cause refined from "table mismatch" to "empty-suggestions skip persist" (see KTD3).

### Problem Frame

日志监控发现 5 类 agent 可靠性问题：Finance Coach JSON 解析频繁触发 repair loop（P1）、LLM 生成不存在的 target_id（P1）、task result verify 对空结果误判失败（P2）、summarization fraction 触发器因缺少 context_window 被丢弃（P2）、input sanitization 降级警告噪音（P3）。代码核对还发现两个隐藏 bug：worker.py 在 fallback 成功后仍发 error event、空建议回调跳过持久化导致 verify 失败。

### Requirements

**R1: Finance Coach JSON 输出稳定性 (P1)** — 将 `JSON invalid, retry=N/3` 警告频率降至接近 0。通过 SKILL.md 添加 few-shot 示例 + max_tokens 增至 8000 + 强调 `id` 字段格式。

**R2: Hallucinated target_id 防御 (P1)** — 保持现有三重防御（prompt 约束 + repair + 白名单过滤），通过 few-shot 示例强化 prompt 层。`filter_coach_suggestions_by_ids` 保持现有行为（清 target_id 保留 target_type）。

**R3: Task result not found 修复 (P2)** — 修复 `_persist_coach_result` 跳过空结果导致 `_verify_task_result` 误判失败。根因：LLM 返回 `{"suggestions": []}` 是合法输出（SKILL.md 允许），但回调跳过持久化 → verify 找不到 AIReport 行 → 任务标记 failed。修复方向：回调始终持久化（空结果也写入 AIReport），verify 逻辑无需改动。

**R4: Summarization context_window 警告 (P2)** — 消除 `Dropped summarization fraction trigger` 警告。`_inject_summarization` 改为注入 messages/tokens 绝对值触发器。

**R5: Input sanitization 警告降噪 (P3)** — 减少 `rfind failed` 日志噪音。不 fork DeerFlow（Bridge-don't-fork），接受设计内降级行为。

**R6: Worker.py error-publish bug 修复 (P2)** — 修复 `_run_finance_coach_agent` 在 fallback 成功后仍发 error event 的缩进 bug。将 `bridge.publish("error")` 移入 fallback 失败的 `else` 分支，仅当 repair loop 和 fallback 均失败时才发 error event。同时修正注释/代码不一致（line 1422-1425 说 "target_id/target_type are cleared" 但代码只清 target_id）。

### Flows

**F1: Finance Coach 完整流程（修复后）**
```
backend POST /ai/finance-coach/generate
  → build_family_finance_snapshot() → snapshot JSON
  → AgentClient.stream → finance-coach app
  → SKILL.md prompt (含 few-shot 示例) → LLM output
  → parse_report_json → validate_coach_json
  → [失败] run_json_repair_loop (3 retries)
  → [仍失败] extract_json_via_llm final fallback
  → [仍失败] publish error event + return
  → [成功] filter_coach_suggestions_by_ids (anti-hallucination)
  → publish finance_coach.result
  → _persist_coach_result callback → upsert_skill_result → AIReport 表
  → _verify_task_result → 查 AIReport 表 ✅ (空结果也持久化后)
  → task status = completed
```

### Acceptance Examples

**AE1**: Finance Coach 正常输出 — 有高利率债务家庭触发，0 次 repair retry，0 次 hallucinated target_id。

**AE2**: Finance Coach 空结果 — 无数据家庭触发，返回 `{"suggestions": []}`，task status = completed（非 failed）。

**AE3**: 长对话压缩 — 45 条消息对话自动触发压缩，0 次 "Dropped fraction trigger" 警告。

**AE4**: Worker error-publish 修复 — fallback 成功时不发 error event。

### Scope Boundaries

**不在范围内**: 前端改动、DeerFlow 上游贡献、新监控指标、available_target_ids 映射。

**Deferred**: 若 few-shot 仍不够稳定 → structured output/JSON schema 强制；若警告噪音持续 → 向上游提 PR。

---

## Planning Contract

### Key Technical Decisions

**KTD1: 保留 target_type 当清空 target_id 时** (session-settled: user-approved)
`filter_coach_suggestions_by_ids` 保持现有行为。前端导航需 target_type 确定列表 tab。

**KTD2: 不 fork DeerFlow** (session-settled: user-approved)
接受 input sanitization 降级行为。Bridge-don't-fork 原则；上游标注"no security regression"。

**KTD3: 空结果始终持久化** (planning-time decision)
`_persist_coach_result` 始终写入 AIReport，即使 suggestions 为空。原 skip 逻辑（"保持现有缓存"）属于读取时关注点，不应阻塞写入。"读取时 TTL 过期"已提供自然缓存失效。

**KTD4: 绝对值触发器替代 fraction** (session-settled: user-approved)
`_inject_summarization` 改为 messages/tokens 触发器。YAGNI — 无需维护 model→context_window 映射表。

**KTD5: 修复 worker.py error-publish 缩进 bug** (planning-time decision)
`bridge.publish("error")` 移入 fallback 失败的 else 分支。代码证据确认即使 fallback 成功也发 error。

### Assumptions

- 现有 `filter_coach_suggestions_by_ids` 的三重防御已足够，不需要增加 `available_target_ids` 映射
- `AIReport` 表的 `skill_id` 字段已支持 `"finance-coach"` 值（已验证：`upsert_skill_result` 直接用此 skill_id）
- 前端已能处理 `target_id: ""` + `target_type: "liability"|"asset"|"wish"` 的情况

---

## Implementation Units

### U1. Fix worker.py error-publish bug + comment correction

**Goal**: 修复 finance-coach fallback 成功后仍发 error event 的 bug，修正注释/代码不一致。

**Requirements**: R6

**Dependencies**: none

**Files**:
- `server/apps/agent/services/runtime/worker.py` (lines 1392-1450)
- `server/tests/agent/test_finance_coach_worker.py` (新增)

**Approach**:
1. 在 `_run_finance_coach_agent` 中，将 `bridge.publish("error", ...)` 从 `if validation_errors:` 块的底部移入 `else:` 分支（fallback 失败时才发 error）
2. 修正 line 1422-1425 注释："target_id/target_type are cleared" → "target_id is cleared, target_type is kept"
3. 添加单元测试覆盖 3 个分支：
   - 首次解析成功 → 不发 error，发 result
   - repair loop 失败 + fallback 成功 → 不发 error，发 result
   - repair loop 失败 + fallback 失败 → 发 error

**Patterns to follow**: `server/apps/agent/services/runtime/worker.py` 现有的 `_run_asset_report_agent` 分支结构

**Test scenarios**:
- 首次 `validate_coach_json` 通过 → bridge.publish("custom", finance_coach.result) 被调用，bridge.publish("error") 未被调用
- repair loop 3 次失败 + `extract_json_via_llm` 返回有效 JSON → bridge.publish("custom", finance_coach.result) 被调用，bridge.publish("error") 未被调用
- repair loop 3 次失败 + `extract_json_via_llm` 返回 None → bridge.publish("error") 被调用

**Verification**: `pytest tests/agent/test_finance_coach_worker.py -v` 全部通过

---

### U2. Fix empty-suggestions persist skip in finance-coach callback

**Goal**: 修复 `_persist_coach_result` 跳过空结果导致 `_verify_task_result` 误判任务失败。

**Requirements**: R3

**Dependencies**: none

**Files**:
- `server/apps/backend/app/routers/ai_finance_coach.py` (lines 171-192, `_persist_coach_result`)
- `server/tests/backend/test_finance_coach_persist.py` (新增)

**Approach**:
1. 移除 `_persist_coach_result` 中 `if not suggestions: return` 的 skip 逻辑
2. 始终调用 `upsert_skill_result(_db, family_id, "finance-coach", payload)`，即使 suggestions 为空
3. 保留 `if payload:` 检查（防止 None payload）
4. 添加单元测试覆盖：
   - 正常 suggestions → persist 被调用
   - 空 suggestions `[]` → persist 仍被调用（修复后）
   - None payload → persist 不被调用

**Patterns to follow**: `server/apps/backend/app/routers/ai_wish_advice.py` 的 `_persist_wish_advice_result` 回调模式

**Test scenarios**:
- `finance_coach.result` event with `suggestions: [{"id": "s1", ...}]` → `upsert_skill_result` 被调用，AIReport 行 status="completed"
- `finance_coach.result` event with `suggestions: []` → `upsert_skill_result` 仍被调用（不再 skip），AIReport 行 status="completed"
- `finance_coach.result` event with `payload: None` → `upsert_skill_result` 不被调用

**Verification**: `pytest tests/backend/test_finance_coach_persist.py -v` 全部通过

---

### U3. Enhance Finance Coach SKILL.md with few-shot examples

**Goal**: 通过 few-shot 示例提高 LLM 输出稳定性，减少 JSON 解析失败和 target_id 幻觉。

**Requirements**: R1, R2

**Dependencies**: none

**Files**:
- `server/apps/agent/skills/builtin/public/finance-coach/SKILL.md`

**Approach**:
1. `max_tokens: 6000` → `8000`
2. 在 "Most Important Rules" 后添加 "Few-shot Examples" 章节，含 2 个完整示例：
   - Example 1: 高利率债务建议（展示 id/target_id 正确复制）
   - Example 2: 空结果场景（无重大问题时返回空数组）
3. 添加 "Common Mistakes" 对比：缺少 id 字段（错误）vs 包含 id 字段（正确）
4. 强化 Rule 3 措辞：强调 "NEVER fabricate or guess — copy verbatim from the snapshot"

**Patterns to follow**: `server/apps/agent/skills/builtin/public/asset-report/SKILL.md` 的示例结构

**Test scenarios**:
- Test expectation: none — SKILL.md 是 prompt 配置，通过集成测试验证效果
- 集成验证：触发 5 次 finance-coach，检查 repair loop 触发次数

**Verification**: 日志中 `JSON invalid, retry` 频率降至 0-1 次/5 触发

---

### U4. Switch summarization to absolute-value triggers

**Goal**: 消除 `Dropped summarization fraction trigger clause(s)` 警告。

**Requirements**: R4

**Dependencies**: none

**Files**:
- `server/apps/agent/services/deerflow_adapter/family_adapter_cache.py` (lines 279-301, `_inject_summarization`)
- `server/tests/agent/test_family_adapter_summarization.py` (新增)

**Approach**:
1. 修改 `_inject_summarization` 函数，将 `trigger` 从 fraction 改为绝对值：
   ```python
   config["summarization"] = {
       "enabled": True,
       "trigger": [
           {"type": "messages", "value": 40},
           {"type": "tokens", "value": 12000},
       ],
       "keep": {"type": "messages", "value": 12},  # 从 20 改为 12，与 base/config.yaml 对齐
   }
   ```
2. 注意 `keep.value` 也从 20 改为 12（与 `deerflow_config/base/config.yaml` line 43 对齐——压缩后保留 6 轮对话）
3. trigger 从单个 dict 变为 list（DeerFlow 支持多触发器 OR 关系）
4. 添加单元测试验证注入的配置结构正确

**Patterns to follow**: `server/apps/agent/deerflow_config/base/config.yaml` 的 summarization section（已有绝对值触发器格式）

**Test scenarios**:
- `_inject_summarization(config, memory_enabled=True)` → `config["summarization"]["trigger"]` 是包含 messages/tokens 两个触发器的 list
- `_inject_summarization(config, memory_enabled=False)` → config 无变化（函数 early return）

**Verification**: 长对话（>40 条消息）日志中无 "Dropped summarization fraction trigger" 警告

---

### U5. Suppress input sanitization warning log

**Goal**: 减少 `rfind failed with original_user_content set` 警告的日志噪音。

**Requirements**: R5

**Dependencies**: none

**Files**:
- `server/apps/agent/app/main.py` (lifespan 中配置 logging filter)
- `server/tests/agent/test_input_sanitization_log_suppression.py` (新增，可选)

**Approach**:
1. 在 agent 启动配置中（`main.py` lifespan 或 `worker.py` 模块级别），对 `deerflow.agents.middlewares.input_sanitization_middleware` logger 添加 filter：
   - 将包含 "rfind failed with original_user_content set" 的 WARNING 降级为 DEBUG
   - 其他来自该 logger 的日志保持原级别
2. 使用 Python `logging.Filter` 实现选择性降级，不影响其他 DeerFlow 中间件日志

**Patterns to follow**: `server/packages/core/logging.py` 的日志配置模式

**Test scenarios**:
- 模拟 input_sanitization_middleware 发出 "rfind failed" WARNING → 日志输出为 DEBUG 级别（被 INFO 级别过滤掉）
- 模拟同一 logger 发出其他 WARNING → 日志输出保持 WARNING 级别

**Verification**: agent 启动后日志中无 "rfind failed" 警告

---

## Verification Contract

### Per-Unit Commands

```bash
# U1: worker.py error-publish bug fix
uv run pytest tests/agent/test_finance_coach_worker.py -v

# U2: empty-suggestions persist fix
uv run pytest tests/backend/test_finance_coach_persist.py -v

# U3: SKILL.md — integration verification (manual)
# Trigger finance-coach 5 times, check logs for repair/hallucination frequency

# U4: summarization trigger change
uv run pytest tests/agent/test_family_adapter_summarization.py -v

# U5: log suppression
# Manual verification: start agent, check logs for "rfind failed" absence
```

### Regression Suite

```bash
# Full agent module tests
uv run pytest tests/agent/ -v --timeout=60

# Full backend module tests
uv run pytest tests/backend/ -v --timeout=60

# Lint + type check
uv run ruff check server/apps/agent/ server/apps/backend/
uv run mypy server/apps/agent/ --exclude vendor
uv run mypy server/apps/backend/
```

### Integration Verification

```bash
# End-to-end finance-coach flow
# 1. Start docker-compose
# 2. POST /api/v1/ai/finance-coach/generate
# 3. Check task status = completed (not failed)
# 4. Check logs: 0x "result not found", 0x "Dropped fraction trigger"
```

---

## Definition of Done

### Global Criteria

- [ ] 所有 5 个 Implementation Units 完成
- [ ] `pytest tests/agent/ tests/backend/` 全通过（含新增测试）
- [ ] `ruff check` + `mypy` 无新错误
- [ ] 集成验证通过（finance-coach 任务 status = completed）
- [ ] 日志验证：无 "result not found"、无 "Dropped fraction trigger"、无 "rfind failed" 警告
- [ ] 无废弃代码残留（实验性代码已清理）

### Per-Unit Done Criteria

- **U1**: worker.py 3 个分支的单元测试全部通过
- **U2**: 空 suggestions 持久化测试通过，verify 不再误判
- **U3**: SKILL.md 修改完成，few-shot 示例格式正确
- **U4**: `_inject_summarization` 注入绝对值触发器，`keep.value` 从 20 改为 12（与 base config.yaml 对齐），单元测试通过
- **U5**: 日志 filter 配置生效（`main.py` lifespan），"rfind failed" 不再出现在 INFO 级别日志

---

## Sources

- Origin: `server/.dev-logs/日志观察优化/实施方案.md` + 同目录分析文件
- Code evidence: `worker.py:1392-1450`, `ai_finance_coach.py:171-192`, `family_adapter_cache.py:279-301`, `finance_coach_cache.py:93-115`
- DeerFlow middleware: `.venv/.../deerflow/agents/middlewares/summarization_middleware.py`, `input_sanitization_middleware.py:395-406`
- Skill: `server/apps/agent/skills/builtin/public/finance-coach/SKILL.md`

---

## Product Contract Preservation

Product Contract unchanged — R1-R5, AE1-AE4, F1-F2 IDs preserved. R3 root cause refined: "表不一致" corrected to "空结果跳过持久化"（代码证据：`upsert_skill_result` 写入 AIReport 表，非独立 finance_coach_cache 表）。This is a clarification, not a scope change.

---

**Next Step**: Plan ready. Proceed to `ce-work` for implementation, or `ce-doc-review` for plan review.
