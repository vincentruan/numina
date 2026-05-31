---
date: 2026-05-29
type: refactor
origin: null
status: active
deepened: 2026-05-31
---

# refactor: 消除 AI 三档感知 / 补回联网搜索 / 合并 AI 问答到数鸣

## Summary

回滚/调整最近 #78 (`2cb7fe26`) 与 #80 (`0ba20e40 feat(ai-chat): restore DeerFlow chat UX fusion R1-R8`) 落地的 AI 重构里偏离产品意图的三处实现，并把 thinking/reasoning 后端配置对齐到 context7 验证过的 2026 最新 API：

1. **深度思考二态语义稳定化**：UI 已是 boolean（U1 已落地）。后端 `family_adapter_cache.py` 已为所有 thinking-capable provider 显式提供 `when_thinking_enabled` / `when_thinking_disabled`（U2 已落地），并把 native OpenAI 切到 DeerFlow 2 的 `supports_reasoning_effort: true`（U2' 已落地）。**剩余工作**：U8 把 native OpenAI 切到 Responses API（GPT-5 推荐路径）；U10 新增 `system-config.yaml` 维护"模型默认 max_tokens 表"；U11 给 backend 与 agent 加 yaml loader；U12 `ai_providers` 表加 `max_tokens INTEGER NULL` 列 + defaults 端点；U13 agent emit max_tokens 到 model entry；U14 前端表单加输入框 + 默认值回写；U9 在 U13 基础上把 Anthropic budget_tokens 改成按已解析的 max_tokens 动态计算。
2. **联网搜索作为可选特性回归 agentId 路径**：U3 已补回 `web_search` 全链路。
3. **AI 问答合并进数鸣**：U5/U6/U7 已落地（migration 删 `id=100000000000003`，agent_dispatch 兜底，前端注释清理）。

非目标：不重写 `/ai` 整体 IA、不动 skill 管理页、不改 `agent_dispatch._resolve_skills` 现有 sentinel 机制（数鸣继续 `["*"]`）、不动 time-machine、不接入真正的 web search 工具（仅行为引导）、不切 OpenAI-compatible 网关（GLM/Qwen/QwQ via DashScope/Novita/vLLM）到 Responses API、不做 system-config.yaml 热更新（重启服务才生效）。

---

## State After 2026-05-31 (Code-Reality Snapshot)

合并 `origin/main` (8 commits, `c40c8c51..c9e03221`) + 已落地的 U1–U7、U2' 之后，代码现状如下：

| 项目 | 状态 |
|---|---|
| 数鸣 agent ID | `100000000000005`（`b6745e8a2c14` migration） |
| ai-assistant agent | **已删除**（migration `c8a1e7d3f4b2_remove_ai_assistant_agent.py`，`down_revision=a7b2c3d4e5f6`，单 head） |
| time-machine agent | `100000000000004` 不变 |
| `AgentStreamRequest` | 含 `message / thread_id / enable_thinking / web_search / reasoning_effort` ✅ |
| `stream_agent_dispatch(web_search=...)` | ✅ 已加 |
| `agent_dispatch.py` legacy ID fallback | `_LEGACY_AI_ASSISTANT_AGENT_ID=100000000000003` → `_NUMINA_AGENT_ID=100000000000005` ✅ |
| 联网搜索 system message 注入 | ✅ 与 `chat_adapter.py:93-96` 同义 |
| `AIChatInput.vue` | smart_light / smart_full 子按钮 **已删** ✅；mode toggle + 独立 webSearch toggle |
| `AIChatPage.vue` | `ChatMode = 'normal'\|'smart'` ✅；`webSearch` 独立 ref；`reasoningEffort = deepThink ? 'high' : 'low'` |
| i18n | `smartLight` / `smartFull` keys **已删**；`modeSmart` = "深度思考"/"Deep think" |
| `family_adapter_cache.py` 顶部 docstring | ✅ 含 4 套 provider 契约说明 |
| `ANTHROPIC_HIGH_EFFORT_BUDGET_TOKENS=10000` / `LOW=2000` | ✅ 已常量化 |
| native OpenAI thinking-supported 配置 | ✅ `supports_reasoning_effort: True` + `{"reasoning_effort": "high"\|"low"}` |
| native OpenAI `use_class` | ✅ `langchain_openai:ChatOpenAI`（不再误用 patched_openai） |
| OpenAI-compatible 网关（带 base_url） | 仍 `extra_body.enable_thinking`（vendor extension，正确） |
| Anthropic native | `thinking={"type":"enabled","budget_tokens":HIGH}` / `{"type":"disabled"}` |
| DeepSeek R1 | `extra_body.thinking.{type}` 不变 |
| `frontend AIHubPage.vue` 注释 | ✅ 已删除 "Fall back to ai-assistant" 字样 |

行动调整：

- **U1 / U2 / U3 / U5 / U6 / U7 / U2'** — 全部完成。
- **U8（新增，待确认）** — 把 native OpenAI 切到 DeerFlow 2 的 Responses API 路径（`use_responses_api: true` + `output_version: responses/v1`），覆盖 GPT-5 系列推荐用法。
- **U9（新增，待确认）** — 给 `ANTHROPIC_HIGH_EFFORT_BUDGET_TOKENS` / `LOW` 常量加权威来源注释（指向 anthropic-sdk-python `examples/thinking.py` 与官方 `budget_tokens >= 1024 < max_tokens` 约束）。

---

## Provider API Contracts (context7 verified, 2026)

按 context7 拉到的官方文档（openai-python 当前 / anthropic-sdk-python current / DeerFlow 2 CONFIGURATION.md & README.md）确认的最新合约。**本计划优先复用 DeerFlow 2 已有能力，绝不引入自研字段。**

### OpenAI Chat Completions API

源：`openai-python` `src/openai/resources/chat/completions/completions.py`

```python
client.chat.completions.create(
    model="gpt-5.5",
    messages=[...],
    reasoning_effort: Optional[ReasoningEffort],   # 'low'|'medium'|'high'，顶层
    verbosity: Optional[Literal["low","medium","high"]],  # 顶层
    web_search_options: ...,                       # OpenAI 官方 web search
    max_completion_tokens: int,
    ...
)
```

要点：`reasoning_effort` 是顶层；不接受任何 `extra_body.enable_thinking` / `extra_body.thinking` 字段（那些是 vendor extensions）。

### OpenAI Responses API（GPT-5 推荐路径）

源：`openai-python` README + `src/openai/types/responses/`

```python
client.responses.create(
    model="gpt-5",
    input=[{"role":"user","content":"..."}],
    instructions=...,
    text={"format": {"type":"json_object"}, "verbosity": "low"|"medium"|"high"},
    reasoning={"effort": "low"|"medium"|"high"},   # 嵌套在 reasoning 字段下
    max_output_tokens: int,                         # 含 reasoning tokens
    ...
)
```

要点：`verbosity` 嵌在 `text.verbosity`；`reasoning.effort` 嵌在 `reasoning` 字段；`max_output_tokens` 同时计 visible + reasoning tokens。

