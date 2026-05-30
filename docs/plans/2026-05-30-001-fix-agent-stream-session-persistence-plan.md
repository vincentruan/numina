---
title: 'fix: Persist title/summary/journal on agent-first stream path'
type: fix
created: 2026-05-30
status: active
plan_depth: lightweight
reviewed: 2026-05-30
---

## Summary

修复 `/agent/{agent_id}/stream` 路径（`stream_agent_dispatch`）未持久化会话元数据导致前端列表全显示"未命名会话"的缺陷。DeerFlow `TitleMiddleware` 已经无条件挂在 `make_lead_agent()` 中间件链里且默认启用（doc-review 阶段直接读 vendored harness 源码 `agent.py:284` 与 `title_config.py:9` 确认）—— 我们只要在流式完成后用 `agent_graph.aget_state(...)` 读出 `state.values.title`、过 `pii_redactor.redact_text` 后同步回 backend `ai_chat_sessions` 表；同时补齐 summary、status 与 agent journal jsonl 写入，使 `GET /api/v1/ai/sessions` 列表与 `/sessions/{id}/events` 回放对所有 agent 路径会话生效。

不改前端、不改 DB schema、不改旧的 `/chat/ask/stream` 路径行为。

---

## Problem Frame

### 当前现象

前端 `AIChatPage` 历史会话列表（`AIChatPage.vue:95`）每条都显示 `t('aiChat.untitledSession')` 兜底文案，因为 `GET /api/v1/ai/sessions` 返回的 `title` 字段始终为 `null`。

### 根因

`stream_agent_dispatch`（`server/apps/agent/services/agent_dispatch.py:191`）是当前前端发起带 `agent_id` 对话时实际跑的执行入口，但它**只 emit NDJSON 事件、不更新 backend 会话表**。具体缺失：

| 持久化动作 | 旧 chat 路径 (`orchestrator._stream_dispatch_event_lines`) | 新 agent 路径 (`stream_agent_dispatch`) |
|---|---|---|
| `_upsert_session`（session 元数据） | ✅ 第 829 行 fire-and-forget | ❌ |
| `_update_session_summary`（summary, status, last_model） | ✅ 第 907 行 | ❌ |
| `_generate_title`（标题） | ✅ 第 921 行 fire-and-forget | ❌ |
| `session_journal.write_user_message` | ✅ 第 823 行 | ❌ |
| `session_journal.write_assistant_message` | ✅ 第 893 行 | ❌ |
| `session_journal.write_session_start/end` | ✅ | ❌ |

后端 `chat_stream`（`server/apps/backend/app/routers/ai_chat.py:234`）在 `body.agent_id` 存在时一律转发到 `/agent/{agent_id}/stream` —— 而前端 `numina` 是 system agent、自定义 agent 也都带 `agent_id`，所以**新建会话 100% 走这条没持久化逻辑的路径**。

### 修复目标

让 `stream_agent_dispatch` 在流式完成后做四件事，全部 fire-and-forget，不阻塞流式输出：

1. 读 DeerFlow `state.values.title`（由内置 `TitleMiddleware` 生成），fallback 到「日期+agent_name+用户名」格式。
2. 调用 backend `update_session_summary` 持久化 `title` + `summary[:200]` + `status`。
3. 写 `session_journal.write_user_message / write_assistant_message / write_session_end`。
4. 失败静默：标题/journal 写入失败不影响主流程。

---

## Scope Boundaries

### In Scope

- `server/apps/agent/services/agent_dispatch.py`：重构 try/finally 控制流 + 持久化逻辑（含 PII redaction）
- `server/apps/agent/services/session_journal.py`：新增公开 `resolve_path` 方法
- `server/apps/agent/tests/integration/test_titlemiddleware_wiring.py`：U1 pre-flight 验证（新增）
- `server/apps/agent/tests/unit/test_agent_dispatch.py`：U2/U3 单测（新增）
- `server/apps/agent/tests/integration/test_agent_dispatch_persistence.py`：U4 集成测试（新增）

### Out of Scope

- 前端改动（`title` 字段已经在用）
- DB schema 变更（`ai_chat_sessions.title` 列已经存在）
- `deerflow_config/base/config.yaml` 修改 —— TitleMiddleware 已经无条件激活（doc-review 验证），无需启用配置
- `/chat/ask/stream` 旧路径的标题生成逻辑（保留 `orchestrator._generate_title`，等旧路径下线再清理）

### Deferred to Follow-Up Work

- **统一两条路径**：让 `orchestrator._stream_dispatch_event_lines` 也改读 `state.values.title`，删除 `_generate_title` 里的独立 LLM 调用。需要对 `DeerFlowAdapter` 暴露 `get_state(thread_id)` 接口，改动面比当前修复大，单独排期。本计划落地后双路径会并行存在一段时间，标题相关改动需要双写两处——已记入 Open Questions。
- **历史 untitled 会话回填**：当前已存在的 `title=NULL` 记录不在本计划覆盖。可以用一次性脚本扫表 + 调用 LLM 摘要，但属于运维任务而非缺陷修复。

