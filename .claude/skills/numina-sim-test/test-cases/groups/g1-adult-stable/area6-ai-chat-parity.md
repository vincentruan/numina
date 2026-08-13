# Area 6 — AI chat DeerFlow-fidelity parity (输入/输出/系统集成 + 设计出入)

Shared conventions in [`_common.md`](../../_common.md).

> **Why this area exists:** the user's explicit ask — "main app的ai功能是非常关键的测试功能点,需要细化,chat整体的交互细节需要复刻deerflow... 需要细化输入、输出(对话、报告、系统集成),是不是有跟设计出入?" This area tests the numina AI chat against DeerFlow's interaction contract (reference repo `/Users/vincentruan/geek_space/github/deer-flow-reference`), flags **design divergences** (跟设计出入), and adds fine-grained input/output/system-integration cases.
>
> **Grounded comparison basis:** numina already mirrors DeerFlow on most contract points (LangGraph SDK `useStream`/`client.runs.stream` with `streamMode:['messages-tuple','values','custom']`, 6 message group types via `useMessageGroups`, ChainOfThought single renderer, 4-preset token-usage system, SubtaskCard, HumanInputCard, cookie-auth + `X-Family-Id`/`X-User-Id`, slash-skill autocomplete, SuggestionChips). The cases below verify each parity point and flag the confirmed divergences (D1–D7, see the table below).

Auth: adult session as `demouser` via cookie+localStorage injection (SKILL.md "Phase 2 fallback"). AI must be enabled + a provider configured. All cases on `${BASE}ai/chat` unless noted.

## Confirmed design divergences (跟设计出入) — test + flag these

> These were verified against source on branch `feat/two-ai-apps-unified-dispatch`.
> Disposition set by the user 2026-07-21:
> **D1/D2/D3 = 实现遗漏, 同步 DeerFlow 实现; D4 = 设计如此 (按模式自动选择); D5 = 待按手机端设计适配后引入.**
> **D6/D7 added 2026-07-21** via DeerFlow `core/scheduled-tasks/` + `core/threads/utils.ts` audit:
> D6 = 功能级缺口 (独立提案, 非 chat parity bug); D7 = DeerFlow 特有 (numina 无 IM 桥接, 设计如此不引入).

