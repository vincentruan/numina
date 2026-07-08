"""Tests for ai_internal session summary — original_title preservation.

Regression guard: when the user manually renames a session, the auto-generated
title (produced by DeerFlow's TitleMiddleware) must be preserved in
``original_title`` on the first rename, and never overwritten on subsequent
renames.
"""

from types import SimpleNamespace
from unittest.mock import MagicMock

from apps.backend.app.routers.ai_internal import (
    SessionSummaryRequest,
    internal_update_session_summary,
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
