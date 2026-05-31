"""U2 unit tests: stream_agent_dispatch session persistence.

Covers the helpers introduced for the agent-first persistence fix
(`docs/plans/2026-05-30-001-fix-agent-stream-session-persistence-plan.md`):

- ``_persist_session_metadata``: reads ``state.values.title`` via
  ``aget_state``, redacts both title and answer through ``pii_redactor``,
  upserts the session, and writes summary/status. All failure paths log
  warnings without raising.
- ``_build_fallback_title``: produces ``YYYY-MM-DD <agent_name> <user_name>``,
  sourcing user_name from ``BackendClient.get_user`` (with safe defaults).

These tests do not run the actual stream — they exercise the helpers
directly with a fake `agent_graph` so the persistence contract is locked
without requiring a real LLM round-trip.
"""

from __future__ import annotations

import time
from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock

import pytest

from apps.agent.services import agent_dispatch

# ---------------------------------------------------------------------------
# Fakes
# ---------------------------------------------------------------------------


class _FakeStateGraph:
    """Minimal stand-in for a CompiledStateGraph exposing ``aget_state``."""

    def __init__(self, *, values: dict[str, Any] | None = None, raises: Exception | None = None) -> None:
        self._values = values
        self._raises = raises

    async def aget_state(self, _config: dict[str, Any]) -> Any:
        if self._raises is not None:
            raise self._raises
        return SimpleNamespace(values=dict(self._values or {}))


class _SyncOnlyStateGraph:
    """Older-langgraph shape: only ``get_state`` (sync), no ``aget_state``."""

    def __init__(self, *, values: dict[str, Any] | None = None) -> None:
        self._values = values

    def get_state(self, _config: dict[str, Any]) -> Any:
        return SimpleNamespace(values=dict(self._values or {}))


class _RecordingRepo:
    """In-memory repo capturing the calls _persist_session_metadata emits."""

    def __init__(self) -> None:
        self.upsert_calls: list[dict[str, Any]] = []
        self.update_calls: list[dict[str, Any]] = []

    async def upsert(self, **kwargs: Any) -> None:
        self.upsert_calls.append(kwargs)

    async def update_summary(self, **kwargs: Any) -> None:
        self.update_calls.append(kwargs)


@pytest.fixture
def fake_repo(monkeypatch: pytest.MonkeyPatch) -> _RecordingRepo:
    """Patch AiSessionRepository so we observe the persistence calls."""
    repo = _RecordingRepo()
    monkeypatch.setattr(
        "apps.agent.services.session_store.AiSessionRepository",
        lambda *_args, **_kwargs: repo,
    )
    return repo


@pytest.fixture
def runnable_config() -> dict[str, Any]:
    return {"configurable": {"thread_id": "session-abc", "user_id": "u-1"}}


# ---------------------------------------------------------------------------
# happy path
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_happy_path_persists_redacted_title_and_summary(
    fake_repo: _RecordingRepo,
    runnable_config: dict[str, Any],
) -> None:
    """When state has a title, both title and summary are redacted and written."""
    graph = _FakeStateGraph(values={"title": "净资产分析"})

    await agent_dispatch._persist_session_metadata(
        agent_graph=graph,
        runnable_config=runnable_config,
        family_id="100",
        user_id="42",
        session_id="session-abc",
        agent_name="numina",
        answer="您的净资产健康。",
        model_id="claude-sonnet-4-6",
        success=True,
    )

    assert len(fake_repo.upsert_calls) == 1
    upsert = fake_repo.upsert_calls[0]
    assert upsert["session_id"] == "session-abc"
    assert upsert["family_id"] == "100"
    assert upsert["user_id"] == "42"
    assert upsert["capability"] == "numina"
    assert upsert["last_model"] == "claude-sonnet-4-6"
    assert "/100/agent/agent/42/session-abc.jsonl" in upsert["jsonl_path"]

    assert len(fake_repo.update_calls) == 1
    update = fake_repo.update_calls[0]
    assert update["title"] == "净资产分析"
    assert update["summary"] == "您的净资产健康。"
    assert update["status"] == "completed"
    assert update["model"] == "claude-sonnet-4-6"


