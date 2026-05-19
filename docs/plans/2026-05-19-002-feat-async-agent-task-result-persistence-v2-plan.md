---
title: "feat: Async agent task result persistence v2 — task semantics + LLM fallback + circuit breaker"
date: 2026-05-19
status: active
origin: docs/brainstorms/2026-05-19-async-agent-task-result-persistence-v2-requirements.md
type: feat
scope: Standard
---

# feat: Async agent task result persistence v2

**Origin:** `docs/brainstorms/2026-05-19-async-agent-task-result-persistence-v2-requirements.md`
**Scope:** Backend + Frontend + (conditional) Agent skill_loader

---

## Problem Frame

四个 AI capability（alerts、disposal、spending_leak、allocation）的"重新扫描"按钮在生产环境表现为：流式 console 跑完 → console 折叠 → toast 提示"扫描完成" → **页面卡片仍空**。

一次优化（2026-05-17）已落地 `ai_result_parser.py`、`ai_result_writer.py`、`_ai_events_helper.py` 调度链与六份 `skills/custom/{capability}/SKILL.md`，但仍未真正解决问题。基于代码静态分析，二次失效点共五处（详见 origin §一次优化为何没解决）：

1. `_llm_fallback_extract` 是 stub（`ai_result_parser.py:194-232`）
2. `_ai_events_helper.py:103` 先 `complete_task` 再 parse/write，前端误把 completed 当结构化结果可用
3. 静默降级：parser 返回 None 仅 `logger.warning` 一行
4. regex 对 LLM 漂移格式（围栏、纯 JSON、带 markdown 标题）不容错
5. `skill_loader.py:127` 当 `base.prompt = ""` 时可能落到完全无 STRUCTURED_DATA 指令的 prompt

第 (2) 项是用户描述的"混淆了提交成功和真实完成的状态"的直接对应。

---

## Success Criteria

| Requirement | Acceptance |
|-------------|-----------|
| R1: Task 状态语义重定义 | `completed` 100% 等价于"结构化结果已落库（或经过 LLM fallback 后确认无可写数据）"；前端 `loadXxx()` 仅在 `completed` 时触发 |
| R2: LLM Fallback 真实现 + 三段式控制 | regex 失败 → fallback；1h/5 次 → 限流；24h/20 次 → 熔断；管理员可重置 |
| R3: Regex 容错 | 兼容 HTML 注释 / `\`\`\`json` 围栏 / 末尾纯 JSON 三种载体 |
| R4 (条件触发): SKILL.md prompt 真实生效 | 生产 raw answer 中可观察到 STRUCTURED_DATA 块；否则修复 `skill_loader.py:127` |
| R5: 可观测性 + 管理端干预 | `ai_extraction_audit` 表记录每次提取尝试；管理员页面新增「提取熔断」区块 |
| R6: 失败时保留 console 文本 | `capability.error` 不清空 think/answer 内容；显示红色警告条 + 重试按钮 |

---

## Scope Boundaries

### In scope
- Backend：
  - `server/apps/backend/app/services/ai_result_parser.py` — R2/R3 真实现 + 三段式控制
  - `server/apps/backend/app/routers/_ai_events_helper.py` — R1 状态语义切换
  - 新建 `server/apps/backend/app/models/ai_extraction_audit.py` — R2.4
  - 新建 `server/apps/backend/app/models/ai_extraction_circuit.py` — R2.6
  - 新建 `server/apps/backend/app/services/ai_extraction_circuit_service.py` — 计数 + 限流/熔断状态机
  - 新建 `server/apps/backend/app/routers/admin_ai_extraction.py` — 管理端审计 + 重置端点
  - Alembic migration：两张新表
- Frontend：
  - `frontend/apps/main/src/composables/useAITask.ts` — R1.3、R6.1、R6.4
  - `frontend/apps/main/src/components/ai/TaskConsole.vue` — R6.4 失败时不折叠 + 警告条
  - `frontend/apps/main/src/i18n/locales/zh-CN.ts` — 新增失败/限流/熔断 i18n key
  - 「模型管理」页面新增「提取熔断」区块（位置参考现有页面结构，规划阶段不锁路径）
- Agent（条件触发）：
  - `server/apps/agent/services/deerflow_adapter/skill_loader.py` — 仅当 R4 诊断证实 prompt 未生效时执行
- Tests：
  - 单元测试：parser/writer/circuit_service
  - 集成测试：四个 capability 的 stream → completed → GET 链路

### Deferred to Follow-Up Work
- report、liability 两个 capability 的二次优化（按用户指示，先稳定本次范围）
- 切换到 tool_calling / JSON mode（Approach B，留给三次优化）
- LLM fallback 的 metrics dashboard（Grafana / Prometheus 集成）

### Outside scope
- AI 问答 chat、time_machine 任意改动
- task queue / promote 机制重构
- NDJSON 协议格式重设计
- 前端 UI 重做

---

## Key Technical Decisions

**D1：`post_processing` 作为新 status 值，String column 不动迁移**
`AITask.status` 已经是 `String(20)`（见 `server/packages/db/models/ai_task.py:16`），新增字符串值无需 alembic enum migration。审计与监控可以清楚看到 task 处于"流已结束、正在落库"的中间态。前端在 `getAITask()` 返回 `post_processing` 时按 running 等价处理（依然显示 console），仅在 `completed` 时才触发 `onComplete`。

**D2：限流/熔断计数器走 SQL 时间窗口，不引入 Redis**
基于 `ai_extraction_audit` 表 `(family_id, capability, extracted_at)` 索引做 `COUNT(*) WHERE extracted_at > NOW() - INTERVAL`. 自托管原则下避免新增依赖；家庭级低频使用（每个家庭每天扫描 < 10 次）SQL 完全可控。每次扫描结束后做一次窗口查询写入 `ai_extraction_circuit.state`，扫描发起前读一次 `ai_extraction_circuit.state`。

