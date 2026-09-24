# Worker + Router Boilerplate Refactor — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Eliminate ~260 lines of duplicated boilerplate by extracting a config-driven generic runner for simple agent apps (#9) and a shared `trigger_and_stream()` helper for SSE lifecycle routers (#10).

**Architecture:** Part A adds a `_SimpleAppConfig` dataclass + `_SIMPLE_APPS` registry + `_run_simple_app()` generic runner to worker.py, replacing 3 near-identical runner functions with config entries and a dict-based dispatch. Part B adds `trigger_and_stream()` to bridge_consumer.py, encapsulating the trigger→heartbeat→lifecycle→stream pattern shared by 3 backend routers. Both parts are independently deployable and tested.

**Tech Stack:** Python 3.12+, FastAPI, asyncio, dataclasses, pytest (asyncio_mode=auto for agent tests), uv workspace

**Spec:** [`docs/superpowers/specs/2026-09-24-worker-router-refactor-design.md`](../specs/2026-09-24-worker-router-refactor-design.md)

## Global Constraints

- **Python 3.12+** — use `str | None` union syntax, `list[str]` generics (no `typing.List`/`typing.Optional`)
- **Import direction** — agent must NOT import from backend; backend must NOT import from agent; shared code lives in `packages/`
- **No trailing slashes** — router decorators use `""` not `"/"` (FastAPI `redirect_slashes=False`)
- **Snowflake IDs as strings** — all ID fields in API responses serialized as strings via `SnowflakeBase`
- **`learning_child.py` is excluded** from the `trigger_and_stream` refactor — it uses a fundamentally different SSE lifecycle
- **Incremental formatting** — format only files touched, not entire modules
- **No speculative code** — don't add abstractions beyond what the spec requires

## Review Focus

1. **`_run_simple_app` must produce identical SSE output to the old runners** — same RunPipeline params, same result event shape, same session title. Verification: dispatch test per app comparing config→RunPipeline kwargs mapping (Task 1, step 6).
2. **`trigger_and_stream` cleanup must be robust** — the spec changes `_hb_task.cancel()` to `await _hb_task` with `contextlib.suppress(CancelledError)`. If the heartbeat task raises an unexpected exception, it must not crash the SSE stream. Verification: test that heartbeat cancellation is clean (Task 3, step 5).
3. **`on_result` callback must flow through `trigger_and_stream` to `_spawn_lifecycle_consumer`** — ai_finance_coach and ai_literacy_report depend on this for result persistence. If the parameter is lost, results are silently not persisted. Verification: test that on_result is forwarded (Task 3, step 5).
4. **Dispatch dict must cover all simple apps** — if an app is in `_SIMPLE_APPS` but missing from the dispatch check, it falls through to `ValueError`. Verification: test that every key in `_SIMPLE_APPS` routes correctly (Task 1, step 6).
5. **Router error paths must still work after refactor** — each router has custom error handling (checkpoint resume errors, circuit breaker, insufficient data). The refactor must not bypass these pre-checks. Verification: existing router tests must pass unchanged (Tasks 4-6).

---

## File Structure

### Part A — Worker Generic Runner

| Action | File | Responsibility |
|--------|------|----------------|
| Modify | `server/apps/agent/services/runtime/worker.py` | Add `_SimpleAppConfig` dataclass, `_SIMPLE_APPS` registry, `_run_simple_app()` generic runner, `_RUNNERS` dispatch dict. Remove 3 old runners. Simplify dispatch in `run_agent()`. |
| Create | `server/tests/agent/unit/test_worker_simple_apps.py` | Tests for config registry, generic runner dispatch, result event publishing |

### Part B — `trigger_and_stream` Helper

| Action | File | Responsibility |
|--------|------|----------------|
| Modify | `server/apps/backend/app/services/bridge_consumer.py` | Add `trigger_and_stream()` helper function |
| Create | `server/tests/backend/test_trigger_and_stream.py` | Tests for trigger_and_stream SSE lifecycle |
| Modify | `server/apps/backend/app/routers/ai_report.py` | Replace SSE lifecycle boilerplate with `trigger_and_stream()` call |
| Modify | `server/apps/backend/app/routers/ai_finance_coach.py` | Replace SSE lifecycle boilerplate with `trigger_and_stream()` call |
| Modify | `server/apps/backend/app/routers/ai_literacy_report.py` | Replace SSE lifecycle boilerplate with `trigger_and_stream()` call |

---

### Task 1: Worker — Generic Runner + Config Registry + Dispatch

**Files:**
- Modify: `server/apps/agent/services/runtime/worker.py`
- Create: `server/tests/agent/unit/test_worker_simple_apps.py`

**Interfaces:**
- Consumes: `RunPipeline` (from `.run_pipeline`), `_extract_backend_user_message()`, `_SYNTHETIC_TRIGGERS_BY_LANG`, `_LANGUAGE_INSTRUCTIONS`, `_SESSION_TITLES_BY_LANG`, `_set_session_title()`, `_track_task()` — all already defined in worker.py or run_pipeline.py
- Produces: `_SimpleAppConfig` (frozen dataclass), `_SIMPLE_APPS` (dict[str, _SimpleAppConfig]), `_run_simple_app()` (async function), `_RUNNERS` (dict[str, Callable])

**Context for implementer:**

Read these files before starting:
- `server/apps/agent/services/runtime/worker.py` — focus on lines 536-467 (dispatch), 1554-1653 (dashboard-narrative runner), 1948-2041 (literacy runner), 2047-2116 (learning-tutor runner)
- `server/apps/agent/services/runtime/run_pipeline.py` — focus on lines 194-291 (constructor), 561-687 (run_skill)
- `server/tests/agent/unit/test_worker_literacy_report.py` — existing dispatch test pattern
- `server/tests/agent/unit/test_run_pipeline.py` — existing RunPipeline test pattern

- [ ] **Step 1: Write failing tests for config registry and generic runner**

Create `server/tests/agent/unit/test_worker_simple_apps.py`:

