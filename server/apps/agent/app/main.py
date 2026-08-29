"""Numina AI Agent 微服务入口。"""

import logging
import os
from contextlib import asynccontextmanager
from pathlib import Path

# Patch MCP SDK's httpx client factory before any imports that use it.
# CRITICAL: httpx defaults trust_env=True, which picks up macOS system proxy settings.
# This causes 503 errors when connecting to SSE endpoints. trust_env=False bypasses
# proxy detection and connects directly to localhost endpoints.
import httpx
import mcp.shared._httpx_utils as _httpx_utils
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from apps.agent.app.config import settings
from apps.agent.app.routers import cache as cache_router
from apps.agent.app.routers import gateway as gateway_router
from apps.agent.core.logging import setup_logging
from apps.agent.routers import import_parse as import_parse_router
from apps.agent.routers import input_polish as input_polish_router
from apps.agent.routers import model_test as model_test_router
from apps.agent.routers import runs_stream as runs_stream_router
from apps.agent.routers import suggest as suggest_router
from apps.agent.routers import threads as threads_router

_original_create_mcp_http_client = _httpx_utils.create_mcp_http_client


def _patched_create_mcp_http_client(
    headers: dict[str, str] | None = None,
    timeout: httpx.Timeout | None = None,
    auth: httpx.Auth | None = None,
) -> httpx.AsyncClient:
    """Patched factory that uses trust_env=False to avoid proxy issues."""
    import logging

    logger = logging.getLogger(__name__)
    logger.debug("[mcp_patch] creating httpx client with trust_env=False")
    return httpx.AsyncClient(
        headers=headers or {},
        timeout=timeout
        or httpx.Timeout(
            _httpx_utils.MCP_DEFAULT_TIMEOUT,
            read=_httpx_utils.MCP_DEFAULT_SSE_READ_TIMEOUT,
        ),
        auth=auth,
        follow_redirects=True,
        trust_env=False,  # CRITICAL: avoid macOS system proxy causing 503 errors
    )


_httpx_utils.create_mcp_http_client = _patched_create_mcp_http_client

if "DEER_FLOW_CONFIG_PATH" not in os.environ:
    os.environ["DEER_FLOW_CONFIG_PATH"] = str(
        Path(__file__).resolve().parent.parent
        / "deerflow_config"
        / "base"
        / "config.yaml"
    )

setup_logging(log_level=settings.LOG_LEVEL, log_dir=settings.LOG_DIR)

# Bridge the per-family DeerFlow AppConfig into the background memory-update
# timer thread (see services/deerflow_adapter/memory_config_bridge.py for why).
# Importing the module installs the patch idempotently at process start, before
# any agent run can enqueue a memory update.
try:
    from apps.agent.services.deerflow_adapter import (
        memory_config_bridge,
    )
