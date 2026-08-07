"""按家庭缓存的 DeerFlowAdapter — 支持动态注入家庭级 AI 配置。

方案 B 实现：
- 每家庭一个 DeerFlowClient 实例（LRU 缓存）
- 动态生成临时配置文件，注入家庭的 api_key/model_id
- 缓存失效：家庭禁用 AI 或配置变更时清理

Session memory injection:
- A shared SqliteSaver checkpointer is passed explicitly to every DeerFlowClient.
- Without an explicit checkpointer, DeerFlowClient falls back to get_checkpointer()
  which may return InMemorySaver (lost on restart) or a stale singleton after
  reload_app_config() resets the global config for a different family.
- All families share one checkpointer instance; DeerFlow namespaces state by
  thread_id so family isolation is maintained at the conversation level.

Model entry construction
------------------------
The per-family ``models[0]`` block is built by
``packages.core.model_entry.build_model_entry`` — the single source of truth
for provider class selection, thinking routing, max_tokens resolution, and
Responses API wiring. That module documents the per-provider contracts
(DeepSeek R1, OpenAI-compatible, native OpenAI, Anthropic extended thinking).

This module's ``_generate_temp_config`` composes that model entry with
Numina-specific, non-provider concerns — per-family memory isolation,
sandbox, skills, MCP, and web_search tool injection — then writes a
temporary YAML config for DeerFlow to consume.

DeerFlow runtime transformations
--------------------------------
We deliberately do NOT inject ``stream_usage=True`` or normalize
``api_base → base_url`` here. DeerFlow's ``create_chat_model()`` factory
handles both generically:

- ``stream_usage``: ``factory.py:304-306`` auto-injects for any model class
  whose ``model_fields`` includes ``stream_usage``.
- ``api_base``: ``factory.py:45-73`` (``_normalize_openai_base_url``)
  renames ``api_base → base_url`` for ``BaseChatOpenAI`` subclasses that
  don't declare ``api_base`` themselves (``ChatDeepSeek`` does, so it is
  left alone — matches the vendor SDK).

The family-scoped ``stream_chunk_timeout`` override (DB ``timeout_seconds``)
is a Numina value-add on top of DeerFlow's 240s default and is emitted by
``build_model_entry``.
"""

import atexit
import contextlib
import logging
import os
import re
import shutil
import tempfile
import threading
from collections import OrderedDict
from pathlib import Path
from typing import Any, cast

from deerflow.client import DeerFlowClient
from deerflow.config.app_config import reload_app_config

from packages.core.model_entry import build_model_entry

logger = logging.getLogger(__name__)


def _inject_memory(
    config: dict[str, Any],
    family_id: str,
    memory_enabled: bool,
) -> None:
    """Inject per-family memory path isolation into config (in-place).

    Each family gets its own ``{AGENT_DATA_DIR}/{family_id}/agent/memory/``
    directory so DeerMem facts don't leak across families. When
    ``memory_enabled=False`` (fixed-flow agents like asset-report), injection
    and write are both disabled.
    """
    from apps.agent.app.config import settings

    memory_path = Path(settings.AGENT_DATA_DIR) / family_id / "agent" / "memory"
    memory_path.mkdir(parents=True, exist_ok=True)
    if "memory" not in config:
        config["memory"] = {}
    config["memory"]["manager_class"] = "deermem"
    backend_config = config["memory"].get("backend_config") or {}
    backend_config["storage_path"] = str(memory_path)
    config["memory"]["backend_config"] = backend_config

    if not memory_enabled:
        config["memory"]["enabled"] = False
        config["memory"]["injection_enabled"] = False


def _inject_sandbox(config: dict[str, Any]) -> None:
    """Inject Numina's family-scoped sandbox provider (in-place)."""
    if "sandbox" not in config:
        config["sandbox"] = {
            "use": "apps.agent.services.runtime.sandbox_provider:NuminaLocalSandboxProvider"
        }


def _inject_skills(config: dict[str, Any]) -> None:
    """Inject host-resolved skills.path into config (in-place).

    The base config ships a container path that doesn't resolve on the host
    dev machine, so we override with the agent's builtin skills root.
    """
    _skills_root = Path(__file__).resolve().parent.parent.parent / "skills" / "builtin"
    config.setdefault("skills", {})
    config["skills"]["path"] = str(_skills_root)


