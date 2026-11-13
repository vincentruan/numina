"""Handler-level tests for record_teach_back_turn MCP tool (#15).

Tests the full tool-call path through MCPSession.call_tool, covering:
- hit turn appends to progress_json
- mixed [hit, miss, hit] run reaches success
- miss-only run leaves progress untouched
- double resolve does not double-reward (idempotency #10)
- verdict validation (#21)
- confusion_id topic-scope validation (#22)
- caller-bound child validation (#23)
"""
import json
from unittest.mock import MagicMock, patch

import pytest

from apps.backend.app.services.mcp_session import MCPSession


@pytest.fixture
def mock_db():
    return MagicMock()


def _patch_mcp(mock_db, user=None):
    """Return nested patches for SessionLocal and _get_caller_user."""
    sl = patch("apps.backend.app.services.mcp_session.SessionLocal")
    gu = patch("apps.backend.app.services.mcp_session._get_caller_user")
    if user is None:
        user = MagicMock(id=1001, family_id=100, role="member")
    return sl, gu, user


def _make_mcp_session(family_id="100", caller_user_id="1001", caller_role="member"):
    return MCPSession(family_id=family_id, caller_user_id=caller_user_id, caller_role=caller_role)


def _setup_session_query(mock_db, session, child_user_id="child1", family_id="100"):
    """Configure mock_db.query to return the LearningSession for the join query."""
    mock_session_query = MagicMock()
    mock_session_query.join.return_value = mock_session_query
    mock_session_query.filter.return_value = mock_session_query
    mock_session_query.first.return_value = session
    # Default: first query call returns session query
    mock_db.query.return_value = mock_session_query
    return mock_session_query


def _setup_confusion_query(mock_db, confusion):
    """Configure mock_db.query to return a TopicConfusion for topic-scope check."""
    mock_confusion_query = MagicMock()
    mock_confusion_query.filter.return_value = mock_confusion_query
    mock_confusion_query.first.return_value = confusion
    return mock_confusion_query


def _setup_progress_query(mock_db, progress):
    mock_progress_query = MagicMock()
    mock_progress_query.filter.return_value = mock_progress_query
    mock_progress_query.first.return_value = progress
    return mock_progress_query


def _make_session(session_id=1, child_id=1001, topic_id=100, progress_json=None, ended_at=None):
    session = MagicMock()
    session.id = session_id
    session.child_id = child_id
    session.topic_id = topic_id
    session.progress_json = progress_json
    session.ended_at = ended_at
    return session


def _make_confusion(confusion_id=10, topic_id=100, expected_expression=None):
    confusion = MagicMock()
    confusion.id = confusion_id
    confusion.topic_id = topic_id
    confusion.expected_expression = expected_expression
    confusion.review_status = "approved"
    return confusion


def _make_progress(child_id=1001, topic_id=100, mastery_level="mastered"):
    progress = MagicMock()
    progress.child_id = child_id
    progress.topic_id = topic_id
    progress.mastery_level = mastery_level
    progress.stability = 5.0
    progress.ease_factor = 2.5
    progress.consecutive_review_passes = 0
    return progress


