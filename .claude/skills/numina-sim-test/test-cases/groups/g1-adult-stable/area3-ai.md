# Area 3 — AI capabilities (PDF识别 / AI资产报告 / 数鸣智能体 / AI对话)

Shared conventions in [`_common.md`](../../_common.md).

Covers the `two-ai-apps-unified-dispatch` refactor: three `stream_run` AI
apps (数鸣 numina / asset-report / import-parse) + chat/chat-search auto-select.
All verified landed in `server/apps/agent/skills/builtin/public/`.

> **AI prerequisite:** AI must be enabled for the family. If `aiStore.aiEnabled`
> is false, AIHubPage shows the disabled card with a CTA to `/settings/ai`.
> Configure a provider at `/settings/ai/provider/new` before these cases.
> For vision cases (C3.8 scanned PDF), the configured model must have
> `supports_vision=True`.

> **Auth:** establish the adult session as `demouser` / `DemoPass123` via the
> cookie+localStorage injection fallback (SKILL.md "Phase 2 fallback") — the
> default `bsk fill` form-login can trigger a password-manager extension that
> hijacks the tab. AI cases assume this adult session is already established.

## Existing cases — core AI flows

### C3.1 AI Hub (AIHubPage) — report card + 数鸣 + agents + entry

```
bsk navigate ${BASE}ai --session <id> --wait-until networkidle
bsk snapshot --session <id>
```

Assertions:
- [ ] Health score ring renders (displayScore + scoreArc)
- [ ] Stats row: suggestions count, alerts count, data completeness %
- [ ] If report exists: report-summary-card renders summary + "查看完整报告" → `/ai/report`
- [ ] If no report + AI enabled: report-empty-card with "生成第一份报告" CTA
- [ ] If AI disabled: ai-disabled-card with CTA → `/settings/ai`
- [ ] NuminaAgentCard (数鸣 featured card) renders, emits `@consult`
- [ ] 我的智能体 section (collapsible) lists enabled custom agents
- [ ] 分析应用 section lists Time Machine → `/ai/time-machine`
- [ ] Chat input box (InputBox component) at bottom with mode selector (flash/thinking/pro/ultra)
- [ ] `[console]` zero errors

### C3.2 AI chat (AIChatPage) — send message + stream response

```
bsk navigate ${BASE}ai/chat --session <id> --wait-until networkidle
bsk snapshot --session <id>
# fill chat input, send
bsk fill @eN --value 帮我分析一下我的资产情况 --session <id>
bsk click @eM --session <id>   # send button
bsk wait-ms 5s
bsk snapshot --session <id>
```

Assertions:
- [ ] AIChatBox renders with message list + input
- [ ] User message bubble appears after send
- [ ] AI response streams in (SSE) — assistant message appears within timeout
- [ ] No blank/empty AI response (blank-response fix: empty/thinking-only content detection)
- [ ] No duplicate greeting on retry (hasPriorProgress anchored on userMsg.id)
- [ ] "发送中" state clears after stream completes (error-cleanup fix)
- [ ] `[console]` zero errors

### C3.3 AI chat — agent consult (数鸣智能体 / custom agent)

```
# From AIHubPage, click 数鸣 (NuminaAgentCard) or a custom AgentCard
bsk navigate ${BASE}ai --session <id> --wait-until networkidle
bsk snapshot --session <id>
bsk click @eN --session <id>   # consult button
# → navigates to /ai/chat?agentId=<id>
bsk wait-ms 3s
bsk snapshot --session <id>
```

Assertions:
- [ ] Navigates to `/ai/chat?agentId=<id>` (or with `thread_id` if cached session exists)
- [ ] Chat page loads with the selected agent context
- [ ] **数鸣智能体自动发送预设问题**：进入聊天后，数鸣智能体自动发送一条预设问题（如"帮我看看家庭财务近况，我想快速了解有没有需要关注的变化"）
- [ ] **预设问题内容质量**：预设问题包含一句话概括 + 值得关注的发现 + 具体可操作建议（精确到金额或账户）
- [ ] Sending a message routes through that agent's system_ids + bootstrap
- [ ] If agent has a cached session, `thread_id` is passed in query
- [ ] `[console]` zero errors

### C3.4 AI asset report (AIReportPage) — 3-step generation

```
bsk navigate ${BASE}ai/report --session <id> --wait-until networkidle
bsk snapshot --session <id>
```

If no report: click "开始分析" button.
```
bsk click @eN --session <id>   # start button
bsk wait-ms 10s                # generation is long; poll instead if preferred
bsk snapshot --session <id>
```

