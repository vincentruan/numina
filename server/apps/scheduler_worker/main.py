"""scheduler_worker — standalone APScheduler + worker process.

Runs all 7 background jobs independently from the backend API process.
Exposes /health for Docker healthcheck.

Start:
    cd server && uv run uvicorn apps.scheduler_worker.main:app --host 0.0.0.0 --port 8002
"""

from contextlib import asynccontextmanager

from fastapi import FastAPI, Response

from packages.core.logging import get_logger, setup_logging
from packages.core.settings import settings

logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Start scheduler on startup, shut it down on exit."""
    setup_logging(
        log_level=settings.LOG_LEVEL,
        log_dir=settings.LOG_DIR,
    )
    logger.info("scheduler_worker starting up")

    from apps.scheduler_worker.scheduler import scheduler, setup_all_jobs  # noqa: PLC0415

    setup_all_jobs()
    scheduler.start()
    logger.info(f"APScheduler started with {len(scheduler.get_jobs())} jobs")

    yield

    logger.info("scheduler_worker shutting down")
    scheduler.shutdown(wait=True)
    logger.info("APScheduler stopped")


app = FastAPI(
    title="Numina Scheduler Worker",
    description="Standalone APScheduler process for Numina background jobs",
    version="1.0.0",
    lifespan=lifespan,
)


@app.get("/health")
def health(response: Response) -> dict:
    """Docker healthcheck endpoint."""
    from apps.scheduler_worker.scheduler import scheduler  # noqa: PLC0415

    jobs = scheduler.get_jobs()
    if not scheduler.running:
        response.status_code = 503
    return {
        "status": "ok" if scheduler.running else "degraded",
        "scheduler_running": scheduler.running,
        "job_count": len(jobs),
        "jobs": [
            {
                "id": job.id,
                "name": job.name,
                "next_run": str(job.next_run_time) if job.next_run_time else None,
            }
            for job in jobs
        ],
    }
