"""Tests for session-based AI chat API (JSONL storage)."""

import json
from contextlib import nullcontext
from unittest.mock import AsyncMock, MagicMock, patch

from apps.backend.app.models.ai_chat_session import AIChatSession
from apps.backend.app.models.cached_file import CachedFile
from apps.backend.app.models.file_remote_location import FileRemoteLocation
from apps.backend.app.models.storage_backend import StorageBackend


def _enable_ai(db, auth_headers, client):
    """Enable AI for the test user's family."""
    # Get current user to find family_id
    me = client.get("/api/v1/auth/me", headers=auth_headers).json()
    family_id = me["data"]["family_id"]
    from apps.backend.app.models.ai_provider_config import AIProviderConfig
    cfg = AIProviderConfig(
        family_id=family_id,
        name="测试配置",
        provider="anthropic",
        api_key_encrypted="test_encrypted_key",
        model_id="claude-3-5-sonnet-20241022",
        is_active=True,
    )
    db.add(cfg)
    db.commit()
    return family_id


def _mock_agent_response(answer: str = "Test answer"):
    """Create a mock httpx response from the agent."""
    mock_resp = MagicMock()
    mock_resp.raise_for_status = MagicMock()
    mock_resp.json.return_value = {"summary": answer}
    mock_client = AsyncMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    mock_client.post = AsyncMock(return_value=mock_resp)
    return mock_client


def _mock_agent_stream(ndjson_lines: list[str]):
    """Create a mock httpx streaming response that yields NDJSON lines."""
    async def _aiter_text():
        for line in ndjson_lines:
            yield line

    mock_resp = MagicMock()
    mock_resp.raise_for_status = MagicMock()
    mock_resp.aiter_text = _aiter_text
    mock_stream = AsyncMock()
    mock_stream.__aenter__ = AsyncMock(return_value=mock_resp)
    mock_stream.__aexit__ = AsyncMock(return_value=False)
    mock_client = AsyncMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    mock_client.stream = MagicMock(return_value=mock_stream)
    return mock_client


# ── Session lifecycle ──────────────────────────────────────────────────────────

def test_chat_creates_session_when_none_exists(client, auth_headers, db, tmp_path):
    """POST /ai/chat without session_id creates a new session."""
    family_id = _enable_ai(db, auth_headers, client)

    with patch("apps.backend.app.config.settings.CHAT_DIR", str(tmp_path)), \
         patch("httpx.AsyncClient", return_value=_mock_agent_response()):
        resp = client.post(
            "/api/v1/ai/chat",
            json={"question": "Hello"},
            headers=auth_headers,
        )

    assert resp.status_code == 200
    data = resp.json()["data"]
    assert "session_id" in data
    assert data["answer"] == "Test answer"

    # Verify session was created in DB
    session = db.query(AIChatSession).filter_by(family_id=family_id).first()
    assert session is not None
    assert session.message_count == 2  # user + assistant


def test_chat_reuses_existing_session(client, auth_headers, db, tmp_path):
    """POST /ai/chat with session_id appends to existing session."""
    _enable_ai(db, auth_headers, client)

    with patch("apps.backend.app.config.settings.CHAT_DIR", str(tmp_path)), \
         patch("httpx.AsyncClient", return_value=_mock_agent_response()):
        # First message — creates session
        resp1 = client.post(
            "/api/v1/ai/chat",
            json={"question": "First question"},
            headers=auth_headers,
        )
        session_id = resp1.json()["data"]["session_id"]

        # Second message — reuses session
        resp2 = client.post(
            "/api/v1/ai/chat",
            json={"question": "Second question", "session_id": session_id},
            headers=auth_headers,
        )

    assert resp2.status_code == 200
    assert resp2.json()["data"]["session_id"] == str(session_id)

    session = db.query(AIChatSession).filter_by(id=session_id).first()
    assert session.message_count == 4  # 2 user + 2 assistant


def test_chat_invalid_session_id_returns_404(client, auth_headers, db, tmp_path):
    """POST /ai/chat with non-existent session_id returns 404."""
    _enable_ai(db, auth_headers, client)

    with patch("apps.backend.app.config.settings.CHAT_DIR", str(tmp_path)):
        resp = client.post(
            "/api/v1/ai/chat",
            json={"question": "Hello", "session_id": "00000000-0000-0000-0000-000000000000"},
            headers=auth_headers,
        )

    assert resp.status_code == 404