---

## Key Technical Decisions

### 决策 1：复用 DeerFlow `TitleMiddleware`，不再在 agent 层调 LLM

**Why**：根 CLAUDE.md 与 `agent/CLAUDE.md` 都明令禁止重复实现 DeerFlow 已有能力（`Orchestrator` / `MemoryManager` 等）。`TitleMiddleware` 在 `_build_middlewares()` 里**无条件**追加到 `make_lead_agent()` 的中间件链（vendored harness `backend/packages/harness/deerflow/agents/lead_agent/agent.py:284`），`TitleConfig.enabled` 默认 `True`（`title_config.py:9`），首轮 `after_model` / `aafter_model` 钩子触发 LLM 摘要写入 `state["title"]`，由 `SqliteSaver` checkpointer 自动持久化（参考 `_should_generate_title` guard `title_middleware.py:69-89`，再次调用会直接 short-circuit）。

**Trade-off**：DeerFlow 的 prompt 是英文的，可能需要在配置里覆盖 `model_name` 让中文回复用中文标题。先用默认看效果，必要时再补 prompt 配置（DeerFlow 支持自定义 `title_config.prompt_template`）。

### 决策 2：标题来源优先级 = `state.values.title` > 日期模板 fallback

**Why**：
- chat 类对话（agent.skills == `["chat"]` 或 `["*"]`）→ TitleMiddleware 会生成有意义的 LLM 摘要
- 业务流程化 agent（自定义 agent 跑固定 capability）→ 输出文本通常是结构化结果（资产体检报告之类），LLM 摘要质量低，沿用现有 `日期+agent_name+用户名` 模板更可读

判定依据：`state.values.title` 为空 → 走 fallback。不需要前置判断 agent 类型。

### 决策 3：复用 orchestrator 的 `_fire_and_forget` helper，不直接 `asyncio.create_task`

**Why**：
- `stream_agent_dispatch` 是 `async def` generator，被 FastAPI 的 `StreamingResponse` 包裹。客户端断开或异常 close 时 generator 会被 `aclose()`，`asyncio.create_task` 创建的 task 会被 owner loop 调度但**只有 finally 块真的执行了**才会被创建。
- `services/orchestrator.py:187-196` 已有 `_fire_and_forget(coro)` 实现：在 module-level event loop 上 schedule 并附加 done-callback。直接 `from apps.agent.services.orchestrator import _fire_and_forget` 复用（`agent/CLAUDE.md` 没禁止 agent_dispatch 反向 import orchestrator helpers）。
- **`try/finally` 必须包整个 `stream_agent_dispatch` 函数体（在 `thread_id` 确定之后）**，覆盖当前所有 10+ 个早返回路径（agent_dispatch.py 222/229/233/265/273/298/310/329/347/355/449），不能只包 `astream` 循环。
- 失败用 `logger.warning` 吞掉（**只 log `type(e).__name__` 与 `session_id`，不 log `str(e)`** —— `aget_state` 的异常 payload 可能含完整 state 字典）。

### 决策 4：所有持久化字段都过 `pii_redactor`

**Why**：`agent/CLAUDE.md` Key Invariant #1：「Always call `pii_redactor.redact()` on `FamilyContext` before passing data to any LLM call or writing to logs.」
- 旧 chat 路径（orchestrator）`title` 输入用的是 `redacted_free_text`，`summary` 写的是 `redacted_answer[:200]`。
- 新 agent 路径**必须保持同等保护**：`pii_redactor.redact_text(state.values.title)` 后再持久化，`pii_redactor.redact_text("".join(answer_parts))[:200]` 写 summary，journal 的 `write_assistant_message` 同样写 redacted 文本。

### 决策 5：保留 orchestrator `_generate_title` 不动

**Why**：`/chat/ask/stream` 旧路径还有兼容客户端在用（前端不带 agent_id 时的 fallback），而该路径用的是 `DeerFlowAdapter.stream_dispatch`，不直接持有 LangGraph graph 句柄，没法直接 `aget_state`。两条路径的统一留作 follow-up（见 Deferred）。

### 决策 6：U2 显式给 `agent_graph` 绑定 shared checkpointer（U1 验证驱动）

**Why**：U1 step 1 实测 fail —— `make_lead_agent(runnable_config)` 返回的 `CompiledStateGraph` `.checkpointer` 为 `None`。原因是 vendored harness `agents/lead_agent/agent.py:434-446` 调 `create_agent(...)` 时**没传 `checkpointer=` kwarg**，而 agent_dispatch 也不像 `DeerFlowClient._create_agent`（`client.py:242-248`）那样在 fallback 到 `get_checkpointer()` —— 所以这条路径上 graph 永远是 stateless 的，对应 `aget_state` 必抛 `ValueError("No checkpointer set")`。