**D3：`ai_extraction_audit` 单张全局表，无分区**
自托管 Numina 的家庭数量（个位数到几十）+ 扫描频率（每天个位数次）下，单表 `(family_id, capability, extracted_at)` 索引足够。如未来部署放大再考虑分区。

**D4：「提取熔断」管理端页面权限 = 现有 admin role**
复用 `ai_config.py` 中的 admin auth 模式（`require_admin` dep）。重置端点 `POST /admin/ai-extraction-circuit/reset` 写入 `manually_reset_at` 与 `reset_by_user_id`，便于审计。

**D5：R4 采用"先诊断再修复"两步走**
`skill_loader.py:127` 的修复成本不高，但风险是改动 prompt 链路时引入 chat / time_machine 等其他 capability 的回归。先在生产抓一份 raw answer 文本（通过 R5.3 增强后的 logger.error 自动落地）确认 STRUCTURED_DATA 是否真的从 LLM 出来，再决定是否需要修。U10 是"诊断步"，U11 是"条件修复步"——U11 仅在 U10 抓到无 STRUCTURED_DATA 块的样本时才执行。

**D6：失败时不调用 `onComplete` 但保留 think/answer 文本**
`useAITask.ts` 的 `handleEvent` 在 `capability.error` 时仅设置 `status='failed'` 并停止计时器，**不清空** `thinkContent.value` / `answerContent.value`。`TaskConsole.vue` 在 `failed` 状态时不折叠（移除当前的 `isConsoleOpen.value = false`），并渲染顶部红色警告条 + 重试按钮。

---

## High-Level Technical Design

### Task 状态机 (R1)

```
当前 (有 bug):
  running → [stream ends] → complete_task() → [parse/write] → 静默成功或静默失败 → frontend onComplete()
                                                                                      ↓
                                                                                  loadXxx() ← 这里看到空表

目标 (R1):
  running → [stream ends] → status=post_processing
                                  ↓
                            [parse + write 全成功] → status=completed → frontend onComplete()
                                  ↓
                            [parse 失败 → fallback 失败 / 限流 / 熔断]
                                  ↓
                            status=failed + capability.error 事件 → frontend 显示警告条
```

*This illustrates the intended approach and is directional guidance for review, not implementation specification.*

### 三段式 Circuit Breaker (R2.5/R2.6)

```
                  扫描请求到达
                       ↓
              读 ai_extraction_circuit.state
                       ↓
       ┌───────────────┼───────────────┐
       ↓               ↓               ↓
   state=ok      state=rate_limited  state=circuit_open
       ↓               ↓               ↓
    正常调用     opened_until>now?    路由层直接返回
    agent +       是→当 ok 处理       capability.error
    parser        否→regex 失败时
                    跳过 fallback
                        ↓
                   走 fail_task
```

阈值（D7 from origin）：
- 1h 内 fallback 触发 ≥ 5 次 → state=rate_limited，opened_until=now+30min
- 24h 内 fallback 触发 ≥ 20 次 → state=circuit_open，需手动重置
- circuit_open 优先级高于 rate_limited
- 状态转移在每次扫描结束后由 `circuit_service.evaluate(family_id, capability)` 统一计算

*This illustrates the intended approach and is directional guidance for review, not implementation specification.*

### Regex 容错（R3）

载体优先级（按序尝试，命中即返）：

1. `<!-- STRUCTURED_DATA\n…\n-->` — 当前协议，命中率最高
2. ` ```json\n…\n``` ` — markdown 围栏，部分模型默认输出
3. 末尾的纯 JSON（balanced 括号匹配，从最后一个 `[` 或 `{` 反向解析）

载体命中分布写入 `ai_extraction_audit.method`（regex_html / regex_fence / regex_bare / llm_fallback / failed）。

---

## Implementation Units

### U1. Migration: `ai_extraction_audit` & `ai_extraction_circuit` 两张新表

**Goal:** 建立可观测性 + 状态机的持久化基础。

**Requirements:** R2.4, R2.6, R5.1

**Dependencies:** none

**Files:**
- `server/apps/backend/app/models/ai_extraction_audit.py` (new)
- `server/apps/backend/app/models/ai_extraction_circuit.py` (new)
- `server/apps/backend/app/models/__init__.py` (export new models)
- `server/apps/backend/alembic/versions/<NNNN>_add_ai_extraction_audit_and_circuit.py` (new)

**Approach:**

`ai_extraction_audit` schema：
- `id` BigInteger PK (snowflake)
- `family_id` BigInteger, indexed
- `capability` String(32), indexed
- `task_id` String(64) nullable（关联 AITask.id；nullable 因为路由层熔断未起 task）
- `method` String(32) — `regex_html` / `regex_fence` / `regex_bare` / `llm_fallback_hit` / `failed`
- `extracted_at` DateTime(timezone) default now, indexed
- `error_msg` Text nullable
- `answer_excerpt` Text nullable（前 500 字脱敏样本，仅 method=failed 时填充，便于事后排查）
- composite index `(family_id, capability, extracted_at)`

`ai_extraction_circuit` schema：
- `id` BigInteger PK (snowflake)
- `family_id` BigInteger
- `capability` String(32)
- `state` String(20) default `ok` — `ok` / `rate_limited` / `circuit_open`
- `opened_at` DateTime nullable
- `opened_until` DateTime nullable（仅 rate_limited 状态使用；circuit_open 时为 NULL）
- `manually_reset_at` DateTime nullable
- `reset_by_user_id` BigInteger nullable
- `last_evaluated_at` DateTime
- unique constraint `(family_id, capability)`

**Patterns to follow:** `server/apps/backend/app/models/ai_task.py` 的 SQLAlchemy 2.0 mapped_column 模式；`server/packages/db/models/ai_task.py` 的 String column 实现。