def _inject_mcp(
    config: dict[str, Any],
    mcp_servers: list[dict[str, Any]] | None,
) -> None:
    """Inject MCP servers list into config (in-place)."""
    if mcp_servers:
        config["mcp_servers"] = mcp_servers


def _inject_token_budget(config: dict[str, Any]) -> None:
    """Inject per-run token budget limits into config (in-place).

    Enables DeerFlow's native ``TokenBudgetMiddleware`` (added by
    ``build_middlewares`` when ``token_budget.enabled=True``).  Previously
    this was done by injecting ``TokenBudgetMiddleware`` into
    ``custom_middlewares``, but that caused a duplicate-name AssertionError
    because DeerFlow's factory also adds one with the same ``.name``.
    """
    if "token_budget" not in config:
        config["token_budget"] = {}
    config["token_budget"]["enabled"] = True
    config["token_budget"].setdefault("max_tokens", 200_000)
    config["token_budget"].setdefault("warn_threshold", 0.8)
    config["token_budget"].setdefault("hard_stop_threshold", 1.0)


def _inject_web_search(
    config: dict[str, Any],
    ai_config: dict[str, Any],
    mcp_servers: list[dict[str, Any]] | None,
    web_search_mcp_servers: list[dict[str, Any]],
) -> None:
    """Inject web_search tool configuration (in-place).

    Priority: native providers > MCP fallback. When no native providers are
    configured, the web_search tool is removed and MCP servers (if any) take
    over via the ``mcp_servers`` config key.
    """
    web_search_providers = ai_config.get("web_search_providers", [])

    if web_search_providers:
        first_provider = web_search_providers[0]
        provider_class = first_provider.get("provider_class", "")
        provider_api_key = first_provider.get("api_key", "")
        provider_max_results = first_provider.get("max_results", 5)

        if not provider_class:
            logger.warning(
                "[deerflow_config] web_search provider_class is empty; "
                "removing web_search tool",
            )
            tools = config.get("tools", [])
            config["tools"] = [t for t in tools if t.get("name") != "web_search"]
        else:
            tools = config.get("tools", [])
            for tool in tools:
                if tool.get("name") == "web_search":
                    tool["use"] = provider_class
                    tool["api_key"] = provider_api_key
                    tool["max_results"] = provider_max_results
                    break

            # Inject web_fetch tool (Jina AI-based page content fetcher)
            tools = config.get("tools", [])
            if not any(t.get("name") == "web_fetch" for t in tools):
                tools.append(
                    {
                        "name": "web_fetch",
                        "group": "web",
                        "use": "deerflow.community.jina_ai_tools:web_fetch_tool",
                        "timeout": 10,
                        "trust_env": False,
                    }
                )
                config["tools"] = tools
    else:
        # No native providers — remove web_search tool
        tools = config.get("tools", [])
        config["tools"] = [
            t for t in tools if t.get("name") not in ("web_search", "web_fetch")
        ]

        # Inject web search MCP servers if available
        if web_search_mcp_servers and not mcp_servers:
            config["mcp_servers"] = web_search_mcp_servers
        elif web_search_mcp_servers and mcp_servers:
            existing_servers = config.get("mcp_servers", [])
            existing_names = {s.get("name") for s in existing_servers}
            for ws_server in web_search_mcp_servers:
                if ws_server.get("name") not in existing_names:
                    existing_servers.append(ws_server)
            config["mcp_servers"] = existing_servers


def _write_extensions_config(
    temp_dir: Path,
    mcp_servers: list[dict[str, Any]],
) -> None:
    """Write extensions_config.json for DeerFlow's ExtensionsConfig.from_file().

    DeerFlow reads MCP server configs from this file (not from config.yaml).
    The DEER_FLOW_EXTENSIONS_CONFIG_PATH env var is set in adapter._produce()
    to point here, under _init_lock serialization.
    """
    import json as _json

    mcp_servers_dict = {}
    for srv in mcp_servers:
        name = srv.get("name", "default")
        mcp_servers_dict[name] = {
            "type": srv.get("transport", "sse"),
            "url": srv.get("url", ""),
            "headers": srv.get("headers", {}),
            "enabled": True,
            # tool_name_prefix=False: MCP tools keep their base names (e.g.
            # ``get_assets``) instead of ``{server_name}_get_assets`` (e.g.
            # ``Numina Backend MCP_get_assets``). Skill ``allowed-tools``
            # declarations use base names, and ``filter_tools_by_skill_allowed_tools``
            # (deerflow/skills/tool_policy.py:65) matches by full name — a prefixed
            # name would never match the base-name allowlist, silently filtering
            # out every business tool (root cause of "all records empty" and
            # asset-report Recursion-100). DeerFlow honours this per-server via
            # ``McpServerConfig.tool_name_prefix`` (native get_mcp_tools:696).
            "tool_name_prefix": False,
        }
    extensions_data = {"mcpServers": mcp_servers_dict}
    extensions_path = temp_dir / "extensions_config.json"
    with open(extensions_path, "w", encoding="utf-8") as f:
        _json.dump(extensions_data, f, ensure_ascii=False)


