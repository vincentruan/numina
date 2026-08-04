"""Runtime compatibility patches for the pinned DeerFlow harness.

The pinned ``deerflow-harness`` (rev ``10890e10``, version 2.1.0) upstream-fixed
the two contextvar/CallbackManager bugs this module used to patch:

- ``deerflow.tools.sync.make_sync_tool_wrapper`` now captures
  ``contextvars.copy_context()`` and runs the coroutine inside it in the pool
  thread (upstream ``sync.py``). It also gained ``RunnableConfig`` injection
  support (``_get_runnable_config_param``) that the old numina patch lacked.
- ``deerflow.tools.builtins.task_tool._find_usage_recorder`` now unwraps
  ``BaseCallbackManager`` via ``.handlers`` (upstream ``task_tool.py``).

Both numina overrides were therefore **removed** as strictly weaker duplicates.
What remains here is functionality the upstream harness does NOT provide:

1. ``get_available_tools`` patch - filters tools to the active skill's
   allowed-tools whitelist. The upstream sync-wrap fix (3599b570) is detected
   at runtime; when present we skip our own wrap. Clarification
   (``ask_clarification``) is handled natively by DeerFlow's
   ``ClarificationMiddleware`` (always last in ``build_middlewares``), which
   intercepts the tool call and emits a ``human_input`` artifact - no numina
   override needed.
2. ``_apply_subagent_contextvar_patch`` — ``_submit_to_isolated_loop_in_context``
   upstream wraps the ``run_coroutine_threadsafe`` *call* in
   ``context.run(...)``; for parent-set ContextVars this already preserves
   them (context is snapshot-bound at ``copy_context()`` time, verified
   2026-07-24). Numina additionally wraps the coroutine *body*
   (``await context.run(coro_factory)``) to also cover LangGraph runtime
   ContextVars (e.g. ``get_stream_writer()``) whose injection point may not
   be captured by the snapshot. Retained pending an end-to-end ultra-mode
   regression test asserting ``task_started``/``task_completed`` emission.
3. MCP proxy bypass + per-family extensions-config path resolution — Numina
   specific (``trust_env=False`` + ``X-Agent-Token``/``X-Family-Id`` headers
   + coroutine-scoped ContextVar for multi-family isolation).

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
    # Upstream 2.1.0 already fixed make_sync_tool_wrapper (contextvar propagation
    # + RunnableConfig injection) and _find_usage_recorder (CallbackManager unwrap),
    # so those two patches were removed. _apply_subagent_contextvar_patch targets a
    # different call site (_submit_to_isolated_loop_in_context) whose upstream wrap
    # scope differs from ours — kept until a regression test covers ultra-mode events.
    _apply_subagent_contextvar_patch()
    _apply_mcp_proxy_bypass_patch()
    _apply_clarification_artifact_patch()
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
        logger.warning("[sync_tool_patch] langchain_core.messages.HumanMessage not found; skipping")
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
    logger.info("[sync_tool_patch] patched HumanMessage.__init__ to inject ORIGINAL_USER_CONTENT_KEY")


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
        from apps.agent.services.deerflow_adapter.active_skill_context import (
            get_active_skill,
        )
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
        # review_skill_package is a DeerFlow built-in that only works inside
        # DeerFlow's own workspace (requires .skill archives or SKILL.md dirs).
        # In the numina agent workspace it always fails with ValueError and
        # causes the LLM to loop retrying — exclude it from the always-available
        # set so the chat skill never sees it.
        _numina_always_available = ALWAYS_AVAILABLE_BUILTIN_TOOL_NAMES - {
            "review_skill_package",
        }
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
            always_allowed_tool_names=_numina_always_available,
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


def _apply_subagent_contextvar_patch() -> None:
    """Patch ``_submit_to_isolated_loop_in_context`` to run the coroutine body in-context.

    Upstream 2.1.0 (rev ``10890e10``) wraps the ``run_coroutine_threadsafe``
    *call* in ``context.run(lambda: ...)`` rather than the coroutine *body*.
    Empirical probes (2026-07-24) show that for ContextVars set in the parent
    thread before ``copy_context()``, upstream's wrap already preserves them
    inside the coroutine body on the isolated loop thread — the context is
    snapshot-bound at ``copy_context()`` time and travels with the coroutine.
    Under that scenario this patch is a no-op equivalent.

    The patch is retained because the one path NOT covered by the probes is a
    LangGraph runtime ContextVar (e.g. ``get_stream_writer()``) whose injection
    point may not be captured by the ``copy_context()`` snapshot the way a
    plain parent-set ContextVar is. Removing this patch requires a regression
    test that exercises the ultra-mode subagent flow end-to-end and asserts
    ``task_started`` / ``task_completed`` custom events are emitted — which
    needs a LangGraph runtime + mocked LLM and is not yet in place.

    Fix: wrap the coroutine so its body awaits inside ``context.run(...)``,
    guaranteeing every ContextVar read — regardless of injection mechanism —
    resolves against the captured context on the isolated loop thread.
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
        """Patched get_mcp_tools that injects trust_env=False into SSE/HTTP.

        The extensions config path is resolved inside ``ExtensionsConfig.from_file``
        via the patched ``resolve_config_path`` (see
        ``_apply_extensions_config_path_patch``), which consults Numina's per-run
        ContextVar before the process-global env var — so no explicit path needs
        to be passed here.
        """
        extensions_config = ExtensionsConfig.from_file()
        servers_config = build_servers_config(extensions_config)
        if not servers_config:
            _mcp_mod.logger.info("No enabled MCP servers configured")
            return []

        # Inject the no-proxy httpx client factory into every SSE/HTTP server
        # so internal MCP calls bypass system proxy env vars.
        # Also inject X-Agent-Token + X-Family-Id headers — the Numina Backend MCP
        # SSE endpoint (mcp_internal.py:72) requires X-Agent-Token; without it the
        # connection 403s and ALL MCP tools (get_assets/import_assets_batch/...) are
        # unavailable. The worker sets srv["headers"] on the runtime mcp_servers
        # dict, but the MCP client reads from extensions_config (file-based) which
        # has no auth headers — so inject them here from settings + family context.
        from apps.agent.services.runtime.sandbox_provider import (
            get_caller_user_id_context as _get_caller,
        )
        from apps.agent.services.runtime.sandbox_provider import (
            get_family_sandbox_context as _get_family,
        )
        _mcp_family_id = _get_family()
        _mcp_caller_user_id = _get_caller()
        _mcp_agent_token = None
        if _mcp_family_id:
            from packages.security.service_auth.agent_jwt import create_agent_token
            _mcp_agent_token = create_agent_token(_mcp_family_id)
        for _name, cfg in servers_config.items():
            if cfg.get("transport") in ("sse", "http"):
                cfg["httpx_client_factory"] = _no_proxy_httpx_client
                if _mcp_agent_token or _mcp_family_id or _mcp_caller_user_id:
                    existing_headers = dict(cfg.get("headers", {}))
                    if _mcp_agent_token:
                        existing_headers["X-Agent-Token"] = _mcp_agent_token
                    if _mcp_family_id:
                        existing_headers["X-Family-Id"] = _mcp_family_id
                    if _mcp_caller_user_id:
                        existing_headers["X-Caller-User-Id"] = _mcp_caller_user_id
                    cfg["headers"] = existing_headers

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
            # tool_name_prefix=False: MCP tools keep their base names (e.g.
            # ``get_assets``) instead of ``{server_name}_get_assets`` (e.g.
            # ``Numina Backend MCP_get_assets``). Skill ``allowed-tools``
            # declarations use base names, and ``filter_tools_by_skill_allowed_tools``
            # (deerflow/skills/tool_policy.py:65) matches by full name — a prefixed
            # name would never match the base-name allowlist, silently filtering
            # out every business tool (root cause of "all records empty" and
            # asset-report Recursion-100). Numina runs a single MCP server, so
            # there is no cross-server tool-name collision risk from disabling
            # the prefix. Mirrors DeerFlow reference skills (e.g. skill-reviewer)
            # which declare ``allowed-tools`` as unprefixed base names.
            client = MultiServerMCPClient(
                servers_config,
                tool_interceptors=tool_interceptors,
                tool_name_prefix=False,
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
    staleness check, and ``_patched_get_mcp_tools`` — all see the same per-run
    path with no cross-family leakage. An explicit ``config_path`` argument
    still takes precedence (priority 1), preserving the original API contract.
    """
    try:
        from deerflow.config.extensions_config import ExtensionsConfig
    except ImportError:
        logger.warning("[sync_tool_patch] ExtensionsConfig not found; skipping resolve_config_path patch")
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
    logger.info("[sync_tool_patch] patched ExtensionsConfig.resolve_config_path to consult per-run ContextVar before env var")

def _apply_clarification_artifact_patch() -> None:
    """Patch ``_tool_message_event`` + ``_serialize_message`` to preserve ``artifact``.

    DeerFlow's ``ClarificationMiddleware`` stores the ``human_input`` payload
    (question, ``input_mode``, ``options``, ``request_id``) in
    ``ToolMessage.artifact``. Both ``DeerFlowClient._tool_message_event``
    (``messages`` stream mode) and ``_serialize_message`` (``values`` stream
    mode) drop this field, so the frontend never receives the structured
    clarification request - only the formatted question text in ``content``.

    This patch preserves ``artifact`` in both event paths so the frontend can
    use DeerFlow's native ``extractHumanInputRequest`` pattern
    (``message.artifact.human_input``) to render the clarification UI and
    submit the answer as a new message (no LangGraph ``interrupt()``/resume).
    """
    try:
        from deerflow.client import DeerFlowClient
    except ImportError:
        logger.warning("[sync_tool_patch] DeerFlowClient not found; skipping clarification artifact patch")
        return

    _orig_tool_message_event = DeerFlowClient._tool_message_event

    def _patched_tool_message_event(msg):
        event = _orig_tool_message_event(msg)
        artifact = getattr(msg, "artifact", None)
        if artifact is not None:
            event.data["artifact"] = artifact
        return event

    DeerFlowClient._tool_message_event = staticmethod(_patched_tool_message_event)

    _orig_serialize_message = DeerFlowClient._serialize_message

    def _patched_serialize_message(msg):
        d = _orig_serialize_message(msg)
        # Only ToolMessage carries an artifact (ClarificationMiddleware's human_input)
        artifact = getattr(msg, "artifact", None)
        if artifact is not None and d.get("type") == "tool":
            d["artifact"] = artifact
        return d

    DeerFlowClient._serialize_message = staticmethod(_patched_serialize_message)

    logger.info("[sync_tool_patch] patched _tool_message_event + _serialize_message to preserve ToolMessage.artifact (human_input)")


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
    scoped to the call. The patched ``get_mcp_tools`` (see
    ``_apply_mcp_proxy_bypass_patch``) already injects auth headers from
    ContextVars, so no header plumbing is needed here.

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
            # patched version (see _apply_mcp_proxy_bypass_patch) already
            # injects auth headers from ContextVars.
            from deerflow.mcp.tools import get_mcp_tools
            _cache_mod._mcp_tools_cache = _asyncio.run(get_mcp_tools())
            _cache_mod._cache_initialized = True
            _cache_mod._config_path, _cache_mod._config_signature = (
                _cache_mod._current_config_state()
            )
            logger.info(
                "[sync_tool_patch] MCP tools initialized via threading-lock patch: %d tool(s)",
                len(_cache_mod._mcp_tools_cache or []),
            )
        except Exception:
            logger.exception("[sync_tool_patch] MCP tools init failed via threading-lock patch")
            return []
        finally:
            _lazy_init_thread_lock.release()

        return _cache_mod._mcp_tools_cache or []

    _cache_mod.get_cached_mcp_tools = _patched_get_cached_mcp_tools
    logger.info("[sync_tool_patch] patched get_cached_mcp_tools to use threading.Lock (fixes event-loop deadlock in worker threads)")
