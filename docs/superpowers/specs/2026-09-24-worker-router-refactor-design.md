# Worker.py + Router Boilerplate Refactor Design

> Date: 2026-09-24
> Branch: `feat/learning-tutor-deerflow-sse`
> Source: Code review items #9 (worker.py dedup) + #10 (router boilerplate dedup)

## Problem

### #9 — worker.py at 2116 lines

Every new app (`numina`, `asset-report`, `import-parse`, `finance-coach`, `wish-advice`, `dashboard-narrative`, `literacy-weekly-report`, `learning-tutor`) adds ~100 lines of near-identical boilerplate. The dispatch block is an 8-branch if/elif chain with identical argument passing.

### #10 — Router boilerplate duplication

3 backend routers (`ai_report.py`, `ai_finance_coach.py`, `ai_literacy_report.py`) copy-paste ~30-40 lines of `trigger_agent_run → extract_run_id → lease_heartbeat → lifecycle_consumer → consume_task_stream → tracked_sse_stream → StreamingResponse`.

Note: `learning_child.py` is **excluded** from this refactor — it uses a fundamentally different SSE lifecycle (`AITaskService.create_task` + `consume_task_stream` without `_lease_heartbeat` or `tracked_sse_stream`, plus `Last-Event-ID` reconnection and session-scoped status queries). See [Scope Exclusions](#scope-exclusions).

## Design: #9 — Generic Runner + Config Registry

### Approach

Extract a `_run_simple_app()` generic runner driven by a per-app config dict. Replace 3 simple runners with config entries. Keep custom runners for the 5 complex apps (including wish-advice, which has significant post-processing).

### Simple vs Complex split

**Simple (→ config-driven):**

| App | Unique params |
|-----|---------------|
| `dashboard-narrative` | `mcp_servers=[]`, `timeout=60`, `thinking=True`, `reasoning_delta=True`, result: `{narrative, thinking}` |
| `literacy-weekly-report` | `timeout=120`, `thinking=True`, `reasoning_delta=True`, result: `{report, thinking}` |
| `learning-tutor` | `timeout=120`, `thinking=False`, `memory=False`, no result event |

These 3 runners share ~90% code: `RunPipeline` setup → `run_skill()` → read `p.ai_text` / `p.thinking_text` → optional `bridge.publish` result event → `_set_session_title`.

**Complex (→ keep as-is):**

| App | Reason to keep custom |
|-----|----------------------|
| `numina` | Chat routing, plan mode, subagent, memory, multi-turn — fundamentally different |
| `asset-report` | 3-step pipeline, custom middleware, JSON result parsing |
| `import-parse` | Custom post-processing, tool_call synthesis, file handling |
| `finance-coach` | Custom result parsing, repair cycle, coach-specific logic |
| `wish-advice` | JSON parse → validate-repair cycle (`run_json_repair_loop`) → LLM extraction fallback → structured `{redistribution[]}` payload (~170 lines post-processing) |

### Config schema

```python
from collections.abc import Callable

# Result builder signature: (ai_text, thinking_text) → payload dict | None
_ResultBuilder = Callable[[str, str], dict[str, Any] | None]

@dataclass(frozen=True)
class _SimpleAppConfig:
    """Per-app config for the generic simple-app runner."""
    app_name: str
    skill_name: str                           # DeerFlow skill (matches SKILL.md name)
    enable_thinking: bool = False
    enable_reasoning_delta: bool = False      # forward reasoning_delta to frontend
    timeout_seconds: int = 120
    mcp_servers: list | None = None           # None = default resolution; [] = no MCP
    memory_enabled: bool = True
    trigger_key: str = ""                     # key into _SYNTHETIC_TRIGGERS_BY_LANG
    result_event_type: str = ""               # "" = no result event (e.g., learning-tutor)
    result_builder: _ResultBuilder | None = None  # builds payload from ai_text + thinking_text
```

### Config registry

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

### Generic runner

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
        mcp_servers=cfg.mcp_servers,       # None → default resolution; [] → no MCP
        skill_name=cfg.skill_name,          # __aenter__ calls set_active_skill internally
    ) as p:
        # Build user message from synthetic trigger + language instruction
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

### Dispatch simplification

Replace the 8-branch if/elif with a dict lookup:

```python
_RUNNERS = {
    "asset-report": _run_asset_report_agent,
    "import-parse": _run_import_parse_agent,
    "finance-coach": _run_finance_coach_agent,
    "wish-advice": _run_wish_advice_agent,
    "numina": _run_numina_agent,
}

# In run_agent:
if app in _SIMPLE_APPS:
    await _run_simple_app(_SIMPLE_APPS[app], bridge=bridge, ...)
elif app in _RUNNERS:
    await _RUNNERS[app](bridge=bridge, ...)
else:
    raise ValueError(f"Unknown app: {app}")
```