# Safe ID pattern for family_id validation (prevents path traversal)
_SAFE_ID_PATTERN = re.compile(r"^[A-Za-z0-9_\-]+$")

# LRU 缓存：最多 100 个家庭
_MAX_CACHE_SIZE = 100
# Values are either (DeerFlowClient, Path) for a live entry, or None as a
# placeholder while a new client is being initialised (prevents TOCTOU races
# where two threads both pass the size check and both insert).
_adapter_cache: OrderedDict[
    tuple[str, str, bool, bool, str, str, tuple[int, ...], bool, frozenset[str] | None],
    tuple[DeerFlowClient, Path] | None,
] = OrderedDict()
# Thread lock to prevent concurrent cache mutations (works in sync context)
_cache_lock = threading.Lock()
# Per-key init lock: serialises reload_app_config + DeerFlowClient() for the
# same (family_id, config_id) so concurrent requests don't interleave global
# DeerFlow config state.
_init_lock = threading.Lock()

# Shared checkpointer singleton — created once, reused by all DeerFlowClient instances.
# Guarded by _checkpointer_lock to prevent double-initialisation under concurrency.
_shared_checkpointer: Any = None
_checkpointer_lock = threading.Lock()
_checkpointer_ctx: Any = (
    None  # open context manager keeping the SqliteSaver connection alive
)
_checkpointer_pool: Any = None  # open psycopg connection pool for PostgresSaver


async def async_init_checkpointer(db_path: str | None = None) -> None:
    """Initialize the shared LangGraph checkpointer at startup.

    Supports two backends selected by the DEERFLOW_DB_URL env var:
    - ``postgres://…`` / ``postgresql://…`` → AsyncPostgresSaver (cluster deployments)
    - unset or ``sqlite://…``              → AsyncSqliteSaver (local dev)

    Must be called from an async context (FastAPI lifespan). This properly
    enters the async context manager so checkpoint state persists across
    restarts.

    Args:
        db_path: Optional override for the SQLite checkpointer DB path. If not
            provided, reads from settings.DEERFLOW_DB_PATH. Ignored when
            DEERFLOW_DB_URL points at a Postgres backend.
    """
    global _shared_checkpointer, _checkpointer_ctx, _checkpointer_pool

    import os as _os
    import re as _re

    db_url = _os.environ.get("DEERFLOW_DB_URL")

    with _checkpointer_lock:
        if _shared_checkpointer is not None:
            return

        try:
            if db_url and db_url.startswith("postgres"):
                # ── Postgres backend (AsyncPostgresSaver) ──────────────
                from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
                from psycopg_pool import AsyncConnectionPool

                # psycopg_pool expects a raw PostgreSQL URL, not a SQLAlchemy
                # dialect URL like ``postgresql+asyncpg://...``. Strip the
                # ``+<driver>`` suffix if present.
                pg_conninfo = _re.sub(
                    r"^postgresql\+\w+://",
                    "postgresql://",
                    db_url,
                )

                _checkpointer_pool = AsyncConnectionPool(
                    conninfo=pg_conninfo,
                    kwargs={"autocommit": True},
                    min_size=2,
                    max_size=10,
                    open=False,  # defer to await .open() — avoids psycopg_pool
                    # RuntimeWarning about constructor-time auto-open
                )
                await _checkpointer_pool.open()
                _shared_checkpointer = AsyncPostgresSaver(
                    conn=cast(Any, _checkpointer_pool),
                )
                await _shared_checkpointer.setup()
                logger.info(
                    "[deerflow_cache] shared checkpointer: AsyncPostgresSaver(%s)",
                    db_url,
                )
            else:
                # ── SQLite backend (AsyncSqliteSaver) ─────────────────
                from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver

                if db_path is None:
                    from apps.agent.app.config import settings

                    db_path = settings.DEERFLOW_DB_PATH

                _os.makedirs(
                    _os.path.dirname(db_path) if _os.path.dirname(db_path) else ".",
                    exist_ok=True,
                )

                _checkpointer_ctx = AsyncSqliteSaver.from_conn_string(db_path)
                _shared_checkpointer = await _checkpointer_ctx.__aenter__()
                logger.info(
                    "[deerflow_cache] shared checkpointer: AsyncSqliteSaver(%s)",
                    db_path,
                )
        except ImportError as _ie:
            from langgraph.checkpoint.memory import InMemorySaver

            _shared_checkpointer = InMemorySaver()
            logger.warning(
                "[deerflow_cache] checkpoint backend not installed (%s); "
                "using InMemorySaver — multi-turn memory will not survive restarts",
                _ie,
            )
        except Exception as e:
            from langgraph.checkpoint.memory import InMemorySaver

            _shared_checkpointer = InMemorySaver()
            logger.warning(
                "[deerflow_cache] checkpointer async init failed (%s); falling back to InMemorySaver",
                e,
            )


