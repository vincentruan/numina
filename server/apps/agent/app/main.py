"""Numina AI Agent 微服务入口。"""

# Patch MCP SDK's httpx client factory before any imports that use it.
# CRITICAL: httpx defaults trust_env=True, which picks up macOS system proxy settings.
# This causes 503 errors when connecting to SSE endpoints. trust_env=False bypasses
# proxy detection and connects directly to localhost endpoints.
import httpx
import mcp.shared._httpx_utils as _httpx_utils

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

# noqa: E402 — imports after patch are intentional
import os  # noqa: E402
from contextlib import asynccontextmanager  # noqa: E402
from pathlib import Path  # noqa: E402

from fastapi import FastAPI  # noqa: E402

from apps.agent.app.config import settings  # noqa: E402
from apps.agent.core.logging import setup_logging  # noqa: E402

if "DEER_FLOW_CONFIG_PATH" not in os.environ:
    os.environ["DEER_FLOW_CONFIG_PATH"] = str(
        Path(__file__).resolve().parent.parent
        / "deerflow_config"
        / "base"
        / "config.yaml"
    )

setup_logging()

# Bridge the per-family DeerFlow AppConfig into the background memory-update
# timer thread (see services/deerflow_adapter/memory_config_bridge.py for why).
# Importing the module installs the patch idempotently at process start, before
# any agent run can enqueue a memory update.
from apps.agent.services.deerflow_adapter import memory_config_bridge  # noqa: F401,E402


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
            # Postgres or explicit URL (cluster deployments)
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

    # [Copied from DeerFlow Reference] — initialise runtime (StreamBridge + RunManager)
    # [Integrated with Numina Multi-Tenant] — shared singletons for all families
    from apps.agent.services.runtime.lifespan import init_runtime, shutdown_runtime

    await init_runtime(app)

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
from fastapi.middleware.cors import CORSMiddleware  # noqa: E402

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


# Router imports after app definition — noqa: E402
from apps.agent.app.routers import cache as cache_router  # noqa: E402
from apps.agent.app.routers import gateway as gateway_router  # noqa: E402
from apps.agent.routers import alerts as alerts_router  # noqa: E402
from apps.agent.routers import allocation as allocation_router  # noqa: E402
from apps.agent.routers import capabilities as capabilities_router  # noqa: E402
from apps.agent.routers import disposal as disposal_router  # noqa: E402
from apps.agent.routers import import_parse as import_parse_router  # noqa: E402
from apps.agent.routers import liability as liability_router  # noqa: E402
from apps.agent.routers import model_test as model_test_router  # noqa: E402
from apps.agent.routers import report as report_router  # noqa: E402
from apps.agent.routers import runs_stream as runs_stream_router  # noqa: E402
from apps.agent.routers import spending_leak as spending_leak_router  # noqa: E402
from apps.agent.routers import suggest as suggest_router  # noqa: E402
from apps.agent.routers import threads as threads_router  # noqa: E402
from apps.agent.routers import time_machine as time_machine_router  # noqa: E402

app.include_router(report_router.router)
app.include_router(suggest_router.router)
app.include_router(alerts_router.router)
app.include_router(disposal_router.router)
app.include_router(liability_router.router)
app.include_router(allocation_router.router)
app.include_router(spending_leak_router.router)
app.include_router(time_machine_router.router)
app.include_router(cache_router.router)
app.include_router(gateway_router.router)
app.include_router(import_parse_router.router)
app.include_router(capabilities_router.router)
app.include_router(model_test_router.router)
app.include_router(threads_router.router)
app.include_router(runs_stream_router.router)


@app.get("/health")
def health():
    return {"status": "ok", "service": "numina-agent"}
