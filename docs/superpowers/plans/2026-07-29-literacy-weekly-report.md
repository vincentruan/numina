# Literacy Weekly Report — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a per-child AI-generated weekly literacy report accessible from the BabyPage via a dedicated chat session, with scheduled auto-generation and follow-up conversation support.

**Architecture:** Extend the existing MCP data tool registry with two read-only literacy tools. Create a new agent (`literacy-weekly-report`) with its own SKILL.md, worker runner, and gateway trigger. The backend orchestrates report generation via `AgentClient` SSE streaming (mirroring `dashboard_narrative.py`), caches results in the existing `LiteracyWeeklyReport` table (extended with `thread_id`), and exposes a status endpoint for the BabyPage entry. The frontend adds a `van-cell` entry gated by `aiStore.aiEnabled`, navigates to `/ai/chat?thread_id=<id>` for the dedicated session. A scheduler cron job pre-generates reports weekly on a configurable schedule.

**Tech Stack:** Python 3.12 + FastAPI + SQLAlchemy + APScheduler (backend), Vue 3 + Vant 4 + TypeScript + Pinia (frontend), DeerFlow agent runtime (agent), MCP protocol (data tools)

## Global Constraints

- All API endpoints: `redirect_slashes=False`, root decorators use `""` not `"/"`
- All response schemas with IDs inherit `SnowflakeBase` (string serialization)
- All UI strings via i18n — no hard-coded Chinese in `.vue` or `.ts`
- Backend errors use `AppError(ErrorCode.XXX)` with Chinese detail strings
- Agent communication always via `AgentClient` (never raw `httpx`)
- Import direction: agent never imports from backend; use `packages/` for shared logic
- MCP tools: registry in `mcp_tool_registry.py`, zero outbound HTTP from MCP layer
- Agent dispatch: all multi-step orchestration via `DeerFlowAdapter.typed_stream_dispatch`
- Scheduler jitter: per-family `random.uniform(0, 300)` for cron jobs
- Config settings: `config_registry.py` is SSOT for defaults/types/validation

---

## File Map

| File | Responsibility |
|------|---------------|
| `server/apps/backend/app/services/mcp_tool_registry.py` | Add `get_child_literacy_profile`, `get_literacy_weekly_data` to `_REGISTRY` |
| `server/apps/backend/app/routers/mcp_internal.py` | Add tool handler implementations (query DB, return JSON) |
| `server/apps/agent/skills/builtin/public/literacy-weekly-report/SKILL.md` | Agent prompt + allowed-tools declaration |
| `server/apps/agent/services/runtime/worker.py` | Add `_run_literacy_weekly_report_agent` branch + runner |
| `server/apps/agent/services/runtime/sse_gateway.py` | Add R1 block + allowlist entry for `literacy-weekly-report` |
| `server/apps/agent/app/routers/gateway.py` | Add `POST /internal/gateway/runs/literacy-weekly-report/{thread_id}` |
| `server/apps/backend/app/services/literacy_report_service.py` | **New** — orchestrate report generation + caching (mirrors `dashboard_narrative.py`) |
| `server/apps/backend/app/routers/ai_literacy_report.py` | **New** — `POST /ai/literacy-report/generate` trigger endpoint |
| `server/apps/backend/app/routers/literacy_parent.py` | Add `GET /literacy-reports/status` for BabyPage entry |
| `server/packages/db/models/literacy_report.py` | Add `thread_id` column |
| `server/apps/backend/alembic/versions/<new>.py` | Migration: add `thread_id` to `literacy_weekly_reports` |
| `server/apps/backend/app/routers/ai_skills.py` | Add `"literacy-weekly-report"` to `RESERVED_NAMES` |
| `server/apps/backend/app/services/config_registry.py` | Add `literacy_report_day`, `literacy_report_hour`, `literacy_report_cache_ttl` |
| `server/apps/agent/app/scheduler.py` | Add weekly literacy report cron job |
| `frontend/apps/main/src/api/literacyReport.ts` | **New** — API client for literacy report status + generate |
| `frontend/apps/main/src/pages/BabyPage.vue` | Add literacy report entry cell |
| `frontend/apps/main/src/i18n/locales/zh-CN.ts` | Add `baby.literacyReport*` keys |
| `frontend/apps/main/src/i18n/locales/en-US.ts` | Add `baby.literacyReport*` keys |
| `server/tests/backend/services/test_literacy_report_service.py` | **New** — service tests |
| `server/tests/backend/routers/test_ai_literacy_report.py` | **New** — router tests |
| `server/tests/backend/routers/test_literacy_report_status.py` | **New** — status endpoint tests |

---

### Task 1: MCP Tool Registry — Add Literacy Data Tools

**Files:**
- Modify: `server/apps/backend/app/services/mcp_tool_registry.py:22-217`
- Test: `server/tests/backend/unit/test_mcp_tool_registry.py`

**Interfaces:**
- Consumes: existing `_REGISTRY` dict, `MCPToolMeta` dataclass
- Produces: two new entries in `_REGISTRY` — `get_child_literacy_profile` and `get_literacy_weekly_data`

- [ ] **Step 1: Write failing test for new registry entries**

In `server/tests/backend/unit/test_mcp_tool_registry.py`, add:

```python
def test_literacy_tools_registered():
    """Literacy MCP tools are registered with correct metadata."""
    from apps.backend.app.services.mcp_tool_registry import get_tool

    profile_tool = get_tool("get_child_literacy_profile")
    assert profile_tool is not None
    assert profile_tool.requires_write is False
    assert "owner" in profile_tool.allowed_roles
    assert "member" in profile_tool.allowed_roles
    assert "child" not in profile_tool.allowed_roles

    data_tool = get_tool("get_literacy_weekly_data")
    assert data_tool is not None
    assert data_tool.requires_write is False
    assert "child_id" in data_tool.input_schema["properties"]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd server && uv run pytest tests/backend/unit/test_mcp_tool_registry.py::test_literacy_tools_registered -v`
Expected: FAIL — `get_tool("get_child_literacy_profile")` returns None

- [ ] **Step 3: Add tool definitions to `_REGISTRY`**

In `server/apps/backend/app/services/mcp_tool_registry.py`, append to the `_REGISTRY` dict (before the closing `}`):

```python
    "get_child_literacy_profile": MCPToolMeta(
        name="get_child_literacy_profile",
        description=(
            "获取家庭中孩子的财商启蒙档案：昵称、年龄段、当前徽章等级、"
            "累计场景完成数、本周周报状态。支持按 child_id 过滤。"
        ),
        input_schema={
            "type": "object",
            "properties": {
                "child_id": {
                    "type": "string",
                    "description": "孩子的 user ID（可选，不传则返回所有孩子）",
                },
            },
            "required": [],
        },
        allowed_roles=frozenset({"owner", "member"}),
        requires_write=False,
    ),
    "get_literacy_weekly_data": MCPToolMeta(
        name="get_literacy_weekly_data",
        description=(
            "获取指定孩子某周的财商启蒙数据：家务完成率、星星币收支、"
            "场景完成情况、徽章变化、与上周的趋势对比。"
        ),
        input_schema={
            "type": "object",
            "properties": {
                "child_id": {
                    "type": "string",
                    "description": "孩子的 user ID",
                },
                "week_start": {
                    "type": "string",
                    "description": "周起始日 ISO 格式（Sunday），不传则返回最近一周",
                },
            },
            "required": ["child_id"],
        },
        allowed_roles=frozenset({"owner", "member"}),
        requires_write=False,
    ),
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd server && uv run pytest tests/backend/unit/test_mcp_tool_registry.py::test_literacy_tools_registered -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add server/apps/backend/app/services/mcp_tool_registry.py server/tests/backend/unit/test_mcp_tool_registry.py
git commit -m "feat(mcp): add get_child_literacy_profile and get_literacy_weekly_data tools"
```

---

### Task 2: MCP Tool Handlers — Implement Data Query Logic

**Files:**
- Modify: `server/apps/backend/app/routers/mcp_internal.py` (add handler cases)
- Test: `server/tests/backend/routers/test_mcp_internal_literacy.py`