def _get_shared_checkpointer(base_config_dir: str | None = None):
    """Return the shared LangGraph checkpointer (must be pre-initialized).

    This function returns the checkpointer that was initialized by
    async_init_checkpointer() at startup. If not yet initialized, it
    falls back to InMemorySaver.

    Note: For proper persistence, call async_init_checkpointer() in the
    FastAPI lifespan before yielding.
    """
    global _shared_checkpointer

    with _checkpointer_lock:
        if _shared_checkpointer is not None:
            return _shared_checkpointer

        # Not yet initialized — use InMemorySaver as fallback
        from langgraph.checkpoint.memory import InMemorySaver

        _shared_checkpointer = InMemorySaver()
        logger.warning(
            "[deerflow_cache] checkpointer not async-initialized; using InMemorySaver"
        )
        return _shared_checkpointer


def _read_checkpointer_path(base_config_dir: str) -> str:
    """Return the checkpointer DB path from settings.

    Uses settings.DEERFLOW_DB_PATH which derives from DATA_ROOT.
    """
    from apps.agent.app.config import settings

    return settings.DEERFLOW_DB_PATH


async def close_shared_checkpointer() -> None:
    """Close the shared checkpointer connection. Call at process shutdown."""
    global _shared_checkpointer, _checkpointer_ctx, _checkpointer_pool
    with _checkpointer_lock:
        if _checkpointer_ctx is not None:
            with contextlib.suppress(Exception):
                await _checkpointer_ctx.__aexit__(None, None, None)
            _checkpointer_ctx = None
        if _checkpointer_pool is not None:
            with contextlib.suppress(Exception):
                await _checkpointer_pool.close()
            _checkpointer_pool = None
        _shared_checkpointer = None


def _mcp_cache_key(mcp_servers: list[dict[str, Any]] | None) -> str:
    """Return a short hash fingerprint for an mcp_servers list, or '' if empty."""
    if not mcp_servers:
        return ""
    import hashlib
    import json

    blob = json.dumps(mcp_servers, sort_keys=True, ensure_ascii=False)
    return hashlib.sha1(blob.encode("utf-8")).hexdigest()[:8]


