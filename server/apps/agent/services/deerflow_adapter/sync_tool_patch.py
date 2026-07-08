"""Runtime compatibility patches for the pinned DeerFlow harness.

The installed ``deerflow-harness`` (rev ``4538c322``) predates upstream fix
``3599b570`` ("fix(harness): wrap all async-only tools for sync clients"). In
that older version, ``deerflow.tools.tools.get_available_tools`` only applies
``_ensure_sync_invocable_tool`` to config-loaded tools, NOT to built-in tools
added via ``SUBAGENT_TOOLS`` (i.e. ``task``). Because ``DeerFlowClient.stream``
runs the graph synchronously, the async-only ``task`` StructuredTool raises
``NotImplementedError: StructuredTool does not support sync invocation`` when
the LLM tries to delegate to a subagent (ultra mode).

This module monkey-patches ``get_available_tools`` to wrap every returned tool
through ``_ensure_sync_invocable_tool`` so the sync stream path can invoke
async-only tools (``task``) the same way it already invokes MCP tools.

Call :func:`apply_sync_tool_patches` once from the agent lifespan startup.
"""

from __future__ import annotations

import inspect
import logging

logger = logging.getLogger(__name__)

_patched = False


def apply_sync_tool_patches() -> None:
    """Wrap all DeerFlow tools for sync invocation (idempotent)."""
    global _patched
    if _patched:
        return

    try:
        from deerflow.tools.tools import (
            _ensure_sync_invocable_tool,
        )
        from deerflow.tools.tools import (
            get_available_tools as _orig_get_available_tools,
        )
    except ImportError:
        logger.warning("[sync_tool_patch] deerflow tools module not found; skipping")
        return

    # Detect whether the installed version already wraps built-in tools
    # (upstream fix 3599b570). If so, no patch is needed.
    try:
        source = inspect.getsource(_orig_get_available_tools)
        if "_ensure_sync_invocable_tool(t) for t in" in source.replace(" ", " "):
            logger.debug("[sync_tool_patch] upstream fix already present; skipping")
            _patched = True
            return
    except Exception:
        pass

    def _patched_get_available_tools(*args, **kwargs):
        tools = _orig_get_available_tools(*args, **kwargs)
        return [_ensure_sync_invocable_tool(t) for t in tools]

    # Replace on the module so other importers pick up the patched version.
    import deerflow.tools.tools as _tools_mod

    _tools_mod.get_available_tools = _patched_get_available_tools

    logger.info("[sync_tool_patch] patched get_available_tools to wrap all tools for sync invocation")
    _patched = True
