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

It also patches ``make_sync_tool_wrapper`` to propagate ``contextvars`` into
the thread pool executor. Without this, ``task_tool`` (which runs in
``_SYNC_TOOL_EXECUTOR``) cannot access ``get_app_config()`` (set via
``push_current_app_config()`` ContextVar in the parent thread) or
``get_stream_writer()`` (LangGraph runtime ContextVar). The result is that
subagents load the wrong config (base template with placeholder API keys)
and ``task_started``/``task_completed`` custom events are never emitted —
the frontend stays stuck at "正在执行 N 个子任务".

It also patches ``deerflow.mcp.tools.get_mcp_tools`` to inject an
``httpx_client_factory`` that builds the MCP client's httpx AsyncClient with
``trust_env=False``. Without this, ``langchain-mcp-adapters``' ``sse_client``
creates an httpx client with the default ``trust_env=True``, which picks up
system proxy env vars (HTTP_PROXY / ALL_PROXY / macOS system proxy). The proxy
intercepts the internal MCP SSE call (``/api/v1/internal/mcp/{family_id}/sse``)
and returns 503, so zero MCP tools load and the agent falls back to the empty
context fields ("所有记录仍为空"). This mirrors the ``trust_env=False`` that
Numina's own :class:`BackendClient` already sets for the same reason.

