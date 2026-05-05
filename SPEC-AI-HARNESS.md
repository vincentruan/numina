# Spec: AI Harness 优化 — 流式任务系统 + 深度思考 + Prompt 抽象

## Objective

优化 `/ai` 页面下所有 DeerFlow harness 调用，实现三个目标：

1. **Prompt/Skill/MCP 抽象** — 将各 capability 的 prompt 从 Python 代码中提取到独立配置文件，统一 skill 注册机制，MCP 工具声明集中管理，遵循 harness 最佳实践
2. **深度思考默认开启** — 若家庭 AI 配置的模型支持 extended thinking（通过现有 `testThinkingOnly()` 检测结果判断），在所有 capability 调用中自动启用，包括 chat
3. **任务状态可观测性** — 新增 `ai_tasks` 表以家庭维度记录所有长任务（非 chat），每个 capability 独立限制一个在途请求，超时判定 30 分钟；前台以"会话台"方式展示流式输出，用户切走再回来可接续

**用户**：家庭管理员（owner 角色），使用 `/ai` 下各功能页面

**成功标准**：
- 点击"生成报告"后，若无在途任务则立即开始，若有则提示等待
- 前台展示滚动会话台（最多保留最后 10 条对话），标题显示状态 + 累计耗时（自动累加到时分）
- 用户切走再回来，若任务仍在运行则接续 streaming；若已完成则折叠会话台展示结果
- 服务重启后，30 分钟内未完成的任务自动标记为 timeout，不阻塞新任务
- 所有 capability 的 prompt 可在不修改 Python 代码的情况下调整

---

## Tech Stack

| 层 | 技术 |
|---|---|
| Backend | Python 3.11 + FastAPI + SQLAlchemy + Alembic |
| Agent | Python 3.11 + FastAPI + DeerFlow/LangChain |
| Frontend | Vue 3 + TypeScript + Vite + Vant 4 |
| 流式传输 | MCP Streamable HTTP（替换现有 WebSocket） |
| 任务持久化 | SQLite（复用现有 `AIChatSession` JSONL 机制） |

---

## Commands

```bash
# Backend
cd backend && uv run alembic upgrade head          # 应用迁移
cd backend && uv run pytest tests/ -v              # 运行测试

# Agent
cd agent && uv run pytest tests/ -v                # 运行测试
cd agent && uv run uvicorn app.main:app --reload   # 开发服务器

# Frontend
cd frontend && npm run typecheck                   # 类型检查
cd frontend && npm run dev                         # 开发服务器
```

---

## Project Structure

### 新增/修改文件

```
agent/
  skills/                          ← 新增：capability prompt 配置目录
    report.md                      ← 体检报告 skill prompt
    alerts.md                      ← 老化预警 skill prompt
    disposal.md                    ← 处置建议 skill prompt
    allocation.md                  ← 配置漂移 skill prompt
    spending_leak.md               ← 支出泄漏 skill prompt
    liability.md                   ← 负债顾问 skill prompt
    time_machine.md                ← 时间机器 skill prompt
    chat.md                        ← 问答助手 skill prompt
  mcp/
    tools.yaml                     ← 新增：MCP 工具声明集中配置
  services/
    orchestrator.py                ← 修改：注入 thinking 参数 + streaming
    deerflow_adapter/
      adapter.py                   ← 修改：支持 stream_dispatch（yield chunks）
      skill_loader.py              ← 新增：从 skills/*.md 加载 prompt
  routers/
    report.py                      ← 修改：改为 streamable-http 端点
    alerts.py                      ← 修改：同上
    disposal.py                    ← 修改：同上
    allocation.py                  ← 修改：同上
    spending_leak.py               ← 修改：同上
    liability.py                   ← 修改：同上
    time_machine.py                ← 修改：同上

backend/
  app/
    models/
      ai_task.py                   ← 新增：AITask 模型
    routers/
      ai_report.py                 ← 修改：任务状态检查 + streamable-http
      ai_alerts.py                 ← 修改：同上
      ai_disposal.py               ← 修改：同上
      ai_allocation.py             ← 修改：同上
      ai_spending_leaks.py         ← 修改：同上
      ai_liability.py              ← 修改：同上
      ai_time_machine.py           ← 修改：同上
    migrations/
      xxxx_add_ai_tasks.py         ← 新增：Alembic 迁移

frontend/
  apps/main/src/
    composables/
      useAITask.ts                 ← 新增：任务状态 + streaming 接续逻辑
      useTaskConsole.ts            ← 新增：会话台 UI 逻辑（滚动、耗时累加）
    components/ai/
      TaskConsole.vue              ← 新增：会话台组件
    pages/
      AIReportPage.vue             ← 修改：使用 TaskConsole
      AIAlertsPage.vue             ← 修改：同上
      AIDisposalPage.vue           ← 修改：同上
      AIAllocationPage.vue         ← 修改：同上
      SpendingLeaksPage.vue        ← 修改：同上
      AILiabilityAdvisorPage.vue   ← 修改：同上
      AITimeMachinePage.vue        ← 修改：同上
    api/
      ai.ts                        ← 修改：新增任务状态 API + streamable-http 调用
    i18n/locales/
      zh-CN.ts                     ← 修改：新增任务相关 i18n key
```

