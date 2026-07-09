"""Thread CRUD, state, and history endpoints for Numina Agent.

Combines the LangGraph checkpointer state with the Numina Backend
session storage (via AiSessionRepository) for fast metadata querying.
"""

from __future__ import annotations

import contextlib
import logging
import uuid
from typing import Any

from deerflow.utils.time import coerce_iso, now_iso
from fastapi import APIRouter, Depends, Header, HTTPException
from langgraph.checkpoint.base import empty_checkpoint, uuid6
from pydantic import BaseModel, Field, field_validator

from apps.agent.app.auth.jwt_verify import VerifiedFamily, verify_family_token
from apps.agent.services.deerflow_adapter.family_adapter_cache import (
    _get_shared_checkpointer,
)
from apps.agent.services.session_store import AiSessionRepository


def serialize_channel_values_for_api(values: dict[str, Any]) -> dict[str, Any]:
    """Convert channel values (including LangChain messages) to dicts for API response."""
    from langchain_core.messages import BaseMessage
    result = {}
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
_SERVER_RESERVED_METADATA_KEYS: frozenset[str] = frozenset({"owner_id", "user_id", "family_id"})

def _strip_reserved_metadata(metadata: dict[str, Any] | None) -> dict[str, Any]:
    if not metadata:
        return metadata or {}
    return {k: v for k, v in metadata.items() if k not in _SERVER_RESERVED_METADATA_KEYS}

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
    metadata: dict[str, Any] = Field(default_factory=dict, description="Thread metadata")
    values: dict[str, Any] = Field(default_factory=dict, description="Current state channel values")
    interrupts: dict[str, Any] = Field(default_factory=dict, description="Pending interrupts")

class ThreadCreateRequest(BaseModel):
    thread_id: str | None = Field(default=None, description="Optional thread ID (auto-generated if omitted)")
    assistant_id: str | None = Field(default=None, description="Associate thread with an assistant")
    metadata: dict[str, Any] = Field(default_factory=dict, description="Initial metadata")

    _strip_reserved = field_validator("metadata")(classmethod(lambda cls, v: _strip_reserved_metadata(v)))

class ThreadSearchRequest(BaseModel):
    metadata: dict[str, Any] = Field(default_factory=dict, description="Metadata filter (exact match)")
    limit: int = Field(default=100, ge=1, le=1000, description="Maximum results")
    offset: int = Field(default=0, ge=0, description="Pagination offset")
    sortBy: str | None = Field(default="updated_at", description="Sort column")
    sortOrder: str | None = Field(default="desc", description="Sort order (asc/desc)")

class ThreadStateResponse(BaseModel):
    values: dict[str, Any] = Field(default_factory=dict, description="Current channel values")
    next: list[str] = Field(default_factory=list, description="Next tasks to execute")
    metadata: dict[str, Any] = Field(default_factory=dict, description="Checkpoint metadata")
    checkpoint: dict[str, Any] = Field(default_factory=dict, description="Checkpoint info")
    checkpoint_id: str | None = Field(default=None, description="Current checkpoint ID")
    parent_checkpoint_id: str | None = Field(default=None, description="Parent checkpoint ID")
    created_at: str | None = Field(default=None, description="Checkpoint timestamp")
    tasks: list[dict[str, Any]] = Field(default_factory=list, description="Interrupted task details")

class ThreadPatchRequest(BaseModel):
    metadata: dict[str, Any] = Field(default_factory=dict, description="Metadata to merge")
    title: str | None = Field(default=None, description="Session title")
    is_pinned: bool | None = Field(default=None, description="Pin/unpin session")
    _strip_reserved = field_validator("metadata")(classmethod(lambda cls, v: _strip_reserved_metadata(v)))

