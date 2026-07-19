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
    # C 方案（vision）：backend 预生成 thread_id + 渲染 PDF 页图后传入。
    # thread_id 让 agent 用同一沙箱（PNG 已落 uploads/）；image_paths 是容器
    # 虚拟路径列表，agent 用 view_image 读取。纯文本解析时这两项为空（向后兼容）。
    thread_id: str | None = None
    image_paths: list[str] | None = None
    # C1 直接写入流程：当传入 confirm_items（用户已确认的持仓条目）时，agent
    # 进入写入模式——调 import_assets_batch MCP 工具批量写库，而非解析文档。
    # backend /import/confirm-via-agent 转发用户确认后的条目到这里。
    confirm_items: list[dict[str, Any]] | None = None


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
    # C 方案（vision）：backend 预生成 thread_id 时复用（PNG 已渲染到该 thread 沙箱）；
    # 否则自生成（纯文本路径，向后兼容）。
    thread_id = body.thread_id or f"importparse-thread-{uuid.uuid4().hex[:12]}"
    family_id = x_family_id
    user_id = x_user_id
    image_paths = body.image_paths or []

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
    # C 方案（vision）：有 image_paths 时附加提示，引导 LLM 先 view_image 读图。
    # C1 直接写入：有 confirm_items 时进入写入模式（调 import_assets_batch）。
    confirm_items = body.confirm_items
    user_content = body.text
    if confirm_items:
        import json as _json

        items_json = _json.dumps(confirm_items, ensure_ascii=False)
        user_content = (
            f"【写入模式】请将以下已确认的持仓条目写入资产。按 SKILL.md §C1 直接写入流程："
            f"调一次 import_assets_batch 工具批量写入（items 参数=下方数组），然后输出"
            f"write_result JSON。不要解析文档、不要 view_image。\n\n"
            f"待写入条目：\n{items_json}"
        )
    elif image_paths:
        paths_list = "\n".join(f"  - {p}" for p in image_paths)
        user_content = (
            f"{body.text}\n\n"
            f"【图片模式】以下是该文档的页面图片路径，你必须按以下步骤执行，"
            f"不得跳过第 1 步直接输出 JSON：\n"
            f"1. 对下面列出的每一个路径调用 view_image 工具（参数 image_path=该路径），"
            f"逐张读取所有图片。这是强制前置条件。\n"
            f"2. 所有图片读完后，综合图片内容（以及上方文本，若有）提取持仓条目。\n"
            f"3. 输出最终 JSON 代码块。\n\n"
            f"待读取的图片路径：\n{paths_list}"
        )
    graph_input = {"messages": [{"role": "user", "content": user_content}]}

    # Resolved-3 blocker A (P1 fix): this endpoint calls _run_import_parse_agent
    # DIRECTLY (bypassing worker.run_agent, which sets the sandbox ContextVar at
    # its dispatch entry). Without setting it here, NuminaLocalSandboxProvider
    # ._build_thread_path_mappings sees get_family_sandbox_context()==None and
    # returns [] → read_file/str_replace fall back to DeerFlow's default-user
    # sandbox (.deer-flow/users/default/...), breaking family-scoped isolation.
    # Mirror worker.py:245's set_family_sandbox_context(family_id) call.
    from apps.agent.services.runtime.sandbox_provider import set_family_sandbox_context

    set_family_sandbox_context(family_id, caller_user_id=user_id)

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
