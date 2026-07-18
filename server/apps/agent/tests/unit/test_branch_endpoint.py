"""Tests for apps.agent.routers.threads — branch endpoint.

Regression guards for the /branches endpoint:
- ``branch_thread`` must create a new thread with copied checkpoint state
- Must validate family_id ownership
- Must find checkpoint containing target message_id
- Must return ThreadBranchResponse with correct metadata
- Must clone the sandbox artifacts when branching from the latest turn (U1)
- Must skip cloning when branching from a historical turn (U1)
- Must remain best-effort when the clone fails (U1)
"""

from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest
from fastapi import HTTPException

from apps.agent.routers.threads import (
    ThreadBranchRequest,
    _ignore_branch_user_data,
    branch_thread,
)


def _verified() -> SimpleNamespace:
    """Stand-in for VerifiedFamily."""
    return SimpleNamespace(family_id="family-1")


def _make_checkpoint_tuple(checkpoint_id: str, messages: list[dict]):
    """Helper to create a mock CheckpointTuple."""
    return SimpleNamespace(
        config={"configurable": {"checkpoint_id": checkpoint_id}},
        checkpoint={
            "id": checkpoint_id,
            "channel_values": {"messages": messages},
            "channel_versions": {"messages": 1},
        },
        metadata={"family_id": "family-1", "created_at": "2026-07-13T00:00:00Z"},
        parent_config=None,
        pending_writes=[],
    )


def _mock_alist(items: list):
    """Create an async iterator mock for checkpointer.alist()."""

    async def alist_iter(*args, **kwargs):
        for item in items:
            yield item

    return alist_iter


async def test_branch_thread_success():
    """branch_thread must create a new thread with copied checkpoint state."""
    messages = [
        {"id": "msg-1", "role": "user", "content": "Hello"},
        {"id": "msg-2", "role": "assistant", "content": "Hi there"},
    ]
    checkpoint_tuple = _make_checkpoint_tuple("ckpt-123", messages)

    with (
        patch("apps.agent.routers.threads.AiSessionRepository") as MockRepo,
        patch("apps.agent.routers.threads.get_checkpointer") as mock_get_ckpt,
    ):
        repo = MockRepo.return_value
        repo.get_session = AsyncMock(
            return_value={
                "session_id": "thread-1",
                "family_id": "family-1",
                "title": "Original Thread",
                "metadata": {},
            }
        )
        repo.upsert = AsyncMock()
        repo.update_summary = AsyncMock()

        checkpointer = mock_get_ckpt.return_value
        checkpointer.alist = _mock_alist([checkpoint_tuple])
        checkpointer.aput = AsyncMock()

        request = ThreadBranchRequest(
            message_id="msg-2",
            message_ids=["msg-2"],
        )

        result = await branch_thread("thread-1", request, "family-1", verified=_verified())

        assert result.thread_id != "thread-1"
        assert result.parent_thread_id == "thread-1"
        assert result.parent_checkpoint_id == "ckpt-123"
        assert result.branched_from_message_id == "msg-2"
        # U1: branching from the latest turn triggers a sandbox clone attempt.
        # The test environment has no sandbox dir on disk, so the clone returns
        # "not_found" but the branch still succeeds.
        assert result.workspace_clone_mode == "not_found"

        # Verify session row was created
        repo.upsert.assert_awaited_once()
        call_args = repo.upsert.call_args
        assert call_args.kwargs["session_id"] == result.thread_id
        assert call_args.kwargs["family_id"] == "family-1"
        assert call_args.kwargs["source"] == "branch"
        # U2: parent_thread_id must propagate through the 6-layer chain to the
        # upsert call, so the branch session row records its parent thread.
        assert call_args.kwargs["parent_thread_id"] == "thread-1"

        # Verify title was set with "分支: " prefix
        repo.update_summary.assert_awaited_once()
        title_call = repo.update_summary.call_args
        assert title_call.kwargs["title"] == "分支: Original Thread"

        # Verify checkpoint was copied
        checkpointer.aput.assert_awaited_once()


