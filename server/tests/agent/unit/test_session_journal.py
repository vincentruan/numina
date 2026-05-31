"""Unit tests for services/session_journal.py."""

import json
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../.."))

from apps.agent.services.session_journal import SessionJournalService, _validate_id


class TestValidateId:
    def test_valid_alphanumeric(self):
        assert _validate_id("abc123", "x") == "abc123"

    def test_valid_with_dash_underscore(self):
        assert _validate_id("sess-20260510-a1b2c3d4", "x") == "sess-20260510-a1b2c3d4"

    def test_empty_raises(self):
        with pytest.raises(ValueError, match="Invalid"):
            _validate_id("", "session_id")

    def test_slash_raises(self):
        with pytest.raises(ValueError, match="Invalid"):
            _validate_id("../../etc/passwd", "family_id")

    def test_space_raises(self):
        with pytest.raises(ValueError, match="Invalid"):
            _validate_id("fam 123", "family_id")


class TestSessionJournalService:
    def test_append_and_read_events(self, tmp_path):
        svc = SessionJournalService(tmp_path)
        event = {"type": "session.start", "sessionId": "s1", "familyId": "f1"}
        svc.append_event("f1", "s1", event)
        events = svc.read_events("f1", "s1")
        assert len(events) == 1
        assert events[0]["type"] == "session.start"

    def test_append_multiple_events(self, tmp_path):
        svc = SessionJournalService(tmp_path)
        for i in range(5):
            svc.append_event("f1", "s1", {"seq": i, "type": "token"})
        events = svc.read_events("f1", "s1")
        assert len(events) == 5
        assert [e["seq"] for e in events] == list(range(5))

    def test_read_nonexistent_returns_empty(self, tmp_path):
        svc = SessionJournalService(tmp_path)
        assert svc.read_events("f1", "no-such-session") == []

    def test_malformed_line_skipped(self, tmp_path):
        svc = SessionJournalService(tmp_path)
        path = svc._session_path("f1", "s1")
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            f.write('{"type": "ok"}\n')
            f.write("NOT JSON\n")
            f.write('{"type": "also-ok"}\n')
        events = svc.read_events("f1", "s1")
        assert len(events) == 2
        assert events[0]["type"] == "ok"
        assert events[1]["type"] == "also-ok"

    def test_write_failure_does_not_raise(self, tmp_path, monkeypatch):
        svc = SessionJournalService(tmp_path)
        # Patch open to simulate a disk-full error
        import builtins
        real_open = builtins.open

        def broken_open(path, *args, **kwargs):
            if "s1.jsonl" in str(path):
                raise OSError("disk full")
            return real_open(path, *args, **kwargs)

        monkeypatch.setattr(builtins, "open", broken_open)
        # Must not raise
        svc.append_event("f1", "s1", {"type": "test"})

    def test_invalid_family_id_raises(self, tmp_path):
        svc = SessionJournalService(tmp_path)
        with pytest.raises(ValueError):
            svc.append_event("bad/family", "s1", {})

    def test_invalid_session_id_raises(self, tmp_path):
        svc = SessionJournalService(tmp_path)
        with pytest.raises(ValueError):
            svc.append_event("f1", "bad session!", {})

    def test_iter_events_yields_all(self, tmp_path):
        svc = SessionJournalService(tmp_path)
        for i in range(3):
            svc.append_event("f1", "s1", {"seq": i})
        result = list(svc.iter_events("f1", "s1"))
        assert len(result) == 3

    def test_iter_events_nonexistent_yields_nothing(self, tmp_path):
        svc = SessionJournalService(tmp_path)
        assert list(svc.iter_events("f1", "no-session")) == []

    def test_family_isolation(self, tmp_path):
        svc = SessionJournalService(tmp_path)
        svc.append_event("fam-A", "s1", {"family": "A"})
        svc.append_event("fam-B", "s1", {"family": "B"})
        a_events = svc.read_events("fam-A", "s1")
        b_events = svc.read_events("fam-B", "s1")
        assert a_events[0]["family"] == "A"
        assert b_events[0]["family"] == "B"

    def test_write_session_start_creates_event(self, tmp_path):
        svc = SessionJournalService(tmp_path)
        jsonl_path = str(tmp_path / "f1" / "s1.jsonl")
        svc.write_session_start(
            family_id="f1",
            session_id="s1",
            user_id="u1",
            capability="chat",
            model_name="claude-3",
            jsonl_path=jsonl_path,
        )
        events = svc.read_events("f1", "s1")
        assert len(events) == 1
        assert events[0]["type"] == "session.start"
        assert events[0]["capability"] == "chat"

    def test_write_user_message(self, tmp_path):
        svc = SessionJournalService(tmp_path)
        svc.write_user_message(
            family_id="f1", session_id="s1", user_id="u1", content="hello"
        )
        events = svc.read_events("f1", "s1")
        assert events[0]["type"] == "user.message"
        assert events[0]["content"] == "hello"
        assert events[0]["visibility"] == "public"

    def test_write_assistant_message(self, tmp_path):
        svc = SessionJournalService(tmp_path)
        svc.write_assistant_message(
            family_id="f1", session_id="s1", content="world", model_name="m1"
        )
        events = svc.read_events("f1", "s1")
        assert events[0]["type"] == "assistant.message"
        assert events[0]["visibility"] == "public"

    def test_write_session_end(self, tmp_path):
        svc = SessionJournalService(tmp_path)
        svc.write_session_end(
            family_id="f1", session_id="s1", success=True, duration_ms=500
        )
        events = svc.read_events("f1", "s1")
        assert events[0]["type"] == "session.end"
        assert events[0]["success"] is True

    def test_events_are_valid_json_lines(self, tmp_path):
        svc = SessionJournalService(tmp_path)
        svc.write_user_message(family_id="f1", session_id="s1", user_id=None, content="test")
        path = svc._session_path("f1", "s1")
        lines = path.read_text(encoding="utf-8").strip().splitlines()
        assert len(lines) == 1
        parsed = json.loads(lines[0])
        assert "eventId" in parsed
        assert "timestamp" in parsed
        assert "schemaVersion" in parsed


