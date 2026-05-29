---
title: DeerFlow Chat UX Fusion
type: feat
status: active
date: 2026-05-27
origin: docs/brainstorms/2026-05-27-deerflow-chat-ux-fusion-requirements.md
---

# feat: DeerFlow Chat UX Fusion — AI 回答过程可视化升级

## Summary

将 DeerFlow 原生问答 UI 的过程可视化模式融合到 Numina 的 AI 交互中：后端补发 tool.call/tool.result 事件以支持差异化工具展示；前端用 Shimmer 动画+自动折叠替代当前思考展示，用 ChainOfThought 竖线连接步骤替代统一 processSteps 列表，将 deep_think 布尔开关扩展为 2 档+子选项输入模式，用弹跳三点替代闪烁光标，回答后显示模板化插值建议药丸。

---

## Problem Frame

AI 在调用业务工具时用户只能看到统一的 processSteps 列表，无法直观区分 AI 在做什么。后端虽定义了 tool.call/tool.result 事件但未发射，前端因此无法做差异化展示。需求文档详见 origin。

---

## Requirements

- R1. 思考阶段标签显示 Shimmer 渐变扫光动画，替代脉冲圆点+计时器
- R2. 思考结束后标签显示"思考了 X 秒"，1 秒后自动折叠；折叠仅触发一次
- R3. 思考内容区域支持 Collapsible 展开/折叠，有 fade + slide 动画
- R4. 每类业务工具在调用时显示独特图标和摘要描述（资产查询/报告生成/心惑分析/趋势计算）
- R5. 连续工具调用步骤用竖线连接，步骤有状态样式（完成=暗淡、进行中=高亮、待定=半透明）
- R6. 输入区提供 2 档模式（普通/智能），替代 deep_think 布尔开关
- R6b. 智能模式提供子选项（轻量/完整）控制工具调用深度
- R7. 流式输出期间底部显示弹跳三点动画，替代闪烁光标
- R8. 回答完成后显示 3-5 个模板化插值建议药丸，用户点击可追问

**Origin actors:** A1 (家庭用户), A2 (AI Agent)
**Origin flows:** F1 (工具调用场景问答), F2 (简单聊天)
**Origin acceptance examples:** AE1 (covers R1-R3), AE2 (covers R4-R5), AE3 (covers R6-R6b), AE4 (covers R7-R8)

**Origin flow coverage note:** Origin F2 (简单聊天) lists R5 (竖线连接) in its coverage, but simple chat has no tool calls so R5 applies vacuously. F2 is effectively covered by R1 (Shimmer 替代连接动画) and R7 (弹跳三点).

---

## Scope Boundaries

- Artifact 文件预览面板——家庭场景不生成代码文件
- Token 用量/上下文进度环形指示器——技术指标对家庭用户无意义
- 消息分支导航（1 of N）——家庭场景过于复杂
- 模型选择器——模型由服务端配置
- SubtaskCard 子任务卡片——v1 聚焦单步工具调用可视化
- web_search 独立开关——智能模式下由 agent 自行决定是否搜索，前端不再暴露独立开关

### Deferred to Follow-Up Work

- 后端 API 动态生成建议标签（v1 用模板化插值，后续接 LLM 生成 API）
- SubtaskCard 多子任务编排展示（需后端 subagent 事件支持）
- Legacy orchestrator 路径的 tool.call/tool.result 事件发射（v1 仅 agent-first 路径支持）
- web_search 作为独立用户可控开关的恢复（需评估使用频率后决定）

---

## Context & Research

### Relevant Code and Patterns