# ---------------------------------------------------------------------------
# Basic turn recording
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_hit_turn_appends_to_progress_json(mock_db):
    """A hit turn appends a teach_back_turn record to progress_json."""
    session = _make_session(progress_json="[]")
    confusion = _make_confusion(expected_expression=None)
    _setup_session_query(mock_db, session)

    # Configure query to return different mocks based on call order
    call_count = [0]
    original_query = mock_db.query

    def query_side_effect(model):
        call_count[0] += 1
        result = original_query(model)
        if call_count[0] == 1:
            # First call: session join query
            mock_q = MagicMock()
            mock_q.join.return_value = mock_q
            mock_q.filter.return_value = mock_q
            mock_q.first.return_value = session
            return mock_q
        elif call_count[0] == 2:
            # Second call: confusion query
            mock_q = MagicMock()
            mock_q.filter.return_value = mock_q
            mock_q.first.return_value = confusion
            return mock_q
        elif call_count[0] == 3:
            # Third call: total_confusions count
            mock_q = MagicMock()
            mock_q.filter.return_value = mock_q
            mock_q.count.return_value = 1
            return mock_q
        return result

    mock_db.query = query_side_effect

    sl_patch, gu_patch, mock_user = _patch_mcp(mock_db)
    with sl_patch as mock_sl, gu_patch as mock_gu:
        mock_sl.return_value.__enter__ = MagicMock(return_value=mock_db)
        mock_sl.return_value.__exit__ = MagicMock(return_value=False)
        mock_gu.return_value = mock_user

        mcp = _make_mcp_session()
        result = await mcp.call_tool("record_teach_back_turn", {
            "session_id": "1",
            "confusion_id": "10",
            "child_explanation": "because the denominator stays the same",
            "verdict": "hit",
            "phase": "evaluate_explanation",
            "next_phase": "present_confusion",
        })

    payload = json.loads(result[0].text)
    assert payload["ok"] is True
    assert payload["verdict"] == "hit"
    assert payload["total_turns"] == 1
    # progress_json should have been updated with a turn record
    stored = json.loads(session.progress_json)
    assert len(stored) == 1
    assert stored[0]["type"] == "teach_back_turn"
    assert stored[0]["verdict"] == "hit"


# ---------------------------------------------------------------------------
# Mixed run with miss-then-hit reaches success
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_mixed_run_hit_miss_hit_reaches_success(mock_db):
    """A [hit, miss, hit] run on 2 confusions ending in resolve yields success (#14)."""
    # After miss+hit+hit: 2 unique hit confusions >= 2 total
    session = _make_session(progress_json=json.dumps([
        {"type": "teach_back_turn", "confusion_id": 10, "verdict": "hit"},
        {"type": "teach_back_turn", "confusion_id": 11, "verdict": "miss"},
    ]))
    confusion = _make_confusion(confusion_id=11, expected_expression=None)
    progress = _make_progress()

    call_count = [0]

    def query_side_effect(model):
        call_count[0] += 1
        if call_count[0] == 1:
            mock_q = MagicMock()
            mock_q.join.return_value = mock_q
            mock_q.filter.return_value = mock_q
            mock_q.first.return_value = session
            return mock_q
        elif call_count[0] == 2:
            mock_q = MagicMock()
            mock_q.filter.return_value = mock_q
            mock_q.first.return_value = confusion
            return mock_q
        elif call_count[0] == 3:
            mock_q = MagicMock()
            mock_q.filter.return_value = mock_q
            mock_q.count.return_value = 2  # 2 approved confusions
            return mock_q
        elif call_count[0] == 4:
            mock_q = MagicMock()
            mock_q.filter.return_value = mock_q
            mock_q.first.return_value = progress
            return mock_q
        elif call_count[0] == 5:
            # ChildMilestone query for cache
            mock_q = MagicMock()
            mock_q.filter.return_value = mock_q
            mock_q.__iter__ = MagicMock(return_value=iter([]))
            return mock_q
        return MagicMock()

    mock_db.query = query_side_effect

    sl_patch, gu_patch, mock_user = _patch_mcp(mock_db)
    with sl_patch as mock_sl, gu_patch as mock_gu:
        mock_sl.return_value.__enter__ = MagicMock(return_value=mock_db)
        mock_sl.return_value.__exit__ = MagicMock(return_value=False)
        mock_gu.return_value = mock_user

        with (
            patch("apps.backend.app.services.learning.teach_back_grading.grade_expression", return_value=None),
            patch("apps.backend.app.services.learning.progress_service.apply_teach_back_success") as mock_success,
            patch("apps.backend.app.services.learning.progress_service.apply_teach_back_rewards", return_value={"xp_awarded": 25}),
        ):
            mcp = _make_mcp_session()
            result = await mcp.call_tool("record_teach_back_turn", {
                "session_id": "1",
                "confusion_id": "11",
                "child_explanation": "the denominators are the same",
                "verdict": "hit",
                "phase": "evaluate_explanation",
                "next_phase": "resolve",
            })

            payload = json.loads(result[0].text)
            assert payload["teach_back_success"] is True
            assert payload["all_confusions_hit"] is True
            mock_success.assert_called_once()


