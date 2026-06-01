"""U3 unit tests: stream_agent_dispatch session journal writes.

Covers:
- ``session_journal.resolve_path``: public path resolver with ``capability="agent"``
  pin (Chinese agent_name slugs would fail _validate_id).
- ``_persist_session_metadata`` writes ``assistant.message`` and
  ``session.end`` events with redacted content (mirroring orchestrator path).
- Journal write failures are swallowed; backend persistence still proceeds.
- Synchronous ``write_session_start`` + ``write_user_message`` on the agent
  dispatch path are exercised by reading back the JSONL after a fake stream.
"""

from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from apps.agent.services import agent_dispatch
from apps.agent.services.session_journal import SessionJournalService

# ---------------------------------------------------------------------------
# resolve_path
# ---------------------------------------------------------------------------


def test_resolve_path_default_capability_agent(tmp_path: Path) -> None:
    """resolve_path returns ``<base>/<family>/agent/agent/<user>/<sid>.jsonl``."""
    svc = SessionJournalService(tmp_path)

    p = svc.resolve_path(
        family_id="100",
        session_id="sess-abc",
        user_id="42",
    )

    expected = tmp_path / "100" / "agent" / "agent" / "42" / "sess-abc.jsonl"
    assert p == expected


def test_resolve_path_rejects_invalid_ids(tmp_path: Path) -> None:
    """Path slug validation matches DeerFlow's regex; Chinese agent names fail."""
    svc = SessionJournalService(tmp_path)

    with pytest.raises(ValueError):
        svc.resolve_path(
            family_id="100",
            session_id="sess-abc",
            capability="数鸣",  # rejected by _validate_id
            user_id="42",
        )

    with pytest.raises(ValueError):
        svc.resolve_path(
            family_id="../etc",  # path traversal
            session_id="sess-abc",
        )


def test_resolve_path_default_user_segment_is_shared(tmp_path: Path) -> None:
    """Default user_id is ``_shared`` for anonymous flows."""
    svc = SessionJournalService(tmp_path)
    p = svc.resolve_path(family_id="100", session_id="sess-1")
    assert "/_shared/" in str(p)


# ---------------------------------------------------------------------------
# _persist_session_metadata journal writes
# ---------------------------------------------------------------------------


class _FakeStateGraph:
    """Minimal stand-in exposing ``aget_state``."""

    def __init__(self, *, values: dict[str, Any] | None = None) -> None:
        self._values = values

    async def aget_state(self, _config: dict[str, Any]) -> Any:
        return SimpleNamespace(values=dict(self._values or {}))


@pytest.fixture
def captured_journal(monkeypatch: pytest.MonkeyPatch) -> list[dict[str, Any]]:
    """Replace session_journal with a recorder that captures append_event calls."""
    captured: list[dict[str, Any]] = []

    class _RecordingJournal:
        def write_session_start(self, **kwargs: Any) -> None:
            captured.append({"event": "session.start", **kwargs})

        def write_user_message(self, **kwargs: Any) -> None:
            captured.append({"event": "user.message", **kwargs})

        def write_assistant_message(self, **kwargs: Any) -> None:
            captured.append({"event": "assistant.message", **kwargs})

        def write_session_end(self, **kwargs: Any) -> None:
            captured.append({"event": "session.end", **kwargs})

        def resolve_path(self, **kwargs: Any) -> Path:
            return Path(
                "/fake/sessions/"
                + kwargs["family_id"]
                + "/agent/"
                + kwargs.get("capability", "agent")
                + "/"
                + kwargs.get("user_id", "_shared")
                + "/"
                + kwargs["session_id"]
                + ".jsonl"
            )

    monkeypatch.setattr(
        "apps.agent.services.agent_dispatch.session_journal",
        _RecordingJournal(),
    )
    return captured


@pytest.fixture
def quiet_repo(monkeypatch: pytest.MonkeyPatch) -> None:
    """Stub the backend repo so we don't try to reach a real backend."""

    class _Noop:
        async def upsert(self, **_: Any) -> None: ...
        async def update_summary(self, **_: Any) -> None: ...

    monkeypatch.setattr(
        "apps.agent.services.session_store.AiSessionRepository",
        lambda *_a, **_kw: _Noop(),
    )


@pytest.mark.asyncio
async def test_persist_writes_assistant_message_and_session_end(
    captured_journal: list[dict[str, Any]],
    quiet_repo: None,
) -> None:
    """assistant.message + session.end land in the journal with redacted text."""
    graph = _FakeStateGraph(values={"title": "T"})

    await agent_dispatch._persist_session_metadata(
        agent_graph=graph,
        runnable_config={"configurable": {"thread_id": "session-abc"}},
        family_id="100",
        user_id="42",
        session_id="session-abc",
        agent_name="numina",
        answer="您的余额: 6225880100000123 元",
        model_id="claude-sonnet-4-6",
        success=True,
        start_ms=None,
    )

    events = {e["event"]: e for e in captured_journal}
    assert "assistant.message" in events
    assert "session.end" in events

    # PII redaction on the assistant message content.
    assistant = events["assistant.message"]
    assert "6225880100000123" not in assistant["content"]
    assert "[已脱敏]" in assistant["content"]
    assert assistant["model_name"] == "claude-sonnet-4-6"

    end = events["session.end"]
    assert end["success"] is True
    assert end["session_id"] == "session-abc"


