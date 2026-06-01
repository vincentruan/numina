"""Automated smoke test: POST /agent/{id}/stream → backend persistence side-effects.

Replaces the manual ``pnpm dev + curl`` step from the plan §Verification.
Mounts the real FastAPI agent app via ``TestClient``, hits the agent stream
endpoint, and asserts:

- The response yields a valid NDJSON stream
- ``stream_agent_dispatch`` writes ``session.start`` + ``user.message`` to the
  on-disk JSONL before astream
- ``_persist_session_metadata`` writes ``assistant.message`` + ``session.end``
  to the JSONL after the stream
- ``AiSessionRepository.upsert`` + ``update_summary`` get called with the
  redacted title, summary, status, last_model

The DeerFlow harness call (``make_lead_agent`` + ``astream``) is mocked so
the test runs without an LLM key; everything else (router, dispatch,
persistence helpers, JSONL writes) is real.
"""

from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock

import pytest
from fastapi.testclient import TestClient

from apps.agent.app.config import settings
from apps.agent.app.main import app
from apps.agent.services.session_journal import SessionJournalService


class _FakeAgent:
    """Minimal CompiledStateGraph stand-in honouring the post-U2 contract."""

    def __init__(self) -> None:
        self.checkpointer: Any = None

    async def astream(
        self,
        _state: dict[str, Any],
        _cfg: dict[str, Any],
        **_kw: Any,
    ):
        # Yield one assistant text chunk so the answer-streaming branch fires
        # and answer_parts ends up non-empty.
        yield {
            "agent": {
                "messages": [
                    SimpleNamespace(content="您的余额: 6225880100000123 元")
                ]
            }
        }

    async def aget_state(self, _config: dict[str, Any]) -> Any:
        return SimpleNamespace(values={"title": "余额查询"})


class _Repo:
    def __init__(self) -> None:
        self.upsert_calls: list[dict[str, Any]] = []
        self.update_calls: list[dict[str, Any]] = []

    async def upsert(self, **kwargs: Any) -> None:
        self.upsert_calls.append(kwargs)

    async def update_summary(self, **kwargs: Any) -> None:
        self.update_calls.append(kwargs)


@pytest.fixture
def smoke_env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> dict[str, Any]:
    """Wire all the seams ``stream_agent_dispatch`` touches.

    Returns a handles dict so individual tests can read back the recorded
    state (``repo``, ``journal_dir``, ``client``).
    """
    monkeypatch.setattr(settings, "AGENT_INTERNAL_TOKEN", "tok")

    journal_dir = tmp_path / "sessions"
    real_journal = SessionJournalService(journal_dir)
    monkeypatch.setattr(
        "apps.agent.services.agent_dispatch.session_journal", real_journal
    )

    repo = _Repo()
    monkeypatch.setattr(
        "apps.agent.services.session_store.AiSessionRepository",
        lambda *_a, **_kw: repo,
    )

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

    fake_backend = SimpleNamespace(
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
                        "ai_model_id": "gpt-test",
                        "api_key": "k",
                    }
                ]
            }
        ),
        get_enabled_skills=AsyncMock(return_value=[]),
        get_enabled_mcp_servers=AsyncMock(return_value=[]),
        get_user=AsyncMock(return_value={"display_name": "测试用户"}),
    )
    monkeypatch.setattr(
        "apps.agent.services.agent_dispatch.BackendClient",
        lambda *_a, **_k: fake_backend,
    )
    monkeypatch.setattr(
        "apps.agent.services.agent_dispatch._select_model",
        lambda providers, _task_type: (providers[0], "gpt-test", []),
    )
    monkeypatch.setattr(
        "apps.agent.services.agent_dispatch.EffectiveConfigBuilder",
        lambda _pm: SimpleNamespace(
            build=lambda **_kw: SimpleNamespace(config_dict={}, extensions_config_path="", skill_sources=[])
        ),
    )

    client = TestClient(app)
    return {"client": client, "repo": repo, "journal_dir": journal_dir}


def test_smoke_stream_endpoint_persists_redacted_metadata(
    smoke_env: dict[str, Any],
) -> None:
    """End-to-end smoke: POST /agent/100000000000005/stream → jsonl + repo."""
    client = smoke_env["client"]

    response = client.post(
        "/agent/100000000000005/stream",
        json={
            "message": "请帮我查 13900001234 这条号码的余额",
            "thread_id": "smoke-session-1",
            "enable_thinking": False,
            "web_search": False,
            "reasoning_effort": "medium",
        },
        headers={
            "X-Family-Id": "100",
            "X-User-Id": "42",
            "X-Agent-Token": "tok",
            "X-Thread-Id": "smoke-session-1",
        },
    )

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("application/x-ndjson")

    lines = [line for line in response.text.splitlines() if line.strip()]
    assert lines, "no NDJSON body received"
    parsed = [json.loads(line) for line in lines]
    # At minimum a phase event and an end event should land.
    types = {evt.get("type") for evt in parsed}
    assert "capability.end" in types or any(
        evt.get("type", "").startswith("capability.") for evt in parsed
    )

    # ── JSONL on disk ─────────────────────────────────────────────────────
    journal_dir: Path = smoke_env["journal_dir"]
    jsonl = journal_dir / "100" / "agent" / "agent" / "42" / "smoke-session-1.jsonl"
    assert jsonl.exists(), (
        f"JSONL not written; tree: "
        f"{[p.relative_to(journal_dir) for p in journal_dir.rglob('*') if p.is_file()]}"
    )
    journal_events = [json.loads(line) for line in jsonl.read_text("utf-8").splitlines() if line.strip()]
    journal_types = [e["type"] for e in journal_events]
    assert "session.start" in journal_types
    assert "user.message" in journal_types
    assert "assistant.message" in journal_types
    assert "session.end" in journal_types

    # ── PII scrubbed in the persisted user message ─────────────────────────
    user_event = next(e for e in journal_events if e["type"] == "user.message")
    assert "13900001234" not in user_event["content"]
    assert "[已脱敏]" in user_event["content"]

    # ── PII scrubbed in the persisted assistant message ───────────────────
    assistant_event = next(
        e for e in journal_events if e["type"] == "assistant.message"
    )
    assert "6225880100000123" not in assistant_event["content"]

    # ── Backend repo round-trip ────────────────────────────────────────────
    repo: _Repo = smoke_env["repo"]
    assert len(repo.upsert_calls) == 1
    assert repo.upsert_calls[0]["session_id"] == "smoke-session-1"
    assert repo.upsert_calls[0]["last_model"] == "gpt-test"
    assert len(repo.update_calls) == 1
    update = repo.update_calls[0]
    assert update["title"] == "余额查询"
    assert update["status"] == "completed"
    assert "6225880100000123" not in update["summary"]
    assert "[已脱敏]" in update["summary"]


def test_smoke_rejects_invalid_token(smoke_env: dict[str, Any]) -> None:
    """The router still enforces ``X-Agent-Token``."""
    response = smoke_env["client"].post(
        "/agent/100000000000005/stream",
        json={"message": "hi"},
        headers={
            "X-Family-Id": "100",
            "X-User-Id": "42",
            "X-Agent-Token": "wrong-token",
        },
    )
    assert response.status_code == 401