def _generate_temp_config(
    base_config_dir: str,
    ai_config: dict[str, Any],
    family_id: str = "",
    mcp_servers: list[dict[str, Any]] | None = None,
    memory_enabled: bool = True,
) -> Path:
    """生成临时配置文件，动态注入家庭的 AI 配置到 models 列表。

    Args:
        base_config_dir: 基础配置目录路径
        ai_config: 家庭的 AI 配置（api_key, ai_provider, ai_model_id 等）
        family_id: 家庭 ID（用于 memory 存储路径隔离）
        mcp_servers: MCP server 列表（注入到 config.yaml + extensions_config.json）
        memory_enabled: Whether DeerMem injection + write are enabled for this
            agent (read from ai_agents.memory_enabled via AgentRegistry by the
            caller). Fixed-flow agents (asset-report) pass False to be
            stateless — each run fetches fresh data instead of accumulating
            history that pollutes later runs (plan U4 Open Question: DeerMem).

    Returns:
        临时配置文件的路径

    Implementation notes — what this function does NOT do (DeerFlow factory handles it):
      - ``stream_usage=True`` injection: DeerFlow factory.py:304-306 auto-injects
        for any model class whose ``model_fields`` includes ``stream_usage``.
      - ``api_base → base_url`` normalization: DeerFlow factory.py:45-73
        (``_normalize_openai_base_url``) handles this for ``BaseChatOpenAI``
        subclasses that don't declare ``api_base`` themselves.
    """
    import yaml  # type: ignore[import-untyped]

    # Validate family_id to prevent path traversal
    if family_id and not _SAFE_ID_PATTERN.match(family_id):
        raise ValueError(
            f"Invalid family_id: {family_id!r}. Must match pattern: {_SAFE_ID_PATTERN.pattern}"
        )

    base_config_path = Path(base_config_dir) / "base" / "config.yaml"
    if not base_config_path.exists():
        raise FileNotFoundError(f"Base config not found: {base_config_path}")

    with open(base_config_path, encoding="utf-8") as f:
        config = yaml.safe_load(f)

    # Build the declarative model entry (provider class + thinking + max_tokens)
    config["models"] = [build_model_entry(ai_config)]
    config.pop("llm", None)

    # Numina-specific injections (no DeerFlow equivalents)
    _inject_memory(config, family_id, memory_enabled)
    _inject_sandbox(config)
    _inject_skills(config)
    _inject_mcp(config, mcp_servers)
    _inject_token_budget(config)
    web_search_mcp = ai_config.get("web_search_mcp_servers", [])
    _inject_web_search(config, ai_config, mcp_servers, web_search_mcp)

    # Write temp YAML config
    temp_dir = Path(tempfile.mkdtemp(prefix="deerflow_config_"))
    temp_config_path = temp_dir / "config.yaml"
    with open(temp_config_path, "w", encoding="utf-8") as f:
        yaml.dump(
            config, f, allow_unicode=True, default_flow_style=False, sort_keys=False
        )
    os.chmod(temp_config_path, 0o600)

    # Write extensions_config.json for MCP server discovery
    if mcp_servers:
        _write_extensions_config(temp_dir, mcp_servers)

    return temp_config_path