### Anthropic Messages API

源：`anthropic-sdk-python` `examples/thinking.py` + `src/anthropic/resources/messages/messages.py`

```python
client.messages.create(
    model="claude-sonnet-4-5-20250929",
    max_tokens=3200,
    thinking={"type": "enabled", "budget_tokens": 1600},   # 官方示例值
    output_config: OutputConfigParam,                       # 已 GA，非 beta
    messages=[...],
)
```

要点：
- `thinking.type` ∈ {`"enabled"`, `"disabled"`, `"adaptive"`(beta)}；
- `thinking.budget_tokens` 必须 `>= 1024`（Anthropic 官方约束）且 `< max_tokens`；
- 官方 SDK 示例使用 `budget_tokens=1600`（未推荐固定值，按场景 tune）；
- `ThinkingConfigAdaptiveParam` 是 beta（`type: "adaptive"`，可选 `display: "summarized"|"omitted"`）— 本计划不消费；
- `output_config` 已 GA（非 beta），但 langchain-anthropic 是否透传需另行验证 — 本计划不消费。

### DeerFlow 2 model entry 字段（YAML/dict）

源：`bytedance/deer-flow` README.md + `backend/docs/CONFIGURATION.md`

```yaml
models:
  # 1. Native OpenAI Responses API (GPT-5 推荐)
  - name: gpt-5-responses
    use: langchain_openai:ChatOpenAI
    model: gpt-5
    api_key: $OPENAI_API_KEY
    use_responses_api: true            # ← DeerFlow 2 原生支持
    output_version: responses/v1       # ← 与 use_responses_api 配对
    supports_reasoning_effort: true    # ← harness emit reasoning.effort
    when_thinking_enabled:
      reasoning_effort: high
    when_thinking_disabled:
      reasoning_effort: low

  # 2. Native OpenAI Chat Completions（无 Responses API）
  - name: gpt-4o
    use: langchain_openai:ChatOpenAI
    model: gpt-4o
    api_key: $OPENAI_API_KEY
    supports_reasoning_effort: true    # harness emit 顶层 reasoning_effort
    when_thinking_enabled:
      reasoning_effort: high
    when_thinking_disabled:
      reasoning_effort: low

  # 3. OpenAI-compatible 网关（vLLM 例）
  - name: qwen3-32b-vllm
    use: deerflow.models.vllm_provider:VllmChatModel
    model: Qwen/Qwen3-32B
    api_key: $VLLM_API_KEY
    base_url: http://localhost:8000/v1
    supports_thinking: true
    when_thinking_enabled:
      extra_body:
        chat_template_kwargs:
          enable_thinking: true        # vendor extension

  # 4. DeepSeek R1
  - name: deepseek-v3
    use: deerflow.models.patched_deepseek:PatchedChatDeepSeek
    model: deepseek-reasoner
    api_key: $DEEPSEEK_API_KEY
    supports_thinking: true
    when_thinking_enabled:
      extra_body:
        thinking:
          type: enabled

  # 5. Native Anthropic Claude
  - name: claude-3-5-sonnet
    use: langchain_anthropic:ChatAnthropic
    model: claude-3-5-sonnet-20241022
    api_key: $ANTHROPIC_API_KEY
    supports_thinking: true
    when_thinking_enabled:
      thinking:
        type: enabled
        budget_tokens: 10000
    when_thinking_disabled:
      thinking:
        type: disabled
```

要点：
- DeerFlow 2 harness 自动根据 `supports_reasoning_effort: true` + `use_responses_api` 决定 emit 形态（Chat Completions: 顶层 `reasoning_effort`；Responses: 嵌套 `reasoning.effort`）。
- `use_responses_api` 必须**配对** `output_version: responses/v1`（DeerFlow README 的所有示例都成对出现）。
- OpenAI-compatible vendor extensions（`extra_body.enable_thinking`、`extra_body.chat_template_kwargs`）只能用在带 `base_url` 的非官方端点；官方 OpenAI 端点会拒绝。

---

## Origin Document Reference

无上游 brainstorm。最相关的前次 brainstorm 是 `docs/brainstorms/2026-05-26-ai-page-agent-skill-restructure-requirements.md`，本计划是其中部分决策的回调与精修（特别是 R5"AI 问答与数鸣并存"和 R6"sentinel skill 解析"周边）。原 brainstorm 的 R5 显式保留 ai-assistant 作为"轻量纯聊天"差异化入口；现在产品方向变更，决定合并以收敛主入口。

---

## Requirements Trace

| Requirement | 实现 Units | 状态 |
|---|---|---|
| 深度思考保持二态 UI | U1 | ✅ done |
| 二态在 provider 上行为显式 | U2 | ✅ done |
| native OpenAI 走标准顶层 reasoning_effort（非 vendor extension） | U2' | ✅ done |
| native OpenAI 升级到 Responses API（GPT-5 推荐路径） | **U8** | 🔄 待执行 |
| 项目根 `system-config.yaml` 维护 max_tokens 默认表 | **U10** | 🔄 待执行 |
| backend & agent 共享 yaml loader（`packages/core/system_config.py`） | **U11** | 🔄 待执行 |
| `ai_providers` 表加 `max_tokens` 列 + defaults 端点 | **U12** | 🔄 待执行 |
| agent emit max_tokens 到 model entry（三段优先级：user → yaml → None） | **U13** | 🔄 待执行 |
| Anthropic budget_tokens 按已解析的 max_tokens 动态计算 | **U9** | 🔄 待执行（依赖 U13） |
| 前端 settings 表单加 max_tokens 字段 + 默认值回写 | **U14** | 🔄 待执行 |
| `agent_stream` 接收 `web_search` 并贯通 | U3 | ✅ done |
| Frontend `webSearch` 在 agentId 路径生效 | U4 | ✅ done（透传链验证） |
| Migration 删除 ai-assistant (id=100000000000003) | U5 | ✅ done |
| agent_id=100000000000003 的请求 fallback 到数鸣 | U6 | ✅ done |
| Frontend 不再渲染 ai-assistant 卡片/选项 | U7 | ✅ done |

---

## Implementation Units

### U1. 移除前端三档 UI，回到二态启停（deep_think boolean）— ✅ done

合并 main 后 PR `0ba20e40` 把前端 chatMode 重构成显式三档（`'normal' | 'smart_light' | 'smart_full'`），与原始诉求"启停深度思考模式"直接冲突。已删除 `smart_light` / `smart_full` 子按钮，回到 `normal ⇄ smart` 二态切换；`reasoning_effort` 不再由 UI 选择，而是由 `deep_think` 决定（false→low、true→high）；`web_search` 拆为独立 toggle（与 deep_think 正交）。

落地证据：`AIChatInput.vue` `mode: 'normal'|'smart'`、`AIChatPage.vue:629` `type ChatMode = 'normal' | 'smart'`、i18n 已删 smartLight/smartFull keys。