**Test scenarios:**
- 迁移 up → 两张表存在，索引和 unique constraint 正确
- 迁移 down → 两张表干净删除，不留引用
- ORM 写入：插入 audit 记录，能按 (family_id, capability, extracted_at) 区间查询
- ORM 写入：同 (family_id, capability) 第二次插入 circuit → IntegrityError（unique 约束）

**Verification:**
- `cd server/apps/backend && uv run alembic upgrade head` 成功
- `uv run alembic downgrade -1 && uv run alembic upgrade head` 双向无错
- `uv run pytest server/tests/backend/test_ai_extraction_models.py -v` 通过

---

### U2. `ai_extraction_circuit_service.py`：状态机 + 计数

**Goal:** 提供 `evaluate(family_id, capability, db)`、`is_open(family_id, capability, db)`、`reset(family_id, capability, user_id, db)` 三个核心接口。

**Requirements:** R2.5, R2.6

**Dependencies:** U1

**Files:**
- `server/apps/backend/app/services/ai_extraction_circuit_service.py` (new)
- `server/tests/backend/test_ai_extraction_circuit_service.py` (new)

**Approach:**

```
class AIExtractionCircuitService:
    @staticmethod
    def is_open(family_id, capability, db) -> tuple[bool, str | None]:
        """在扫描请求发起前调用。返回 (是否阻塞, 阻塞原因)。"""
        # 读 ai_extraction_circuit
        # state=circuit_open → (True, "circuit_open")
        # state=rate_limited 且 opened_until > now → (True, "rate_limited")
        # state=rate_limited 且 opened_until <= now → 内部转回 ok 后返回 (False, None)
        # state=ok or 记录不存在 → (False, None)

    @staticmethod
    def evaluate(family_id, capability, db) -> str:
        """在每次扫描结束（成功 or 失败）后调用。返回新 state。"""
        # COUNT(*) FROM ai_extraction_audit
        #   WHERE family_id=? AND capability=? AND method='llm_fallback_hit'
        #     AND extracted_at > NOW() - INTERVAL '1 hour'
        # 若 ≥5 → state=rate_limited, opened_until=now+30min
        # COUNT(*) ... AND extracted_at > NOW() - INTERVAL '24 hours' → 若 ≥20 → state=circuit_open
        # 上锁顺序：先 24h 检查，再 1h 检查（circuit_open 优先级高于 rate_limited）
        # UPSERT ai_extraction_circuit by (family_id, capability)

    @staticmethod
    def reset(family_id, capability, user_id, db) -> bool:
        """管理员重置。state=ok, manually_reset_at=now, reset_by_user_id=user_id。"""
```

*This illustrates the intended approach and is directional guidance for review, not implementation specification.*

**Patterns to follow:** `server/apps/backend/app/services/ai_task_service.py` 的 staticmethod 服务类风格；现有 circuit-breaker 模式见 `BackendClient.report_circuit_event()` / `reset_circuit_success()` (search agent codebase for context — 已有 provider-level 熔断借鉴)。

**Test scenarios:**
- `is_open`：state=ok → (False, None)
- `is_open`：state=circuit_open → (True, "circuit_open")
- `is_open`：state=rate_limited 且 opened_until 已过期 → 自动恢复 ok 后返回 (False, None)
- `is_open`：state=rate_limited 且未过期 → (True, "rate_limited")
- `evaluate`：1h 内插入 4 条 llm_fallback_hit → state 仍为 ok
- `evaluate`：1h 内插入 5 条 llm_fallback_hit → state=rate_limited，opened_until ≈ now+30min
- `evaluate`：24h 内插入 20 条 llm_fallback_hit + 1h 内仅 4 条 → state=circuit_open（24h 优先）
- `evaluate`：24h 阈值未达且 1h 未达 → state=ok（已过期 rate_limited 自动归零）
- `reset`：state=circuit_open → 写入 manually_reset_at + reset_by_user_id，state=ok
- `evaluate`：并发同 (family_id, capability) 调用 → unique 约束 + UPSERT 不出错

**Verification:** `uv run pytest server/tests/backend/test_ai_extraction_circuit_service.py -v` 全绿；并发场景用 `pytest-asyncio` 的 gather 验证。

---

### U3. `ai_result_parser.py`：Regex 容错升级（R3）

**Goal:** 三种载体兼容 + 命中类型回填 method 字段。

**Requirements:** R3

**Dependencies:** none

**Files:**
- `server/apps/backend/app/services/ai_result_parser.py` (modify)
- `server/tests/backend/test_ai_result_parser.py` (extend existing)