- `frontend/apps/main/src/pages/AIChatPage.vue` — 主聊天页，2780 行，phase 状态机 + AiProcessBlock + 流式渲染
- `frontend/apps/main/src/components/ai/AiProcessBlock.vue` — 过程展示组件，渲染 processSteps[]
- `frontend/apps/main/src/components/common/AIChatInput.vue` — 输入组件，deep_think/web_search v-model 布尔切换
- `frontend/apps/main/src/utils/aiEventNormalizer.ts` — 事件归一化，支持 tool.call/tool.result 解析但后端未发射
- `frontend/apps/main/src/composables/useAgentEventStream.ts` — NDJSON 行解析器
- `frontend/apps/main/src/types/agent-stream.ts` — ProcessStep 联合类型（reasoning/tool_call/subagent/artifact/progress）
- `server/apps/agent/services/stream_events.py` — EventStreamBuilder，已定义 tool_call()/tool_result() 方法但未被调用
- `server/apps/agent/services/agent_dispatch.py` — agent-first 执行路径，只发 phase + token 事件
- `server/apps/agent/services/orchestrator.py` — legacy 路径，`_chunk_to_event_lines()` 只发 phase + token
- `frontend/apps/main/src/components/ai/AiToolCallStep.vue` — 工具调用步骤组件（现有，统一样式）

### Institutional Learnings

- **NDJSON 双路径合约**（`docs/solutions/integration-issues/deerflow-adapter-stream-type-mismatch-and-security-issues-2026-05-16.md`）：raw-text 路径 yield str，NDJSON 路径 yield StreamChunk。新功能必须用 NDJSON 路径。
- **DeerFlow 静默降级**（`docs/solutions/integration-issues/deerflow-harness-silent-fallback-and-concurrency-fixes-2026-04-12.md`）：广泛 except 可吞掉 ImportError 导致功能静默失效。验证 DeerFlow 实际激活。
- **MCP Chat Adapter**（`docs/solutions/architecture-patterns/mcp-chat-adapter-architecture-2026-05-21.md`）：Chat 是固定 capability，有自己的 ChatAdapter。SSE 单例模式。
- **前端交互约束**（frontend CLAUDE.md）："Only display what DeerFlow/backend explicitly returns for UI use. No speculative visualization."

### External References

- DeerFlow 原生 `reasoning.tsx` — Shimmer + Collapsible + 自动折叠实现参考
- DeerFlow 原生 `chain-of-thought.tsx` — 竖线连接 + 状态样式实现参考
- DeerFlow 原生 `shimmer.tsx` — CSS 渐变背景扫光动画（backgroundPosition 动画，2s 循环）
- DeerFlow 原生 `streaming-indicator.tsx` — 三圆点弹跳动画（0.2s 间隔）

---

## Key Technical Decisions

- **后端先补发 phase.thinking + tool.call/tool.result 事件**：agent_dispatch.py 当前只发 phase.answering 和 token 事件，既缺失 phase.thinking（U3 Shimmer 的触发条件），也缺失 tool 事件。重构 astream 迭代为消息类型分发是 U1 的核心变更。
- **2 档+子选项映射到后端参数**：普通→`deep_think=false`；智能-轻量→`deep_think=true, reasoning_effort=low`；智能-完整→`deep_think=true, reasoning_effort=high`。后端新增 `reasoning_effort` 参数（枚举：low/medium/high），默认 medium。需透传 agent_stream.py 中间层。实现前先验证 reasoning_effort 对 DeerFlow agent 的实际行为影响。
- **Shimmer 用纯 CSS 实现**：DeerFlow 用 Framer Motion，Numina 用 Vue 3 + Vant。用 CSS `@keyframes` + `background-image` 渐变实现相同效果，无需引入动画库。prefers-reduced-motion: reduce 下降级为静态文字。
- **ChainOfThought 在 AiProcessBlock 内重构**：不是新建组件替换，而是在现有 AiProcessBlock 内重构渲染逻辑。AiThinkingLabel 替代原 process-header 中的思考状态显示。
- **后端为 tool_type/display_name/icon 的 source of truth**：事件携带完整信息，前端 toolTypeRegistry 仅维护 summaryTemplate，不重复映射。
- **建议标签（非药丸）**：border-radius: 4px，符合设计系统规范。DeerFlow 用 rounded pills 但 Numina 设计系统禁止 pill-shaped 元素。
- **web_search 处置**：前端移除独立 web_search 开关，智能模式下由 agent 自行决定是否搜索。