### Estimated impact

- Removes 3 individual runner functions (~80 lines each) = ~240 lines
- Adds config registry + generic runner (~70 lines)
- Net reduction: ~170 lines from worker.py (2116 → ~1946)

---

## Design: #10 — `trigger_and_stream()` Helper

### Current pattern (repeated in 3 routers)

```python
# 1. Trigger agent
result = await trigger_agent_run(
    agent_client=agent_client, agent_url=agent_url,
    json_body=agent_trigger_body, task_id=task_id, family_id=family_id,
)
run_id = result["run_id"]

# 2. Attach run_id to task
AITaskService.extract_and_attach_run_id(task_id, result["content_location"], family_id)

# 3. Lease heartbeat
_hb_stop = asyncio.Event()
_hb_task = asyncio.create_task(_lease_heartbeat(task_id, family_id, _hb_stop))

# 4. Lifecycle consumer
_spawn_lifecycle_consumer(
    task_id=task_id, family_id=family_id, run_id=run_id,
    bridge=shared_bridge, thread_id=session_id,
)

# 5. SSE forwarder
stream_gen = consume_task_stream(
    task_id=task_id, family_id=family_id,
    last_event_id=last_event_id, run_id=run_id, bridge=shared_bridge,
)

async def _stream_with_cleanup():
    try:
        async for chunk in stream_gen:
            yield chunk
    finally:
        _hb_stop.set()
        _hb_task.cancel()

return StreamingResponse(
    tracked_sse_stream(task_id, _stream_with_cleanup()),
    media_type="text/event-stream",
    headers={"X-Accel-Buffering": "no"},
)
```

### Proposed helper

In `bridge_consumer.py`:

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
) -> StreamingResponse:
    """Full SSE lifecycle: trigger agent → heartbeat → lifecycle consumer → stream.

    Encapsulates the common pattern shared by ai_report, ai_finance_coach,
    and ai_literacy_report routers.

    Note: learning_child.py is NOT included — it has a different SSE lifecycle
    (no heartbeat, no tracked_sse_stream, uses consume_task_stream with
    Last-Event-ID reconnection, and manages its own DB session).
    """
    # 1. Trigger agent
    result = await trigger_agent_run(
        agent_client=agent_client, agent_url=agent_url,
        json_body=json_body, task_id=task_id, family_id=family_id,
    )
    run_id = result["run_id"]

    # 2. Attach run_id to task
    AITaskService.extract_and_attach_run_id(task_id, result["content_location"], family_id)

    # 3. Lease heartbeat
    _hb_stop = asyncio.Event()
    _hb_task = asyncio.create_task(_lease_heartbeat(task_id, family_id, _hb_stop))

    # 4. Lifecycle consumer
    shared_bridge = get_shared_bridge()
    _spawn_lifecycle_consumer(
        task_id=task_id, family_id=family_id, run_id=run_id,
        bridge=shared_bridge, thread_id=session_id,
    )

    # 5. SSE forwarder with cleanup
    stream_gen = consume_task_stream(
        task_id=task_id, family_id=family_id,
        last_event_id=last_event_id, run_id=run_id, bridge=shared_bridge,
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

### Router simplification

Each router reduces from ~30 lines to:

```python
return await trigger_and_stream(
    agent_client=agent_client,
    agent_url=f"/internal/gateway/runs/asset-report/{session_id}",
    json_body=agent_trigger_body,
    task_id=str(task_id),
    family_id=family_id,
    session_id=session_id,
    last_event_id=request.headers.get("Last-Event-ID"),
)
```

### Estimated impact

- 3 routers × ~30 lines saved = ~90 lines eliminated
- Single point of change for lifecycle behavior

---

## Risk Assessment

| Risk | Mitigation |
|------|-----------|
| Generic runner misses app-specific edge case | Keep existing runners as reference; add integration test per app |
| `result_builder` callback too rigid for future apps | Apps with complex result logic (JSON repair, multi-step) stay as custom runners |
| `trigger_and_stream` changes SSE behavior | Behavioral parity test: compare SSE output before/after |
| Dispatch dict misses an app | Unknown app → `ValueError` (fail-fast, not silent fallback) |
| Config dataclass `mcp_servers` semantics unclear | `None` = default resolution (per-family config); `[]` = explicitly no MCP |

## Scope Exclusions

- `learning_child.py` — excluded from #10 refactor; uses different SSE lifecycle (no `_lease_heartbeat`, no `tracked_sse_stream`, has `Last-Event-ID` reconnection, session-scoped status queries, and dual-mode endpoint)
- OQ-10/11 (frontend type dedup) — separate PR, lower priority
- #15, #18 — already fixed in separate commits
- Agent-native gaps — future work
