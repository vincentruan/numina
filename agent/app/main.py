"""Numina AI Agent 微服务入口。"""

from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.config import settings
from core.logging import setup_logging

setup_logging()


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    settings.validate_required()
    from app.scheduler import scheduler, setup_schedules
    from core.backend_client import close_shared_client

    setup_schedules()
    scheduler.start()

    yield

    # Shutdown
    scheduler.shutdown(wait=False)
    await close_shared_client()  # Close shared backend connection pool


app = FastAPI(
    title="Numina AI Agent",
    version="0.1.0",
    lifespan=lifespan,
    # 不对外暴露 docs（内部服务）
    docs_url=None if settings.ENVIRONMENT == "production" else "/docs",
    redoc_url=None,
)


from app.routers import cache as cache_router
from routers import alerts as alerts_router
from routers import allocation as allocation_router
from routers import chat as chat_router
from routers import disposal as disposal_router
from routers import import_parse as import_parse_router
from routers import liability as liability_router
from routers import report as report_router
from routers import spending_leak as spending_leak_router
from routers import suggest as suggest_router
from routers import model_test as model_test_router
from routers import time_machine as time_machine_router

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
app.include_router(model_test_router.router)


@app.get("/health")
def health():
    return {"status": "ok", "service": "numina-agent"}
