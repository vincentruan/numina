# Agent Execution Canvas — Design Spec

**Date:** 2026-06-08
**Status:** Approved
**Scope:** Improve AI agent execution step visualization in chat UI — distinguish short Q&A from long-running tasks, provide user-friendly step summaries, and handle interrupted sessions gracefully.

---

## 1. Problem Statement

Current AI chat UI treats all agent responses uniformly:
- **Short Q&A** (1-2 steps) displayed in narrow bubble width — appropriate
- **Long-running tasks** (≥3 steps) also in narrow bubble — feels cramped, hard to follow progress
- **Deep think sessions** (extended thinking phase) — no visual distinction from regular responses
- **Interrupted sessions** — no indication of execution progress when resuming

### User Pain Points

1. **Visual mismatch:** Complex multi-step tasks (report generation, analysis) squeezed into chat bubble width
2. **Technical jargon:** Raw tool names like `get_asset_allocation`, `calculate_trend` shown to users
3. **No progress context:** Interrupted sessions show only final state, not execution trajectory
4. **Sensitive data exposure:** Raw tool arguments may contain sensitive info (API keys, internal paths)

### Goals

1. Auto-detect long-running tasks and switch to full-width "execution canvas" display
2. Transform technical tool names into user-friendly summaries (Chinese)
3. Provide collapsible detail panels with sensitive data redaction
4. Handle interrupted sessions with execution progress indicator
5. Maintain backward compatibility with existing chat sessions

### Non-Goals

- Changing backend orchestrator logic (DeerFlow stays unchanged)
- Modifying JSONL session journal format
- Adding new API endpoints (all data already available in stream events)
- Replacing existing component architecture (build on top of current components)

---

## 2. Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│  AIChatPage.vue                                                       │
│  - Detects isLongTask (steps.length >= 3 || hasDeepThink)            │
│  - Wraps long tasks in AgentRunCanvas (full-width container)          │
│  - Handles interrupted session detection                              │
└──────────────────────────────────┬──────────────────────────────────┘
                                   │ renders
                                   ▼
┌─────────────────────────────────────────────────────────────────────┐
│  AgentRunCanvas.vue                                                   │
│  - Full-width wrapper (max-width: 100% instead of 720px)             │
│  - Controls bubble ↔ full-width transition                            │
│  - Stores user collapse preference (localStorage)                     │
│  - Shows "running in background" hint when minimized                  │
└──────────────────────────────────┬──────────────────────────────────┘
                                   │ contains
                                   ▼
┌─────────────────────────────────────────────────────────────────────┐
│  AgentRunHeader.vue                                                   │
│  - Task summary header: status badge + elapsed time + model info      │
│  - Collapse/expand toggle                                             │
│  - "View details" button (opens detail panel)                         │
└──────────────────────────────────┬──────────────────────────────────┘
                                   │ displays
                                   ▼
┌─────────────────────────────────────────────────────────────────────┐
│  AiStepSummary.vue                                                    │
│  - User-friendly step summary (mapped from tool type)                 │
│  - Progress animation (pulse for running, checkmark for done)         │
│  - Collapsible to show merged tool calls                              │
└──────────────────────────────────┬──────────────────────────────────┘
                                   │ expands to
                                   ▼
┌─────────────────────────────────────────────────────────────────────┐
│  AiStepDetail.vue                                                     │
│  - Redacted tool arguments (sensitive fields masked)                  │
│  - Execution timestamp                                                │
│  - Error message with suggested action (if failed)                    │
│  - "View history" for merged steps                                    │
└─────────────────────────────────────────────────────────────────────┘
```

### Data Flow

```
Stream Event (tool.call)
    │
    ├── type: "tool_call"
    ├── tool: "get_asset_allocation"
    ├── args: { family_id: "xxx", ... }
    ├── result: { ... }
    └── status: "completed"
    │
    ▼
aiEventNormalizer.ts (existing)
    │
    ▼
ProcessStep {
    name: "get_asset_allocation",
    args: { ... },
    result: { ... },
    status: "completed",
    timestamp: "2026-06-08T..."
}
    │
    ▼
aiStepSummary.ts (NEW)
    │
    ├── toolTypeMap: tool name → category
    ├── summaryTextMap: category → Chinese summary
    └── mergeStrategy: consecutive same-category → single summary
    │
    ▼
AiStepSummary.vue
    │
    ├── Display: "获取资产配置" (user-friendly)
    ├── Icon: category-specific
    └── Status: running/done/error
    │
    ▼ (user clicks "详情")