# ── JSONL file integrity ───────────────────────────────────────────────────────

def test_jsonl_file_contains_correct_messages(client, auth_headers, db, tmp_path):
    """After POST, JSONL file contains valid JSON lines with correct content."""
    family_id = _enable_ai(db, auth_headers, client)

    with patch("apps.backend.app.config.settings.CHAT_DIR", str(tmp_path)), \
         patch("httpx.AsyncClient", return_value=_mock_agent_response("AI reply")):
        resp = client.post(
            "/api/v1/ai/chat",
            json={"question": "My question"},
            headers=auth_headers,
        )

    session_id = resp.json()["data"]["session_id"]
    jsonl_file = tmp_path / family_id / f"{session_id}.jsonl"
    assert jsonl_file.exists()

    lines = [json.loads(line) for line in jsonl_file.read_text().strip().splitlines()]
    assert len(lines) == 2
    assert lines[0]["role"] == "user"
    assert lines[0]["content"] == "My question"
    assert lines[1]["role"] == "assistant"
    assert lines[1]["content"] == "AI reply"
    # Each line has required fields
    for line in lines:
        assert "message_id" in line
        assert "timestamp" in line


# ── GET /ai/chat/history ───────────────────────────────────────────────────────

def test_get_history_returns_messages_in_order(client, auth_headers, db, tmp_path):
    """GET /ai/chat/history returns messages in ascending order."""
    _enable_ai(db, auth_headers, client)

    with patch("apps.backend.app.config.settings.CHAT_DIR", str(tmp_path)), \
         patch("httpx.AsyncClient", return_value=_mock_agent_response("Answer")):
        post_resp = client.post(
            "/api/v1/ai/chat",
            json={"question": "Question"},
            headers=auth_headers,
        )
        session_id = post_resp.json()["data"]["session_id"]

    with patch("apps.backend.app.config.settings.CHAT_DIR", str(tmp_path)):
        resp = client.get(
            f"/api/v1/ai/chat/history?session_id={session_id}",
            headers=auth_headers,
        )

    assert resp.status_code == 200
    messages = resp.json()["data"]["messages"]
    assert len(messages) == 2
    assert messages[0]["role"] == "user"
    assert messages[1]["role"] == "assistant"


def test_get_history_without_session_id_uses_latest(client, auth_headers, db, tmp_path):
    """GET /ai/chat/history without session_id returns latest session's messages."""
    _enable_ai(db, auth_headers, client)

    with patch("apps.backend.app.config.settings.CHAT_DIR", str(tmp_path)), \
         patch("httpx.AsyncClient", return_value=_mock_agent_response()):
        client.post("/api/v1/ai/chat", json={"question": "Q1"}, headers=auth_headers)

    with patch("apps.backend.app.config.settings.CHAT_DIR", str(tmp_path)):
        resp = client.get("/api/v1/ai/chat/history", headers=auth_headers)

    assert resp.status_code == 200
    assert len(resp.json()["data"]["messages"]) == 2


def test_get_history_empty_when_no_sessions(client, auth_headers, db):
    """GET /ai/chat/history returns empty list when family has no sessions."""
    _enable_ai(db, auth_headers, client)

    resp = client.get("/api/v1/ai/chat/history", headers=auth_headers)
    assert resp.status_code == 200
    assert resp.json()["data"]["messages"] == []


def test_get_history_invalid_session_id_returns_404(client, auth_headers, db):
    """GET /ai/chat/history with invalid session_id returns 404."""
    _enable_ai(db, auth_headers, client)

    resp = client.get(
        "/api/v1/ai/chat/history?session_id=00000000-0000-0000-0000-000000000000",
        headers=auth_headers,
    )
    assert resp.status_code == 404