**Interfaces:**
- Consumes: `get_child_literacy_profile` / `get_literacy_weekly_data` tool names from registry
- Produces: JSON responses with child profile data and weekly literacy data
- Depends on: Task 1 (registry entries)

The MCP tool handler pattern in `mcp_internal.py` routes tool calls from the agent's MCP session to backend DB queries. Each tool name maps to a handler function that receives `family_id` + tool `arguments` and returns a dict.

- [ ] **Step 1: Write failing tests for handler logic**

Create `server/tests/backend/routers/test_mcp_internal_literacy.py`:

```python
"""Tests for literacy MCP tool handlers."""
import pytest
from datetime import date, timedelta

from apps.backend.app.services.mcp_tool_handlers import (
    handle_get_child_literacy_profile,
    handle_get_literacy_weekly_data,
)


@pytest.mark.asyncio
async def test_get_child_literacy_profile_returns_children(db, family_with_children):
    """Returns child profiles with badge and scenario data."""
    result = await handle_get_child_literacy_profile(
        db, family_id=family_with_children.id, arguments={}
    )
    assert "children" in result
    assert len(result["children"]) > 0
    child = result["children"][0]
    assert "child_id" in child
    assert "display_name" in child
    assert "age_group" in child
    assert "current_badges" in child


@pytest.mark.asyncio
async def test_get_child_literacy_profile_filter_by_child_id(db, family_with_children):
    """Filtering by child_id returns only that child."""
    children = (
        db.query(User)
        .filter(User.family_id == family_with_children.id, User.role == "child")
        .all()
    )
    target_id = str(children[0].id)
    result = await handle_get_child_literacy_profile(
        db, family_id=family_with_children.id, arguments={"child_id": target_id}
    )
    assert len(result["children"]) == 1
    assert result["children"][0]["child_id"] == target_id


@pytest.mark.asyncio
async def test_get_literacy_weekly_data_returns_signals(db, family_with_children):
    """Returns weekly data with chore/coin/scenario/badge signals."""
    children = (
        db.query(User)
        .filter(User.family_id == family_with_children.id, User.role == "child")
        .all()
    )
    result = await handle_get_literacy_weekly_data(
        db,
        family_id=family_with_children.id,
        arguments={"child_id": str(children[0].id)},
    )
    assert "week_start" in result
    assert "chores_total" in result
    assert "coin_earned" in result
    assert "scenario_completed" in result
    assert "badges_earned" in result
    assert "trend" in result  # vs previous week


@pytest.mark.asyncio
async def test_get_literacy_weekly_data_trend_comparison(db, family_with_children):
    """Trend section compares current week vs previous week."""
    children = (
        db.query(User)
        .filter(User.family_id == family_with_children.id, User.role == "child")
        .all()
    )
    result = await handle_get_literacy_weekly_data(
        db,
        family_id=family_with_children.id,
        arguments={"child_id": str(children[0].id)},
    )
    trend = result["trend"]
    assert "chores_delta" in trend
    assert "coins_delta" in trend
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd server && uv run pytest tests/backend/routers/test_mcp_internal_literacy.py -v`
Expected: FAIL — `ImportError: cannot import name 'handle_get_child_literacy_profile'`

- [ ] **Step 3: Implement handler functions**

Find where existing MCP tool handlers are implemented (likely `mcp_internal.py` or a `mcp_tool_handlers.py` service). Add:

```python
async def handle_get_child_literacy_profile(
    db: Session, *, family_id: int, arguments: dict
) -> dict:
    """MCP handler: return child literacy profiles for the family."""
    from apps.backend.app.services.literacy_report import _get_age_group, _sunday_of
    from packages.db.models.literacy_badge import LiteracyBadge, LiteracyBadgeDefinition
    from packages.db.models.literacy_scenario import LiteracyScenario

    query = db.query(User).filter(
        User.family_id == family_id,
        User.role == "child",
        User.is_active.is_(True),
    )
    child_id_arg = arguments.get("child_id")
    if child_id_arg:
        query = query.filter(User.id == int(child_id_arg))
    children = query.all()

    result_children = []
    for child in children:
        # Current badges (not superseded)
        badges = (
            db.query(LiteracyBadgeDefinition)
            .join(LiteracyBadge, LiteracyBadge.definition_id == LiteracyBadgeDefinition.id)
            .filter(
                LiteracyBadge.child_id == child.id,
                LiteracyBadge.superseded_at.is_(None),
            )
            .all()
        )
        # Total scenarios completed
        scenario_count = (
            db.query(func.count(LiteracyScenario.id))
            .filter(
                LiteracyScenario.child_id == child.id,
                LiteracyScenario.completed_at.is_not(None),
            )
            .scalar()
        ) or 0

        # Latest report
        latest_report = (
            db.query(LiteracyWeeklyReport)
            .filter(LiteracyWeeklyReport.child_id == child.id)
            .order_by(desc(LiteracyWeeklyReport.week_start))
            .first()
        )

        result_children.append({
            "child_id": str(child.id),
            "display_name": child.display_name,
            "age_group": _get_age_group(child.birthday),
            "current_badges": [
                {"dimension": b.dimension, "level": b.level, "name": b.name}
                for b in badges
            ],
            "total_scenarios_completed": scenario_count,
            "latest_report_week": (
                latest_report.week_start.isoformat() if latest_report else None
            ),
        })

    return {"children": result_children}


async def handle_get_literacy_weekly_data(
    db: Session, *, family_id: int, arguments: dict
) -> dict:
    """MCP handler: return weekly literacy data with trend for a child."""
    from apps.backend.app.services.literacy_report import (
        _aggregate_signals,
        _sunday_of,
    )

    child_id = int(arguments["child_id"])
    week_start_arg = arguments.get("week_start")
    if week_start_arg:
        week_start = date.fromisoformat(week_start_arg)
    else:
        week_start = _sunday_of(date.today())

    # Current week signals
    signals = _aggregate_signals(db, child_id, week_start)

    # Previous week for trend
    prev_week = week_start - timedelta(days=7)
    prev_signals = _aggregate_signals(db, child_id, prev_week)

    return {
        "child_id": str(child_id),
        "week_start": week_start.isoformat(),
        **signals,
        "trend": {
            "chores_delta": signals["chores_approved"] - prev_signals["chores_approved"],
            "coins_delta": signals["coin_earned"] - prev_signals["coin_earned"],
            "scenario_was_completed_prev": prev_signals["scenario_completed"],
        },
    }
```

- [ ] **Step 4: Wire handlers into MCP tool dispatch**

In the MCP tool dispatch code (where `call_tool` resolves tool name → handler), add cases:

```python
if tool_name == "get_child_literacy_profile":
    return await handle_get_child_literacy_profile(db, family_id=family_id, arguments=arguments)
if tool_name == "get_literacy_weekly_data":
    return await handle_get_literacy_weekly_data(db, family_id=family_id, arguments=arguments)
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `cd server && uv run pytest tests/backend/routers/test_mcp_internal_literacy.py -v`
Expected: PASS

- [ ] **Step 6: Run full backend test suite to verify no regressions**

Run: `cd server && uv run pytest tests/backend/ -v --timeout=60`
Expected: All pass

- [ ] **Step 7: Commit**

```bash
git add server/apps/backend/app/routers/mcp_internal.py server/tests/backend/routers/test_mcp_internal_literacy.py
# Also add the handler file if separate
git commit -m "feat(mcp): implement literacy data tool handlers with trend comparison"
```

---

### Task 3: DB Migration — Add `thread_id` to LiteracyWeeklyReport

**Files:**
- Modify: `server/packages/db/models/literacy_report.py`
- Create: `server/apps/backend/alembic/versions/<auto>.py`

**Interfaces:**
- Consumes: existing `LiteracyWeeklyReport` model
- Produces: `thread_id` nullable column on `literacy_weekly_reports` table
- Required by: Task 6 (report service stores thread_id)

- [ ] **Step 1: Add `thread_id` column to model**

In `server/packages/db/models/literacy_report.py`, add after the `generated_at` column:

```python
    thread_id: Mapped[str | None] = mapped_column(
        String(64), nullable=True, index=True,
        comment="DeerFlow thread ID for the dedicated chat session",
    )
