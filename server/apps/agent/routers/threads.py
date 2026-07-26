"""Thread CRUD, state, and history endpoints for Numina Agent.

Combines the LangGraph checkpointer state with the Numina Backend
session storage (via AiSessionRepository) for fast metadata querying.
"""

from __future__ import annotations

import asyncio
import contextlib
import logging
import shutil
import uuid
from pathlib import Path
from typing import Any, Literal

from deerflow.utils.time import coerce_iso, now_iso
from fastapi import APIRouter, Depends, Header, HTTPException, Request
from langgraph.checkpoint.base import empty_checkpoint, uuid6
from pydantic import BaseModel, Field, field_validator

from apps.agent.app.auth.jwt_verify import VerifiedFamily, verify_family_token
from apps.agent.services.compact_service import (
    ContextCompactionDisabled,
    ContextCompactionFailed,
    compact_thread,
    result_to_dict,
)
from apps.agent.services.deerflow_adapter.family_adapter_cache import (
    _get_shared_checkpointer,
)
from apps.agent.services.goal_store import (
    DEFAULT_MAX_GOAL_CONTINUATIONS,
    GoalWriteConflict,
    build_goal_state,
    goal_thread_lock,
    read_thread_goal,
    write_thread_goal,
)
from apps.agent.services.runtime.lifespan import get_run_manager
from apps.agent.services.session_store import AiSessionRepository


def serialize_channel_values_for_api(values: dict[str, Any]) -> dict[str, Any]:
    """Convert channel values (including LangChain messages) to dicts for API response."""
    from langchain_core.messages import BaseMessage

    result: dict[str, Any] = {}
    for k, v in values.items():
        if isinstance(v, list):
            result[k] = [m.model_dump() if isinstance(m, BaseMessage) else m for m in v]
        elif isinstance(v, BaseMessage):
            result[k] = v.model_dump()
        else:
            result[k] = v
    return result


logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/threads", tags=["threads"])

# Metadata keys that the server controls; clients are not allowed to set them.
_SERVER_RESERVED_METADATA_KEYS: frozenset[str] = frozenset(
    {"owner_id", "user_id", "family_id"}
)


def _strip_reserved_metadata(metadata: dict[str, Any] | None) -> dict[str, Any]:
    if not metadata:
        return metadata or {}
    return {
        k: v for k, v in metadata.items() if k not in _SERVER_RESERVED_METADATA_KEYS
    }


# ---------------------------------------------------------------------------
# Response / request models
# ---------------------------------------------------------------------------


class ThreadDeleteResponse(BaseModel):
    success: bool
    message: str


class ThreadResponse(BaseModel):
    thread_id: str = Field(description="Unique thread identifier")
    status: str = Field(default="idle", description="Thread status")
    created_at: str = Field(default="", description="ISO timestamp")
    updated_at: str = Field(default="", description="ISO timestamp")
    metadata: dict[str, Any] = Field(
        default_factory=dict, description="Thread metadata"
    )
    values: dict[str, Any] = Field(
        default_factory=dict, description="Current state channel values"
    )
    interrupts: dict[str, Any] = Field(
        default_factory=dict, description="Pending interrupts"
    )


class ThreadCreateRequest(BaseModel):
    thread_id: str | None = Field(
        default=None, description="Optional thread ID (auto-generated if omitted)"
    )
    assistant_id: str | None = Field(
        default=None, description="Associate thread with an assistant"
    )
    metadata: dict[str, Any] = Field(
        default_factory=dict, description="Initial metadata"
    )

    _strip_reserved = field_validator("metadata")(
        classmethod(lambda cls, v: _strip_reserved_metadata(v))
    )


class ThreadSearchRequest(BaseModel):
    metadata: dict[str, Any] = Field(
        default_factory=dict, description="Metadata filter (exact match)"
    )
    limit: int = Field(default=100, ge=1, le=1000, description="Maximum results")
    offset: int = Field(default=0, ge=0, description="Pagination offset")
    sortBy: str | None = Field(default="updated_at", description="Sort column")
    sortOrder: str | None = Field(default="desc", description="Sort order (asc/desc)")


class ThreadStateResponse(BaseModel):
    values: dict[str, Any] = Field(
        default_factory=dict, description="Current channel values"
    )
    next: list[str] = Field(default_factory=list, description="Next tasks to execute")
    metadata: dict[str, Any] = Field(
        default_factory=dict, description="Checkpoint metadata"
    )
    checkpoint: dict[str, Any] = Field(
        default_factory=dict, description="Checkpoint info"
    )
    checkpoint_id: str | None = Field(default=None, description="Current checkpoint ID")
    parent_checkpoint_id: str | None = Field(
        default=None, description="Parent checkpoint ID"
    )
    created_at: str | None = Field(default=None, description="Checkpoint timestamp")
    tasks: list[dict[str, Any]] = Field(
        default_factory=list, description="Interrupted task details"
    )


class ThreadPatchRequest(BaseModel):
    metadata: dict[str, Any] = Field(
        default_factory=dict, description="Metadata to merge"
    )
    title: str | None = Field(default=None, description="Session title")
    is_pinned: bool | None = Field(default=None, description="Pin/unpin session")
    _strip_reserved = field_validator("metadata")(
        classmethod(lambda cls, v: _strip_reserved_metadata(v))
    )


class ThreadStateUpdateRequest(BaseModel):
    values: dict[str, Any] | None = Field(
        default=None, description="Channel values to merge"
    )
    checkpoint_id: str | None = Field(
        default=None, description="Checkpoint to branch from"
    )
    checkpoint: dict[str, Any] | None = Field(
        default=None, description="Full checkpoint object"
    )
    as_node: str | None = Field(
        default=None, description="Node identity for the update"
    )


class ThreadGoalRequest(BaseModel):
    """Request body for setting a thread-scoped goal (DeerFlow threads.py:320-329)."""

    objective: str = Field(
        ..., min_length=1, max_length=4000, description="目标完成条件"
    )
    max_continuations: int = Field(
        default=DEFAULT_MAX_GOAL_CONTINUATIONS,
        ge=0,
        le=DEFAULT_MAX_GOAL_CONTINUATIONS,
        description="最大自动延续轮数",
    )


class ThreadGoalResponse(BaseModel):
    """Response model for a thread goal (DeerFlow threads.py:332-335)."""

    goal: dict[str, Any] | None = Field(
        default=None, description="当前目标状态，无目标时为 null"
    )


class ThreadCompactRequest(BaseModel):
    """Request body for manual context compaction (DeerFlow threads.py:320)."""

    agent_name: str | None = Field(
        default=None,
        description="Optional agent name for the summarization LLM context",
    )