Call :func:`apply_sync_tool_patches` once from the agent lifespan startup.
"""

from __future__ import annotations

import inspect
import logging

from apps.agent.services.deerflow_adapter.interrupt_tools import get_interrupt_tools

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
    # (upstream fix 3599b570). The fix wraps the *final assembled* tool list
    # (``all_tools`` / ``unique_tools``) before returning, not just the
    # config-loaded ``loaded_tools``. We detect by checking whether the
    # ``return`` statement runs tools through ``_ensure_sync_invocable_tool``;
    # the older code only wraps ``loaded_tools`` (line ~44) but leaves
    # ``SUBAGENT_TOOLS`` (``task``) and other builtins unwrapped.
    #
    # IMPORTANT: Even when the upstream fix is present, we MUST still patch
    # get_available_tools to replace DeerFlow's placeholder ask_clarification
    # with Numina's interrupt-based version. The upstream fix only handles
    # sync wrapping — it does NOT know about our interrupt mechanism.
    upstream_fix_present = False
    try:
        source = inspect.getsource(_orig_get_available_tools)
        return_section = source.rsplit("return", 1)[-1]
        if "_ensure_sync_invocable_tool" in return_section:
            upstream_fix_present = True
            logger.debug("[sync_tool_patch] upstream sync-wrap fix detected; will still patch for interrupt tools")
    except Exception:
        pass

    def _patched_get_available_tools(*args, **kwargs):
        tools = _orig_get_available_tools(*args, **kwargs)

        # When the upstream fix is present, tools are already sync-wrapped.
        # When it's absent, we must wrap them ourselves.
        if not upstream_fix_present:
            for t in tools:
                _ensure_sync_invocable_tool(t)

        # Remove DeerFlow's placeholder ask_clarification before adding our interrupt tool.
        # DeerFlow's builtin returns a static string and does NOT call interrupt(),
        # so if the LLM selects it instead of ours, human-in-the-loop breaks.
        tools = [t for t in tools if t.name != "ask_clarification"]

        # Add interrupt tools
        interrupt_tools = get_interrupt_tools()
        for t in interrupt_tools:
            if not upstream_fix_present:
                _ensure_sync_invocable_tool(t)
        tools.extend(interrupt_tools)

        # Note: describe_skill is NOT injected here. DeerFlow registers its native
        # describe_skill tool (deerflow.skills.describe.build_describe_skill_tool)
        # only when skills.deferred_discovery=True (lead_agent/agent.py:540-566).
        # With deferred_discovery=False (Numina default), the full skill metadata is
        # inlined into the system prompt's <available_skills> and the LLM loads the
        # full SKILL.md directly via read_file — describe_skill is unneeded.

        # Restrict tools to the active skill's declared allowed-tools whitelist.
        # Numina's worker pre-selects one skill per chat run (chat / chat-search)
        # and sets it via active_skill_context. DeerFlow's native
        # SkillToolPolicyMiddleware is passive (no slash activation, no
        # skill_context load) in our flow, so we filter here using the pure
        # filter_tools_by_skill_allowed_tools function. Skills without an
        # allowed-tools declaration (None) → allow-all (no filtering).
        tools = _apply_active_skill_tool_filter(tools)

        return tools

    # Replace on BOTH the submodule and the parent package. DeerFlowClient's
    # ``_get_tools()`` imports ``get_available_tools`` from the ``deerflow.tools``
    # *package* (``from deerflow.tools import get_available_tools``), whose
    # ``__init__.py`` re-exports it via ``from .tools import get_available_tools``.
    # Patching only ``deerflow.tools.tools.get_available_tools`` leaves the
    # package-level binding pointing at the original unwrapped function, so the
    # client never sees the patch and the ``task`` tool still fails with
    # ``StructuredTool does not support sync invocation``. Both names must be
    # rebound for the patch to reach the sync stream path.
    import deerflow.tools as _tools_pkg
    import deerflow.tools.tools as _tools_mod

    _tools_mod.get_available_tools = _patched_get_available_tools
    _tools_pkg.get_available_tools = _patched_get_available_tools

    logger.info("[sync_tool_patch] patched get_available_tools to wrap all tools for sync invocation")
    _patched = True
    _apply_contextvar_propagation_patch()
    _apply_mcp_proxy_bypass_patch()


def _apply_active_skill_tool_filter(tools):
    """Filter tools to the active skill's allowed-tools whitelist.

    Called from the patched ``get_available_tools``. No active skill (e.g.
    trigger-based feature dispatch, which loads tools via ``enable_tools``) →
    return tools unchanged (legacy allow-all). Active skill with no
    allowed-tools declaration (``allowed_tools is None``) → the filter returns
    all tools (``allowed_tool_names_for_skills`` returns None for undeclared
    skills, meaning allow-all). Only skills that declare ``allowed-tools`` (even
    ``[]``) restrict the tool set.
    """
    try:
        from apps.agent.services.deerflow_adapter.active_skill_context import get_active_skill
        active_skill_name = get_active_skill()
    except Exception:
        return tools
    if not active_skill_name:
        return tools
    try:
        from deerflow.skills.storage.local_skill_storage import LocalSkillStorage
        from deerflow.skills.tool_policy import (
            ALWAYS_AVAILABLE_BUILTIN_TOOL_NAMES,
            filter_tools_by_skill_allowed_tools,
        )
        storage = LocalSkillStorage()
        all_skills = storage.load_skills(enabled_only=True)
        active_skills = [s for s in all_skills if s.name == active_skill_name]
        if not active_skills:
            logger.warning(
                "[sync_tool_patch] active skill %r not found in skill storage; skipping tool filter",
                active_skill_name,
            )
            return tools
        filtered = filter_tools_by_skill_allowed_tools(
            tools,
            active_skills,
            always_allowed_tool_names=ALWAYS_AVAILABLE_BUILTIN_TOOL_NAMES,
        )
        if len(filtered) < len(tools):
            logger.debug(
                "[sync_tool_patch] filtered tools %d -> %d for active skill %r",
                len(tools), len(filtered), active_skill_name,
            )
        return filtered
    except Exception as e:
        logger.warning(
            "[sync_tool_patch] active-skill tool filter failed (allowing all): %s", e
        )
        return tools


def _apply_contextvar_propagation_patch() -> None:
    """Patch ``make_sync_tool_wrapper`` to propagate contextvars into the pool thread.

    ``deerflow.tools.sync.make_sync_tool_wrapper`` submits async tool coroutines
    to ``_SYNC_TOOL_EXECUTOR`` (a ``ThreadPoolExecutor``) via ``asyncio.run()``.
    However, ``ThreadPoolExecutor.submit()`` does NOT propagate ``contextvars``
    from the calling thread to the worker thread. This means:

    - ``get_app_config()`` (set via ``push_current_app_config()`` ContextVar in
      the parent deerflow thread) is not available → subagent loads wrong/empty
      config (base template with placeholder API keys) → API 401 or wrong model
    - ``get_stream_writer()`` (LangGraph runtime ContextVar) returns a no-op →
      ``task_started``/``task_completed`` custom events are never emitted →
      frontend stays stuck at "正在执行 N 个子任务"

    The fix captures the calling context via ``contextvars.copy_context()`` and
    runs the coroutine inside that context in the pool thread.
    """
    try:
        import deerflow.tools.sync as _sync_mod
        _orig_make_sync_tool_wrapper = _sync_mod.make_sync_tool_wrapper
    except (ImportError, AttributeError):
        logger.warning("[sync_tool_patch] deerflow.tools.sync not found; skipping contextvar patch")
        return

    def _patched_make_sync_tool_wrapper(coro, tool_name: str):
        """Build a sync wrapper that propagates contextvars into the pool thread."""
        import asyncio as _asyncio
        import contextvars

        # Capture the calling context (includes app_config, stream_writer, etc.)
        # at the time the wrapper is CALLED (not when make_sync_tool_wrapper is called).
        # This is critical: the context must be captured in sync_wrapper(), not here,
        # because the tool is invoked from the deerflow thread which has the correct
        # ContextVar values for this specific family request.
        def sync_wrapper(*args, **kwargs):
            # Capture context from the calling thread (deerflow stream thread)
            ctx = contextvars.copy_context()

            def _run_in_context():
                return _asyncio.run(ctx.run(coro, *args, **kwargs))

            try:
                loop = _asyncio.get_running_loop()
            except RuntimeError:
                loop = None

            try:
                if loop is not None and loop.is_running():
                    # Called from within an event loop (deerflow stream thread) —
                    # submit to the pool executor but run inside the captured context
                    future = _sync_mod._SYNC_TOOL_EXECUTOR.submit(_run_in_context)
                    return future.result()
                # No running loop — run directly in the captured context
                return _run_in_context()
            except Exception as e:
                _sync_mod.logger.error(
                    "Error invoking tool %r via sync wrapper: %s", tool_name, e, exc_info=True
                )
                raise

        return sync_wrapper

    _sync_mod.make_sync_tool_wrapper = _patched_make_sync_tool_wrapper
    logger.info("[sync_tool_patch] patched make_sync_tool_wrapper to propagate contextvars into pool thread")
    _apply_subagent_contextvar_patch()
    _apply_callback_manager_patch()


def _apply_callback_manager_patch() -> None:
    """Patch ``_find_usage_recorder`` to handle CallbackManager correctly.

    DeerFlow's ``task_tool._find_usage_recorder`` tries to iterate over
    ``runtime.config.get("callbacks", [])``, but in our environment this is
    a ``CallbackManager`` object (not a list), causing:
        TypeError: 'CallbackManager' object is not iterable

    Fix: extract the handlers list from CallbackManager before iterating.
    """
    import sys
    try:
        # Import the actual module, not the tool instance
        import importlib.util
        spec = importlib.util.find_spec("deerflow.tools.builtins.task_tool")
        if spec is None or spec.loader is None:
            logger.warning("[sync_tool_patch] deerflow.tools.builtins.task_tool module not found; skipping")
            return
        _task_tool_mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(_task_tool_mod)
    except (ImportError, AttributeError, Exception) as e:
        logger.warning(f"[sync_tool_patch] failed to load task_tool module: {e}; skipping")
        return

    if not hasattr(_task_tool_mod, '_find_usage_recorder'):
        logger.warning("[sync_tool_patch] _find_usage_recorder not found in task_tool module; skipping")
        return

    _orig_find_usage_recorder = _task_tool_mod._find_usage_recorder

    def _patched_find_usage_recorder(runtime):
        """Extract usage recorder from runtime, handling CallbackManager."""
        if runtime is None:
            return None
        config = getattr(runtime, "config", None)
        if not isinstance(config, dict):
            return None
        callbacks = config.get("callbacks", [])
        # Handle CallbackManager object (has .handlers attribute)
        if hasattr(callbacks, "handlers"):
            callbacks = callbacks.handlers
        # Ensure callbacks is iterable
        if not hasattr(callbacks, "__iter__"):
            callbacks = [callbacks] if callbacks else []
        for cb in callbacks:
            if hasattr(cb, "record_external_llm_usage_records"):
                return cb
        return None

    _task_tool_mod._find_usage_recorder = _patched_find_usage_recorder
    # Also patch in sys.modules to ensure the patched version is used
    if 'deerflow.tools.builtins.task_tool' in sys.modules:
        sys.modules['deerflow.tools.builtins.task_tool']._find_usage_recorder = _patched_find_usage_recorder
    logger.info("[sync_tool_patch] patched _find_usage_recorder to handle CallbackManager")


def _apply_subagent_contextvar_patch() -> None:
    """Patch ``_submit_to_isolated_loop_in_context`` to propagate contextvars.

    The original function calls ``context.run(lambda: asyncio.run_coroutine_threadsafe(...))``
    which sets the context on the *calling* thread, but the coroutine runs on the
    isolated loop thread where the context is NOT propagated.

    Fix: wrap the coroutine so it runs inside the captured context on the isolated loop.
    """
    try:
        import deerflow.subagents.executor as _executor_mod
    except (ImportError, AttributeError):
        logger.warning("[sync_tool_patch] deerflow.subagents.executor not found; skipping")
        return

    _orig_submit = _executor_mod._submit_to_isolated_loop_in_context

    def _patched_submit(context, coro_factory):
        """Submit coroutine to isolated loop while preserving ContextVar state."""
        import asyncio as _asyncio

        async def _run_in_context():
            return await context.run(coro_factory)

        return _asyncio.run_coroutine_threadsafe(
            _run_in_context(),
            _executor_mod._get_isolated_subagent_loop(),
        )

    _executor_mod._submit_to_isolated_loop_in_context = _patched_submit
    logger.info("[sync_tool_patch] patched _submit_to_isolated_loop_in_context to propagate contextvars into isolated loop")


def _apply_mcp_proxy_bypass_patch() -> None:
    """Patch ``get_mcp_tools`` to bypass system proxy on SSE/HTTP connections.

    ``langchain-mcp-adapters``' ``sse_client`` builds its httpx client via
    :func:`mcp.shared._httpx_utils.create_mcp_http_client`, which does NOT set
    ``trust_env=False``. With the default ``trust_env=True`` the client honours
    system proxy env vars, which intercept internal MCP SSE calls and return
    503 (the agent then loads zero MCP tools and reports "all records empty").
    """
    try:
        import httpx
    except ImportError:
        logger.warning("[sync_tool_patch] httpx not installed; skipping MCP proxy patch")
        return

    def _no_proxy_httpx_client(
        headers: dict[str, str] | None = None,
        timeout: httpx.Timeout | None = None,
        auth: httpx.Auth | None = None,
    ) -> httpx.AsyncClient:
        """httpx client factory that bypasses system proxy (trust_env=False).

        Mirrors :func:`create_mcp_http_client` defaults (follow_redirects=True,
        30s / 300s read timeout) but forces ``trust_env=False`` so internal
        MCP SSE calls never route through a system proxy.
        """
        kwargs: dict = {"follow_redirects": True, "trust_env": False}
        if timeout is None:
            kwargs["timeout"] = httpx.Timeout(30.0, read=300.0)
        else:
            kwargs["timeout"] = timeout
        if headers is not None:
            kwargs["headers"] = headers
        if auth is not None:
            kwargs["auth"] = auth
        return httpx.AsyncClient(**kwargs)

    try:
        import deerflow.mcp.tools as _mcp_mod
        from deerflow.config.extensions_config import ExtensionsConfig
        from deerflow.mcp.client import build_servers_config
        from deerflow.mcp.oauth import (
            build_oauth_tool_interceptor,
            get_initial_oauth_headers,
        )
        from deerflow.tools.sync import make_sync_tool_wrapper
        from langchain_mcp_adapters.client import MultiServerMCPClient

        _orig_get_mcp_tools = _mcp_mod.get_mcp_tools
    except ImportError:
        logger.warning("[sync_tool_patch] deerflow.mcp.tools or adapters not found; skipping MCP proxy patch")
        return

    async def _patched_get_mcp_tools():
        """Patched get_mcp_tools that injects trust_env=False into SSE/HTTP."""
        extensions_config = ExtensionsConfig.from_file()
        servers_config = build_servers_config(extensions_config)
        if not servers_config:
            _mcp_mod.logger.info("No enabled MCP servers configured")
            return []

        # Inject the no-proxy httpx client factory into every SSE/HTTP server
        # so internal MCP calls bypass system proxy env vars.
        for _name, cfg in servers_config.items():
            if cfg.get("transport") in ("sse", "http"):
                cfg["httpx_client_factory"] = _no_proxy_httpx_client

        # Replicate the original OAuth header + interceptor handling.
        initial_oauth_headers = await get_initial_oauth_headers(extensions_config)
        for server_name, auth_header in initial_oauth_headers.items():
            if server_name not in servers_config:
                continue
            if servers_config[server_name].get("transport") in ("sse", "http"):
                existing_headers = dict(servers_config[server_name].get("headers", {}))
                existing_headers["Authorization"] = auth_header
                servers_config[server_name]["headers"] = existing_headers

        tool_interceptors = []
        oauth_interceptor = build_oauth_tool_interceptor(extensions_config)
        if oauth_interceptor is not None:
            tool_interceptors.append(oauth_interceptor)

        try:
            client = MultiServerMCPClient(
                servers_config,
                tool_interceptors=tool_interceptors,
                tool_name_prefix=True,
            )
            tools = await client.get_tools()
            _mcp_mod.logger.info(f"Successfully loaded {len(tools)} tool(s) from MCP servers")

            for tool in tools:
                if getattr(tool, "func", None) is None and getattr(tool, "coroutine", None) is not None:
                    tool.func = make_sync_tool_wrapper(tool.coroutine, tool.name)

            return tools
        except Exception as e:
            _mcp_mod.logger.error(f"Failed to load MCP tools: {e}", exc_info=True)
            return []

    _mcp_mod.get_mcp_tools = _patched_get_mcp_tools
    logger.info("[sync_tool_patch] patched get_mcp_tools to bypass system proxy (trust_env=False) on SSE/HTTP MCP connections")