---

## Data Model

### `ai_tasks` 表

```python
class AITask(Base):
    __tablename__ = "ai_tasks"

    id: Mapped[str]           # UUID，主键
    family_id: Mapped[int]    # 家庭 ID，FK → families.id
    capability: Mapped[str]   # "report" | "alerts" | "disposal" | ...
    status: Mapped[str]       # "running" | "completed" | "failed" | "timeout"
    session_id: Mapped[str | None]  # FK → ai_chat_sessions.id（复用 JSONL）
    started_at: Mapped[datetime]
    completed_at: Mapped[datetime | None]
    error_message: Mapped[str | None]

    # 唯一约束：每个家庭每个 capability 只允许一个 running 任务
    # UniqueConstraint("family_id", "capability", condition="status='running'")
    # → 用应用层检查实现（SQLite partial index 兼容性）
```

**任务超时判定**：`status='running' AND started_at < NOW() - 30min` → 视为 timeout

---

## Streaming 协议

### Agent 侧（Streamable HTTP）

```python
# agent/routers/report.py
@router.post("/generate/stream")
async def generate_report_stream(
    x_family_id: str = Header(...),
    x_agent_token: str = Header(...),
    x_task_id: str = Header(...),      # 新增：任务 ID，用于 JSONL 关联
):
    async def event_stream():
        async for chunk in orchestrator.stream_dispatch(
            capability="report",
            family_id=x_family_id,
            task_id=x_task_id,
        ):
            yield chunk.encode()

    return StreamingResponse(event_stream(), media_type="text/plain")
```

### Backend 侧（透传 + 任务状态更新）

```python
# backend/app/routers/ai_report.py
@router.post("/generate")
async def trigger_generate(current_user, db):
    # 1. 检查在途任务（含超时判定）
    existing = _get_running_task(current_user.family_id, "report", db)
    if existing:
        raise AppError(ErrorCode.TASK_IN_PROGRESS, "报告生成中，请稍后")

    # 2. 创建 AIChatSession（复用 JSONL 机制）
    session = await ChatSessionService.create_session(...)

    # 3. 创建 AITask 记录
    task = AITask(capability="report", session_id=session.id, status="running", ...)
    db.add(task); db.commit()

    # 4. 后台调用 agent streaming，透传给前端
    return StreamingResponse(_proxy_stream(task, session, current_user, db), ...)
```

### Frontend 侧（接续逻辑）

```typescript
// composables/useAITask.ts
async function startOrResume(capability: string) {
  const task = await api.getRunningTask(capability)
  if (task?.status === 'running') {
    // 接续：连接 streaming，从 JSONL 加载已有消息
    await resumeStream(task)
  } else {
    // 新建：触发生成
    await startStream(capability)
  }
}
```

---

## Prompt/Skill 抽象

### Skill 文件格式（`agent/skills/{capability}.md`）

```markdown
---
capability: report
thinking: true          # 是否启用 extended thinking（若模型支持）
mcp_tools:              # 声明此 skill 需要的 MCP 工具
  - numina_assets
  - numina_liabilities
---

# 家庭资产体检报告

你是一位专业的家庭财务顾问...

## 分析维度
1. 净资产健康度
2. 资产配置合理性
...
```

### Skill Loader

```python
# agent/services/deerflow_adapter/skill_loader.py
class SkillLoader:
    def load(self, capability: str) -> SkillConfig:
        """从 skills/{capability}.md 加载 prompt + 元数据"""
        ...

    def get_prompt(self, capability: str) -> str: ...
    def thinking_enabled(self, capability: str) -> bool: ...
    def mcp_tools(self, capability: str) -> list[str]: ...
```

---

## Deep Thinking 注入

```python
# agent/services/orchestrator.py（修改 dispatch）
async def dispatch(self, capability, family_id, ...):
    skill_config = skill_loader.load(capability)

    # thinking_supported：查询 ai_provider_test_results 最新一条
    # test_type='thinking' AND success=True AND config_id=active_config.id
    thinking_supported = ai_config.get("thinking_supported", False)

    adapter = create_family_adapter(
        family_id,
        ai_config,
        enable_thinking=skill_config.thinking and thinking_supported,
    )
    ...
```

`thinking_supported` 字段来源：
- `ai_provider_test_results` 表已有 `test_type='thinking'` + `success` 字段
- Backend `get_family_ai_config()` 响应中新增 `thinking_supported: bool` 字段
- 计算逻辑：取当前 active config 的最新一条 `test_type='thinking'` 记录，`success=True` 则为 `true`
- 用户在 AIConfigPage 点击"🧠 测试思考"后结果自动写入，下次 dispatch 生效

---

## 会话台 UI 规格

### TaskConsole 组件行为