**Decision**：U2 在 `make_lead_agent(...)` 返回后、`astream` 之前**直接 post-hoc 赋值 `agent_graph.checkpointer = _get_shared_checkpointer()`** —— 复用 orchestrator 路径已经在用的 `apps.agent.services.deerflow_adapter.family_adapter_cache._get_shared_checkpointer()`（同一个 SqliteSaver 实例 + 同一个 db 文件）。

**Why post-hoc 而不是 fork harness**：
- 实测 `CompiledStateGraph.checkpointer = saver` 直接生效（`langgraph 1.x`），无需重新 compile。
- fork `make_lead_agent` 加一个 kwarg 等于把 vendored harness patch 化，违反 root CLAUDE.md「禁止重新实现 DeerFlow 已有能力」原则。
- 共享 checkpointer 与 orchestrator 路径用同一个实例，意味着两条路径 thread_id 命名空间一致 —— 同一个 session_id 在两条路径间切换时（见 Open Questions #1）状态可读。

**Trade-off**：依赖 `CompiledStateGraph.checkpointer` 是 settable 属性这一 langgraph 内部约定。如果未来 langgraph 升级把它改成 immutable，需要回到 `create_agent(checkpointer=...)` 调用路径 —— 那时候要 fork `make_lead_agent` 或者通过 monkeypatch `create_agent` 注入。U2 测试需要包含一个 regression assert：`agent_graph.checkpointer is shared` 验证赋值生效；如果该 assert 在 langgraph 升级时 fail，会立刻定位到这个假设。

---

## Decisions Considered and Rejected

### 替代方案：标题生成放后端 `proxy_stream` finally

Adversarial reviewer 提出：后端 `server/apps/backend/app/routers/ai_chat.py:294-305` 的 `proxy_stream` finally 已经有 SessionLocal、`session_id`、`current_user`、`answer_chunks`、`ai_config`，在那里加 `_generate_title` 可以一文件搞定，避开 DeerFlow 配置 / `aget_state` / fire-and-forget 生命周期讨论。

**Reject 理由**：
- backend 当前**只是个反向代理**——不持有任何 LLM client、不知道家庭 AI 配置的 prompt 风格、不和 DeerFlow 状态共存。在 backend 调 LLM 等于把 agent service 的责任倒灌回 backend，违反根 CLAUDE.md `Import direction` 原则（agent 服务应该自包含决策）。
- 后端真要写标题，仍然得调 agent 的某个 endpoint（HTTP 来回一次），增加了一跳网络开销且必须新增内部接口。
- agent 已经持有 LangGraph graph 句柄、checkpointer、`state.values`，**reading is free**——硬要绕开它去后端再调一次 LLM 反而更贵。

但 adversarial 的另一个 concern 是合理的：**backend `proxy_stream` finally 已经在调 `ChatSessionService.append_message`，这条会写 `last_message_summary` / `message_count` / `updated_at`**，与新计划的 `update_summary` 在同样的列上写。这是真实的 race，下面 Risks 表加一行。

---

## Implementation Units

### U1. Pre-flight: 验证 TitleMiddleware 与 checkpointer 已经接通

**Goal**: 在动 U2/U3 业务代码之前，确认两个 load-bearing 假设在当前 deploy 配置下成立——否则 U2 的 `aget_state` 会静默抛 `ValueError("No checkpointer set")`、`state.values.title` 会一直为空、整个修复在生产无声失效。

**Dependencies**: 无（这是 verification gate，不写业务代码）

**Files**:
- 无生产代码修改
- 新增 `server/apps/agent/tests/integration/test_titlemiddleware_wiring.py` — 一次性 verification 测试

**Approach**:

写一个 `pytest -m integration` 标记的测试，做这两件事：

1. **验证 checkpointer 接通**：构造典型 `app_config_dict`（含 `{"checkpointer": {"type": "sqlite", "connection_string": ":memory:"}}`），调 `AppConfig.model_validate(...)` → `make_lead_agent(runnable_config)`，断言 `agent_graph.checkpointer is not None`。如果是 None，说明 `EffectiveConfigBuilder.build()` 的 checkpointer 字段被 harness 内部丢弃，需要改用 `runnable_config["configurable"][CONFIG_KEY_CHECKPOINTER]` 注入路径——这个发现会改变 U2 设计。

2. **验证 TitleMiddleware 在链里**：上一步拿到的 `agent_graph`，反查 `agent_graph.builder` 或 `agent_graph.middleware`（具体 introspection API 需要看 LangChain `create_agent` 输出形态），断言中间件列表含 `TitleMiddleware` 实例。Context7 `/bytedance/deer-flow` 标注它在 `_build_middlewares` 默认链里，但 vendored harness 版本（`uv.lock` 里 git ref）可能滞后——必须实测。