# ---------------------------------------------------------------------------
# Miss-only run does not trigger success
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_miss_only_run_no_success(mock_db):
    """A miss-only run ending in 'end' does not trigger success path."""
    session = _make_session(progress_json="[]")
    confusion = _make_confusion(expected_expression=None)

    call_count = [0]

    def query_side_effect(model):
        call_count[0] += 1
        if call_count[0] == 1:
            mock_q = MagicMock()
            mock_q.join.return_value = mock_q
            mock_q.filter.return_value = mock_q
            mock_q.first.return_value = session
            return mock_q
        elif call_count[0] == 2:
            mock_q = MagicMock()
            mock_q.filter.return_value = mock_q
            mock_q.first.return_value = confusion
            return mock_q
        elif call_count[0] == 3:
            mock_q = MagicMock()
            mock_q.filter.return_value = mock_q
            mock_q.count.return_value = 1
            return mock_q
        return MagicMock()

    mock_db.query = query_side_effect

    sl_patch, gu_patch, mock_user = _patch_mcp(mock_db)
    with sl_patch as mock_sl, gu_patch as mock_gu:
        mock_sl.return_value.__enter__ = MagicMock(return_value=mock_db)
        mock_sl.return_value.__exit__ = MagicMock(return_value=False)
        mock_gu.return_value = mock_user

        with patch("apps.backend.app.services.learning.progress_service.apply_teach_back_success") as mock_success:
            mcp = _make_mcp_session()
            result = await mcp.call_tool("record_teach_back_turn", {
                "session_id": "1",
                "confusion_id": "10",
                "child_explanation": "I don't know",
                "verdict": "miss",
                "phase": "evaluate_explanation",
                "next_phase": "end",
            })

            payload = json.loads(result[0].text)
            assert payload["teach_back_success"] is False
            mock_success.assert_not_called()


# ---------------------------------------------------------------------------
# Double resolve does not double-reward (idempotency #10)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_double_resolve_no_double_reward(mock_db):
    """A second resolve call on an already-ended session does not re-award."""
    from datetime import UTC, datetime
    session = _make_session(
        progress_json=json.dumps([
            {"type": "teach_back_turn", "confusion_id": 10, "verdict": "hit"},
        ]),
        ended_at=datetime.now(UTC),  # already completed
    )
    confusion = _make_confusion(expected_expression=None)

    call_count = [0]

    def query_side_effect(model):
        call_count[0] += 1
        if call_count[0] == 1:
            mock_q = MagicMock()
            mock_q.join.return_value = mock_q
            mock_q.filter.return_value = mock_q
            mock_q.first.return_value = session
            return mock_q
        elif call_count[0] == 2:
            mock_q = MagicMock()
            mock_q.filter.return_value = mock_q
            mock_q.first.return_value = confusion
            return mock_q
        elif call_count[0] == 3:
            mock_q = MagicMock()
            mock_q.filter.return_value = mock_q
            mock_q.count.return_value = 1
            return mock_q
        return MagicMock()

    mock_db.query = query_side_effect

    sl_patch, gu_patch, mock_user = _patch_mcp(mock_db)
    with sl_patch as mock_sl, gu_patch as mock_gu:
        mock_sl.return_value.__enter__ = MagicMock(return_value=mock_db)
        mock_sl.return_value.__exit__ = MagicMock(return_value=False)
        mock_gu.return_value = mock_user

        with (
            patch("apps.backend.app.services.learning.progress_service.apply_teach_back_success") as mock_success,
            patch("apps.backend.app.services.learning.progress_service.apply_teach_back_rewards") as mock_rewards,
        ):
            mcp = _make_mcp_session()
            result = await mcp.call_tool("record_teach_back_turn", {
                "session_id": "1",
                "confusion_id": "10",
                "child_explanation": "again",
                "verdict": "hit",
                "phase": "resolve",
                "next_phase": "end",
            })

            payload = json.loads(result[0].text)
            # Should NOT re-trigger success path since session.ended_at is set
            assert payload["teach_back_success"] is False
            mock_success.assert_not_called()
            mock_rewards.assert_not_called()


