"""Tests for ai_internal session summary — original_title preservation.

Regression guard: when the user manually renames a session, the auto-generated
title (produced by DeerFlow's TitleMiddleware) must be preserved in
``original_title`` on the first rename, and never overwritten on subsequent
renames.

Ported from the former apps/backend/tests/unit/test_ai_internal_session_title.py.
"""

from types import SimpleNamespace
from unittest.mock import MagicMock

from apps.backend.app.routers.ai_internal import (
    SessionSummaryRequest,
    SessionUpsertRequest,
    _session_to_dict,
    internal_update_session_summary,
    internal_upsert_session,
)


def _fake_row(title, original_title, family_id=1):
    return SimpleNamespace(
        title=title,
        original_title=original_title,
        family_id=family_id,
        status="idle",
        last_model=None,
        is_pinned=False,
        updated_at=None,
        last_message_summary=None,
    )


def _mock_db(row):
    db = MagicMock()
    db.query.return_value.filter.return_value.first.return_value = row
    return db


def test_first_rename_preserves_auto_title_as_original():
    """First manual rename copies the existing auto-title into original_title."""
    row = _fake_row(title="自动生成标题", original_title=None)
    db = _mock_db(row)

    result = internal_update_session_summary(
        "thread-1", SessionSummaryRequest(title="我的重命名"), family_id="1", db=db
    )

    assert result == {"ok": True}
    assert row.original_title == "自动生成标题"
    assert row.title == "我的重命名"
    db.commit.assert_called_once()


def test_second_rename_does_not_overwrite_original():
    """Subsequent renames must not overwrite the preserved original_title."""
    row = _fake_row(title="第一次重命名", original_title="自动生成标题")
    db = _mock_db(row)

    internal_update_session_summary(
        "thread-1", SessionSummaryRequest(title="第二次重命名"), family_id="1", db=db
    )

    assert row.original_title == "自动生成标题"
    assert row.title == "第二次重命名"


def test_auto_title_sync_does_not_set_original_when_no_existing_title():
    """When the auto-title is first synced (row.title is None), nothing to preserve."""
    row = _fake_row(title=None, original_title=None)
    db = _mock_db(row)

    internal_update_session_summary(
        "thread-1", SessionSummaryRequest(title="自动生成标题"), family_id="1", db=db
    )

    assert row.original_title is None
    assert row.title == "自动生成标题"


# ---------------------------------------------------------------------------
# U2: parent_thread_id 6-layer propagation
# ---------------------------------------------------------------------------

def test_upsert_session_writes_parent_thread_id_on_create():
    """U2: internal_upsert_session must persist parent_thread_id on a new branch row."""
    db = MagicMock()
    db.query.return_value.filter.return_value.first.return_value = None  # no existing row

    internal_upsert_session(
        SessionUpsertRequest(
            session_id="new-thread",
            user_id="42",
            agent_id=None,
            last_model=None,
            source="branch",
            parent_thread_id="parent-thread",
        ),
        family_id="1",
        db=db,
    )

    db.add.assert_called_once()
    added = db.add.call_args.args[0]
    assert added.parent_thread_id == "parent-thread"
    assert added.source == "branch"
    db.commit.assert_called_once()


def test_upsert_session_parent_thread_id_defaults_none():
    """U2: non-branch upsert (no parent_thread_id) leaves the column None."""
    db = MagicMock()
    db.query.return_value.filter.return_value.first.return_value = None

    internal_upsert_session(
        SessionUpsertRequest(
            session_id="plain-thread",
            user_id="42",
        ),
        family_id="1",
        db=db,
    )

    added = db.add.call_args.args[0]
    assert added.parent_thread_id is None


def test_session_to_dict_exposes_parent_thread_id():
    """U2: _session_to_dict must surface parent_thread_id for list/detail APIs."""
    row = SimpleNamespace(
        id="thread-1",
        family_id=1,
        user_id=42,
        agent_id=None,
        title="Branch",
        original_title=None,
        status="idle",
        last_message_summary=None,
        last_model=None,
        is_pinned=False,
        source="branch",
        parent_thread_id="parent-thread",
        created_at=None,
        updated_at=None,
    )

    d = _session_to_dict(row)
    assert d["parent_thread_id"] == "parent-thread"
    assert d["source"] == "branch"
