"""Runtime compatibility patches for the pinned DeerFlow harness.

The pinned ``deerflow-harness`` (rev ``6556d09d``, version 2.1.0) upstream-fixed
several bugs this module used to patch. The following overrides were therefore
removed as strictly weaker duplicates:

- ``deerflow.tools.sync.make_sync_tool_wrapper`` now captures
  ``contextvars.copy_context()`` and runs the coroutine inside it in the pool
  thread (upstream ``sync.py``). It also gained ``RunnableConfig`` injection
  support (``_get_runnable_config_param``) that the old numina patch lacked.
- ``deerflow.tools.builtins.task_tool._find_usage_recorder`` now unwraps
  ``BaseCallbackManager`` via ``.handlers`` (upstream ``task_tool.py``).
- ``DeerFlowClient._tool_message_event`` and ``DeerFlowClient._serialize_message``
  now preserve ``ToolMessage.artifact`` (client.py:447-474), so the structured
  ``human_input`` payload from ``ClarificationMiddleware`` reaches the frontend
  in both ``messages`` and ``values`` stream modes without numina patches.

What remains here is functionality the upstream harness does NOT provide:

1. ``get_available_tools`` patch - filters tools to the active skill's
   allowed-tools whitelist. The upstream sync-wrap fix (3599b570) is detected
   at runtime; when present we skip our own wrap. Clarification
   (``ask_clarification``) is handled natively by DeerFlow's
   ``ClarificationMiddleware`` (always last in ``build_middlewares``), which
   intercepts the tool call and emits a ``human_input`` artifact - no numina
   override needed.
2. (Removed) ``_apply_subagent_contextvar_patch`` — confirmed redundant after
   thorough investigation (2026-08-07). DeerFlow 6556d09d's
   ``_submit_to_isolated_loop_in_context`` wraps
   ``run_coroutine_threadsafe`` in ``context.run(lambda: ...)``, which captures
   the entire active context at ``copy_context()`` time. All 5 Numina
   ContextVars (sandbox_family_id, caller_user_id, extensions_config_path,
   DeerFlow _current_user, active_skill) are set before ``copy_context()`` and
   propagate correctly through the 3-layer chain (worker → executor thread →
   subagent isolated loop). Verified against Python 3.12 ``contextvars``
   semantics: ``call_soon_threadsafe`` inherits context, ``create_task``
   propagates it, coroutine body sees all vars.
3. MCP httpx factory injection + per-family extensions-config path resolution —
   Numina specific (``trust_env=False`` on ``build_server_params`` for SSE/HTTP
   proxy bypass + coroutine-scoped ContextVar for multi-family MCP config
   isolation). ``tool_name_prefix`` is now declarative (set in
   ``_write_extensions_config``), not patched.

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
    # (upstream fix 3599b570). The fix wraps the *final assembled* tool list
    # (``all_tools`` / ``unique_tools``) before returning, not just the
    # config-loaded ``loaded_tools``. We detect by checking whether the
    # ``return`` statement runs tools through ``_ensure_sync_invocable_tool``;
    # the older code only wraps ``loaded_tools`` (line ~44) but leaves
    # ``SUBAGENT_TOOLS`` (``task``) and other builtins unwrapped.
    #
    # IMPORTANT: Even when the upstream fix is present, we MUST still patch
    # get_available_tools to filter tools to the active skill's allowed-tools
    # whitelist. The upstream fix only handles sync wrapping.
    upstream_fix_present = False
    try:
        source = inspect.getsource(_orig_get_available_tools)
        return_section = source.rsplit("return", 1)[-1]
        if "_ensure_sync_invocable_tool" in return_section:
            upstream_fix_present = True
            logger.debug(
                "[sync_tool_patch] upstream sync-wrap fix detected; will still patch for interrupt tools"
            )
    except Exception:
        pass

    def _patched_get_available_tools(*args, **kwargs):
        tools = _orig_get_available_tools(*args, **kwargs)

        # When the upstream fix is present, tools are already sync-wrapped.
        # When it's absent, we must wrap them ourselves.
        if not upstream_fix_present:
            for t in tools:
                _ensure_sync_invocable_tool(t)

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

    logger.info(
        "[sync_tool_patch] patched get_available_tools to wrap all tools for sync invocation"
    )
    _patched = True
    # Upstream 6556d09d natively preserves ToolMessage.artifact in both stream
    # modes (client.py:447-474), so _apply_clarification_artifact_patch was removed.
    # _apply_subagent_contextvar_patch removed (2026-08-07): native context.run()
    # in _submit_to_isolated_loop_in_context already captures all ContextVars.
    _apply_mcp_httpx_factory_patch()
    _apply_mcp_cache_threading_lock_patch()
    _apply_original_user_content_patch()


def _apply_original_user_content_patch() -> None:
    """Patch ``HumanMessage.__init__`` to inject ``ORIGINAL_USER_CONTENT_KEY``.

    DeerFlow's ``SkillActivationMiddleware`` reads ``ORIGINAL_USER_CONTENT_KEY``
    from the HumanMessage's ``additional_kwargs`` to get the raw user text
    (before JSON wrapping). Numina's adapter wraps user text as JSON context,
    so without this key, ``parse_slash_skill_reference`` fails on the JSON's
    leading ``{``.

    This patch reads the ``numina_original_user_content`` ContextVar (set by
    the adapter before calling ``stream()``) and merges it into the
    HumanMessage's ``additional_kwargs`` at construction time, so DeerFlow's
    middleware sees the raw user text.

    The ContextVar propagates into the DeerFlow executor thread via
    ``_run_in_executor_with_context`` (which uses ``contextvars.copy_context()``),
    so the value set in the adapter's async context is visible inside
    ``DeerFlowClient.stream()``.
    """
    try:
        from langchain_core.messages import HumanMessage
    except ImportError:
        logger.warning(
            "[sync_tool_patch] langchain_core.messages.HumanMessage not found; skipping"
        )
        return

    _orig_init = HumanMessage.__init__

    def _patched_init(self, *args, **kwargs):
        """Inject ORIGINAL_USER_CONTENT_KEY from ContextVar into additional_kwargs."""
        try:
            from deerflow.utils.messages import ORIGINAL_USER_CONTENT_KEY

            from apps.agent.services.deerflow_adapter.original_user_content_context import (
                get_original_user_content,
            )

            original_content = get_original_user_content()
            if original_content is not None:
                # Merge into additional_kwargs (don't overwrite if already set)
                additional_kwargs = kwargs.get("additional_kwargs") or {}
                if ORIGINAL_USER_CONTENT_KEY not in additional_kwargs:
                    additional_kwargs[ORIGINAL_USER_CONTENT_KEY] = original_content
                    kwargs["additional_kwargs"] = additional_kwargs
        except Exception as e:
            # Fail-open: if the patch fails, continue without the key
            logger.debug("[sync_tool_patch] original_user_content patch failed: %s", e)

        _orig_init(self, *args, **kwargs)

    HumanMessage.__init__ = _patched_init  # type: ignore[method-assign]
    logger.info(
        "[sync_tool_patch] patched HumanMessage.__init__ to inject ORIGINAL_USER_CONTENT_KEY"
    )


def _apply_active_skill_tool_filter(tools):
    """Filter tools to the active skill's allowed-tools whitelist.

    Called from the patched ``get_available_tools``. No active skill (e.g.
    trigger-based feature dispatch, which loads tools via ``enable_tools``) →
    return tools unchanged (legacy allow-all). Active skill with no
    allowed-tools declaration (``allowed_tools is None``) → the filter returns
    all tools (``allowed_tool_names_for_skills`` returns None for undeclared
    skills, meaning allow-all). Only skills that declare ``allowed-tools`` (even
    ``[]``) restrict the tool set.

    Security: ``UserScopedSkillStorage`` is used instead of bare
    ``LocalSkillStorage`` so custom skills stored under
    ``users/{family_id}/skills/custom/`` are discoverable. Without the
    user-scoped storage the filter cannot find custom skills and the fallback
    path returns all tools unfiltered — granting custom skills full tool access
    (R4 allowed-tools bypass).
    """
    try:
        from apps.agent.services.deerflow_adapter.active_skill_context import (
            get_active_skill,
        )

        active_skill_name = get_active_skill()
    except Exception:
        return tools
    if not active_skill_name:
        return tools
    try:
        from deerflow.skills.storage.user_scoped_skill_storage import (
            UserScopedSkillStorage,
        )
        from deerflow.skills.tool_policy import (
            ALWAYS_AVAILABLE_BUILTIN_TOOL_NAMES,
            filter_tools_by_skill_allowed_tools,
        )

        from apps.agent.services.runtime.sandbox_provider import (
            get_family_sandbox_context,
        )

        # review_skill_package is a DeerFlow built-in that only works inside
        # DeerFlow's own workspace (requires .skill archives or SKILL.md dirs).
        # In the numina agent workspace it always fails with ValueError and
        # causes the LLM to loop retrying — exclude it from the always-available
        # set so the chat skill never sees it.
        _numina_always_available = ALWAYS_AVAILABLE_BUILTIN_TOOL_NAMES - {
            "review_skill_package",
        }
        # Use UserScopedSkillStorage so custom skills under
        # users/{family_id}/skills/custom/ are discoverable. Bare
        # LocalSkillStorage() scans only the builtin directory and fails to
        # find custom skills — the fallback returns all tools unfiltered.
        family_id = get_family_sandbox_context()
        if not family_id:
            logger.warning(
                "[sync_tool_patch] no sandbox family_id; skipping tool filter for skill %r",
                active_skill_name,
            )
            return tools
        storage = UserScopedSkillStorage(user_id=str(family_id))
        all_skills = storage.load_skills(enabled_only=True)
        active_skills = [s for s in all_skills if s.name == active_skill_name]
        if not active_skills:
            logger.warning(
                "[sync_tool_patch] active skill %r not found in skill storage (family=%s); skipping tool filter",
                active_skill_name,
                family_id,
            )
            return tools
        filtered = filter_tools_by_skill_allowed_tools(
            tools,
            active_skills,
            always_allowed_tool_names=_numina_always_available,
        )
        if len(filtered) < len(tools):
            logger.debug(
                "[sync_tool_patch] filtered tools %d -> %d for active skill %r",
                len(tools),
                len(filtered),
                active_skill_name,
            )
        return filtered
    except Exception as e:
        logger.warning(
            "[sync_tool_patch] active-skill tool filter failed (allowing all): %s", e
        )
        return tools



def _apply_mcp_httpx_factory_patch() -> None:
    """Patch ``build_server_params`` to inject ``trust_env=False`` into SSE/HTTP.

    ``langchain-mcp-adapters``' ``sse_client`` builds its httpx client via
    :func:`mcp.shared._httpx_utils.create_mcp_http_client`, which does NOT set
    ``trust_env=False``. With the default ``trust_env=True`` the client honours
    system proxy env vars, which intercept internal MCP SSE calls and return
    503 (the agent then loads zero MCP tools and reports "all records empty").

    Instead of rewriting ``get_mcp_tools`` (which drops native session pooling,
    concurrent discovery, timeout, validation, routing tags, and interceptors),
    we patch ``build_server_params`` — the clean injection point — to add
    ``httpx_client_factory`` to each SSE/HTTP server's config dict. The native
    ``get_mcp_tools`` then uses this factory when creating MCP connections.

    The ``tool_name_prefix`` per-server setting is handled declaratively:
    ``_write_extensions_config`` writes ``tool_name_prefix: false`` into
    extensions_config.json, which DeerFlow's ``McpServerConfig`` parses natively
    and ``get_mcp_tools`` honours per-server at line 696.
    """
    try:
        import httpx
    except ImportError:
        logger.warning(
            "[sync_tool_patch] httpx not installed; skipping MCP proxy patch"
        )
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
        import deerflow.mcp.client as _client_mod

        _orig_build_server_params = _client_mod.build_server_params
    except (ImportError, AttributeError):
        logger.warning(
            "[sync_tool_patch] deerflow.mcp.client.build_server_params not found; skipping"
        )
        return

    def _patched_build_server_params(
        server_name: str, config: object
    ) -> dict:
        """Inject httpx_client_factory for SSE/HTTP servers (trust_env=False)."""
        params = _orig_build_server_params(server_name, config)
        if params.get("transport") in ("sse", "http"):
            params["httpx_client_factory"] = _no_proxy_httpx_client
        return params

    _client_mod.build_server_params = _patched_build_server_params
    logger.info(
        "[sync_tool_patch] patched build_server_params to inject trust_env=False on SSE/HTTP MCP connections"
    )
    _apply_extensions_config_path_patch()


def _apply_extensions_config_path_patch() -> None:
    """Patch ``ExtensionsConfig.resolve_config_path`` to read the per-run ContextVar.

    DeerFlow resolves the MCP extensions config file via
    ``ExtensionsConfig.resolve_config_path(config_path=None)``, which consults the
    process-global ``DEER_FLOW_EXTENSIONS_CONFIG_PATH`` env var (priority 2). That
    env var is a single process-wide slot — under multi-family concurrency two
    interleaved runs overwrite each other's value, leaking family-A's MCP SSE URL
    (which embeds family-A's id) into family-B's run.

    This patch inserts a new priority-0 step: when no explicit ``config_path``
    argument is passed, consult Numina's coroutine-scoped
    ``numina_extensions_config_path`` ContextVar (set by the adapter alongside
    family_id). The ContextVar is propagated into the deerflow executor thread
    and the sync tool-executor pool, so every call site that resolves the
    extensions config — ``get_available_tools``' gate check, the MCP cache's
    staleness check, and native ``get_mcp_tools`` — all see the same per-run
    path with no cross-family leakage. An explicit ``config_path`` argument
    still takes precedence (priority 1), preserving the original API contract.
    """
    try:
        from deerflow.config.extensions_config import ExtensionsConfig
    except ImportError:
        logger.warning(
            "[sync_tool_patch] ExtensionsConfig not found; skipping resolve_config_path patch"
        )
        return

    _orig_resolve_config_path = ExtensionsConfig.resolve_config_path

    def _patched_resolve_config_path(cls, config_path=None):  # type: ignore[no-untyped-def]
        from apps.agent.services.runtime.sandbox_provider import (
            get_extensions_config_path as _get_ext_path,
        )

        if config_path is None:
            ctx_path = _get_ext_path()
            if ctx_path:
                # Hand off to the original resolver with an explicit path so it
                # still validates existence and returns a Path (priority 1 path).
                return _orig_resolve_config_path.__func__(cls, ctx_path)
        return _orig_resolve_config_path.__func__(cls, config_path)

    ExtensionsConfig.resolve_config_path = classmethod(_patched_resolve_config_path)  # type: ignore[assignment]
    logger.info(
        "[sync_tool_patch] patched ExtensionsConfig.resolve_config_path to consult per-run ContextVar before env var"
    )


def _apply_mcp_cache_threading_lock_patch() -> None:
    """Patch ``deerflow.mcp.cache.get_cached_mcp_tools`` to fix event-loop deadlock.

    Upstream bug: ``_initialization_lock = asyncio.Lock()`` is created at module
    import time, bound to the main thread's event loop. When DeerFlow's worker
    threads (``deerflow_N``) lazily initialize MCP tools via ``asyncio.run()``,
    a *new* event loop is created, but the module-level ``asyncio.Lock`` still
    references the original loop — ``_get_loop().create_future()`` raises
    ``RuntimeError`` on a cross-thread loop access. The upstream ``except
    RuntimeError`` handler at ``cache.py:177`` catches the initial
    ``get_event_loop()`` failure, retries with ``asyncio.run()``, but that also
    fails at ``initialize_mcp_tools`` line 125 (``async with _initialization_lock``)
    for the same reason. Result: **MCP tools: 0** on every agent run.

    Fix: replace the lazy-init path with a ``threading.Lock`` + ``asyncio.run()``
    combination that works correctly in any thread. The threading lock prevents
    concurrent re-initialization; ``asyncio.run()`` creates a fresh event loop
    scoped to the call. The native ``get_mcp_tools`` (via the patched
    ``build_server_params``) injects ``httpx_client_factory`` for proxy bypass;
    auth headers are written to extensions_config.json, so no header plumbing
    is needed here.

    Trigger: ``MCP tools: 0`` in agent logs + ``Failed to lazy-initialize MCP
    tools`` with ``RuntimeError: There is no current event loop in thread
    'deerflow_N'``.
    """
    try:
        import deerflow.mcp.cache as _cache_mod
    except ImportError:
        logger.warning("[sync_tool_patch] deerflow.mcp.cache not found; skipping")
        return

    import asyncio as _asyncio
    import threading as _threading

    _lazy_init_thread_lock = _threading.Lock()

    def _patched_get_cached_mcp_tools():
        """Thread-safe lazy init of MCP tools, safe to call from worker threads."""
        if _cache_mod._cache_initialized and not _cache_mod._is_cache_stale():
            return _cache_mod._mcp_tools_cache or []

        if _cache_mod._is_cache_stale():
            _cache_mod.reset_mcp_tools_cache()

        if _cache_mod._cache_initialized:
            return _cache_mod._mcp_tools_cache or []

        # Use a threading lock to serialize init across worker threads, then
        # asyncio.run() which creates a fresh event loop scoped to this call —
        # avoids the upstream asyncio.Lock bound to the wrong loop.
        if not _lazy_init_thread_lock.acquire(blocking=False):
            # Another thread is initializing; wait briefly then return whatever
            # is cached (even if empty — better than deadlock).
            _lazy_init_thread_lock.acquire()
            _lazy_init_thread_lock.release()
            return _cache_mod._mcp_tools_cache or []
        try:
            # Double-check after acquiring lock
            if _cache_mod._cache_initialized:
                return _cache_mod._mcp_tools_cache or []
            # Bypass upstream initialize_mcp_tools() which uses the broken
            # module-level asyncio.Lock. Call get_mcp_tools() directly — the
            # patched build_server_params injects httpx_client_factory.
            from deerflow.mcp.tools import get_mcp_tools

            _cache_mod._mcp_tools_cache = _asyncio.run(get_mcp_tools())
            _cache_mod._config_path, _cache_mod._config_signature = (
                _cache_mod._current_config_state()
            )
            _cache_mod._cache_initialized = True
            logger.info(
                "[sync_tool_patch] MCP tools initialized via threading-lock patch: %d tool(s)",
                len(_cache_mod._mcp_tools_cache or []),
            )
        except Exception:
            logger.exception(
                "[sync_tool_patch] MCP tools init failed via threading-lock patch"
            )
            return []
        finally:
            _lazy_init_thread_lock.release()

        return _cache_mod._mcp_tools_cache or []

    _cache_mod.get_cached_mcp_tools = _patched_get_cached_mcp_tools
    logger.info(
        "[sync_tool_patch] patched get_cached_mcp_tools to use threading.Lock (fixes event-loop deadlock in worker threads)"
    )