def test_get_history_limit_applied(client, auth_headers, db, tmp_path):
    """GET /ai/chat/history respects limit parameter."""
    _enable_ai(db, auth_headers, client)

    with patch("apps.backend.app.config.settings.CHAT_DIR", str(tmp_path)), \
         patch("httpx.AsyncClient", return_value=_mock_agent_response()):
        # Send 3 messages
        resp = client.post("/api/v1/ai/chat", json={"question": "Q1"}, headers=auth_headers)
        session_id = resp.json()["data"]["session_id"]
        for q in ["Q2", "Q3"]:
            client.post(
                "/api/v1/ai/chat",
                json={"question": q, "session_id": session_id},
                headers=auth_headers,
            )

    with patch("apps.backend.app.config.settings.CHAT_DIR", str(tmp_path)):
        resp = client.get(
            f"/api/v1/ai/chat/history?session_id={session_id}&limit=2",
            headers=auth_headers,
        )

    assert resp.status_code == 200
    assert len(resp.json()["data"]["messages"]) == 2


# ── GET /ai/chat/sessions ──────────────────────────────────────────────────────

def test_get_sessions_returns_list(client, auth_headers, db, tmp_path):
    """GET /ai/chat/sessions returns list of sessions for the family."""
    import asyncio

    from apps.backend.app.services.chat_session import ChatSessionService

    family_id = _enable_ai(db, auth_headers, client)
    me = client.get("/api/v1/auth/me", headers=auth_headers).json()
    user_id = me["data"]["id"]

    with patch("apps.backend.app.config.settings.CHAT_DIR", str(tmp_path)):
        # Create two sessions directly via service
        asyncio.run(ChatSessionService.create_session(family_id, user_id, db))
        asyncio.run(ChatSessionService.create_session(family_id, user_id, db))

    resp = client.get("/api/v1/ai/chat/sessions", headers=auth_headers)
    assert resp.status_code == 200
    sessions = resp.json()["data"]
    assert len(sessions) == 2
    # Each session has required fields
    for s in sessions:
        assert "session_id" in s
        assert "created_at" in s
        assert "message_count" in s


def test_chat_stream_persists_only_non_thinking_tokens(client, auth_headers, db, tmp_path):
    family_id = _enable_ai(db, auth_headers, client)

    ndjson_lines = [
        '{"type":"phase.connecting","phase":"connecting"}\n',
        '{"type":"token.stream","token":"内部思考","is_thinking":true}\n',
        '{"type":"phase.answering","phase":"answering"}\n',
        '{"type":"token.stream","token":"最终回答","is_thinking":false}\n',
        '{"type":"capability.end","result":{"summary":"最终回答"}}\n',
    ]

    with patch("apps.backend.app.config.settings.CHAT_DIR", str(tmp_path)), \
         patch("apps.backend.app.routers.ai_chat.SessionLocal", side_effect=lambda: nullcontext(db)), \
         patch("httpx.AsyncClient", return_value=_mock_agent_stream(ndjson_lines)):
        resp = client.post(
            "/api/v1/ai/chat/stream",
            json={"question": "My question"},
            headers=auth_headers,
        )

    assert resp.status_code == 200
    assert "capability.end" in resp.text

    session = db.query(AIChatSession).filter_by(family_id=family_id).first()
    assert session is not None

    messages = [
        json.loads(line)
        for line in (tmp_path / family_id / f"{session.id}.jsonl").read_text().splitlines()
    ]
    assert messages[0]["role"] == "user"
    assert messages[0]["content"] == "My question"
    assert messages[1]["role"] == "assistant"
    assert messages[1]["content"] == "最终回答"


def test_get_sessions_empty_when_no_sessions(client, auth_headers, db):
    """GET /ai/chat/sessions returns empty list when family has no sessions."""
    _enable_ai(db, auth_headers, client)

    resp = client.get("/api/v1/ai/chat/sessions", headers=auth_headers)
    assert resp.status_code == 200
    assert resp.json()["data"] == []


# ── DELETE /ai/chat/history ────────────────────────────────────────────────────