async def test_branch_thread_404_when_session_not_found():
    """branch_thread must 404 when source session doesn't exist."""
    with (
        patch("apps.agent.routers.threads.AiSessionRepository") as MockRepo,
        patch("apps.agent.routers.threads.get_checkpointer"),
    ):
        repo = MockRepo.return_value
        repo.get_session = AsyncMock(return_value=None)

        request = ThreadBranchRequest(message_id="msg-1", message_ids=["msg-1"])

        with pytest.raises(HTTPException) as exc:
            await branch_thread("thread-1", request, "family-1", verified=_verified())
        assert exc.value.status_code == 404


async def test_branch_thread_404_when_family_id_mismatch():
    """branch_thread must 404 when family_id doesn't match."""
    with (
        patch("apps.agent.routers.threads.AiSessionRepository") as MockRepo,
        patch("apps.agent.routers.threads.get_checkpointer"),
    ):
        repo = MockRepo.return_value
        repo.get_session = AsyncMock(
            return_value={
                "session_id": "thread-1",
                "family_id": "family-999",  # Different family
                "metadata": {},
            }
        )

        request = ThreadBranchRequest(message_id="msg-1", message_ids=["msg-1"])

        with pytest.raises(HTTPException) as exc:
            await branch_thread("thread-1", request, "family-1", verified=_verified())
        assert exc.value.status_code == 404


async def test_branch_thread_409_when_message_not_found():
    """branch_thread must 409 when target message_id is not in any checkpoint."""
    messages = [
        {"id": "msg-1", "role": "user", "content": "Hello"},
    ]
    checkpoint_tuple = _make_checkpoint_tuple("ckpt-123", messages)

    with (
        patch("apps.agent.routers.threads.AiSessionRepository") as MockRepo,
        patch("apps.agent.routers.threads.get_checkpointer") as mock_get_ckpt,
    ):
        repo = MockRepo.return_value
        repo.get_session = AsyncMock(
            return_value={
                "session_id": "thread-1",
                "family_id": "family-1",
                "metadata": {},
            }
        )

        checkpointer = mock_get_ckpt.return_value
        checkpointer.alist = _mock_alist([checkpoint_tuple])

        request = ThreadBranchRequest(
            message_id="msg-999",  # Not in checkpoint
            message_ids=["msg-999"],
        )

        with pytest.raises(HTTPException) as exc:
            await branch_thread("thread-1", request, "family-1", verified=_verified())
        assert exc.value.status_code == 409
        assert "can no longer be branched from" in exc.value.detail


async def test_branch_thread_preserves_family_id_in_metadata():
    """branch_thread must copy family_id to new thread metadata."""
    messages = [{"id": "msg-1", "role": "assistant", "content": "Hi"}]
    checkpoint_tuple = _make_checkpoint_tuple("ckpt-123", messages)

    with (
        patch("apps.agent.routers.threads.AiSessionRepository") as MockRepo,
        patch("apps.agent.routers.threads.get_checkpointer") as mock_get_ckpt,
    ):
        repo = MockRepo.return_value
        repo.get_session = AsyncMock(
            return_value={
                "session_id": "thread-1",
                "family_id": "family-1",
                "metadata": {},
            }
        )
        repo.upsert = AsyncMock()
        repo.update_summary = AsyncMock()

        checkpointer = mock_get_ckpt.return_value
        checkpointer.alist = _mock_alist([checkpoint_tuple])
        checkpointer.aput = AsyncMock()

        request = ThreadBranchRequest(message_id="msg-1", message_ids=["msg-1"])

        await branch_thread("thread-1", request, "family-1", verified=_verified())

        # Verify aput was called with metadata containing family_id
        checkpointer.aput.assert_awaited_once()
        call_args = checkpointer.aput.call_args
        metadata = call_args[0][2]  # Third positional arg is metadata
        assert metadata["family_id"] == "family-1"
        assert metadata["numina_branch"] is True
        # The per-branch parent_thread_id/checkpoint_id/message_id/created_at
        # are NOT duplicated into checkpoint metadata — they are recoverable from
        # the session row (parent_thread_id column) + the ThreadBranchResponse
        # fields. Only the numina_branch marker is written.
        assert "branch_parent_thread_id" not in metadata
        assert "branch_parent_checkpoint_id" not in metadata
        assert "branch_parent_message_id" not in metadata
        assert "branch_created_at" not in metadata


# ---------------------------------------------------------------------------
# U1: sandbox artifact clone scenarios
# ---------------------------------------------------------------------------