```

- [ ] **Step 2: Generate alembic migration**

```bash
cd server/apps/backend && uv run alembic revision --autogenerate -m "add thread_id to literacy_weekly_reports"
```

Verify the generated migration adds a nullable column with index.

- [ ] **Step 3: Apply migration to verify**

```bash
cd server/apps/backend && uv run alembic upgrade head
```

Expected: Success, no errors

- [ ] **Step 4: Commit**

```bash
git add server/packages/db/models/literacy_report.py server/apps/backend/alembic/versions/<new>.py
git commit -m "feat(literacy): add thread_id column to literacy_weekly_reports"
```

---

### Task 4: Agent SKILL.md — Create Literacy Weekly Report Skill

**Files:**
- Create: `server/apps/agent/skills/builtin/public/literacy-weekly-report/SKILL.md`

**Interfaces:**
- Consumes: MCP tools `get_child_literacy_profile`, `get_literacy_weekly_data`
- Produces: Skill definition loaded by DeerFlow harness

- [ ] **Step 1: Create SKILL.md**

Create `server/apps/agent/skills/builtin/public/literacy-weekly-report/SKILL.md`:

```markdown
---
name: literacy-weekly-report
description: |
  儿童财商启蒙周报（专属智能体）。为家长生成指定孩子的周度财商启蒙报告，
  包含本周数据、与上周趋势对比、个性化建议。支持后续追问。

trigger_phrases:
  - /literacy-weekly-report
  - 周报
  - 学习报告

# MCP tools — use base names (sync_tool_patch.py tool_name_prefix=False).
allowed-tools:
  - get_child_literacy_profile
  - get_literacy_weekly_data

thinking: true
max_tokens: 8000
---

## 角色

你是一位温暖而专业的家庭财商启蒙教练。你的任务是为家长撰写孩子的周度学习报告，并在报告生成后回答家长的追问。

## 执行流程

**第 1 步：获取孩子档案**
- 调用 `get_child_literacy_profile` 获取孩子的昵称、年龄段、当前徽章等级。

**第 2 步：获取本周数据**
- 调用 `get_literacy_weekly_data` 获取本周的家务完成率、星星币收支、场景完成情况、徽章变化。
- 注意响应中的 `trend` 字段，它包含与上周的对比数据。

**第 3 步：生成周报**

按以下结构输出报告（中文，语气温和鼓励）：

### 📊 本周概览
用 1-2 句话总结孩子本周的整体表现。

### 🏠 家务与习惯
- 家务完成数 / 总数（完成率）
- 与上周对比趋势（↑/↓/→）

### 💰 星星币收支
- 本周赚取 / 花费
- 当前余额趋势

### 🎓 启蒙场景
- 本周是否完成启蒙场景
- 场景主题简述（如有数据）

### 🏅 徽章成就
- 本周获得的新徽章（如有）
- 当前持有的徽章概览

### 💡 本周建议
基于数据给出 2-3 条具体、可执行的建议：
- 哪些维度表现好，鼓励继续保持
- 哪些维度可以加强，给出具体行动方案
- 建议应基于年龄段（5-7岁/8-10岁/11+）调整语气和深度

## 追问模式

报告生成后，家长可能会追问。常见追问类型：
- "哪个方面最需要加强？" → 基于趋势数据回答
- "和上个月比怎么样？" → 调用 get_literacy_weekly_data 获取历史周数据对比
- "建议用什么方式鼓励他？" → 结合年龄段给出教育建议
- "徽章怎么获得的？" → 基于徽章维度解释标准

追问时，可以继续调用 MCP 工具获取更详细的数据。

## 最重要的规则

1. **语气温暖鼓励**，不用"差"/"失败"等负面词，用"可以提升"/"还有进步空间"替代
2. **数据驱动**，每个观点都要有数据支撑，不要空泛评价
3. **建议可执行**，具体到"每天花 5 分钟一起数硬币"而非"加强财商教育"
4. **年龄适配**，低龄（5-7）用游戏化语言，高龄（11+）可以用更理性的分析
5. **如果数据不足**（如本周无任何记录），如实告知，不要编造数据
```

- [ ] **Step 2: Verify skill is discovered by harness**

Run: `cd server && uv run python -c "from apps.agent.services.capability_registry import CapabilityRegistry; r = CapabilityRegistry(); skills = r.list_skills(); print([s['name'] for s in skills if 'literacy' in s['name']])"`

Expected: `['literacy-weekly-report']` appears in the list

- [ ] **Step 3: Commit**

```bash
git add server/apps/agent/skills/builtin/public/literacy-weekly-report/SKILL.md
git commit -m "feat(agent): add literacy-weekly-report skill with prompt and MCP tools"
```

---

### Task 5: Agent Worker — Add Dispatch Branch + Runner

**Files:**
- Modify: `server/apps/agent/services/runtime/worker.py:290-388` (dispatch) + append runner
- Modify: `server/apps/agent/services/runtime/sse_gateway.py:195-233` (R1 gate + allowlist)
- Modify: `server/apps/agent/app/routers/gateway.py:461-525` (trigger endpoint)
- Test: `server/tests/agent/unit/test_worker_literacy_report.py`

**Interfaces:**
- Consumes: SKILL.md (Task 4), sse_gateway allowlist
- Produces: `_run_literacy_weekly_report_agent` runner, `POST /internal/gateway/runs/literacy-weekly-report/{thread_id}` trigger
- Depends on: Task 4

- [ ] **Step 1: Add R1 gate block in sse_gateway.py**

In `server/apps/agent/services/runtime/sse_gateway.py`, after the `dashboard-narrative` block (line ~224):

```python
    if not internal and app == "literacy-weekly-report":
        raise _app_rejected_error(
            status_code=409,
            app=app,
            reason="启蒙周报须经由后端触发端点，请勿直连 /runs/stream",
        )
```

And add to the allowlist check (line ~225-232):

```python
    if (
        app != "numina"
        and app != "asset-report"
        and app != "import-parse"
        and app != "finance-coach"
        and app != "wish-advice"
        and app != "dashboard-narrative"
        and app != "literacy-weekly-report"
    ):
```

- [ ] **Step 2: Add dispatch branch in worker.py**

In `server/apps/agent/services/runtime/worker.py`, in the `run_agent` function's dispatch section (after the `dashboard-narrative` branch ~line 374):

```python
        if app == "literacy-weekly-report":
            await _run_literacy_weekly_report_agent(
                bridge=bridge,
                run_manager=run_manager,
                record=record,
                family_id=family_id,
                user_id=user_id,
                thread_id=thread_id,
                graph_input=graph_input,
                config=config,
            )
            return
```

- [ ] **Step 3: Implement `_run_literacy_weekly_report_agent` runner**

Append to `worker.py` (mirrors `_run_finance_coach_agent` pattern):

```python
_SYNTHETIC_LITERACY_REPORT_TRIGGER = "/literacy-weekly-report"

_RESULT_EVENT_TYPE = "literacy_weekly_report.result"


def _extract_literacy_report_context(graph_input: dict | None) -> str | None:
    """Extract the backend-injected report context from graph_input messages."""
    if not graph_input:
        return None
    messages = graph_input.get("messages", [])
    if not messages:
        return None
    last = messages[-1]
    content = last.get("content", "")
    if isinstance(content, str) and content.startswith("{"):
        return content
    return None