---

## Open Questions

### Resolved During Planning

- 输入模式设计：2 档+子选项（普通/智能，智能含轻量/完整），替代原始 3 档设计
- 建议药丸 v1 实现：模板化插值而非硬编码
- 模式锁定规则：2 档模式切换开启新对话，智能模式子选项可在对话内切换

### Deferred to Implementation

- 工具类型图标映射的完整业务注册表：v1 先覆盖 4 类核心工具（资产/报告/心惑/趋势），后续扩展
- `reasoning_effort` 参数对 DeerFlow agent 行为的实际影响：需在实现时测试 low vs high 的工具调用行为差异

---

## High-Level Technical Design

> *This illustrates the intended approach and is directional guidance for review, not implementation specification. The implementing agent should treat it as context, not code to reproduce.*

### 事件流架构

```
用户提问 (mode: normal|smart-light|smart-full)
    │
    ▼
后端 agent_dispatch.py
    ├─ 解析 mode → deep_think + reasoning_effort 参数
    ├─ make_lead_agent(runnable_config)
    ├─ astream(state) ──► AIMessage chunks
    │   ├─ 检测 tool_calls → 发射 tool.call 事件
    │   ├─ 检测 tool results → 发射 tool.result 事件
    │   ├─ thinking tokens → 发射 token.stream(is_thinking=true)
    │   └─ answer tokens → 发射 token.stream(is_thinking=false)
    └─ 发射 phase.connecting → phase.thinking → phase.answering → capability.end
    │
    ▼
前端 NDJSON 解析 → aiEventNormalizer
    ├─ tool.call → ProcessStep(type=tool_call, toolName, displayName, icon)
    ├─ tool.result → 更新 ProcessStep 状态
    ├─ token.stream(is_thinking) → 推理/回答内容
    └─ phase events → 驱动 UI 状态机
    │
    ▼
AiProcessBlock 重构渲染
    ├─ Shimmer 思考标签 + 自动折叠
    ├─ ChainOfThought 竖线连接步骤
    │   ├─ 工具图标 + 摘要（按类型差异化）
    │   └─ 状态样式（complete/active/pending）
    └─ 弹跳三点流式指示器
    │
    ▼
回答完成 → 模板化建议药丸
```

---

## Implementation Units

### U1. 后端补发 tool.call/tool.result 事件

**Goal:** 让 agent_dispatch.py 的 agent-first 路径在流式输出中发射结构化工具调用事件和 phase.thinking 事件，使前端能区分不同工具类型并触发思考动画。

**Requirements:** R1, R2, R4, R5

**Dependencies:** None

**Files:**
- Modify: `server/apps/agent/services/agent_dispatch.py`
- Modify: `server/apps/agent/services/stream_events.py`
- Test: `server/tests/agent/unit/test_agent_dispatch.py`

**Approach:**
- 重构 `agent_dispatch.py` 的 astream 迭代，从仅提取 string content 改为按消息类型分发：
  - AIMessage 含 reasoning content → 发射 `phase.thinking` + `token(is_thinking=True)`（当前代码缺失 phase.thinking 发射，这是 U3 Shimmer 动画的前置依赖）
  - AIMessage 含 tool_calls → 发射 `tool.call` 事件（含 tool_name, tool_type, display_name, icon）
  - ToolMessage → 发射 `tool.result` 事件
  - AIMessage 含 text content → 发射 `phase.answering` + `token(is_thinking=False)`
- 后端为 tool.call 事件的 source of truth：工具名称到 {tool_type, display_name, icon} 的映射在后端维护，事件携带完整信息。前端 toolTypeRegistry 仅维护 summaryTemplate（展示文案模板），不做 display_name/icon 映射
- 在 stream_events.py 中为 tool_call 事件新增 `tool_type` 字段（业务类型：asset_query/report_gen/wish_analysis/trend_calc）