class ThreadStateUpdateRequest(BaseModel):
    values: dict[str, Any] | None = Field(default=None, description="Channel values to merge")
    checkpoint_id: str | None = Field(default=None, description="Checkpoint to branch from")
    checkpoint: dict[str, Any] | None = Field(default=None, description="Full checkpoint object")
    as_node: str | None = Field(default=None, description="Node identity for the update")

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
        raise HTTPException(status_code=503, detail="Failed to delete thread from database")
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
        last_model=body.metadata.get("model_name", None)
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
            thread_id=r.get("session_id", ""),
            status=r.get("status", "idle"),
            created_at=coerce_iso(r.get("created_at", "")),
            updated_at=coerce_iso(r.get("updated_at", "")),
            metadata={
                "title": r.get("title", ""),
                "original_title": r.get("original_title"),
                "is_pinned": r.get("is_pinned", False),
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
            title=body.metadata["title"]
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
            "updated_at": coerce_iso(ckpt_meta.get("updated_at", ckpt_meta.get("created_at", ""))),
            "metadata": {},
        }

    status = _derive_thread_status(checkpoint_tuple) if checkpoint_tuple is not None else record.get("status", "idle")
    checkpoint = getattr(checkpoint_tuple, "checkpoint", {}) or {} if checkpoint_tuple is not None else {}
    channel_values = checkpoint.get("channel_values", {})

    # Merge title and is_pinned into metadata for frontend ThreadSession compatibility
    meta = dict(record.get("metadata", {}) or {})
    if record.get("title"):
        meta["title"] = record["title"]
    if record.get("original_title"):
        meta["original_title"] = record["original_title"]
    if "is_pinned" in record:
        meta["is_pinned"] = record["is_pinned"]

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

    # Family ownership check
    ckpt_family_id = metadata.get("family_id")
    if not ckpt_family_id or str(ckpt_family_id) != str(verified.family_id):
        raise HTTPException(status_code=404, detail=f"Thread {thread_id} not found")
    checkpoint_id = getattr(checkpoint_tuple, "config", {}).get("configurable", {}).get("checkpoint_id")
    channel_values = checkpoint.get("channel_values", {})

    parent_config = getattr(checkpoint_tuple, "parent_config", None)
    parent_checkpoint_id = parent_config.get("configurable", {}).get("checkpoint_id") if parent_config else None

    tasks_raw = getattr(checkpoint_tuple, "tasks", []) or []
    next_tasks = [t.name for t in tasks_raw if hasattr(t, "name")]
    tasks = [{"id": getattr(t, "id", ""), "name": getattr(t, "name", "")} for t in tasks_raw]

    return ThreadStateResponse(
        values=serialize_channel_values_for_api(channel_values),
        next=next_tasks,
        metadata=metadata,
        checkpoint={"id": checkpoint_id, "ts": coerce_iso(metadata.get("created_at", ""))},
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

    # Family ownership check
    ckpt_family_id = metadata.get("family_id")
    if not ckpt_family_id or str(ckpt_family_id) != str(verified.family_id):
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

    new_checkpoint_id = new_config.get("configurable", {}).get("checkpoint_id") if isinstance(new_config, dict) else None

    if body.values and "title" in body.values:
        new_title = body.values["title"]
        if new_title:
            await repo.update_summary(session_id=thread_id, family_id=x_family_id, summary=None, title=new_title)

    return ThreadStateResponse(
        values=serialize_channel_values_for_api(channel_values),
        next=[],
        metadata=metadata,
        checkpoint_id=new_checkpoint_id,
        created_at=coerce_iso(metadata.get("created_at", "")),
    )

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
        parent_id = parent_config.get("configurable", {}).get("checkpoint_id") if parent_config else None
        channel_values = checkpoint.get("channel_values", {})

        values = {}
        if title := channel_values.get("title"):
            values["title"] = title
        if thread_data := channel_values.get("thread_data"):
            values["thread_data"] = thread_data

        if is_latest_checkpoint and "messages" in channel_values:
            values["messages"] = serialize_channel_values_for_api({"messages": channel_values["messages"]}).get("messages", [])
        is_latest_checkpoint = False

        tasks_raw = getattr(checkpoint_tuple, "tasks", []) or []
        next_tasks = [t.name for t in tasks_raw if hasattr(t, "name")]

        user_meta = {k: v for k, v in metadata.items() if k not in ("created_at", "updated_at", "step", "source", "writes", "parents")}
        if "step" in metadata:
            user_meta["step"] = metadata["step"]

        entries.append(HistoryEntry(
            checkpoint_id=checkpoint_id,
            parent_checkpoint_id=parent_id,
            metadata=user_meta,
            values=values,
            created_at=coerce_iso(metadata.get("created_at", "")),
            next=next_tasks,
        ))

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

    # Family ownership check
    ckpt_family_id = metadata.get("family_id")
    if not ckpt_family_id or str(ckpt_family_id) != str(verified.family_id):
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
        "total_tokens": prompt_tokens + completion_tokens
    }