async def _run_literacy_weekly_report_agent(
    *,
    bridge: StreamBridge,
    run_manager: RunManager,
    record: RunRecord,
    family_id: str,
    user_id: str | None,
    thread_id: str,
    graph_input: dict | None,
    config: dict[str, Any],
) -> None:
    """literacy-weekly-report dispatch branch.

    Runs a single stream_run agent with skill_name='literacy-weekly-report'.
    The backend injects child_id + week context as the user message.
    The agent calls MCP tools to fetch literacy data and generates a weekly report.
    Emits a ``literacy_weekly_report.result`` custom event before the end frame.
    """
    run_id = record.run_id
    t_start = time.monotonic()
    success = False
    error_type: str | None = None

    try:
        await run_manager.set_status(run_id, RunStatus.running)
        await bridge.publish(run_id, "metadata", {"run_id": run_id, "thread_id": thread_id})

        client = BackendClient(family_id=family_id)
        ai_config = await client.get_family_ai_config()
        providers = ai_config.get("providers", [])
        if not providers:
            raise RuntimeError("未配置 AI 供应商")
        selected_provider = next(
            (p for p in providers if p.get("is_active")), providers[0]
        )

        mcp_servers = await _resolve_numina_mcp_servers(
            client, family_id, user_id, "[_run_literacy_weekly_report_agent]"
        )

        from apps.agent.services.agent_registry import get_agent_registry
        agent_meta = await get_agent_registry().get("literacy-weekly-report", family_id)
        memory_enabled = (
            bool(agent_meta.get("memory_enabled", True)) if agent_meta else True
        )

        adapter = create_family_adapter(
            family_id,
            selected_provider,
            timeout_seconds=120,
            subagent_enabled=False,
            plan_mode=False,
            mcp_servers=mcp_servers,
            agent_name="literacy-weekly-report",
            memory_enabled=memory_enabled,
        )

        # User message = backend-injected context or synthetic trigger
        user_message = (
            _extract_literacy_report_context(graph_input)
            or _SYNTHETIC_LITERACY_REPORT_TRIGGER
        )

        # PII redaction (Key Invariant #1)
        redacted_content = pii_redactor.redact_text(user_message)
        user_msg_dict = {"role": "user", "content": redacted_content}

        set_active_skill("literacy-weekly-report")

        async for frame in adapter.typed_stream_dispatch(
            thread_id=thread_id,
            user_message=user_msg_dict,
            config=config or {},
        ):
            await bridge.publish(run_id, frame.get("type", "custom"), frame)

        success = True
        completion_status = "ok"

    except Exception as exc:
        error_type = type(exc).__name__
        logger.error(
            "[_run_literacy_weekly_report_agent] failed run=%s err=%s",
            run_id, error_type,
        )
        await bridge.publish(
            run_id, "error",
            {"message": "周报生成失败", "name": error_type},
        )
    finally:
        set_active_skill(None)
        duration_ms = (time.monotonic() - t_start) * 1000
        audit_logger.log_call(
            AuditEntry(
                family_id=family_id,
                user_id=user_id or "",
                skill="literacy-weekly-report",
                duration_ms=duration_ms,
                success=success,
                error_type=error_type,
            )
        )

        await bridge.publish_end(run_id)
        asyncio.create_task(bridge.cleanup(run_id, delay=60))
        asyncio.create_task(schedule_run_cleanup(run_manager, run_id, delay=300))
```

- [ ] **Step 4: Add gateway trigger endpoint**

In `server/apps/agent/app/routers/gateway.py`, add request model and endpoint (mirrors `DashboardNarrativeRunRequest`):

```python
class LiteracyWeeklyReportRunRequest(BaseModel):
    """Request body for internal literacy-weekly-report run trigger."""

    family_id: str
    user_id: str | None = None
    input: dict[str, Any] | None = None
    on_disconnect: str = "cancel"