3. **验证 `aget_state` 端到端**：跑一轮真实 stream（mock LLM 返回固定文本），完成后调 `agent_graph.aget_state(runnable_config)`，断言 `state.values` 非空且 `"title"` 字段存在（哪怕为 `None` 也行——只要 schema 接得通）。

**Patterns to follow**:
- `tests/integration/` 现有测试的 fixture 风格

**Test scenarios**:
- 上述三步本身就是测试体；测试 pass 才允许动 U2
- 如果 step 1 fail：U2 设计需要改用 `runnable_config["configurable"][CONFIG_KEY_CHECKPOINTER]` 注入，并把这个改动也加进 U2
- 如果 step 2 fail：TitleMiddleware 没在链里，U2 必须显式注册它（可能要改 EffectiveConfigBuilder 注入 middleware list 或自己写 `_register_title_middleware` helper）—— 这是 plan-pivoting 级别的发现，必须先暂停回到 plan
- 如果 step 3 fail 但 step 1/2 pass：说明 Title 生成或 state 读取有 subtle issue，到时再 debug

**Verification**: `uv run pytest apps/agent/tests/integration/test_titlemiddleware_wiring.py -v` 全绿。

**Actual gate result (2026-05-30, run on `feat/ai-agent-refactor`)**:

| Step | Result | Implication |
|---|---|---|
| 1. checkpointer attached | ❌ FAIL | `make_lead_agent(...).checkpointer is None`. Vendored harness `agents/lead_agent/agent.py:434-446` calls `create_agent(...)` without `checkpointer=`; agent_dispatch also doesn't fallback to `get_checkpointer()` like `DeerFlowClient._create_agent` does. → **U2 plan-pivot triggered**: 决策 6 added — post-hoc assign `agent_graph.checkpointer = _get_shared_checkpointer()` after `make_lead_agent` returns. Verified `CompiledStateGraph.checkpointer` is settable post-compile. |
| 2. TitleMiddleware in chain, default enabled | ✅ PASS | `_build_middlewares(...)` contains exactly one `TitleMiddleware` instance and `_get_title_config().enabled is True`. Confirms harness reality matches plan claim. |
| 3. aget_state end-to-end | ⚠️ INCONCLUSIVE | Failed earlier inside `astream` for an unrelated reason: `ThreadDataMiddleware.before_agent` accessed `runtime.context.get("run_id")` and got `AttributeError: 'NoneType' object has no attribute 'get'`. Test fixture's `runnable_config` doesn't seed `context`. Real production path constructs `runnable_config` differently — agent_dispatch.py:331 doesn't seed context either, but real LangGraph runtime likely fills it. **Action**: U2 must include a real-graph integration test (covered by U4) that doesn't rely on the U1 fixture's minimal stub; the U1 step-3 stub is left in place but its scope narrowed to "validate `aget_state` returns a `StateSnapshot` whose `.values` dict contains the `title` schema slot AFTER U2's checkpointer wiring lands". |

---

### U2. `stream_agent_dispatch` 持久化 title + summary + status（含 PII redaction）

**Goal**: 流式完成后，从 DeerFlow state 读 title、过 PII redactor、同步回 backend `ai_chat_sessions`。

**Dependencies**: U1（必须三个验证步骤都 pass）

**Files**:
- `server/apps/agent/services/agent_dispatch.py` — 重构 `stream_agent_dispatch` 主流程：在 `thread_id` 确定之后包 `try/finally`，覆盖所有早返回路径；finally 调 `_fire_and_forget(_persist_session_metadata(...))`
- `server/apps/agent/services/session_store.py` — 已有 `update_summary` 接口，无需改动
- `server/apps/agent/tests/unit/test_agent_dispatch.py` — **新建**（当前不存在），覆盖持久化、PII 路径、异常路径

**Approach**:

#### 重构 `stream_agent_dispatch` 控制流

把现有结构（10+ 个早返回散落 + 末尾的 `astream` 循环）改成：

```text
async def stream_agent_dispatch(...):
    # ... 前置 5 步: 拉 agent_config / ai_config / skills / mcp / providers
    if any_error_before_thread_id:
        yield error; return  # 这些早返回保持不动 —— 此时还没 session 概念

    # 步骤 5 之后, thread_id 确定了
    if not thread_id:
        thread_id = str(uuid.uuid4())

    # 从这里开始，所有路径都进 try/finally
    answer_parts: list[str] = []
    success = False
    try:
        # 6-8: build effective_config / runnable_config / agent_graph
        # 这些可能抛错，但 thread_id 已存在 —— finally 会跑，记 status="error"

        # 决策 6：U1 验证 fail 触发 —— make_lead_agent 不带 checkpointer。
        # 在 astream 之前 post-hoc 绑定 shared checkpointer，使 aget_state 可读。
        # 与 orchestrator 路径共享同一 SqliteSaver 实例（同一 db 文件 / thread_id 命名空间）。
        from apps.agent.services.deerflow_adapter.family_adapter_cache import (
            _get_shared_checkpointer,
        )
        agent_graph.checkpointer = _get_shared_checkpointer()

        # 9: astream loop
        # 10: emit end event
        success = True
    finally:
        _fire_and_forget(_persist_session_metadata(
            agent_graph=agent_graph if 'agent_graph' in locals() else None,
            runnable_config=runnable_config if 'runnable_config' in locals() else None,
            family_id=family_id,
            user_id=user_id,
            session_id=thread_id,
            agent_name=agent_name,
            answer="".join(answer_parts),
            model_id=model_id,
            success=success,
        ))
```

