import logging
import os
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.config import settings
from app.core.logging_config import setup_logging
from app.database import Base, SessionLocal, engine
from app.middleware.rate_limit import RateLimitMiddleware
from app.scheduler import fetch_rates_job, scheduler, setup_exchange_rate_schedule
from app.seed.categories import seed_categories
from app.seed.currencies import seed_currencies
from app.services.exchange_rate import ExchangeRateService
from app.services.snapshot import auto_generate_daily_snapshots

# Import all models so Base.metadata knows about them
from app.models.user import User  # noqa: F401
from app.models.family import Family  # noqa: F401
from app.models.category import Category  # noqa: F401
from app.models.asset import Asset  # noqa: F401
from app.models.liability import Liability  # noqa: F401
from app.models.snapshot import AssetSnapshot  # noqa: F401
from app.models.tag import Tag  # noqa: F401
from app.models.wish import Wish  # noqa: F401
from app.models.payment_record import PaymentRecord  # noqa: F401
from app.models.valuation import AssetValuation  # noqa: F401
from app.models.activity import Activity  # noqa: F401
from app.models.exchange_rate import ExchangeRate  # noqa: F401
from app.models.currency import Currency  # noqa: F401

from app.routers import auth, assets, liabilities, categories, tags, dashboard, family, wishes
from app.routers import currencies as currencies_router
from app.routers import export as export_router
from app.routers import import_ as import_router
from app.routers import activities as activities_router
from app.routers import upload


logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Initialize unified logging configuration
    setup_logging(
        log_level=settings.LOG_LEVEL,
        log_dir=settings.LOG_DIR,
        log_format=settings.LOG_FORMAT,
        max_bytes=settings.LOG_MAX_BYTES,
        backup_count=settings.LOG_BACKUP_COUNT,
        rotation_mode=settings.LOG_ROTATION_MODE,
        retention_days=settings.LOG_RETENTION_DAYS,
    )
    logger.info("统一日志配置已初始化")

    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        seed_categories(db)
        seed_currencies(db)
        # Auto-generate daily snapshots for all families
        try:
            auto_generate_daily_snapshots(db)
        except Exception as e:
            logger.warning(f"自动快照生成失败: {e}")
        # Fetch exchange rates immediately if none exist
        try:
            from app.models.exchange_rate import ExchangeRate
            has_rates = db.query(ExchangeRate).first() is not None
            if not has_rates:
                logger.info("首次启动，立即获取汇率数据...")
                ExchangeRateService.fetch_and_store_rates(db)
        except Exception as e:
            logger.warning(f"初始汇率获取失败: {e}")
    finally:
        db.close()

    if settings.ENVIRONMENT == "production" and settings.CORS_ORIGINS == ["*"]:
        logger.warning("生产环境 CORS_ORIGINS 设置为 ['*']，建议配置具体域名。")

    # Security logging is now configured via setup_logging()
    if settings.ENABLE_SECURITY_LOGGING:
        logger.info("安全日志已启用（使用统一日志配置）")

    try:
        setup_exchange_rate_schedule()
        scheduler.start()
        logger.info("APScheduler 已启动")
    except Exception as e:
        logger.error(f"APScheduler 启动失败：{e}")

    yield

    scheduler.shutdown()
    logger.info("APScheduler 已停止")


app = FastAPI(title="Numina - 家庭资产可视化", version="1.0.0", lifespan=lifespan)

# Add rate limiting middleware (before CORS)
app.add_middleware(RateLimitMiddleware)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router, prefix="/api/v1")
app.include_router(assets.router, prefix="/api/v1")
app.include_router(liabilities.router, prefix="/api/v1")
app.include_router(categories.router, prefix="/api/v1")
app.include_router(tags.router, prefix="/api/v1")
app.include_router(dashboard.router, prefix="/api/v1")
app.include_router(family.router, prefix="/api/v1")
app.include_router(export_router.router, prefix="/api/v1")
app.include_router(import_router.router, prefix="/api/v1")
app.include_router(wishes.router, prefix="/api/v1")
app.include_router(currencies_router.router, prefix="/api/v1")
app.include_router(activities_router.router, prefix="/api/v1")
app.include_router(upload.router, prefix="/api/v1")

# Serve uploaded files
upload_dir = Path(os.getenv("UPLOAD_DIR", "./data/uploads"))
upload_dir.mkdir(parents=True, exist_ok=True)
app.mount("/uploads", StaticFiles(directory=str(upload_dir)), name="uploads")


@app.get("/api/health")
def health():
    return {"status": "ok"}