def get_family_adapter(
    family_id: str,
    ai_config: dict[str, Any],
    base_config_dir: str | None = None,
    timeout_seconds: int = 120,
    subagent_enabled: bool = False,
    plan_mode: bool = False,
    mcp_servers: list[dict[str, Any]] | None = None,
    agent_name: str | None = None,
    middlewares: list[Any] | None = None,
    memory_enabled: bool = True,
    available_skills: set[str] | None = None,
) -> tuple[DeerFlowClient, Path]:
    """获取家庭的 DeerFlowClient 实例（带缓存）。

    Each client receives the shared checkpointer so multi-turn conversation
    state is persisted across requests. DeerFlow namespaces state by thread_id,
    so different families' conversations remain isolated even with a shared
    checkpointer instance.

    Cache key is (family_id, config_id, subagent_enabled, plan_mode, mcp_key,
    agent_name, middlewares_key, memory_enabled, available_skills_key) — different
    flag combinations create distinct client instances since these are init-time
    parameters on DeerFlowClient. agent_name is in the key because it selects a
    distinct DeerMem memory bucket (per (agent_name, user_id)) — an asset-report
    client must not share a chat client's memory. middlewares is in the key (as
    id() tuple) because a client with a custom middleware must not be reused for
    a chat run that should not emit that middleware's events. available_skills
    is in the key because a client with a different skill whitelist must not be
    reused for a run with a different set of enabled skills (U3: slash activation).

    Thread safety:
    - _cache_lock guards all reads/writes to _adapter_cache.
    - A None placeholder is inserted under _cache_lock before releasing it,
      so concurrent threads that miss the cache see the placeholder and wait
      on _init_lock rather than both starting initialisation.
    - _init_lock serialises reload_app_config() + DeerFlowClient() so that
      concurrent requests for different families don't interleave global
      DeerFlow config state.

    Args:
        family_id: 家庭 ID
        ai_config: 家庭的 AI 配置
        base_config_dir: 基础配置目录，默认为 agent/deerflow_config
        timeout_seconds: DeerFlow 超时时间
        available_skills: Optional set of skill names to make available for slash
            activation. If None (default), all scanned skills are available. U3:
            the worker fetches the family's enabled custom skills and passes them
            here so DeerFlow's SkillActivationMiddleware enforces the whitelist.

    Returns:
        DeerFlowClient 实例
    """
    if base_config_dir is None:
        base_config_dir = os.path.join(
            os.path.dirname(__file__), "..", "..", "deerflow_config"
        )

    config_id: str = ai_config.get("config_id", "")
    # middlewares are unhashable objects; key by their id() tuple so a client
    # built with a custom middleware never collides with a no-middleware
    # chat client. (Both are module-singleton or per-pipeline lists, so id()
    # is stable across calls within a process.)
    middlewares_key = tuple(id(m) for m in middlewares) if middlewares else ()
    # available_skills is a set (unhashable); key by frozenset so a client with
    # a different skill whitelist never collides (U3: slash activation).
    available_skills_key = (
        frozenset(available_skills) if available_skills is not None else None
    )
    cache_key: tuple[
        str, str, bool, bool, str, str, tuple[int, ...], bool, frozenset[str] | None
    ] = (
        family_id,
        config_id,
        subagent_enabled,
        plan_mode,
        _mcp_cache_key(mcp_servers),
        agent_name or "",
        middlewares_key,
        memory_enabled,
        available_skills_key,
    )

    # Fast path: return cached client
    with _cache_lock:
        entry = _adapter_cache.get(cache_key)
        if entry is not None:
            _adapter_cache.move_to_end(cache_key)
            logger.debug(
                "[deerflow_cache] reuse cached adapter for family=%s config_id=%s subagent=%s plan=%s",
                family_id,
                config_id,
                subagent_enabled,
                plan_mode,
            )
            return entry

        # Reserve the slot with a placeholder to prevent concurrent initialisations
        # for the same key (TOCTOU fix). Also evict the oldest entry if at capacity.
        if len(_adapter_cache) >= _MAX_CACHE_SIZE:
            oldest_key, oldest_entry = _adapter_cache.popitem(last=False)
            if oldest_entry is not None:
                _, oldest_config_path = oldest_entry
                with contextlib.suppress(Exception):
                    shutil.rmtree(oldest_config_path.parent, ignore_errors=True)
            logger.debug("[deerflow_cache] evicted adapter for key=%s", oldest_key)

        _adapter_cache[cache_key] = None  # placeholder

    # Serialise reload_app_config() + DeerFlowClient() to prevent concurrent
    # threads from interleaving global DeerFlow config state. File I/O for
    # _generate_temp_config happens outside this lock to minimise contention.
    # memory_enabled is read by the async caller (worker) via AgentRegistry and
    # threaded down as a bool — get_family_adapter is sync (runs inside the
    # adapter's ThreadPoolExecutor), so it cannot await the registry itself.
    temp_config_path = _generate_temp_config(
        base_config_dir,
        ai_config,
        family_id=family_id,
        mcp_servers=mcp_servers,
        memory_enabled=memory_enabled,
    )

    # Obtain the shared checkpointer before reload_app_config() so the
    # checkpointer DB path is read from the base config, not the per-family
    # temp config (initialised exactly once).
    checkpointer = _get_shared_checkpointer(base_config_dir)

    try:
        with _init_lock:
            # Re-check: another thread may have completed init for this key
            # while we were waiting on _init_lock.
            with _cache_lock:
                entry = _adapter_cache.get(cache_key)
                if entry is not None:
                    _adapter_cache.move_to_end(cache_key)
                    # Clean up the temp config we generated but won't use
                    with contextlib.suppress(Exception):
                        shutil.rmtree(temp_config_path.parent, ignore_errors=True)
                    return entry

            # Set DEER_FLOW_CONFIG_PATH inside the init lock so concurrent
            # threads for different families don't overwrite each other's path.
            # DeerFlowClient.__init__ calls get_app_config() which uses this
            # env var to resolve the config file path.
            prev_config_path = os.environ.get("DEER_FLOW_CONFIG_PATH")
            os.environ["DEER_FLOW_CONFIG_PATH"] = str(temp_config_path)
            try:
                reload_app_config(str(temp_config_path))
                client = DeerFlowClient(
                    config_path=str(temp_config_path),
                    checkpointer=checkpointer,
                    model_name="main",  # Use explicit model name to avoid config.models[0] IndexError
                    # Init-time: provider CAPABILITY (can this model think at all?).
                    # Per-request: orchestrator passes thinking_enabled= to stream()
                    # via **kwargs, which overrides this default per-call. See HARNESS_API.md OD-4.
                    thinking_enabled=bool(ai_config.get("thinking_supported", False)),
                    subagent_enabled=subagent_enabled,
                    plan_mode=plan_mode,
                    agent_name=agent_name,
                    middlewares=middlewares,
                    available_skills=available_skills,  # U3: slash activation whitelist
                )
            finally:
                # Restore previous value (or remove if it wasn't set)
                if prev_config_path is not None:
                    os.environ["DEER_FLOW_CONFIG_PATH"] = prev_config_path
                else:
                    os.environ.pop("DEER_FLOW_CONFIG_PATH", None)

        with _cache_lock:
            stored_entry: tuple[DeerFlowClient, Path] = (client, temp_config_path)
            _adapter_cache[cache_key] = stored_entry

        logger.info(
            "[deerflow_cache] created new adapter for family=%s config_id=%s model=%s",
            family_id,
            config_id,
            ai_config.get("ai_model_id"),
        )
        return stored_entry
    except Exception as e:
        # Remove placeholder and clean up temp config on failure
        with _cache_lock:
            if _adapter_cache.get(cache_key) is None:
                _adapter_cache.pop(cache_key, None)
        with contextlib.suppress(Exception):
            shutil.rmtree(temp_config_path.parent, ignore_errors=True)
        raise RuntimeError(
            f"Failed to initialize DeerFlowClient for family={family_id} config_id={config_id}: {e}"
        ) from e


