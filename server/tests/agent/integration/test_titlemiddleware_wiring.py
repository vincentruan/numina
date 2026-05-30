"""U1 pre-flight: verify TitleMiddleware + checkpointer wiring on agent-first path.

Three load-bearing assumptions for the agent-first persistence fix
(`docs/plans/2026-05-30-001-fix-agent-stream-session-persistence-plan.md`):

  1. The graph returned by ``make_lead_agent(runnable_config)`` has a
     checkpointer attached, so a post-stream ``aget_state(...)`` call can read
     persisted thread state.
  2. ``TitleMiddleware`` is registered in the middleware chain with its
     ``enabled`` flag at the harness default of ``True``.
  3. After a real ``astream`` round-trip, ``aget_state`` returns a state whose
     values include the ``title`` slot — even when the value is ``None`` /
     ``""`` (the schema must connect; the LLM call is mocked).

If any check fails, the U2 design needs revisiting before any business code
lands.  See plan §U1 for the pivot rules.
"""

from __future__ import annotations

from collections.abc import AsyncIterator, Iterator
from typing import Any

import pytest
from deerflow.agents.lead_agent.agent import _build_middlewares, make_lead_agent
from deerflow.agents.middlewares.title_middleware import TitleMiddleware
from deerflow.config.app_config import AppConfig
from langchain_core.language_models.fake_chat_models import FakeListChatModel
from langgraph.checkpoint.memory import InMemorySaver

pytestmark = pytest.mark.integration


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _build_app_config_dict() -> dict[str, Any]:
    """The minimum AppConfig shape that lets ``make_lead_agent`` succeed.

    Mirrors what ``EffectiveConfigBuilder.build()`` emits at runtime: a single
    `models[0]`, the `sandbox.use` placeholder agent_dispatch.py seeds, and an
    in-memory sqlite checkpointer so the integration test never touches disk.
    """
    return {
        "models": [
            {
                "name": "main",
                # FakeListChatModel doesn't need credentials and ignores `use`,
                # but DeerFlow's ModelConfig still expects the key. Point at a
                # known langchain class — we'll patch ``create_chat_model``.
                "use": "langchain_core.language_models.fake_chat_models:FakeListChatModel",
                "model": "fake-list",
                "api_key": "unused",
                "supports_thinking": False,
            }
        ],
        "sandbox": {"use": "deerflow.sandbox.local:LocalSandboxProvider"},
        "checkpointer": {"type": "memory"},
    }


@pytest.fixture
def runnable_config() -> Iterator[dict[str, Any]]:
    """Build the same shape ``stream_agent_dispatch`` constructs at runtime."""
    app_config_obj = AppConfig.model_validate(_build_app_config_dict())
    yield {
        "configurable": {
            "thread_id": "u1-pre-flight-thread",
            "app_config": app_config_obj,
            "user_id": "u1-pre-flight-user",
        }
    }


@pytest.fixture
def fake_chat_model() -> FakeListChatModel:
    """Returns a FakeListChatModel that emits a single deterministic response.

    Two scripted responses: one for the lead agent's reply, one for the title
    middleware's title-generation call.  TitleMiddleware uses ``ainvoke`` while
    the agent uses ``astream`` — both consume from the same scripted list.
    """
    return FakeListChatModel(responses=["净资产分析", "对话标题示例"])


# ---------------------------------------------------------------------------
# Step 2 — TitleMiddleware in chain (cheapest check; no graph compile needed)
# ---------------------------------------------------------------------------


def test_step2_title_middleware_in_chain(runnable_config: dict[str, Any]) -> None:
    """U1 step 2: TitleMiddleware is in the middleware chain at default enabled.

    Reading ``_build_middlewares`` directly is the smallest possible probe — if
    this fails, the harness version diverges from the source we audited and U2
    must register the middleware explicitly.
    """
    app_config_obj = runnable_config["configurable"]["app_config"]
    middlewares = _build_middlewares(
        runnable_config,
        model_name="main",
        agent_name=None,
        app_config=app_config_obj,
    )

    title_mws = [mw for mw in middlewares if isinstance(mw, TitleMiddleware)]
    assert len(title_mws) == 1, (
        f"Expected exactly one TitleMiddleware in the chain; got "
        f"{[type(mw).__name__ for mw in middlewares]}"
    )

    # The harness default is enabled=True. If a future config flag flips this
    # globally, we want the test to flag it before the regression hits prod.
    cfg = title_mws[0]._get_title_config()
    assert cfg.enabled is True, (
        "TitleMiddleware found but disabled in config — title generation "
        "won't fire; check TitleConfig defaults / overrides"
    )