---

### U2. 后端深度思考二态映射的可读性强化 — ✅ done

`family_adapter_cache.py` 顶部新增 docstring 章节，描述 4 套 provider 当前 API 契约（context7 验证）；引入 `ANTHROPIC_HIGH_EFFORT_BUDGET_TOKENS=10000` / `ANTHROPIC_LOW_EFFORT_BUDGET_TOKENS=2000` 常量（LOW 预留）；把 native OpenAI 从误用的 `extra_body.enable_thinking` 切到 DeerFlow 2 的 `supports_reasoning_effort: True` + `{"reasoning_effort": "high"|"low"}`；OpenAI-compatible 网关分支保留 vendor extension `extra_body.enable_thinking`。

落地证据：模块顶 docstring（line 1–53）、常量定义（line 76–77）、`provider == "openai" and not base_url` 分支（line 245–248、284–289）。

---

### U3. agent_stream 路径补回 web_search 参数 — ✅ done

`AgentStreamRequest` 加 `web_search: bool = False`；`stream_agent_dispatch` 签名加 `web_search: bool = False`；state 构造时把联网搜索 guidance 注入 system message 第 0 项。

落地证据：`agent_stream.py:19`、`agent_dispatch.py:198`、`agent_dispatch.py` 中 `state = {"messages": [{"role":"system",...}]}`。

测试：`tests/agent/unit/test_agent_stream.py` 7 项全绿（含 `web_search=True` 默认值用例）。

---

### U4. Frontend agentId 路径透传 webSearch — ✅ done

前端→backend→agent 三段透传链已贯通：`sendChatMessageStream` payload 含 `web_search`；backend `ChatStreamRequest` 已声明（`ai_chat.py:53`）；`ai_chat.py:236-242` agent_id 分支 `agent_body` 含 `"web_search": body.web_search`；agent_stream 路由 schema 接住后 dispatch 注入 system message。

---

### U5. Alembic migration: 删除 ai-assistant 系统智能体 — ✅ done

落地：`server/apps/backend/alembic/versions/c8a1e7d3f4b2_remove_ai_assistant_agent.py`，`down_revision="a7b2c3d4e5f6"`，单 head（`alembic heads` 输出仅 `c8a1e7d3f4b2`）。upgrade 删 `id=100000000000003 AND family_id=0 AND agent_name='ai-assistant'`；downgrade verbatim 重插（含 soul_md）。AST 模块校验通过。

---

### U6. agent_dispatch 对 ai-assistant agent_id fallback — ✅ done

落地：`agent_dispatch.py` 模块顶常量 `_NUMINA_AGENT_ID=100000000000005`、`_LEGACY_AI_ASSISTANT_AGENT_ID=100000000000003`；`stream_agent_dispatch` 第一段 fetch 失败时按 legacy ID 兜底到 numina；fallback 命中时记 `info` 级日志；其余 agent_id 错误保持原 `AGENT_CONFIG_ERROR`。

---

### U7. Frontend AIHubPage 注释与兜底链清理 — ✅ done

`AIHubPage.vue:298` 注释更新（删除 "Fall back to ai-assistant" 字样）。`AIChatPage.vue` `loadActiveAgent` 已有 try/catch 兜底到 numina（与 U6 后端兜底对齐）。`settings.aiAssistant` i18n key 保留（指 AI 设置入口标题，与 ai-assistant agent 无关）。

---

### U2'. native OpenAI 切到 DeerFlow 2 supports_reasoning_effort — ✅ done

落地：`family_adapter_cache.py` 把 native OpenAI（`provider == "openai" and not base_url`）的 `use_class` 从 `deerflow.models.patched_openai:ReasoningChatOpenAI` 改回 stock `langchain_openai:ChatOpenAI`；model entry 添加 `supports_reasoning_effort: True`；`when_thinking_enabled = {"reasoning_effort": "high"}`、`when_thinking_disabled = {"reasoning_effort": "low"}`。

OpenAI-compatible 网关、Anthropic、DeepSeek 三个分支不动。

---

### U8. native OpenAI 升级到 Responses API（GPT-5 推荐路径）— 🔄 待执行

**Goal:** 把 native OpenAI 模型从 Chat Completions 切到 Responses API。GPT-5 系列在 Responses 模式下行为更完整（reasoning summary、`text.verbosity`、`reasoning.effort` 嵌套结构）。DeerFlow 2 harness 已支持 `use_responses_api: true` + `output_version: responses/v1` 一键切换；本 unit 仅在配置层加这两个字段，不动其他 provider。

**Why:**
- DeerFlow 2 README/CONFIGURATION.md 把 "GPT-5 (Responses API)" 列为推荐示例，明确 `gpt-5` 走 Responses。
- Responses API 的 `reasoning.effort` 是结构化字段（`reasoning: {effort: "low"|"medium"|"high"}`），优于 Chat Completions 的顶层 `reasoning_effort`（后者在某些 SDK 版本里仍保留但 OpenAI 推荐迁移）。
- `output_version: responses/v1` 让 LangChain 输出形态稳定，便于下游 streaming 解析。
- OpenAI-compatible 网关（DashScope/Novita/vLLM）大多**不**支持 Responses API — 仅切 native OpenAI。

**Dependencies:** U2'（native OpenAI 已走 stock `ChatOpenAI` + `supports_reasoning_effort`）

**Files:**
- `server/apps/agent/services/deerflow_adapter/family_adapter_cache.py`（修改 — native OpenAI 分支加两个字段）
- `server/tests/agent/unit/test_family_adapter_cache.py`（新增或扩展 — 断言 yaml 含 `use_responses_api: True` 与 `output_version: 'responses/v1'`）

**Approach:**

1. 在 `_generate_temp_config` 中 native OpenAI 分支（`provider == "openai" and not base_url`）的 `model_entry` 配置阶段，追加：
   ```python
   model_entry["use_responses_api"] = True
   model_entry["output_version"] = "responses/v1"
   ```
   保留现有 `supports_reasoning_effort: True` 与 `when_thinking_enabled/disabled` — DeerFlow 2 harness 在 Responses 模式下自动把 `reasoning_effort` 映射到 `reasoning.effort`。
2. 在该分支正上方加 5–8 行 inline doc-comment，解释为何切 Responses API（含 GPT-5 推荐链接 keyword、与 OpenAI-compatible 分支的对照）。
3. 模块顶 docstring 的 "Future upgrade path" 段落（line 49–52）改为已落地说明（"Native OpenAI uses Responses API since 2026-05-31; OpenAI-compatible gateways stay on Chat Completions"）。
4. 不改 OpenAI-compatible 网关、Anthropic、DeepSeek 分支。
5. 不改 `agent_dispatch.py`（`reasoning_effort` 注入 `app_config_dict["model"]` 的逻辑由 main 合入，DeerFlow 在 Responses 模式下会消费同名字段）。

**Patterns to follow:** DeerFlow 2 README "gpt-5-responses" 示例（已在 §Provider API Contracts 章节引述）。