class ThreadCompactResponse(BaseModel):
    """Response for ``POST /{thread_id}/compact`` (DeerFlow threads.py:332-335)."""

    compacted: bool = Field(description="Whether compaction actually occurred")
    reason: str | None = Field(
        default=None,
        description="Skip reason when not compacted (e.g. not_enough_messages)",
    )
    removed_count: int = Field(default=0, description="Messages summarized and removed")
    preserved_count: int = Field(
        default=0, description="Messages kept in the visible tail"
    )
    summary_updated: bool = Field(
        default=False, description="Whether summary_text was updated"
    )
    checkpoint_id: str | None = Field(
        default=None, description="New checkpoint ID after compaction"
    )
    total_tokens: int = Field(
        default=0, description="Token count of the produced summary"
    )


class HistoryEntry(BaseModel):
    checkpoint_id: str
    parent_checkpoint_id: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
    values: dict[str, Any] = Field(default_factory=dict)
    created_at: str | None = None
    next: list[str] = Field(default_factory=list)


class ThreadHistoryRequest(BaseModel):
    limit: int = Field(default=10, ge=1, le=100, description="Maximum entries")
    before: str | None = Field(default=None, description="Cursor for pagination")


# ---------------------------------------------------------------------------
# Branch models (DeerFlow threads.py:375-388)
# ---------------------------------------------------------------------------

# Metadata key marking a thread as a branch (DeerFlow uses "deerflow_branch")
_BRANCH_METADATA_KEY = "numina_branch"

# Sandbox artifact clone outcome (single source of truth for the values that
# cross the backend->frontend boundary as ``ThreadBranchResponse.workspace_clone_mode``
# and the frontend ``branchCloneWarnKey`` switch). Mirrors DeerFlow's modes:
# - ``current_thread_best_effort``: cloned from the latest turn
# - ``skipped_historical_turn``: branch from an older turn — workspace files
#   would leak a later timeline, so not cloned
# - ``not_found``: source sandbox dir absent
# - ``failed``: clone raised, branch still created (best-effort)
WorkspaceCloneMode = Literal[
    "current_thread_best_effort",
    "skipped_historical_turn",
    "not_found",
    "failed",
]


class ThreadBranchRequest(BaseModel):
    """Request body for branching a thread from a completed assistant turn."""

    message_id: str = Field(description="AI message ID to branch from")
    message_ids: list[str] = Field(
        default_factory=list,
        description="All AI message IDs in the same turn",
    )
    title: str | None = Field(default=None, description="Optional branch title")


class ThreadBranchResponse(BaseModel):
    """Response from branch endpoint (DeerFlow threads.py:383-388)."""

    thread_id: str
    parent_thread_id: str
    parent_checkpoint_id: str
    branched_from_message_id: str
    # Sandbox artifact clone outcome. Typed as ``WorkspaceCloneMode`` so a typo
    # on either side of the backend->frontend boundary is a contract break, not
    # a silent fall-through to the no-warning branch. Required — ``branch_thread``
    # always sets it explicitly before returning. See ``WorkspaceCloneMode``
    # above for the value semantics.
    workspace_clone_mode: WorkspaceCloneMode


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _derive_thread_status(checkpoint_tuple) -> str:
    if checkpoint_tuple is None:
        return "idle"
    pending_writes = getattr(checkpoint_tuple, "pending_writes", None) or []
    for pw in pending_writes:
        if len(pw) >= 2 and pw[1] == "__error__":
            return "error"
    tasks = getattr(checkpoint_tuple, "tasks", None)
    if tasks:
        return "interrupted"
    return "idle"


def get_checkpointer():
    return _get_shared_checkpointer(None)


# ---------------------------------------------------------------------------
# Branch helpers (DeerFlow threads.py:135-210)
# ---------------------------------------------------------------------------


async def _find_branch_checkpoint(
    checkpointer, thread_id: str, target_message_ids: set[str]
) -> tuple[Any, bool] | None:
    """Find the checkpoint containing the target message IDs.

    DeerFlow 参考：threads.py:135-145
    Scans checkpoint history (limit 100) and returns the first tuple whose
    ``channel_values.messages`` contains a message whose id is in
    ``target_message_ids``. Returns ``None`` when no match is found.

    The scan is newest-first (``alist`` yields newest-first), so the first
    checkpoint holding the target messages IS the thread's latest turn that
    contains them. The returned bool is whether those target messages form
    the tail visible assistant turn in that checkpoint (i.e. the branch is
    from the genuinely latest turn, safe to clone workspace files). Resolving
    both the source checkpoint and the latest-turn decision in ONE scan
    avoids a second ``alist`` call and its TOCTOU window (a concurrent run
    checkpointing a newer turn between scans would otherwise downgrade a
    latest-turn branch to ``skipped_historical_turn``).
    """
    config = {"configurable": {"thread_id": thread_id, "checkpoint_ns": ""}}
    try:
        async for checkpoint_tuple in checkpointer.alist(
            config, limit=_BRANCH_HISTORY_SCAN_LIMIT
        ):
            messages = _checkpoint_messages(checkpoint_tuple)
            for msg in messages:
                msg_id = getattr(msg, "id", None) or (
                    msg.get("id") if isinstance(msg, dict) else None
                )
                if msg_id and msg_id in target_message_ids:
                    is_latest_turn = _matches_branch_target(
                        messages, target_message_ids
                    )
                    return checkpoint_tuple, is_latest_turn
    except Exception:
        logger.warning(
            "Failed to scan checkpoints for thread %s; branch cannot resolve source turn",
            thread_id,
            exc_info=True,
        )
        return None
    return None


def _checkpoint_id(checkpoint_tuple) -> str | None:
    """Extract checkpoint_id from a CheckpointTuple (DeerFlow threads.py helper)."""
    if checkpoint_tuple is None:
        return None
    checkpoint_id_val = (
        getattr(checkpoint_tuple, "config", {})
        .get("configurable", {})
        .get("checkpoint_id")
    )
    return str(checkpoint_id_val) if checkpoint_id_val is not None else None


def _default_branch_display_name(
    source_title: str | None, *, source_is_branch: bool = False
) -> str | None:
    """Derive a display name for a branch (DeerFlow threads.py:211-224).

    - If the source has no title, return None (caller keeps the source title).
    - If the source is already a branch, keep its title unchanged (avoid
      "分支: 分支: 分支: ..." nesting).
    - Otherwise, prefix with "分支: ".
    """
    if not source_title:
        return None
    if source_is_branch:
        return source_title
    return f"分支: {source_title}"


# ---------------------------------------------------------------------------
# Branch sandbox artifact clone helpers (DeerFlow threads.py:147-210)
# ---------------------------------------------------------------------------

# Cap on checkpoint history scan when resolving the latest turn (matches
# DeerFlow _BRANCH_HISTORY_SCAN_LIMIT).
_BRANCH_HISTORY_SCAN_LIMIT = 100