**Approach:**
- 抽出 `_extract_structured_block(answer_text) -> tuple[str | None, str]` 返回 `(block_str, method_label)`
- 三个 regex 模式按优先级排序：`STRUCTURED_DATA` → ```json fence → balanced bare JSON
- 第三种载体的 balanced 括号实现：从字符串末尾反向扫描，找到最后一个 `{` 或 `[`，再正向 walk 直到括号 balanced 或 EOF；若 balanced 失败返回 None
- `parse_capability_result(...)` 返回 `tuple[list[dict] | dict | None, str]`，第二个元素是 method label，由调用方写入 audit 表

**Patterns to follow:** 当前 `STRUCTURED_DATA_PATTERN` 的 `re.DOTALL` 用法；保持其他 schema 校验不变。

**Test scenarios:**
- HTML 注释格式有效 JSON → method="regex_html"
- HTML 注释格式但内部 JSON 不合法 → 落到围栏匹配 → 围栏不匹配 → 落到 bare JSON → 都失败 → return (None, "regex_failed")
- ` ```json\n[...]\n``` ` 格式有效 → method="regex_fence"
- ` ```json\n{...}\n``` ` 格式（report 类对象）有效 → method="regex_fence"
- 末尾纯 `[{"asset_name":...}]` → method="regex_bare"
- 末尾 `{...}` 嵌套结构 → balanced 括号匹配后 method="regex_bare"
- 三种格式都不匹配 → return (None, "regex_failed")
- HTML 注释 + 围栏 + bare 三种都存在 → 命中第一个（HTML），method="regex_html"
- bare JSON 含有内部字符串里的 `}` → balanced 计数器不被字符串内 `}` 误导（实现需 string-aware 解析；test 用 `{"x": "}"}` 验证）

**Verification:** `uv run pytest server/tests/backend/test_ai_result_parser.py -v` 通过且新增 8+ 用例；现有测试不破坏。

---

### U4. `ai_result_parser._llm_fallback_extract` 真实现（R2.1–R2.3）

**Goal:** regex 失败时调用一次便宜模型抽取结构化数据。

**Requirements:** R2.1, R2.2, R2.3

**Dependencies:** U3

**Files:**
- `server/apps/backend/app/services/ai_result_parser.py` (modify)
- `server/tests/backend/test_ai_result_parser.py` (extend)

**Approach:**
- 删除当前 `_llm_fallback_extract` 中的 `# TODO`；保留 provider 选择逻辑（按 `display_order` 升序第一个 active 配置）
- 新增 `_build_extraction_prompt(capability, answer_text)` 返回模型 prompt：「以下是 {capability} 分析文本，请提取其中的结构化信息为 JSON，schema：{schema_dict}，仅输出 JSON 不输出任何解释」
- 调用 `LLMClient(provider=..., api_key=..., model_id=..., base_url=...)` 的 `complete(prompt, max_tokens=800, temperature=0.1)`，包 `asyncio.wait_for(..., timeout=5.0)`
- 返回值经 `json.loads` + `_validate_json(data, capability)` 校验
- 任意异常（超时、JSON 解析失败、schema 校验失败）→ return None
- `parse_capability_result` 升级为 async 函数，先 regex（U3），再 LLM fallback（本 unit），返回 `(data, method)`，method 可能是 `regex_html` / `regex_fence` / `regex_bare` / `llm_fallback_hit` / `failed`

**Execution note:** Test-first — fallback 调用是关键路径，先写"模型返回纯 JSON 成功"用例，再写超时、解析失败、schema 错误等错误路径。

**Patterns to follow:** `server/apps/agent/core/llm.py:LLMClient`（已存在的 provider abstraction，复用）；`apps.backend.app.services.ai_crypto.decrypt_api_key` 解密。

**Test scenarios:**
- LLM 返回有效 JSON 字符串 → method="llm_fallback_hit"，返回 data
- LLM 返回纯 JSON 但有 markdown 围栏（` ```json [...] ``` `）→ 内部用 U3 的容错二次清洗 → method="llm_fallback_hit"
- LLM 5 秒未返回 → asyncio.TimeoutError → return (None, "failed")
- LLM 返回非 JSON 文本 → json.loads 失败 → return (None, "failed")
- LLM 返回 JSON 但缺 required 字段 → schema 校验失败 → return (None, "failed")
- 家庭无 active provider config → return (None, "failed")，logger.warning
- API key 解密失败 → return (None, "failed")
- LLM 返回 schema=array 但 `{}`（类型不匹配）→ return (None, "failed")
- temperature 和 max_tokens 实际传入 LLMClient.complete()

**Verification:** `uv run pytest server/tests/backend/test_ai_result_parser.py::test_llm_fallback -v` 通过；mock LLMClient 验证 timeout=5、temperature=0.1、max_tokens=800 实际生效。

---

### U5. `_ai_events_helper.py`：Task 状态语义切换（R1.1, R1.2, R1.3）+ 三段式控制接入

**Goal:** 把 task.status 切换时机从"流结束"挪到"落库结束"；接入 circuit_service。

**Requirements:** R1.1, R1.2, R1.3, R2.5, R5.3

**Dependencies:** U1, U2, U3, U4

**Files:**
- `server/apps/backend/app/routers/_ai_events_helper.py` (modify)
- `server/apps/backend/app/services/ai_task_service.py` (modify — 新增 `mark_post_processing` 方法)
- `server/tests/backend/test_ai_events_helper.py` (new)

**Approach:**

```
proxy_capability_events(...):
    # 1. 流过程不变（继续 yield NDJSON）
    async for line in resp.aiter_lines():
        yield ...
    
    # 2. 流结束 → 切到 post_processing
    AITaskService.mark_post_processing(task_id, gen_db)
    
    # 3. 检查 circuit
    blocked, reason = AIExtractionCircuitService.is_open(family_id, capability, gen_db)
    if blocked:
        # rate_limited 且过期处理在 is_open 内已恢复；这里只处理实质阻塞
        AITaskService.fail_task(task_id, f"circuit_{reason}", gen_db)
        yield builder.error(f"AI 输出格式异常，{...}", code=reason).to_ndjson()
        return
    
    # 4. parse + 可能的 LLM fallback
    parser_result, method = await parse_capability_result(capability, answer, family_id, gen_db)
    
    # 5. 写 audit 表（fire-and-forget 异步）
    _fire_and_forget(write_extraction_audit(family_id, capability, task_id, method, ...))
    
    # 6. 更新 circuit state
    AIExtractionCircuitService.evaluate(family_id, capability, gen_db)
    
    # 7. 根据 method 决定 task 终态
    if parser_result is not None:
        write_capability_results(capability, family_id, parser_result, gen_db)
        AITaskService.complete_task(task_id, gen_db)
        # promote 下一个排队 task（保持现有逻辑）
    else:
        AITaskService.fail_task(task_id, "structured_extraction_failed", gen_db)
        yield builder.error("分析已完成，但结构化结果落库失败，请稍后重试", code="extraction_failed").to_ndjson()
        # promote 下一个排队 task
```

*This illustrates the intended approach and is directional guidance for review, not implementation specification.*