**Test scenarios:**

- **Native OpenAI + thinking_supported**: `provider="openai"`、`base_url=""`、`thinking_supported=True` → emitted yaml `models[0]` 包含 `use_responses_api: True`、`output_version: "responses/v1"`、`supports_reasoning_effort: True`、`when_thinking_enabled.reasoning_effort == "high"`、`when_thinking_disabled.reasoning_effort == "low"`、`use == "langchain_openai:ChatOpenAI"`。
- **Native OpenAI + non-thinking**: `thinking_supported=False` → 仍含 `use_responses_api: True` + `output_version`（即使不思考，Responses API 也是 native 端推荐路径）。**Decision needed**: 也可以选择仅在 thinking 模型上加 — 见 §Decisions to confirm。
- **OpenAI-compatible 网关**（带 base_url）: 不含 `use_responses_api`、不含 `output_version`，仍走 `extra_body.enable_thinking`。
- **Anthropic / DeepSeek**: 完全不变。
- **AST 静态检查**: `family_adapter_cache.py` 中 `use_responses_api` 与 `output_version` 必须**一起出现**（成对存在），不可单独。

**Verification:**

```bash
cd server/apps/agent && uv run ruff check services/deerflow_adapter/family_adapter_cache.py
cd server && uv run pytest tests/agent/unit/test_agent_stream.py -v   # 不破坏现有 7 项
```

不依赖 deerflow runtime（避免本机 deerflow 包未装的环境问题），用 yaml dump + dict assertion 做离线断言。

---

### U9. Anthropic budget_tokens 按 max_tokens 动态计算 — 🔄 待执行

**Goal:** 把 `ANTHROPIC_HIGH_EFFORT_BUDGET_TOKENS=10000` / `LOW=2000` 这两个写死的常量改成基于模型 `max_tokens` 的 fraction 动态计算，避免 `budget_tokens >= max_tokens` 引发 API 报错（context7 验证：anthropic-sdk-python `examples/thinking.py` 中 `budget_tokens=1600 < max_tokens=3200`，即官方默认就是按比例切的）。

**Why（context7 拉到的关键事实）:**

- `anthropic-sdk-python:src/anthropic/types/model_info.py` 区分 `max_input_tokens`（context window，输入上限）与 `max_tokens`（单次响应的输出上限）。`budget_tokens` 是**从输出预算里切**的，跟 `max_tokens` 直接相关，与 `max_input_tokens` 无关。
- Anthropic 官方硬约束（来源：anthropic-sdk-python `examples/thinking.py` + 文档）：
  - `budget_tokens >= 1024`（最小值）
  - `budget_tokens < max_tokens`（必须留可见输出空间）
- 业界默认值差异巨大：anthropic-sdk-python 示例 `1600`、`simonw/llm-anthropic` 复杂任务示例 `32000`、DeerFlow 2 README 把 `claude-sonnet-4.6` 配 `max_tokens: 4096` —— **DeerFlow 2 没有预设 budget_tokens，留给配置方决定**。
- 当前写死 10000 在 `max_tokens=8192` 或 `max_tokens=4096`（DeerFlow `claude-sonnet-4.6` 示例）的家庭配置下会直接 API 报错：`budget_tokens(10000) >= max_tokens(4096)`。

**Dependencies:** 无（独立后端改动；不依赖 U8）

**Files:**
- `server/apps/agent/services/deerflow_adapter/family_adapter_cache.py`（修改）
- `server/tests/agent/unit/test_family_adapter_cache.py`（新增/扩展）

**Approach:**

1. 删除 `ANTHROPIC_HIGH_EFFORT_BUDGET_TOKENS=10000` / `LOW=2000` 两个写死常量。改为引入与 fraction/floor/ceiling 相关的模块级常量：
   ```python
   # Anthropic extended-thinking budget tokens are computed as a fraction of
   # the model's per-response max_tokens. Anthropic API constraints (verified
   # via context7 against anthropic-sdk-python:examples/thinking.py and the
   # ModelInfo schema):
   #   - budget_tokens >= 1024  (hard minimum)
   #   - budget_tokens <  max_tokens  (must leave room for visible output)
   # Sources: anthropic-sdk-python `examples/thinking.py` (budget=1600,
   # max=3200 → ~50%), simonw/llm-anthropic README (32000 for complex tasks).
   # DeerFlow 2 itself does not prescribe a default — see
   # bytedance/deer-flow:backend/docs/CONFIGURATION.md.
   ANTHROPIC_BUDGET_MIN_TOKENS = 1024     # API hard minimum
   ANTHROPIC_HIGH_EFFORT_FRACTION = 0.60  # deep_think=true → 60% of max_tokens
   ANTHROPIC_LOW_EFFORT_FRACTION = 0.25   # deep_think=false (low tier) → 25%
   # Safety headroom so visible output isn't crowded out:
   ANTHROPIC_BUDGET_OUTPUT_HEADROOM_TOKENS = 256
   ```

2. 新增 helper 函数：
   ```python
   def _compute_anthropic_thinking_budget(
       max_tokens: int,
       fraction: float,
   ) -> int | None:
       """Compute Anthropic budget_tokens for the given max_tokens / fraction.

       Returns None when max_tokens is too small to satisfy
       budget >= ANTHROPIC_BUDGET_MIN_TOKENS *and* budget < max_tokens
       simultaneously — caller should fall back to thinking.type=disabled.

       Algorithm:
         raw = floor(max_tokens * fraction)
         capped = min(raw, max_tokens - ANTHROPIC_BUDGET_OUTPUT_HEADROOM_TOKENS)
         if capped < ANTHROPIC_BUDGET_MIN_TOKENS:
             return None
         return capped
       """
   ```

3. 修改 native Anthropic 分支（`provider == "anthropic"` 且 `thinking_supported=True`）：
   - 从 `ai_config` 读 `max_tokens`（已存在的字段；如缺失则 fall back 到一个保守默认 `4096`，与 DeerFlow `claude-sonnet-4.6` 示例对齐）。
   - 调 `_compute_anthropic_thinking_budget(max_tokens, ANTHROPIC_HIGH_EFFORT_FRACTION)` 得到 `high_budget`。
   - 如果 `high_budget is None`（max_tokens 太小，连 1024 都满足不了）：log warning，把 `when_thinking_enabled` 设成 `{"thinking": {"type": "disabled"}}`（降级，与 disabled 一致），并发 `info` 级日志解释。
   - 否则：`when_thinking_enabled = {"thinking": {"type": "enabled", "budget_tokens": high_budget}}`。
   - `when_thinking_disabled` 仍维持 `{"thinking": {"type": "disabled"}}`（不消费 LOW fraction —— LOW 留作未来 Anthropic `output_config.effort: "low"` 路径，仅作为常量声明）。
   - 在该分支正上方加 doc-comment，解释 fraction 选择来源与降级路径。

4. **不**改 OpenAI / OpenAI-compatible / DeepSeek 分支。