```python
"""Tests for the config-driven simple-app runner in worker.py."""

from __future__ import annotations

import asyncio
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


class TestSimpleAppConfig:
    """Verify the _SimpleAppConfig registry has expected entries and values."""

    def test_simple_apps_registry_has_three_entries(self):
        from apps.agent.services.runtime.worker import _SIMPLE_APPS

        assert set(_SIMPLE_APPS.keys()) == {
            "dashboard-narrative",
            "literacy-weekly-report",
            "learning-tutor",
        }

    def test_dashboard_narrative_config(self):
        from apps.agent.services.runtime.worker import _SIMPLE_APPS

        cfg = _SIMPLE_APPS["dashboard-narrative"]
        assert cfg.skill_name == "dashboard-narrative"
        assert cfg.enable_thinking is True
        assert cfg.enable_reasoning_delta is True
        assert cfg.timeout_seconds == 60
        assert cfg.mcp_servers == []
        assert cfg.memory_enabled is True
        assert cfg.result_event_type == "dashboard_narrative.result"
        assert cfg.result_builder is not None

    def test_literacy_weekly_report_config(self):
        from apps.agent.services.runtime.worker import _SIMPLE_APPS

        cfg = _SIMPLE_APPS["literacy-weekly-report"]
        assert cfg.skill_name == "literacy-weekly-report"
        assert cfg.enable_thinking is True
        assert cfg.enable_reasoning_delta is True
        assert cfg.timeout_seconds == 120
        assert cfg.mcp_servers is None  # default MCP resolution
        assert cfg.memory_enabled is True
        assert cfg.result_event_type == "literacy_weekly_report.result"

    def test_learning_tutor_config(self):
        from apps.agent.services.runtime.worker import _SIMPLE_APPS

        cfg = _SIMPLE_APPS["learning-tutor"]
        assert cfg.skill_name == "learning-tutor"
        assert cfg.enable_thinking is False
        assert cfg.enable_reasoning_delta is False
        assert cfg.memory_enabled is False
        assert cfg.result_event_type == ""  # no result event
        assert cfg.result_builder is None

    def test_result_builder_dashboard_narrative(self):
        from apps.agent.services.runtime.worker import _SIMPLE_APPS

        cfg = _SIMPLE_APPS["dashboard-narrative"]
        payload = cfg.result_builder("narrative text", "thinking text")
        assert payload == {"narrative": "narrative text", "thinking": "thinking text"}

    def test_result_builder_literacy_report(self):
        from apps.agent.services.runtime.worker import _SIMPLE_APPS

        cfg = _SIMPLE_APPS["literacy-weekly-report"]
        payload = cfg.result_builder("report text", "thinking text")
        assert payload == {"report": "report text", "thinking": "thinking text"}


class TestRunnersDict:
    """Verify the _RUNNERS dispatch dict covers complex apps."""

    def test_runners_dict_has_five_complex_apps(self):
        from apps.agent.services.runtime.worker import _RUNNERS

        assert set(_RUNNERS.keys()) == {
            "asset-report",
            "import-parse",
            "finance-coach",
            "wish-advice",
            "numina",
        }

    def test_simple_and_complex_cover_all_known_apps(self):
        from apps.agent.services.runtime.worker import _RUNNERS, _SIMPLE_APPS

        all_apps = set(_SIMPLE_APPS.keys()) | set(_RUNNERS.keys())
        expected = {
            "numina", "asset-report", "import-parse", "finance-coach",
            "wish-advice", "dashboard-narrative", "literacy-weekly-report",
            "learning-tutor",
        }
        assert all_apps == expected


class TestRunSimpleApp:
    """Verify the generic runner constructs RunPipeline correctly."""

    @pytest.fixture
    def mock_record(self):
        record = MagicMock()
        record.metadata = {"language": "zh"}
        record.run_id = "test-run-id"
        return record

    @pytest.fixture
    def mock_deps(self):
        bridge = AsyncMock()
        run_manager = MagicMock()
        return bridge, run_manager

    async def test_dispatch_routes_simple_app_to_generic_runner(
        self, mock_deps
    ):
        """run_agent should route simple apps to _run_simple_app."""
        from apps.agent.services.runtime.worker import run_agent

        bridge, run_manager = mock_deps
        record = MagicMock()
        record.metadata = {"app": "dashboard-narrative", "language": "zh"}
        record.run_id = "test-run-id"

        with patch(
            "apps.agent.services.runtime.worker._run_simple_app",
            new_callable=AsyncMock,
        ) as mock_run, patch(
            "apps.agent.services.runtime.worker.set_family_sandbox_context",
        ), patch(
            "apps.agent.services.runtime.worker.reset_family_sandbox_context",
        ):
            await run_agent(
                bridge=bridge,
                run_manager=run_manager,
                record=record,
                family_id="123",
                user_id="456",
                thread_id="thread-1",
                graph_input=None,
                config={},
            )
            mock_run.assert_awaited_once()
            # Verify the config passed is the dashboard-narrative config
            cfg_arg = mock_run.call_args.args[0]
            assert cfg_arg.app_name == "dashboard-narrative"

    async def test_dispatch_routes_numina_to_runners_dict(self, mock_deps):
        """run_agent should route 'numina' through _RUNNERS dict."""
        from apps.agent.services.runtime.worker import run_agent

        bridge, run_manager = mock_deps
        record = MagicMock()
        record.metadata = {}  # default app = "numina"
        record.run_id = "test-run-id"

        with patch(
            "apps.agent.services.runtime.worker._run_numina_agent",
            new_callable=AsyncMock,
        ) as mock_numina, patch(
            "apps.agent.services.runtime.worker.set_family_sandbox_context",
        ), patch(
            "apps.agent.services.runtime.worker.reset_family_sandbox_context",
        ):
            await run_agent(
                bridge=bridge,
                run_manager=run_manager,
                record=record,
                family_id="123",
                user_id="456",
                thread_id="thread-1",
                graph_input=None,
                config={},
            )
            mock_numina.assert_awaited_once()

    async def test_unknown_app_raises_value_error(self, mock_deps):
        """run_agent should raise ValueError for unknown app names."""
        from apps.agent.services.runtime.worker import run_agent

        bridge, run_manager = mock_deps
        record = MagicMock()
        record.metadata = {"app": "nonexistent-app"}

        with pytest.raises(ValueError, match="Unknown app"):
            await run_agent(
                bridge=bridge,
                run_manager=run_manager,
                record=record,
                family_id="123",
                user_id="456",
                thread_id="thread-1",
                graph_input=None,
                config={},
            )

    async def test_run_simple_app_passes_config_to_pipeline(
        self, mock_record, mock_deps
    ):
        """_run_simple_app should construct RunPipeline with config params."""
        from apps.agent.services.runtime.worker import (
            _SIMPLE_APPS,
            _run_simple_app,
        )

        bridge, run_manager = mock_deps
        cfg = _SIMPLE_APPS["dashboard-narrative"]

        mock_pipeline = AsyncMock()
        mock_pipeline.__aenter__ = AsyncMock(return_value=mock_pipeline)
        mock_pipeline.__aexit__ = AsyncMock(return_value=False)
        mock_pipeline.ai_text = "test narrative"
        mock_pipeline.thinking_text = "test thinking"
        mock_pipeline.run_skill = AsyncMock()

        with patch(
            "apps.agent.services.runtime.worker.RunPipeline",
            return_value=mock_pipeline,
        ):
            await _run_simple_app(
                cfg,
                bridge=bridge,
                run_manager=run_manager,
                record=mock_record,
                family_id="123",
                user_id="456",
                thread_id="thread-1",
                graph_input=None,
                config={},
            )

        mock_pipeline.run_skill.assert_awaited_once()
        call_kwargs = mock_pipeline.run_skill.call_args
        assert call_kwargs.kwargs.get("enable_reasoning_delta") is True

    async def test_run_simple_app_publishes_result_event_for_dashboard(
        self, mock_record, mock_deps
    ):
        """dashboard-narrative should publish dashboard_narrative.result event."""
        from apps.agent.services.runtime.worker import (
            _SIMPLE_APPS,
            _run_simple_app,
        )

        bridge, run_manager = mock_deps
        cfg = _SIMPLE_APPS["dashboard-narrative"]

        mock_pipeline = AsyncMock()
        mock_pipeline.__aenter__ = AsyncMock(return_value=mock_pipeline)
        mock_pipeline.__aexit__ = AsyncMock(return_value=False)
        mock_pipeline.ai_text = "narrative text"
        mock_pipeline.thinking_text = "thinking text"
        mock_pipeline.run_skill = AsyncMock()

        with patch(
            "apps.agent.services.runtime.worker.RunPipeline",
            return_value=mock_pipeline,
        ):
            await _run_simple_app(
                cfg,
                bridge=bridge,
                run_manager=run_manager,
                record=mock_record,
                family_id="123",
                user_id="456",
                thread_id="thread-1",
                graph_input=None,
                config={},
            )

        # Verify bridge.publish was called with result event
        publish_calls = [
            c for c in bridge.publish.call_args_list
            if len(c.args) >= 2
            and isinstance(c.args[1], dict)
            and c.args[1].get("type") == "dashboard_narrative.result"
        ]
        assert len(publish_calls) == 1
        payload = publish_calls[0].args[1]["payload"]
        assert payload == {"narrative": "narrative text", "thinking": "thinking text"}

    async def test_run_simple_app_no_result_event_for_learning_tutor(
        self, mock_record, mock_deps
    ):
        """learning-tutor should NOT publish a result event."""
        from apps.agent.services.runtime.worker import (
            _SIMPLE_APPS,
            _run_simple_app,
        )

        bridge, run_manager = mock_deps
        cfg = _SIMPLE_APPS["learning-tutor"]

        mock_pipeline = AsyncMock()
        mock_pipeline.__aenter__ = AsyncMock(return_value=mock_pipeline)
        mock_pipeline.__aexit__ = AsyncMock(return_value=False)
        mock_pipeline.run_skill = AsyncMock()

        with patch(
            "apps.agent.services.runtime.worker.RunPipeline",
            return_value=mock_pipeline,
        ):
            await _run_simple_app(
                cfg,
                bridge=bridge,
                run_manager=run_manager,
                record=mock_record,
                family_id="123",
                user_id="456",
                thread_id="thread-1",
                graph_input=None,
                config={},
            )

        # No custom result event should be published
        custom_publishes = [
            c for c in bridge.publish.call_args_list
            if len(c.args) >= 2
            and isinstance(c.args[1], dict)
            and c.args[1].get("type", "").endswith(".result")
        ]
        assert len(custom_publishes) == 0
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd server && uv run pytest tests/agent/unit/test_worker_simple_apps.py -v`
Expected: FAIL — `_SIMPLE_APPS`, `_run_simple_app`, `_RUNNERS` not yet defined in worker.py