**Patterns to follow:**
- `server/apps/agent/services/stream_events.py` EventStreamBuilder 已有 tool_call()/tool_result() 方法签名
- `server/apps/agent/services/orchestrator.py` `_chunk_to_event_lines()` 的 phase.thinking 发射模式（agent_dispatch 当前缺失此逻辑）

**Test scenarios:**
- Happy path: agent 调用单工具 → 发射 phase.thinking → tool.call + tool.result → phase.answering，事件包含正确 tool_type/display_name/icon
- Happy path: agent 连续调用多工具 → 按顺序发射多组 tool.call/tool.result 事件
- Happy path: agent 纯思考无工具 → 发射 phase.thinking + token(is_thinking=True) → phase.answering
- Edge case: agent 无工具调用 → 只发射 phase + token 事件，不发射 tool 事件
- Error path: agent 中途崩溃 → capability.error 事件触发，所有 active 步骤标记为 failed
- Integration: 端到端 NDJSON 流包含完整事件序列（phase.connecting → phase.thinking → tool.call → tool.result → phase.answering → capability.end）

**Verification:**
- `pytest server/tests/agent/unit/test_agent_dispatch.py` 通过
- 手动测试 NDJSON 流中可见 phase.thinking、tool.call/tool.result 事件行

---

### U2. 后端新增 reasoning_effort 参数支持

**Goal:** 后端聊天流式接口支持 reasoning_effort 参数，与 deep_think 配合控制 AI 思考深度和工具调用行为。同时明确 web_search 参数在新模式下的处置。

**Requirements:** R6, R6b

**Dependencies:** None (与 U1 并行)

**Files:**
- Modify: `server/apps/backend/app/routers/ai_chat.py`
- Modify: `server/apps/agent/routers/agent_stream.py`
- Modify: `server/apps/agent/services/agent_dispatch.py`
- Modify: `server/apps/backend/app/schemas/` 相关 schema 文件
- Test: `server/tests/backend/test_ai_chat.py`

**Approach:**
- ChatStreamRequest schema 新增 `reasoning_effort` 可选字段（枚举：low/medium/high，默认 medium）
- ai_chat.py 路由将 reasoning_effort 透传给 agent_stream.py 的 AgentStreamRequest（当前缺失此中间层，reasoning_effort 会在 agent service 边界丢失）
- agent_stream.py 的 AgentStreamRequest 新增 `reasoning_effort` 字段，stream_agent_dispatch() 签名新增此参数
- agent_dispatch.py 将 reasoning_effort 注入 EffectiveConfigBuilder 的 config
- 兼容性：reasoning_effort 仅在 deep_think=true 时生效，deep_think=false 时忽略
- web_search 处置：智能模式默认 web_search=false，web_search 功能从独立开关降级为后端行为（智能模式下由 agent 自行决定是否需要搜索）。前端移除独立 web_search 开关，在 Scope Boundaries 中显式声明
- 实现前验证：先确认 reasoning_effort 传入 EffectiveConfigBuilder/DeerFlow 后实际能改变 agent 行为。若无效，则 U2 缩减为前端仅映射 deep_think（智能-轻量和智能-完整均发 deep_think=true），reasoning_effort 后端支持延后

**Patterns to follow:**
- 现有 `deep_think` → `enable_thinking` 的透传路径（ai_chat.py → agent_stream.py → agent_dispatch.py）

**Test scenarios:**
- Happy path: deep_think=true + reasoning_effort=low → 请求成功，config 含 reasoning_effort=low
- Happy path: deep_think=true + reasoning_effort=high → 请求成功，config 含 reasoning_effort=high
- Edge case: deep_think=false + reasoning_effort=any → reasoning_effort 被忽略
- Edge case: 不传 reasoning_effort → 默认 medium
- Edge case: 旧客户端不传 reasoning_effort → 行为与当前一致（向后兼容）

**Verification:**
- `pytest server/tests/backend/test_ai_chat.py` 通过
- 请求参数正确透传到 agent config（验证 agent_stream.py → agent_dispatch.py 链路）

