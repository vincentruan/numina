"""Numina AI Agent 微服务入口。"""

from contextlib import asynccontextmanager

from fastapi import FastAPI

from apps.agent.app.config import settings
from apps.agent.core.logging import setup_logging

setup_logging()


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    settings.validate_required()
    from apps.agent.app.scheduler import scheduler, setup_schedules
    from apps.agent.core.backend_client import close_shared_client

    setup_schedules()
    scheduler.start()

    # Initialise DeerFlow persistence engine (checkpointer only — session metadata
    # is now stored in backend via HTTP). Supports sqlite (default) and postgres
    # via DEERFLOW_DB_URL env var.
    try:
        import os

        from deerflow.persistence.engine import init_engine

        db_url = os.environ.get("DEERFLOW_DB_URL")
        if db_url:
            # Postgres or explicit URL (cluster deployments)
            await init_engine(backend="postgres" if db_url.startswith("postgres") else "sqlite", url=db_url)
        else:
            # Default: local SQLite for single-node deployments
            db_dir = ".deer-flow/data"
            db_path = os.path.join(db_dir, "deerflow.db")
            await init_engine(
                backend="sqlite",
                url=f"sqlite+aiosqlite:///{db_path}",
                sqlite_dir=db_dir,
            )
    except Exception as _e:
        import logging
        logging.getLogger(__name__).warning("DeerFlow engine init failed: %s", _e)

    yield

    # Shutdown
    scheduler.shutdown(wait=False)
    await close_shared_client()  # Close shared backend connection pool
    try:
        from apps.agent.services.deerflow_adapter.family_adapter_cache import (
            close_shared_checkpointer,
        )
        close_shared_checkpointer()
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


from apps.agent.app.routers import cache as cache_router
from apps.agent.routers import alerts as alerts_router
from apps.agent.routers import allocation as allocation_router
from apps.agent.routers import capabilities as capabilities_router
from apps.agent.routers import chat as chat_router
from apps.agent.routers import disposal as disposal_router
from apps.agent.routers import import_parse as import_parse_router
from apps.agent.routers import liability as liability_router
from apps.agent.routers import model_test as model_test_router
from apps.agent.routers import report as report_router
from apps.agent.routers import sessions as sessions_router
from apps.agent.routers import spending_leak as spending_leak_router
from apps.agent.routers import suggest as suggest_router
from apps.agent.routers import time_machine as time_machine_router

app.include_router(report_router.router)
app.include_router(suggest_router.router)
app.include_router(alerts_router.router)
app.include_router(disposal_router.router)
app.include_router(liability_router.router)
app.include_router(allocation_router.router)
app.include_router(chat_router.router)
app.include_router(spending_leak_router.router)
app.include_router(time_machine_router.router)
app.include_router(cache_router.router)
app.include_router(import_parse_router.router)
app.include_router(capabilities_router.router)
app.include_router(model_test_router.router)
app.include_router(sessions_router.router)


@app.get("/health")
def health():
    return {"status": "ok", "service": "numina-agent"}