AiStepDetail.vue
    │
    ├── aiEventRedactor.ts (NEW)
    │   └── SENSITIVE_KEYS: ["api_key", "password", "token", "secret", "internal_path"]
    │   └── redact(obj): replaces sensitive values with "***REDACTED***"
    │
    └── Display: redacted args + timestamp
```

---

## 3. Tool Category Mapping

### Categories

| Category | Tools | User-Friendly Summary |
|----------|-------|----------------------|
| `data_query` | `get_asset_allocation`, `get_liability_summary`, `query_assets`, `query_family_members` | 查询数据 |
| `calculation` | `calculate_trend`, `calculate_net_worth`, `compute_allocation_ratio` | 计算分析 |
| `report_gen` | `generate_report`, `create_chart`, `export_data` | 生成报告 |
| `web_search` | `web_search`, `fetch_url`, `scrape_content` | 网络搜索 |
| `deep_think` | (thinking phase) | 深度思考 |
| `file_ops` | `read_file`, `write_file`, `upload_file` | 文件操作 |
| `external_api` | `call_external_api`, `fetch_exchange_rate` | 调用外部服务 |

### Merge Strategy

Consecutive steps of the same category are merged into one summary line:
- `get_asset_allocation` → `calculate_trend` → `calculate_net_worth` (3 separate)
- Merged display: "计算分析 (3次)"

User can expand to see individual calls with timestamps.

---

## 4. Sensitive Data Redaction

### Sensitive Keys (SENSITIVE_KEYS)

```typescript
const SENSITIVE_KEYS = [
  'api_key', 'apikey', 'key',
  'password', 'pwd', 'pass',
  'token', 'access_token', 'auth_token',
  'secret', 'secret_key',
  'internal_path', 'file_path', 'path',
  'credential', 'credentials',
  'private_key', 'private'
];
```

### Redaction Logic

```typescript
function redact(obj: Record<string, unknown>, depth = 0): Record<string, unknown> {
  if (depth > 5) return { _truncated: '...' }; // Prevent deep recursion

  const result: Record<string, unknown> = {};
  for (const [key, value] of Object.entries(obj)) {
    const lowerKey = key.toLowerCase();
    if (SENSITIVE_KEYS.some(k => lowerKey.includes(k))) {
      result[key] = '***REDACTED***';
    } else if (typeof value === 'object' && value !== null) {
      result[key] = redact(value as Record<string, unknown>, depth + 1);
    } else {
      result[key] = value;
    }
  }
  return result;
}
```

---

## 5. Long Task Detection

### Criteria

```typescript
function isLongTask(steps: ProcessStep[], hasDeepThink: boolean): boolean {
  // Deep think always triggers full-width
  if (hasDeepThink) return true;

  // 3+ steps = long task
  if (steps.length >= 3) return true;

  // Report generation = long task
  if (steps.some(s => s.name === 'generate_report')) return true;

  // Web search with multiple results = long task
  if (steps.some(s => s.name === 'web_search' && s.result?.results?.length > 3)) return true;

  return false;
}
```

### User Override

- User can manually collapse full-width display back to bubble
- Preference stored in `localStorage: ai-chat-collapse-preference`
- On next long task, respects stored preference

---

## 6. Interrupted Session Handling

### Detection

```typescript
function isInterruptedSession(steps: ProcessStep[], finalStatus: string): boolean {
  // Session ended but last step not completed
  if (finalStatus === 'ended' && steps.some(s => s.status === 'running')) {
    return true;
  }

  // Session has error but no explicit failure step
  if (finalStatus === 'error' && !steps.some(s => s.status === 'error')) {
    return true;
  }

  return false;
}
```

### Display

When interrupted session is detected:
1. Show "执行中断" badge in header
2. Display progress summary: "已完成 3/5 步骤"
3. Provide "继续执行" button if session can be resumed
4. Gray out incomplete steps

---

## 7. Summary & File Change List

### 7.1 新增文件

| 文件路径 | 职责 | 行数估算 |
|----------|------|----------|
| `components/ai/AgentRunCanvas.vue` | 全宽 wrapper，控制气泡/全宽切换 | ~80 |
| `components/ai/AgentRunHeader.vue` | 任务摘要头部：状态 + 耗时 + 模型信息 | ~60 |
| `components/ai/AiStepSummary.vue` | 用户友好摘要展示 + 动效 | ~50 |
| `components/ai/AiStepDetail.vue` | 脱敏详情折叠面板 | ~100 |
| `utils/aiStepSummary.ts` | 工具类型 → 用户友好文案映射 | ~120 |
| `utils/aiEventRedactor.ts` | 敏感字段脱敏函数 | ~80 |

### 7.2 改造文件

| 文件路径 | 改动内容 | 改动量 |
|----------|----------|--------|
| `pages/AIChatPage.vue` | 添加 isLongTask 检测、AgentRunCanvas wrapper、中断状态检测、后台提示 | +150 行 |
| `components/ai/AiProcessBlock.vue` | 新增 fullWidth prop、样式适配全宽 | +30 行 |
| `components/ai/AiStepBlock.vue` | 新增 summary slot、redactedArgs prop、详情折叠 | +60 行 |
| `i18n/locales/zh-CN.ts` | 新增 aiStepSummary 翻译组 | +40 行 |

### 7.3 可选后端改动（Phase 2）

| 文件路径 | 改动内容 | 改动量 |
|----------|----------|--------|
| `services/stream_events.py` | tool_call 增加 category 字段 | +10 行 |
| `services/orchestrator.py` | `_chunk_to_event_lines` 增加 display_summary | +20 行 |

### 7.4 不改动的关键文件

| 文件 | 理由 |
|------|------|
| `utils/aiEventNormalizer.ts` | 已满足需求，无需改动 |
| `types/agent-stream.ts` | ProcessStep 类型已完整，无需扩展 |
| `services/session_journal.py` | JSONL 记录逻辑不变 |
| `deerflow_adapter/adapter.py` | DeerFlow 编排不变 |
| API 协议 | 所有新字段 optional，向后兼容 |

---

## 8. Verification Steps

### Phase 1 验证（前端改动）

```bash
# 1. TypeScript 检查
cd frontend/apps/main
pnpm typecheck