@pytest.mark.asyncio
async def test_session_end_records_failure_status(
    captured_journal: list[dict[str, Any]],
    quiet_repo: None,
) -> None:
    """success=False propagates into the journal end event."""
    graph = _FakeStateGraph(values={})

    await agent_dispatch._persist_session_metadata(
        agent_graph=graph,
        runnable_config={"configurable": {"thread_id": "session-abc"}},
        family_id="100",
        user_id=None,
        session_id="session-abc",
        agent_name="numina",
        answer="",
        model_id=None,
        success=False,
        start_ms=None,
    )

    end_events = [e for e in captured_journal if e["event"] == "session.end"]
    assert end_events
    assert end_events[0]["success"] is False
    # No assistant.message when answer is empty.
    assert not any(e["event"] == "assistant.message" for e in captured_journal)


@pytest.mark.asyncio
async def test_journal_write_failure_does_not_block_repo(
    monkeypatch: pytest.MonkeyPatch,
    quiet_repo: None,
) -> None:
    """If session_journal.write_assistant_message raises, repo writes still run."""

    class _BrokenJournal:
        def write_assistant_message(self, **_: Any) -> None:
            raise OSError("disk full")

        def write_session_end(self, **_: Any) -> None:
            raise OSError("disk full")

    repo_called = {"upsert": 0, "update": 0}

    class _Repo:
        async def upsert(self, **_: Any) -> None:
            repo_called["upsert"] += 1

        async def update_summary(self, **_: Any) -> None:
            repo_called["update"] += 1

    monkeypatch.setattr(
        "apps.agent.services.agent_dispatch.session_journal",
        _BrokenJournal(),
    )
    monkeypatch.setattr(
        "apps.agent.services.session_store.AiSessionRepository",
        lambda *_a, **_kw: _Repo(),
    )

    graph = _FakeStateGraph(values={"title": "T"})
    await agent_dispatch._persist_session_metadata(
        agent_graph=graph,
        runnable_config={"configurable": {"thread_id": "session-abc"}},
        family_id="100",
        user_id="42",
        session_id="session-abc",
        agent_name="numina",
        answer="hello",
        model_id="m",
        success=True,
        start_ms=None,
    )

    assert repo_called["upsert"] == 1
    assert repo_called["update"] == 1


# ---------------------------------------------------------------------------
# stream_agent_dispatch sync journal writes (start + user_message)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_stream_dispatch_writes_start_and_user_message_on_disk(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """End-to-end: stream_agent_dispatch writes session.start + user.message
    to the JSONL file before astream runs."""

    # Point session_journal at the temp dir.
    fresh = SessionJournalService(tmp_path)
    monkeypatch.setattr(
        "apps.agent.services.agent_dispatch.session_journal",
        fresh,
    )

    class _FakeAgent:
        def __init__(self) -> None:
            self.checkpointer: Any = None

        async def astream(self, _state: dict[str, Any], _cfg: dict[str, Any], **_kw: Any):
            if False:
                yield None

        async def aget_state(self, _cfg: dict[str, Any]) -> Any:
            return SimpleNamespace(values={"title": "T"})

    monkeypatch.setattr(
        "apps.agent.services.agent_dispatch.make_lead_agent",
        lambda _config: _FakeAgent(),
    )
    monkeypatch.setattr(
        "apps.agent.services.agent_dispatch.AppConfig",
        SimpleNamespace(model_validate=lambda _d: SimpleNamespace()),
    )
    monkeypatch.setattr(
        "apps.agent.services.deerflow_adapter.family_adapter_cache._get_shared_checkpointer",
        lambda *_a, **_k: object(),
    )

    from unittest.mock import AsyncMock

    fake_client = SimpleNamespace(
        get_agent_config=AsyncMock(
            return_value={"agent_name": "numina", "is_enabled": True, "skills": ["chat"]}
        ),
        get_family_ai_config=AsyncMock(
            return_value={
                "providers": [
                    {
                        "config_id": "c1",
                        "ai_provider": "openai",
                        "ai_model_id": "gpt",
                        "api_key": "k",
                    }
                ]
            }
        ),
        get_enabled_skills=AsyncMock(return_value=[]),
        get_enabled_mcp_servers=AsyncMock(return_value=[]),
        get_user=AsyncMock(return_value={"display_name": "张三"}),
    )
    monkeypatch.setattr(
        "apps.agent.services.agent_dispatch.BackendClient",
        lambda *_a, **_k: fake_client,
    )
    monkeypatch.setattr(
        "apps.agent.services.agent_dispatch._select_model",
        lambda providers, _task_type: (providers[0], "gpt", []),
    )
    monkeypatch.setattr(
        "apps.agent.services.agent_dispatch.EffectiveConfigBuilder",
        lambda _pm: SimpleNamespace(
            build=lambda **_kw: SimpleNamespace(config_dict={}, extensions_config_path="", skill_sources=[])
        ),
    )

    user_msg = "请帮我看看 13900001234 这条号码的对账单"

    out: list[str] = []
    async for chunk in agent_dispatch.stream_agent_dispatch(
        agent_id=100000000000005,
        family_id="100",
        user_id="42",
        thread_id="session-abc",
        message=user_msg,
    ):
        out.append(chunk)

    jsonl = tmp_path / "100" / "agent" / "agent" / "42" / "session-abc.jsonl"
    assert jsonl.exists(), "JSONL not written by stream_agent_dispatch"
    events = [json.loads(line) for line in jsonl.read_text("utf-8").splitlines() if line.strip()]
    types = [e["type"] for e in events]
    assert "session.start" in types
    assert "user.message" in types

    # Locate the user message and confirm PII redacted.
    user_event = next(e for e in events if e["type"] == "user.message")
    assert "13900001234" not in user_event["content"]
    assert "[已脱敏]" in user_event["content"]
    # Session start carries jsonl_path that matches the on-disk location.
    start_event = next(e for e in events if e["type"] == "session.start")
    assert start_event["jsonlPath"].endswith("session-abc.jsonl")
    assert start_event["capability"] == "agent"