class TestPathCacheTenantIsolation:
    """C1 regression: _path_cache must be keyed by (family_id, session_id).

    A session_id-only key allows family A's write_session_start to set the
    cache entry, then family B opening a stream with the same thread_id
    would inherit family A's path — leaking conversation content into a
    different tenant's JSONL.
    """

    def test_same_session_id_different_families_use_distinct_paths(self, tmp_path):
        svc = SessionJournalService(tmp_path)
        shared_session_id = "thread-shared-id"

        # Family A starts a session, caches its path.
        svc.write_session_start(
            family_id="famA",
            session_id=shared_session_id,
            user_id="userA",
            capability="agent",
            model_name="m",
            jsonl_path=str(
                tmp_path / "famA" / "agent" / "agent" / "userA" / f"{shared_session_id}.jsonl"
            ),
        )
        # Family B then opens with the SAME session_id.
        svc.write_session_start(
            family_id="famB",
            session_id=shared_session_id,
            user_id="userB",
            capability="agent",
            model_name="m",
            jsonl_path=str(
                tmp_path / "famB" / "agent" / "agent" / "userB" / f"{shared_session_id}.jsonl"
            ),
        )

        # Each family should resolve to its own path, even via the cache hit.
        path_a = svc._session_path("famA", shared_session_id)
        path_b = svc._session_path("famB", shared_session_id)
        assert path_a != path_b
        assert "famA" in str(path_a)
        assert "famB" in str(path_b)

    def test_subsequent_writes_route_to_owning_family(self, tmp_path):
        """Family A's write_user_message must land in famA's JSONL even
        after famB has cached a path under the same session_id."""
        svc = SessionJournalService(tmp_path)
        shared = "thread-collision"

        path_a = tmp_path / "famA" / "agent" / "agent" / "userA" / f"{shared}.jsonl"
        path_b = tmp_path / "famB" / "agent" / "agent" / "userB" / f"{shared}.jsonl"

        svc.write_session_start(
            family_id="famA", session_id=shared, user_id="userA",
            capability="agent", model_name="m", jsonl_path=str(path_a),
        )
        svc.write_session_start(
            family_id="famB", session_id=shared, user_id="userB",
            capability="agent", model_name="m", jsonl_path=str(path_b),
        )
        # famA writes — must NOT bleed into famB's file.
        svc.write_user_message(
            family_id="famA", session_id=shared, user_id="userA", content="A's secret"
        )
        svc.write_user_message(
            family_id="famB", session_id=shared, user_id="userB", content="B's secret"
        )

        events_a = svc.read_events("famA", shared)
        events_b = svc.read_events("famB", shared)

        a_user_msgs = [e for e in events_a if e["type"] == "user.message"]
        b_user_msgs = [e for e in events_b if e["type"] == "user.message"]

        assert any(e["content"] == "A's secret" for e in a_user_msgs)
        assert not any(e["content"] == "B's secret" for e in a_user_msgs)
        assert any(e["content"] == "B's secret" for e in b_user_msgs)
        assert not any(e["content"] == "A's secret" for e in b_user_msgs)

