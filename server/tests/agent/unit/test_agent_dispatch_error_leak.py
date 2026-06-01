"""C2 regression: stream_agent_dispatch error events must not leak str(e).

Exception payloads from LLM clients, DeerFlow, and httpx can include the raw
conversation, prompts, internal URLs, or auth headers. The agent path must
return fixed user-facing strings on the wire and log the exception type
server-side via ``logger.warning``.
"""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock

import pytest

from apps.agent.services import agent_dispatch

_SECRET_NEEDLES = [
    "TOKEN_SECRET_DO_NOT_LEAK",
    "AUTHORIZATION_HEADER_LEAK",
    "/internal/private/url",
    "Bearer eyJraWQiOiJsZWFr",
]


async def _drain(agen) -> list[str]:
    out = []
    async for chunk in agen:
        out.append(chunk)
    return out


def _wire_minimal_seams(monkeypatch: pytest.MonkeyPatch) -> dict[str, Any]:
    """Wire the seams stream_agent_dispatch needs before reaching the
    target failure point. Tests override one of these to inject the failure."""
    fake_client = SimpleNamespace(
        get_agent_config=AsyncMock(
            return_value={
                "agent_name": "numina",
                "is_enabled": True,
                "skills": ["chat"],
            }
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
    )
    monkeypatch.setattr(
        "apps.agent.services.agent_dispatch.BackendClient",
        lambda *_a, **_k: fake_client,
    )
    monkeypatch.setattr(
        "apps.agent.services.agent_dispatch._select_model",
        lambda providers, _t: (providers[0], "gpt", []),
    )
    monkeypatch.setattr(
        "apps.agent.services.agent_dispatch.EffectiveConfigBuilder",
        lambda _pm: SimpleNamespace(
            build=lambda **_k: SimpleNamespace(config_dict={}, extensions_config_path="", skill_sources=[])
        ),
    )
    monkeypatch.setattr(
        "apps.agent.services.agent_dispatch.AppConfig",
        SimpleNamespace(model_validate=lambda _d: SimpleNamespace()),
    )
    return {"client": fake_client}


def _assert_no_secret_in_chunks(chunks: list[str]) -> None:
    blob = "".join(chunks)
    for needle in _SECRET_NEEDLES:
        assert needle not in blob, (
            f"Secret '{needle}' leaked into NDJSON: {blob!r}"
        )


@pytest.mark.asyncio
async def test_ai_config_error_does_not_leak_exception_string(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Boom in get_family_ai_config — error event must be the fixed string."""
    seams = _wire_minimal_seams(monkeypatch)
    seams["client"].get_family_ai_config = AsyncMock(
        side_effect=RuntimeError(
            "TOKEN_SECRET_DO_NOT_LEAK Bearer eyJraWQiOiJsZWFr at /internal/private/url"
        )
    )

    chunks = await _drain(
        agent_dispatch.stream_agent_dispatch(
            agent_id=100000000000005,
            family_id="100",
            user_id="42",
            thread_id="leak-test-1",
            message="hi",
        )
    )

    _assert_no_secret_in_chunks(chunks)
    assert any('"code":"AI_CONFIG_ERROR"' in c for c in chunks)


@pytest.mark.asyncio
async def test_agent_create_error_does_not_leak_exception_string(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Boom in make_lead_agent — error event must be the fixed string."""
    _wire_minimal_seams(monkeypatch)
    monkeypatch.setattr(
        "apps.agent.services.deerflow_adapter.family_adapter_cache._get_shared_checkpointer",
        lambda *_a, **_k: object(),
    )

    def _explode(_config: Any) -> Any:
        raise RuntimeError(
            "TOKEN_SECRET_DO_NOT_LEAK in deerflow init at /internal/private/url"
        )

    monkeypatch.setattr(
        "apps.agent.services.agent_dispatch.make_lead_agent", _explode
    )

    chunks = await _drain(
        agent_dispatch.stream_agent_dispatch(
            agent_id=100000000000005,
            family_id="100",
            user_id="42",
            thread_id="leak-test-2",
            message="hi",
        )
    )

    _assert_no_secret_in_chunks(chunks)
    assert any('"code":"AGENT_CREATE_ERROR"' in c for c in chunks)


@pytest.mark.asyncio
async def test_stream_error_does_not_leak_exception_string(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Boom inside the astream loop — error event must be the fixed string."""
    _wire_minimal_seams(monkeypatch)
    monkeypatch.setattr(
        "apps.agent.services.deerflow_adapter.family_adapter_cache._get_shared_checkpointer",
        lambda *_a, **_k: object(),
    )

    class _ExplodingAgent:
        def __init__(self) -> None:
            self.checkpointer: Any = None

        async def astream(self, _state, _cfg, **_kw):
            raise RuntimeError(
                "AUTHORIZATION_HEADER_LEAK in upstream provider call to /internal/private/url"
            )
            if False:  # pragma: no cover — generator marker
                yield None

        async def aget_state(self, _cfg):
            return SimpleNamespace(values={})

    monkeypatch.setattr(
        "apps.agent.services.agent_dispatch.make_lead_agent",
        lambda _config: _ExplodingAgent(),
    )

    chunks = await _drain(
        agent_dispatch.stream_agent_dispatch(
            agent_id=100000000000005,
            family_id="100",
            user_id="42",
            thread_id="leak-test-3",
            message="hi",
        )
    )

    _assert_no_secret_in_chunks(chunks)
    assert any('"code":"STREAM_ERROR"' in c for c in chunks)


@pytest.mark.asyncio
async def test_error_path_logs_exception_type_server_side(
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """The same boom must produce a server-side WARNING log carrying the
    exception type (no payload), so SREs can correlate without leaking PII."""
    seams = _wire_minimal_seams(monkeypatch)

    class _DistinctType(RuntimeError):
        pass

    seams["client"].get_family_ai_config = AsyncMock(
        side_effect=_DistinctType("TOKEN_SECRET_DO_NOT_LEAK")
    )

    with caplog.at_level("WARNING", logger="apps.agent.services.agent_dispatch"):
        await _drain(
            agent_dispatch.stream_agent_dispatch(
                agent_id=100000000000005,
                family_id="100",
                user_id="42",
                thread_id="leak-test-log",
                message="hi",
            )
        )

    relevant = [
        r for r in caplog.records
        if r.name == "apps.agent.services.agent_dispatch"
    ]
    assert relevant, "expected a server-side warning"
    msgs = [r.getMessage() for r in relevant]
    # The exception type appears so SREs can grep — but the payload doesn't.
    assert any("_DistinctType" in m for m in msgs)
    for m in msgs:
        assert "TOKEN_SECRET_DO_NOT_LEAK" not in m