**Patterns to follow:** 现有 `_generate_temp_config` 中读 `ai_config` 字段的风格；`logger.info` 的格式。

**Test scenarios:**

- **常规 max_tokens**: `ai_config.max_tokens=16384` + thinking_supported=true → `when_thinking_enabled.thinking.budget_tokens == int(16384 * 0.60) == 9830`，`type == "enabled"`。
- **DeerFlow Claude Sonnet 4.6 默认**: `max_tokens=4096` → `int(4096 * 0.60) == 2457`；`min(2457, 4096-256) == 2457`；`>= 1024` ✅ → `budget_tokens == 2457`。
- **Haiku 紧约束**: `max_tokens=2048` → `int(2048 * 0.60) == 1228`；`min(1228, 2048-256) == 1228`；`>= 1024` ✅ → `1228`。
- **极小 max_tokens**: `max_tokens=1500` → `int(1500*0.60)=900`；`min(900, 1500-256)=900`；`< 1024` → returns None → 降级到 `{"type": "disabled"}` + warning log。
- **缺失 max_tokens**: `ai_config` 不含 `max_tokens` → 用 default `4096` → 走 Sonnet 4.6 案例。
- **AST 静态校验**: `family_adapter_cache.py` 不再含字面量 `10000` / `2000` 在 budget 上下文（只能在常量定义出现）。

**Verification:**

```bash
cd server/apps/agent && uv run ruff check services/deerflow_adapter/family_adapter_cache.py
cd server && uv run pytest tests/agent/unit/ -v   # 含 budget helper 单元测试
```

helper 函数纯算术，可独立测试，不依赖 deerflow runtime。

---

### U10. 系统配置 yaml：项目根新增 `system-config.yaml` — 🔄 待执行

**Goal:** 把"模型 max_tokens 默认值"这类不常变的系统级配置从代码常量移到项目根的 yaml 配置文件（与 `.env` / `docker-compose.yml` 同级），专用于维护"系统不常变配置"。这是后续 U11/U12/U13 的依赖基础。

**Why（用户原始诉求）:**

> "将这些值放到与.env同级的yaml文件中，并且该值仅作为用户在ai配置模型提供商时新增几个上下文上限的维护（默认根据模型前缀从系统配置值回写，用户可自行修改）"

把默认值从代码挪到 yaml 的好处：
- 运维不用 redeploy 就能改默认（OPS 友好，新模型上线只改 yaml）
- 多环境差异化（dev/staging/prod 各自的 max_tokens 上限可不同）
- 配置文件便于审计与 diff

**Dependencies:** 无（独立文件创建）

**Files:**
- `system-config.yaml`（新建，项目根，与 `docker-compose.yml` 同级）
- `system-config.example.yaml`（新建，示例，进 git；真正的 `system-config.yaml` 进 .gitignore？— 见 §Approach 决策）
- `.gitignore`（修改）

**Approach:**

1. 在项目根创建 `system-config.yaml`，结构：
   ```yaml
   # numina 系统级配置（不常变项）
   # 与 .env / docker-compose.yml 同级。修改后需重启 agent / backend 服务生效。
   #
   # 数据时间戳：2026-05-31，通过厂商官方文档 + 联网验证。
   # 维护者负责更新：当各厂商发布新模型或调整输出上限时。
   #
   # 本文件不含密钥；与环境无关的"模型规格"等元数据。
   # 环境密钥放 .env；家庭级用户配置放数据库 ai_providers 表。

   ai_models:
     # 输出 token 上限默认值（max_tokens 字段）。
     # 用户在前端"AI 模型提供商"表单的 max_tokens 字段留空时，
     # 后端按 model_id 前缀匹配并回写到 UI；用户可改。
     # 命中顺序敏感：更长前缀放前面。
     # 未命中前缀 → 用户必须显式填，否则 emit yaml 不写 max_tokens 键
     #   → SDK / 服务端默认接管。
     max_tokens_defaults_by_prefix:
       # ── OpenAI GPT-5 / o-series ──
       - prefix: gpt-5
         max_tokens: 128000
         note: GPT-5 / 5.1 / 5.2 / Codex 全 128K (openai.com/api 官方)
       - prefix: o1-pro
         max_tokens: 100000
       - prefix: o1-mini
         max_tokens: 65536
       - prefix: o1
         max_tokens: 100000
       - prefix: o3
         max_tokens: 100000
       - prefix: o4
         max_tokens: 100000
       # ── OpenAI 常规 ──
       - prefix: gpt-4o
         max_tokens: 4096
       - prefix: gpt-4-
         max_tokens: 4096
       - prefix: gpt-4
         max_tokens: 4096
       - prefix: gpt-3.5
         max_tokens: 4096
       # ── Anthropic Claude 4 系列 ──
       - prefix: claude-opus-4
         max_tokens: 64000
       - prefix: claude-sonnet-4
         max_tokens: 64000
       - prefix: claude-haiku-4
         max_tokens: 8192
       # ── Claude 3.x 系列 ──
       - prefix: claude-3-7
         max_tokens: 8192
         note: 8K base; 128K 需 'output-128k-2025-02-19' header（本系统不带）
       - prefix: claude-3-5
         max_tokens: 8192
       - prefix: claude-haiku
         max_tokens: 4096
       - prefix: claude-3-opus
         max_tokens: 4096
       - prefix: claude
         max_tokens: 8192
       # ── DeepSeek ──
       - prefix: deepseek-reasoner
         max_tokens: 8192
         note: API 接受 32K 但官方建议 ≤8K (AWS Bedrock model card)
       - prefix: deepseek-chat
         max_tokens: 8192
       - prefix: deepseek
         max_tokens: 8192
       # ── 阿里 Qwen / 通义 ──
       - prefix: qwen3-max
         max_tokens: 66000
         note: Alibaba 官方规格
       - prefix: qwen3
         max_tokens: 8192
       - prefix: qwen2.5
         max_tokens: 8192
       - prefix: qwen2
         max_tokens: 8192
       - prefix: qwen-max
         max_tokens: 8192
       - prefix: qwen-plus
         max_tokens: 8192
       - prefix: qwen-turbo
         max_tokens: 8192
       - prefix: qwen
         max_tokens: 8192
       - prefix: qwq
         max_tokens: 8192
       # ── Moonshot Kimi ──
       - prefix: kimi-k2
         max_tokens: 16384
       - prefix: moonshot-v1
         max_tokens: 16384
       - prefix: moonshot
         max_tokens: 16384
       - prefix: kimi
         max_tokens: 16384
       # ── 智谱 GLM ──
       - prefix: glm-4-6
         max_tokens: 128000
         note: GLM-4.6 官方 128K
       - prefix: glm-4.6
         max_tokens: 128000
       - prefix: glm-4-5
         max_tokens: 16384
       - prefix: glm-4.5
         max_tokens: 16384
       - prefix: glm-4
         max_tokens: 8192
       - prefix: glm
         max_tokens: 8192
       # ── MiniMax ──
       - prefix: MiniMax-M2
         max_tokens: 4096
       - prefix: minimax
         max_tokens: 4096
       # ── Google Gemini（如经 OpenAI-compatible 接入） ──
       - prefix: gemini-3
         max_tokens: 128000
       - prefix: gemini-2.5
         max_tokens: 65536
       - prefix: gemini-2
         max_tokens: 8192
       - prefix: gemini
         max_tokens: 8192
   ```

