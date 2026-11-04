"""Tests for finance-coach empty-suggestions persist fix (U2).

Verifies that _persist_coach_result always persists to AIReport,
even when suggestions is empty (a valid LLM output per SKILL.md).

Strategy: directly call the route handler with mocked dependencies
to capture the on_result callback, then invoke it.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from apps.backend.app.routers import ai_finance_coach as _mod


async def _capture_callback():
    """Call the route handler with all deps mocked; return the on_result callback."""
    captured = {}

    async def _fake_trigger(*args, **kwargs):
        captured["callback"] = kwargs.get("on_result")
        from fastapi.responses import JSONResponse
        return JSONResponse({"task_id": "t1", "status": "queued"})

    mock_user = MagicMock()
    mock_user.id = "user1"
    mock_user.family_id = "fam1"
    mock_user.language = "zh"

    mock_session = MagicMock()
    mock_session.id = 12345

    mock_task = MagicMock()
    mock_task.id = 67890
    mock_task.session_id = 12345
    mock_task.run_id = None

    mock_db = MagicMock()

    snapshot_with_data = {
        "high_interest_debts": [{"id": "d1"}],
        "idle_assets": [],
        "top_daily_cost_assets": [],
        "wishes": [],
    }

    with (
        patch.object(_mod, "check_circuit_blocked", return_value=None),
        patch.object(_mod, "latest_by_skill", return_value=None),
        patch.object(_mod, "is_cache_fresh", return_value=False),
        patch.object(_mod.AITaskService, "get_running_task", return_value=None),
        patch.object(_mod, "_check_ai_enabled"),
        patch.object(_mod.ChatSessionService, "create_session", new=AsyncMock(return_value=mock_session)),
        patch.object(_mod.AITaskService, "get_any_running_task", return_value=None),
        patch.object(_mod.AITaskService, "create_task", return_value=mock_task),
        patch.object(_mod, "build_family_finance_snapshot", return_value=snapshot_with_data),
        patch.object(_mod, "trigger_and_stream", new=AsyncMock(side_effect=_fake_trigger)),
    ):
        await _mod.trigger_finance_coach(
            request=MagicMock(),
            force=True,
            current_user=mock_user,
            _owner=None,
            db=mock_db,
        )

    return captured.get("callback")


# ── Branch 1: normal suggestions ──────────────────────────────────


@pytest.mark.asyncio
async def test_persist_normal_suggestions():
    """Normal suggestions → upsert_skill_result called."""
    callback = await _capture_callback()
    assert callback is not None, "Failed to capture the on_result callback"

    with (
        patch("apps.backend.app.database.SessionLocal") as mock_sf,
        patch.object(_mod, "upsert_skill_result") as mock_upsert,
    ):
        mock_db = MagicMock()
        mock_sf.return_value = mock_db

        await callback("custom", {
            "type": "finance_coach.result",
            "payload": {"suggestions": [{"id": "s1", "severity": "high"}]},
        })

        mock_upsert.assert_called_once()
        mock_db.commit.assert_called_once()


# ── Branch 2: empty suggestions (the fix) ────────────────────────


@pytest.mark.asyncio
async def test_persist_empty_suggestions():
    """Empty suggestions → upsert_skill_result STILL called (the fix)."""
    callback = await _capture_callback()
    assert callback is not None, "Failed to capture the on_result callback"

    with (
        patch("apps.backend.app.database.SessionLocal") as mock_sf,
        patch.object(_mod, "upsert_skill_result") as mock_upsert,
    ):
        mock_db = MagicMock()
        mock_sf.return_value = mock_db

        await callback("custom", {
            "type": "finance_coach.result",
            "payload": {"suggestions": []},
        })

        mock_upsert.assert_called_once()
        mock_db.commit.assert_called_once()


# ── Branch 3: None payload ──────────────────────────────────────


@pytest.mark.asyncio
async def test_persist_none_payload_skipped():
    """None payload → upsert_skill_result NOT called (guard)."""
    callback = await _capture_callback()
    assert callback is not None, "Failed to capture the on_result callback"

    with patch.object(_mod, "upsert_skill_result") as mock_upsert:
        await callback("custom", {
            "type": "finance_coach.result",
            "payload": None,
        })
        mock_upsert.assert_not_called()