def _checkpoint_messages(checkpoint_tuple) -> list[Any]:
    """Extract the messages list from a CheckpointTuple's channel_values."""
    checkpoint = getattr(checkpoint_tuple, "checkpoint", {}) or {}
    return list(checkpoint.get("channel_values", {}).get("messages", []))


def _message_id(message: Any) -> str | None:
    """Extract the id from a message that may be a BaseMessage or a dict."""
    return getattr(message, "id", None) or (
        message.get("id") if isinstance(message, dict) else None
    )


def _is_branch_assistant_message(message: Any) -> bool:
    """Return True if the message is an assistant message eligible to branch from."""
    role = getattr(message, "type", None) or (
        message.get("role") if isinstance(message, dict) else None
    )
    return role in ("ai", "assistant")


def _is_branch_visible_message(message: Any) -> bool:
    """Return True if the message is visible in the conversation timeline.

    Excludes tool messages (which are not user-facing turns) so a trailing
    tool message does not disqualify an otherwise-latest assistant turn.
    """
    role = getattr(message, "type", None) or (
        message.get("role") if isinstance(message, dict) else None
    )
    return role not in ("tool", "function")


def _matches_branch_target(messages: list[Any], target_message_ids: set[str]) -> bool:
    """Return True when target_message_ids form the tail visible assistant turn.

    DeerFlow threads.py:147-160. The targets must all be assistant messages and
    there must be no visible message after the last target (i.e. the target turn
    is the final visible turn in this checkpoint).
    """
    if not target_message_ids:
        return False
    index_by_id = {_message_id(m): i for i, m in enumerate(messages) if _message_id(m)}
    if not target_message_ids.issubset(index_by_id.keys()):
        return False
    if any(
        not _is_branch_assistant_message(messages[index_by_id[mid]])
        for mid in target_message_ids
    ):
        return False
    target_end_index = max(index_by_id[mid] for mid in target_message_ids)
    return not any(
        _is_branch_visible_message(m) for m in messages[target_end_index + 1 :]
    )


def _ignore_branch_user_data(directory: str, names: list[str]) -> set[str]:
    """shutil.copytree ignore predicate (DeerFlow threads.py:176-185).

    Skips partial-upload temp files and symbolic links so the branch does not
    inherit broken/partial artifacts. The temp-file patterns cover the
    interrupted-upload markers the upload path produces (``.upload-*.part``)
    plus common editor/transfer leftovers (``.tmp``, ``.partial``, ``.swp``,
    ``.swo``) that would otherwise clone as fake downloadable artifacts.
    Symlinks are skipped at every directory level copytree descends into (the
    predicate is invoked per-directory), so nested symlinks are excluded too
    rather than dereferenced and copied.
    """
    ignored: set[str] = set()
    base = Path(directory)
    for name in names:
        path = base / name
        if path.is_symlink():
            ignored.add(name)
            continue
        if _is_branch_temp_artifact(name):
            ignored.add(name)
    return ignored


# Temp-file suffixes/patterns excluded from a branch clone. Extend here when a
# new upload/transfer path introduces another partial-write marker.
_BRANCH_TEMP_SUFFIXES = (".tmp", ".partial", ".part", ".swp", ".swo")


def _is_branch_temp_artifact(name: str) -> bool:
    """Return True for partial-upload temp files and editor/transfer leftovers."""
    if name.startswith(".upload-") and name.endswith(".part"):
        return True
    return name.endswith(_BRANCH_TEMP_SUFFIXES)


def _copy_branch_sandbox_sync(
    family_id: str, source_thread_id: str, target_thread_id: str
) -> str:
    """Synchronously copy the source thread's sandbox user-data dir onto the branch.

    Resolves the sandbox thread directory via DeerFlow's paths API (unified
    layout 2026-07-19): ``{DEER_FLOW_HOME}/users/{family_id}/threads/{thread_id}/``
    — aligned with ``sandbox_provider.py`` which uses the same DeerFlow layout.
    The family_id is used in its raw string form exactly as the sandbox provider
    receives it (it is NOT cast to int here — the provider uses the string form,
    and casting would mismatch the on-disk path for non-numeric family IDs).
    ``copytree`` covers ``user-data/{workspace,uploads,outputs}`` (the full
    thread dir, aligning with DeerFlow's whole-user-data clone). Returns one of:
    ``"not_found"`` (source thread dir absent), ``"current_thread_best_effort"`` (copied),
    ``"failed"`` (raised).

    The target_thread_id is a freshly-generated UUID (a brand-new branch), so
    any pre-existing occupant at the target path is a stale partial clone left
    by an interrupted prior attempt or a lazy-mkdir empty. It is cleared before
    copytree so the clone is the single source of truth — without this,
    ``dirs_exist_ok=True`` would MERGE the new source over stale partial files
    without removing them, yielding a mixed stale+new artifact set reported as
    ``"current_thread_best_effort"`` (success).
    """
    from deerflow.config.paths import get_paths

    paths = get_paths()
    # DeerFlow layout: {DEER_FLOW_HOME}/users/{family_id}/threads/{tid}/
    source = Path(paths.host_thread_dir(source_thread_id, user_id=family_id))
    target = Path(paths.host_thread_dir(target_thread_id, user_id=family_id))
    if not source.exists():
        return "not_found"
    if target.exists():
        # Fresh branch UUID: a pre-existing target is a stale/partial clone.
        # Clear it so copytree does not merge new over old.
        shutil.rmtree(target, ignore_errors=True)
    shutil.copytree(source, target, ignore=_ignore_branch_user_data, dirs_exist_ok=True)
    return "current_thread_best_effort"


# Upper bound on a single sandbox clone. AGENT_DATA_DIR may sit on a shared/NFS
# volume; without a cap a large sandbox or stalled mount hangs the branch
# request (and the frontend branch button) indefinitely. On timeout the clone
# degrades to "failed" — the branch is already created, so this is best-effort.
_BRANCH_CLONE_TIMEOUT_SECONDS = 60


