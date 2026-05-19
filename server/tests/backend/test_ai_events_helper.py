"""Tests for _ai_events_helper.proxy_capability_events.

Verifies the corrected task state machine (R1):
  running -> post_processing -> completed/failed
and the parse+write+audit chain.
"""

from datetime import datetime
from typing import AsyncIterator
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from apps.backend.app.models.ai_extraction_audit import AIExtractionAudit
from apps.backend.app.models.user import User
from apps.backend.app.utils.snowflake import next_id
from packages.db.models.ai_task import AITask
from packages.db.models.family import Family


@pytest.fixture
def family(db):
    fam = Family(id=next_id(), name="EventsHelperFamily", created_by=next_id())
    db.add(fam)
    db.commit()
    return fam


@pytest.fixture
def user(db, family):
    u = User(
        id=next_id(),
        username="eh_user",
        display_name="EH",
        password_hash="x",
        family_id=family.id,
    )
    db.add(u)
    db.commit()
    return u


@pytest.fixture
def task(db, family):
    t = AITask(
        id=next_id(),
        family_id=family.id,
        capability="alerts",
        status="running",
        started_at=datetime.utcnow(),
    )
    db.add(t)
    db.commit()
    return t


class FakeStreamResponse:
    """Mimics httpx streaming response context manager."""

    def __init__(self, lines: list[str]):
        self._lines = lines

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        return None

    async def aiter_lines(self) -> AsyncIterator[str]:
        for line in self._lines:
            yield line


class FakeAsyncClient:
    def __init__(self, lines: list[str]):
        self._lines = lines

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        return None

    def stream(self, *args, **kwargs):
        return FakeStreamResponse(self._lines)


def _make_ndjson_stream(answer_text: str) -> list[str]:
    import json

    lines: list[str] = []
    # Simulate token.stream events for the answer
    lines.append(json.dumps({"type": "phase.thinking"}))
    lines.append(json.dumps({"type": "phase.answering"}))
    lines.append(json.dumps({"type": "token.stream", "is_thinking": False, "token": answer_text}))
    lines.append(json.dumps({"type": "capability.end", "result": {"summary": ""}}))
    return lines


async def _consume(gen) -> list[bytes]:
    out: list[bytes] = []
    async for chunk in gen:
        out.append(chunk)
    return out


def _patch_session_local(monkeypatch, db):
    """Make the helper's SessionLocal() return the test db (with no-op close)."""

    class _NoCloseSession:
        def __init__(self, target):
            self._target = target

        def __getattr__(self, name):
            return getattr(self._target, name)

        def close(self):
            pass  # do not close the test session

    from apps.backend.app import database as app_database

    monkeypatch.setattr(
        app_database, "SessionLocal", lambda: _NoCloseSession(db)
    )


class TestHappyPath:
    async def test_regex_html_succeeds_completes_task(self, db, family, user, task, monkeypatch):
        """Stream with valid STRUCTURED_DATA → completed + audit method=regex_html."""
        from apps.backend.app.routers import _ai_events_helper

        answer = (
            'Analysis text. <!-- STRUCTURED_DATA\n'
            '[{"asset_name": "Car", "alert_type": "aging", "severity": "high"}]\n'
            '-->'
        )
        lines = _make_ndjson_stream(answer)

        monkeypatch.setattr(_ai_events_helper.httpx, "AsyncClient", lambda **k: FakeAsyncClient(lines))
        _patch_session_local(monkeypatch, db)

        from apps.backend.app.services.chat_session import ChatSessionService
        monkeypatch.setattr(
            ChatSessionService, "get_session", lambda *args, **kwargs: None
        )

        gen = _ai_events_helper.proxy_capability_events(
            agent_path="/alerts/events",
            capability="alerts",
            task_id=str(task.id),
            session_id="0",
            family_id=family.id,
            current_user=user,
            db=db,
        )
        chunks = await _consume(gen)
        # Stream content forwarded
        assert any(b"phase.answering" in c for c in chunks)
        # No error event
        assert not any(b"capability.error" in c for c in chunks)

        # Task is completed
        db.refresh(task)
        assert task.status == "completed"

        # Audit row exists with method=regex_html
        audit = db.query(AIExtractionAudit).filter_by(family_id=family.id, capability="alerts").first()
        assert audit is not None
        assert audit.method == "regex_html"
        assert audit.task_id == str(task.id)
        assert audit.error_msg is None

    async def test_post_processing_transitions(self, db, family, user, task, monkeypatch):
        """Verify mark_post_processing was applied (status moves running → post_processing → completed)."""
        from apps.backend.app.routers import _ai_events_helper
        from apps.backend.app.services.ai_task_service import AITaskService

        answer = (
            '<!-- STRUCTURED_DATA\n'
            '[{"asset_name": "X", "alert_type": "aging", "severity": "low"}]\n'
            '-->'
        )
        lines = _make_ndjson_stream(answer)

        monkeypatch.setattr(_ai_events_helper.httpx, "AsyncClient", lambda **k: FakeAsyncClient(lines))
        _patch_session_local(monkeypatch, db)
        from apps.backend.app.services.chat_session import ChatSessionService
        monkeypatch.setattr(ChatSessionService, "get_session", lambda *a, **k: None)

        # Spy on mark_post_processing
        calls = {"count": 0}
        original = AITaskService.mark_post_processing

        def spy(task_id, db_):
            calls["count"] += 1
            return original(task_id, db_)

        monkeypatch.setattr(AITaskService, "mark_post_processing", spy)

        gen = _ai_events_helper.proxy_capability_events(
            agent_path="/alerts/events",
            capability="alerts",
            task_id=str(task.id),
            session_id="0",
            family_id=family.id,
            current_user=user,
            db=db,
        )
        await _consume(gen)
        assert calls["count"] == 1
        db.refresh(task)
        assert task.status == "completed"