def test_delete_specific_session(client, auth_headers, db, tmp_path):
    """DELETE /ai/chat/history?session_id=X deletes only that session."""
    import asyncio

    from apps.backend.app.services.chat_session import ChatSessionService

    family_id = _enable_ai(db, auth_headers, client)
    me = client.get("/api/v1/auth/me", headers=auth_headers).json()
    user_id = me["data"]["id"]

    with patch("apps.backend.app.config.settings.CHAT_DIR", str(tmp_path)):
        session1 = asyncio.run(
            ChatSessionService.create_session(family_id, user_id, db)
        )
        session2 = asyncio.run(
            ChatSessionService.create_session(family_id, user_id, db)
        )

    resp = client.delete(
        f"/api/v1/ai/chat/history?session_id={session1.id}",
        headers=auth_headers,
    )
    assert resp.status_code == 200
    assert resp.json()["data"]["ok"] is True

    # Only session 1 deleted
    remaining = db.query(AIChatSession).all()
    assert len(remaining) == 1
    assert remaining[0].id == session2.id


def test_delete_all_sessions(client, auth_headers, db, tmp_path):
    """DELETE /ai/chat/history without session_id deletes all family sessions."""
    _enable_ai(db, auth_headers, client)

    with patch("apps.backend.app.config.settings.CHAT_DIR", str(tmp_path)), \
         patch("httpx.AsyncClient", return_value=_mock_agent_response()):
        client.post("/api/v1/ai/chat", json={"question": "Q1"}, headers=auth_headers)
        client.post("/api/v1/ai/chat", json={"question": "Q2"}, headers=auth_headers)

    resp = client.delete("/api/v1/ai/chat/history", headers=auth_headers)
    assert resp.status_code == 200

    assert db.query(AIChatSession).count() == 0


def test_delete_soft_deletes_cached_file(client, auth_headers, db, tmp_path):
    """DELETE marks CachedFile as deleted (soft delete)."""
    _enable_ai(db, auth_headers, client)

    with patch("apps.backend.app.config.settings.CHAT_DIR", str(tmp_path)), \
         patch("httpx.AsyncClient", return_value=_mock_agent_response()):
        resp = client.post("/api/v1/ai/chat", json={"question": "Q"}, headers=auth_headers)
        session_id = resp.json()["data"]["session_id"]

    session = db.query(AIChatSession).filter_by(id=session_id).first()
    cached_file_id = session.cached_file_id

    client.delete(f"/api/v1/ai/chat/history?session_id={session_id}", headers=auth_headers)

    db.expire_all()
    cached_file = db.query(CachedFile).filter_by(id=cached_file_id).first()
    assert cached_file is not None
    assert cached_file.deleted_at is not None


# ── Cross-family isolation ─────────────────────────────────────────────────────

def test_cross_family_session_isolation(client, auth_headers, second_user_headers, db, tmp_path):
    """Family A cannot access Family B's sessions."""
    _enable_ai(db, auth_headers, client)
    _enable_ai(db, second_user_headers, client)

    with patch("apps.backend.app.config.settings.CHAT_DIR", str(tmp_path)), \
         patch("httpx.AsyncClient", return_value=_mock_agent_response()):
        resp = client.post(
            "/api/v1/ai/chat",
            json={"question": "Family A question"},
            headers=auth_headers,
        )
        family_a_session_id = resp.json()["data"]["session_id"]

    # Family B tries to access Family A's session
    with patch("apps.backend.app.config.settings.CHAT_DIR", str(tmp_path)):
        resp = client.get(
            f"/api/v1/ai/chat/history?session_id={family_a_session_id}",
            headers=second_user_headers,
        )
    assert resp.status_code == 404

    # Family B's sessions list is empty
    resp = client.get("/api/v1/ai/chat/sessions", headers=second_user_headers)
    assert resp.json()["data"] == []


def test_cross_family_delete_isolation(client, auth_headers, second_user_headers, db, tmp_path):
    """Family B cannot delete Family A's session."""
    _enable_ai(db, auth_headers, client)
    _enable_ai(db, second_user_headers, client)

    with patch("apps.backend.app.config.settings.CHAT_DIR", str(tmp_path)), \
         patch("httpx.AsyncClient", return_value=_mock_agent_response()):
        resp = client.post(
            "/api/v1/ai/chat",
            json={"question": "Family A question"},
            headers=auth_headers,
        )
        family_a_session_id = resp.json()["data"]["session_id"]

    # Family B tries to delete Family A's session — silently does nothing
    client.delete(
        f"/api/v1/ai/chat/history?session_id={family_a_session_id}",
        headers=second_user_headers,
    )

    # Family A's session still exists
    assert db.query(AIChatSession).filter_by(id=family_a_session_id).first() is not None