`_fire_and_forget` 直接 `from apps.agent.services.orchestrator import _fire_and_forget` 复用。

#### `_persist_session_metadata` 职责（PII-safe 版）

1. `state = await agent_graph.aget_state(runnable_config)` — 包在 `try/except (AttributeError, ValueError)` 里：`AttributeError` → 同步 `agent_graph.get_state` via `loop.run_in_executor`；`ValueError("No checkpointer set")` → 视为 U1 验证 regress，记 warning 并把 title 设为 None 走 fallback。
2. `raw_title = state.values.get("title") if state else None`
3. **PII redaction**：
   - `title = pii_redactor.redact_text(raw_title)[0] if raw_title else None`
   - `redacted_answer, _ = pii_redactor.redact_text(answer)`
   - `summary = redacted_answer[:200] if redacted_answer else None`
4. `title` 为空（或 redact 后全空）→ 调 `_build_fallback_title(family_id, agent_name, user_id)` 生成「YYYY-MM-DD agent_name 用户名」（fallback 输入是 agent metadata，不含用户消息，不需要 redact）
5. `repo = AiSessionRepository(family_id)`
6. `await repo.upsert(session_id=session_id, family_id=family_id, user_id=user_id, capability=agent_name, jsonl_path=<resolve via session_journal.resolve_path>, last_model=model_id)`
7. `await repo.update_summary(session_id=session_id, family_id=family_id, summary=summary, model=model_id, status="completed" if success else "error", title=title[:50] if title else None)`

`_build_fallback_title` 复制 `orchestrator._generate_title` 里 chat≠'chat' 分支的格式逻辑（`time.strftime` + `BackendClient.get_user`），不要从 orchestrator 导入私有函数 —— 复制成 module-private helper（约 20 行），注释指向 orchestrator 同源代码以便日后统一时一并清理。

#### 异常日志规范

任何 `try/except` 包装内只 log `type(e).__name__` + `session_id`，**不 log `str(e)`** —— `aget_state` 与 LangGraph 异常 payload 可能含完整 state 字典（消息历史等）。

```python
except Exception as e:
    logger.warning(
        "[agent_dispatch] persist failed session=%s err_type=%s",
        session_id, type(e).__name__,
    )
```

**Patterns to follow**:
- `services/orchestrator.py:187-196` 的 `_fire_and_forget` 实现
- `services/orchestrator.py:892-910` PII redaction 模式（`pii_redactor.redact_text(...)` 解包 tuple）
- `services/session_store.py:48` 的 logger.warning 静默失败惯例（**不照抄 `%s, e` 格式 —— 那个格式会泄漏 state**）

**Test scenarios** (`tests/unit/test_agent_dispatch.py` — **新建**):
- happy path：mock `agent_graph.astream` + mock `aget_state` 返回 `{"title": "净资产分析"}`，断言 `repo.update_summary` 被调用且 `title` 是 redact 后版本
- **checkpointer 绑定 regression**：构造一个真实的 `make_lead_agent` 调用（mock LLM），断言 `agent_graph.checkpointer is _get_shared_checkpointer()` —— 该 assert 锁定决策 6 的假设：langgraph 升级若把 `.checkpointer` 改为 immutable 该测试会立刻 fail，触发回到决策 6 trade-off 段记录的备选路径
- PII redaction：mock `aget_state` 返回含手机号 / 身份证号的 title，断言写入 DB 的 title 是 redacted（用 fixed PII fixture 与 `pii_redactor` 实测，不 mock redactor）
- title 为空 fallback：mock `aget_state` 返回 `{}`，断言 fallback 调用 `BackendClient.get_user` 且最终 title 形如 `2026-05-30 numina <user_name>`
- summary redaction：mock `astream` 输出含金额 / 账号的 answer_parts，断言 `update_summary` 收到的 summary 已被 redact
- update_summary 失败：mock 抛 `httpx.HTTPError`，断言 `stream_agent_dispatch` 不抛、流式输出完整、log 不含异常 payload（`caplog.records[0].message` 不包含 `"e="` 或 state 字典）
- 早返回路径：模拟在 `astream` 之前抛错（如 `agent_graph.astream` 自身 raise），断言 finally 仍然调用 `update_summary` 且 `status="error"`、`summary=None`
- aget_state 抛 `ValueError("No checkpointer set")`：断言 fallback title 被使用，update_summary 仍然被调（status=completed 或 error 取决于 stream 是否已成功），不抛