# ---------------------------------------------------------------------------
# PII redaction
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_title_with_html_tags_is_stripped_before_persist(
    fake_repo: _RecordingRepo,
    runnable_config: dict[str, Any],
) -> None:
    """HTML-like tags in the LLM-generated title must be stripped before
    landing in ai_chat_sessions.title — defence-in-depth in case a future
    frontend uses v-html. Plan §Risks row 6."""
    graph = _FakeStateGraph(
        values={"title": "<script>alert(1)</script>净资产<b>分析</b>"}
    )

    await agent_dispatch._persist_session_metadata(
        agent_graph=graph,
        runnable_config=runnable_config,
        family_id="100",
        user_id="42",
        session_id="session-html",
        agent_name="numina",
        answer="",
        model_id="m",
        success=True,
    )

    title = fake_repo.update_calls[0]["title"]
    assert "<script>" not in title
    assert "</script>" not in title
    assert "<b>" not in title
    assert "</b>" not in title
    # Tag *content* (the alert call) is left after stripping; an injected
    # script tag becomes inert text, but the body remains. Test that the
    # readable portion survives so the title isn't reduced to nothing.
    assert "净资产" in title
    assert "分析" in title


@pytest.mark.asyncio
async def test_title_with_pii_is_redacted_before_persist(
    fake_repo: _RecordingRepo,
    runnable_config: dict[str, Any],
) -> None:
    """Phone numbers in the LLM-generated title must not leak to backend."""
    graph = _FakeStateGraph(values={"title": "联系 13900001234 商讨"})

    await agent_dispatch._persist_session_metadata(
        agent_graph=graph,
        runnable_config=runnable_config,
        family_id="100",
        user_id="42",
        session_id="session-abc",
        agent_name="numina",
        answer="",
        model_id="m",
        success=True,
    )

    title = fake_repo.update_calls[0]["title"]
    assert "13900001234" not in title
    assert "[已脱敏]" in title


@pytest.mark.asyncio
async def test_summary_with_pii_is_redacted_before_persist(
    fake_repo: _RecordingRepo,
    runnable_config: dict[str, Any],
) -> None:
    """PII in the streamed answer must not leak into ai_chat_sessions.summary."""
    graph = _FakeStateGraph(values={"title": "T"})
    answer_with_pii = "请联系 13900001234 或 6225880100000123 完成转账。"

    await agent_dispatch._persist_session_metadata(
        agent_graph=graph,
        runnable_config=runnable_config,
        family_id="100",
        user_id="42",
        session_id="session-abc",
        agent_name="numina",
        answer=answer_with_pii,
        model_id="m",
        success=True,
    )

    summary = fake_repo.update_calls[0]["summary"]
    assert "13900001234" not in summary
    assert "6225880100000123" not in summary