Assertions:
- [ ] ReportStepTimeline renders 3 steps (step1 thinking → step2 JSON → step3)
- [ ] Step statuses transition: pending → running → done
- [ ] Tool calls + tool results display in timeline
- [ ] On success: overall score circle + summary render
- [ ] On failure: failed-placeholder shows error + retry button
- [ ] Elastic fallback: if step1 markdown landed but step2/3 failed, "查看 Markdown" button available
- [ ] Cached report: subsequent visits show cached badge, no re-generation
- [ ] `[console]` zero errors

### C3.5 PDF import / parse (ImportReportPage) — upload → preview → confirm

```
bsk navigate ${BASE}finance/import --session <id> --wait-until networkidle
bsk snapshot --session <id>
```

**File upload** (bsk cannot trigger `<input type=file>` directly via click; use
`bsk fill` on the hidden input, or `bsk evaluate` to set files — see
[`_common.md`](../../_common.md) "File upload note"):
```
# Locate the hidden file input via get-html or evaluate, then set its files
bsk evaluate --session <id> --expr "<set input.files via DataTransfer>"
```

Assertions:
- [ ] Upload section shows van-uploader (accept=application/pdf, max 25MB)
- [ ] After upload: parsing section shows van-loading
- [ ] After parse: preview section shows source + report_date + item list
- [ ] Each preview item: editable name + current_value + action tag (update/create)
- [ ] Matched asset name shown when item matches existing asset
- [ ] Warning text shown for ambiguous items
- [ ] Oversized file (>25MB) → "文件过大" toast
- [ ] Confirm button → POSTs batch → returns to asset list with updated/created assets
- [ ] `[console]` zero errors

### C3.6 AI time machine (AITimeMachinePage)

```
bsk navigate ${BASE}ai/time-machine --session <id> --wait-until networkidle
bsk snapshot --session <id>
```

Assertions:
- [ ] Time machine UI renders
- [ ] Date/period selector present
- [ ] Projection renders without error
- [ ] `[console]` zero errors

### C3.7 AI settings — provider config (AIConfigPage)

```
bsk navigate ${BASE}settings/ai --session <id> --wait-until networkidle
bsk snapshot --session <id>
```

Assertions:
- [ ] Provider list renders (empty state if none configured)
- [ ] "添加供应商" → `/settings/ai/provider/new`
- [ ] MCP / web-search / skills / agents management entries present
- [ ] AI enabled toggle reflects family AI state
- [ ] `[console]` zero errors

---

## New cases — asset-report single-agent 3-step pipeline

Covers the unified-dispatch refactor: asset-report is now a single `stream_run`
agent run (not backend cross-HTTP orchestration). Steps: (1) family-data MCP
取数 + write_file markdown audit → (2) read_file 读回 + 输出 indicators JSON
→ (3) worker json-repair 落库. Skill: `asset-report/SKILL.md`.

### C3.8 Asset report — single-run pipeline + WRITE_FILE declaration

```
# Trigger a fresh report (force regenerate if cached)
bsk navigate ${BASE}ai/report --session <id> --wait-until networkidle
bsk snapshot --session <id>
bsk click @eN --session <id>     # 开始分析 / regenerate
bsk wait-ms 12s                  # 3-step pipeline; poll if needed
bsk snapshot --session <id>
bsk screenshot --session <id> --out dogfood-output/c3.8-asset-report-run.png
```

Assertions:
- [ ] All 3 steps complete within a single agent run (step1 → step2 → step3 transition without backend re-dispatch)
- [ ] Step1 calls family-data MCP tools (get_family_overview etc.) — visible in tool-call timeline
- [ ] Step1 writes markdown via `write_file` and declares `WRITE_FILE: <filename>` in the response text (required because `write_file` returns only `"OK"`)
- [ ] Step2 `read_file` reads the declared filename back (verifies sandbox landing)
- [ ] Step3 outputs valid indicators JSON (no trailing comma, no markdown tables in `narrative` — list format only)
- [ ] On success: overall score circle + summary render from the JSON
- [ ] `[console]` zero errors

### C3.9 Asset report — elastic markdown fallback

```
# If step2/3 fail (simulate by using a weak/non-vision model or interrupting):
# visit /ai/report after a partial run
bsk navigate ${BASE}ai/report --session <id> --wait-until networkidle
bsk snapshot --session <id>
```

Assertions:
- [ ] If step1 markdown landed but step2/3 failed: "查看 Markdown" button available (elastic fallback)
- [ ] Clicking it opens/links to the landed markdown report (the `WRITE_FILE`-declared filename)
- [ ] Failed-placeholder shows error + retry button alongside the markdown fallback
- [ ] `[console]` zero errors