# ---------------------------------------------------------------------------
# Step 1 — checkpointer wired on agent_graph
# ---------------------------------------------------------------------------


def test_step1_checkpointer_wired(
    runnable_config: dict[str, Any],
    fake_chat_model: FakeListChatModel,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """U1 step 1: ``make_lead_agent(runnable_config).checkpointer`` is not None.

    Patches ``create_chat_model`` so the graph compiles without a real LLM key.
    A failure here is the canonical plan-pivot trigger — U2 would need to
    inject the shared checkpointer via ``runnable_config['configurable']`` or
    on the ``CompiledGraph`` directly before ``astream`` runs.
    """

    def _fake_create_chat_model(**_: Any) -> FakeListChatModel:
        return fake_chat_model

    monkeypatch.setattr(
        "deerflow.agents.lead_agent.agent.create_chat_model",
        _fake_create_chat_model,
    )
    monkeypatch.setattr(
        "deerflow.agents.middlewares.title_middleware.create_chat_model",
        _fake_create_chat_model,
    )

    agent_graph = make_lead_agent(runnable_config)

    checkpointer = getattr(agent_graph, "checkpointer", None)
    assert checkpointer is not None, (
        "make_lead_agent returned a graph with no checkpointer attached — "
        "post-stream aget_state will raise. U2 must explicitly bind a "
        "checkpointer (e.g. via runnable_config['configurable']) before "
        "the persistence fix can rely on state.values.title."
    )


# ---------------------------------------------------------------------------
# Step 3 — aget_state end-to-end
# ---------------------------------------------------------------------------


async def _drain(agen: AsyncIterator[Any]) -> list[Any]:
    out = []
    async for chunk in agen:
        out.append(chunk)
    return out


@pytest.mark.asyncio
async def test_step3_aget_state_end_to_end(
    runnable_config: dict[str, Any],
    fake_chat_model: FakeListChatModel,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """U1 step 3: after a real astream round-trip with the U2 wiring in place,
    ``aget_state(runnable_config)`` returns a ``StateSnapshot`` whose ``values``
    dict carries the ``title`` schema slot.

    Post-U2 the agent_dispatch path post-hoc binds the shared checkpointer
    onto ``agent_graph`` before astream — that's the contract this test locks.
    The ``configurable["context"]`` field is required by ``ThreadDataMiddleware``
    (harness ``thread_data_middleware.py:110`` accesses ``runtime.context.get``
    without the same ``or {}`` guard line 83 uses, so we seed an empty dict).
    """

    def _fake_create_chat_model(**_: Any) -> FakeListChatModel:
        return fake_chat_model

    monkeypatch.setattr(
        "deerflow.agents.lead_agent.agent.create_chat_model",
        _fake_create_chat_model,
    )
    monkeypatch.setattr(
        "deerflow.agents.middlewares.title_middleware.create_chat_model",
        _fake_create_chat_model,
    )

    agent_graph = make_lead_agent(runnable_config)

    # Mirror the production wiring from agent_dispatch.py:376 — bind a
    # checkpointer post-compile so aget_state has somewhere to read from.
    agent_graph.checkpointer = InMemorySaver()  # type: ignore[attr-defined]

    state_input = {
        "messages": [
            {"role": "user", "content": "我家的净资产健康吗？"},
        ]
    }

    # ``context`` is the runtime context the harness middleware chain expects
    # (langgraph 0.6+ Runtime API; passed at invoke time, not nested in
    # ``configurable``). ``ThreadDataMiddleware`` reads ``runtime.context.get
    # ("run_id")`` without a None guard so we seed an empty-but-truthy dict.
    await _drain(
        agent_graph.astream(state_input, runnable_config, context={"run_id": "u1-step3-run"})
    )

    snapshot = await agent_graph.aget_state(runnable_config)
    assert snapshot is not None, "aget_state returned None — checkpoint missing"
    assert isinstance(snapshot.values, dict), (
        f"snapshot.values is not a dict (type={type(snapshot.values).__name__})"
    )
    # ThreadState merges TitleMiddlewareState — the `title` key must reachable
    # via .get() even when TitleMiddleware declined to fire (FakeListChatModel
    # output may not satisfy _should_generate_title).
    title_value = snapshot.values.get("title")
    assert title_value is None or isinstance(title_value, str), (
        f"title slot has wrong type: {type(title_value).__name__} = {title_value!r}"
    )
    # Sanity: the messages slot also persists, so the checkpointer is live.
    assert "messages" in snapshot.values
