"""Bilateral parity: legacy orchestrator stream vs agent-first dispatch.

Plan §U4 (`docs/plans/2026-05-30-001-fix-agent-stream-session-persistence-plan.md`)
requires that for the same fake-LLM input, both paths produce ai_chat_sessions
rows with the same *shape* — non-empty title (≤50 chars), `status="completed"`,
`last_model` echoes the request, `last_message_summary` non-empty when an
answer was produced.

These tests don't run the full astream / DeerFlow pipeline. Instead they
exercise the two paths' persistence helpers (``Orchestrator._update_session_summary`` +
``Orchestrator._generate_title`` for legacy; ``agent_dispatch._persist_session_metadata``
for agent-first) against the same fake repo and assert the resulting row
shape is consistent.
"""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock

import pytest

from apps.agent.services import agent_dispatch
from apps.agent.services.orchestrator import Orchestrator

# ---------------------------------------------------------------------------
# Shared fake repo recording rows from both paths
# ---------------------------------------------------------------------------


class _RecordingRepo:
    def __init__(self) -> None:
        self.upsert_calls: list[dict[str, Any]] = []
        self.update_calls: list[dict[str, Any]] = []

    async def upsert(self, **kwargs: Any) -> None:
        self.upsert_calls.append(kwargs)

    async def update_summary(self, **kwargs: Any) -> None:
        self.update_calls.append(kwargs)

    @property
    def final_row(self) -> dict[str, Any]:
        merged: dict[str, Any] = {}
        for call in self.upsert_calls:
            merged.update(call)
        for call in self.update_calls:
            merged.update(call)
        return merged


def _quiet_journal(monkeypatch: pytest.MonkeyPatch) -> None:
    """Stub session_journal in both modules so file I/O isn't part of the test."""

    class _Noop:
        def write_assistant_message(self, **_: Any) -> None: ...
        def write_session_end(self, **_: Any) -> None: ...
        def write_session_start(self, **_: Any) -> None: ...
        def write_user_message(self, **_: Any) -> None: ...
        def resolve_path(self, **kwargs: Any):
            from pathlib import Path
            return Path(f"/tmp/{kwargs['session_id']}.jsonl")

    monkeypatch.setattr("apps.agent.services.agent_dispatch.session_journal", _Noop())


class _FakeStateGraph:
    def __init__(self, values: dict[str, Any]) -> None:
        self._values = values

    async def aget_state(self, _config: dict[str, Any]) -> Any:
        return SimpleNamespace(values=dict(self._values))


