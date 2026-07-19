"""金融文档持仓解析端点（由 backend 调用）。

U8 (Resolved-10): import_parse 从 ``orchestrator.dispatch`` 重构为第 3 个
stream_run agent（``app="import-parse"``）。本端点是 backend ``/import/parse-pdf``
的同步 JSON 入口：在请求内运行 ``_run_import_parse_agent``（捕获 bridge 事件），
从 ``import-parse.result`` custom 事件提取解析结果，返回 ``{source, report_date,
items}`` 同步 JSON（前端契约不变）。

设计权衡（plan U8 step 7 "实现期定"）：backend 需同步 JSON，而 import-parse 能力
是 stream_run agent。本端点作 backend adapter —— 在请求内内联运行 agent run +
聚合结果为同步 JSON，避免 frontend 改 SSE 消费。MCP 批量写入工具 + 多模态 vision
为 U8 follow-up（plan 前提链 dependent #2）。
"""

import asyncio
import logging
import uuid
from types import SimpleNamespace
from typing import Any

from fastapi import APIRouter, Header, HTTPException
from pydantic import BaseModel

from apps.agent.app.config import settings
from apps.agent.services.runtime.worker import _run_import_parse_agent

router = APIRouter(prefix="/import", tags=["import"])
logger = logging.getLogger(__name__)

# 解析结果为空时的兜底返回（与 import_parse_service 旧契约一致）。
_EMPTY_RESULT: dict[str, Any] = {"source": "", "report_date": None, "items": []}


class ImportParseRequest(BaseModel):
    text: str


class _CapturingBridge:
    """Minimal StreamBridge stub that captures published events for sync harvest.

    Mirrors the shape ``_run_import_parse_agent`` drives: ``publish`` accumulates
    events, ``publish_end`` / ``cleanup`` are no-ops. The harvest step reads
    the captured ``import-parse.result`` custom event.
    """

    def __init__(self) -> None:
        self.published: list[tuple[str, Any]] = []

    async def publish(self, run_id: str, event: str, data: Any) -> None:
        self.published.append((event, data))

    async def publish_end(self, run_id: str) -> None:
        self.published.append(("__end_sentinel__", None))

    async def cleanup(self, run_id: str, delay: float = 0) -> None:
        pass


@router.post("/parse")
async def parse_import(
    body: ImportParseRequest,
    x_family_id: str = Header(..., alias="X-Family-Id"),
    x_agent_token: str = Header(..., alias="X-Agent-Token"),
    x_user_id: str = Header(None, alias="X-User-Id"),
):
    """解析金融文档文本，提取持仓快照（由 backend 调用）。

    返回同步 JSON ``{source, report_date, items}``（前端契约不变）。内部运行
    ``app="import-parse"`` stream_run agent；agent 解析失败或超时返回空结果
    （items=[]），不抛异常 —— 与旧 ``import_parse_service`` 兜底契约一致。
    """
    if x_agent_token != settings.AGENT_INTERNAL_TOKEN:
        raise HTTPException(status_code=401, detail="invalid token")

    from deerflow.runtime import RunStatus

    run_id = f"importparse-{uuid.uuid4().hex[:12]}"
    thread_id = f"importparse-thread-{uuid.uuid4().hex[:12]}"
    family_id = x_family_id
    user_id = x_user_id

    # Build a minimal RunRecord duck-typed for _run_import_parse_agent (mirrors
    # what RunManager.create_or_reject produces; only run_id/status/abort_event
    # are read by the worker).
    record = SimpleNamespace(
        run_id=run_id,
        status=RunStatus.pending,
        abort_event=asyncio.Event(),
    )

    # _run_import_parse_agent expects a RunManager with set_status; provide a
    # minimal stub (the sync path does not need real run-lifecycle tracking).
    class _RM:
        async def set_status(self, run_id: str, status: Any, **kw: Any) -> None:
            record.status = status  # type: ignore[assignment]

        async def cleanup(self, run_id: str, delay: float = 0) -> None:
            pass

    # The document text is injected as the run's user message (the worker's
    # _extract_import_parse_document reads messages[-1].content).
    graph_input = {"messages": [{"role": "user", "content": body.text}]}

    # Resolved-3 blocker A (P1 fix): this endpoint calls _run_import_parse_agent
    # DIRECTLY (bypassing worker.run_agent, which sets the sandbox ContextVar at
    # its dispatch entry). Without setting it here, NuminaLocalSandboxProvider
    # ._build_thread_path_mappings sees get_family_sandbox_context()==None and
    # returns [] → read_file/str_replace fall back to DeerFlow's default-user
    # sandbox (.deer-flow/users/default/...), breaking family-scoped isolation.
    # Mirror worker.py:245's set_family_sandbox_context(family_id) call.
    from apps.agent.services.runtime.sandbox_provider import set_family_sandbox_context

    set_family_sandbox_context(family_id)

    bridge = _CapturingBridge()
    try:
        # P2 #14: bound the agent run with a hard timeout strictly shorter than
        # the backend's 120s httpx timeout (IMPORT_PARSE_TIMEOUT_SECONDS=110s)
        # so a hanging LLM / MCP call returns the empty-result contract before
        # the backend disconnects — otherwise the orphaned agent run keeps
        # consuming LLM tokens + sandbox resources after the client is gone.
        # ``asyncio.timeout`` raises ``TimeoutError``, which we map to the same
        # empty-result fallback as any other agent failure.
        async with asyncio.timeout(settings.IMPORT_PARSE_TIMEOUT_SECONDS):
            await _run_import_parse_agent(
                bridge=bridge,  # type: ignore[arg-type]
                run_manager=_RM(),  # type: ignore[arg-type]
                record=record,
                family_id=family_id,
                user_id=user_id,
                thread_id=thread_id,
                graph_input=graph_input,
                config={},
            )
    except asyncio.CancelledError:
        # Client (backend) disconnected before the run finished — cooperative
        # cancel so the in-flight LLM call stops ASAP rather than running to
        # completion as an orphan. ``_run_import_parse_agent`` handles
        # ``CancelledError`` internally and sets run status; we re-raise so
        # FastAPI closes the request cleanly.
        record.abort_event.set()
        logger.info("[parse_import] client disconnected, aborting run=%s", run_id)
        raise
    except TimeoutError:
        # ``asyncio.timeout`` expired — fall through to the empty-result return
        # (the ``for`` loop below finds no result event).
        logger.warning(
            "[parse_import] agent run timed out after %.1fs family=%s run=%s",
            settings.IMPORT_PARSE_TIMEOUT_SECONDS, family_id, run_id,
        )
        record.abort_event.set()
    except Exception as exc:
        logger.warning("[parse_import] agent run failed family=%s err=%s", family_id, type(exc).__name__)
        return dict(_EMPTY_RESULT)

    # Harvest the import-parse.result custom event (worker emits at most one).
    for event, data in bridge.published:
        if event == "custom" and isinstance(data, dict) and data.get("type") == "import-parse.result":
            payload = data.get("payload")
            if isinstance(payload, dict):
                return payload
        if event == "custom" and isinstance(data, dict) and data.get("type") == "report.step2_json":
            # parse_report_json may be reused; treat the payload as the result.
            payload = data.get("payload")
            if isinstance(payload, dict):
                return payload

    # No result event (LLM produced no parseable JSON) — return empty result.
    logger.info("[parse_import] no import-parse.result event family=%s run=%s", family_id, run_id)
    return dict(_EMPTY_RESULT)