async def _copy_branch_user_data(
    family_id: str, source_thread_id: str, target_thread_id: str
) -> str:
    """Async wrapper around the sync sandbox clone (DeerFlow threads.py:202-210).

    File IO is offloaded via ``asyncio.to_thread`` to avoid blocking the event
    loop on large sandbox dirs, and bounded by ``asyncio.wait_for`` so a large
    sandbox or a stalled mount cannot hang the branch request indefinitely.
    Failures are best-effort: the branch is already created (checkpoint +
    session row written), so a clone failure or timeout only yields
    ``"failed"`` and a warning rather than aborting the branch.
    """
    try:
        return await asyncio.wait_for(
            asyncio.to_thread(
                _copy_branch_sandbox_sync, family_id, source_thread_id, target_thread_id
            ),
            timeout=_BRANCH_CLONE_TIMEOUT_SECONDS,
        )
    except TimeoutError:
        logger.warning(
            "Timed out copying sandbox for branch %s -> %s after %ss",
            source_thread_id,
            target_thread_id,
            _BRANCH_CLONE_TIMEOUT_SECONDS,
        )
        return "failed"
    except Exception:
        logger.warning(
            "Failed to copy sandbox for branch %s -> %s",
            source_thread_id,
            target_thread_id,
            exc_info=True,
        )
        return "failed"


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.delete("/{thread_id}", response_model=ThreadDeleteResponse)
async def delete_thread(
    thread_id: str,
    x_family_id: str = Header(..., alias="X-Family-Id"),
    verified: VerifiedFamily = Depends(verify_family_token),
) -> ThreadDeleteResponse:
    # Delete the persistent session row (ai_chat_sessions) so the thread does
    # not reappear in search after deletion, then best-effort drop the
    # checkpointer state.
    repo = AiSessionRepository(x_family_id)
    deleted = await repo.delete_session(session_id=thread_id, family_id=x_family_id)
    if not deleted:
        raise HTTPException(
            status_code=503, detail="Failed to delete thread from database"
        )
    checkpointer = get_checkpointer()
    if hasattr(checkpointer, "adelete_thread"):
        with contextlib.suppress(Exception):
            await checkpointer.adelete_thread(thread_id)
    return ThreadDeleteResponse(success=True, message="Thread deleted")


@router.post("", response_model=ThreadResponse)
async def create_thread(
    body: ThreadCreateRequest,
    x_family_id: str = Header(..., alias="X-Family-Id"),
    x_user_id: str = Header(None, alias="X-User-Id"),
    verified: VerifiedFamily = Depends(verify_family_token),
) -> ThreadResponse:
    checkpointer = get_checkpointer()
    repo = AiSessionRepository(x_family_id)
    thread_id = body.thread_id or str(uuid.uuid4())
    now = now_iso()

    existing = await repo.get_session(thread_id)
    if existing:
        return ThreadResponse(
            thread_id=thread_id,
            status=existing.get("status", "idle"),
            created_at=coerce_iso(existing.get("created_at", "")),
            updated_at=coerce_iso(existing.get("updated_at", "")),
            metadata=existing.get("metadata", {}),
        )

    # Upsert session
    await repo.upsert(
        session_id=thread_id,
        family_id=x_family_id,
        user_id=x_user_id,
        agent_id=body.assistant_id,
        last_model=body.metadata.get("model_name", None),
        source=body.metadata.get("source"),
    )

    config = {"configurable": {"thread_id": thread_id, "checkpoint_ns": ""}}
    ckpt_metadata = {
        "step": -1,
        "source": "input",
        "writes": None,
        "parents": {},
        **body.metadata,
        "created_at": now,
        "family_id": x_family_id,
    }
    await checkpointer.aput(config, empty_checkpoint(), ckpt_metadata, {})

    return ThreadResponse(
        thread_id=thread_id,
        status="idle",
        created_at=now,
        updated_at=now,
        metadata=body.metadata,
    )


@router.post("/search", response_model=list[ThreadResponse])
async def search_threads(
    body: ThreadSearchRequest,
    x_family_id: str = Header(..., alias="X-Family-Id"),
    verified: VerifiedFamily = Depends(verify_family_token),
) -> list[ThreadResponse]:
    repo = AiSessionRepository(x_family_id)
    sessions, total = await repo.list_sessions(
        x_family_id,
        limit=body.limit,
        offset=body.offset,
        sort_by=body.sortBy or "updated_at",
        sort_order=body.sortOrder or "desc",
    )

    return [
        ThreadResponse(
            thread_id=str(r.get("session_id", "")),
            status=r.get("status", "idle"),
            created_at=coerce_iso(r.get("created_at", "")),
            updated_at=coerce_iso(r.get("updated_at", "")),
            metadata={
                "title": r.get("title", ""),
                "original_title": r.get("original_title"),
                "is_pinned": r.get("is_pinned", False),
                # U3: branch lineage for the history page. is_branch is derived
                # from source=="branch" (snake_case metadata key, aligned with
                # is_pinned); parent_thread_id comes from the session row
                # (U2 column). The checkpoint-internal numina_branch marker is
                # not mixed in here.
                "is_branch": r.get("source") == "branch",
                "parent_thread_id": r.get("parent_thread_id"),
            },
            values={"title": r.get("title", "")} if r.get("title") else {},
            interrupts={},
        )
        for r in sessions
    ]


@router.patch("/{thread_id}", response_model=ThreadResponse)
async def patch_thread(
    thread_id: str,
    body: ThreadPatchRequest,
    x_family_id: str = Header(..., alias="X-Family-Id"),
    verified: VerifiedFamily = Depends(verify_family_token),
) -> ThreadResponse:
    repo = AiSessionRepository(x_family_id)
    # Handle metadata-based title updates (legacy path)
    if "title" in body.metadata:
        await repo.update_summary(
            session_id=thread_id,
            family_id=x_family_id,
            summary=None,
            title=body.metadata["title"],
        )
    # Handle top-level title/is_pinned updates
    if body.title is not None or body.is_pinned is not None:
        await repo.update_session(
            session_id=thread_id,
            title=body.title,
            is_pinned=body.is_pinned,
        )
    return await get_thread(thread_id, x_family_id)


