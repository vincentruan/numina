"""Tests for _run_finance_coach_agent error-publish fix (U1).

Verifies three branches after the validate→repair→fallback chain:
1. First parse succeeds → publish result, no error
2. Repair loop fails + fallback succeeds → publish result, no error
3. Repair loop fails + fallback fails → publish error, no result
"""

from contextlib import asynccontextmanager
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


def _make_bridge():
    return AsyncMock()


def _make_record():
    record = MagicMock()
    record.run_id = "run-1"
    record.metadata = {"language": "zh"}
    return record


def _make_pipeline_mock(*, ai_text: str = '{"suggestions": []}'):
    """Build a patch target for RunPipeline that yields a mock context.

    Returns (patch_side_effect, context_mock) so tests can inspect ai_text etc.
    """
    ctx = MagicMock()
    ctx.ai_text = ai_text
    ctx.run_id = "run-1"
    ctx.selected_provider = "openai"
    ctx.run_skill = AsyncMock()  # succeeds by default → _coach_ok = True

    @asynccontextmanager
    async def _enter(**_kwargs):
        yield ctx

    return _enter, ctx


_COMMON_PATCHES = {
    "_extract_backend_user_message": 'apps.agent.services.runtime.worker._extract_backend_user_message',
    "_set_session_title": 'apps.agent.services.runtime.worker._set_session_title',
    "_track_task": 'apps.agent.services.runtime.worker._track_task',
    "extract_coach_snapshot_ids": 'apps.agent.services.runtime.worker.extract_coach_snapshot_ids',
    "parse_report_json": 'apps.agent.services.runtime.worker.parse_report_json',
    "run_json_repair_loop": 'apps.agent.services.runtime.worker.run_json_repair_loop',
    "extract_json_via_llm": 'apps.agent.services.runtime.worker.extract_json_via_llm',
    "filter_coach_suggestions_by_ids": 'apps.agent.services.runtime.worker.filter_coach_suggestions_by_ids',
    "RunPipeline": 'apps.agent.services.runtime.run_pipeline.RunPipeline',
}


async def _invoke(bridge, record, *, pipeline_side_effect):
    from apps.agent.services.runtime.worker import _run_finance_coach_agent

    await _run_finance_coach_agent(
        bridge=bridge,
        run_manager=MagicMock(),
        record=record,
        family_id="fam1",
        user_id="user1",
        thread_id="thread1",
        graph_input={"messages": [{"role": "user", "content": "{}"}]},
        config={},
    )


def _count_events(bridge, event_type: str):
    """Count bridge.publish calls for a given event_type (2nd positional arg)."""
    return [
        c for c in bridge.publish.call_args_list
        if len(c.args) >= 3 and c.args[1] == event_type
    ]


def _count_custom_type(bridge, custom_type: str):
    """Count bridge.publish('custom', {'type': custom_type, ...}) calls."""
    return [
        c for c in bridge.publish.call_args_list
        if len(c.args) >= 3
        and c.args[1] == "custom"
        and isinstance(c.args[2], dict)
        and c.args[2].get("type") == custom_type
    ]


# ── Branch 1: first parse succeeds ──────────────────────────────────


@pytest.mark.asyncio
async def test_first_parse_success_publishes_result_no_error():
    """run_json_repair_loop returns (parsed, 0) with no errors → result, no error."""
    bridge = _make_bridge()
    record = _make_record()
    pipeline_enter, _ctx = _make_pipeline_mock()

    parsed_result = {"suggestions": [{"id": "s1", "severity": "high", "title": "t",
                                       "action": "a", "target_type": "liability",
                                       "target_id": "s1", "cta_label": "btn"}]}

    with (
        patch(_COMMON_PATCHES["RunPipeline"], side_effect=pipeline_enter),
        patch(_COMMON_PATCHES["_extract_backend_user_message"], return_value='{"snapshot": true}'),
        patch(_COMMON_PATCHES["_set_session_title"], new=AsyncMock()),
        patch(_COMMON_PATCHES["_track_task"]),
        patch(_COMMON_PATCHES["extract_coach_snapshot_ids"], return_value={"s1"}),
        patch(_COMMON_PATCHES["parse_report_json"], return_value=parsed_result),
        # repair loop returns (parsed, 0 repairs) — first parse already valid
        patch(_COMMON_PATCHES["run_json_repair_loop"], new=AsyncMock(return_value=(parsed_result, 0))),
        # validate_coach_json called after repair loop → no errors
        patch("apps.agent.services.runtime.worker.validate_coach_json", return_value=[]),
        patch(_COMMON_PATCHES["filter_coach_suggestions_by_ids"], return_value=(parsed_result, 0)),
    ):
        await _invoke(bridge, record, pipeline_side_effect=pipeline_enter)

    assert len(_count_custom_type(bridge, "finance_coach.result")) == 1
    assert len(_count_events(bridge, "error")) == 0