**Verification**: `uv run pytest apps/agent/tests/unit/test_agent_dispatch.py -v` 全绿；手动跑一次 chat → `GET /api/v1/ai/sessions` 看到带真实标题。

---

### U3. `stream_agent_dispatch` 写 session journal jsonl（含 redacted 文本）

**Goal**: 让 `GET /sessions/{id}/events` 对 agent 路径产生的会话有完整事件回放，且 journal 内容也是 PII-redacted。

**Dependencies**: U2（共用 `_persist_session_metadata` 的 finally 钩子 + redaction pipeline）

**Files**:
- `server/apps/agent/services/agent_dispatch.py` — 在主流程前后插入 4 个 journal 调用
- `server/apps/agent/services/session_journal.py` — **新增公开 `resolve_path` 方法**

**Approach**:

#### `session_journal.py` 结构调整

把现有的私有 `_session_path` 暴露为公开 `resolve_path(family_id, session_id, capability="agent", user_id="_shared") -> Path`：

```text
def resolve_path(self, family_id: str, session_id: str, capability: str = "agent", user_id: str = "_shared") -> Path:
    """Public wrapper around _session_path. agent_dispatch uses this to get jsonl_path
    string for write_session_start without exposing _validate_id constraints to callers."""
    return self._session_path(family_id, session_id, capability=capability, user_id=user_id)
```

注意 `_validate_id` regex `^[A-Za-z0-9_\-]+$` 拒绝中文，所以 `capability` 必须用固定占位符 `"agent"`，不能传 `agent_name`（system agent 名 `数鸣` 会 fail）。

#### journal 写入时机

1. **入口**（在 `try/finally` 体内、`astream` 之前，**同步**写）：
   `session_journal.write_session_start(family_id=..., session_id=thread_id, user_id=..., capability="agent", model_name=model_id, jsonl_path=str(session_journal.resolve_path(...)))`

2. **首条用户消息**（同步，在 `agent_graph.astream` 调用之前）：
   `redacted_msg, _ = pii_redactor.redact_text(message)`
   `session_journal.write_user_message(family_id=..., session_id=thread_id, user_id=..., content=redacted_msg)`
   —— **同步写**是因为这条消息必须在 stream 开始前落盘，才能保证 events 回放顺序。Journal 写入是本地文件 append，~微秒级，不阻塞流。

3. **流式完成 / 异常**（在 `_persist_session_metadata` 内，作为 fire-and-forget 的一部分）：
   - `session_journal.write_assistant_message(..., content=redacted_answer, model_name=model_id)` —— 用 U2 已经 redact 过的 answer
   - `session_journal.write_session_end(..., success=success, duration_ms=elapsed_ms, tokens_used=0)`

任何 journal 写入抛错（已经被 `session_journal.append_event` 内部 try/except 吞了，但留个 warning）不影响主流程。

**Patterns to follow**:
- `services/orchestrator.py:823, 893` 的 journal 调用位置
- `services/session_journal.py:90-102` 的 `append_event` 静默失败模式

**Test scenarios** (`tests/unit/test_session_journal.py` 已存在则增补 / `tests/unit/test_agent_dispatch.py` 新建):
- `test_session_journal.py`：调 `journal.resolve_path("100", "abc", capability="agent", user_id="42")`，断言返回 `<base>/100/agent/agent/42/abc.jsonl`
- `test_agent_dispatch.py`：流式跑完后读取目标 jsonl 文件，断言事件序列依次是 `session.start → user.message → assistant.message → session.end`，且 `user.message.content` 与 `assistant.message.content` 都已 redact
- `test_agent_dispatch.py`：`write_session_start` 抛异常（mock journal raise）时主流程不抛、流式结果完整
- `test_agent_dispatch.py`：跑完后读 jsonl，断言里面**不包含**任何 PII fixture 字符串（手机号、账号格式）
- `test_agent_dispatch_persistence.py`（integration，U4 涵盖）：跑完后调用 `GET /sessions/{id}/events`（agent 内部接口）拿到非空事件列表

**Verification**: `uv run pytest apps/agent/tests/ -v -k "session_journal or (agent_dispatch and journal)"` 全绿；手动 `curl -H "X-Agent-Token: ..." http://localhost:8001/sessions/<id>/events` 拿到流式事件且无 PII 泄漏。

---

### U4. 一致性回归测试

**Goal**: 确保旧路径 `/chat/ask/stream` 行为不变，新路径与旧路径在 backend 表里产生形同的 session 记录形态。

**Dependencies**: U1, U2, U3

**Files**:
- `server/apps/agent/tests/integration/test_agent_dispatch_persistence.py` — 新增
- `server/apps/agent/tests/integration/test_orchestrator_legacy_path.py`（如已存在则增补） — 增加对照断言

**Approach**:

写两个并列测试：
1. agent path：通过 `stream_agent_dispatch` 跑完一轮，断言 backend session 行 `title != null`、`status == "completed"`、`last_model` 与请求 model 一致、`last_message_summary` 非空。
2. legacy path：通过 `orchestrator.stream_dispatch_events(capability="chat", ...)` 跑完，断言上述同样字段。

两条路径用相同 mock LLM（返回固定文本），断言 backend 持久化结果在以下字段上**形态相同**：`title`（非空 & 长度 ≤ 50）、`status`、`last_message_summary`、`message_count` 增量、`updated_at` 更新。

**Test expectation**: 这是验收测试单元，所有测试就是它的输出，不需要单独列 scenario。

**Verification**: `uv run pytest apps/agent/tests/integration/ -v -k persistence` 全绿。

---

## System-Wide Impact

| 维度 | 影响 |
|---|---|
| 数据库 | `ai_chat_sessions.title` / `last_message_summary` / `status` / `last_model` 现在会被 agent 路径写入。无 schema 变化。 |
| Checkpointer | DeerFlow `ThreadState.title` 字段已经在 schema 里且 middleware 默认在写——本计划只是开始**读**它，不引入新字段或 migration 风险。 |
| 文件系统 | `SESSIONS_DATA_DIR/{family_id}/agent/agent/{user_id}/{session_id}.jsonl` 会新增写入 —— 与 orchestrator 现有路径结构兼容。 |
| 性能 | 多一次 `aget_state` 调用（read SQLite），fire-and-forget 不阻塞流。LLM 标题生成由 `TitleMiddleware` 在首轮 after_agent 阶段同步触发 —— 已经存在于旧路径，不是新增成本。 |
| 用户可见 | 修复后所有新建对话都有真实标题；历史 untitled 记录保持原样（见 deferred）。 |

---

## Risks & Mitigations

| 风险 | 概率 | 影响 | 缓解 |
|---|---|---|---|
| `aget_state` 在某些 LangGraph 版本下不可用（仅有同步 `get_state`） | 中 | 持久化失败 | 优先尝试 `aget_state`，捕获 `AttributeError` 后用 `loop.run_in_executor` 包同步 `get_state`；在 U2 测试里覆盖两种路径 |
| `aget_state` 抛 `ValueError("No checkpointer set")`（U1 验证 regress） | 中 | 持久化失败、title 一律 fallback | U2 显式 catch，记 warning，title 走 fallback 模板（不阻断流） |
| `TitleMiddleware` 默认 prompt 输出英文，对中文对话不合适 | 中 | 标题质量差 | U1 验证后先观察一轮真实流量；如果质量差，在 `title.model_name` 显式指定模型并补 prompt（DeerFlow 支持自定义 prompt，见 Context7 `CONFIGURATION.md`） |
| Backend `proxy_stream` finally 已写 `last_message_summary` / `message_count` / `updated_at`，与 agent 的 `update_summary` 双写同列 | 中 | last 字段值取决于谁后写，可能 race | U2 用 `_fire_and_forget` 启动后，agent 路径的 `update_summary` 通常**比** backend 的 `append_message` **晚执行**（streamingResponse close → backend finally → agent 持久化任务才被 schedule）。两边都是 idempotent overwrite，最终值由 agent 路径决定且 agent 写的 summary 已 redact，符合最终期望。U4 集成测试断言两条字段最终值与 agent 写入一致。如果实测发现顺序反过来，把 `update_summary` 改为只在 backend 没填时填补（COALESCE 语义），但当前默认假设 backend 字段被 agent 后写覆盖 |
| journal `jsonl_path` 解析逻辑与 orchestrator 不一致导致两条路径文件路径冲突 | 低 | 历史回放错乱 | U3 将 `resolve_path` 抽成 `session_journal` 的公开方法，两条路径共用同一个 resolver |
| TitleMiddleware 用 `models[0]` 即家庭主模型 → 数据 residency 假设隐式 | 低 | 未来若改 title 用别的模型可能跨边界 | `base/config.yaml` 注释 `model_name: null` 的语义；本计划不引入独立 title 模型 |
| LLM 输出含 HTML/script 字符 → 当前前端用 mustache 渲染不会执行，但未来 client 可能 v-html | 低 | 防御层缺失 | U2 在写 DB 前 `re.sub(r'<[^>]+>', '', title).strip()` 去 HTML 标签（与 PII redact 同一管道，5 行代码） |
| 异常日志泄漏 state payload | 低 | 内部 log 含消息历史 | U2 异常路径只 log `type(e).__name__` + `session_id`，**不**用 `%s, e` 模式；测试 caplog 断言 |

---

## Verification Strategy

按单元逐步验证：