### C3.10 Asset report — cache + entity-change invalidation

```
# After a successful report (C3.8), revisit /ai/report
bsk navigate ${BASE}ai/report --session <id> --wait-until networkidle
bsk snapshot --session <id>
# Then mutate an asset and revisit
bsk navigate ${BASE}assets/new --session <id> --wait-until networkidle
# ... create asset ...
bsk navigate ${BASE}ai/report --session <id> --wait-until networkidle
bsk snapshot --session <id>
```

Assertions:
- [ ] Cached report: second visit shows cached badge, no re-generation POST
- [ ] After an asset/liability write, the report cache is invalidated (Plan A entity-change invalidation; capability-cache on `ai_reports`)
- [ ] Revisiting after mutation prompts regeneration (or shows stale-then-regenerate)
- [ ] `[console]` zero errors

---

## New cases — import-parse multimodal + MCP batch write

Covers import-parse as the 3rd `stream_run` agent: file → assets/liabilities/
credit-cards structured parse. Multimodal: scanned PDF → page images + `view_image`
+ vision LLM. MCP batch write: `import_assets_batch` (when `confirm_items`
passed). Skill: `import-parse/SKILL.md`.

### C3.11 PDF import — digital PDF (text-extractable)

```
# Upload a digital PDF via the ImportReportPage (C3.5 upload flow)
bsk navigate ${BASE}finance/import --session <id> --wait-until networkidle
# ... set input.files to a digital PDF fixture ...
bsk wait-ms 8s
bsk snapshot --session <id>
bsk screenshot --session <id> --out dogfood-output/c3.11-pdf-digital.png
```

Assertions:
- [ ] Parse completes; preview shows source + report_date + parsed item list
- [ ] Each item has editable name + current_value + action tag (update/create)
- [ ] Matched existing assets show the matched name
- [ ] Ambiguous items show warning text
- [ ] `[console]` zero errors

### C3.12 PDF import — scanned PDF (vision pipeline)

```
# Upload a scanned/image-only PDF (vision pipeline)
# ... set input.files to a scanned PDF fixture ...
bsk wait-ms 12s                  # vision is slower; poll
bsk snapshot --session <id>
bsk screenshot --session <id> --out dogfood-output/c3.12-pdf-scanned.png
```

Prerequisite: the family's configured model has `supports_vision=True`
(else `view_image` is not registered and scanned PDFs cannot be parsed).

Assertions:
- [ ] The agent converts PDF pages to images and calls `view_image` (visible in tool-call timeline)
- [ ] `supports_vision` injection active — `view_image` tool appears (only for vision models)
- [ ] Sparse detection: pages with no relevant data are skipped without error
- [ ] 10-page cap: PDFs >10 pages do not hang (cap enforced, remaining pages skipped with a note)
- [ ] Parsed items appear in preview (same shape as C3.11)
- [ ] `[console]` zero errors

### C3.13 PDF import — confirm batch write via MCP

```
# After preview (C3.11/C3.12), click confirm
bsk snapshot --session <id>
bsk click @eN --session <id>     # confirm button
bsk wait-ms 3s
bsk snapshot --session <id>
```

Assertions:
- [ ] Confirm calls the import-parse agent with `confirm_items` → agent invokes `import_assets_batch` MCP tool (single batch write)
- [ ] After confirm, navigates to asset list with updated/created assets visible
- [ ] Partial-failure: if some items fail, the successful ones still land (batch partial-failure handling)
- [ ] `[console]` zero errors

---

## New cases — 数鸣 SOUL 3 analysis directions

Covers the unified-dispatch refactor: 4 `family-*` skills merged into 数鸣 SOUL
(`chat/SKILL.md`), which now provides 3 core analysis directions: (1) 资产负债分析,
(2) 优化现金流, (3) 挖掘投资机会. Triggered via natural conversation in `/ai/chat`.

### C3.14 数鸣 — 资产负债分析 direction

```
bsk navigate ${BASE}ai/chat --session <id> --wait-until networkidle
bsk fill @eN --value 分析一下我的资产负债健康度 --session <id>
bsk click @eM --session <id>
bsk wait-ms 8s
bsk snapshot --session <id>
```

Assertions:
- [ ] AI response addresses 资产负债分析: net-worth health, allocation structure/concentration, liability pressure & term structure, asset-liability matching
- [ ] Response is substantive (not blank/thinking-only — blank-response fix holds)
- [ ] No structured-card regression: the old family-asset-checkup persistent card no longer exists (KTD-9 deleted); analysis is free-text/JSON in chat
- [ ] `[console]` zero errors