- [ ] **Step 3: Add `_SimpleAppConfig` dataclass and `_SIMPLE_APPS` registry to worker.py**

Add near the top of worker.py (after existing imports, before the first runner function), around line 100:

```python
from collections.abc import Callable
from dataclasses import dataclass

# Result builder signature: (ai_text, thinking_text) → payload dict | None
_ResultBuilder = Callable[[str, str], dict[str, Any] | None]


@dataclass(frozen=True)
class _SimpleAppConfig:
    """Per-app config for the generic simple-app runner."""

    app_name: str
    skill_name: str  # DeerFlow skill (matches SKILL.md name)
    enable_thinking: bool = False
    enable_reasoning_delta: bool = False  # forward reasoning_delta to frontend
    timeout_seconds: int = 120
    mcp_servers: list | None = None  # None = default resolution; [] = no MCP
    memory_enabled: bool = True
    trigger_key: str = ""  # key into _SYNTHETIC_TRIGGERS_BY_LANG
    result_event_type: str = ""  # "" = no result event (e.g., learning-tutor)
    result_builder: _ResultBuilder | None = None  # builds payload from ai_text + thinking_text
```

Then add the registry **after** `_SYNTHETIC_TRIGGERS_BY_LANG` and `_SESSION_TITLES_BY_LANG` are defined (around line 990):

```python
_SIMPLE_APPS: dict[str, _SimpleAppConfig] = {
    "dashboard-narrative": _SimpleAppConfig(
        app_name="dashboard-narrative",
        skill_name="dashboard-narrative",
        mcp_servers=[],
        timeout_seconds=60,
        enable_thinking=True,
        enable_reasoning_delta=True,
        trigger_key="dashboard-narrative",
        result_event_type="dashboard_narrative.result",
        result_builder=lambda ai, th: {"narrative": ai, "thinking": th},
    ),
    "literacy-weekly-report": _SimpleAppConfig(
        app_name="literacy-weekly-report",
        skill_name="literacy-weekly-report",
        enable_thinking=True,
        enable_reasoning_delta=True,
        trigger_key="literacy-weekly-report",
        result_event_type="literacy_weekly_report.result",
        result_builder=lambda ai, th: {"report": ai, "thinking": th},
    ),
    "learning-tutor": _SimpleAppConfig(
        app_name="learning-tutor",
        skill_name="learning-tutor",
        enable_thinking=False,
        memory_enabled=False,
        trigger_key="learning-tutor",
        # no result_event_type, no result_builder — frontend consumes streamed frames directly
    ),
}
```

- [ ] **Step 4: Add `_run_simple_app()` generic runner to worker.py**

Add after the `_SIMPLE_APPS` registry:

```python
async def _run_simple_app(
    cfg: _SimpleAppConfig,
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
    """Generic runner for simple single-run apps.

    Replaces _run_dashboard_narrative_agent, _run_literacy_weekly_report_agent,
    _run_learning_tutor_agent.

    Uses the RunPipeline.run_skill() → p.ai_text / p.thinking_text pattern.
    RunPipeline.__aenter__ handles set_active_skill internally via skill_name param.
    """
    from .run_pipeline import RunPipeline

    async with RunPipeline(
        app_name=cfg.app_name,
        family_id=family_id,
        user_id=user_id,
        thread_id=thread_id,
        record=record,
        bridge=bridge,
        run_manager=run_manager,
        memory_enabled=cfg.memory_enabled,
        enable_thinking=cfg.enable_thinking,
        timeout_seconds=cfg.timeout_seconds,
        mcp_servers=cfg.mcp_servers,
        skill_name=cfg.skill_name,
    ) as p:
        # Build user message from backend-injected content or synthetic trigger
        user_language = (record.metadata or {}).get("language") or "zh"
        user_message = _extract_backend_user_message(graph_input) or \
            _SYNTHETIC_TRIGGERS_BY_LANG.get(cfg.trigger_key, {}).get(
                user_language,
                _SYNTHETIC_TRIGGERS_BY_LANG.get(cfg.trigger_key, {}).get("default", ""),
            )
        lang_instruction = _LANGUAGE_INSTRUCTIONS.get(
            user_language, _LANGUAGE_INSTRUCTIONS["default"]
        )
        user_message = f"{lang_instruction}\n\n{user_message}"

        # Set session title (fire-and-forget)
        title_key = _SESSION_TITLES_BY_LANG.get(cfg.app_name, {})
        title_prefix = title_key.get(user_language, title_key.get("default", cfg.app_name))
        _track_task(asyncio.create_task(
            _set_session_title(thread_id, family_id, title_prefix)
        ))

        # Execute skill — RunPipeline handles frame streaming, PII redaction, etc.
        await p.run_skill(user_message, enable_reasoning_delta=cfg.enable_reasoning_delta)

        # Publish result event if configured
        if cfg.result_event_type and cfg.result_builder:
            payload = cfg.result_builder(p.ai_text.strip(), p.thinking_text)
            if payload is not None:
                await bridge.publish(p.run_id, "custom", {
                    "type": cfg.result_event_type,
                    "payload": payload,
                })
```

- [ ] **Step 5: Replace dispatch chain with dict lookup in `run_agent()`**

In `run_agent()` (around lines 335-432), replace the 8-branch if chain. First, add the `_RUNNERS` dict near `_SIMPLE_APPS`:

```python
_RUNNERS: dict[str, Callable[..., Any]] = {
    "asset-report": _run_asset_report_agent,
    "import-parse": _run_import_parse_agent,
    "finance-coach": _run_finance_coach_agent,
    "wish-advice": _run_wish_advice_agent,
    "numina": _run_numina_agent,
}
```

Then replace the dispatch block in `run_agent()`:

```python
    # Dispatch to the appropriate runner
    app = record.metadata.get("app", "numina") if record.metadata else "numina"

    if app in _SIMPLE_APPS:
        await _run_simple_app(
            _SIMPLE_APPS[app],
            bridge=bridge,
            run_manager=run_manager,
            record=record,
            family_id=family_id,
            user_id=user_id,
            thread_id=thread_id,
            graph_input=graph_input,
            config=config,
        )
    elif app in _RUNNERS:
        runner = _RUNNERS[app]
        kwargs: dict[str, Any] = dict(
            bridge=bridge,
            run_manager=run_manager,
            record=record,
            family_id=family_id,
            user_id=user_id,
            thread_id=thread_id,
            graph_input=graph_input,
            config=config,
        )
        if app == "numina":
            kwargs["stream_modes"] = stream_modes
        await runner(**kwargs)
    else:
        raise ValueError(f"Unknown app: {app}")
```

**Important:** The `_RUNNERS` dict references `_run_numina_agent`, `_run_asset_report_agent`, etc. These functions are defined later in the file. Since Python resolves function references at call time (not at dict construction time for module-level dicts), this works — but verify the dict is constructed **after** all runner function definitions, OR use lazy references. The safest approach is to place `_RUNNERS` after the last runner function definition (after `_run_numina_agent`).

Alternatively, place `_RUNNERS` at the very end of the file (after all runners are defined) and reference it from `run_agent()` by name. This avoids forward-reference issues.

- [ ] **Step 6: Remove the 3 old runner functions**

Delete these functions entirely:
- `_run_dashboard_narrative_agent` (lines ~1554-1653)
- `_run_literacy_weekly_report_agent` (lines ~1948-2041)
- `_run_learning_tutor_agent` (lines ~2047-2116)

Also remove their standalone fallback constants that are no longer referenced by anything:
- `_SYNTHETIC_DASHBOARD_NARRATIVE_TRIGGER` (line ~1551) — still used as fallback in `_SYNTHETIC_TRIGGERS_BY_LANG`, check if referenced elsewhere first
- `_SYNTHETIC_LITERACY_REPORT_TRIGGER` (line ~1945) — same check
- `_SYNTHETIC_LEARNING_TUTOR_TRIGGER` (line ~2044) — same check

**Do NOT remove** these constants without first running `grep -rn` to verify no other code references them.

- [ ] **Step 7: Run tests to verify they pass**

Run: `cd server && uv run pytest tests/agent/unit/test_worker_simple_apps.py -v`
Expected: All PASS

Also run existing worker tests to verify no regressions:

Run: `cd server && uv run pytest tests/agent/unit/test_worker_literacy_report.py tests/agent/integration/test_learning_tutor_dispatch.py tests/agent/unit/test_run_pipeline.py -v`
Expected: All PASS (dispatch tests may need updating if they import old function names)

- [ ] **Step 8: Run lint and type checks**

Run: `cd server && uv run ruff check apps/agent/services/runtime/worker.py`
Run: `cd server && uv run ruff format apps/agent/services/runtime/worker.py`
Run: `cd server && uv run mypy apps/agent/services/runtime/worker.py --exclude vendor`
Expected: No new errors

- [ ] **Step 9: Commit**

```bash
git add server/apps/agent/services/runtime/worker.py server/tests/agent/unit/test_worker_simple_apps.py
git commit -m "refactor(agent): replace 3 simple runners with config-driven generic runner

Extract _SimpleAppConfig dataclass + _SIMPLE_APPS registry +
_run_simple_app() generic runner driven by per-app config.
Replace 8-branch dispatch chain with dict lookup.

Removes ~240 lines of duplicated runner boilerplate.
Net reduction: ~170 lines from worker.py.

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>"
```