| # | DeerFlow has | Numina status (grounded) | Disposition | Evidence |
|---|--------------|--------------------------|-------------|----------|
| D1 | `/goal <condition>` slash command (PUTs goal + submits condition as next task → run starts; `/goal` status + `/goal clear` do NOT start a run) + `GoalStatus` bar above composer | **✅ 已实现 2026-07-21** — slash infra (U1) + `GET/PUT/DELETE /api/threads/{id}/goal` (U2, threads.py:882/900/927, checkpoint `channel_values["goal"]` no DB migration) + worker 续跑循环 (U4, `_stream_once` loop + 独立非思考评估器 LLM + `continuation_count/max` 8 + `no_progress_count/max` 2 双熔断 + per-thread lock) + `GoalStatusBar.vue` + `useActiveGoal.ts` optimistic-UI 对账 (U5) | **DONE** | `server/apps/agent/routers/threads.py:882,900,927` (goal endpoints), `server/apps/agent/services/goal_store.py` (R1b clamp 8), `server/apps/agent/services/goal_evaluator.py`, `server/apps/agent/services/runtime/worker.py:2148` (`_stream_once`), `:1664` (`_prepare_goal_continuation_input`), `frontend/apps/main/src/components/ai-chat/GoalStatusBar.vue`, `composables/ai-chat/useActiveGoal.ts`, `api/ai-chat.ts:331,341,359` (`getThreadGoal`/`setThreadGoal`/`clearThreadGoal`), `tests/unit/test_goal_endpoints.py` + `test_goal_continuation.py` (48 passed) |
| D2 | `/compact` slash command (POSTs to compact endpoint; skipped on new/empty threads) | **✅ 已实现 2026-07-21** — `POST /api/threads/{id}/compact` (U6, threads.py:1224) directly imports DeerFlow canonical `compact_thread_context` (KTD-5, no hand-written message partitioning — handles `RemoveMessage(ALL)` + preserved tail + `channel_versions` bump + `summary_text`); transient bridge (`ref<Message[]>` + `watch(visibleHistory)` prune, ported from DeerFlow hooks.ts) prevents UI flicker; owner/adult role gate (KTD-8) | **DONE** | `server/apps/agent/routers/threads.py:1224` (`compact_thread_endpoint`), `server/apps/agent/services/compact_service.py` (thin wrapper around `compact_thread_context`), `frontend/apps/main/src/api/ai-chat.ts:223` (`compactThread`), `composables/ai-chat/useThreadChat.ts:193` (transient bridge), `tests/unit/test_compact_endpoint.py` (passed) |
| D3 | Input-polish button (sparkles) — rewrites draft via backend, spinner + undo | **✅ 已实现 2026-07-21** — `POST /api/input-polish` (agent router, `verify_family_token` cookie auth) + `services/input_polish.py` (reuses `_create_lightweight_llm`) + `InputBox.vue` polish button/undo/abort + `polishInputDraft` API client + 6 i18n keys | **DONE** | `server/apps/agent/routers/input_polish.py`, `server/apps/agent/services/input_polish.py`, `frontend/.../InputBox.vue` (`onPolishInput`/`onUndoPolishInput`/`abortInputPolish`), `api/ai-chat.ts:polishInputDraft` |
| D4 | User-selectable `reasoning_effort` selector (`minimal|low|medium|high`, desktop only) | **设计如此, 不改** — `reasoning_effort` is auto-set per mode (`INPUT_MODE_CONFIGS[mode].reasoning_effort`), not user-selectable | **BY DESIGN** — user confirmed 2026-07-21: 根据模式自动选择 is intentional | `InputBox.vue:206,221,265,344` (`reasoning_effort`); `INPUT_MODE_CONFIGS` at `:216,221,265`; `getResolvedMode` at `:271,283`; `supports_thinking` at `:210,283` |
| D5 | `TodoList` bar above composer driven by `write_todos` tool (plan mode pro/ultra) | **✅ 已实现 2026-07-21** — 移动端 Vant 4 适配设计 + 实现 (U7): `TodoListBar.vue` (`van-collapse` + 只读 `van-checkbox` + `van-tag` 状态, 默认折叠, ≥44px 触控区) + `useThreadTodos.ts` (从 `thread.values.todos` 派生) + langchain `TodoListMiddleware` 挂载 (worker.py:2086 `plan_mode=True` 时注入, sync `before_model`/`after_model` 规避风险 1, 模块级单例规避风险 2) + `todos` channel + `merge_todos` reducer | **DONE** | `docs/design/ai-chat-todolist-mobile-adaptation.md` (设计规格), `frontend/apps/main/src/components/ai-chat/TodoListBar.vue`, `composables/ai-chat/useThreadTodos.ts`, `server/apps/agent/services/deerflow_adapter/todo_middleware.py`, `services/runtime/worker.py:2086` (plan_mode gate injection) |
| D6 | Scheduled Tasks — full user-level AI task scheduling subsystem: create task with prompt + cron/once schedule, recipes (trending/news/issues/weekly), pause/resume/trigger, run history | **无用户级实现** — numina `server/apps/agent/app/scheduler.py` is APScheduler infra (all `add_job` calls commented out); `server/apps/scheduler_worker/scheduler.py` runs 7 system-preset jobs (exchange_rate/reminder_daily/snapshot_daily etc.), NOT user-created tasks. Zero grep hits for `scheduled_task\|ScheduledTask\|schedule_spec\|context_mode` in frontend + server business code | **独立提案 / 非 chat parity bug** — DeerFlow's scheduled-tasks is a complete standalone product subsystem (frontend page + 10 gateway routes + model + migration + 6 test files). numina's self-hosted family-asset positioning needs product evaluation before adopting (e.g. "weekly auto family-finance report"). High cost: model+migration+gateway router+worker bridge to `stream_run`+frontend page+cron input+i18n. Track as feature proposal, NOT as chat parity regression | DeerFlow `frontend/src/core/scheduled-tasks/{types,api,recipes,hooks,cron}.ts` + `app/workspace/scheduled-tasks/page.tsx` + `components/workspace/{thread-scheduled-tasks-link,scheduled-task-schedule-input}.tsx` + `backend/app/gateway/routers/scheduled_tasks.py`; numina `server/apps/agent/app/scheduler.py:91` (APScheduler placeholder), `server/apps/scheduler_worker/scheduler.py` (7 system jobs) |
| D7 | Thread Channel Source — `ChannelThreadSource` (`{type:"im_channel",provider,label}`) identifying which IM channel (Telegram/Slack/Discord/Feishu/DingTalk/WeChat/WeCom) a thread originated from; icon+badge in chat list + thread detail | **无对应实现** — zero grep hits for `channel_source\|ChannelThreadSource\|im_channel` in numina. `telegram` hits are unrelated (notification push via `NotificationConfigPage` + `notification/sender.py`, NOT bidirectional IM bridge). numina `createThread(source)` (`api/ai-chat.ts:103`) `source` param is a free-text page-route origin string (e.g. `wish_detail`/`liability_detail`), NOT an IM provider | **设计如此, 不引入** — channel-source is the display derivative of DeerFlow's IM-bridge subsystem (`backend/app/channels/` + 7 provider connectors). numina is self-hosted with web/child-app-only chat entries; no IM bridge design, so channel-source has no metadata source to display. Migrating the UI alone is meaningless. Note: do NOT confuse numina's existing `createThread(source)` page-route origin with channel_source — different concepts | DeerFlow `frontend/src/core/threads/utils.ts:5,76` (`ChannelThreadSource` + `channelSourceOfThread`) + `components/workspace/{thread-channel-source.tsx, channels/channel-provider-icon.tsx}` + `backend/app/channels/`; numina `api/ai-chat.ts:103` (`createThread(source)` = route origin) |

