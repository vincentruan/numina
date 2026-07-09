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
    try:
        source = inspect.getsource(_orig_get_available_tools)
        return_section = source.rsplit("return", 1)[-1]
        if "_ensure_sync_invocable_tool" in return_section:
            logger.debug("[sync_tool_patch] upstream fix already present; skipping")
            _patched = True
            _apply_mcp_proxy_bypass_patch()
            return
    except Exception:
        pass

    def _patched_get_available_tools(*args, **kwargs):
        tools = _orig_get_available_tools(*args, **kwargs)
        return [_ensure_sync_invocable_tool(t) for t in tools]

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
    _apply_mcp_proxy_bypass_patch()


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