2. 同时建 `system-config.example.yaml`（与上面内容相同，作为模板示例进 git）。

3. **Git 策略决策**：
   - **方案 A（推荐）**：`system-config.yaml` 进 git（这些是公开规格信息、不含密钥）；运维要为某环境定制时复制为 `system-config.local.yaml` 不进 git。
   - **方案 B**：仅 `system-config.example.yaml` 进 git，部署方复制为 `system-config.yaml`（仿 `.env` 模式）。
   - 默认采用 **A** —— 这是规格元数据不是环境配置，没必要每个部署都复制。

4. **`.gitignore`** 加：
   ```
   /system-config.local.yaml
   ```

**Test scenarios:**
- yaml 用 `pyyaml.safe_load` 能 load 通过（无语法错）。
- prefix 字段全部 lowercase（除 `MiniMax-M2`，因为我们 case-insensitive 匹配）— 见 U11 helper。

**Verification:**
```bash
python -c "import yaml; yaml.safe_load(open('system-config.yaml'))"   # 解析 OK
```

---

### U11. 系统配置 loader：backend & agent 加 yaml 读取层 — 🔄 待执行

**Goal:** 给 backend 和 agent 各加一个 thin loader，读 `system-config.yaml`（启动时 load 一次进内存，热更需 SIGHUP 或 restart）。U12/U13 通过 loader 读 max_tokens 默认表。

**Dependencies:** U10（yaml 文件存在）

**Files:**
- `server/apps/backend/app/config/system_config.py`（新建）
- `server/apps/agent/app/config/system_config.py`（新建）
- `server/packages/core/system_config.py`（推荐共享 — 见 §Approach 决策）

**Approach:**

1. **共享方案（推荐）**：在 `server/packages/core/` 加 `system_config.py`，backend 和 agent 共用：
   ```python
   """System-level configuration loaded from project-root system-config.yaml.

   Contrast with:
   - .env / settings.py: environment-specific secrets and runtime params
   - DB ai_providers: per-family user config (overrides system defaults)
   """
   from __future__ import annotations
   import logging
   import os
   from functools import lru_cache
   from pathlib import Path
   from typing import Any
   import yaml

   logger = logging.getLogger(__name__)

   _CONFIG_FILENAME = "system-config.yaml"
   _LOCAL_OVERRIDE_FILENAME = "system-config.local.yaml"


   def _project_root() -> Path:
       """Walk up from server/ to find project root (contains docker-compose.yml)."""
       cur = Path(__file__).resolve()
       for _ in range(8):
           if (cur / "docker-compose.yml").exists():
               return cur
           cur = cur.parent
       raise RuntimeError("Cannot locate project root (no docker-compose.yml)")


   @lru_cache(maxsize=1)
   def get_system_config() -> dict[str, Any]:
       root = _project_root()
       primary = root / _CONFIG_FILENAME
       override = root / _LOCAL_OVERRIDE_FILENAME

       if not primary.exists():
           logger.warning("%s not found at %s; using empty system config",
                          _CONFIG_FILENAME, primary)
           return {}

       with open(primary, encoding="utf-8") as f:
           cfg: dict = yaml.safe_load(f) or {}

       if override.exists():
           with open(override, encoding="utf-8") as f:
               local: dict = yaml.safe_load(f) or {}
           cfg = _deep_merge(cfg, local)
           logger.info("Loaded system config with local override from %s", override)

       return cfg


   def _deep_merge(base: dict, override: dict) -> dict:
       """Recursive dict merge; override wins."""
       out = dict(base)
       for k, v in override.items():
           if k in out and isinstance(out[k], dict) and isinstance(v, dict):
               out[k] = _deep_merge(out[k], v)
           else:
               out[k] = v
       return out


   def get_max_tokens_default(model_id: str) -> int | None:
       """Resolve default max_tokens by model_id prefix (case-insensitive).

       Returns None if no prefix matches (caller should treat as 'no default').
       """
       if not model_id:
           return None
       cfg = get_system_config()
       table = (cfg.get("ai_models") or {}).get("max_tokens_defaults_by_prefix") or []
       low = model_id.lower()
       for entry in table:
           prefix = (entry.get("prefix") or "").lower()
           if prefix and low.startswith(prefix):
               value = entry.get("max_tokens")
               if isinstance(value, int) and value > 0:
                   return value
       return None
   ```

2. **测试热点**（`server/tests/packages/core/test_system_config.py`）：
   - 加载缺失文件 → 返回 {} + warning。
   - 加载语法错文件 → raise yaml.YAMLError（不容错，启动期就报）。
   - prefix match 顺序敏感（`claude-sonnet-4` 在 `claude` 之前）。
   - `local override` 文件存在时 deep-merge 覆盖。
   - `get_max_tokens_default("gpt-5-mini")` → `128000`。
   - `get_max_tokens_default("unknown-model")` → `None`。
   - `get_max_tokens_default("")` / `None` → `None`。

**Verification:**
```bash
cd server && uv run pytest tests/packages/core/test_system_config.py -v
cd server/apps/agent && uv run ruff check ../../packages/core/system_config.py
```

---

### U12. DB 层：`ai_providers` 表加 `max_tokens INTEGER NULL` 列 — 🔄 待执行

**Goal:** 把用户在 settings 表单的 max_tokens 显式输入持久化到数据库。null 表示"用户未填，按 yaml 推断"。

**Dependencies:** 无（独立 DB 改动；U13 消费此列）

**Files:**
- `server/apps/backend/app/models/ai_provider_config.py`（修改 — 加 ORM 列）
- `server/apps/backend/alembic/versions/<新 migration>.py`（新建）
- `server/apps/backend/app/schemas/ai_provider.py`（修改 — pydantic schema 加可选字段）
- `server/apps/backend/app/routers/ai_providers.py`（修改 — POST/PUT 接受 max_tokens）

**Approach:**

1. 新 migration（revision 自定义 12-char，down_revision 接到 `c8a1e7d3f4b2`）：
   ```python
   def upgrade() -> None:
       op.add_column(
           "ai_providers",
           sa.Column("max_tokens", sa.Integer(), nullable=True),
       )

   def downgrade() -> None:
       op.drop_column("ai_providers", "max_tokens")
   ```
2. ORM：
   ```python
   max_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
   ```