---

### U3. 前端 Shimmer 动画 + 思考自动折叠

**Goal:** 用 Shimmer 渐变扫光动画替代当前脉冲圆点+计时器，思考结束后自动折叠。

**Requirements:** R1, R2, R3

**Dependencies:** None (与 U1/U2 并行)

**Files:**
- Create: `frontend/apps/main/src/components/ai/AiThinkingLabel.vue`
- Modify: `frontend/apps/main/src/pages/AIChatPage.vue`
- Modify: `frontend/apps/main/src/i18n/locales/zh-CN.ts`
- Modify: `frontend/apps/main/src/i18n/locales/en-US.ts`
- Test: `frontend/apps/main/tests/unit/components/ai/AiThinkingLabel.test.ts`

**Approach:**
- 新建 AiThinkingLabel 组件，接收 `isStreaming`、`duration` props
- 流式期间：显示 Shimmer 动画 + "思考中..." 文字（Shimmer 用 CSS `background-image: linear-gradient(...)` + `@keyframes shimmer-sweep` 从右到左循环，2s 周期）
- 流式结束：显示"思考了 Xs"文字，1 秒后 emit `auto-collapse` 事件（仅触发一次，用 ref 追踪）
- AIChatPage 中将 connecting-region 的脉冲圆点替换为 AiThinkingLabel
- 思考内容区域用 Vant Collapse 或 CSS transition 实现 fade + slide 动画

**Technical design:**

Shimmer CSS 核心思路：
- 文字元素设置 `background-image: linear-gradient(90deg, transparent 0%, var(--bg-shimmer) 50%, transparent 100%)`
- `background-size: 200% 100%`
- `@keyframes shimmer-sweep { from { background-position: 100% center } to { background-position: 0% center } }`
- `-webkit-background-clip: text; color: transparent` 使渐变只作用于文字

**Patterns to follow:**
- DeerFlow `shimmer.tsx` 的 CSS 渐变扫光模式
- DeerFlow `reasoning.tsx` 的自动折叠逻辑（1 秒延迟，hasAutoClosed 追踪）
- 现有 `shimmer-sweep` keyframe 在 AIChatPage.vue 中已用于 connecting-region

**Test scenarios:**
- Happy path: isStreaming=true → 渲染 Shimmer 动画 + "思考中..."
- Happy path: isStreaming=false, duration=8 → 渲染"思考了 8s"
- Edge case: duration=0 → 渲染"思考了不到1秒"
- Integration: 自动折叠在流式结束后 1 秒触发，用户手动展开后不再自动折叠

**Verification:**
- `npm run typecheck` 通过
- `npm run test:run` 通过
- 视觉验证：思考时标签有渐变扫光效果，结束后折叠

---

### U4. 前端 ChainOfThought 步骤渲染重构

**Goal:** 重构 AiProcessBlock 的工具步骤渲染，实现竖线连接、状态样式（含 error 状态）和按工具类型差异化展示。

**Requirements:** R4, R5

**Dependencies:** U1 (后端需发射 tool.call/tool.result 事件含 tool_type/display_name/icon)

**Files:**
- Modify: `frontend/apps/main/src/types/agent-stream.ts` (ProcessStep 新增 tool_type 字段)
- Modify: `frontend/apps/main/src/components/ai/AiProcessBlock.vue`
- Modify: `frontend/apps/main/src/components/ai/AiToolCallStep.vue`
- Create: `frontend/apps/main/src/utils/toolTypeRegistry.ts` (仅 summaryTemplate 映射)
- Modify: `frontend/apps/main/src/utils/aiEventNormalizer.ts`
- Modify: `frontend/apps/main/src/i18n/locales/zh-CN.ts`
- Modify: `frontend/apps/main/src/i18n/locales/en-US.ts`
- Test: `frontend/apps/main/tests/unit/components/ai/AiProcessBlock.test.ts`
- Test: `frontend/apps/main/tests/unit/utils/toolTypeRegistry.test.ts`