### C3.15 数鸣 — 优化现金流 direction

```
bsk fill @eN --value 帮我看看哪里能优化现金流 --session <id>
bsk click @eM --session <id>
bsk wait-ms 8s
bsk snapshot --session <id>
```

Assertions:
- [ ] AI response addresses 优化现金流: idle/low-efficiency asset holding costs, consumption leaks, releasable occupied funds, 节流/盘活 ideas
- [ ] Integrates the old "闲置清仓"/"资金泄漏" perspectives (now in SOUL, not separate skills)
- [ ] `[console]` zero errors

### C3.16 数鸣 — 挖掘投资机会 direction

```
bsk fill @eN --value 有没有可以再配置的资金方向 --session <id>
bsk click @eM --session <id>
bsk wait-ms 8s
bsk snapshot --session <id>
```

Assertions:
- [ ] AI response addresses 挖掘投资机会: structural idle funds / allocation gaps, reconfiguration directions
- [ ] Includes the disclaimer (信息整理, 不构成投资建议) per SOUL boundary
- [ ] `[console]` zero errors

---

## New cases — chat modes + chat-search auto-select

Covers the 4 chat presets (flash/thinking/pro/ultra) with auto-downgrade when
the model lacks `supports_thinking`, and chat-search auto-selection based on
`websearch_enabled` + `has_search_capability`.

### C3.17 Chat — four-mode selector + auto-downgrade

```
bsk navigate ${BASE}ai/chat --session <id> --wait-until networkidle
bsk snapshot --session <id>
# Cycle the mode selector
bsk click @eN --session <id>     # open mode selector
bsk snapshot --session <id>
```

Assertions:
- [ ] Mode selector shows available presets: flash / thinking / pro / ultra (those supported by the configured model)
- [ ] Selecting `thinking`/`pro`/`ultra` on a model with `supports_thinking=False` auto-downgrades to `flash` (InputBox auto-downgrade logic)
- [ ] Selected mode persists (`getLastSelectedMode`) across navigation/reload
- [ ] Sending a message in each mode produces a streamed response (no mode-specific blank/stuck)
- [ ] `[console]` zero errors

### C3.18 Chat-search — web search auto-select

```
# Enable web search on the chat input (toggle/setting), then send a query needing fresh info
bsk navigate ${BASE}ai/chat --session <id> --wait-until networkidle
bsk snapshot --session <id>
# toggle websearch_enabled on (via the input affordance)
bsk fill @eN --value 查一下最新的 LPR 利率 --session <id>
bsk click @eM --session <id>
bsk wait-ms 10s
bsk snapshot --session <id>
```

Prerequisite: a web-search capability is configured (`has_search_capability`
true), else chat-search is not selected and search is skipped.

Assertions:
- [ ] With `websearch_enabled=True` + search capability configured: worker auto-selects `chat-search` skill (not `chat`)
- [ ] Tool-call timeline shows `web_search`/`web_fetch` invocations
- [ ] AI response cites/uses the fetched web content
- [ ] With `websearch_enabled=False`: worker selects `chat` skill; no web_search calls (数鸣 SOUL "不要尝试联网搜索" boundary)
- [ ] `[console]` zero errors

### C3.19 Chat — retry does not duplicate greeting

```
# Send a message, then retry it
bsk fill @eN --value 你好 --session <id>
bsk click @eM --session <id>
bsk wait-ms 3s
bsk snapshot --session <id>
# click retry on the user message
bsk click @eR --session <id>     # retry affordance
bsk wait-ms 3s
bsk snapshot --session <id>
```

Assertions:
- [ ] Retry does NOT produce a duplicate greeting (hasPriorProgress anchored on userMsg.id, not phase)
- [ ] The retried response replaces/appends cleanly without "发送中" stuck state (error-cleanup fix)
- [ ] `[console]` zero errors

### C3.20 Chat — agent consult thread context

```
# From AIHubPage consult 数鸣 (C3.3), then send a follow-up
bsk navigate ${BASE}ai/chat?agentId=<numina-agent-id> --session <id> --wait-until networkidle
bsk fill @eN --value 接着上次的思路 --session <id>
bsk click @eM --session <id>
bsk wait-ms 6s
bsk snapshot --session <id>
```

Assertions:
- [ ] If a cached thread exists for the agent, `thread_id` is in the query and the conversation resumes context
- [ ] The follow-up message routes through the agent's system_ids (数鸣 SOUL, not a generic chat)
- [ ] No blank response on context-resume
- [ ] `[console]` zero errors

---

## New cases — 响应质量 + 性能基准 + 数据准确性