| 状态 | 标题 | 内容 |
|---|---|---|
| running | `⏳ 分析中 · 02:34` | 滚动输出，保留最后 10 条 |
| completed | `✅ 已完成 · 05:12` | 折叠，展示结果 |
| failed | `❌ 失败 · 01:08` | 展示错误信息 |
| timeout | `⏰ 超时` | 提示重试 |

- 耗时格式：`MM:SS`，超过 1 小时显示 `HH:MM`
- 每秒自动累加耗时（`setInterval`）
- 最多保留最后 10 条 chunk，超出时从头部移除（避免浏览器崩溃）
- 用户切走（`visibilitychange`）时停止 streaming 连接，保留已有消息
- 用户回来时调用 `startOrResume()`，若任务仍 running 则重连 streaming

---

## Code Style

```python
# agent/services/deerflow_adapter/skill_loader.py
import yaml
from pathlib import Path
from dataclasses import dataclass

SKILLS_DIR = Path(__file__).parent.parent.parent / "skills"

@dataclass
class SkillConfig:
    capability: str
    prompt: str
    thinking: bool = True
    mcp_tools: list[str] = field(default_factory=list)

class SkillLoader:
    _cache: dict[str, SkillConfig] = {}

    def load(self, capability: str) -> SkillConfig:
        if capability in self._cache:
            return self._cache[capability]
        path = SKILLS_DIR / f"{capability}.md"
        if not path.exists():
            raise FileNotFoundError(f"Skill not found: {capability}")
        # parse frontmatter + body
        ...
        self._cache[capability] = config
        return config
```

```typescript
// frontend: composables/useAITask.ts
export function useAITask(capability: string) {
  const status = ref<'idle' | 'running' | 'completed' | 'failed' | 'timeout'>('idle')
  const chunks = ref<string[]>([])          // 最多 10 条
  const elapsedSeconds = ref(0)

  const MAX_CHUNKS = 10

  function appendChunk(text: string) {
    chunks.value.push(text)
    if (chunks.value.length > MAX_CHUNKS) {
      chunks.value.shift()
    }
  }
  ...
}
```

**命名约定**：
- Python：snake_case，类名 PascalCase
- TypeScript：camelCase，组件名 PascalCase
- i18n key：`ai.task.{capability}.{key}`（如 `ai.task.report.generating`）
- Emoji 前缀：遵循现有 toast/error 规范

---

## Testing Strategy

| 层 | 框架 | 覆盖目标 |
|---|---|---|
| Backend unit | pytest | `AITask` CRUD、超时判定逻辑 |
| Agent unit | pytest | `SkillLoader.load()`、`stream_dispatch()` chunk 收集 |
| Integration | pytest + httpx | 任务创建 → streaming → 完成全流程 |
| Frontend | 手动 + typecheck | `useAITask` 状态机、`TaskConsole` 渲染 |

测试文件位置：
- `backend/tests/test_ai_task.py`
- `agent/tests/test_skill_loader.py`
- `agent/tests/test_orchestrator_streaming.py`

---

## Boundaries

**Always:**
- 所有 UI 字符串通过 `t('key')` 引用，key 定义在 `zh-CN.ts`
- 任务状态检查必须包含超时判定（`started_at < NOW() - 30min`）
- Streaming chunk 写入 JSONL（复用 `ChatSessionService.append_message`）
- `AITask` 创建和 `AIChatSession` 创建在同一事务中

**Ask first:**
- 修改 `AIChatSession` 或 `ChatSessionService` 的现有字段/行为
- 修改 DeerFlow `config.yaml` 结构
- 为 `ai_tasks` 表添加索引或约束
- 修改现有 chat（`/ai/chat`）的行为

**Never:**
- 在 `.vue` 文件中硬编码中文字符串
- 在同一事务外创建 `AITask`（避免孤立任务）
- 删除现有 WebSocket 端点（保留向后兼容，新增 streamable-http 端点）
- 在 `skills/*.md` 中硬编码 API key 或家庭数据

---

## Success Criteria

- [ ] 点击"生成报告"：若有 running 任务（且未超时）则返回 409 + 提示；否则创建任务并开始 streaming
- [ ] 服务重启后，30 分钟前的 running 任务在下次请求时自动标记为 timeout
- [ ] 前台会话台：标题每秒累加耗时，内容保留最后 10 条 chunk
- [ ] 用户切走再回来：若任务 running 则重连 streaming 并接续；若 completed 则折叠展示结果
- [ ] 修改 `agent/skills/report.md` 中的 prompt 后重启 agent，报告内容随之变化（无需改 Python）
- [ ] 支持 extended thinking 的模型（`thinking_supported=true`）调用时，DeerFlow 收到 thinking 参数
- [ ] `npm run typecheck` 通过，`uv run pytest` 通过

---

## Open Questions

无。所有关键决策已确认：
- 每个 capability 独立限制一个在途请求 ✓
- 统一改为 streamable-http（保留旧 WebSocket 端点向后兼容）✓
- 复用现有 `AIChatSession` + JSONL 机制 ✓
- 用户回来时接续 streaming（若任务仍在跑）✓
