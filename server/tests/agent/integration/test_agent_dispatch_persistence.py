"""U4 parity tests: agent path persists records that match the legacy
orchestrator path's shape contract.

The legacy ``/chat/ask/stream`` path already writes ``title``,
``last_message_summary``, ``status``, ``last_model`` to ai_chat_sessions via
``orchestrator._update_session_summary`` + ``orchestrator._generate_title``.
U2/U3 added equivalent writes to the agent-first path.  These tests lock the
contract: for the same fake-LLM input, the agent path produces records of the
same *shape* the legacy path produces — non-empty title ≤50 chars, status in
{"completed", "error"}, last_model echoes the request model, summary present
when an answer was emitted.

These tests don't run the legacy orchestrator (its full stream_dispatch needs
a wired family adapter cache and a real DeerFlowAdapter — out of scope here).
The orchestrator side of the contract is locked by the existing
``tests/agent/integration/test_orchestrator_pipeline.py`` suite.  These tests
focus on agent path's *output shape* matching what the legacy path produces.

Also covers Open Question #1: same thread_id used across both paths leaves
the backend record in a consistent final state with PII redacted.
"""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock

import pytest

from apps.agent.services import agent_dispatch


class _FakeStateGraph:
    def __init__(self, *, values: dict[str, Any] | None = None) -> None:
        self._values = values

    async def aget_state(self, _config: dict[str, Any]) -> Any:
        return SimpleNamespace(values=dict(self._values or {}))


class _RecordingRepo:
    """In-memory repo capturing the final-state row written by both paths."""

    def __init__(self) -> None:
        self.upsert_calls: list[dict[str, Any]] = []
        self.update_calls: list[dict[str, Any]] = []

    async def upsert(self, **kwargs: Any) -> None:
        self.upsert_calls.append(kwargs)

    async def update_summary(self, **kwargs: Any) -> None:
        self.update_calls.append(kwargs)

    @property
    def final_row(self) -> dict[str, Any]:
        """The row state after all writes — last update_summary wins per Risks
        table assumption (agent path runs after backend's append_message)."""
        merged: dict[str, Any] = {}
        for call in self.upsert_calls:
            merged.update(call)
        for call in self.update_calls:
            merged.update(call)
        return merged


@pytest.fixture
def fake_repo(monkeypatch: pytest.MonkeyPatch) -> _RecordingRepo:
    repo = _RecordingRepo()
    monkeypatch.setattr(
        "apps.agent.services.session_store.AiSessionRepository",
        lambda *_a, **_kw: repo,
    )
    return repo


@pytest.fixture
def quiet_journal(monkeypatch: pytest.MonkeyPatch) -> None:
    """Stub the journal so file I/O isn't part of these contract tests."""

    class _Noop:
        def write_assistant_message(self, **_: Any) -> None: ...
        def write_session_end(self, **_: Any) -> None: ...
        def write_session_start(self, **_: Any) -> None: ...
        def write_user_message(self, **_: Any) -> None: ...
        def resolve_path(self, **kwargs: Any):
            from pathlib import Path
            return Path(f"/tmp/{kwargs['session_id']}.jsonl")

    monkeypatch.setattr(
        "apps.agent.services.agent_dispatch.session_journal",
        _Noop(),
    )


# ---------------------------------------------------------------------------
# Contract: persisted row shape matches the four canonical fields
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_agent_path_writes_full_canonical_shape(
    fake_repo: _RecordingRepo,
    quiet_journal: None,
) -> None:
    """Agent path produces a row with all four canonical fields populated."""
    graph = _FakeStateGraph(values={"title": "净资产健康度分析"})

    await agent_dispatch._persist_session_metadata(
        agent_graph=graph,
        runnable_config={"configurable": {"thread_id": "session-shape"}},
        family_id="100",
        user_id="42",
        session_id="session-shape",
        agent_name="numina",
        answer="您的净资产健康。",
        model_id="claude-sonnet-4-6",
        success=True,
        start_ms=None,
    )

    row = fake_repo.final_row

    # title: non-empty, ≤50 chars
    assert isinstance(row["title"], str)
    assert row["title"]
    assert len(row["title"]) <= 50

    # status: completed for success path
    assert row["status"] == "completed"

    # last_model echoes request
    assert row["last_model"] == "claude-sonnet-4-6"
    assert row["model"] == "claude-sonnet-4-6"

    # summary: present and bounded
    assert isinstance(row["summary"], str)
    assert len(row["summary"]) <= 200

    # capability is the agent name (legacy uses skill name; both are non-empty)
    assert row["capability"] == "numina"