class TestFailurePath:
    async def test_regex_and_fallback_both_fail(self, db, family, user, task, monkeypatch):
        """No STRUCTURED_DATA, no provider config → status=failed + capability.error emitted."""
        from apps.backend.app.routers import _ai_events_helper

        # Plain prose, no JSON anywhere → regex fails, fallback has no provider → method='failed'
        answer = "Just plain analysis text with no structured data block at all"
        lines = _make_ndjson_stream(answer)

        monkeypatch.setattr(_ai_events_helper.httpx, "AsyncClient", lambda **k: FakeAsyncClient(lines))
        _patch_session_local(monkeypatch, db)
        from apps.backend.app.services.chat_session import ChatSessionService
        monkeypatch.setattr(ChatSessionService, "get_session", lambda *a, **k: None)

        gen = _ai_events_helper.proxy_capability_events(
            agent_path="/alerts/events",
            capability="alerts",
            task_id=str(task.id),
            session_id="0",
            family_id=family.id,
            current_user=user,
            db=db,
        )
        chunks = await _consume(gen)
        # capability.error emitted at the end
        joined = b"".join(chunks).decode()
        assert "capability.error" in joined
        assert "extraction_failed" in joined

        # Task is failed
        db.refresh(task)
        assert task.status == "failed"
        assert task.error_message == "structured_extraction_failed"

        # Audit row: method=failed, error_msg set, answer_excerpt set
        audit = db.query(AIExtractionAudit).filter_by(family_id=family.id, capability="alerts").first()
        assert audit is not None
        assert audit.method == "failed"
        assert audit.error_msg == "extraction_failed"
        assert audit.answer_excerpt is not None and len(audit.answer_excerpt) <= 500

    async def test_agent_stream_exception(self, db, family, user, task, monkeypatch):
        """Network exception during stream → fail_task + agent_stream_error event."""
        from apps.backend.app.routers import _ai_events_helper

        class ExplodingClient:
            async def __aenter__(self):
                return self

            async def __aexit__(self, *args):
                return None

            def stream(self, *args, **kwargs):
                raise RuntimeError("network exploded")

        monkeypatch.setattr(_ai_events_helper.httpx, "AsyncClient", lambda **k: ExplodingClient())
        _patch_session_local(monkeypatch, db)

        gen = _ai_events_helper.proxy_capability_events(
            agent_path="/alerts/events",
            capability="alerts",
            task_id=str(task.id),
            session_id="0",
            family_id=family.id,
            current_user=user,
            db=db,
        )
        chunks = await _consume(gen)
        joined = b"".join(chunks).decode()
        assert "capability.error" in joined
        assert "agent_stream_error" in joined

        db.refresh(task)
        assert task.status == "failed"


class TestCircuitEvaluateOnFailure:
    async def test_evaluate_called_on_extraction_failure(
        self, db, family, user, task, monkeypatch
    ):
        from apps.backend.app.routers import _ai_events_helper
        from apps.backend.app.services.ai_extraction_circuit_service import (
            AIExtractionCircuitService,
        )

        answer = "no structured data, plain prose only"
        lines = _make_ndjson_stream(answer)

        monkeypatch.setattr(_ai_events_helper.httpx, "AsyncClient", lambda **k: FakeAsyncClient(lines))
        _patch_session_local(monkeypatch, db)
        from apps.backend.app.services.chat_session import ChatSessionService
        monkeypatch.setattr(ChatSessionService, "get_session", lambda *a, **k: None)

        calls = {"count": 0}
        original = AIExtractionCircuitService.evaluate

        def spy(fid, cap, dbs):
            calls["count"] += 1
            return original(fid, cap, dbs)

        monkeypatch.setattr(AIExtractionCircuitService, "evaluate", spy)

        gen = _ai_events_helper.proxy_capability_events(
            agent_path="/alerts/events",
            capability="alerts",
            task_id=str(task.id),
            session_id="0",
            family_id=family.id,
            current_user=user,
            db=db,
        )
        await _consume(gen)
        assert calls["count"] == 1