3. pydantic schema 与 router 的 POST/PUT body 接 max_tokens（int | None）。
4. 内部 GET（agent 用）把 max_tokens 透传到 dict。
5. **新增公开端点** `GET /api/v1/ai/providers/defaults?model_id=xxx`：
   ```python
   from packages.core.system_config import get_max_tokens_default
   @router.get("/providers/defaults")
   def get_provider_defaults(model_id: str):
       return {"max_tokens": get_max_tokens_default(model_id)}
   ```
   前端 U13 调这个端点回写 max_tokens 输入框默认值。

**Test scenarios:**
- migration up/down round-trip。
- POST `/api/v1/ai/providers` with `{"max_tokens": 32000}` → DB 行有该值。
- POST without max_tokens → DB 行 NULL。
- GET `/providers/defaults?model_id=gpt-5` → `{"max_tokens": 128000}`。
- GET `/providers/defaults?model_id=unknown` → `{"max_tokens": null}`。

---

### U13. agent 层：`family_adapter_cache.py` emit max_tokens — 🔄 待执行

**Goal:** 让 `_generate_temp_config` 把"用户配置 max_tokens / yaml 默认值"二选一注入到 model entry yaml；为 U9 计算 budget_tokens 提供数值。

**Dependencies:** U10 (yaml) + U11 (loader) + U12 (DB 列)

**Files:**
- `server/apps/agent/services/deerflow_adapter/family_adapter_cache.py`（修改）
- `server/tests/agent/unit/test_family_adapter_cache.py`（新增/扩展）

**Approach:**

1. import：
   ```python
   from packages.core.system_config import get_max_tokens_default
   ```

2. 新增 helper：
   ```python
   def _resolve_max_tokens(ai_config: dict) -> int | None:
       """Resolve effective max_tokens with priority:
         1. ai_config['max_tokens']  (user-set in DB)
         2. system-config.yaml prefix-matched default
         3. None  → emit no max_tokens key in model entry
       """
       explicit = ai_config.get("max_tokens")
       if isinstance(explicit, int) and explicit > 0:
           return explicit
       model_id = (ai_config.get("ai_model_id") or "").strip()
       return get_max_tokens_default(model_id)
   ```

3. 在 `_generate_temp_config` 构造 `model_entry` 后：
   ```python
   resolved_max = _resolve_max_tokens(ai_config)
   if resolved_max is not None:
       model_entry["max_tokens"] = resolved_max
   ```

4. **U9 接入**：native Anthropic 分支 `_compute_anthropic_thinking_budget(resolved_max or 4096, ...)`。

5. **U9 修订**：之前 plan 用代码内 `_MAX_TOKENS_DEFAULTS_BY_MODEL_PREFIX` 现已迁移到 yaml + loader；U9 不需再改前缀表，只读 `_resolve_max_tokens` 结果。

**Test scenarios:** （Mock `get_max_tokens_default` 隔离 yaml 文件依赖）
- **Explicit override**: `ai_config={"max_tokens": 2048, "ai_model_id":"gpt-5"}` → 2048（不查 yaml）。
- **Prefix hit via yaml**: `ai_config={"ai_model_id":"gpt-5"}` + mock loader 返回 128000 → emitted yaml 含 `max_tokens: 128000`。
- **Prefix miss**: mock loader 返回 None → emitted yaml 不含 max_tokens key。
- **Negative explicit**: `max_tokens=-1` → ignored，回退 yaml。
- **U9 联动**: Claude Sonnet 4 (yaml=64000) + thinking → `budget=int(64000*0.60)=38400`，远超 1024 floor。
- **U9 联动 fallback**: yaml 命中 None + Anthropic + thinking → 用 4096 兜底 → `budget=2457`。

**Verification:**
```bash
cd server/apps/agent && uv run ruff check services/deerflow_adapter/family_adapter_cache.py
cd server && uv run pytest tests/agent/unit/test_family_adapter_cache.py -v
```

---

### U14. Frontend：AI provider 表单加 max_tokens 字段（默认值回写）— 🔄 待执行

**Goal:** 用户在"添加/编辑 AI 模型提供商"表单填 model_id 时，自动调 `GET /api/v1/ai/providers/defaults?model_id=xxx` 把 yaml 推断的默认值预填到 max_tokens 输入框。用户可改可清空（清空 = 走 yaml 默认 / SDK 默认）。

**Dependencies:** U10 (yaml) + U11 (loader) + U12 (DB 列 + defaults 端点)

**Files:**
- `frontend/apps/main/src/pages/SettingsAIPage.vue`（或 provider 表单组件）（修改）
- `frontend/apps/main/src/api/ai.ts`（修改 — 加 `getProviderDefaults(modelId)`）

**Approach:**

1. 加 API 调用：
   ```ts
   export async function getProviderDefaults(modelId: string): Promise<{ max_tokens: number | null }> {
     return await api.get('/ai/providers/defaults', { params: { model_id: modelId } })
   }
   ```

2. 表单加字段：
   ```vue
   <van-field
     v-model.number="form.max_tokens"
     label="单次输出上限"
     placeholder="留空走系统默认"
     type="digit"
     :hint="defaultsHint"
   />
   ```
   `defaultsHint` 显示 "GPT-5 系统默认 128000 tokens（联网验证 2025-2026）"。

3. `model_id` blur 时调 `getProviderDefaults`：
   - 若返回非 null **且**用户当前 `max_tokens` 为空：预填该值。
   - 若返回 null：placeholder 改成 "未识别模型，请按厂商文档填写或留空"。
   - 若用户已经手动改过（form dirty flag），不覆盖。

4. i18n key：`settings.aiProvider.maxTokensLabel` / `settings.aiProvider.maxTokensHint`。

**Test scenarios:**
- 输入 `gpt-5-mini` → blur → max_tokens 输入框预填 128000。
- 用户先改成 32000 → 再 blur → **保持 32000 不覆盖**。
- 输入未知模型 `my-finetune-v1` → blur → max_tokens placeholder 提示且不预填。
- 提交表单（max_tokens=32000）→ POST body 含 `max_tokens: 32000`。
- 提交表单（max_tokens=空）→ POST body 含 `max_tokens: null`。

**Verification:**
```bash
cd frontend/apps/main && pnpm typecheck && pnpm test:run
```

---


## Scope Boundaries

### In scope (this PR)

- **U8**: native OpenAI → Responses API（`use_responses_api: true` + `output_version: responses/v1`）
- **U9**: Anthropic budget_tokens 按已解析的 max_tokens 动态计算（fraction-based 60%/25%）
- **U10**: 项目根新增 `system-config.yaml`（系统不常变配置，含 `ai_models.max_tokens_defaults_by_prefix`）
- **U11**: backend & agent 共享 yaml loader（`packages/core/system_config.py`），提供 `get_max_tokens_default(model_id)`
- **U12**: `ai_providers` 表加 `max_tokens INTEGER NULL` 列 + 公开端点 `GET /api/v1/ai/providers/defaults?model_id=xxx`
- **U13**: agent 层 `family_adapter_cache._resolve_max_tokens` 三段优先级（user → yaml → None）+ emit
- **U14**: 前端表单加 max_tokens 字段 + 默认值回写（model_id blur 调 defaults 端点）