# ── Branch 2: repair fails + fallback succeeds ─────────────────────


@pytest.mark.asyncio
async def test_fallback_success_publishes_result_no_error():
    """Repair loop exhausted, extract_json_via_llm returns valid JSON → result, no error."""
    bridge = _make_bridge()
    record = _make_record()
    pipeline_enter, _ctx = _make_pipeline_mock(ai_text="broken")

    fallback_result = {"suggestions": [{"id": "s2", "severity": "medium", "title": "t2",
                                         "action": "a2", "target_type": "asset",
                                         "target_id": "s2", "cta_label": "btn2"}]}

    with (
        patch(_COMMON_PATCHES["RunPipeline"], side_effect=pipeline_enter),
        patch(_COMMON_PATCHES["_extract_backend_user_message"], return_value='{"snapshot": true}'),
        patch(_COMMON_PATCHES["_set_session_title"], new=AsyncMock()),
        patch(_COMMON_PATCHES["_track_task"]),
        patch(_COMMON_PATCHES["extract_coach_snapshot_ids"], return_value={"s2"}),
        patch(_COMMON_PATCHES["parse_report_json"], return_value={"bad": "data"}),
        # run_json_repair_loop returns the fallback result after repair attempts
        patch(_COMMON_PATCHES["run_json_repair_loop"], new=AsyncMock(return_value=(fallback_result, 3))),
        # validate_coach_json called after repair loop → no errors (fallback is valid)
        patch("apps.agent.services.runtime.worker.validate_coach_json", return_value=[]),
        patch(_COMMON_PATCHES["extract_json_via_llm"], new=AsyncMock(return_value=fallback_result)),
        patch(_COMMON_PATCHES["filter_coach_suggestions_by_ids"], return_value=(fallback_result, 0)),
    ):
        await _invoke(bridge, record, pipeline_side_effect=pipeline_enter)

    assert len(_count_custom_type(bridge, "finance_coach.result")) == 1
    assert len(_count_events(bridge, "error")) == 0


# ── Branch 3: repair fails + fallback fails ────────────────────────


@pytest.mark.asyncio
async def test_fallback_failure_publishes_error_no_result():
    """Both repair and fallback fail → error event, no result event."""
    bridge = _make_bridge()
    record = _make_record()
    pipeline_enter, _ctx = _make_pipeline_mock(ai_text="broken")

    bad_parsed = {"bad": "data"}
    validation_errors = ["missing id field"]

    with (
        patch(_COMMON_PATCHES["RunPipeline"], side_effect=pipeline_enter),
        patch(_COMMON_PATCHES["_extract_backend_user_message"], return_value='{"snapshot": true}'),
        patch(_COMMON_PATCHES["_set_session_title"], new=AsyncMock()),
        patch(_COMMON_PATCHES["_track_task"]),
        patch(_COMMON_PATCHES["extract_coach_snapshot_ids"], return_value=set()),
        patch(_COMMON_PATCHES["parse_report_json"], return_value=bad_parsed),
        # repair loop returns the bad parsed value + error count
        patch(_COMMON_PATCHES["run_json_repair_loop"], new=AsyncMock(return_value=(bad_parsed, 3))),
        # validate_coach_json still returns errors after repair loop
        patch(
            "apps.agent.services.runtime.worker.validate_coach_json",
            return_value=validation_errors,
        ),
        # fallback returns None → both repair and fallback failed
        patch(_COMMON_PATCHES["extract_json_via_llm"], new=AsyncMock(return_value=None)),
    ):
        await _invoke(bridge, record, pipeline_side_effect=pipeline_enter)

    assert len(_count_events(bridge, "error")) == 1
    assert len(_count_custom_type(bridge, "finance_coach.result")) == 0
