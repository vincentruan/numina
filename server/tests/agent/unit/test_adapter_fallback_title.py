"""Regression tests for adapter fallback-title handling in typed_stream_dispatch.

Bug: on follow-up turns ("追问"), the session title was overwritten with the
follow-up user message text. Root cause: ``typed_stream_dispatch`` replaced the
checkpoint's stale fallback title with ``context.free_text`` (the CURRENT turn's
user message). On follow-up, this overwrote the first-turn LLM title.

Fix: drop the fallback title from values events entirely. The frontend already
has a temp title from ``handleStartChat`` during streaming, and the LLM title
arrives via ``bridge.publish`` after the stream on the first turn.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, AsyncGenerator
from unittest.mock import patch

import pytest

from apps.agent.schemas.context import RedactedContext
from apps.agent.services.deerflow_adapter.adapter import DeerFlowAdapter


@dataclass
class _FakeEvent:
    type: str
    data: Any


def _make_adapter() -> DeerFlowAdapter:
    adapter = DeerFlowAdapter.__new__(DeerFlowAdapter)
    adapter._timeout = 10
    adapter._family_id = "fam_test"
    adapter._ai_config = {}
    adapter._is_family_mode = True
    adapter._config_path = None
    return adapter


def _ctx(free_text: str = "帮我分析资产") -> RedactedContext:
    return RedactedContext(family_id="fam-1", free_text=free_text)


async def _collect_typed(
    raw_events: list[_FakeEvent],
    context: RedactedContext | None = None,
) -> list[tuple[str, dict]]:
    """Run typed_stream_dispatch with mocked raw_stream_dispatch."""
    adapter = _make_adapter()

    async def _mock_raw(*args, **kwargs) -> AsyncGenerator:
        for event in raw_events:
            yield event

    with patch.object(adapter, "raw_stream_dispatch", side_effect=_mock_raw):
        result = []
        async for item in adapter.typed_stream_dispatch(
            "chat", context or _ctx(), "thread-1"
        ):
            result.append(item)
    return result


# ── Regression: follow-up title must not be overwritten ───────────────────────


@pytest.mark.asyncio
async def test_typed_stream_drops_fallback_title_from_values():
    """A fallback title in a values event must be dropped (not forwarded).

    Regression: the old code replaced the fallback with ``context.free_text``,
    which on follow-up turns overwrote the first-turn LLM title with the
    follow-up user message text.
    """
    # Simulate a checkpoint values event carrying the raw JSON wrapper fallback.
    fallback_title = '{"family_id": "123", "free_text": "帮我分析资产"}'
    raw_events = [
        _FakeEvent(type="values", data={"title": fallback_title, "messages": []}),
    ]
    # Follow-up turn — context.free_text is the follow-up message.
    result = await _collect_typed(raw_events, _ctx(free_text="那负债情况呢"))

    values_events = [data for etype, data in result if etype == "values"]
    assert len(values_events) == 1
    # Title must be dropped — not replaced with the follow-up user text.
    assert "title" not in values_events[0], (
        "Fallback title should be dropped from values event, "
        "not replaced with the current user message"
    )


@pytest.mark.asyncio
async def test_typed_stream_preserves_proper_title_in_values():
    """A proper (non-fallback) title in a values event must be forwarded as-is."""
    proper_title = "家庭资产总览"
    raw_events = [
        _FakeEvent(type="values", data={"title": proper_title, "messages": []}),
    ]
    result = await _collect_typed(raw_events)

    values_events = [data for etype, data in result if etype == "values"]
    assert len(values_events) == 1
    assert values_events[0]["title"] == proper_title


@pytest.mark.asyncio
async def test_typed_stream_drops_skill_prefix_fallback_title():
    """Legacy [SKILL:chat]-prefixed fallback titles must also be dropped."""
    fallback_title = '[SKILL:chat]\n{"free_text": "家庭资产负债"}'
    raw_events = [
        _FakeEvent(type="values", data={"title": fallback_title}),
    ]
    result = await _collect_typed(raw_events)

    values_events = [data for etype, data in result if etype == "values"]
    assert len(values_events) == 1
    assert "title" not in values_events[0]


@pytest.mark.asyncio
async def test_typed_stream_values_without_title_passes_through():
    """Values events without a title field pass through unchanged."""
    raw_events = [
        _FakeEvent(type="values", data={"messages": [{"role": "user", "content": "hi"}]}),
    ]
    result = await _collect_typed(raw_events)

    values_events = [data for etype, data in result if etype == "values"]
    assert len(values_events) == 1
    assert "messages" in values_events[0]
    assert "title" not in values_events[0]