`AITaskService.mark_post_processing(task_id, db)` 新增方法，仅当 status='running' 时才允许切换到 'post_processing'，其他状态 noop。

`logger.error` 替代当前的 `logger.warning`，并在 method='failed' 时附带 `answer[:500]`（脱敏后）—— 调用 `pii_redactor.redact_text` 或现有的脱敏函数。

**Execution note:** 此 unit 的复杂度 + 跨 task / circuit / parser / writer 多方协作，建议先写集成测试覆盖"成功路径"和"regex 失败 + fallback 成功"两个主流，再补错误路径。

**Patterns to follow:** 当前 `_ai_events_helper.py` 的 try/finally + `gen_db` 模式；`_fire_and_forget` 用法见 `apps/agent/services/orchestrator.py:97`。

**Test scenarios:**
- 主路径：流结束 → mark_post_processing → regex 命中 → write_capability_results → complete_task；audit 表有一条 method=regex_html 记录；circuit state=ok
- 主路径变体：regex 失败 → llm_fallback_hit → write_capability_results → complete_task；audit method=llm_fallback_hit
- 失败路径：regex 失败 + fallback 失败 → fail_task("structured_extraction_failed")；NDJSON 末尾追加 capability.error；audit method=failed
- circuit_open 短路：扫描进入时 is_open 返回 True → fail_task；不调用 agent stream；NDJSON 仅含 capability.error（注：此场景实际由 router 层短路，本 unit 测的是 helper 内部的兜底）
- rate_limited 路径：has 5 fallback hits in 1h → 第 6 次扫描进入 helper → is_open=True → fail_task("rate_limited")
- task 状态迁移检查：mark_post_processing 只在 running 时生效；status=cancelled 时跳过
- 下一个排队 task 仍然 promote（不论本次成功或失败）
- audit 表写入是 fire-and-forget：写失败不阻塞主流程
- DB session 隔离：generator 用 gen_db，不复用 request 的 db
- logger.error 触发 + answer 前 500 字脱敏后落日志（mock pii_redactor 验证调用）

**Verification:** `uv run pytest server/tests/backend/test_ai_events_helper.py -v` 通过；用 `httpx_mock` 模拟 agent NDJSON 输入。

---

### U6. 管理端 Admin API：审计查询 + 重置

**Goal:** 暴露 `GET /admin/ai-extraction-audit` 与 `POST /admin/ai-extraction-circuit/reset`。

**Requirements:** R5.2, R5.4, D7 人工介入

**Dependencies:** U1, U2

**Files:**
- `server/apps/backend/app/routers/admin_ai_extraction.py` (new)
- `server/apps/backend/app/main.py` (register router)
- `server/tests/backend/test_admin_ai_extraction.py` (new)

**Approach:**

```
GET /admin/ai-extraction-audit
  query: family_id (optional), capability (optional), days (default 7), limit (default 100)
  auth: require_admin (现有 dep)
  返回: list of audit rows + 聚合统计 {regex_hit_pct, llm_fallback_pct, failed_pct}

GET /admin/ai-extraction-circuit
  auth: require_admin
  返回: list of (family_id, capability, state, opened_at, opened_until, last_evaluated_at)
        仅返回 state != 'ok' 的记录

POST /admin/ai-extraction-circuit/reset
  body: {family_id: str, capability: str}
  auth: require_admin
  调用 AIExtractionCircuitService.reset(family_id, capability, current_user.id, db)
  返回: {ok: True, reset_at: timestamp}
```

*This illustrates the intended approach and is directional guidance for review, not implementation specification.*

API 路径全部走 `""`（无尾部斜杠，遵循 CLAUDE.md 约定）；ID 字段按 SnowflakeBase 序列化为字符串。

**Patterns to follow:** `server/apps/backend/app/routers/ai_config.py` 的 admin 鉴权 + APIRouter 模式；`server/apps/backend/app/auth/deps.py:require_admin`。

**Test scenarios:**
- GET audit：admin 用户 + family_id=1 → 200，返回该家庭近 7 天 audit 记录
- GET audit：非 admin 用户 → 403
- GET audit：days=30 → 返回 30 天数据；聚合百分比正确
- GET circuit：admin 用户 → 仅返回 state != 'ok' 的记录
- POST reset：admin + 有效 (family_id, capability) → ok=True，DB 中 manually_reset_at + reset_by_user_id 已写入，state=ok
- POST reset：admin + (family_id, capability) 无对应 circuit 记录 → 创建一条 state=ok 记录
- POST reset：非 admin → 403
- POST reset：body 缺字段 → 422

**Verification:** `uv run pytest server/tests/backend/test_admin_ai_extraction.py -v` 通过；手动 cURL 验证响应结构。

---

### U7. 路由层接入 circuit 短路（4 个 capability router）

**Goal:** 扫描发起前先查 circuit 状态，circuit_open / 有效期内 rate_limited 直接返回 NDJSON capability.error，不调 agent。

**Requirements:** R2.5（短路逻辑）

**Dependencies:** U2

**Files:**
- `server/apps/backend/app/routers/ai_alerts.py` (modify)
- `server/apps/backend/app/routers/ai_disposal.py` (modify)
- `server/apps/backend/app/routers/ai_spending_leaks.py` (modify)
- `server/apps/backend/app/routers/ai_allocation.py` (modify)
- `server/tests/backend/test_ai_alerts.py` (extend；其他三个 capability 复用同模式)

**Approach:**

每个 router 的 `/refresh/events` 入口在 `AITaskService.get_running_task` 检查之后、`AITaskService.get_any_running_task` 之前插入：

```
blocked, reason = AIExtractionCircuitService.is_open(family_id, capability, db)
if blocked:
    return StreamingResponse(
        _yield_circuit_error_ndjson(capability, task_id="", reason=reason),
        media_type="application/x-ndjson",
    )
```