> **Reporting divergences:** D3 is now an implemented feature — test it as a
> normal parity case (C6.6). D4 is by-design — do NOT flag as a divergence; the
> test asserts the auto-per-mode behavior. D1/D2/D5 are **✅ implemented
> 2026-07-21** (see `docs/plans/2026-07-21-001-...-plan.md` U1-U7; U3 GoalMiddleware
> removed per KTD-9 to align with DeerFlow) — test as normal parity cases. D6 is
> a **feature-level gap** (independent proposal, not a chat parity regression) —
> do NOT test as a bug; record as "独立提案 D6". D7 is **by-design not adopted**
> (numina has no IM bridge) — do NOT test; record as "设计如此 D7". Do NOT mark
> pending/by-design items as bugs.

---

## Section 1 — Input (composer) fidelity

### C6.1 Mode presets + auto-downgrade (parity ✓)

```
bsk navigate ${BASE}ai/chat --session <id> --wait-until networkidle
bsk snapshot --session <id>
bsk click @eN --session <id>     # open mode selector
bsk snapshot --session <id>
```

Assertions (parity with DeerFlow four-mode selector):
- [ ] Four presets available: `flash | thinking | pro | ultra` (thinking hidden/aliased when `selectedModel.supports_thinking === false` — `InputBox.vue:210`)
- [ ] Each mode sets `reasoning_effort`: ultra→high, pro→medium, thinking→low, flash→minimal (verify via `INPUT_MODE_CONFIGS` — `InputBox.vue:216,221,265,344`)
- [ ] Selecting `thinking`/`pro`/`ultra` on a non-`supports_thinking` model auto-downgrades (`getResolvedMode`, `InputBox.vue:271,283`)
- [ ] `subagent_enabled` gated to `ultra` mode ( DeerFlow parity: `subagent_enabled = mode === "ultra"`)
- [ ] Selected mode persists across navigation/reload (`getLastSelectedMode`)
- [ ] `[console]` zero errors

### C6.2 Model selector — search + capability tags

```
bsk navigate ${BASE}ai/chat --session <id> --wait-until networkidle
bsk snapshot --session <id>     # capture the model selector entry ref
bsk click @eN --session <id>     # model selector entry → open popup
bsk snapshot --session <id>
```

Assertions:
- [ ] `ModelSelectorPopup` renders with search
- [ ] Each model shows capability tags: `supports_thinking` → thinking tag, `supports_vision` → vision tag (`ModelSelectorPopup.vue:48-49`)
- [ ] Selecting a model re-resolves the current mode against `supports_thinking`
- [ ] `[console]` zero errors

### C6.3 Attachments — upload-limit validation (parity ✓)

```
bsk navigate ${BASE}ai/chat --session <id> --wait-until networkidle
# Open the attachment affordance in InputBox
bsk snapshot --session <id>
bsk click @eN --session <id>     # paperclip / attach
```

Assertions (DeerFlow parity: client-side upload-limit validation with localized toasts):
- [ ] Attachments accepted (paperclip / drag-drop / paste if implemented)
- [ ] Upload-limit validation: max_files / max_file_size / max_total_size enforced client-side with localized toast on violation
- [ ] `[console]` zero errors

### C6.4 Voice input — SpeechRecognition (parity ✓)

```
bsk navigate ${BASE}ai/chat --session <id> --wait-until networkidle
bsk evaluate --session <id> --expr "'webkitSpeechRecognition' in window || 'SpeechRecognition' in window ? 'supported' : 'unsupported'"
# if supported, click the voice toggle
bsk snapshot --session <id>
bsk click @eN --session <id>     # voice / mic toggle
```

Assertions (DeerFlow parity: continuous + interim, locale-aware, auto-restart):
- [ ] `VoiceInputButton` + `useSpeechRecognition` composable present (`composables/ai-chat/useSpeechRecognition.ts`)
- [ ] On a browser with SpeechRecognition: mic toggle starts recognition; interim transcript appears in the input; square toggle stops
- [ ] On a browser WITHOUT SpeechRecognition: button feature-detects and no-ops gracefully (no crash)
- [ ] `[console]` zero errors

### C6.5 Slash-skill autocomplete (parity ✓)

```
bsk navigate ${BASE}ai/chat --session <id> --wait-until networkidle
bsk snapshot --session <id>
# type a leading slash
bsk fill @eN --value / --session <id>
bsk wait-ms 300
bsk snapshot --session <id>
```

Assertions (DeerFlow parity: ArrowUp/Down nav, Enter/Tab apply, Esc dismiss):
- [ ] Leading `/` triggers slash-skill autocomplete popup
- [ ] Builtins (e.g. `/goal`, `/compact` per DeerFlow) — **D1/D2 ✅ 已实现 2026-07-21**: slash infra (U1 `SlashPalette.vue` + `useSlashCommands.ts`) wired into live `InputBox.vue`; `/goal <condition>` → PUT + submit-as-run, `/goal` → status toast, `/goal clear` → DELETE, `/compact` → POST compact endpoint. Test as normal builtin slash commands
- [ ] ArrowUp/Down navigates, Enter/Tab applies, Esc dismisses
- [ ] `[console]` zero errors