def _make_latest_turn_checkpoint(checkpoint_id: str, assistant_id: str):
    """A checkpoint whose final visible message is the target assistant turn."""
    return _make_checkpoint_tuple(
        checkpoint_id,
        [
            {"id": "u-1", "role": "user", "content": "Hello"},
            {"id": assistant_id, "role": "assistant", "content": "Hi"},
        ],
    )


async def test_branch_clones_sandbox_on_latest_turn(tmp_path):
    """U1 happy path: latest-turn branch + source sandbox exists -> clone called."""
    checkpoint_tuple = _make_latest_turn_checkpoint("ckpt-123", "msg-2")

    with (
        patch("apps.agent.routers.threads.AiSessionRepository") as MockRepo,
        patch("apps.agent.routers.threads.get_checkpointer") as mock_get_ckpt,
        patch("apps.agent.routers.threads._copy_branch_user_data", new=AsyncMock(return_value="current_thread_best_effort")) as mock_copy,
    ):
        repo = MockRepo.return_value
        repo.get_session = AsyncMock(
            return_value={
                "session_id": "thread-1",
                "family_id": "family-1",
                "title": "Original",
                "metadata": {},
            }
        )
        repo.upsert = AsyncMock()
        repo.update_summary = AsyncMock()

        checkpointer = mock_get_ckpt.return_value
        checkpointer.alist = _mock_alist([checkpoint_tuple])
        checkpointer.aput = AsyncMock()

        request = ThreadBranchRequest(message_id="msg-2", message_ids=["msg-2"])
        result = await branch_thread("thread-1", request, "family-1", verified=_verified())

        assert result.workspace_clone_mode == "current_thread_best_effort"
        mock_copy.assert_awaited_once()
        # family_id passed through in raw string form (not int-cast)
        assert mock_copy.call_args.args[0] == "family-1"
        assert mock_copy.call_args.args[1] == "thread-1"
        assert mock_copy.call_args.args[2] == result.thread_id


async def test_branch_skips_clone_on_historical_turn():
    """U1: branching from a historical (non-latest) turn skips cloning."""
    # Two checkpoints: newest has a later assistant turn (msg-3), older has the
    # target (msg-2). Branching from msg-2 is NOT the latest turn -> skip.
    newest = _make_checkpoint_tuple(
        "ckpt-new",
        [
            {"id": "u-1", "role": "user", "content": "Hello"},
            {"id": "msg-2", "role": "assistant", "content": "Hi"},
            {"id": "u-2", "role": "user", "content": "Again"},
            {"id": "msg-3", "role": "assistant", "content": "Hi again"},
        ],
    )

    with (
        patch("apps.agent.routers.threads.AiSessionRepository") as MockRepo,
        patch("apps.agent.routers.threads.get_checkpointer") as mock_get_ckpt,
        patch("apps.agent.routers.threads._copy_branch_user_data", new=AsyncMock()) as mock_copy,
    ):
        repo = MockRepo.return_value
        repo.get_session = AsyncMock(
            return_value={
                "session_id": "thread-1",
                "family_id": "family-1",
                "metadata": {},
            }
        )
        repo.upsert = AsyncMock()
        repo.update_summary = AsyncMock()

        checkpointer = mock_get_ckpt.return_value
        checkpointer.alist = _mock_alist([newest])
        checkpointer.aput = AsyncMock()

        request = ThreadBranchRequest(message_id="msg-2", message_ids=["msg-2"])
        result = await branch_thread("thread-1", request, "family-1", verified=_verified())

        assert result.workspace_clone_mode == "skipped_historical_turn"
        mock_copy.assert_not_awaited()