@router.get("/{thread_id}", response_model=ThreadResponse)
async def get_thread(
    thread_id: str,
    x_family_id: str = Header(..., alias="X-Family-Id"),
    verified: VerifiedFamily = Depends(verify_family_token),
) -> ThreadResponse:
    repo = AiSessionRepository(x_family_id)
    checkpointer = get_checkpointer()

    record = await repo.get_session(thread_id)
    config = {"configurable": {"thread_id": thread_id, "checkpoint_ns": ""}}
    checkpoint_tuple = await checkpointer.aget_tuple(config)

    if record is None and checkpoint_tuple is None:
        raise HTTPException(status_code=404, detail=f"Thread {thread_id} not found")

    # Defense-in-depth family ownership check on the record path. The backend
    # BackendClient filters by X-Family-Id, but the invariant should be enforced
    # locally too: U4's parent-link navigation pushes attacker-influenced
    # parent_thread_id values into this endpoint, and any future record source
    # that bypasses the backend filter must not leak cross-family state. Mirrors
    # the checkpoint-fallback check below and branch_thread's source check.
    if record is not None:
        record_family_id = record.get("family_id")
        if not record_family_id or str(record_family_id) != str(verified.family_id):
            raise HTTPException(status_code=404, detail=f"Thread {thread_id} not found")

    if record is None and checkpoint_tuple is not None:
        ckpt_meta = getattr(checkpoint_tuple, "metadata", {}) or {}
        # Family ownership check for checkpoint fallback
        ckpt_family_id = ckpt_meta.get("family_id")
        if not ckpt_family_id or str(ckpt_family_id) != str(verified.family_id):
            raise HTTPException(status_code=404, detail=f"Thread {thread_id} not found")
        record = {
            "session_id": thread_id,
            "status": "idle",
            "created_at": coerce_iso(ckpt_meta.get("created_at", "")),
            "updated_at": coerce_iso(
                ckpt_meta.get("updated_at", ckpt_meta.get("created_at", ""))
            ),
            "metadata": {},
        }

    assert record is not None  # guaranteed by the 404 check above

    status = (
        _derive_thread_status(checkpoint_tuple)
        if checkpoint_tuple is not None
        else record.get("status", "idle")
    )
    checkpoint = (
        getattr(checkpoint_tuple, "checkpoint", {}) or {}
        if checkpoint_tuple is not None
        else {}
    )
    channel_values = checkpoint.get("channel_values", {})

    # Merge title and is_pinned into metadata for frontend ThreadSession compatibility
    meta = dict(record.get("metadata", {}) or {})
    if record.get("title"):
        meta["title"] = record["title"]
    if record.get("original_title"):
        meta["original_title"] = record["original_title"]
    if "is_pinned" in record:
        meta["is_pinned"] = record["is_pinned"]
    # U3: branch lineage (aligned with search_threads metadata shape).
    meta["is_branch"] = record.get("source") == "branch"
    meta["parent_thread_id"] = record.get("parent_thread_id")

    return ThreadResponse(
        thread_id=thread_id,
        status=status,
        created_at=coerce_iso(record.get("created_at", "")),
        updated_at=coerce_iso(record.get("updated_at", "")),
        metadata=meta,
        values=serialize_channel_values_for_api(channel_values),
    )


@router.get("/{thread_id}/state", response_model=ThreadStateResponse)
async def get_thread_state(
    thread_id: str,
    x_family_id: str = Header(..., alias="X-Family-Id"),
    verified: VerifiedFamily = Depends(verify_family_token),
) -> ThreadStateResponse:
    repo = AiSessionRepository(x_family_id)
    checkpointer = get_checkpointer()
    config = {"configurable": {"thread_id": thread_id, "checkpoint_ns": ""}}
    checkpoint_tuple = await checkpointer.aget_tuple(config)

    # Dual-source resolution (mirrors get_thread): when the checkpointer has no
    # tuple, fall back to the ai_chat_sessions row before 404-ing. Orphan
    # threads (e.g. pre-a97eb08c UUID threads with a session row but no
    # checkpoint) would otherwise hard-404 loadHistory even though the thread
    # exists in the session index. With no checkpoint there are no messages to
    # load, so return an empty state instead.
    if checkpoint_tuple is None:
        record = await repo.get_session(thread_id)
        if record is None:
            raise HTTPException(status_code=404, detail=f"Thread {thread_id} not found")
        meta = {
            "title": record.get("title") or "",
            "is_pinned": record.get("is_pinned", False),
            "created_at": coerce_iso(record.get("created_at", "")),
            "updated_at": coerce_iso(record.get("updated_at", "")),
        }
        return ThreadStateResponse(
            values={},
            next=[],
            metadata=meta,
            checkpoint={"id": None, "ts": meta["created_at"]},
            checkpoint_id=None,
            parent_checkpoint_id=None,
            created_at=meta["created_at"],
            tasks=[],
        )

    checkpoint = getattr(checkpoint_tuple, "checkpoint", {}) or {}
    metadata = getattr(checkpoint_tuple, "metadata", {}) or {}

    # Family ownership check — prefer checkpoint metadata, fall back to session record
    ckpt_family_id = metadata.get("family_id")
    if not ckpt_family_id:
        # Checkpoint metadata lacks family_id (e.g. older checkpoints written before
        # family_id was added to metadata). Fall back to the session row.
        record = await repo.get_session(thread_id)
        if record is None:
            raise HTTPException(status_code=404, detail=f"Thread {thread_id} not found")
        record_family_id = record.get("family_id")
        if not record_family_id or str(record_family_id) != str(verified.family_id):
            raise HTTPException(status_code=404, detail=f"Thread {thread_id} not found")
    elif str(ckpt_family_id) != str(verified.family_id):
        raise HTTPException(status_code=404, detail=f"Thread {thread_id} not found")
    checkpoint_id = (
        getattr(checkpoint_tuple, "config", {})
        .get("configurable", {})
        .get("checkpoint_id")
    )
    channel_values = checkpoint.get("channel_values", {})

    parent_config = getattr(checkpoint_tuple, "parent_config", None)
    parent_checkpoint_id = (
        parent_config.get("configurable", {}).get("checkpoint_id")
        if parent_config
        else None
    )

    tasks_raw = getattr(checkpoint_tuple, "tasks", []) or []
    next_tasks = [t.name for t in tasks_raw if hasattr(t, "name")]
    tasks = [
        {"id": getattr(t, "id", ""), "name": getattr(t, "name", "")} for t in tasks_raw
    ]

    return ThreadStateResponse(
        values=serialize_channel_values_for_api(channel_values),
        next=next_tasks,
        metadata=metadata,
        checkpoint={
            "id": checkpoint_id,
            "ts": coerce_iso(metadata.get("created_at", "")),
        },
        checkpoint_id=checkpoint_id,
        parent_checkpoint_id=parent_checkpoint_id,
        created_at=coerce_iso(metadata.get("created_at", "")),
        tasks=tasks,
    )


@router.post("/{thread_id}/state", response_model=ThreadStateResponse)
async def update_thread_state(
    thread_id: str,
    body: ThreadStateUpdateRequest,
    x_family_id: str = Header(..., alias="X-Family-Id"),
    verified: VerifiedFamily = Depends(verify_family_token),
) -> ThreadStateResponse:
    checkpointer = get_checkpointer()
    repo = AiSessionRepository(x_family_id)

    read_config = {"configurable": {"thread_id": thread_id, "checkpoint_ns": ""}}
    if body.checkpoint_id:
        read_config["configurable"]["checkpoint_id"] = body.checkpoint_id

    checkpoint_tuple = await checkpointer.aget_tuple(read_config)
    if checkpoint_tuple is None:
        raise HTTPException(status_code=404, detail=f"Thread {thread_id} not found")

    checkpoint = dict(getattr(checkpoint_tuple, "checkpoint", {}) or {})
    metadata = dict(getattr(checkpoint_tuple, "metadata", {}) or {})

    # Family ownership check — prefer checkpoint metadata, fall back to session record
    ckpt_family_id = metadata.get("family_id")
    if not ckpt_family_id:
        record = await repo.get_session(thread_id)
        if record is None:
            raise HTTPException(status_code=404, detail=f"Thread {thread_id} not found")
        record_family_id = record.get("family_id")
        if not record_family_id or str(record_family_id) != str(verified.family_id):
            raise HTTPException(status_code=404, detail=f"Thread {thread_id} not found")
    elif str(ckpt_family_id) != str(verified.family_id):
        raise HTTPException(status_code=404, detail=f"Thread {thread_id} not found")

    channel_values = dict(checkpoint.get("channel_values", {}))

    if body.values:
        channel_values.update(body.values)

    checkpoint["channel_values"] = channel_values
    metadata["updated_at"] = now_iso()

    if body.as_node:
        metadata["source"] = "update"
        metadata["step"] = metadata.get("step", 0) + 1
        metadata["writes"] = {body.as_node: body.values}

    checkpoint["id"] = str(uuid6())
    write_config = {"configurable": {"thread_id": thread_id, "checkpoint_ns": ""}}
    new_config = await checkpointer.aput(write_config, checkpoint, metadata, {})

    new_checkpoint_id = (
        new_config.get("configurable", {}).get("checkpoint_id")
        if isinstance(new_config, dict)
        else None
    )

    if body.values and "title" in body.values:
        new_title = body.values["title"]
        if new_title:
            await repo.update_summary(
                session_id=thread_id,
                family_id=x_family_id,
                summary=None,
                title=new_title,
            )

    return ThreadStateResponse(
        values=serialize_channel_values_for_api(channel_values),
        next=[],
        metadata=metadata,
        checkpoint_id=new_checkpoint_id,
        created_at=coerce_iso(metadata.get("created_at", "")),
    )