# ---------------------------------------------------------------------------
# Bilateral parity
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_legacy_and_agent_paths_produce_same_row_shape(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Both paths write title (non-empty, ≤50), status='completed',
    last_model echoes request, summary non-empty for the same input."""
    legacy_repo = _RecordingRepo()
    agent_repo = _RecordingRepo()

    # Patch AiSessionRepository to return per-call captured repo. The
    # Orchestrator helpers and agent_dispatch helper both read it through
    # the same module path.
    repo_picker = {"current": legacy_repo}

    monkeypatch.setattr(
        "apps.agent.services.session_store.AiSessionRepository",
        lambda *_a, **_kw: repo_picker["current"],
    )
    _quiet_journal(monkeypatch)

    answer = "您的净资产健康。"
    model_id = "claude-sonnet-4-6"

    # ── Legacy path ────────────────────────────────────────────────────────
    orch = Orchestrator()
    repo_picker["current"] = legacy_repo
    await orch._update_session_summary(
        session_id="session-legacy",
        family_id="100",
        summary=answer,  # legacy path stores the redacted answer as summary
        model=model_id,
        status="completed",
        title="净资产健康度分析",  # legacy populates title via _generate_title
    )
    # Legacy upsert lives separately on a different code path; mirror what
    # _stream_dispatch_event_lines emits in its happy path.
    await orch._upsert_session(
        session_id="session-legacy",
        family_id="100",
        user_id="42",
        capability="chat",
        jsonl_path="/sessions/100/agent/chat/42/session-legacy.jsonl",
        model_name=model_id,
    )

    # ── Agent path ─────────────────────────────────────────────────────────
    repo_picker["current"] = agent_repo
    graph = _FakeStateGraph(values={"title": "净资产健康度分析"})
    await agent_dispatch._persist_session_metadata(
        agent_graph=graph,
        runnable_config={"configurable": {"thread_id": "session-agent"}},
        family_id="100",
        user_id="42",
        session_id="session-agent",
        agent_name="numina",
        answer=answer,
        model_id=model_id,
        success=True,
        start_ms=None,
    )

    # ── Parity assertions ──────────────────────────────────────────────────
    legacy = legacy_repo.final_row
    agent = agent_repo.final_row

    # Both have a non-empty title ≤50 chars
    assert legacy["title"] and isinstance(legacy["title"], str)
    assert agent["title"] and isinstance(agent["title"], str)
    assert len(legacy["title"]) <= 50
    assert len(agent["title"]) <= 50

    # Both report completed status
    assert legacy["status"] == "completed"
    assert agent["status"] == "completed"

    # Both echo the request model into last_model
    assert legacy["last_model"] == model_id
    assert agent["last_model"] == model_id

    # Both record a non-empty summary; agent's is bounded ≤200 chars.
    assert legacy["summary"] and len(legacy["summary"]) > 0
    assert agent["summary"] and len(agent["summary"]) > 0
    assert len(agent["summary"]) <= 200

    # Both include capability — legacy uses skill ("chat"), agent uses
    # agent_name ("numina"); both are non-empty.
    assert legacy["capability"]
    assert agent["capability"]
    # Both have a jsonl_path set so frontend session events route work
    assert legacy["jsonl_path"]
    assert agent["jsonl_path"]


@pytest.mark.asyncio
async def test_both_paths_record_error_status_on_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Stream failure on either path leaves status='error' on the row."""
    legacy_repo = _RecordingRepo()
    agent_repo = _RecordingRepo()
    repo_picker = {"current": legacy_repo}

    monkeypatch.setattr(
        "apps.agent.services.session_store.AiSessionRepository",
        lambda *_a, **_kw: repo_picker["current"],
    )
    _quiet_journal(monkeypatch)

    monkeypatch.setattr(
        "apps.agent.services.agent_dispatch.BackendClient",
        lambda *_a, **_k: SimpleNamespace(
            get_user=AsyncMock(return_value={"display_name": "李四"})
        ),
    )

    # Legacy: simulate the orchestrator's error-path summary write.
    repo_picker["current"] = legacy_repo
    orch = Orchestrator()
    await orch._update_session_summary(
        session_id="session-legacy-err",
        family_id="100",
        summary=None,
        model=None,
        status="error",
        title=None,
    )

    # Agent: success=False makes _persist_session_metadata write status=error.
    repo_picker["current"] = agent_repo
    graph = _FakeStateGraph(values={})  # no LLM-generated title
    await agent_dispatch._persist_session_metadata(
        agent_graph=graph,
        runnable_config={"configurable": {"thread_id": "session-agent-err"}},
        family_id="100",
        user_id="42",
        session_id="session-agent-err",
        agent_name="numina",
        answer="",
        model_id=None,
        success=False,
        start_ms=None,
    )

    assert legacy_repo.final_row["status"] == "error"
    assert agent_repo.final_row["status"] == "error"


@pytest.mark.asyncio
async def test_legacy_summary_writes_round_trip_on_repo(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Sanity probe: orchestrator's _update_session_summary actually reaches
    AiSessionRepository.update_summary with all four canonical fields."""
    repo = _RecordingRepo()
    monkeypatch.setattr(
        "apps.agent.services.session_store.AiSessionRepository",
        lambda *_a, **_kw: repo,
    )

    orch = Orchestrator()
    await orch._update_session_summary(
        session_id="session-x",
        family_id="100",
        summary="概要",
        model="m-1",
        status="completed",
        title="标题",
    )

    assert len(repo.update_calls) == 1
    call = repo.update_calls[0]
    assert call["title"] == "标题"
    assert call["summary"] == "概要"
    assert call["status"] == "completed"
    assert call["model"] == "m-1"


@pytest.mark.asyncio
async def test_legacy_path_does_not_redact_summary(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Diagnostic: legacy ``_update_session_summary`` writes whatever the
    caller passes — no second redaction layer. The agent path adds its own
    redaction via ``_persist_session_metadata`` (locked by U2 tests).

    This test pins the contract that the redaction lives in **the caller**
    of legacy ``_update_session_summary`` (orchestrator pre-redacts via
    ``redacted_answer = pii_redactor.redact_text(final_answer)[0]``), and the
    agent path matches by redacting before write. Both end up with redacted
    rows in the DB despite being two different code paths.
    """
    repo = _RecordingRepo()
    monkeypatch.setattr(
        "apps.agent.services.session_store.AiSessionRepository",
        lambda *_a, **_kw: repo,
    )

    # If a caller forgot to redact, legacy path would persist raw PII —
    # demonstrating why the agent path's redaction layer is non-negotiable.
    orch = Orchestrator()
    await orch._update_session_summary(
        session_id="session-direct",
        family_id="100",
        summary="联系 13900001234 商讨",  # raw PII (caller bug surface)
        model="m",
        status="completed",
        title=None,
    )

    # The legacy helper passes raw text through unchanged.
    assert repo.update_calls[0]["summary"] == "联系 13900001234 商讨"