async def test_branch_clone_failure_is_best_effort():
    """U1: clone raising must not abort the branch; mode == "failed"."""
    checkpoint_tuple = _make_latest_turn_checkpoint("ckpt-123", "msg-2")

    with (
        patch("apps.agent.routers.threads.AiSessionRepository") as MockRepo,
        patch("apps.agent.routers.threads.get_checkpointer") as mock_get_ckpt,
        # Patch the sync helper so the async wrapper's except path runs and
        # returns "failed" — the branch must still succeed (best-effort).
        patch("apps.agent.routers.threads._copy_branch_sandbox_sync", side_effect=RuntimeError("disk full")),
    ):
        repo = MockRepo.return_value
        repo.get_session = AsyncMock(
            return_value={
                "session_id": "thread-1",
                "family_id": "family-1",
                "metadata": {},
            }
        )
        repo.upsert = AsyncMock()
        repo.update_summary = AsyncMock()

        checkpointer = mock_get_ckpt.return_value
        checkpointer.alist = _mock_alist([checkpoint_tuple])
        checkpointer.aput = AsyncMock()

        request = ThreadBranchRequest(message_id="msg-2", message_ids=["msg-2"])
        result = await branch_thread("thread-1", request, "family-1", verified=_verified())

        # Branch created despite clone failure; mode reflects best-effort failure.
        assert result.thread_id != "thread-1"
        assert result.workspace_clone_mode == "failed"


def test_ignore_branch_user_data_filters_part_uploads_and_symlinks(tmp_path):
    """U1: _ignore_branch_user_data skips .upload-*.part files and symlinks."""
    # Real file (kept), partial upload (ignored), symlink (ignored).
    (tmp_path / "report.md").write_text("data")
    (tmp_path / ".upload-abc.part").write_text("partial")
    link = tmp_path / "link-to-outputs"
    link.symlink_to(tmp_path / "report.md")

    names = [p.name for p in tmp_path.iterdir()]
    ignored = _ignore_branch_user_data(str(tmp_path), names)

    assert ".upload-abc.part" in ignored
    assert "link-to-outputs" in ignored
    assert "report.md" not in ignored


def test_copy_branch_sandbox_sync_clones_all_subdirs(tmp_path):
    """U1: copytree covers workspace/, uploads/, outputs/ — not just outputs."""
    from apps.agent.routers.threads import _copy_branch_sandbox_sync

    # Build a sandbox base dir layout matching sandbox_provider.py.
    src_base = tmp_path / "workspaces" / "family-1" / "sandboxes"
    src_thread = src_base / "src-thread"
    for sub in ("workspace", "uploads", "outputs"):
        d = src_thread / sub
        d.mkdir(parents=True)
        (d / "file.txt").write_text(f"{sub}-content")

    with patch("apps.agent.routers.threads.settings.AGENT_DATA_DIR", str(tmp_path / "workspaces")):
        mode = _copy_branch_sandbox_sync("family-1", "src-thread", "tgt-thread")

    assert mode == "current_thread_best_effort"
    tgt = src_base / "tgt-thread"
    for sub in ("workspace", "uploads", "outputs"):
        assert (tgt / sub / "file.txt").read_text() == f"{sub}-content"


def test_copy_branch_sandbox_sync_not_found(tmp_path):
    """U1: source sandbox base absent -> 'not_found'."""
    from apps.agent.routers.threads import _copy_branch_sandbox_sync

    with patch("apps.agent.routers.threads.settings.AGENT_DATA_DIR", str(tmp_path / "workspaces")):
        mode = _copy_branch_sandbox_sync("family-1", "no-such-thread", "tgt-thread")
    assert mode == "not_found"


# ---------------------------------------------------------------------------
# Review-fix regression guards (2026-07-17 ce-code-review)
# ---------------------------------------------------------------------------


async def test_branch_409_when_alist_raises():
    """#2 regression: an alist exception must surface as 409, not silently
    downgrade a latest-turn branch to skipped_historical_turn.

    _find_branch_checkpoint now catches alist failures and returns None, which
    branch_thread translates to 409 — the honest 'cannot branch' signal. The
    previous second-scan design returned False on exception -> branch created
    with workspace_clone_mode='skipped_historical_turn', misrepresenting the
    cause and dropping workspace files for a genuine latest-turn branch.
    """
    with (
        patch("apps.agent.routers.threads.AiSessionRepository") as MockRepo,
        patch("apps.agent.routers.threads.get_checkpointer") as mock_get_ckpt,
    ):
        repo = MockRepo.return_value
        repo.get_session = AsyncMock(
            return_value={
                "session_id": "thread-1",
                "family_id": "family-1",
                "metadata": {},
            }
        )
        repo.upsert = AsyncMock()
        repo.update_summary = AsyncMock()

        checkpointer = mock_get_ckpt.return_value

        async def alist_raise(*args, **kwargs):
            raise RuntimeError("database is locked")
            yield  # pragma: no cover - make it an async generator

        checkpointer.alist = alist_raise
        checkpointer.aput = AsyncMock()

        request = ThreadBranchRequest(message_id="msg-1", message_ids=["msg-1"])
        with pytest.raises(HTTPException) as exc_info:
            await branch_thread("thread-1", request, "family-1", verified=_verified())
        assert exc_info.value.status_code == 409
        # The branch must NOT be created (no upsert) when the source turn cannot
        # be resolved — fail closed at the checkpoint stage.
        repo.upsert.assert_not_awaited()