`_yield_circuit_error_ndjson` 是 `_ai_events_helper.py` 中新增的 helper，yield 一行 NDJSON `capability.error` 即结束。注意：这一路径不创建 AITask（无 task_id），因为没有真正发起任务。

**Patterns to follow:** 现有 `existing = AITaskService.get_running_task(...)` 短路模式。

**Test scenarios:**
- circuit state=ok：正常进入 task 创建 + agent 调用
- circuit state=rate_limited 且未过期：路由直接返回 NDJSON capability.error，无 task 创建
- circuit state=rate_limited 已过期：is_open 内部已转为 ok，正常进入主流程
- circuit state=circuit_open：路由直接返回 NDJSON capability.error，无 task 创建
- 4 个 capability 行为一致

**Verification:** 4 个 capability 各有一个测试用例，确保短路统一生效；`uv run pytest server/tests/backend/test_ai_alerts.py -v` 通过。

---

### U8. Frontend `useAITask.ts`：Task 状态语义对齐 + 失败保留文本（R1.3, R6.1）

**Goal:** 前端按 `completed` 触发 `onComplete`；`capability.error` 时保留 console 文本不清空。

**Requirements:** R1.3, R6.1, R6.5

**Dependencies:** U5（backend NDJSON 协议先稳定）

**Files:**
- `frontend/apps/main/src/composables/useAITask.ts` (modify)
- `frontend/apps/main/src/api/ai.ts` (modify — 扩展 `AITaskStatus.status` 类型)
- `frontend/apps/main/src/composables/__tests__/useAITask.test.ts` (new or extend)

**Approach:**
- `AITaskStatus['status']` 类型联合体增加 `'post_processing'`
- `consumeEventStream` 流结束时 **不再** 直接 `status.value = 'completed'`：改成"等待轮询确认"的中间态。具体方案：流结束时设置 `phase.value = null`、保留 `status='running'`，启动一次性的 `pollOnce()` 调 `getAITask()`：
  - 返回 `post_processing` → 100ms 后再轮询，最多 30 次（共 3s 上限）
  - 返回 `completed` → 设置 `status='completed'` + 调 `onComplete()`
  - 返回 `failed` / `timeout` → 设置 `status='failed'`，保留 think/answer 文本
  - 超过 3s 仍 `post_processing` → 视为 failed，提示「结构化结果处理超时」
- `handleEvent('capability.error')`：
  - 设置 `status.value = 'failed'`
  - **不**清空 `thinkContent.value` / `answerContent.value`
  - 解析 event.code 字段：`circuit_open` / `rate_limited` / `extraction_failed` / 其他，通过 i18n 显示对应 toast
  - 不调 `onComplete?.()`
- 暴露新字段 `errorCode: ref<string | null>` 给页面用于条件渲染重试按钮 / 警告条

**Execution note:** 前端逻辑改动不算多但跨多个事件分支，先写"capability.error 进入 → status=failed + 保留文本"的 vitest 单元测试再改逻辑。

**Patterns to follow:** 现有 `useAITask` 的 `handleEvent` switch 风格；`startPolling` / `stopPolling` 的轮询模式。

**Test scenarios:**
- 流正常结束 + 后端 1s 内返回 completed → status='completed'，onComplete 调用一次
- 流结束 + 后端连续 5 次返回 post_processing 后 completed → status 在中间态保持 running，最后 completed，onComplete 仅调一次
- 流结束 + 后端持续返回 post_processing 超过 3s → status='failed'，不调 onComplete
- 流末尾 capability.error code='extraction_failed' → status='failed'，thinkContent/answerContent 保留，不调 onComplete
- 流末尾 capability.error code='rate_limited' → status='failed'，errorCode='rate_limited'
- 流末尾 capability.error code='circuit_open' → status='failed'，errorCode='circuit_open'
- 用户在 post_processing 中点击 cancel → cancelTask 正常执行，停止轮询
- visibilitychange 切走又回来：post_processing 中也能恢复轮询

**Verification:** `cd frontend/apps/main && npm run test:run -- useAITask` 通过。

---

### U9. Frontend `TaskConsole.vue` + 4 个页面：失败时保留 console + 警告条 + 重试（R6.4, R6.5）+ 模型管理熔断区块（R5.4）

**Goal:** failed 状态下 console 不折叠；警告条 + 重试按钮；新增「提取熔断」管理区块。

**Requirements:** R6.4, R6.5, R5.4

**Dependencies:** U6（admin API）, U8（status='failed' 信号）

**Files:**
- `frontend/apps/main/src/components/ai/TaskConsole.vue` (modify — failed 状态 prop 渲染)
- `frontend/apps/main/src/pages/AIAlertsPage.vue` (modify — 接 errorCode + retry handler)
- `frontend/apps/main/src/pages/AIDisposalPage.vue` (modify — 同上)
- `frontend/apps/main/src/components/ai/SpendingLeaksCard.vue` (modify — 同上)
- `frontend/apps/main/src/pages/AIAllocationPage.vue` (modify — 同上)
- `frontend/apps/main/src/i18n/locales/zh-CN.ts` (add keys: `aiTask.extractionFailed`, `aiTask.rateLimited`, `aiTask.circuitOpen`, `aiTask.retry`, `aiAdmin.extractionCircuitTitle`, `aiAdmin.resetCircuitBtn`, ...)
- `frontend/apps/main/src/pages/admin/AIConfigPage.vue` (or wherever「模型管理」实际在 — 规划阶段不锁路径) (modify — 嵌入熔断区块)
- `frontend/apps/main/src/components/admin/ExtractionCircuitSection.vue` (new — 熔断列表 + 重置按钮)
- `frontend/apps/main/src/api/aiAdmin.ts` (new or extend — 调用 admin endpoints)