# ---------------------------------------------------------------------------
# Goal endpoints (DeerFlow threads.py:832-880)
# ---------------------------------------------------------------------------

# Adult family roles allowed to set/clear goals and compact conversation history.
# The backend ``require_adult`` (apps/backend/app/auth/deps.py) admits
# ``role in ('owner', 'member')`` — ``User.role`` only ever stores
# 'owner' / 'member' / 'child' (packages/db/models/user.py), the literal
# 'adult' is never issued by jwt_utils/auth. Using {'owner','adult'} here
# silently rejected every role='member' adult with 403; 'member' is the
# correct peer of 'owner'.
_OWNER_ADULT_ROLES = frozenset({"owner", "member"})


async def _verify_goal_thread_ownership(
    checkpointer,
    repo: AiSessionRepository,
    thread_id: str,
    verified: VerifiedFamily,
) -> None:
    """Second-layer family-ownership check on the checkpoint (KTD-8).

    ``verify_family_token`` only matches the JWT ``fid`` to the ``X-Family-Id``
    header — it does NOT prove the thread belongs to that family. Read the
    checkpoint metadata.family_id (falling back to the session row) and raise
    404 on mismatch, mirroring ``get_thread_state`` / ``update_thread_state``.
    """
    config = {"configurable": {"thread_id": thread_id, "checkpoint_ns": ""}}
    checkpoint_tuple = await checkpointer.aget_tuple(config)
    if checkpoint_tuple is None:
        record = await repo.get_session(thread_id)
        if record is None:
            raise HTTPException(status_code=404, detail=f"Thread {thread_id} not found")
        record_family_id = record.get("family_id")
        if not record_family_id or str(record_family_id) != str(verified.family_id):
            raise HTTPException(status_code=404, detail=f"Thread {thread_id} not found")
        return
    metadata = getattr(checkpoint_tuple, "metadata", {}) or {}
    ckpt_family_id = metadata.get("family_id")
    if not ckpt_family_id:
        record = await repo.get_session(thread_id)
        if record is None:
            raise HTTPException(status_code=404, detail=f"Thread {thread_id} not found")
        record_family_id = record.get("family_id")
        if not record_family_id or str(record_family_id) != str(verified.family_id):
            raise HTTPException(status_code=404, detail=f"Thread {thread_id} not found")
    elif str(ckpt_family_id) != str(verified.family_id):
        raise HTTPException(status_code=404, detail=f"Thread {thread_id} not found")


@router.get("/{thread_id}/goal", response_model=ThreadGoalResponse)
async def get_thread_goal(
    thread_id: str,
    x_family_id: str = Header(..., alias="X-Family-Id"),
    verified: VerifiedFamily = Depends(verify_family_token),
) -> ThreadGoalResponse:
    """Return the active Claude-style goal for a thread, if any."""
    checkpointer = get_checkpointer()
    repo = AiSessionRepository(x_family_id)
    await _verify_goal_thread_ownership(checkpointer, repo, thread_id, verified)
    try:
        goal = await read_thread_goal(checkpointer, thread_id)
    except Exception:
        logger.exception("Failed to read goal for thread %s", thread_id)
        raise HTTPException(status_code=500, detail="读取线程目标失败") from None
    return ThreadGoalResponse(goal=goal)


@router.put("/{thread_id}/goal", response_model=ThreadGoalResponse)
async def set_thread_goal(
    thread_id: str,
    body: ThreadGoalRequest,
    x_family_id: str = Header(..., alias="X-Family-Id"),
    verified: VerifiedFamily = Depends(verify_family_token),
) -> ThreadGoalResponse:
    """Set or replace the active goal for a thread (owner/adult only, KTD-8)."""
    if verified.role not in _OWNER_ADULT_ROLES:
        raise HTTPException(status_code=403, detail="仅家长可设置目标")
    checkpointer = get_checkpointer()
    repo = AiSessionRepository(x_family_id)
    await _verify_goal_thread_ownership(checkpointer, repo, thread_id, verified)
    goal = build_goal_state(body.objective, max_continuations=body.max_continuations)
    try:
        async with goal_thread_lock(thread_id):
            await write_thread_goal(
                checkpointer, thread_id, goal, as_node="goal", create_if_missing=True
            )
    except GoalWriteConflict:
        raise HTTPException(
            status_code=409, detail="目标已被并发修改，请重试"
        ) from None
    except Exception:
        logger.exception("Failed to set goal for thread %s", thread_id)
        raise HTTPException(status_code=500, detail="设置线程目标失败") from None
    return ThreadGoalResponse(goal=goal)


@router.delete("/{thread_id}/goal", response_model=ThreadGoalResponse)
async def clear_thread_goal(
    thread_id: str,
    x_family_id: str = Header(..., alias="X-Family-Id"),
    verified: VerifiedFamily = Depends(verify_family_token),
) -> ThreadGoalResponse:
    """Clear the active goal for a thread (owner/adult only, KTD-8)."""
    if verified.role not in _OWNER_ADULT_ROLES:
        raise HTTPException(status_code=403, detail="仅家长可清除目标")
    checkpointer = get_checkpointer()
    repo = AiSessionRepository(x_family_id)
    await _verify_goal_thread_ownership(checkpointer, repo, thread_id, verified)
    try:
        async with goal_thread_lock(thread_id):
            await write_thread_goal(checkpointer, thread_id, None, as_node="goal")
    except GoalWriteConflict:
        raise HTTPException(
            status_code=409, detail="目标已被并发修改，请重试"
        ) from None
    except Exception:
        logger.exception("Failed to clear goal for thread %s", thread_id)
        raise HTTPException(status_code=500, detail="清除线程目标失败") from None
    return ThreadGoalResponse(goal=None)