@router.post("/runs/literacy-weekly-report/{thread_id}")
async def trigger_literacy_weekly_report_run(
    thread_id: str,
    body: LiteracyWeeklyReportRunRequest,
    request: Request,
    x_agent_token: str = Header(..., alias="X-Agent-Token"),
) -> StreamingResponse:
    """Trigger a literacy-weekly-report stream_run from the backend."""
    _verify_token(x_agent_token)
    _validate_path_segment(thread_id, "thread_id")

    run_body = SimpleNamespace(
        assistant_id=None,
        input=body.input,
        config=None,
        metadata={"app": "literacy-weekly-report"},
        on_disconnect=body.on_disconnect,
        multitask_strategy="reject",
    )

    record = await start_run(
        run_body, thread_id, request, body.family_id, body.user_id, internal=True,
    )
    run_mgr = get_run_manager(request)

    async def sse_generator():
        async for frame in sse_consumer(
            get_stream_bridge(request), record, request, run_mgr
        ):
            yield frame

    return StreamingResponse(
        sse_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
```

- [ ] **Step 5: Write test for worker dispatch**

Create `server/tests/agent/unit/test_worker_literacy_report.py`:

```python
"""Test literacy-weekly-report worker dispatch branch."""
import pytest
from unittest.mock import AsyncMock, patch


@pytest.mark.asyncio
async def test_worker_dispatches_literacy_weekly_report():
    """worker.run_agent routes app='literacy-weekly-report' to the correct runner."""
    from apps.agent.services.runtime.worker import run_agent

    mock_bridge = AsyncMock()
    mock_run_manager = AsyncMock()
    mock_record = AsyncMock()
    mock_record.metadata = {"app": "literacy-weekly-report"}
    mock_record.run_id = "test-run-id"

    with patch(
        "apps.agent.services.runtime.worker._run_literacy_weekly_report_agent",
        new_callable=AsyncMock,
    ) as mock_runner:
        await run_agent(
            bridge=mock_bridge,
            run_manager=mock_run_manager,
            record=mock_record,
            family_id="123",
            user_id="456",
            thread_id="thread-abc",
            graph_input=None,
            config={},
        )
        mock_runner.assert_called_once()


@pytest.mark.asyncio
async def test_sse_gateway_blocks_frontend_direct_dispatch():
    """Frontend direct dispatch of literacy-weekly-report is rejected with 409."""
    from apps.agent.services.runtime.sse_gateway import start_run

    body = type("Body", (), {
        "metadata": {"app": "literacy-weekly-report"},
        "assistant_id": None,
        "on_disconnect": "cancel",
    })()

    with pytest.raises(Exception) as exc_info:
        await start_run(
            body, "thread-id", AsyncMock(), "123", "456", internal=False,
        )
    assert exc_info.value.status_code == 409
```

- [ ] **Step 6: Run agent tests**

Run: `cd server && uv run pytest tests/agent/unit/test_worker_literacy_report.py -v`
Expected: PASS

- [ ] **Step 7: Commit**

```bash
git add server/apps/agent/services/runtime/worker.py server/apps/agent/services/runtime/sse_gateway.py server/apps/agent/app/routers/gateway.py server/tests/agent/unit/test_worker_literacy_report.py
git commit -m "feat(agent): add literacy-weekly-report worker runner, gateway trigger, R1 gate"
```

---

### Task 6: Backend Report Service — Orchestration + Caching

**Files:**
- Create: `server/apps/backend/app/services/literacy_report_service.py`
- Test: `server/tests/backend/services/test_literacy_report_service.py`

**Interfaces:**
- Consumes: `AgentClient`, `LiteracyWeeklyReport` model (with `thread_id`), `finance_coach_cache.is_cache_fresh`
- Produces: `generate_literacy_report()`, `get_report_status()`, `get_or_create_thread()`
- Depends on: Task 3 (thread_id column), Task 5 (agent gateway)

- [ ] **Step 1: Write failing tests**

Create `server/tests/backend/services/test_literacy_report_service.py`:

```python
"""Tests for literacy_report_service."""
import pytest
from datetime import date, timedelta
from unittest.mock import AsyncMock, patch

from apps.backend.app.services.literacy_report_service import (
    generate_literacy_report,
    get_report_status,
    build_report_context,
)


def test_build_report_context_includes_child_data(db, family_with_children):
    """Context includes child profile and weekly signals."""
    child = (
        db.query(User)
        .filter(User.family_id == family_with_children.id, User.role == "child")
        .first()
    )
    context = build_report_context(db, child_id=child.id, week_start=date.today())
    assert "child_id" in context
    assert "display_name" in context
    assert "age_group" in context
    assert "signals" in context
    assert "week_start" in context


def test_get_report_status_no_report(db, family_with_children):
    """Returns status='none' when no report exists."""
    child = (
        db.query(User)
        .filter(User.family_id == family_with_children.id, User.role == "child")
        .first()
    )
    status = get_report_status(db, family_id=family_with_children.id, child_id=child.id)
    assert status["status"] == "none"
    assert status["thread_id"] is None


def test_get_report_status_with_report(db, family_with_children):
    """Returns status='ready' with thread_id when report exists."""
    from packages.db.models.literacy_report import LiteracyWeeklyReport
    from apps.backend.app.services.literacy_report import _sunday_of
    import json

    child = (
        db.query(User)
        .filter(User.family_id == family_with_children.id, User.role == "child")
        .first()
    )
    today = _sunday_of(date.today())
    report = LiteracyWeeklyReport(
        child_id=child.id,
        week_start=today,
        report_json=json.dumps({"signals": {}}),
        narrative="本周表现不错",
        thread_id="thread-abc-123",
    )
    db.add(report)
    db.commit()

    status = get_report_status(db, family_id=family_with_children.id, child_id=child.id)
    assert status["status"] == "ready"
    assert status["thread_id"] == "thread-abc-123"
    assert status["week_start"] == today.isoformat()


@pytest.mark.asyncio
async def test_generate_literacy_report_idempotent(db, family_with_children):
    """Calling generate twice returns the same report without regenerating."""
    from apps.backend.app.services.literacy_report import _sunday_of

    child = (
        db.query(User)
        .filter(User.family_id == family_with_children.id, User.role == "child")
        .first()
    )
    today = _sunday_of(date.today())

    with patch(
        "apps.backend.app.services.literacy_report_service._stream_report_sse",
        new_callable=AsyncMock,
    ):
        result1 = await generate_literacy_report(
            db, family_id=family_with_children.id, child_id=child.id, week_start=today,
        )
        result2 = await generate_literacy_report(
            db, family_id=family_with_children.id, child_id=child.id, week_start=today,
        )
    assert result1.id == result2.id
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd server && uv run pytest tests/backend/services/test_literacy_report_service.py -v`
Expected: FAIL — ImportError

- [ ] **Step 3: Implement the service**

Create `server/apps/backend/app/services/literacy_report_service.py`:

```python
"""Literacy weekly report orchestration service.

Mirrors dashboard_narrative.py pattern: cache check → threshold check →
build context → stream via agent → persist result.

Uses LiteracyWeeklyReport table (extended with thread_id) for persistence.
The thread_id links to the dedicated chat session for follow-up questions.
"""
import json
import logging
import uuid
from datetime import date, timedelta
from typing import Any

from sqlalchemy import desc
from sqlalchemy.orm import Session

from packages.db.models.literacy_report import LiteracyWeeklyReport

logger = logging.getLogger(__name__)

SKILL_ID = "literacy-weekly-report"


def build_report_context(db: Session, *, child_id: int, week_start: date) -> dict[str, Any]:
    """Build structured context for the LLM prompt."""
    from apps.backend.app.services.literacy_report import (
        _aggregate_signals,
        _get_age_group,
        _sunday_of,
    )
    from packages.db.models.user import User

    child = db.query(User).filter(User.id == child_id).one()
    signals = _aggregate_signals(db, child_id, week_start)

    # Previous week for trend
    prev_week = week_start - timedelta(days=7)
    prev_signals = _aggregate_signals(db, child_id, prev_week)

    return {
        "child_id": str(child_id),
        "display_name": child.display_name,
        "age_group": _get_age_group(child.birthday, reference=week_start),
        "week_start": week_start.isoformat(),
        "signals": signals,
        "trend": {
            "chores_delta": signals["chores_approved"] - prev_signals["chores_approved"],
            "coins_delta": signals["coin_earned"] - prev_signals["coin_earned"],
        },
    }


def get_report_status(
    db: Session, *, family_id: int, child_id: int
) -> dict[str, Any]:
    """Return the current report status for BabyPage entry display.

    Returns dict with: status ('none'|'ready'|'generating'), thread_id,
    week_start, narrative (truncated), generated_at.
    """
    from apps.backend.app.services.literacy_report import _sunday_of

    current_week = _sunday_of(date.today())

    report = (
        db.query(LiteracyWeeklyReport)
        .filter(
            LiteracyWeeklyReport.child_id == child_id,
            LiteracyWeeklyReport.week_start == current_week,
        )
        .first()
    )

    if report is None:
        return {
            "status": "none",
            "thread_id": None,
            "week_start": current_week.isoformat(),
            "narrative": None,
            "generated_at": None,
        }

    return {
        "status": "ready",
        "thread_id": report.thread_id,
        "week_start": report.week_start.isoformat(),
        "narrative": report.narrative[:100] if report.narrative else None,
        "generated_at": (
            report.generated_at.isoformat() if report.generated_at else None
        ),
    }


def _make_thread_id(family_id: str, child_id: int) -> str:
    """Generate a unique thread_id for the report chat session."""
    return f"literacy-report-{family_id}-{child_id}-{uuid.uuid4().hex[:8]}"


async def _stream_report_sse(
    *, family_id: str, user_id: str, context: dict, thread_id: str,
) -> bytes:
    """Proxy the agent's literacy-weekly-report SSE stream.

    Calls the agent gateway and collects all SSE bytes.
    Returns the collected bytes for result parsing.
    """
    from apps.backend.app.services.agent_client import AgentClient

    agent_client = AgentClient(family_id, user_id, timeout=120.0)
    agent_url = f"/internal/gateway/runs/literacy-weekly-report/{thread_id}"

    collected = b""
    async with agent_client.stream(
        "POST",
        agent_url,
        json={
            "family_id": str(family_id),
            "user_id": str(user_id),
            "input": {
                "messages": [
                    {"role": "user", "content": json.dumps(context, ensure_ascii=False)}
                ]
            },
        },
    ) as resp:
        if resp.status_code != 200:
            body = await resp.aread()
            logger.warning(
                "[literacy-report] agent non-200: status=%s body=%s",
                resp.status_code, body[:200],
            )
            return b""
        async for line in resp.aiter_lines():
            collected += (line + "\n").encode()
    return collected


def _persist_report_result(
    db: Session, *, child_id: int, week_start: date, thread_id: str, collected_sse: bytes,
) -> LiteracyWeeklyReport | None:
    """Extract narrative from SSE result and persist to LiteracyWeeklyReport."""
    text = collected_sse.decode("utf-8", errors="replace")

    # Parse the literacy_weekly_report.result custom event
    narrative = None
    for block in text.split("\n\n"):
        if "literacy_weekly_report.result" not in block:
            continue
        for line in block.split("\n"):
            if line.startswith("data: "):
                try:
                    data = json.loads(line[len("data: "):])
                    if data.get("type") == "literacy_weekly_report.result":
                        narrative = data.get("payload", {}).get("narrative")
                except json.JSONDecodeError:
                    continue

    if not narrative:
        return None

    # Check for existing report (idempotency)
    existing = (
        db.query(LiteracyWeeklyReport)
        .filter(
            LiteracyWeeklyReport.child_id == child_id,
            LiteracyWeeklyReport.week_start == week_start,
        )
        .first()
    )
    if existing:
        existing.narrative = narrative
        existing.thread_id = thread_id
        db.flush()
        return existing

    report = LiteracyWeeklyReport(
        child_id=child_id,
        week_start=week_start,
        report_json=json.dumps({}, ensure_ascii=False),
        narrative=narrative,
        thread_id=thread_id,
    )
    db.add(report)
    db.flush()
    return report


async def generate_literacy_report(
    db: Session,
    *,
    family_id: int,
    child_id: int,
    week_start: date,
    user_id: str,
) -> LiteracyWeeklyReport | None:
    """Generate a weekly literacy report (or return existing).

    Idempotent: if a report already exists for this child + week, return it.
    Otherwise: build context → stream via agent → persist result.
    """
    # Idempotency check
    existing = (
        db.query(LiteracyWeeklyReport)
        .filter(
            LiteracyWeeklyReport.child_id == child_id,
            LiteracyWeeklyReport.week_start == week_start,
        )
        .first()
    )
    if existing is not None:
        return existing

    # Build context
    context = build_report_context(db, child_id=child_id, week_start=week_start)

    # Create thread
    thread_id = _make_thread_id(str(family_id), child_id)

    # Stream via agent
    try:
        collected = await _stream_report_sse(
            family_id=str(family_id),
            user_id=user_id,
            context=context,
            thread_id=thread_id,
        )
    except Exception:
        logger.warning("[literacy-report] agent stream failed", exc_info=True)
        return None

    if not collected:
        return None

    # Persist result (uses request-scoped db)
    report = _persist_report_result(
        db,
        child_id=child_id,
        week_start=week_start,
        thread_id=thread_id,
        collected_sse=collected,
    )
    return report
```

- [ ] **Step 4: Run tests**

Run: `cd server && uv run pytest tests/backend/services/test_literacy_report_service.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add server/apps/backend/app/services/literacy_report_service.py server/tests/backend/services/test_literacy_report_service.py
git commit -m "feat(literacy): add report orchestration service with caching and agent dispatch"
```

---

### Task 7: Backend Router — Trigger + Status Endpoints

**Files:**
- Create: `server/apps/backend/app/routers/ai_literacy_report.py`
- Modify: `server/apps/backend/app/routers/literacy_parent.py` (add status endpoint)
- Modify: `server/apps/backend/app/main.py` (register new router)
- Test: `server/tests/backend/routers/test_ai_literacy_report.py`

**Interfaces:**
- Consumes: `literacy_report_service` (Task 6)
- Produces: `POST /ai/literacy-report/generate`, `GET /literacy-reports/status`
- Depends on: Task 6

- [ ] **Step 1: Create trigger router**

Create `server/apps/backend/app/routers/ai_literacy_report.py`:

```python
"""Literacy weekly report trigger endpoint.

POST /api/v1/ai/literacy-report/generate?child_id=...&force=false
    Cache check → if fresh, return JSON 200.
    Otherwise → stream via agent → persist → return result.

Mirrors ai_finance_coach.py pattern.
"""
import logging

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from apps.backend.app.auth.ai_deps import require_ai_enabled
from apps.backend.app.auth.deps import require_adult
from apps.backend.app.database import get_db
from apps.backend.app.models.user import User
from apps.backend.app.services.literacy_report import _sunday_of
from apps.backend.app.services.literacy_report_service import (
    generate_literacy_report,
    get_report_status,
)
from datetime import date

router = APIRouter(prefix="/ai/literacy-report", tags=["ai-literacy-report"])
logger = logging.getLogger(__name__)


@router.post("/generate")
async def trigger_generate(
    child_id: str = Query(..., description="Child user ID"),
    force: bool = Query(False),
    current_user: User = Depends(require_adult),
    _ai: None = Depends(require_ai_enabled),
    db: Session = Depends(get_db),
):
    """Generate (or return cached) weekly literacy report for a child.

    If the report is already fresh, returns JSON with status + thread_id.
    Otherwise triggers agent generation and returns the result.
    """
    from apps.backend.app.errors import AppError, ErrorCode

    try:
        cid = int(child_id)
    except (ValueError, TypeError):
        raise AppError(ErrorCode.VALIDATION_ERROR, details=f"无效的 child_id: {child_id}") from None

    # Validate child belongs to family
    child = (
        db.query(User)
        .filter(User.id == cid, User.family_id == current_user.family_id, User.role == "child")
        .first()
    )
    if child is None:
        raise AppError(ErrorCode.AUTH_CHILD_NOT_FOUND)

    week_start = _sunday_of(date.today())

    # Cache check (unless force)
    if not force:
        status = get_report_status(db, family_id=current_user.family_id, child_id=cid)
        if status["status"] == "ready":
            return status

    # Generate
    report = await generate_literacy_report(
        db,
        family_id=current_user.family_id,
        child_id=cid,
        week_start=week_start,
        user_id=str(current_user.id),
    )
    db.commit()

    if report is None:
        return {"status": "error", "thread_id": None, "week_start": week_start.isoformat(),
                "narrative": None, "generated_at": None}

    return {
        "status": "ready",
        "thread_id": report.thread_id,
        "week_start": report.week_start.isoformat(),
        "narrative": report.narrative[:100] if report.narrative else None,
        "generated_at": report.generated_at.isoformat() if report.generated_at else None,
    }
```

- [ ] **Step 2: Add status endpoint to literacy_parent.py**

In `server/apps/backend/app/routers/literacy_parent.py`, add:

```python
@router.get("/status")
def get_child_report_status(
    child_id: str = Query(..., description="Child user ID"),
    current_user: User = Depends(require_adult),
    db: Session = Depends(get_db),
):
    """Return the current week's report status for BabyPage entry display."""
    from apps.backend.app.errors import AppError, ErrorCode
    from apps.backend.app.services.literacy_report_service import get_report_status

    try:
        cid = int(child_id)
    except (ValueError, TypeError):
        raise AppError(ErrorCode.VALIDATION_ERROR, details=f"无效的 child_id: {child_id}") from None
    _validate_child_in_family(db, cid, current_user.family_id)

    return get_report_status(db, family_id=current_user.family_id, child_id=cid)
```

- [ ] **Step 3: Register router in main.py**

In `server/apps/backend/app/main.py`, add the router import and registration:

```python
from apps.backend.app.routers import ai_literacy_report
app.include_router(ai_literacy_report.router, prefix="/api/v1")
```

- [ ] **Step 4: Write router tests**

Create `server/tests/backend/routers/test_ai_literacy_report.py`:

```python
"""Tests for ai_literacy_report trigger endpoint."""
import pytest
from unittest.mock import AsyncMock, patch


def test_generate_requires_ai_enabled(client, auth_headers, family_with_children):
    """Endpoint returns 403 when AI is not enabled."""
    # Remove AI providers to disable AI
    response = client.post(
        "/api/v1/ai/literacy-report/generate?child_id=123",
        headers=auth_headers,
    )
    # Should fail with AI not enabled or child not found
    assert response.status_code in (403, 404)


def test_generate_returns_status_for_existing_report(
    client, auth_headers, db, family_with_children
):
    """Returns cached status when report already exists."""
    from packages.db.models.literacy_report import LiteracyWeeklyReport
    from apps.backend.app.services.literacy_report import _sunday_of
    from packages.db.models.user import User
    import json

    child = db.query(User).filter(
        User.family_id == family_with_children.id, User.role == "child"
    ).first()
    today = _sunday_of(date.today())
    report = LiteracyWeeklyReport(
        child_id=child.id, week_start=today,
        report_json=json.dumps({}), narrative="测试报告",
        thread_id="thread-test-123",
    )
    db.add(report)
    db.commit()

    response = client.get(
        f"/api/v1/literacy-reports/status?child_id={child.id}",
        headers=auth_headers,
    )
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ready"
    assert data["thread_id"] == "thread-test-123"


def test_status_endpoint_returns_none_when_no_report(
    client, auth_headers, db, family_with_children
):
    """Returns status='none' when no report exists yet."""
    from packages.db.models.user import User

    child = db.query(User).filter(
        User.family_id == family_with_children.id, User.role == "child"
    ).first()

    response = client.get(
        f"/api/v1/literacy-reports/status?child_id={child.id}",
        headers=auth_headers,
    )
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "none"
    assert data["thread_id"] is None
```

- [ ] **Step 5: Run tests**

Run: `cd server && uv run pytest tests/backend/routers/test_ai_literacy_report.py tests/backend/routers/test_literacy_report_status.py -v`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add server/apps/backend/app/routers/ai_literacy_report.py server/apps/backend/app/routers/literacy_parent.py server/apps/backend/app/main.py server/tests/backend/routers/test_ai_literacy_report.py
git commit -m "feat(literacy): add report trigger endpoint and BabyPage status API"
```

---

### Task 8: RESERVED_NAMES + Config Registry

**Files:**
- Modify: `server/apps/backend/app/routers/ai_skills.py:50` (RESERVED_NAMES)
- Modify: `server/apps/backend/app/services/config_registry.py` (new settings)
- Test: `server/tests/backend/test_config_registry.py`

**Interfaces:**
- Consumes: existing patterns
- Produces: skill ID protection + configurable schedule settings

- [ ] **Step 1: Add to RESERVED_NAMES**

In `server/apps/backend/app/routers/ai_skills.py`, update line 50:

```python
RESERVED_NAMES = ["chat", "asset-report", "import-parse", "finance-coach", "wish-advice", "dashboard-narrative", "literacy-weekly-report"]
```

- [ ] **Step 2: Add config settings to config_registry.py**

In `server/apps/backend/app/services/config_registry.py`, add to `FAMILY_SETTING_DEFINITIONS`:

```python
    # --- Literacy weekly report ---
    "literacy_report_day": SettingDefinition(
        type="int", default=0, min=0, max=6, step=1,
        label_key="familyConfig.literacyReportDay",
        description_key="familyConfig.literacyReportDayDesc",
    ),
    "literacy_report_hour": SettingDefinition(
        type="int", default=8, min=0, max=23, step=1,
        label_key="familyConfig.literacyReportHour",
        description_key="familyConfig.literacyReportHourDesc",
    ),
    "ai_cache_ttl_literacy_weekly_report": SettingDefinition(
        type="int", default=10080, min=1440, max=20160, step=1440,
        label_key="familyConfig.aiCacheTtlLiteracyReport",
        description_key="familyConfig.aiCacheTtlLiteracyReportDesc",
    ),
```

Day uses 0=Sunday convention (matching `_sunday_of`). TTL default is 7 days (10080 min).

- [ ] **Step 3: Write test**

In `server/tests/backend/test_config_registry.py`:

```python
def test_literacy_report_settings_registered():
    from apps.backend.app.services.config_registry import FAMILY_SETTING_DEFINITIONS
    assert "literacy_report_day" in FAMILY_SETTING_DEFINITIONS
    assert "literacy_report_hour" in FAMILY_SETTING_DEFINITIONS
    assert "ai_cache_ttl_literacy_weekly_report" in FAMILY_SETTING_DEFINITIONS
    # Default: Sunday (0), 8am, 7-day TTL
    assert FAMILY_SETTING_DEFINITIONS["literacy_report_day"].default == 0
    assert FAMILY_SETTING_DEFINITIONS["literacy_report_hour"].default == 8
```

- [ ] **Step 4: Run tests**

Run: `cd server && uv run pytest tests/backend/test_config_registry.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add server/apps/backend/app/routers/ai_skills.py server/apps/backend/app/services/config_registry.py server/tests/backend/test_config_registry.py
git commit -m "feat(literacy): reserve skill ID and add configurable schedule settings"
```

---

### Task 9: Scheduler — Weekly Literacy Report Cron Job

**Files:**
- Modify: `server/apps/agent/app/scheduler.py`
- Test: `server/tests/agent/unit/test_scheduler_literacy.py`

**Interfaces:**
- Consumes: `BackendClient.get_ai_enabled_families()`, config settings via backend HTTP
- Produces: scheduled weekly report generation for all AI-enabled families

- [ ] **Step 1: Write test**

Create `server/tests/agent/unit/test_scheduler_literacy.py`:

```python
"""Test scheduler literacy report job."""
import pytest
from unittest.mock import AsyncMock, patch, MagicMock


@pytest.mark.asyncio
async def test_generate_weekly_literacy_reports_enumerates_families():
    """The scheduler job iterates AI-enabled families and generates reports."""
    from apps.agent.app.scheduler import generate_weekly_literacy_reports

    with patch(
        "apps.agent.app.scheduler._get_ai_enabled_families",
        new_callable=AsyncMock,
        return_value=["111", "222"],
    ), patch(
        "apps.agent.app.scheduler._get_family_children",
        new_callable=AsyncMock,
        return_value=[{"child_id": "333", "display_name": "小宝"}],
    ), patch(
        "apps.agent.app.scheduler._trigger_report_generation",
        new_callable=AsyncMock,
    ) as mock_trigger:
        await generate_weekly_literacy_reports()
    assert mock_trigger.call_count == 2  # 2 families × 1 child each


@pytest.mark.asyncio
async def test_generate_weekly_literacy_reports_handles_failure():
    """One family failure doesn't abort the entire run."""
    from apps.agent.app.scheduler import generate_weekly_literacy_reports

    call_count = 0

    async def flaky_trigger(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            raise RuntimeError("simulated failure")

    with patch(
        "apps.agent.app.scheduler._get_ai_enabled_families",
        new_callable=AsyncMock,
        return_value=["111", "222"],
    ), patch(
        "apps.agent.app.scheduler._get_family_children",
        new_callable=AsyncMock,
        return_value=[{"child_id": "333"}],
    ), patch(
        "apps.agent.app.scheduler._trigger_report_generation",
        side_effect=flaky_trigger,
    ):
        await generate_weekly_literacy_reports()
    assert call_count == 2  # Both families attempted despite first failure
```

- [ ] **Step 2: Implement scheduler job**

In `server/apps/agent/app/scheduler.py`, add the job function and register it:

```python
import random
import asyncio
from datetime import date

logger = logging.getLogger(__name__)


async def _get_ai_enabled_families() -> list[str]:
    """Fetch family IDs that have AI enabled."""
    from apps.agent.core.backend_client import BackendClient
    # Use a system-level call — no specific family
    # The backend endpoint /internal/ai/families?ai_only=true returns eligible families
    try:
        from apps.agent.app.config import settings
        import httpx
        async with httpx.AsyncClient(base_url=settings.BACKEND_BASE_URL) as client:
            resp = await client.get(
                "/api/v1/internal/ai/families",
                params={"ai_only": "true"},
                headers={"X-Agent-Token": settings.AGENT_INTERNAL_TOKEN},
            )
            resp.raise_for_status()
            return resp.json().get("family_ids", [])
    except Exception:
        logger.warning("[scheduler] failed to fetch AI-enabled families", exc_info=True)
        return []


async def _get_family_children(family_id: str) -> list[dict]:
    """Fetch children for a family via backend."""
    try:
        from apps.agent.app.config import settings
        import httpx
        async with httpx.AsyncClient(base_url=settings.BACKEND_BASE_URL) as client:
            resp = await client.get(
                "/api/v1/literacy-reports/children",
                headers={"X-Agent-Token": settings.AGENT_INTERNAL_TOKEN,
                         "X-Family-Id": family_id},
            )
            resp.raise_for_status()
            return resp.json().get("children", [])
    except Exception:
        logger.warning("[scheduler] failed to fetch children for family %s", family_id, exc_info=True)
        return []


async def _trigger_report_generation(family_id: str, child_id: str) -> None:
    """Trigger report generation via backend endpoint."""
    try:
        from apps.agent.app.config import settings
        import httpx
        async with httpx.AsyncClient(base_url=settings.BACKEND_BASE_URL, timeout=120.0) as client:
            resp = await client.post(
                "/api/v1/ai/literacy-report/generate",
                params={"child_id": child_id, "force": "true"},
                headers={"X-Agent-Token": settings.AGENT_INTERNAL_TOKEN,
                         "X-Family-Id": family_id},
            )
            resp.raise_for_status()
    except Exception:
        logger.warning("[scheduler] report generation failed family=%s child=%s", family_id, child_id, exc_info=True)


async def generate_weekly_literacy_reports() -> None:
    """Weekly cron: generate literacy reports for all AI-enabled families."""
    families = await _get_ai_enabled_families()
    logger.info("[scheduler] generating literacy reports for %d families", len(families))

    for family_id in families:
        # Jitter per family (scheduler contract)
        await asyncio.sleep(random.uniform(0, 300))

        try:
            children = await _get_family_children(family_id)
        except Exception:
            logger.warning("[scheduler] failed to get children for family %s", family_id)
            continue

        for child_info in children:
            child_id = child_info.get("child_id")
            if not child_id:
                continue
            # Per-child delay
            await asyncio.sleep(random.uniform(2, 8))
            await _trigger_report_generation(family_id, child_id)

    logger.info("[scheduler] literacy report generation complete")
```

And register in `setup_schedules()`:

```python
def setup_schedules() -> None:
    """注册所有定时任务。"""
    # 每周 literacy 周报（周日上午 8:00，随机偏移在任务内部处理）
    scheduler.add_job(
        generate_weekly_literacy_reports,
        "cron",
        day_of_week="sun",
        hour=8,
        minute=0,
        id="weekly_literacy_report",
    )
    logger.info("定时任务已配置")
```

- [ ] **Step 3: Run tests**

Run: `cd server && uv run pytest tests/agent/unit/test_scheduler_literacy.py -v`
Expected: PASS

- [ ] **Step 4: Commit**

```bash
git add server/apps/agent/app/scheduler.py server/tests/agent/unit/test_scheduler_literacy.py
git commit -m "feat(scheduler): add weekly literacy report cron job with jitter"
```

---

### Task 10: Frontend — API Client + i18n Keys

**Files:**
- Create: `frontend/apps/main/src/api/literacyReport.ts`
- Modify: `frontend/apps/main/src/i18n/locales/zh-CN.ts`
- Modify: `frontend/apps/main/src/i18n/locales/en-US.ts`

**Interfaces:**
- Consumes: backend `GET /literacy-reports/status`, `POST /ai/literacy-report/generate`
- Produces: typed API functions for frontend consumption

- [ ] **Step 1: Create API client**

Create `frontend/apps/main/src/api/literacyReport.ts`:

```typescript
import http from './index'

export interface ReportStatus {
  status: 'none' | 'ready' | 'generating'
  thread_id: string | null
  week_start: string
  narrative: string | null
  generated_at: string | null
}

/** Get the current week's report status for a child (BabyPage entry). */
export function getReportStatus(childId: string) {
  return http.get<ReportStatus>('/literacy-reports/status', {
    params: { child_id: childId },
  })
}

/** Trigger report generation (or return cached). */
export function generateReport(childId: string, force = false) {
  return http.post<ReportStatus>('/ai/literacy-report/generate', null, {
    params: { child_id: childId, force },
  })
}
```

- [ ] **Step 2: Add i18n keys**

In `frontend/apps/main/src/i18n/locales/zh-CN.ts`, add under `baby`:

```typescript
    literacyReportEntry: '启蒙周报',
    literacyReportReady: '本周报告已生成',
    literacyReportNone: '本周报告未生成',
    literacyReportGenerating: '报告生成中…',
    literacyReportDaysUntil: '{days}天后更新',
    literacyReportToday: '今天更新',
```

In `frontend/apps/main/src/i18n/locales/en-US.ts`:

```typescript
    literacyReportEntry: 'Literacy Report',
    literacyReportReady: 'Report ready',
    literacyReportNone: 'No report yet',
    literacyReportGenerating: 'Generating…',
    literacyReportDaysUntil: 'Updates in {days} days',
    literacyReportToday: 'Updates today',
```

- [ ] **Step 3: Run typecheck**

```bash
cd frontend/apps/main && pnpm typecheck
```
Expected: 0 errors

- [ ] **Step 4: Commit**

```bash
git add frontend/apps/main/src/api/literacyReport.ts frontend/apps/main/src/i18n/locales/zh-CN.ts frontend/apps/main/src/i18n/locales/en-US.ts
git commit -m "feat(literacy): add report API client and i18n keys"
```

---

### Task 11: Frontend — BabyPage Entry Cell

**Files:**
- Modify: `frontend/apps/main/src/pages/BabyPage.vue:42-66` (summary-card section)

**Interfaces:**
- Consumes: `getReportStatus` API (Task 10), `aiStore.aiEnabled`, `selectedChildId`
- Produces: `van-cell` entry with status text, click navigates to `/ai/chat?thread_id=<id>`
- Depends on: Task 10

- [ ] **Step 1: Add report status composable**

In BabyPage.vue's `<script setup>`, add:

```typescript
import { getReportStatus, type ReportStatus } from '@/api/literacyReport'
import { useAIStore } from '@/stores/ai'

const aiStore = useAIStore()

// Literacy report status per child
const reportStatusMap = ref<Record<string, ReportStatus>>({})

async function loadReportStatuses() {
  if (!aiStore.aiEnabled || !childMembers.value.length) return
  for (const child of childMembers.value) {
    try {
      const { data } = await getReportStatus(String(child.id))
      reportStatusMap.value[String(child.id)] = data
    } catch {
      // best-effort
    }
  }
}

function reportStatusLabel(childId: string): string {
  const status = reportStatusMap.value[String(childId)]
  if (!status) return t('baby.literacyReportNone')
  switch (status.status) {
    case 'ready': return t('baby.literacyReportReady')
    case 'generating': return t('baby.literacyReportGenerating')
    default: return t('baby.literacyReportNone')
  }
}

function navigateToReport(childId: string) {
  const status = reportStatusMap.value[String(childId)]
  if (status?.thread_id) {
    router.push(`/ai/chat?thread_id=${encodeURIComponent(status.thread_id)}`)
  } else {
    // No cached thread — trigger generation then navigate
    generateReport(String(childId)).then(({ data }) => {
      if (data.thread_id) {
        router.push(`/ai/chat?thread_id=${encodeURIComponent(data.thread_id)}`)
      }
    })
  }
}
```

Also import `generateReport`:

```typescript
import { getReportStatus, generateReport, type ReportStatus } from '@/api/literacyReport'
```

- [ ] **Step 2: Add cell to summary-card template**

In `BabyPage.vue`'s summary-card `van-cell-group`, add after the `choreTemplates` cell (line ~65):

```vue
          <van-cell
            v-if="aiStore.aiEnabled && selectedChildId"
            :title="t('baby.literacyReportEntry')"
            :value="reportStatusLabel(String(selectedChildId))"
            is-link
            @click="navigateToReport(String(selectedChildId))"
          />
```

- [ ] **Step 3: Call loadReportStatuses on data load**

In the `loadData` function (or `onRefresh`), add:

```typescript
await loadReportStatuses()
```

And in `onActivated` (for KeepAlive):

```typescript
void loadReportStatuses()
```

- [ ] **Step 4: Run typecheck + tests**

```bash
cd frontend/apps/main && pnpm typecheck && pnpm test:run
```
Expected: 0 typecheck errors, all tests pass

- [ ] **Step 5: Commit**

```bash
git add frontend/apps/main/src/pages/BabyPage.vue
git commit -m "feat(baby): add literacy weekly report entry cell with AI gate"
```

---

### Task 12: Full Regression + Integration Verification

**Files:** (no new files — verification task)

- [ ] **Step 1: Run backend tests**

```bash
cd server && uv run pytest tests/backend/ -v --timeout=60
```
Expected: All pass

- [ ] **Step 2: Run agent tests**

```bash
cd server && uv run pytest tests/agent/ -v --timeout=60
```
Expected: All pass

- [ ] **Step 3: Run frontend typecheck**

```bash
cd frontend/apps/main && pnpm typecheck
cd frontend/apps/child && pnpm typecheck
```
Expected: 0 errors

- [ ] **Step 4: Run frontend tests**

```bash
cd frontend && pnpm -r test:run
```
Expected: All pass

- [ ] **Step 5: Run ruff lint**

```bash
cd server && uv run ruff check apps/backend/ apps/agent/
```
Expected: 0 errors

- [ ] **Step 6: Verify alembic on fresh DB**

```bash
cd server/apps/backend && rm -f /tmp/test_fresh.db && DATABASE_URL=sqlite+aiosqlite:////tmp/test_fresh.db uv run alembic upgrade head
```
Expected: All migrations apply cleanly, including new `thread_id` column

- [ ] **Step 7: Final commit if any fixes needed**

```bash
git add -A
git commit -m "fix: address regression issues from full verification"
```

---

## Execution Summary

| Task | Description | Est. Time |
|------|-------------|-----------|
| 1 | MCP Tool Registry | 10 min |
| 2 | MCP Tool Handlers | 20 min |
| 3 | DB Migration (thread_id) | 10 min |
| 4 | SKILL.md | 10 min |
| 5 | Agent Worker + Gateway | 30 min |
| 6 | Report Service | 25 min |
| 7 | Trigger + Status Routers | 20 min |
| 8 | RESERVED_NAMES + Config | 10 min |
| 9 | Scheduler Cron | 20 min |
| 10 | Frontend API + i18n | 10 min |
| 11 | BabyPage Entry Cell | 15 min |
| 12 | Full Regression | 15 min |
| **Total** | | **~3 hours** |
