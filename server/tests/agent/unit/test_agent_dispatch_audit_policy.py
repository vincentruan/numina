"""C3 regression: stream_agent_dispatch satisfies agent/CLAUDE.md
Key Invariants #2 (policy_guard.check) and #3 (audit_logger emit).

Both invariants must fire on every code path — success, policy denial,
config error, stream error. Audit emit must never raise.
"""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from apps.agent.services import agent_dispatch
from apps.agent.services.audit_logger import AuditEntry


async def _drain(agen) -> list[str]:
    out = []
    async for chunk in agen:
        out.append(chunk)
    return out


def _wire_seams(
    monkeypatch: pytest.MonkeyPatch,
    *,
    ai_config_overrides: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Wire backend / config / model-selection seams for stream_agent_dispatch."""
    base_ai_config: dict[str, Any] = {
        "ai_enabled": True,
        "allowed_capabilities": [],
        "admin_only_capabilities": [],
        "member_role": "member",
        "providers": [
            {
                "config_id": "c1",
                "ai_provider": "openai",
                "ai_model_id": "gpt",
                "api_key": "k",
            }
        ],
    }
    if ai_config_overrides:
        base_ai_config.update(ai_config_overrides)

    fake_client = SimpleNamespace(
        get_agent_config=AsyncMock(
            return_value={
                "agent_name": "numina",
                "is_enabled": True,
                "skills": ["chat"],
            }
        ),
        get_family_ai_config=AsyncMock(return_value=base_ai_config),
        get_enabled_skills=AsyncMock(return_value=[]),
        get_enabled_mcp_servers=AsyncMock(return_value=[]),
        get_user=AsyncMock(return_value={"display_name": "u"}),
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
    monkeypatch.setattr(
        "apps.agent.services.deerflow_adapter.family_adapter_cache._get_shared_checkpointer",
        lambda *_a, **_k: object(),
    )
    return {"client": fake_client}


@pytest.fixture
def captured_audit(monkeypatch: pytest.MonkeyPatch) -> list[AuditEntry]:
    """Replace audit_logger with a recorder."""
    captured: list[AuditEntry] = []

    class _Recorder:
        def log_call(self, entry: AuditEntry) -> None:
            captured.append(entry)

    monkeypatch.setattr(
        "apps.agent.services.agent_dispatch.audit_logger", _Recorder()
    )
    return captured


@pytest.fixture
def captured_policy(monkeypatch: pytest.MonkeyPatch) -> list[tuple]:
    """Replace policy_guard.check with a spy that allows by default."""
    calls: list[tuple] = []
    real_check = agent_dispatch.policy_guard.check

    class _Spy:
        def check(self, policy, capability):
            calls.append((policy, capability))
            return real_check(policy, capability)

    monkeypatch.setattr(
        "apps.agent.services.agent_dispatch.policy_guard", _Spy()
    )
    return calls


# ---------------------------------------------------------------------------
# Invariant #2: policy_guard.check is called before make_lead_agent
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_policy_guard_called_with_agent_name_as_capability(
    monkeypatch: pytest.MonkeyPatch,
    captured_policy: list[tuple],
    captured_audit: list[AuditEntry],
) -> None:
    _wire_seams(monkeypatch)

    class _FakeAgent:
        def __init__(self) -> None:
            self.checkpointer: Any = None

        async def astream(self, _state, _cfg, **_kw):
            if False:
                yield None

        async def aget_state(self, _cfg):
            return SimpleNamespace(values={})

    monkeypatch.setattr(
        "apps.agent.services.agent_dispatch.make_lead_agent",
        lambda _config: _FakeAgent(),
    )

    await _drain(
        agent_dispatch.stream_agent_dispatch(
            agent_id=100000000000005,
            family_id="100",
            user_id="42",
            thread_id="audit-success",
            message="hi",
        )
    )

    assert captured_policy, "policy_guard.check was not called"
    _policy, capability = captured_policy[0]
    assert capability == "numina"


@pytest.mark.asyncio
async def test_policy_denial_short_circuits_with_audit(
    monkeypatch: pytest.MonkeyPatch,
    captured_audit: list[AuditEntry],
) -> None:
    """If the family has ai_enabled=False, dispatch must short-circuit before
    make_lead_agent is called and audit log a PolicyDenied entry."""
    _wire_seams(monkeypatch, ai_config_overrides={"ai_enabled": False})

    create_called = {"called": False}

    def _explode(_config: Any) -> Any:
        create_called["called"] = True
        raise AssertionError("make_lead_agent must not be called after policy denial")

    monkeypatch.setattr(
        "apps.agent.services.agent_dispatch.make_lead_agent", _explode
    )

    chunks = await _drain(
        agent_dispatch.stream_agent_dispatch(
            agent_id=100000000000005,
            family_id="100",
            user_id="42",
            thread_id="audit-deny",
            message="hi",
        )
    )

    assert not create_called["called"]
    assert any('"code":"POLICY_DENIED"' in c for c in chunks)

    assert captured_audit, "audit log not emitted on policy denial"
    last = captured_audit[-1]
    assert last.success is False
    assert last.error_type == "PolicyDenied"
    assert last.family_id == "100"


# ---------------------------------------------------------------------------
# Invariant #3: audit_logger.log_call fires on every terminal path
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_audit_emitted_on_success(
    monkeypatch: pytest.MonkeyPatch,
    captured_audit: list[AuditEntry],
) -> None:
    _wire_seams(monkeypatch)

    class _FakeAgent:
        def __init__(self) -> None:
            self.checkpointer: Any = None

        async def astream(self, _state, _cfg, **_kw):
            if False:
                yield None

        async def aget_state(self, _cfg):
            return SimpleNamespace(values={})

    monkeypatch.setattr(
        "apps.agent.services.agent_dispatch.make_lead_agent",
        lambda _config: _FakeAgent(),
    )

    await _drain(
        agent_dispatch.stream_agent_dispatch(
            agent_id=100000000000005,
            family_id="100",
            user_id="42",
            thread_id="audit-success",
            message="hi",
        )
    )

    assert captured_audit, "audit log not emitted on success path"
    last = captured_audit[-1]
    assert last.success is True
    assert last.error_type is None
    assert last.deerflow_attempted is True
    assert last.capability == "numina"
    assert last.family_id == "100"
    assert last.user_id == "42"
    assert last.duration_ms is not None
    assert last.duration_ms >= 0


@pytest.mark.asyncio
async def test_audit_emitted_when_agent_config_fetch_fails(
    monkeypatch: pytest.MonkeyPatch,
    captured_audit: list[AuditEntry],
) -> None:
    seams = _wire_seams(monkeypatch)
    seams["client"].get_agent_config = AsyncMock(
        side_effect=RuntimeError("backend down")
    )

    await _drain(
        agent_dispatch.stream_agent_dispatch(
            agent_id=100000000000005,
            family_id="100",
            user_id="42",
            thread_id="audit-cfg-err",
            message="hi",
        )
    )

    assert captured_audit, "audit log not emitted on agent_config error"
    last = captured_audit[-1]
    assert last.success is False
    assert last.error_type == "AgentConfigError"
    assert last.deerflow_attempted is False


@pytest.mark.asyncio
async def test_audit_emitted_when_stream_raises(
    monkeypatch: pytest.MonkeyPatch,
    captured_audit: list[AuditEntry],
) -> None:
    _wire_seams(monkeypatch)

    class _ExplodingAgent:
        def __init__(self) -> None:
            self.checkpointer: Any = None

        async def astream(self, _state, _cfg, **_kw):
            raise RuntimeError("upstream provider 5xx")
            if False:  # pragma: no cover
                yield None

        async def aget_state(self, _cfg):
            return SimpleNamespace(values={})

    monkeypatch.setattr(
        "apps.agent.services.agent_dispatch.make_lead_agent",
        lambda _config: _ExplodingAgent(),
    )

    await _drain(
        agent_dispatch.stream_agent_dispatch(
            agent_id=100000000000005,
            family_id="100",
            user_id="42",
            thread_id="audit-stream-err",
            message="hi",
        )
    )

    last = captured_audit[-1]
    assert last.success is False
    assert last.error_type == "RuntimeError"
    assert last.deerflow_attempted is True


@pytest.mark.asyncio
async def test_audit_failure_never_breaks_main_path(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """If audit_logger.log_call itself raises, dispatch must complete normally
    and the user-visible NDJSON stream must not see the audit error."""
    _wire_seams(monkeypatch)

    boom = MagicMock(side_effect=RuntimeError("audit infra down"))
    monkeypatch.setattr(
        "apps.agent.services.agent_dispatch.audit_logger",
        SimpleNamespace(log_call=boom),
    )

    class _FakeAgent:
        def __init__(self) -> None:
            self.checkpointer: Any = None

        async def astream(self, _state, _cfg, **_kw):
            if False:
                yield None

        async def aget_state(self, _cfg):
            return SimpleNamespace(values={})

    monkeypatch.setattr(
        "apps.agent.services.agent_dispatch.make_lead_agent",
        lambda _config: _FakeAgent(),
    )

    chunks = await _drain(
        agent_dispatch.stream_agent_dispatch(
            agent_id=100000000000005,
            family_id="100",
            user_id="42",
            thread_id="audit-broken-infra",
            message="hi",
        )
    )

    assert chunks, "stream produced no output"
    # Audit was attempted at least once.
    assert boom.call_count >= 1
    # No audit error string leaks into the user stream.
    blob = "".join(chunks)
    assert "audit infra down" not in blob