# ── CachedFile integration ─────────────────────────────────────────────────────

def test_cached_file_created_on_first_message(client, auth_headers, db, tmp_path):
    """First message creates a CachedFile row with correct mime_type."""
    family_id = _enable_ai(db, auth_headers, client)

    with patch("apps.backend.app.config.settings.CHAT_DIR", str(tmp_path)), \
         patch("httpx.AsyncClient", return_value=_mock_agent_response()):
        resp = client.post(
            "/api/v1/ai/chat",
            json={"question": "Q"},
            headers=auth_headers,
        )
        session_id = resp.json()["data"]["session_id"]

    session = db.query(AIChatSession).filter_by(id=session_id).first()
    assert session.cached_file_id is not None

    cached_file = db.query(CachedFile).filter_by(id=session.cached_file_id).first()
    assert cached_file is not None
    assert cached_file.mime_type == "application/x-ndjson"
    assert cached_file.family_id == int(family_id)
    assert cached_file.sha256 is not None
    assert len(cached_file.sha256) == 64


def test_remote_sync_queued_when_enabled(client, auth_headers, db, tmp_path):
    """When CHAT_ENABLE_REMOTE_SYNC=True and default backend exists, FileRemoteLocation is created."""
    _enable_ai(db, auth_headers, client)

    # Create a default storage backend
    backend = StorageBackend(
        id="test-backend",
        backend_type="local",
        display_name="Test",
        is_default=True,
        is_active=True,
    )
    db.add(backend)
    db.commit()

    with patch("apps.backend.app.config.settings.CHAT_DIR", str(tmp_path)), \
         patch("apps.backend.app.config.settings.CHAT_ENABLE_REMOTE_SYNC", True), \
         patch("apps.backend.app.services.chat_session.settings.CHAT_ENABLE_REMOTE_SYNC", True), \
         patch("httpx.AsyncClient", return_value=_mock_agent_response()):
        resp = client.post(
            "/api/v1/ai/chat",
            json={"question": "Q"},
            headers=auth_headers,
        )
        session_id = resp.json()["data"]["session_id"]

    session = db.query(AIChatSession).filter_by(id=session_id).first()
    remote_loc = db.query(FileRemoteLocation).filter_by(file_id=session.cached_file_id).first()
    assert remote_loc is not None
    assert remote_loc.sync_status == "pending"


def test_remote_sync_not_queued_by_default(client, auth_headers, db, tmp_path):
    """By default (CHAT_ENABLE_REMOTE_SYNC=False), no FileRemoteLocation is created."""
    _enable_ai(db, auth_headers, client)

    with patch("apps.backend.app.config.settings.CHAT_DIR", str(tmp_path)), \
         patch("httpx.AsyncClient", return_value=_mock_agent_response()):
        resp = client.post(
            "/api/v1/ai/chat",
            json={"question": "Q"},
            headers=auth_headers,
        )
        session_id = resp.json()["data"]["session_id"]

    session = db.query(AIChatSession).filter_by(id=session_id).first()
    remote_locs = db.query(FileRemoteLocation).filter_by(file_id=session.cached_file_id).all()
    assert len(remote_locs) == 0


# ── Agent thread_id forwarding ─────────────────────────────────────────────────

def test_agent_receives_thread_id_header(client, auth_headers, db, tmp_path):
    """POST /ai/chat passes X-Thread-Id header to agent matching session.id."""
    _enable_ai(db, auth_headers, client)

    captured_headers = {}

    mock_resp = MagicMock()
    mock_resp.raise_for_status = MagicMock()
    mock_resp.json.return_value = {"summary": "Answer"}

    async def mock_post(url, json=None, headers=None, **kwargs):
        captured_headers.update(headers or {})
        return mock_resp

    mock_client = AsyncMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    mock_client.post = mock_post

    with patch("apps.backend.app.config.settings.CHAT_DIR", str(tmp_path)), \
         patch("httpx.AsyncClient", return_value=mock_client):
        resp = client.post(
            "/api/v1/ai/chat",
            json={"question": "Q"},
            headers=auth_headers,
        )

    session_id = resp.json()["data"]["session_id"]
    assert captured_headers.get("X-Thread-Id") == session_id