def _atexit_cleanup() -> None:
    """Clean up all cached adapters and temp config dirs at process exit."""
    with contextlib.suppress(Exception):
        clear_cache()


atexit.register(_atexit_cleanup)


def invalidate_family_adapter(family_id: str) -> None:
    """清理家庭的所有缓存实例（按 family_id 批量清除所有 config_id 条目）。

    Args:
        family_id: 家庭 ID
    """
    with _cache_lock:
        keys_to_remove = [k for k in _adapter_cache if k[0] == family_id]
        for key in keys_to_remove:
            entry = _adapter_cache.pop(key)
            if entry is not None:
                _, config_path = entry
                with contextlib.suppress(Exception):
                    shutil.rmtree(config_path.parent, ignore_errors=True)
            logger.info(
                "[deerflow_cache] invalidated adapter for family=%s config_id=%s",
                family_id,
                key[1],
            )


def invalidate_family_adapter_cache(
    family_id: str, config_id: str | None = None
) -> None:
    """清理家庭的缓存实例。

    Args:
        family_id: 家庭 ID
        config_id: 供应商配置 ID。若提供则只清除该条目；若为 None 则清除该家庭所有条目。
    """
    with _cache_lock:
        if config_id is not None:
            # Remove all 4-tuple entries matching (family_id, config_id, *, *)
            keys_to_remove = [
                k for k in _adapter_cache if k[0] == family_id and k[1] == config_id
            ]
            for key in keys_to_remove:
                entry = _adapter_cache.pop(key)
                if entry is not None:
                    _, config_path = entry
                    with contextlib.suppress(Exception):
                        shutil.rmtree(config_path.parent, ignore_errors=True)
                logger.info(
                    "[deerflow_cache] invalidated adapter for family=%s config_id=%s flags=%s",
                    family_id,
                    config_id,
                    key[2:],
                )
        else:
            keys_to_remove = [k for k in _adapter_cache if k[0] == family_id]
            for key in keys_to_remove:
                entry = _adapter_cache.pop(key)
                if entry is not None:
                    _, config_path = entry
                    with contextlib.suppress(Exception):
                        shutil.rmtree(config_path.parent, ignore_errors=True)
                logger.info(
                    "[deerflow_cache] invalidated adapter for family=%s config_id=%s",
                    family_id,
                    key[1],
                )


def clear_cache() -> None:
    """清理所有缓存实例。"""
    with _cache_lock:
        for _key, entry in list(_adapter_cache.items()):
            if entry is not None:
                _, config_path = entry
                with contextlib.suppress(Exception):
                    shutil.rmtree(config_path.parent, ignore_errors=True)
        _adapter_cache.clear()
        logger.info("[deerflow_cache] cleared all cached adapters")


def get_cache_stats() -> dict[str, int]:
    """获取缓存统计信息。"""
    with _cache_lock:
        return {
            "cached_families": len(_adapter_cache),
            "max_size": _MAX_CACHE_SIZE,
        }