---

### Task 2: Bridge Consumer — Add `trigger_and_stream()` Helper

**Files:**
- Modify: `server/apps/backend/app/services/bridge_consumer.py`
- Create: `server/tests/backend/test_trigger_and_stream.py`

**Interfaces:**
- Consumes: `trigger_agent_run()`, `_lease_heartbeat()`, `_spawn_lifecycle_consumer()`, `consume_task_stream()`, `get_shared_bridge()` — all already in bridge_consumer.py; `AITaskService.extract_and_attach_run_id()`; `tracked_sse_stream()` from `subscriber_registry`
- Produces: `trigger_and_stream()` — async function returning `StreamingResponse`

**Context for implementer:**

Read these files before starting:
- `server/apps/backend/app/services/bridge_consumer.py` — full file, especially the functions listed above
- `server/apps/backend/app/routers/ai_report.py` — lines 263-354 (the SSE lifecycle pattern to be replaced)
- `server/apps/backend/app/routers/ai_finance_coach.py` — lines 219-283
- `server/apps/backend/app/routers/ai_literacy_report.py` — lines 294-358
- `server/tests/backend/test_bridge_consumer_lifecycle.py` — existing lifecycle test patterns

- [ ] **Step 1: Write failing tests for `trigger_and_stream`**

Create `server/tests/backend/test_trigger_and_stream.py`:

```python
"""Tests for the trigger_and_stream() helper in bridge_consumer.py."""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


@pytest.fixture
def mock_agent_client():
    """Mock AgentClient that returns a canned trigger response."""
    client = AsyncMock()
    resp = MagicMock()
    resp.headers = {"Content-Location": "/api/threads/t1/runs/run-123"}
    resp.raise_for_status = MagicMock()
    client.post = AsyncMock(return_value=resp)
    return client


@pytest.fixture
def patched_helpers():
    """Patch all downstream dependencies of trigger_and_stream."""
    with (
        patch(
            "apps.backend.app.services.bridge_consumer.AITaskService"
        ) as mock_task_svc,
        patch(
            "apps.backend.app.services.bridge_consumer._lease_heartbeat",
            new_callable=AsyncMock,
        ) as mock_hb,
        patch(
            "apps.backend.app.services.bridge_consumer._spawn_lifecycle_consumer",
        ) as mock_lifecycle,
        patch(
            "apps.backend.app.services.bridge_consumer.consume_task_stream",
        ) as mock_consume,
        patch(
            "apps.backend.app.services.bridge_consumer.get_shared_bridge",
        ) as mock_bridge,
        patch(
            "apps.backend.app.services.bridge_consumer.tracked_sse_stream",
        ) as mock_tracked,
    ):
        mock_task_svc.extract_and_attach_run_id = MagicMock()
        # Make consume_task_stream return a simple async generator
        async def fake_stream(**kwargs):
            yield "event: metadata\ndata: {\"task_id\": \"t1\"}\n\n"
            yield "event: end\ndata: {\"status\": \"success\"}\n\n"

        mock_consume.side_effect = fake_stream
        # Make tracked_sse_stream pass through
        mock_tracked.side_effect = lambda task_id, gen: gen
        # Heartbeat should be an async function that waits on stop_event
        async def fake_heartbeat(task_id, family_id, stop_event):
            await stop_event.wait()

        mock_hb.side_effect = fake_heartbeat

        yield {
            "task_svc": mock_task_svc,
            "heartbeat": mock_hb,
            "lifecycle": mock_lifecycle,
            "consume": mock_consume,
            "bridge": mock_bridge,
            "tracked": mock_tracked,
        }


class TestTriggerAndStream:
    """Verify trigger_and_stream encapsulates the full SSE lifecycle."""

    async def test_returns_streaming_response(self, mock_agent_client, patched_helpers):
        from apps.backend.app.services.bridge_consumer import trigger_and_stream
        from fastapi.responses import StreamingResponse

        result = await trigger_and_stream(
            agent_client=mock_agent_client,
            agent_url="/internal/gateway/runs/asset-report/session-1",
            json_body={"family_id": "123"},
            task_id="task-1",
            family_id=123,
            session_id="session-1",
        )
        assert isinstance(result, StreamingResponse)
        assert result.media_type == "text/event-stream"

    async def test_attaches_run_id_to_task(self, mock_agent_client, patched_helpers):
        from apps.backend.app.services.bridge_consumer import trigger_and_stream

        await trigger_and_stream(
            agent_client=mock_agent_client,
            agent_url="/internal/gateway/runs/asset-report/session-1",
            json_body={"family_id": "123"},
            task_id="task-1",
            family_id=123,
            session_id="session-1",
        )
        patched_helpers["task_svc"].extract_and_attach_run_id.assert_called_once_with(
            "task-1", "/api/threads/t1/runs/run-123", 123
        )

    async def test_spawns_lifecycle_consumer(self, mock_agent_client, patched_helpers):
        from apps.backend.app.services.bridge_consumer import trigger_and_stream

        await trigger_and_stream(
            agent_client=mock_agent_client,
            agent_url="/internal/gateway/runs/asset-report/session-1",
            json_body={"family_id": "123"},
            task_id="task-1",
            family_id=123,
            session_id="session-1",
        )
        patched_helpers["lifecycle"].assert_called_once()
        call_kwargs = patched_helpers["lifecycle"].call_args.kwargs
        assert call_kwargs["task_id"] == "task-1"
        assert call_kwargs["family_id"] == 123
        assert call_kwargs["run_id"] == "run-123"

    async def test_passes_on_result_callback(self, mock_agent_client, patched_helpers):
        from apps.backend.app.services.bridge_consumer import trigger_and_stream

        on_result = AsyncMock()
        await trigger_and_stream(
            agent_client=mock_agent_client,
            agent_url="/internal/gateway/runs/finance-coach/session-1",
            json_body={"family_id": "123"},
            task_id="task-1",
            family_id=123,
            session_id="session-1",
            on_result=on_result,
        )
        call_kwargs = patched_helpers["lifecycle"].call_args.kwargs
        assert call_kwargs.get("on_result") is on_result

    async def test_passes_thread_id_to_lifecycle(
        self, mock_agent_client, patched_helpers
    ):
        from apps.backend.app.services.bridge_consumer import trigger_and_stream

        await trigger_and_stream(
            agent_client=mock_agent_client,
            agent_url="/internal/gateway/runs/asset-report/session-1",
            json_body={"family_id": "123"},
            task_id="task-1",
            family_id=123,
            session_id="session-1",
            thread_id="custom-thread-id",
        )
        call_kwargs = patched_helpers["lifecycle"].call_args.kwargs
        assert call_kwargs.get("thread_id") == "custom-thread-id"

    async def test_default_thread_id_is_session_id(
        self, mock_agent_client, patched_helpers
    ):
        from apps.backend.app.services.bridge_consumer import trigger_and_stream

        await trigger_and_stream(
            agent_client=mock_agent_client,
            agent_url="/internal/gateway/runs/asset-report/session-1",
            json_body={"family_id": "123"},
            task_id="task-1",
            family_id=123,
            session_id="session-1",
        )
        call_kwargs = patched_helpers["lifecycle"].call_args.kwargs
        assert call_kwargs.get("thread_id") == "session-1"

    async def test_passes_last_event_id_to_consume(
        self, mock_agent_client, patched_helpers
    ):
        from apps.backend.app.services.bridge_consumer import trigger_and_stream

        await trigger_and_stream(
            agent_client=mock_agent_client,
            agent_url="/internal/gateway/runs/asset-report/session-1",
            json_body={"family_id": "123"},
            task_id="task-1",
            family_id=123,
            session_id="session-1",
            last_event_id="evt-42",
        )
        call_kwargs = patched_helpers["consume"].call_args.kwargs
        assert call_kwargs.get("last_event_id") == "evt-42"

    async def test_sets_x_accel_buffering_header(
        self, mock_agent_client, patched_helpers
    ):
        from apps.backend.app.services.bridge_consumer import trigger_and_stream

        result = await trigger_and_stream(
            agent_client=mock_agent_client,
            agent_url="/internal/gateway/runs/asset-report/session-1",
            json_body={"family_id": "123"},
            task_id="task-1",
            family_id=123,
            session_id="session-1",
        )
        assert result.headers.get("X-Accel-Buffering") == "no"

    async def test_propagates_trigger_failure(self, mock_agent_client, patched_helpers):
        """Agent trigger failure should propagate to the caller for error handling."""
        from apps.backend.app.services.bridge_consumer import trigger_and_stream

        mock_agent_client.post = AsyncMock(
            side_effect=Exception("Agent unavailable")
        )
        with pytest.raises(Exception, match="Agent unavailable"):
            await trigger_and_stream(
                agent_client=mock_agent_client,
                agent_url="/internal/gateway/runs/asset-report/session-1",
                json_body={"family_id": "123"},
                task_id="task-1",
                family_id=123,
                session_id="session-1",
            )
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd server && uv run pytest tests/backend/test_trigger_and_stream.py -v`
Expected: FAIL — `trigger_and_stream` not yet defined