Covers the quality dimensions validated in manual testing 2026-07-25: response
quality (data accuracy, analysis depth, actionable suggestions, friendly tone),
performance baseline (response time for simple/medium/complex questions), and
data consistency (AI response vs API return values).

### C3.21 数鸣响应质量验证

```
bsk navigate ${BASE}ai/chat --session <id> --wait-until networkidle
bsk fill @eN --value 请帮我分析一下我们家庭目前的资产配置情况，有什么优化建议吗？ --session <id>
bsk click @eM --session <id>
bsk wait-ms 30s                  # 复杂分析需要较长时间
bsk snapshot --session <id>
bsk screenshot --session <id> --out dogfood-output/c3.21-response-quality.png
```

Assertions:
- [ ] **数据准确性**：响应中引用的总资产、总负债、净资产数值与 `/dashboard/overview` API 返回一致（误差 < 1%）
- [ ] **分析深度**：响应包含多维度分析（至少 3 个维度，如资产结构、负债管理、流动性、风险保障等）
- [ ] **建议可操作性**：优化建议具体到金额或账户（如"建议预留 ¥15-20 万应急金"，而非"建议增加现金储备"）
- [ ] **语气友好度**：语气温暖亲切，使用 emoji 增强可读性（如"🏠 家庭财务全景"、"💡 优化建议"）
- [ ] **格式美观**：使用表格展示数据（如资产配置表、负债结构表），使用图表可视化（如饼图展示资产分布）
- [ ] **异常识别**：如果系统中有测试数据（如 C1 开头的测试资产），响应中提醒清理
- [ ] **后续引导**：响应末尾提供 2-3 个后续问题建议（如"如何快速更新负债余额？"）
- [ ] `[console]` zero errors

### C3.22 AI 响应性能基准

```
# 简单问题
bsk navigate ${BASE}ai/chat --session <id> --wait-until networkidle
bsk fill @eN --value 你好 --session <id>
bsk click @eM --session <id>
# 记录开始时间，轮询直到响应完成
bsk wait-ms 5s
bsk snapshot --session <id>
# 记录简单问题响应时间

# 中等问题
bsk fill @eN --value 分析我的资产配置 --session <id>
bsk click @eM --session <id>
bsk wait-ms 15s
bsk snapshot --session <id>
# 记录中等问题响应时间

# 复杂问题
bsk fill @eN --value 深度研究我的资产负债结构并给出三套优化方案 --session <id>
bsk click @eM --session <id>
bsk wait-ms 30s
bsk snapshot --session <id>
# 记录复杂问题响应时间
```

Assertions:
- [ ] **简单问题**（如"你好"）响应时间 < 5s
- [ ] **中等问题**（如"分析资产配置"）响应时间 < 30s
- [ ] **复杂问题**（如"深度研究+三套方案"）响应时间 < 60s
- [ ] 响应时间超过 60s 时，显示"生成中"进度提示（非卡死状态）
- [ ] 每个响应阶段（简单/中等/复杂）的 Token 消耗在合理范围内（简单 < 5K，中等 5K-15K，复杂 15K-30K）
- [ ] `[console]` zero errors

### C3.23 AI 响应数据准确性

```
bsk navigate ${BASE}ai/chat --session <id> --wait-until networkidle
bsk fill @eN --value 我的总资产和净资产是多少 --session <id>
bsk click @eM --session <id>
bsk wait-ms 8s
bsk snapshot --session <id>
# 同时调用 API 获取真实数据
# API_RESPONSE=$(curl -s -H "$AUTH" "$API_BASE/dashboard/overview")
# API_TOTAL_ASSETS=$(echo "$API_RESPONSE" | jq -r '.data.total_assets')
# API_NET_WORTH=$(echo "$API_RESPONSE" | jq -r '.data.net_worth')
# 对比 AI 响应中的数值与 API 返回
```

Assertions:
- [ ] AI 响应中的**总资产**数值与 `/dashboard/overview` API 返回的 `total_assets` 一致（误差 < 1%）
- [ ] AI 响应中的**净资产**数值与 `/dashboard/overview` API 返回的 `net_worth` 一致（误差 < 1%）
- [ ] AI 响应中的**总负债**数值与 `/dashboard/overview` API 返回的 `total_liabilities` 一致（误差 < 1%）
- [ ] AI 响应中引用的具体资产/负债名称与系统数据一致（无幻觉，如不会编造不存在的资产）
- [ ] 如果用户询问具体资产详情（如"茅台股票多少钱"），AI 响应与 `/assets/:id` API 返回一致
- [ ] `[console]` zero errors