**Approach:**
- `agent-stream.ts` ProcessStep 的 tool_call 变体新增 `tool_type?: string` 字段；AgentEvent.tool 对象新增 `tool_type?: string`
- 前端以后端事件为 source of truth：tool.call 事件携带的 tool_type/display_name/icon 直接填入 ProcessStep，无需前端重复映射
- 新建 `toolTypeRegistry.ts` 仅维护 summaryTemplate（工具名 → 展示文案模板，如 "正在查询资产..."）。未知工具 fallback 为通用图标+"正在处理..."
- 重构 AiProcessBlock 渲染：
  - 步骤间用 1px 竖线连接（`border-left` 或绝对定位 `w-px` 线条）
  - 步骤状态样式（4 种）：complete=暗淡色，active=高亮，pending=半透明，error=红色调+错误图标+虚线竖线段
  - 工具步骤按 tool_type 显示对应图标和摘要
  - AiThinkingLabel 替代 AiProcessBlock 的 process-header 中的思考状态显示（U3 的 Shimmer 标签替代原 header 的脉冲圆点+计时器）
- AiToolCallStep 增加差异化渲染：根据 tool_type prop 显示不同图标和描述文字
- capability.error 事件处理：将所有 active 步骤标记为 failed 状态，显示错误样式
- 响应式：375px 下竖线连接步骤使用更紧凑间距，步骤图标缩小至 14px
- 无障碍：步骤列表使用 role="list"/role="listitem"，每个步骤 aria-label 含工具类型和状态

**Patterns to follow:**
- DeerFlow `chain-of-thought.tsx` 的竖线连接和 statusStyles 映射
- 现有 AiProcessBlock.vue 的 @media (max-width: 768px) 响应式规则
- 现有 AIChatInput.vue 的 aria-pressed/aria-label 无障碍模式

**Test scenarios:**
- Happy path: tool.call 事件含 tool_type=asset_query → 渲染资产图标 + "正在查询资产..."
- Happy path: 连续 3 个工具步骤 → 竖线连接，首个 active 高亮，后续 pending 半透明
- Error path: tool.result success=false → 步骤显示 error 样式（红色调+错误图标）
- Error path: capability.error 事件 → 所有 active 步骤转为 failed 状态
- Edge case: 未知工具名 → fallback 渲染通用图标 + "正在处理..."
- Integration: 后端 tool.call + tool.result 事件驱动步骤状态从 active → complete/error，样式正确切换

**Verification:**
- `npm run typecheck` 通过
- `npm run test:run` 通过
- 视觉验证：步骤间有竖线连接，4 种状态样式正确，375px 下布局不溢出

---

### U5. 前端 2 档+子选项输入模式

**Goal:** 将 deep_think 布尔开关扩展为普通/智能 2 档模式，智能模式含轻量/完整子选项。移除独立 web_search 开关（智能模式下由 agent 自行决定是否搜索）。

**Requirements:** R6, R6b

**Dependencies:** U2 (后端需支持 reasoning_effort 参数)

**Files:**
- Modify: `frontend/apps/main/src/components/common/AIChatInput.vue`
- Modify: `frontend/apps/main/src/pages/AIChatPage.vue`
- Modify: `frontend/apps/main/src/api/ai.ts`
- Modify: `frontend/apps/main/src/i18n/locales/zh-CN.ts`
- Modify: `frontend/apps/main/src/i18n/locales/en-US.ts`
- Test: `frontend/apps/main/tests/unit/components/common/AIChatInput.test.ts`