# ---------------------------------------------------------------------------
# Verdict validation (#21)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_invalid_verdict_rejected(mock_db):
    """An invalid verdict value is rejected with invalid_verdict error."""
    sl_patch, gu_patch, mock_user = _patch_mcp(mock_db)
    with sl_patch as mock_sl, gu_patch as mock_gu:
        mock_sl.return_value.__enter__ = MagicMock(return_value=mock_db)
        mock_sl.return_value.__exit__ = MagicMock(return_value=False)
        mock_gu.return_value = mock_user

        mcp = _make_mcp_session()
        result = await mcp.call_tool("record_teach_back_turn", {
            "session_id": "1",
            "confusion_id": "10",
            "child_explanation": "test",
            "verdict": "maybe",  # invalid
            "phase": "evaluate_explanation",
            "next_phase": "present_confusion",
        })

        payload = json.loads(result[0].text)
        assert payload["error"] == "invalid_verdict"
        assert "hit" in payload["detail"] or "miss" in payload["detail"]


# ---------------------------------------------------------------------------
# Confusion topic-scope validation (#22)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_confusion_not_in_topic_rejected(mock_db):
    """A confusion_id from a different topic is rejected."""
    session = _make_session()
    call_count = [0]

    def query_side_effect(model):
        call_count[0] += 1
        if call_count[0] == 1:
            mock_q = MagicMock()
            mock_q.join.return_value = mock_q
            mock_q.filter.return_value = mock_q
            mock_q.first.return_value = session
            return mock_q
        elif call_count[0] == 2:
            mock_q = MagicMock()
            mock_q.filter.return_value = mock_q
            mock_q.first.return_value = None  # confusion not found
            return mock_q
        return MagicMock()

    mock_db.query = query_side_effect

    sl_patch, gu_patch, mock_user = _patch_mcp(mock_db)
    with sl_patch as mock_sl, gu_patch as mock_gu:
        mock_sl.return_value.__enter__ = MagicMock(return_value=mock_db)
        mock_sl.return_value.__exit__ = MagicMock(return_value=False)
        mock_gu.return_value = mock_user

        mcp = _make_mcp_session()
        result = await mcp.call_tool("record_teach_back_turn", {
            "session_id": "1",
            "confusion_id": "999",  # wrong topic
            "child_explanation": "test",
            "verdict": "hit",
            "phase": "evaluate_explanation",
            "next_phase": "present_confusion",
        })

        payload = json.loads(result[0].text)
        assert payload["error"] == "confusion_not_found"


# ---------------------------------------------------------------------------
# Caller-bound child validation (#23)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_wrong_child_rejected(mock_db):
    """A session belonging to a different child is rejected."""
    mock_q = MagicMock()
    mock_q.join.return_value = mock_q
    mock_q.filter.return_value = mock_q
    mock_q.first.return_value = None  # no match (wrong child)
    mock_db.query.return_value = mock_q

    sl_patch, gu_patch, mock_user = _patch_mcp(mock_db)
    with sl_patch as mock_sl, gu_patch as mock_gu:
        mock_sl.return_value.__enter__ = MagicMock(return_value=mock_db)
        mock_sl.return_value.__exit__ = MagicMock(return_value=False)
        mock_gu.return_value = mock_user

        mcp = _make_mcp_session(caller_user_id="1001")
        result = await mcp.call_tool("record_teach_back_turn", {
            "session_id": "1",
            "confusion_id": "10",
            "child_explanation": "test",
            "verdict": "hit",
            "phase": "evaluate_explanation",
            "next_phase": "present_confusion",
        })

        payload = json.loads(result[0].text)
        assert payload["error"] == "session_not_found"