@router.post("/{thread_id}/history", response_model=list[HistoryEntry])
async def get_thread_history(
    thread_id: str,
    body: ThreadHistoryRequest,
    x_family_id: str = Header(..., alias="X-Family-Id"),
    verified: VerifiedFamily = Depends(verify_family_token),
) -> list[HistoryEntry]:
    checkpointer = get_checkpointer()
    config = {"configurable": {"thread_id": thread_id}}
    if body.before:
        config["configurable"]["checkpoint_id"] = body.before

    entries = []
    is_latest_checkpoint = True
    async for checkpoint_tuple in checkpointer.alist(config, limit=body.limit):
        ckpt_config = getattr(checkpoint_tuple, "config", {})
        parent_config = getattr(checkpoint_tuple, "parent_config", None)
        metadata = getattr(checkpoint_tuple, "metadata", {}) or {}

        # Family ownership check
        ckpt_family_id = metadata.get("family_id")
        if not ckpt_family_id or str(ckpt_family_id) != str(verified.family_id):
            raise HTTPException(status_code=404, detail=f"Thread {thread_id} not found")

        checkpoint = getattr(checkpoint_tuple, "checkpoint", {}) or {}

        checkpoint_id = ckpt_config.get("configurable", {}).get("checkpoint_id", "")
        parent_id = (
            parent_config.get("configurable", {}).get("checkpoint_id")
            if parent_config
            else None
        )
        channel_values = checkpoint.get("channel_values", {})

        values = {}
        if title := channel_values.get("title"):
            values["title"] = title
        if thread_data := channel_values.get("thread_data"):
            values["thread_data"] = thread_data

        if is_latest_checkpoint and "messages" in channel_values:
            values["messages"] = serialize_channel_values_for_api(
                {"messages": channel_values["messages"]}
            ).get("messages", [])
        is_latest_checkpoint = False

        tasks_raw = getattr(checkpoint_tuple, "tasks", []) or []
        next_tasks = [t.name for t in tasks_raw if hasattr(t, "name")]

        user_meta = {
            k: v
            for k, v in metadata.items()
            if k
            not in ("created_at", "updated_at", "step", "source", "writes", "parents")
        }
        if "step" in metadata:
            user_meta["step"] = metadata["step"]

        entries.append(
            HistoryEntry(
                checkpoint_id=checkpoint_id,
                parent_checkpoint_id=parent_id,
                metadata=user_meta,
                values=values,
                created_at=coerce_iso(metadata.get("created_at", "")),
                next=next_tasks,
            )
        )

    return entries


@router.get("/{thread_id}/token-usage")
async def get_thread_token_usage(
    thread_id: str,
    x_family_id: str = Header(..., alias="X-Family-Id"),
    verified: VerifiedFamily = Depends(verify_family_token),
) -> dict[str, int]:
    """Calculate and return the total token usage for a thread."""
    checkpointer = get_checkpointer()
    config = {"configurable": {"thread_id": thread_id, "checkpoint_ns": ""}}
    checkpoint_tuple = await checkpointer.aget_tuple(config)

    if checkpoint_tuple is None:
        return {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}

    metadata = getattr(checkpoint_tuple, "metadata", {}) or {}

    # Family ownership check — prefer checkpoint metadata, fall back to session record
    ckpt_family_id = metadata.get("family_id")
    if not ckpt_family_id:
        # Checkpoint metadata lacks family_id (e.g. older checkpoints written before
        # family_id was added to metadata). Fall back to the session row.
        repo = AiSessionRepository(x_family_id)
        record = await repo.get_session(thread_id)
        if record is None:
            raise HTTPException(status_code=404, detail=f"Thread {thread_id} not found")
        record_family_id = record.get("family_id")
        if not record_family_id or str(record_family_id) != str(verified.family_id):
            raise HTTPException(status_code=404, detail=f"Thread {thread_id} not found")
    elif str(ckpt_family_id) != str(verified.family_id):
        raise HTTPException(status_code=404, detail=f"Thread {thread_id} not found")

    checkpoint = getattr(checkpoint_tuple, "checkpoint", {}) or {}
    messages = checkpoint.get("channel_values", {}).get("messages", [])

    prompt_tokens = 0
    completion_tokens = 0

    for msg in messages:
        if hasattr(msg, "usage_metadata") and msg.usage_metadata:
            prompt_tokens += msg.usage_metadata.get("input_tokens", 0)
            completion_tokens += msg.usage_metadata.get("output_tokens", 0)

    return {
        "prompt_tokens": prompt_tokens,
        "completion_tokens": completion_tokens,
        "total_tokens": prompt_tokens + completion_tokens,
    }


# ---------------------------------------------------------------------------
# Branch endpoint (DeerFlow threads.py:579-665)
# ---------------------------------------------------------------------------