**Approach:**
- AIChatInput 新增 `mode` prop（枚举：normal | smart_light | smart_full），替代 deep_think/web_search 双布尔
- 移除独立 web_search 开关；智能模式下 web_search 由后端 agent 行为决定，前端不再发送 web_search 参数
- UI 改为：主按钮切换普通/智能，智能激活时显示子选项（轻量/完整），类似 DeerFlow 的 mode selector
- AIChatPage 将 mode 映射为请求参数：normal→`{deep_think:false}`；smart_light→`{deep_think:true, reasoning_effort:low}`；smart_full→`{deep_think:true, reasoning_effort:high}`
- ai.ts 的 sendChatMessageStream 新增 `reasoning_effort` 可选参数，`web_search` 参数保留但默认 false
- 模式切换时使用 Vant Dialog 确认（若当前对话已有消息），确认后开启新对话
- 响应式：375px 下模式选择器使用紧凑布局（图标+下拉而非展开式选项）
- 无障碍：模式按钮需 aria-pressed 和 aria-label，子选项需键盘箭头导航

**Patterns to follow:**
- DeerFlow input-box.tsx 的 mode selector 模式
- 现有 deepThink/webSearch v-model 模式
- 现有 AIChatInput.vue 的 aria-pressed/aria-label 无障碍模式

**Test scenarios:**
- Happy path: 选择普通模式 → 请求含 deep_think=false
- Happy path: 选择智能-轻量 → 请求含 deep_think=true, reasoning_effort=low
- Happy path: 选择智能-完整 → 请求含 deep_think=true, reasoning_effort=high
- Edge case: 对话中有消息时切换模式 → Vant Dialog 弹出确认，确认后开启新对话
- Edge case: 对话中切换智能模式子选项（轻量↔完整）→ 无需确认，直接切换
- Covers AE3.

**Verification:**
- `npm run typecheck` 通过
- `npm run test:run` 通过
- 三种模式的请求参数正确

---

### U6. 前端弹跳三点流式指示器 + 模板化建议药丸

**Goal:** 用弹跳三点动画替代闪烁光标，回答完成后显示模板化插值建议标签（border-radius: 4px，符合设计系统规范）。

**Requirements:** R7, R8

**Dependencies:** None (与 U3/U4 并行)

**Files:**
- Create: `frontend/apps/main/src/components/ai/StreamingDots.vue`
- Create: `frontend/apps/main/src/components/ai/SuggestionChips.vue`
- Create: `frontend/apps/main/src/utils/suggestionTemplates.ts`
- Modify: `frontend/apps/main/src/pages/AIChatPage.vue`
- Modify: `frontend/apps/main/src/i18n/locales/zh-CN.ts`
- Modify: `frontend/apps/main/src/i18n/locales/en-US.ts`
- Test: `frontend/apps/main/tests/unit/components/ai/StreamingDots.test.ts`
- Test: `frontend/apps/main/tests/unit/components/ai/SuggestionChips.test.ts`

**Approach:**
- StreamingDots 组件：三个圆点 flex 排列，`animation: bouncing 1s infinite`，0.2s 间隔延迟。圆点用 `var(--text-secondary)` 色，尺寸 w-2 h-2
- 替换 AIChatPage 中的 `.stream-cursor` span 为 `<StreamingDots />`
- SuggestionChips 组件（非药丸，使用 4px border-radius 符合设计系统）：接收 `suggestions: string[]`，渲染为圆角标签按钮行（border-radius: 4px，匹配 badge/tag 规范），点击 emit `select(text)`
- suggestionTemplates.ts：模板列表 + 插值函数。模板如 `"查看{category}详情"`、`"{category}趋势如何"`、`"分析我的{category}配置"`。从对话上下文提取变量（如最后一条 AI 消息涉及的资产类别）
- AIChatPage 在消息 phase=done 时生成建议并显示 SuggestionChips
- 响应式：375px 下标签使用 flex-wrap 或水平滚动，标签文字可截断
- 无障碍：StreamingDots 使用 aria-hidden="true" + visually-hidden live region；SuggestionChips 使用 role="group"，回答完成后键盘聚焦到标签组
- Reduced motion：StreamingDots 在 prefers-reduced-motion: reduce 下降级为静态三个点；SuggestionChips 出现动画降级为即时显示