# ---------------------------------------------------------------------------
# fallback title
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_empty_title_falls_back_to_date_template(
    fake_repo: _RecordingRepo,
    runnable_config: dict[str, Any],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """state.values.title=None → 'YYYY-MM-DD numina <user_name>' fallback."""
    graph = _FakeStateGraph(values={"title": None})

    fake_client = SimpleNamespace(
        get_user=AsyncMock(return_value={"display_name": "张三"})
    )
    monkeypatch.setattr(
        "apps.agent.services.agent_dispatch.BackendClient",
        lambda **_: fake_client,
    )

    await agent_dispatch._persist_session_metadata(
        agent_graph=graph,
        runnable_config=runnable_config,
        family_id="100",
        user_id="42",
        session_id="session-abc",
        agent_name="numina",
        answer="",
        model_id="m",
        success=True,
    )

    title = fake_repo.update_calls[0]["title"]
    today = time.strftime("%Y-%m-%d", time.localtime())
    assert title.startswith(today)
    assert "numina" in title
    assert "张三" in title


@pytest.mark.asyncio
async def test_fallback_title_uses_anon_when_user_lookup_fails(
    fake_repo: _RecordingRepo,
    runnable_config: dict[str, Any],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Backend user lookup error → '匿名用户' rather than crashing."""
    graph = _FakeStateGraph(values={})

    fake_client = SimpleNamespace(
        get_user=AsyncMock(side_effect=RuntimeError("backend down"))
    )
    monkeypatch.setattr(
        "apps.agent.services.agent_dispatch.BackendClient",
        lambda **_: fake_client,
    )

    await agent_dispatch._persist_session_metadata(
        agent_graph=graph,
        runnable_config=runnable_config,
        family_id="100",
        user_id="42",
        session_id="session-abc",
        agent_name="numina",
        answer="",
        model_id="m",
        success=True,
    )

    title = fake_repo.update_calls[0]["title"]
    assert "匿名用户" in title


# ---------------------------------------------------------------------------
# status: error path
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_failed_stream_writes_status_error(
    fake_repo: _RecordingRepo,
    runnable_config: dict[str, Any],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """success=False ⇒ status='error' and summary may be None when answer empty."""
    graph = _FakeStateGraph(values={"title": "T"})
    monkeypatch.setattr(
        "apps.agent.services.agent_dispatch.BackendClient",
        lambda **_: SimpleNamespace(get_user=AsyncMock(return_value=None)),
    )

    await agent_dispatch._persist_session_metadata(
        agent_graph=graph,
        runnable_config=runnable_config,
        family_id="100",
        user_id=None,
        session_id="session-abc",
        agent_name="numina",
        answer="",
        model_id=None,
        success=False,
    )

    update = fake_repo.update_calls[0]
    assert update["status"] == "error"
    assert update["summary"] is None


# ---------------------------------------------------------------------------
# aget_state error handling
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_aget_state_no_checkpointer_falls_back(
    fake_repo: _RecordingRepo,
    runnable_config: dict[str, Any],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """ValueError('No checkpointer set') triggers the fallback title path
    rather than re-raising."""
    graph = _FakeStateGraph(raises=ValueError("No checkpointer set"))

    monkeypatch.setattr(
        "apps.agent.services.agent_dispatch.BackendClient",
        lambda **_: SimpleNamespace(get_user=AsyncMock(return_value={"display_name": "李四"})),
    )

    await agent_dispatch._persist_session_metadata(
        agent_graph=graph,
        runnable_config=runnable_config,
        family_id="100",
        user_id="42",
        session_id="session-abc",
        agent_name="numina",
        answer="",
        model_id="m",
        success=True,
    )

    # Persistence still happened — falling back to date+name template.
    assert fake_repo.update_calls
    title = fake_repo.update_calls[0]["title"]
    assert "李四" in title


@pytest.mark.asyncio
async def test_sync_only_get_state_is_supported(
    fake_repo: _RecordingRepo,
    runnable_config: dict[str, Any],
) -> None:
    """When the graph only exposes sync get_state, the helper proxies via
    run_in_executor instead of crashing."""
    graph = _SyncOnlyStateGraph(values={"title": "测试标题"})

    await agent_dispatch._persist_session_metadata(
        agent_graph=graph,
        runnable_config=runnable_config,
        family_id="100",
        user_id="42",
        session_id="session-abc",
        agent_name="numina",
        answer="",
        model_id="m",
        success=True,
    )

    assert fake_repo.update_calls[0]["title"] == "测试标题"


@pytest.mark.asyncio
async def test_repo_failure_does_not_raise(
    runnable_config: dict[str, Any],
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Backend error during update_summary is logged at WARNING and swallowed.

    The log line must NOT contain str(e) — exception payloads can include
    full state / message history.
    """
    graph = _FakeStateGraph(values={"title": "T"})

    class _BoomRepo:
        async def upsert(self, **_: Any) -> None:
            raise RuntimeError("boom-with-secrets-in-payload")

        async def update_summary(self, **_: Any) -> None:
            raise RuntimeError("boom-with-secrets-in-payload")

    monkeypatch.setattr(
        "apps.agent.services.session_store.AiSessionRepository",
        lambda *_a, **_kw: _BoomRepo(),
    )

    with caplog.at_level("WARNING", logger="apps.agent.services.agent_dispatch"):
        await agent_dispatch._persist_session_metadata(
            agent_graph=graph,
            runnable_config=runnable_config,
            family_id="100",
            user_id="42",
            session_id="session-abc",
            agent_name="numina",
            answer="",
            model_id="m",
            success=True,
        )

    # Locate the agent_dispatch warning (other modules may also log).
    relevant = [r for r in caplog.records if r.name == "apps.agent.services.agent_dispatch"]
    assert relevant, "expected a warning from agent_dispatch"
    # Must not leak the exception's str representation in the log message.
    for record in relevant:
        assert "boom-with-secrets-in-payload" not in record.getMessage()


# ---------------------------------------------------------------------------
# Decision 6 regression: checkpointer is post-hoc settable on CompiledStateGraph
# ---------------------------------------------------------------------------


def test_compiled_state_graph_checkpointer_is_post_hoc_settable() -> None:
    """Locks Decision 6's load-bearing assumption: ``CompiledStateGraph`` allows
    assigning ``.checkpointer`` after compile.

    If a future langgraph upgrade changes this contract, this test fails first
    and we revisit Decision 6's trade-off.
    """
    from langchain.agents import create_agent
    from langchain_core.language_models.fake_chat_models import FakeListChatModel
    from langgraph.checkpoint.memory import InMemorySaver

    graph = create_agent(model=FakeListChatModel(responses=["x"]), tools=[])
    assert getattr(graph, "checkpointer", None) is None

    saver = InMemorySaver()
    graph.checkpointer = saver  # type: ignore[attr-defined]

    assert graph.checkpointer is saver


# ---------------------------------------------------------------------------
# stream_agent_dispatch wires shared checkpointer
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_stream_dispatch_binds_shared_checkpointer(
    monkeypatch: pytest.MonkeyPatch,
    fake_repo: _RecordingRepo,
) -> None:
    """End-to-end: stream_agent_dispatch assigns ``_get_shared_checkpointer()``
    onto ``agent_graph.checkpointer`` before the astream loop runs."""

    captured: dict[str, Any] = {}
    sentinel_checkpointer = object()

    class _FakeAgent:
        def __init__(self) -> None:
            self.checkpointer: Any = None

        async def astream(self, _state: dict[str, Any], _cfg: dict[str, Any], **_kw: Any):
            # When astream begins, U2 must already have wired the checkpointer.
            captured["checkpointer_at_astream"] = self.checkpointer
            if False:
                yield None  # generator type-marker; loop body never executes

        async def aget_state(self, _cfg: dict[str, Any]) -> Any:
            return SimpleNamespace(values={"title": "T"})

    fake_agent = _FakeAgent()

    monkeypatch.setattr(
        "apps.agent.services.agent_dispatch.make_lead_agent",
        lambda _config: fake_agent,
    )
    # AppConfig.model_validate would explode on our minimal dict; bypass it.
    monkeypatch.setattr(
        "apps.agent.services.agent_dispatch.AppConfig",
        SimpleNamespace(model_validate=lambda _d: SimpleNamespace()),
    )
    monkeypatch.setattr(
        "apps.agent.services.deerflow_adapter.family_adapter_cache._get_shared_checkpointer",
        lambda *_a, **_k: sentinel_checkpointer,
    )

    # Stub the BackendClient calls stream_agent_dispatch makes pre-stream so the
    # function reaches the make_lead_agent branch.
    fake_client = SimpleNamespace(
        get_agent_config=AsyncMock(return_value={"agent_name": "numina", "is_enabled": True, "skills": ["chat"]}),
        get_family_ai_config=AsyncMock(return_value={"providers": [{"config_id": "c1", "ai_provider": "openai", "ai_model_id": "gpt", "api_key": "k"}]}),
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

    # EffectiveConfigBuilder.build returns an object with .config_dict
    monkeypatch.setattr(
        "apps.agent.services.agent_dispatch.EffectiveConfigBuilder",
        lambda _pm: SimpleNamespace(
            build=lambda **_kw: SimpleNamespace(config_dict={})
        ),
    )

    out = []
    async for chunk in agent_dispatch.stream_agent_dispatch(
        agent_id=100000000000005,
        family_id="100",
        user_id="42",
        thread_id="session-abc",
        message="hi",
    ):
        out.append(chunk)

    assert captured.get("checkpointer_at_astream") is sentinel_checkpointer