@router.post("/{thread_id}/branches", response_model=ThreadBranchResponse)
async def branch_thread(
    thread_id: str,
    body: ThreadBranchRequest,
    x_family_id: str = Header(..., alias="X-Family-Id"),
    x_user_id: str = Header(None, alias="X-User-Id"),
    verified: VerifiedFamily = Depends(verify_family_token),
) -> ThreadBranchResponse:
    """Create a new branch from a completed assistant turn.

    DeerFlow 参考：threads.py:579-665
    Finds the checkpoint containing the target message, deep-copies it to a
    new thread_id, and creates a session row in the backend DB.

    # [Integrated with Numina Multi-Tenant] — family_id validation + propagation
    """
    import copy

    checkpointer = get_checkpointer()
    repo = AiSessionRepository(x_family_id)

    # 1. Validate source thread exists and belongs to this family
    source_record = await repo.get_session(thread_id)
    if source_record is None:
        raise HTTPException(status_code=404, detail=f"Thread {thread_id} not found")

    source_family_id = source_record.get("family_id")
    if not source_family_id or str(source_family_id) != str(verified.family_id):
        raise HTTPException(status_code=404, detail=f"Thread {thread_id} not found")

    # 2. Find checkpoint containing the target message (single alist scan).
    #    The scan also resolves whether the target is the latest turn, so the
    #    clone decision and the source checkpoint come from one pass with no
    #    TOCTOU window between two scans.
    target_message_ids = {body.message_id, *body.message_ids}
    branch_checkpoint = await _find_branch_checkpoint(
        checkpointer, thread_id, target_message_ids
    )

    if branch_checkpoint is None:
        raise HTTPException(
            status_code=409,
            detail="This turn can no longer be branched from.",
        )
    checkpoint_tuple, branch_from_latest_turn = branch_checkpoint

    parent_checkpoint_id = _checkpoint_id(checkpoint_tuple)
    if not parent_checkpoint_id:
        raise HTTPException(
            status_code=409,
            detail="This turn can no longer be branched from.",
        )

    # 3. Generate new thread ID and copy checkpoint (DeerFlow threads.py:609-644)
    new_thread_id = str(uuid.uuid4())
    now = now_iso()

    branch_metadata = {
        # numina_branch is the checkpoint-level branch marker (DeerFlow-aligned).
        # Frontend lineage (is_branch / parent_thread_id) is served from the
        # session row (source=="branch" + the parent_thread_id column), NOT
        # from these keys — see search_threads/get_thread. The per-branch
        # parent_thread_id/checkpoint_id/message_id/created_at are recoverable
        # from the session row + parent_checkpoint_id response field, so they
        # are not duplicated into checkpoint metadata (previously written here
        # but never read in production).
        _BRANCH_METADATA_KEY: True,
    }

    checkpoint = copy.deepcopy(getattr(checkpoint_tuple, "checkpoint", {}) or {})
    metadata = copy.deepcopy(getattr(checkpoint_tuple, "metadata", {}) or {})
    checkpoint["id"] = str(uuid6())
    metadata.update(
        {
            "source": "branch",
            "updated_at": now,
            "created_at": now,
            "family_id": x_family_id,  # preserve tenant isolation
            **branch_metadata,
        }
    )

    # Derive title (DeerFlow threads.py:619-622)
    source_title = source_record.get("title") or ""
    # The session row carries lineage via the ``source`` field (== "branch"),
    # not via checkpoint metadata — the session dict from ``repo.get_session``
    # has no top-level ``metadata`` key. Using ``source`` (already the signal
    # at lines 488/565/927) avoids double-prefixing a branch-of-branch title.
    source_is_branch = source_record.get("source") == "branch"
    display_title = body.title or _default_branch_display_name(
        source_title, source_is_branch=source_is_branch
    )
    if display_title:
        metadata["title"] = display_title
        if source_title:
            metadata["original_title"] = source_title

    # 4. Write checkpoint to new thread (DeerFlow threads.py:638-644)
    write_config = {"configurable": {"thread_id": new_thread_id, "checkpoint_ns": ""}}
    new_versions = dict(checkpoint.get("channel_versions", {}) or {})
    try:
        await checkpointer.aput(write_config, checkpoint, metadata, new_versions)
    except Exception:
        logger.exception(
            "Failed to write branch checkpoint for thread %s", new_thread_id
        )
        raise HTTPException(status_code=500, detail="Failed to create branch") from None

    # 5. Create session row in backend DB (DeerFlow threads.py:646-656)
    try:
        await repo.upsert(
            session_id=new_thread_id,
            family_id=x_family_id,
            user_id=x_user_id,
            agent_id=source_record.get("agent_id"),
            last_model=source_record.get("last_model"),
            source="branch",
            parent_thread_id=thread_id,
        )
        if display_title:
            await repo.update_summary(
                session_id=new_thread_id,
                family_id=x_family_id,
                summary=None,
                title=display_title,
            )
    except Exception:
        logger.exception("Failed to write branch session for thread %s", new_thread_id)
        raise HTTPException(status_code=500, detail="Failed to create branch") from None

    # 5a. Clone sandbox artifacts (DeerFlow threads.py:667-671)
    # Workspace files are not checkpointed, so they only reflect the *current*
    # thread state. Cloning them onto a branch from an older turn would leak
    # files created after that turn (message history rolls back, workspace
    # would not). Restrict the best-effort clone to branches taken from the
    # latest turn so history and workspace stay consistent. The latest-turn
    # decision was resolved in the same scan as the source checkpoint above.
    if branch_from_latest_turn:
        workspace_clone_mode = await _copy_branch_user_data(
            x_family_id, thread_id, new_thread_id
        )
    else:
        workspace_clone_mode = "skipped_historical_turn"

    # 6. Log structured event for success metrics
    logger.info(
        "event=thread_branched, source_thread_id=%s, new_thread_id=%s, message_id=%s, family_id=%s, workspace_clone_mode=%s",
        thread_id,
        new_thread_id,
        body.message_id,
        x_family_id,
        workspace_clone_mode,
    )

    return ThreadBranchResponse(
        thread_id=new_thread_id,
        parent_thread_id=thread_id,
        parent_checkpoint_id=parent_checkpoint_id,
        branched_from_message_id=body.message_id,
        workspace_clone_mode=workspace_clone_mode,  # type: ignore[arg-type]  # str from _copy_branch_user_data; values match WorkspaceCloneMode Literal
    )


# ---------------------------------------------------------------------------
# Compact endpoint (U6 — D2 DeerFlow threads.py:896-926)
# ---------------------------------------------------------------------------


@router.post("/{thread_id}/compact", response_model=ThreadCompactResponse)
async def compact_thread_endpoint(
    thread_id: str,
    body: ThreadCompactRequest,
    request: Request,
    x_family_id: str = Header(..., alias="X-Family-Id"),
    verified: VerifiedFamily = Depends(verify_family_token),
) -> ThreadCompactResponse:
    """Manually summarize old thread context while preserving the visible tail.

    Compacts the thread via DeerFlow's canonical ``compact_thread_context``
    (KTD-5), which handles ``RemoveMessage(ALL)`` + preserved tail +
    ``channel_versions`` bump + ``summary_text``. Owner/adult only (KTD-8);
    409 if a run is in flight; 404 if the thread is missing or belongs to
    another family (ownership check, not the single-layer auth check).
    """
    if verified.role not in _OWNER_ADULT_ROLES:
        raise HTTPException(status_code=403, detail="仅家长可压缩对话历史")
    checkpointer = get_checkpointer()
    repo = AiSessionRepository(x_family_id)
    await _verify_goal_thread_ownership(checkpointer, repo, thread_id, verified)

    run_manager = get_run_manager(request)
    try:
        if await run_manager.has_inflight(thread_id):
            raise HTTPException(
                status_code=409, detail="对话正在运行，请在运行结束后再压缩"
            )
        result = await compact_thread(
            checkpointer,
            thread_id,
            user_id=verified.user_id,
            agent_name=body.agent_name,
        )
    except ContextCompactionDisabled:
        raise HTTPException(status_code=409, detail="上下文压缩已禁用") from None
    except ContextCompactionFailed:
        raise HTTPException(status_code=503, detail="压缩对话历史失败") from None
    except LookupError:
        raise HTTPException(
            status_code=404, detail=f"Thread {thread_id} not found"
        ) from None
    except HTTPException:
        raise
    except Exception:
        logger.exception("Failed to compact thread %s", thread_id)
        raise HTTPException(status_code=503, detail="压缩对话历史失败") from None
    return ThreadCompactResponse(**result_to_dict(result))