**Patterns to follow:**
- DeerFlow `streaming-indicator.tsx` 的三点弹跳模式
- DeerFlow `suggestion.tsx` 的标签按钮模式
- 现有空状态 suggestion cards 的数据结构
- DESIGN.md: "Border Radius Scale: Sharp (4px): Buttons, badges, tags, small interactive elements"

**Test scenarios:**
- Happy path: StreamingDots 渲染三个圆点，有弹跳动画
- Happy path: 建议标签渲染 3-5 个按钮（4px border-radius），点击触发 select 事件
- Edge case: 模板插值变量为空 → 使用 fallback 默认值（如"资产"）
- Reduced motion: prefers-reduced-motion 下 StreamingDots 显示静态三点
- Integration: AI 回答完成 → 建议标签出现，点击标签 → 输入框填入文字并发送
- Covers AE4.

**Verification:**
- `npm run typecheck` 通过
- `npm run test:run` 通过
- 弹跳动画和标签交互正常，4px border-radius 符合设计系统

---

## System-Wide Impact

- **Interaction graph:** ai_chat.py 路由 → agent_dispatch.py → NDJSON 事件流 → 前端 normalizer → UI 渲染。U1 和 U2 修改了中间层（事件协议和请求参数），前后端需同步发布。
- **Error propagation:** tool.call 发射后若无 tool.result（agent 崩溃或超时），前端步骤停留在 active 状态。需在 capability.error 事件处理中将所有 active 步骤标记为 failed。
- **State lifecycle risks:** 模式切换（普通/智能）若在对话中途发生，可能导致前端 mode 与后端 session 状态不一致。通过"切换模式开启新对话"规避。
- **API surface parity:** sendChatMessageStream 参数变更（新增 reasoning_effort）需保持向后兼容——不传时默认行为不变。
- **Integration coverage:** U1 的后端事件变更 + U4 的前端消费需要端到端集成测试，验证完整事件序列从前端到 UI 渲染。

---

## Risks & Dependencies

| Risk | Mitigation |
|------|------------|
| agent_dispatch.py astream 重构可能因 LangGraph 输出格式变化而中断 | 参考现有 DeerFlow harness 的 astream 输出格式，写防御性解析（检查 tool_calls/reasoning_content 属性存在性） |
| 2 档模式与 deep_think 向后兼容 | 不传 reasoning_effort 时默认 medium，不传 deep_think 时默认 false，旧客户端不受影响 |
| Shimmer 动画在低端设备性能问题 | CSS 动画比 JS 动画性能好；prefers-reduced-motion: reduce 降级为静态文字（U3/U6 均需实现） |
| 建议标签模板插值与实际对话脱节 | v1 为过渡方案，从对话上下文尽力提取变量；v2 接后端 LLM 生成 |
| reasoning_effort 可能对 DeerFlow agent 无实际行为影响 | U2 实现前先验证；若无效则缩减为前端仅映射 deep_think，延后 reasoning_effort 后端支持 |
| 移除 web_search 开关影响现有用户 | 在 Scope Boundaries 中显式声明；智能模式下 agent 自行决定搜索行为；后续可恢复独立开关 |
| Legacy orchestrator 路径不发射 tool 事件 | v1 仅 agent-first 路径支持差异化工具展示；无 agent_id 的请求保持现有行为 |

---

## Sources & References

- **Origin document:** [docs/brainstorms/2026-05-27-deerflow-chat-ux-fusion-requirements.md](docs/brainstorms/2026-05-27-deerflow-chat-ux-fusion-requirements.md)
- DeerFlow 原生组件参考: reasoning.tsx, chain-of-thought.tsx, shimmer.tsx, streaming-indicator.tsx, input-box.tsx, suggestion.tsx
- Related: `docs/solutions/integration-issues/deerflow-adapter-stream-type-mismatch-and-security-issues-2026-05-16.md`
- Related: `docs/solutions/integration-issues/deerflow-harness-silent-fallback-and-concurrency-fixes-2026-04-12.md`