1. **U1 完成后**：`uv run pytest apps/agent/tests/integration/test_titlemiddleware_wiring.py -v` 全绿。三个验证步骤都 pass 才允许进 U2；任一 fail 时回到 plan revise。
2. **U2 完成后**：单测全绿；启动 agent 跑一轮 chat，`sqlite3 ${NUMINA_DATA_DIR:-.numina/data}/numina.db "SELECT title, status FROM ai_chat_sessions ORDER BY id DESC LIMIT 1"` 看到真实标题与 `completed` 状态（路径需根据 `settings.NUMINA_DATA_DIR` 实际值调整）。
3. **U3 完成后**：单测全绿；`ls $SESSIONS_DATA_DIR/{family_id}/agent/agent/{user_id}/` 看到 jsonl 文件，`tail -1` 是 `session.end`；用 PII fixture 输入跑一轮，grep jsonl 确认无 PII 字符串泄漏。
4. **U4 完成后**：集成测试全绿。
5. **回归**：手动跑 `pnpm dev` 起前端 + agent + backend，从历史会话页面看到新建会话有真实标题；`/sessions/{id}/events` curl 出非空流。

不在本计划做：浏览器端的 UI 验证。前端无改动，只要后端字段填上了就生效。

---

## Open Questions

doc-review 阶段提出的次要问题，留待实现期或后续工作处理：

1. **会话 ID 是否 path-scoped？** — Risks 表第 4 行的双写竞态分析假设：一个 session_id 不会先在 legacy 路径开、再被 agent 路径接管。如果客户端**可以**用同一个 session_id 在两条路径之间切换（如先 chat 后切到 numina agent），则双写竞态变成 sustained——需要确认前端行为。**Action**：实现 U4 时增加一个测试用例验证两条路径用同一 thread_id 的行为。
2. **历史 untitled 会话回填策略** — 当前已存在的 `title=NULL` 记录不在本计划覆盖。后续可写一次性脚本扫表 + LLM 摘要，作为运维任务排期。
3. **U2 的 `_build_fallback_title` 复制 vs 抽取** — 短期复制是 acceptable trade-off。如果未来 fallback 格式需要变（如加上 emoji 或 capability icon），重复逻辑会成痛点。届时把 `_build_fallback_title` 抽到 `packages/core` 共享。
4. **统一两条路径的 follow-up plan 范围** — 本计划 deferred 段说"单独排期"。届时把 orchestrator 旧路径的 `_generate_title` 删掉换成 `aget_state` 读取，需要给 `DeerFlowAdapter` 暴露 `get_state(thread_id)` 接口。预估 2 个 unit。

---

## Origin

无上游 brainstorm 文档。本计划由用户对话中的 bug 排查直接导出（见会话内 root-cause 分析）。

---

## Review History

- **2026-05-30 doc-review**: 4 reviewers (coherence, feasibility, security-lens, adversarial). Key revisions integrated:
  - U1 从"启用 TitleMiddleware 配置"改为"pre-flight 验证"，因为 Feasibility reviewer 直接读 vendored harness 源码（`agent.py:284`、`title_config.py:9`）证实 middleware 已无条件挂载且默认启用。
  - 新增决策 4「所有持久化字段都过 `pii_redactor`」，因为 Security reviewer 指出旧路径用 `redacted_free_text` / `redacted_answer`、新路径直接写 raw 文本——违反 `agent/CLAUDE.md` Key Invariant #1。
  - 决策 3 改为复用 `orchestrator._fire_and_forget` 而非裸 `asyncio.create_task`，且 `try/finally` 必须包覆所有早返回路径（Feasibility F4 / Adversarial F3 一致指出）。
  - 新增「Decisions Considered and Rejected」章节，记录 backend-side 标题生成方案被 reject 的理由（Adversarial F5）。
  - U3 Files 列修正：`session_journal.py` 是 modified（新增 `resolve_path`），不是"无需改动"（Coherence + Feasibility + Adversarial 三方一致指出）。
  - 异常日志规范明确化：只 log `type(e).__name__` + `session_id`，不 log `str(e)`（Security SEC-005）。
  - Risks 表加 backend `proxy_stream` 双写竞态行（Adversarial F1）。
- **2026-05-30 U1 gate execution**: U1 跑出 plan-pivoting 结果。
  - Step 2 ✅ —— TitleMiddleware 默认启用、确实在 `_build_middlewares` 链里，与计划假设一致。
  - Step 1 ❌ —— `make_lead_agent` 返回的 graph `.checkpointer is None`。新增决策 6：U2 在 `astream` 之前 post-hoc `agent_graph.checkpointer = _get_shared_checkpointer()`（实测 `CompiledStateGraph.checkpointer` 可后置赋值，且复用 orchestrator 路径同一 SqliteSaver）。U2 Approach 同步插入该绑定逻辑、Test scenarios 增加 regression assert 锁定该 langgraph 内部约定。
  - Step 3 ⚠️ —— 因独立的 `ThreadDataMiddleware.before_agent` `runtime.context` 缺失而 fail；不影响 gate 决策。U1 测试本身保留作为 regression（仍可在决策 6 落地后跑通 step 3 schema slot 检查），其原始作用——证明 step 1 fail——已经达成并被 U2 决策吸收。