- [ ] **Step 3: Add module-level `AITaskService` import to bridge_consumer.py**

`AITaskService` is currently imported lazily inside `_lease_heartbeat` and `_spawn_lifecycle_consumer`. The new `trigger_and_stream()` function calls `AITaskService.extract_and_attach_run_id()` directly. Add a module-level import:

```python
from apps.backend.app.services.ai_task_service import AITaskService
```

Add this after the existing imports (around line 22). This is safe — `ai_task_service` does not import from `bridge_consumer`, so no circular dependency.

Also add the `StreamingResponse` and `tracked_sse_stream` imports:

```python
from fastapi.responses import StreamingResponse
from .subscriber_registry import tracked_sse_stream
```

- [ ] **Step 4: Add `trigger_and_stream()` to bridge_consumer.py**

Add the following to the existing imports if not already present:

```python
import contextlib
```

Then add the function after `consume_task_stream()` (at the end of the file):

```python
async def trigger_and_stream(
    *,
    agent_client: Any,
    agent_url: str,
    json_body: dict[str, Any],
    task_id: str,
    family_id: int | str,
    session_id: str,
    last_event_id: str | None = None,
    on_result: Callable[..., Coroutine[Any, Any, None]] | None = None,
    thread_id: str | None = None,
) -> StreamingResponse:
    """Full SSE lifecycle: trigger agent → heartbeat → lifecycle consumer → stream.

    Encapsulates the common pattern shared by ai_report, ai_finance_coach,
    and ai_literacy_report routers.

    Note: learning_child.py is NOT included — it has a different SSE lifecycle
    (no heartbeat, no tracked_sse_stream, uses consume_task_stream with
    Last-Event-ID reconnection, and manages its own DB session).

    Raises:
        Exception: If agent trigger fails — caller handles with app-specific error stream.
    """
    # 1. Trigger agent
    result = await trigger_agent_run(
        agent_client=agent_client,
        agent_url=agent_url,
        json_body=json_body,
        task_id=task_id,
        family_id=family_id,
    )
    run_id = result["run_id"]

    # 2. Attach run_id to task
    AITaskService.extract_and_attach_run_id(task_id, result["content_location"], family_id)

    # 3. Lease heartbeat
    _hb_stop = asyncio.Event()
    _hb_task = asyncio.create_task(_lease_heartbeat(task_id, family_id, _hb_stop))

    # 4. Lifecycle consumer
    shared_bridge = get_shared_bridge()
    lifecycle_kwargs: dict[str, Any] = dict(
        task_id=task_id,
        family_id=family_id,
        run_id=run_id,
        bridge=shared_bridge,
    )
    if on_result is not None:
        lifecycle_kwargs["on_result"] = on_result
    if thread_id is not None:
        lifecycle_kwargs["thread_id"] = thread_id
    else:
        lifecycle_kwargs["thread_id"] = session_id
    _spawn_lifecycle_consumer(**lifecycle_kwargs)

    # 5. SSE forwarder with cleanup
    stream_gen = consume_task_stream(
        task_id=task_id,
        family_id=family_id,
        last_event_id=last_event_id,
        run_id=run_id,
        bridge=shared_bridge,
    )

    async def _stream():
        try:
            async for chunk in stream_gen:
                yield chunk
        finally:
            _hb_stop.set()
            with contextlib.suppress(asyncio.CancelledError):
                await _hb_task

    return StreamingResponse(
        tracked_sse_stream(task_id, _stream()),
        media_type="text/event-stream",
        headers={"X-Accel-Buffering": "no"},
    )
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `cd server && uv run pytest tests/backend/test_trigger_and_stream.py -v`
Expected: All PASS

- [ ] **Step 6: Run lint and type checks**

Run: `cd server && uv run ruff check apps/backend/app/services/bridge_consumer.py`
Run: `cd server && uv run ruff format apps/backend/app/services/bridge_consumer.py`
Expected: Clean

- [ ] **Step 7: Commit**

```bash
git add server/apps/backend/app/services/bridge_consumer.py server/tests/backend/test_trigger_and_stream.py
git commit -m "refactor(backend): add trigger_and_stream() helper for SSE lifecycle