**Approach:**
- `TaskConsole.vue`：新增 `errorCode?: string | null` prop；当 `status === 'failed'` 时不折叠（不内部 emit `update:modelValue` 把 isConsoleOpen 切回 false），并在顶部渲染红色警告条；emit `retry` 事件供父组件监听
- 4 个页面对应：`<TaskConsole ... :error-code="errorCode" @retry="onRefresh" />`；onRefresh 已存在
- 警告条文案分支（i18n）：
  - `extraction_failed` → 「⚠️ 分析已完成，但结构化结果落库失败，可参考上方文本」
  - `rate_limited` → 「⚠️ AI 输出格式异常，已暂停自动修复 30 分钟」
  - `circuit_open` → 「⚠️ 该功能已被熔断保护，请联系管理员重置」
- `ExtractionCircuitSection.vue`：调用 `getExtractionCircuit()` 列出非 ok 的 (family, capability) 对，每行有「重置」按钮调 `resetExtractionCircuit({ family_id, capability })`，重置成功后刷新列表 + toast「✅ 已重置」

**Patterns to follow:** 现有 TaskConsole.vue 的 props/emits 风格；现有 admin 页面的 vant 列表 + 操作按钮模式（参考 `AIConfigPage.vue` 的 provider 列表）。

**Test scenarios:**
- TaskConsole 在 status='failed' 时不折叠，渲染红色警告条
- TaskConsole 在 status='failed' + errorCode='circuit_open' 时显示对应文案
- 点击「重试」按钮 emit retry 事件
- AIAlertsPage 接收 retry 事件后调 startStream 重新发起
- ExtractionCircuitSection 加载时调 GET API 并渲染列表
- 列表项「重置」按钮点击 → POST API → 成功后从列表移除该行 + toast
- 重置失败 → 显示错误 toast，列表保留
- 所有新增 i18n key 在 zh-CN.ts 中存在（无硬编码中文）

**Verification:** `cd frontend/apps/main && npm run test:run -- TaskConsole` + `npm run test:run -- ExtractionCircuitSection` 通过；手动验证四个 capability 页面失败状态显示正确。

---

### U10. R4 诊断步：生产 raw answer 抽样验证（必做）

**Goal:** 通过 R5.3 增强后的 logger.error 在生产收集一份 method='failed' 时的 raw answer 样本，确认 STRUCTURED_DATA 块是否真的从 LLM 出来。

**Requirements:** R4 触发条件

**Dependencies:** U5（logger.error + audit answer_excerpt 已落地）

**Files:**
- `docs/solutions/test-failures/2026-05-19-extraction-failure-samples.md` (new — 收集样本 + 决策记录)

**Approach:**
- U1–U9 全部上线后，让生产运行 1-3 天（取决于扫描频率）
- 通过 `GET /admin/ai-extraction-audit?days=3&limit=100` 取近 3 天 method=failed 或 llm_fallback_hit 的记录
- 抽 5-10 个样本，检查 `answer_excerpt` 字段：
  - 若文本中能搜到 `STRUCTURED_DATA` 字符串（即使格式漂移）→ prompt 是生效的，**U11 不必做**
  - 若 5 个样本都完全没有 STRUCTURED_DATA 字样 → prompt 没有真正进入 LLM，**U11 必做**
- 写决策记录到 `docs/solutions/test-failures/`

**Test scenarios:** N/A（诊断步，无代码测试；产物是决策文档）

**Verification:** 决策文档存在并明确 U11 是 GO 还是 NO-GO。

---

### U11. (条件触发) `skill_loader.py:127` Prompt 内容生效修复（R4）

**Goal:** 仅当 U10 诊断证实 prompt 未生效时执行；修复 SkillLoader 把 SKILL.md 的 markdown body 真正传到 DeerFlow。

**Requirements:** R4.1, R4.2

**Dependencies:** U10（诊断结论为 GO）

**Files:**
- `server/apps/agent/services/deerflow_adapter/skill_loader.py` (modify)
- `server/apps/agent/tests/unit/test_skill_loader.py` (extend)

**Approach:**
- 在 `SkillLoader.load()` 里读 `skills/custom/{capability}/SKILL.md` 的 markdown body（frontmatter 之后的内容）填入 `SkillConfig.prompt`
- 当前 line 75 的 `prompt=""` 改为 `prompt=_load_custom_skill_body(capability)`
- `_load_custom_skill_body(capability) -> str`：路径 `SKILLS_DIR / "custom" / capability / "SKILL.md"`，读 frontmatter 之后的内容；文件不存在或解析失败 → 返回 `""` 并 logger.warning
- `load_for_family` 的逻辑保持："家庭有自定义 prompt 用自定义；否则用 base.prompt"（base.prompt 现在是真实的 SKILL.md body）
- 最关键：要确认 DeerFlow harness 在 SkillConfig.prompt 非空时如何使用 prompt —— 这部分需要在 U11 时再做一次源码确认（DeerFlow 自己有 prompt 加载链路，可能与 SkillConfig.prompt 重复）。如确认 harness 自己已加载 SKILL.md，本 unit 退化为"只在 family 自定义 prompt 时生效"的边界修复，避免双加载冲突

**Patterns to follow:** `skill_loader.py` 现有的 `_FRONTMATTER_RE` 正则；`SKILLS_DIR` 路径解析。

**Test scenarios:**
- 加载 alerts skill：`prompt` 字段非空，包含 `STRUCTURED_DATA` 字串
- 加载不存在的 capability：prompt=""，logger.warning 触发，不抛异常
- per-family override：family 配置了 custom_prompt → effective_prompt 用 custom；family 未配置 → 用 base.prompt（即 SKILL.md body）
- frontmatter-only 文件（如当前的 chat.md）：prompt=""（无 body），不抛异常
- 缓存：load 同一 capability 两次只读文件一次

**Verification:**
- `cd server/apps/agent && uv run pytest tests/unit/test_skill_loader.py -v` 通过
- 集成层：手动触发 alerts 扫描，从 R5.3 的日志看 raw answer 是否包含 STRUCTURED_DATA
- 回归：chat 与 time_machine 的 stream 行为不变（不用 SKILL.md body 的路径不破坏）