# 2. ESLint
pnpm lint

# 3. 构建
pnpm build

# 4. 手动验证场景
# - 短问答（无 steps）：保持气泡宽度
# - 长任务（≥3 steps）：自动全宽
# - Deep think：thinking 阶段立即全宽
# - 用户折叠：记住偏好
# - 中断会话恢复：显示执行进度
# - 步骤失败：显示友好错误 + 建议操作
# - 脱敏验证：敏感字段不显示
```

### Phase 2 验证（后端改动 - 可选）

```bash
cd server
uv run ruff check apps/agent/
uv run mypy apps/agent/
uv run pytest apps/agent/tests/ -v

# 验证事件字段
curl http://localhost:8001/api/v1/ai/sessions/{id}/events | jq 'select(.type=="tool.call") | .tool'
# 应包含 category 字段
```

---

## 9. Potential Risks

| 风险 | 影响 | 缓解措施 |
|------|------|----------|
| **阈值误判** | 短长任务边界模糊 | 用户可手动折叠，阈值可配置 |
| **旧会话无 JSONL** | 无法恢复执行过程 | 降级为纯文本消息 |
| **脱敏遗漏** | 敏感字段暴露 | 定期审计 SENSITIVE_KEYS 列表 |
| **步骤合并丢失信息** | 用户看不到每次调用详情 | 合并后提供"查看历史"展开 |
| **中断检测失败** | 错误标记为完成 | fallback 为正常结束状态 |

---

## 10. Follow-up Suggestions

1. **Phase 1 先行:** 前端改动独立验证，不影响后端
2. **用户反馈收集:** 阈值调优、文案优化
3. **Phase 2 可选:** 后端增强仅在需要更精准分类时实施
4. **监控:** 记录 `isLongTask` 触发比例，辅助阈值调优

---

## 11. Total Change Estimate

| 类型 | 文件数 | 新增行数 |
|------|--------|----------|
| 新增 | 6 | ~400 |
| 改造 | 4 | ~280 |
| 后端可选 | 2 | ~30 |
| **合计** | **12** | **~710** |

---

## 12. Design Principles

设计完成。整体方案最小侵入，复用现有组件，不破坏 DeerFlow 编排逻辑，向后兼容旧会话。

- **Minimal intrusion:** All new components are additive, no existing logic changes
- **Reuse existing components:** Build on top of `AiProcessBlock` and `AiStepBlock`
- **DeerFlow unchanged:** Orchestrator logic stays the same
- **Backward compatible:** Old sessions degrade gracefully to text-only display