### Already done

- U1–U7、U2'（见各 unit "✅ done" 标记）

### Deferred to follow-on

- **OpenAI-compatible 网关切 Responses API**：DashScope/Novita/vLLM 大多不支持 Responses，本计划不切。
- **Anthropic `output_config.effort: "low"`** 作为 LOW 路径的真正实现。
- **Anthropic `thinking.type="adaptive"`**（beta）。
- **OpenAI `verbosity` 字段**（Responses: `text.verbosity`）：未来加 UI"详尽 vs 简洁"开关时再补。
- **真实 web search 工具接入**：本计划仍只做行为引导。
- **system-config.yaml 热更新（SIGHUP）**：当前重启服务才生效；未来如需动态生效再补。

### Outside this product's identity

- 不引入第三个系统智能体；本计划是收敛而非扩展。
- 不重写 skill 管理；不动 `_resolve_skills`。

---

## Decisions Locked-in（已确认）

1. **U8 范围**：宽方案 — 所有 native OpenAI（含 GPT-4o）都加 `use_responses_api: true` + `output_version: responses/v1`。
2. **U9 fraction**：60% (high) / 25% (low)，与 anthropic-sdk-python 官方示例 50% 同量级。LOW 仅声明，运行时降级走 `{"thinking":{"type":"disabled"}}`。
3. **max_tokens 默认值放 yaml**：与 `.env` 同级的 `system-config.yaml`，运维可改不用 redeploy。
4. **覆盖范围**：18+ 类厂商（OpenAI / Claude / DeepSeek / Qwen / QwQ / Kimi / Moonshot / MiniMax / GLM / Gemini）。未命中前缀 → emit yaml 不写 max_tokens 键 → SDK / 服务端默认接管。
5. **默认值采用 2025-2026 联网验证的官方规格**：GPT-5 128K / Claude 4 系列 64K / Qwen3 Max 66K / Kimi K2 16K / GLM-4.6 128K / Gemini 3 Pro 128K。
6. **三段优先级**：用户显式 (DB) > yaml prefix 默认 > None。
7. **前端默认回写策略**：model_id blur 时调 defaults 端点；用户已 dirty 不覆盖；未识别模型 placeholder 提示。
8. **Git 策略**：`system-config.yaml` 进 git（公开规格，无密钥）；`system-config.local.yaml` 进 .gitignore（运维定制覆盖）。
9. **U8–U14 同 PR 推**：DB / 配置 / 后端 / 前端一次性到位，避免半成品状态。

---

## Risks & Mitigations

- **R1（U8）：langchain-openai 旧版本可能不识别 `use_responses_api`**。
  - **缓解**：DeerFlow 2 harness 是字段消费方，不是 langchain-openai；harness 在 emit 到 langchain 时已做版本兼容（DeerFlow README `gpt-5-responses` 示例就是这条路径）。
  - **回滚**：删 model_entry 中两行即可还原 U2' 的 Chat Completions 路径。
- **R2（U8）：`reasoning_effort` 在 Responses 与 Chat Completions 形态不同**（顶层 vs `reasoning.effort`）。
  - **缓解**：DeerFlow harness 自动适配（看 `use_responses_api` flag 决定 emit 形态）。
- **R3（U9）：max_tokens 太小（< 1707）时无法满足 budget>=1024 又 budget<max_tokens**。
  - **缓解**：`_compute_anthropic_thinking_budget` 返回 None，分支降级到 `{"thinking":{"type":"disabled"}}` 并发 info 日志。
- **R4（U9）：fraction 选 0.60 与官方 50% 示例不完全一致**。
  - **缓解**：60% 让 deep_think 在 max_tokens 紧的场景下也能满足 1024 floor。如 reviewer 反对，让步到 0.50。
- **R5（U10）：yaml 文件丢失或语法错**。
  - **缓解**：loader 缺失 → 返回 {} + warning（不阻 boot）；语法错 → raise yaml.YAMLError（启动期立即失败，不带病运行）。
- **R6（U10）：`system-config.local.yaml` 进了 git**。
  - **缓解**：`.gitignore` 加 entry；CI 加 grep 检查"不允许 system-config.local.yaml 出现在 commit"。
- **R7（U11）：lru_cache 在多进程 worker 下各自缓存一份**。
  - **缓解**：可接受 — yaml 解析极快（<5ms），首次访问后即缓存。重启所有 worker 一致。
- **R8（U12）：alembic head 多分支**。
  - **缓解**：down_revision 严格接 `c8a1e7d3f4b2`；写完后 `alembic heads` 必须返回单 head。
- **R9（U13）：用户 `max_tokens` 显式填 0 / 负数**。
  - **缓解**：helper 中 `isinstance(explicit, int) and explicit > 0` 守卫，falsy 视作"未填"，回退 yaml。
- **R10（U14）：用户在表单填了又清空，预期是 null（走 yaml）但前端发空字符串**。
  - **缓解**：API client 把空串 → null；后端 schema 标注 `max_tokens: int | None = None`。

---

## Verification Strategy

按 unit 顺序：

1. **U10**：
   ```bash
   python -c "import yaml; yaml.safe_load(open('system-config.yaml'))"
   ```
2. **U11**：
   ```bash
   cd server && uv run pytest tests/packages/core/test_system_config.py -v
   ```
3. **U12**：
   ```bash
   cd server && uv run alembic -c apps/backend/alembic.ini heads   # 单 head
   uv run pytest tests/backend/test_ai_providers_max_tokens.py -v   # CRUD 测试
   ```
4. **U13**：
   ```bash
   cd server/apps/agent && uv run ruff check services/deerflow_adapter/family_adapter_cache.py
   cd server && uv run pytest tests/agent/unit/test_family_adapter_cache.py -v
   ```
5. **U8 / U9**：包含在 U13 测试用例中（断言 yaml emit 形态 + Anthropic budget 计算）。
6. **U14**：
   ```bash
   cd frontend/apps/main && pnpm typecheck && pnpm test:run
   ```
7. **端到端 smoke（手动）**：起 docker-compose → 在 settings 添加 `gpt-5` provider → 看 max_tokens 输入框预填 128000 → 不改直接保存 → DB 行 max_tokens=128000（用户已确认）→ 数鸣对话开 deep_think → agent 日志含 `use_responses_api: true` + `reasoning.effort: high`。

---

## Future Considerations

- **OpenAI Responses 新字段**：`text.verbosity`、`reasoning.summary` 都是后续 UX 提升点。
- **Anthropic `output_config`** GA 后用它替代 thinking.type=disabled 的 LOW 路径模拟。
- **system-config.yaml 扩展**：未来可放更多元数据（不同 provider 的默认 timeout、不同 capability 的默认 cost weights 等）。
- **DeerFlow 3** 如果加抽象层把"low/medium/high effort"统一到 provider-agnostic 字段，我们可以删掉所有 vendor-specific 分支。
- **真实 web search 工具**建议作为 MCP server 或 DeerFlow tool slot 接入。