except Exception as e:
    logging.getLogger(__name__).warning("memory_config_bridge install failed: %s", e)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    settings.validate_required()
    from apps.agent.app.scheduler import scheduler, setup_schedules
    from apps.agent.core.backend_client import close_shared_client
    from apps.agent.services.audit_logger import setup_audit_logger

    setup_audit_logger()
    setup_schedules()
    scheduler.start()

    # Seed builtin skills: symlink source skill dirs into PathManager's expected data path
    # so that EffectiveConfigBuilder._materialize_skills can find and resolve them.
    from pathlib import Path

    from packages.core import get_path_manager

    pm = get_path_manager()
    builtin_src = Path(__file__).resolve().parent.parent / "skills" / "builtin"
    if builtin_src.is_dir():
        pm.builtin_skills_dir.mkdir(parents=True, exist_ok=True)
        for skill_dir in builtin_src.iterdir():
            if skill_dir.is_dir() and (skill_dir / "SKILL.md").exists():
                link = pm.builtin_skills_dir / skill_dir.name
                import os

                if link.is_symlink():
                    link.unlink()
                if not link.exists():
                    os.symlink(skill_dir, link)

    # Initialise DeerFlow persistence engine (checkpointer only — session metadata
    # is now stored in backend via HTTP). Supports sqlite (default) and postgres
    # via DEERFLOW_DB_URL env var.
    try:
        import os
        from pathlib import Path

        from deerflow.persistence.engine import init_engine

        db_url = os.environ.get("DEERFLOW_DB_URL")
        if db_url:
            # Ensure async-compatible driver — create_async_engine requires
            # asyncpg, not psycopg2.  Mirrors DeerFlow's DatabaseConfig
            # .app_sqlalchemy_url rewrite which we bypass by calling init_engine
            # directly with the raw env var.
            import re as _re
            from urllib.parse import (  # noqa: I001
                parse_qs,
                urlencode,
                urlparse,
                urlunparse,
            )

            if db_url.startswith("postgresql"):
                db_url = _re.sub(
                    r"^postgresql(\+\w+)?://", "postgresql+asyncpg://", db_url
                )
                # asyncpg does not recognise psycopg2-style ``sslmode`` query
                # param — convert it to the ``ssl`` param asyncpg understands.
                parsed = urlparse(db_url)
                qs = parse_qs(parsed.query)
                if "sslmode" in qs:
                    sslmode = qs.pop("sslmode")[0]
                    # asyncpg ssl values: "prefer", "require", "verify-ca",
                    # "verify-full".  Map common psycopg2 sslmode values.
                    _ssl_map = {
                        "disable": "prefer",
                        "allow": "prefer",
                        "prefer": "prefer",
                        "require": "require",
                        "verify-ca": "verify-ca",
                        "verify-full": "verify-full",
                    }
                    qs["ssl"] = [_ssl_map.get(sslmode, "require")]
                    rebuilt = parsed._replace(query=urlencode(qs, doseq=True))
                    db_url = urlunparse(rebuilt)
            await init_engine(
                backend="postgres" if db_url.startswith("postgres") else "sqlite",
                url=db_url,
            )
        else:
            # Default: local SQLite using settings.DEERFLOW_DB_PATH
            db_path = settings.DEERFLOW_DB_PATH
            Path(db_path).parent.mkdir(parents=True, exist_ok=True)
            await init_engine(
                backend="sqlite",
                url=f"sqlite+aiosqlite:///{db_path}",
                sqlite_dir=str(Path(db_path).parent),
            )
    except Exception as _e:
        import logging

        logging.getLogger(__name__).warning("DeerFlow engine init failed: %s", _e)

    # Initialize AsyncSqliteSaver checkpointer for LangGraph conversation persistence.
    # Must be done in async context (lifespan) so the async context manager is entered properly.
    try:
        from apps.agent.services.deerflow_adapter.family_adapter_cache import (
            async_init_checkpointer,
        )

        await async_init_checkpointer()
    except Exception as _e:
        import logging

        logging.getLogger(__name__).warning("AsyncSqliteSaver init failed: %s", _e)

    # Apply DeerFlow sync-tool compatibility patch: the pinned harness (rev
    # 4538c322) predates upstream fix 3599b570, so the built-in ``task`` tool
    # (subagent delegation, used in ultra mode) lacks the sync wrapper that
    # MCP tools already get. Without this, ultra mode fails with
    # "StructuredTool does not support sync invocation" on the sync stream path.
    try:
        from apps.agent.services.deerflow_adapter.sync_tool_patch import (
            apply_sync_tool_patches,
        )

        apply_sync_tool_patches()
    except Exception as _e:
        import logging

        logging.getLogger(__name__).warning("sync_tool_patch failed: %s", _e)

    # [Copied from DeerFlow Reference] — initialise runtime (StreamBridge + RunManager)
    # [Integrated with Numina Multi-Tenant] — shared singletons for all families
    from apps.agent.services.runtime.lifespan import init_runtime, shutdown_runtime

    await init_runtime(app)

    # U7: Register SIGTERM handler for graceful shutdown
    # Guard: signal.signal only works in the main thread (tests run lifespan
    # in a worker thread via TestClient).
    import signal
    import threading

    if threading.current_thread() is threading.main_thread():

        def sigterm_handler(signum, frame):
            """Handle SIGTERM by marking shutdown state.

            The actual shutdown logic runs in lifespan's shutdown phase.
            This handler just sets the flag so routers can reject new tasks.
            """
            import logging
            logging.getLogger(__name__).info("[SIGTERM] Received SIGTERM, marking shutdown state")
            from apps.agent.services.runtime.shutdown_state import mark_shutting_down
            mark_shutting_down()

        signal.signal(signal.SIGTERM, sigterm_handler)

    yield

    # [Copied from DeerFlow Reference] — drain in-flight runs BEFORE checkpointer close
    # so each settled run can flush its final checkpoint while resources are open.
    # Shutdown
    await shutdown_runtime(app)
    scheduler.shutdown(wait=False)
    await close_shared_client()  # Close shared backend connection pool
    try:
        from apps.agent.services.deerflow_adapter.family_adapter_cache import (
            close_shared_checkpointer,
        )

        await close_shared_checkpointer()
    except Exception:
        pass
    try:
        from deerflow.persistence.engine import close_engine

        await close_engine()
    except Exception:
        pass


app = FastAPI(
    title="Numina AI Agent",
    version="0.1.0",
    lifespan=lifespan,
    # 不对外暴露 docs（内部服务）
    docs_url=None if settings.ENVIRONMENT == "production" else "/docs",
    redoc_url=None,
)

# CORS middleware for frontend → agent calls (suggestions endpoint)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://localhost:5174",
        "http://127.0.0.1:5173",
    ],
    allow_credentials=True,
    allow_methods=["POST", "OPTIONS"],
    allow_headers=["X-Family-Id", "X-Agent-Token", "X-User-Id", "Content-Type"],
)


app.include_router(suggest_router.router)
app.include_router(cache_router.router)
app.include_router(gateway_router.router)
app.include_router(import_parse_router.router)
app.include_router(input_polish_router.router)
app.include_router(model_test_router.router)
app.include_router(threads_router.router)
app.include_router(runs_stream_router.router)


@app.get("/health")
def health():
    return {"status": "ok", "service": "numina-agent"}