Encapsulates the common trigger→heartbeat→lifecycle→stream pattern
shared by ai_report, ai_finance_coach, and ai_literacy_report routers.
Supports optional on_result callback and thread_id override.

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>"
```

---

### Task 3: Router Simplification — ai_report.py

**Files:**
- Modify: `server/apps/backend/app/routers/ai_report.py`

**Interfaces:**
- Consumes: `trigger_and_stream()` from Task 2
- Produces: Same SSE endpoint behavior, less code

**Context for implementer:**

The ai_report router has special handling:
- **Checkpoint resume**: the `resume` parameter modifies `agent_trigger_body` with checkpoint config
- **Error stream**: on trigger failure, returns a single-event SSE error stream (NOT a JSON error)
- **Timeout**: uses `AgentClient(family_id, user_id, timeout=300.0)`

The pre-checks (circuit breaker, cache, running task detection, session creation) and error handling stay in the router. Only the happy-path SSE lifecycle (trigger→heartbeat→lifecycle→stream) is replaced.

- [ ] **Step 1: Update imports in ai_report.py**

Replace the existing bridge_consumer imports:

```python
# Remove these individual imports:
from apps.backend.app.services.bridge_consumer import (
    _lease_heartbeat,
    _spawn_lifecycle_consumer,
    consume_task_stream,
    get_shared_bridge,
    trigger_agent_run,
)

# Add:
from apps.backend.app.services.bridge_consumer import (
    get_shared_bridge,
    trigger_agent_run,
    trigger_and_stream,
)
```

Keep `trigger_agent_run` and `get_shared_bridge` if they're used elsewhere in the file (e.g., error paths). If only used in the replaced block, remove them.

Also remove unused imports:
```python
# These are only used in the replaced block — remove if no longer needed:
import asyncio  # check if used elsewhere first
import contextlib  # check if used elsewhere first
```

And remove:
```python
from apps.backend.app.services.subscriber_registry import tracked_sse_stream
```

- [ ] **Step 2: Replace the SSE lifecycle block**

Find the block in `trigger_generate_events` that starts with `result = await trigger_agent_run(...)` and ends with `return StreamingResponse(...)`. Replace with:

```python
    # Trigger agent and stream SSE
    try:
        return await trigger_and_stream(
            agent_client=agent_client,
            agent_url=agent_url,
            json_body=agent_trigger_body,
            task_id=str(task_id),
            family_id=family_id,
            session_id=session_id,
            last_event_id=request.headers.get("Last-Event-ID"),
            thread_id=session_id,
        )
    except Exception as e:
        logger.error("Agent trigger failed for task %s: %s", task_id, e)
        error_msg = "读写报告服务异常"
        error_event = f"event: error\ndata: {json.dumps({'error': error_msg})}\n\n"
        end_event = "event: end\ndata: {\"status\": \"error\"}\n\n"

        async def _error_stream():
            yield error_event
            yield end_event

        return StreamingResponse(
            tracked_sse_stream(str(task_id), _error_stream()),
            media_type="text/event-stream",
            headers={"X-Accel-Buffering": "no"},
        )
```

**Note:** The error stream still needs `tracked_sse_stream`, so keep that import if the error path uses it. Alternatively, use the pattern from the existing code for the error path.

- [ ] **Step 3: Verify existing tests still pass**

Run: `cd server && uv run pytest tests/backend/test_ai_report.py tests/backend/test_ai_report_trigger.py tests/backend/test_ai_report_checkpoint_resume.py -v`
Expected: All PASS — the endpoint behavior is unchanged

- [ ] **Step 4: Run lint**

Run: `cd server && uv run ruff check apps/backend/app/routers/ai_report.py`
Run: `cd server && uv run ruff format apps/backend/app/routers/ai_report.py`
Expected: Clean

- [ ] **Step 5: Commit**

```bash
git add server/apps/backend/app/routers/ai_report.py
git commit -m "refactor(backend): simplify ai_report router with trigger_and_stream()

Replace ~30 lines of SSE lifecycle boilerplate with single
trigger_and_stream() call. Error handling preserved.

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>"
```

---

### Task 4: Router Simplification — ai_finance_coach.py

**Files:**
- Modify: `server/apps/backend/app/routers/ai_finance_coach.py`

**Interfaces:**
- Consumes: `trigger_and_stream()` from Task 2
- Produces: Same SSE endpoint behavior, less code

**Context for implementer:**

The ai_finance_coach router has special handling:
- **Resume path** (lines ~96-125): When resuming an existing running task, returns SSE directly WITHOUT heartbeat/lifecycle. This path is NOT replaced — only the fresh-trigger path uses `trigger_and_stream()`.
- **`on_result` callback**: passes `_persist_coach_result` to lifecycle consumer
- **No `thread_id`**: does not pass thread_id to `_spawn_lifecycle_consumer` (the `trigger_and_stream` default of `session_id` is acceptable here since the lifecycle consumer uses it for event persistence)
- **Insufficient-data gate**: skips LLM call when no financial data — this pre-check stays

- [ ] **Step 1: Update imports in ai_finance_coach.py**

Replace bridge_consumer imports:

```python
# Remove:
from apps.backend.app.services.bridge_consumer import (
    _lease_heartbeat,
    _spawn_lifecycle_consumer,
    consume_task_stream,
    get_shared_bridge,
    trigger_agent_run,
)

# Add:
from apps.backend.app.services.bridge_consumer import (
    get_shared_bridge,
    trigger_agent_run,
    trigger_and_stream,
)
```

Remove unused imports:
```python
import asyncio  # check if used in resume path first
from apps.backend.app.services.subscriber_registry import tracked_sse_stream  # check if used in resume path
```

- [ ] **Step 2: Replace the fresh-trigger SSE lifecycle block**

Find the block that starts with `result = await trigger_agent_run(...)` (after the insufficient-data gate and agent_trigger_body construction). Replace with:

```python
    # Trigger agent and stream SSE
    try:
        return await trigger_and_stream(
            agent_client=agent_client,
            agent_url=agent_url,
            json_body=agent_trigger_body,
            task_id=str(task_id),
            family_id=family_id,
            session_id=session_id,
            last_event_id=request.headers.get("Last-Event-ID"),
            on_result=_persist_coach_result,
        )
    except Exception as e:
        logger.error("Finance coach trigger failed for task %s: %s", task_id, e)
        error_msg = "读写财务教练服务异常"
        error_event = f"event: error\ndata: {json.dumps({'error': error_msg})}\n\n"
        end_event = "event: end\ndata: {\"status\": \"error\"}\n\n"

        async def _error_stream():
            yield error_event
            yield end_event

        return StreamingResponse(
            tracked_sse_stream(str(task_id), _error_stream()),
            media_type="text/event-stream",
            headers={"X-Accel-Buffering": "no"},
        )