### C6.6 Input polish button (D3 — ✅ implemented 2026-07-21)

```
bsk navigate ${BASE}ai/chat --session <id> --wait-until networkidle
bsk snapshot --session <id>
# type a rough draft
bsk fill @eN --value 帮我看看资产 --session <id>
bsk snapshot --session <id>     # polish button enabled (sparkles)
bsk click @eM --session <id>     # polish button
bsk wait-ms 4s                  # single LLM call
bsk snapshot --session <id>     # rewritten text in textarea + undo button
bsk screenshot --session <id> --out dogfood-output/c6.6-input-polish.png
# click undo
bsk snapshot --session <id>
bsk click @eU --session <id>     # undo button
bsk snapshot --session <id>     # original draft restored
```

Assertions (D3 implemented — `POST /api/input-polish`, `services/input_polish.py` reuses `_create_lightweight_llm`):
- [ ] Polish button (sparkles icon) renders in the composer toolbar, between web-search and plus
- [ ] Button **disabled** when input empty, when input starts with `/` (don't polish slash commands), or while streaming/submitted
- [ ] Clicking polish: spinner shows on the button while the LLM call is in flight
- [ ] On success with `changed=true`: textarea replaced with rewritten text; button swaps to an **undo** icon
- [ ] Undo restores the original draft; undo button disappears once the user edits the rewritten text
- [ ] On `changed=false` (already clear): toast `aiChat.inputPolishNoChanges`, textarea unchanged, no undo
- [ ] No-LLM fallback: if no provider configured, returns original unchanged (no error toast)
- [ ] Staleness: editing the textarea mid-polish discards the result (no stale overwrite)
- [ ] Abort on unmount/thread-switch: in-flight polish is cancelled (no late overwrite)
- [ ] `[console]` zero errors

### C6.7 Submit button mode-awareness + blocked states (parity ✓)

```
bsk snapshot --session <id>     # idle
bsk fill @eN --value 测试 --session <id>
bsk snapshot --session <id>     # ready (submit arrow)
# (streaming state tested in C6.8)
```

Assertions (DeerFlow parity: ready→submit arrow, streaming→stop square, error→error state; blocked when uploading / open human-input card / history loading):
- [ ] Idle with empty input: submit disabled
- [ ] Input present: submit enabled (arrow)
- [ ] Streaming: button becomes stop (square) — clicking stops the run
- [ ] Submit blocked while uploading attachments
- [ ] Submit blocked while a `HumanInputCard` (clarification) is open (`HumanInputCard.vue` pending state)
- [ ] Submit blocked while history is loading on an existing thread
- [ ] `[console]` zero errors

### C6.8 Suggestion chips after run (parity ✓)

```
# After a completed run (C6.9), verify follow-up suggestions
bsk snapshot --session <id>
```

Assertions (DeerFlow parity: POST /suggestions with last 6 messages; clicking with existing text → replace/append dialog):
- [ ] `SuggestionChips` component renders above/below composer after a run (`components/ai/SuggestionChips.vue`)
- [ ] Chips populated from stream `custom` `suggestions` event (`useThreadChat.ts:197,557`)
- [ ] Clicking a chip with existing input text → replace/append dialog (DeerFlow parity); with empty input → fills + sends (or fills, per numina impl — verify actual behavior)
- [ ] `[console]` zero errors

---

## Section 2 — Output: conversation rendering

### C6.9 Send + stream — no blank/duplicate/stuck (regression set)

```
bsk navigate ${BASE}ai/chat --session <id> --wait-until networkidle
bsk snapshot --session <id>
bsk fill @eN --value 帮我分析一下我的资产情况 --session <id>
bsk click @eM --session <id>
bsk wait-ms 8s
bsk snapshot --session <id>
```

Assertions:
- [ ] User bubble appears immediately (optimistic, right-aligned, `AiUserBubble` + sendStatus)
- [ ] Three-dot `StreamingIndicator` during first model round-trip
- [ ] Assistant text streams in via `messages-tuple` events (appended by id)
- [ ] No blank/thinking-only response (blank-response fallback `aiChat.noResponseFallback`)
- [ ] No duplicate greeting on retry (`hasPriorProgress` anchored on `userMsg.id`)
- [ ] "发送中" / in-progress states cleared after stream (`finalizeAllInProgress` on every end/error path)
- [ ] `[console]` zero errors

### C6.10 Message groups — all 6 types render (parity ✓)

```
# Drive a run that exercises tool calls + clarification + (if ultra) subagent + present-files
bsk fill @eN --value 帮我查一下最新的LPR利率并整理成文件 --session <id>   # needs websearch + may produce artifact
bsk click @eM --session <id>
bsk wait-ms 12s
bsk snapshot --session <id>
```

Assertions (DeerFlow 6 group types via `useMessageGroups`):
- [ ] `human` — user bubble (right, plain text verbatim, no markdown parse)
- [ ] `assistant` — `AiFinalAnswer` + `MarkdownContent` (DOMPurify `v-html`, shiki code blocks)
- [ ] `assistant:processing` — `ChainOfThought` (reasoning + tool calls + planning; single renderer; pending/running/done statuses; expand/collapse)
- [ ] `assistant:clarification` — `HumanInputCard` (question/options/choiceWithOther/multiSelect; pending/answered/error)
- [ ] `assistant:present-files` — `ArtifactFileList` cards
- [ ] `assistant:subagent` — `SubtaskCard` (collapsible, ShineBorder/glow while in_progress)
- [ ] `[console]` zero errors

### C6.11 Markdown rendering — code blocks + tables (v-html survival)

```
bsk fill @eN --value 用表格对比雪球法和雪崩法 --session <id>
bsk click @eM --session <id>
bsk wait-ms 8s
bsk snapshot --session <id>
```

Assertions:
- [ ] Markdown tables render with **DOM-injected action bars surviving `v-html` re-render** (`MarkdownContent.vue:272` table fix — DeerFlow table action bar parity)
- [ ] Code blocks render with language header bar; streaming code blocks distinct (`data-streaming-code-block`)
- [ ] Inline code distinct from blocks
- [ ] `[console]` zero errors

### C6.12 ChainOfThought — single renderer + step statuses (parity ✓)

```
# Run that triggers tool calls (e.g. asset overview via family-data MCP)
bsk fill @eN --value 调用工具看一下我的家庭资产概览 --session <id>
bsk click @eM --session <id>
bsk wait-ms 10s
bsk snapshot --session <id>
```

Assertions (DeerFlow parity: single `ChainOfThought` renderer, NOT separate PlanningStepsPanel — the removed-redundant-panel fix):
- [ ] `ChainOfThought` single renderer (`ChainOfThought.vue:42-55,526,704-716`) — no separate `PlanningStepsPanel`
- [ ] Steps: assistantText / reasoning / toolCall; steps before last tool call collapsible ("more/less")
- [ ] Step statuses `complete|active|pending` with vertical connector line
- [ ] `custom` event `tool_call` → planning step; `tool_result` → step done + result attached
- [ ] Per-tool-name renderers: web_search (link badges), web_fetch (globe+title), write_file/str_replace (clickable → artifact), bash (command block), generic WrenchIcon
- [ ] `[console]` zero errors

### C6.13 HumanInputCard — clarification round-trip (parity ✓)

```
# Ask an ambiguous question that triggers ask_clarification
bsk fill @eN --value 帮我分析一下 --session <id>   # deliberately vague
bsk click @eM --session <id>
bsk wait-ms 8s
bsk snapshot --session <id>
```

Assertions (DeerFlow parity: clarification ends run as `success` NOT `interrupted`; composer disabled while card open):
- [ ] `assistant:clarification` group renders `HumanInputCard` with question + options (or choiceWithOther / multiSelect)
- [ ] Bottom composer **disabled** while a human-input card is open (C6.7 blocked-state parity)
- [ ] Submitting the card sends a hidden (`hide_from_ui: true`) human message with the response payload
- [ ] After answering, the run resumes (new assistant group appears)
- [ ] The clarification run ended as `success` (not `interrupted`/error) — `interrupt` custom event → `ask_clarification` (`useThreadChat.ts`)
- [ ] `[console]` zero errors

### C6.14 SubtaskCard — subagent dispatch (ultra mode, parity ✓)

```
# Switch to ultra mode, send a task that spawns a subagent
bsk click @eN --session <id>     # mode selector → ultra
bsk snapshot --session <id>
bsk fill @eM --value 深度研究我的资产负债结构并给出三套优化方案 --session <id>
bsk click @eK --session <id>
bsk wait-ms 15s
bsk snapshot --session <id>
```

Assertions (DeerFlow parity: `task` tool → SubtaskCard, NOT inline steps):
- [ ] `subagent_enabled` true only in ultra mode (config.configurable)
- [ ] `task` tool call renders as `SubtaskCard` (collapsible, ClipboardListIcon, description shimmers while in_progress)
- [ ] Collapsed summary shows model label + token label + status icon + latest-tool-call flip display
- [ ] Expanded shows: prompt (streamdown) → display steps (reasoning interleaved with tool names) → completed/result or failed/error
- [ ] `custom` events `task_started/running/completed/failed/timed_out/cancelled` handled (`useThreadChat.ts`)
- [ ] `[console]` zero errors

### C6.15 Subtask step backfill on expand (parity ✓)

```
bsk snapshot --session <id>     # on a completed SubtaskCard
bsk click @eN --session <id>     # expand a subagent task card
bsk wait-ms 2s
bsk snapshot --session <id>
```

Assertions (DeerFlow parity: paginated backfill of `subagent.step` events):
- [ ] Expanding a completed subtask pages its step events until a short page
- [ ] No duplicate steps after backfill (identity dedup)
- [ ] `[console]` zero errors

---

## Section 3 — Output: token usage (4-preset system, parity ✓)

### C6.16 Token usage — 4 presets + inline modes

```
bsk navigate ${BASE}ai/chat --session <id> --wait-until networkidle
# after a completed run (C6.9), open the header token-usage popover
bsk snapshot --session <id>
bsk click @eN --session <id>     # CoinsIcon / token-usage header button
bsk snapshot --session <id>
```

Assertions (DeerFlow parity: off/summary/per_turn/debug; localStorage persistence):
- [ ] Header `TokenUsage.vue` popover shows input/output/total
- [ ] 4 presets as radio group: off / summary / per_turn / debug (`TokenUsage.vue:45,101-109,184-242`)
- [ ] Preset persists in localStorage (`numina:token-usage-preset`, default `per_turn`)
- [ ] `per_turn` inline mode renders `MessageTokenUsageList` per assistant turn
- [ ] `debug` inline mode renders step-attribution cards (thinking/final_answer/tool_batch/todo_update/subagent_dispatch + action kinds)
- [ ] Header + inline stay in sync (module-level singleton)
- [ ] `realtimeTokenUsage` computed via `accumulateUsage` over `chat.messages` per-message `usageMetadata`, with fallback to backend `/token-usage` API
- [ ] `[console]` zero errors

---

## Section 4 — Output: reports & artifacts

### C6.17 Artifacts panel — write_file / present_files (parity ✓)

```
# Run that produces an artifact (write_file or present_files)
bsk fill @eN --value 把分析结果写成文件 --session <id>
bsk click @eM --session <id>
bsk wait-ms 10s
bsk snapshot --session <id>
```

Assertions (DeerFlow parity):
- [ ] `write_file`/`str_replace` tool-call steps clickable → open `ArtifactPreviewPopup` at `write-file:{path}?message_id=…&tool_call_id=…`
- [ ] `assistant:present-files` group → `ArtifactFileList` cards (filename, type icon, extension, download link)
- [ ] Artifacts header button appears only when artifacts exist; opens side panel
- [ ] `[console]` zero errors

### C6.18 AI asset report — 3-step pipeline (separate surface, parity ✓)

> The structured AI report is a **separate surface** from chat (`AIReportPage` +
> `useReportStream` → `POST /api/v1/ai/report/generate/events`). There is **no
> direct chat↔report wiring** — the AI hub links to `/ai/report`. This matches
> the unified-dispatch refactor (asset-report is its own `stream_run` agent).

```
bsk navigate ${BASE}ai/report --session <id> --wait-until networkidle
bsk snapshot --session <id>
bsk click @eN --session <id>     # 开始分析 / regenerate (if cached, force)
bsk wait-ms 12s
bsk snapshot --session <id>
bsk screenshot --session <id> --out dogfood-output/c6.18-ai-report.png
```

Assertions:
- [ ] `ReportStepTimeline` renders 3 steps bound to `stream.step1Status/step2Status/step3Status` (`AIReportPage.vue:6-17`)
- [ ] Step transitions pending → running → finish (`step1Status==='finish' && ...` — `AIReportPage.vue:363`)
- [ ] Format detectors branch: `hasIndicatorsFormat` (L368) / `isNarrativeFormat` (L385) / `isLegacyFormat` (L374)
- [ ] On success: score ring + indicator/summary/narrative sections render
- [ ] Markdown fallback: `aiReport.viewMarkdownFallback` button (L30) + `aiReport.viewMarkdown` (L82) when step1 landed but step2/3 failed
- [ ] Cache-hit short-circuit: subsequent visits show cached report, no re-generate POST
- [ ] `[console]` zero errors

---

## Section 5 — History & threading

### C6.19 Chat history — list + infinite scroll + actions (parity ✓)

```
bsk navigate ${BASE}ai/chat/history --session <id> --wait-until networkidle
bsk snapshot --session <id>
```

Assertions (DeerFlow parity: cursor-paginated, date-groups, infinite scroll, swipe/long-press actions):
- [ ] `ChatHistoryPage` + `useThreadList`: paginated `POST /api/threads/search` (PAGE_SIZE 20)
- [ ] Date-groups: pinned / today / yesterday / earlier
- [ ] `IntersectionObserver` infinite scroll (1200ms throttle)
- [ ] Swipe-to-reveal + long-press actions; `<van-action-sheet>` (Vant 4 component API, NOT the removed `showActionSheet` function — the history-page-stuck fix)
- [ ] Actions: rename / pin / delete / export (markdown+json) / share
- [ ] Branch lineage badges + parent links (DeerFlow branch-from-turn parity)
- [ ] `[console]` zero errors

### C6.20 Title sync + orphan thread handling

```
# Open a thread, send a message, wait for title to sync
bsk navigate ${BASE}ai/chat?thread_id=<id> --session <id> --wait-until networkidle
bsk fill @eN --value 测试标题同步 --session <id>
bsk click @eM --session <id>
bsk wait-ms 18s                  # scheduleTitleRefresh polls at 3s/8s/15s
bsk snapshot --session <id>
# Orphan UUID thread
bsk navigate ${BASE}ai/chat?thread_id=<old-uuid> --session <id> --wait-until networkidle
bsk snapshot --session <id>
```

Assertions:
- [ ] Title syncs from checkpoint via `scheduleTitleRefresh` (polls `getThread`, skips `[SKILL:` wrapper titles — the title-middleware-sync fix)
- [ ] thread_id dual scheme (Snowflake vs UUID) handled opaquely
- [ ] Orphan UUID threads (pre-a97eb08c) return empty state, NOT 404 (backend `get_thread_state` fallback to `ai_chat_sessions` row — the thread-404-no-checkpoint fix)
- [ ] `[console]` zero errors

### C6.21 Branch from turn (parity ✓)

```
# From a completed assistant turn, trigger branch
bsk snapshot --session <id>
bsk click @eN --session <id>     # branch affordance on an assistant turn
bsk wait-ms 1s
bsk snapshot --session <id>
```

Assertions (DeerFlow parity: creates a new thread from a checkpoint):
- [ ] Branch-from-turn creates a new thread from the checkpoint and navigates to it
- [ ] Branch lineage visible in history (C6.19)
- [ ] `[console]` zero errors

### C6.22 Regenerate (parity ✓)

```
# Regenerate the latest assistant turn
bsk snapshot --session <id>
bsk click @eN --session <id>     # regenerate affordance (latest assistant group only)
bsk wait-ms 8s
bsk snapshot --session <id>
```

Assertions (DeerFlow parity: prepare-then-submit with checkpoint; superseded ids hidden until confirmed):
- [ ] Regenerate prepares then submits from checkpoint
- [ ] Superseded run/message ids hidden until confirmed
- [ ] No duplicate greeting / no stuck "发送中" (C6.9 regression set holds)
- [ ] `[console]` zero errors

---

## Section 6 — System integration

### C6.23 Auth + family context headers (parity ✓)

```
bsk navigate ${BASE}ai/chat --session <id> --wait-until networkidle
# inspect the fetch headers the chat sends
bsk evaluate --session <id> --expr "(async () => {
  // monkey-patch fetch to capture the next runs.stream call headers
  const orig = window.fetch;
  window.__capturedHeaders = null;
  window.fetch = function(url, opts) {
    if (typeof url === 'string' && url.includes('/runs/stream')) {
      window.__capturedHeaders = opts && opts.headers;
    }
    return orig.apply(this, arguments);
  };
  return 'patched';
})()"
# send a message to trigger the stream call
bsk fill @eN --value hi --session <id>
bsk click @eM --session <id>
bsk wait-ms 2s
bsk evaluate --session <id> --expr "JSON.stringify(window.__capturedHeaders)"
```

Assertions:
- [ ] Chat calls `client.runs.stream(threadId, 'agent', {streamMode:['messages-tuple','values','custom'], config.configurable, signal})` (LangGraph SDK)
- [ ] **Cookie-auth**: `credentials:'include'` (NO Bearer token) — mirrors `startAIStream`
- [ ] `X-Family-Id` header present (resolved `familyStore.family?.id || authStore.user?.family_id`)
- [ ] `X-User-Id` header present
- [ ] `agent_id` is NOT in the request body — carried via URL query + `agentStore`; backend dispatches by `'agent'` graph + `[SKILL:chat]` prompt wrapper
- [ ] `[console]` zero errors

### C6.24 Family race — no auto-send before family ready (regression ✓)

```
bsk navigate ${BASE}ai/chat?source=wish_detail&id=<id> --session <id> --wait-until networkidle
bsk snapshot --session <id>
```

Assertions (the submit-loses-input-family-race fix):
- [ ] On a `source=wish_detail` (or `liability_detail`) deep-link, the chat does NOT auto-send before `familyStore.fetchFamily()` resolves
- [ ] `await familyStore.fetchFamily()` guards the auto-send path
- [ ] `[console]` zero errors

### C6.25 Execution-mode flags in config.configurable (parity ✓)

> **Prerequisite:** reuses the C6.23 fetch monkey-patch (captured `window.__capturedHeaders`).
> Run C6.23 first to install the patch, then send one message per mode here —
> each `runs.stream` call's `config.configurable` is captured for inspection.

```
# Assumes C6.23 fetch patch is already installed on the session.
# For each mode in {flash, thinking, pro, ultra}: open mode selector, pick mode,
# send a short message, then read the captured config.
bsk navigate ${BASE}ai/chat --session <id> --wait-until networkidle
# (per mode) bsk click @eN  # mode selector → pick mode; fill + send; wait-ms 3s
bsk evaluate --session <id> --expr "JSON.stringify(window.__capturedHeaders)"
```

Assertions (DeerFlow parity — runtime context):
- [ ] `thinking_enabled = mode !== 'flash'`
- [ ] `is_plan_mode = mode in {pro, ultra}`
- [ ] `subagent_enabled = mode === 'ultra'`
- [ ] `reasoning_effort` passed (auto-set per mode — D4 divergence: not user-selectable)
- [ ] `websearch_enabled` passed (toggles chat-search auto-select — see C3.18)
- [ ] `thread_id` passed
- [ ] `[console]` zero errors

### C6.26 Error + retry + resume (parity ✓)

> **Prerequisite:** this case requires a **triggered stream error**, which cannot
> be produced by navigation alone. Two options: (a) use an invalid/misconfigured
> model so the LLM call 500s mid-stream; (b) disable network in DevTools
> mid-stream. Mark `Blocked (needs human verify)` if neither is available
> headlessly, then continue.

```
bsk navigate ${BASE}ai/chat --session <id> --wait-until networkidle
# Option (a): configure an invalid model via /settings/ai, send a message → stream error
# Option (b): send a message, then DevTools → Offline mid-stream
bsk snapshot --session <id>     # assert error UI + finalizeAllInProgress
# Then resume (network back / valid model):
bsk evaluate --session <id> --expr "(async()=>{ const r=await fetch('/api/threads/'+threadId+'/runs/resume',{method:'POST',credentials:'include'}); return String(r.status)})()"
```

Assertions:
- [ ] Stream `error` event → `finalizeAllInProgress` + throw + toast (string / Error.message / nested `.error.message`)
- [ ] 3-retry exponential backoff (1s/2s/4s jittered), 120s timeout (`useThreadChat.ts`)
- [ ] Resume endpoint `POST /api/threads/{id}/runs/resume` parsed as raw SSE (TextDecoder + event:/data: parsing)
- [ ] Idempotent `input:null` resume keyed on `userMsg.id`
- [ ] Cancel swallows "not cancellable" 409; "not active on this worker" 409 clears reconnect key
- [ ] `[console]` zero errors

### C6.27 Agent popup Teleport + copy button fallback (regression ✓)

```
# Trigger the agent popup (e.g. click an agent badge / consult 数鸣)
bsk snapshot --session <id>
bsk click @eN --session <id>
bsk wait-ms 500
bsk snapshot --session <id>
# Copy an assistant message on a non-secure context (LAN-IP HTTP)
bsk click @eM --session <id>     # copy button
```

Assertions:
- [ ] Agent popup uses `Teleport to body` (escapes `backdrop-filter` stacking context — the agent-popup-teleport fix, `InputBox.vue:610` and `:776` for the agent-info popup)
- [ ] Copy button works on non-secure HTTP context (LAN-IP) via `execCommand` fallback (the copy-button-non-secure-context fix, `tableUtils.ts:123`)
- [ ] `[console]` zero errors

---

## Parity summary matrix

| DeerFlow contract | Numina | Case | Notes |
|---|---|---|---|
| 4 mode presets + auto-downgrade | ✓ | C6.1 | `reasoning_effort` auto per mode |
| Model selector + capability tags | ✓ | C6.2 | |
| Attachments + upload-limit validation | ✓ | C6.3 | verify toast strings |
| Voice input (SpeechRecognition) | ✓ | C6.4 | feature-detect fallback |
| Slash-skill autocomplete | ✓ | C6.5 | builtins `/goal`+`/compact` now ported (D1/D2 ✅) |
| Input-polish button | ✅ D3 (done) | C6.6 | implemented 2026-07-21 |
| `/goal` + GoalStatus bar | ✅ D1 (done) | C6.5 | implemented 2026-07-21 — goal endpoints + worker 续跑循环 + GoalStatusBar |
| `/compact` | ✅ D2 (done) | C6.5 | implemented 2026-07-21 — compact endpoint + transient bridge |
| User-selectable reasoning_effort | ◐ D4 (by design) | C6.1 | 设计如此 — auto per mode, intentional |
| Submit blocked states | ✓ | C6.7 | |
| Suggestion chips | ✓ | C6.8 | |
| 6 message group types | ✓ | C6.10 | |
| Markdown tables (v-html survival) | ✓ | C6.11 | |
| ChainOfThought single renderer | ✓ | C6.12 | |
| HumanInputCard clarification | ✓ | C6.13 | ends as success |
| SubtaskCard subagent | ✓ | C6.14 | ultra only |
| Subtask step backfill | ✓ | C6.15 | |
| Token-usage 4 presets | ✓ | C6.16 | |
| Artifacts panel | ✓ | C6.17 | |
| 3-step AI report (separate) | ✓ | C6.18 | no chat↔report wiring |
| History infinite scroll + actions | ✓ | C6.19 | Vant4 action-sheet |
| Title sync + orphan threads | ✓ | C6.20 | |
| Branch from turn | ✓ | C6.21 | |
| Regenerate | ✓ | C6.22 | |
| Cookie-auth + X-Family-Id/X-User-Id | ✓ | C6.23 | no Bearer |
| Family race guard | ✓ | C6.24 | |
| Execution-mode flags | ✓ | C6.25 | |
| Error/retry/resume | ✓ | C6.26 | |
| Agent popup Teleport + copy fallback | ✓ | C6.27 | |
| TodoList bar above composer | ✅ D5 (done) | C6.5 | implemented 2026-07-21 — TodoListBar + useThreadTodos + TodoMiddleware (plan_mode gate) |
| Scheduled Tasks subsystem | ⊘ D6 (独立提案) | — (feature proposal) | 功能级缺口, 非 chat parity bug; 待产品评估后独立提案 (DeerFlow 完整子系统) |
| Thread Channel Source | ⊘ D7 (设计不引入) | — (by design) | DeerFlow 特有 IM-bridge 衍生; numina 无 IM 桥接, 不引入 |