async def test_branch_from_branch_does_not_double_prefix_title():
    """#3 regression: source_is_branch reads the session-row 'source' field,
    not a non-existent metadata key. A branch-of-branch must not get a
    double '分支: 分支: ' prefix.
    """
    checkpoint_tuple = _make_latest_turn_checkpoint("ckpt-123", "msg-2")

    with (
        patch("apps.agent.routers.threads.AiSessionRepository") as MockRepo,
        patch("apps.agent.routers.threads.get_checkpointer") as mock_get_ckpt,
        patch("apps.agent.routers.threads._copy_branch_user_data", new=AsyncMock(return_value="not_found")),
    ):
        repo = MockRepo.return_value
        # Source is ITSELF a branch: source == "branch". Its title is already
        # prefixed; the new branch must keep it unchanged, not re-prefix.
        repo.get_session = AsyncMock(
            return_value={
                "session_id": "thread-1",
                "family_id": "family-1",
                "title": "分支: Original",
                "source": "branch",
                "metadata": {},
            }
        )
        repo.upsert = AsyncMock()
        repo.update_summary = AsyncMock()

        checkpointer = mock_get_ckpt.return_value
        checkpointer.alist = _mock_alist([checkpoint_tuple])
        checkpointer.aput = AsyncMock()

        request = ThreadBranchRequest(message_id="msg-2", message_ids=["msg-2"])
        await branch_thread("thread-1", request, "family-1", verified=_verified())

        repo.update_summary.assert_awaited_once()
        title_call = repo.update_summary.call_args
        # NOT "分支: 分支: Original" — the nested-prefix guard fires.
        assert title_call.kwargs["title"] == "分支: Original"


async def test_branch_from_non_branch_applies_prefix():
    """#3 complement: a normal (non-branch) source still gets the prefix."""
    checkpoint_tuple = _make_latest_turn_checkpoint("ckpt-123", "msg-2")

    with (
        patch("apps.agent.routers.threads.AiSessionRepository") as MockRepo,
        patch("apps.agent.routers.threads.get_checkpointer") as mock_get_ckpt,
        patch("apps.agent.routers.threads._copy_branch_user_data", new=AsyncMock(return_value="not_found")),
    ):
        repo = MockRepo.return_value
        repo.get_session = AsyncMock(
            return_value={
                "session_id": "thread-1",
                "family_id": "family-1",
                "title": "Original",
                "source": "chat",
                "metadata": {},
            }
        )
        repo.upsert = AsyncMock()
        repo.update_summary = AsyncMock()

        checkpointer = mock_get_ckpt.return_value
        checkpointer.alist = _mock_alist([checkpoint_tuple])
        checkpointer.aput = AsyncMock()

        request = ThreadBranchRequest(message_id="msg-2", message_ids=["msg-2"])
        await branch_thread("thread-1", request, "family-1", verified=_verified())

        title_call = repo.update_summary.call_args
        assert title_call.kwargs["title"] == "分支: Original"