```

**Note:** The resume path (returning SSE for an already-running task) is NOT changed — it has its own code that directly subscribes to the bridge without triggering a new agent run.

- [ ] **Step 3: Verify existing tests still pass**

Run: `cd server && uv run pytest tests/backend/routers/test_ai_finance_coach.py -v`
Expected: All PASS

- [ ] **Step 4: Run lint**

Run: `cd server && uv run ruff check apps/backend/app/routers/ai_finance_coach.py`
Run: `cd server && uv run ruff format apps/backend/app/routers/ai_finance_coach.py`
Expected: Clean

- [ ] **Step 5: Commit**

```bash
git add server/apps/backend/app/routers/ai_finance_coach.py
git commit -m "refactor(backend): simplify ai_finance_coach router with trigger_and_stream()

Replace ~30 lines of SSE lifecycle boilerplate with single
trigger_and_stream() call. Passes on_result callback for
coach result persistence. Resume path unchanged.

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>"
```

---

### Task 5: Router Simplification — ai_literacy_report.py

**Files:**
- Modify: `server/apps/backend/app/routers/ai_literacy_report.py`

**Interfaces:**
- Consumes: `trigger_and_stream()` from Task 2
- Produces: Same SSE endpoint behavior, less code

**Context for implementer:**

The ai_literacy_report router has special handling:
- **`child_id` validation**: pre-check that child belongs to family — stays
- **`on_result` callback**: passes `_persist_literacy_result` to lifecycle consumer
- **Custom `thread_id`**: uses `_make_thread_id(family_id, cid)` instead of `session_id` — this is the child-scoped thread ID for event persistence
- **`AgentClient` timeout=120.0**: the caller constructs `AgentClient` before calling `trigger_and_stream`, so the timeout is already set
- **`SnowflakeResponse`**: used for the 202 queued response — stays

- [ ] **Step 1: Update imports in ai_literacy_report.py**

Replace bridge_consumer imports:

```python
# Remove:
from apps.backend.app.services.bridge_consumer import (
    _lease_heartbeat,
    _spawn_lifecycle_consumer,
    consume_task_stream,
    get_shared_bridge,
    trigger_agent_run,
)

# Add:
from apps.backend.app.services.bridge_consumer import (
    get_shared_bridge,
    trigger_agent_run,
    trigger_and_stream,
)
```

Remove unused imports:
```python
import asyncio  # check if used elsewhere first
from apps.backend.app.services.subscriber_registry import tracked_sse_stream  # check if used in error path
```

- [ ] **Step 2: Replace the SSE lifecycle block**

Find the block that starts with `result = await trigger_agent_run(...)`. Replace with:

```python
    # Trigger agent and stream SSE
    try:
        return await trigger_and_stream(
            agent_client=agent_client,
            agent_url=agent_url,
            json_body=agent_trigger_body,
            task_id=str(task_id),
            family_id=family_id,
            session_id=session_id,
            last_event_id=request.headers.get("Last-Event-ID"),
            on_result=_persist_literacy_result,
            thread_id=_make_thread_id(family_id, cid),
        )
    except Exception as e:
        logger.error("Literacy report trigger failed for task %s: %s", task_id, e)
        error_msg = "读写周报服务异常"
        error_event = f"event: error\ndata: {json.dumps({'error': error_msg})}\n\n"
        end_event = "event: end\ndata: {\"status\": \"error\"}\n\n"

        async def _error_stream():
            yield error_event
            yield end_event

        return StreamingResponse(
            tracked_sse_stream(str(task_id), _error_stream()),
            media_type="text/event-stream",
            headers={"X-Accel-Buffering": "no"},
        )
```

- [ ] **Step 3: Verify existing tests still pass**

Run: `cd server && uv run pytest tests/backend/routers/test_ai_literacy_report.py -v`
Expected: All PASS

- [ ] **Step 4: Run lint**

Run: `cd server && uv run ruff check apps/backend/app/routers/ai_literacy_report.py`
Run: `cd server && uv run ruff format apps/backend/app/routers/ai_literacy_report.py`
Expected: Clean

- [ ] **Step 5: Commit**

```bash
git add server/apps/backend/app/routers/ai_literacy_report.py
git commit -m "refactor(backend): simplify ai_literacy_report router with trigger_and_stream()

Replace ~30 lines of SSE lifecycle boilerplate with single
trigger_and_stream() call. Passes custom thread_id for
child-scoped event persistence.

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>"
```

---

### Task 6: Full Verification

**Files:** No new changes — verification only

- [ ] **Step 1: Run full agent test suite**

Run: `cd server && uv run pytest tests/agent/ -v`
Expected: All PASS — no regressions in dispatch, RunPipeline, worker tests

- [ ] **Step 2: Run full backend test suite**

Run: `cd server && uv run pytest tests/backend/ -v`
Expected: All PASS — no regressions in router, bridge consumer, service tests

- [ ] **Step 3: Run lint across all changed files**

Run:
```bash
cd server && uv run ruff check \
  apps/agent/services/runtime/worker.py \
  apps/backend/app/services/bridge_consumer.py \
  apps/backend/app/routers/ai_report.py \
  apps/backend/app/routers/ai_finance_coach.py \
  apps/backend/app/routers/ai_literacy_report.py
```
Expected: Clean

- [ ] **Step 4: Run mypy on changed agent code**

Run: `cd server && uv run mypy apps/agent/services/runtime/worker.py --exclude vendor`
Expected: No new type errors

- [ ] **Step 5: Verify line count reduction**

Run:
```bash
wc -l server/apps/agent/services/runtime/worker.py
```
Expected: ~1946 lines (down from ~2116, ~170 line reduction)

Run:
```bash
for f in ai_report ai_finance_coach ai_literacy_report; do
  echo -n "$f: "; wc -l < "server/apps/backend/app/routers/$f.py"
done
```
Compare with pre-refactor counts to verify ~30 lines removed per router.

- [ ] **Step 6: Verify `learning_child.py` was NOT modified**

Run: `git diff HEAD -- server/apps/backend/app/routers/learning_child.py`
Expected: Empty diff — this file is explicitly excluded from the refactor