---

### U12. End-to-end 验证 + 4 个 capability 烟囱测试

**Goal:** 完整链路 stream → post_processing → completed → GET 返回非空数据；4 个 capability 都通过。

**Requirements:** Success Criteria #1, #3

**Dependencies:** U1–U9（U10/U11 不阻塞，按 U10 结果分支）

**Files:**
- `server/tests/backend/test_e2e_async_capabilities.py` (new — 4 个 e2e 测试)

**Approach:**
- 每个 capability 一个测试：
  1. 用 `httpx_mock` 模拟 agent NDJSON 输出，包含 thinking + answering token + 末尾 STRUCTURED_DATA 块
  2. POST `/ai/{capability}/refresh/events`
  3. 消费 NDJSON 直到 `capability.end`
  4. 轮询 `/ai/tasks/{capability}` 直到 `status=completed`
  5. GET `/ai/{capability}` 验证返回非空列表
  6. 验证 audit 表有 method=regex_html 的一条记录
- 第二个变体：mock agent 输出无 STRUCTURED_DATA，但 LLM fallback mock 返回有效 JSON → 验证 completed + GET 非空 + audit method=llm_fallback_hit
- 第三个变体：fallback 也失败 → status=failed + GET 空 + audit method=failed

**Test scenarios:**
- alerts e2e 主路径
- disposal e2e 主路径
- spending_leak e2e 主路径
- allocation e2e 主路径
- 任一 capability fallback 命中路径
- 任一 capability extraction 全失败路径

**Verification:** `uv run pytest server/tests/backend/test_e2e_async_capabilities.py -v` 全绿。

---

## Sequencing

```
U1 (migration: audit + circuit tables)
  └─ U2 (circuit_service)
       ├─ U6 (admin API)
       └─ U7 (router circuit short-circuit)

U3 (regex 容错) — independent
  └─ U4 (LLM fallback)
       └─ U5 (events helper: status semantics + circuit hookup)
            ├─ U8 (frontend useAITask)
            │    └─ U9 (TaskConsole + pages + admin section)
            ├─ U10 (诊断步 — 上线后跑)
            │    └─ U11 (条件触发: skill_loader 修复)
            └─ U12 (e2e 验证)

并行轨：
  Track A: U1 → U2 → {U6, U7}
  Track B: U3 → U4 → U5
  Track C: U5 → U8 → U9
  Track D: U5 → U10 → (U11 conditional)
  Track E: U5+U6+U7+U9 → U12
```

PR 拆分建议：
- **PR 1**：U1 + U2 + U6 + U7（DB 基础设施 + admin API + 路由短路；不影响现有行为）
- **PR 2**：U3 + U4（parser 升级；纯 backend 内部改动）
- **PR 3**：U5（events helper 切语义；这是行为转变的 PR，单独评审）
- **PR 4**：U8 + U9（前端 + i18n + 管理端区块）
- **PR 5**：U12（e2e 测试落地）
- **后续 PR**（U10 诊断 + U11 条件修复）：上线 1-3 天后再决定

---

## Risks

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|-----------|
| LLM fallback 调用增加 1-3s 延迟，前端轮询超时 3s 判 failed | Medium | High | U8 把超时上调到 8s（>5s LLM 超时 + 缓冲）；U5 fallback 异步进行，audit 写入 fire-and-forget |
| 三段式状态机的 SQL 时间窗口查询慢 | Low | Medium | `(family_id, capability, extracted_at)` 复合索引必备；自托管低 QPS 场景下完全可控 |
| `mark_post_processing` 与 `cancel_task` 的并发竞争 | Low | Low | `mark_post_processing` 仅在 `running` 时切换，`cancel_task` 在任意状态下都可终止 |
| frontend 轮询风暴（用户多 tab 同时打开同 capability） | Low | Medium | 复用现有 `POLL_INTERVAL_MS=3000` 节流；后端 `get_running_task` 已有去重 |
| U11 修复 SKILL.md 加载链路时破坏 chat / time_machine | Medium | High | U11 必须先确认 DeerFlow harness 自己的加载链路；测试覆盖到 chat 与 time_machine 的回归 |
| audit 表快速膨胀（每次扫描写一行） | Low | Low | 自托管小流量；如必要后续加 7 天 TTL 清理 cron |
| circuit_open 状态被恶意触发（family 内某成员故意触发 LLM 失败 20 次） | Very Low | Low | admin 重置 + 审计 reset_by_user_id 留痕；按家庭维度隔离不影响其他家庭 |

---

## Deferred Implementation Notes

- `_yield_circuit_error_ndjson` 的具体函数位置（`_ai_events_helper.py` 还是新文件）：实现时决定，避免循环引用
- audit 表 `answer_excerpt` 的脱敏粒度：实现时复用 `pii_redactor.redact_text` 现有逻辑，不再单独设计
- 「模型管理」页面的具体路径：U9 实现时通过 router config 确认（`frontend/apps/main/src/router/index.ts`）
- DeerFlow harness 是否已经自加载 `skills/custom/*/SKILL.md`：U11 实现前必须 grep `vendor/deerflow-harness/` 确认；如已自加载，U11 退化为"仅修复 family override 边界"
- alembic migration 文件名 `<NNNN>` 的具体序号：实现时按 `alembic history` 当前最新版本递增
- e2e 测试的 mock 工具选择（`httpx_mock` vs `respx`）：U12 实现时按现有 backend 测试约定选择
- audit 写入是否需要批量化：自托管低 QPS 场景下单条 INSERT 即可；如未来流量上来再批量

Plan written to /Users/vincentruan/geek_space/github/numina/docs/plans/2026-05-19-002-feat-async-agent-task-result-persistence-v2-plan.md