def test_copy_branch_sandbox_sync_replaces_stale_target(tmp_path):
    """#4 regression: a pre-existing/partial target dir must be REPLACED, not
    merged into. dirs_exist_ok=True alone merges new over old, leaving a mixed
    stale+new artifact set reported as success.
    """
    from apps.agent.routers.threads import _copy_branch_sandbox_sync

    # Path scheme: AGENT_DATA_DIR / {family_id} / "sandboxes" / {thread_id}
    src_base = tmp_path / "family-1" / "sandboxes"
    src_thread = src_base / "src-thread"
    (src_thread / "outputs").mkdir(parents=True)
    (src_thread / "outputs" / "new_report.md").write_text("new")

    # Stale partial target from an interrupted prior clone: has an OLD file
    # that is NOT in the source. With dirs_exist_ok=True alone this would
    # survive the clone (merge), surfacing as a stale downloadable artifact.
    tgt_thread = src_base / "tgt-thread"
    (tgt_thread / "outputs").mkdir(parents=True)
    (tgt_thread / "outputs" / "stale_report.md").write_text("old")

    with patch("apps.agent.routers.threads.settings.AGENT_DATA_DIR", str(tmp_path)):
        mode = _copy_branch_sandbox_sync("family-1", "src-thread", "tgt-thread")

    assert mode == "current_thread_best_effort"
    # New file present
    assert (tgt_thread / "outputs" / "new_report.md").read_text() == "new"
    # Stale file REMOVED (replace, not merge)
    assert not (tgt_thread / "outputs" / "stale_report.md").exists()


def test_ignore_branch_user_data_filters_temp_suffixes(tmp_path):
    """#11 regression: temp-file ignore is broader than .upload-*.part —
    .tmp/.partial/.swp/.swo leftovers must not clone as fake artifacts.
    """
    from apps.agent.routers.threads import _ignore_branch_user_data

    (tmp_path / "report.md").write_text("data")
    (tmp_path / "draft.tmp").write_text("temp")
    (tmp_path / "upload.partial").write_text("partial")
    (tmp_path / "edit.swp").write_text("swap")
    (tmp_path / ".upload-xyz.part").write_text("part-upload")

    names = [p.name for p in tmp_path.iterdir()]
    ignored = _ignore_branch_user_data(str(tmp_path), names)

    assert "draft.tmp" in ignored
    assert "upload.partial" in ignored
    assert "edit.swp" in ignored
    assert ".upload-xyz.part" in ignored
    assert "report.md" not in ignored


async def test_copy_branch_user_data_timeout_is_best_effort():
    """#5 regression: a copytree that exceeds the wait_for timeout degrades to
    'failed' (best-effort) rather than hanging the branch request.

    Patches ``asyncio.to_thread`` to return a long-awaited coroutine (which
    ``wait_for`` CAN cancel cleanly) rather than a real blocking thread — a
    real ``time.sleep`` in a thread cannot be interrupted by ``wait_for`` and
    would leak the thread. This isolates the timeout -> 'failed' path.
    """
    import asyncio

    from apps.agent.routers.threads import _copy_branch_user_data

    real_to_thread = asyncio.to_thread

    async def slow_to_thread(*args, **kwargs):
        # Simulate a stalled mount: never completes within the test's window.
        # wait_for cancels this coroutine on timeout (unlike a real thread).
        await asyncio.sleep(3600)

    with (
        patch("apps.agent.routers.threads.asyncio.to_thread", side_effect=slow_to_thread),
        patch("apps.agent.routers.threads._BRANCH_CLONE_TIMEOUT_SECONDS", 0.01),
    ):
        mode = await _copy_branch_user_data("family-1", "src", "tgt")
    assert mode == "failed"
    # Sanity: the real asyncio.to_thread is unchanged outside the patch.
    assert asyncio.to_thread is real_to_thread


async def test_get_thread_404_on_family_mismatch():
    """#7 regression: get_thread record-path must enforce family ownership
    explicitly (defense-in-depth), not rely solely on the BackendClient filter.
    U4 parent-link navigation pushes attacker-influenced thread_ids here.
    """
    from apps.agent.routers.threads import get_thread

    with (
        patch("apps.agent.routers.threads.AiSessionRepository") as MockRepo,
        patch("apps.agent.routers.threads.get_checkpointer") as mock_get_ckpt,
    ):
        repo = MockRepo.return_value
        # Record exists but belongs to a DIFFERENT family.
        repo.get_session = AsyncMock(
            return_value={
                "session_id": "thread-1",
                "family_id": "family-OTHER",
                "status": "idle",
                "metadata": {},
            }
        )
        checkpointer = mock_get_ckpt.return_value
        checkpointer.aget_tuple = AsyncMock(return_value=None)

        # verified.family_id is "family-1" (see _verified()).
        with pytest.raises(HTTPException) as exc_info:
            await get_thread("thread-1", x_family_id="family-1", verified=_verified())
        assert exc_info.value.status_code == 404