@pytest.mark.asyncio
async def test_agent_path_status_error_when_stream_fails(
    fake_repo: _RecordingRepo,
    quiet_journal: None,
) -> None:
    """Failed stream → status=error, summary may be None when no answer streamed."""
    graph = _FakeStateGraph(values={"title": None})

    monkeypatch_backend_user = SimpleNamespace(
        get_user=AsyncMock(return_value={"display_name": "李四"})
    )
    import unittest.mock as _mock

    with _mock.patch(
        "apps.agent.services.agent_dispatch.BackendClient",
        lambda *_a, **_k: monkeypatch_backend_user,
    ):
        await agent_dispatch._persist_session_metadata(
            agent_graph=graph,
            runnable_config={"configurable": {"thread_id": "session-err"}},
            family_id="100",
            user_id="42",
            session_id="session-err",
            agent_name="numina",
            answer="",
            model_id="m",
            success=False,
            start_ms=None,
        )

    row = fake_repo.final_row
    assert row["status"] == "error"
    assert row["summary"] is None
    # Title falls back to date+name template — still non-empty.
    assert row["title"]


# ---------------------------------------------------------------------------
# Title length cap — even pathologically long state titles are bounded
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_long_state_title_is_truncated_to_fifty_chars(
    fake_repo: _RecordingRepo,
    quiet_journal: None,
) -> None:
    """LLM-emitted title >50 chars must be truncated, not rejected."""
    long_title = "这是一个非常非常非常非常非常非常非常非常非常长的标题" * 5
    graph = _FakeStateGraph(values={"title": long_title})

    await agent_dispatch._persist_session_metadata(
        agent_graph=graph,
        runnable_config={"configurable": {"thread_id": "session-long"}},
        family_id="100",
        user_id="42",
        session_id="session-long",
        agent_name="numina",
        answer="",
        model_id="m",
        success=True,
        start_ms=None,
    )

    row = fake_repo.final_row
    assert len(row["title"]) <= 50
    # Truncation preserves the prefix — easier to reason about than ellipsis.
    assert row["title"] == long_title[:50]


# ---------------------------------------------------------------------------
# Open Question #1: same thread_id reused across paths
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_agent_writes_overwrite_prior_legacy_writes(
    fake_repo: _RecordingRepo,
    quiet_journal: None,
) -> None:
    """Simulates the legacy path writing first (e.g. via backend
    ChatSessionService.append_message), then the agent path running for the
    same thread_id. Final row reflects agent's intent and PII is redacted —
    matching the Risks-table assumption.
    """
    # 1. Legacy-style prior write: imagine backend put status='running' and
    #    a non-redacted summary on the row before agent's persistence ran.
    fake_repo.update_calls.append({
        "session_id": "session-shared",
        "family_id": "100",
        "summary": "联系 13900001234 谈合作",  # un-redacted (legacy bug surface)
        "model": "legacy-model",
        "status": "running",
        "title": None,
    })

    # 2. Agent path runs over the same session_id.
    graph = _FakeStateGraph(values={"title": "合作详情"})
    await agent_dispatch._persist_session_metadata(
        agent_graph=graph,
        runnable_config={"configurable": {"thread_id": "session-shared"}},
        family_id="100",
        user_id="42",
        session_id="session-shared",
        agent_name="numina",
        answer="可以联系 13900001234 完成对接。",  # contains PII to test redaction
        model_id="claude-sonnet-4-6",
        success=True,
        start_ms=None,
    )

    row = fake_repo.final_row

    # Agent path's writes win on the canonical fields.
    assert row["status"] == "completed"
    assert row["model"] == "claude-sonnet-4-6"
    assert row["title"] == "合作详情"

    # PII is redacted in the latest summary write — even though the legacy
    # entry was un-redacted, the final state is clean.
    assert "13900001234" not in row["summary"]
    assert "[已脱敏]" in row["summary"]


# ---------------------------------------------------------------------------
# Multi-turn: existing title is replaced when state has a new one
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_existing_title_replaced_when_state_has_new_one(
    fake_repo: _RecordingRepo,
    quiet_journal: None,
) -> None:
    """In a multi-turn scenario, TitleMiddleware short-circuits and
    state.values.title still holds the prior value. The agent path should
    persist that value rather than overwriting with a fallback."""
    # Pretend a prior title exists in DB.
    fake_repo.update_calls.append({
        "session_id": "session-multi",
        "family_id": "100",
        "summary": None,
        "model": None,
        "status": "completed",
        "title": "首轮标题",
    })

    graph = _FakeStateGraph(values={"title": "首轮标题"})
    await agent_dispatch._persist_session_metadata(
        agent_graph=graph,
        runnable_config={"configurable": {"thread_id": "session-multi"}},
        family_id="100",
        user_id="42",
        session_id="session-multi",
        agent_name="numina",
        answer="第二轮回答",
        model_id="m",
        success=True,
        start_ms=None,
    )

    row = fake_repo.final_row
    # Title preserved across turns (no clobber to fallback template).
    assert row["title"] == "首轮标题"
    # Summary updates with the latest turn's answer.
    assert row["summary"] == "第二轮回答"
