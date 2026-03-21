import logging
import os
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.config import settings
from app.database import Base, SessionLocal, engine
from app.seed.categories import seed_categories
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

from app.routers import auth, assets, liabilities, categories, tags, dashboard, family, wishes
from app.routers import export as export_router
from app.routers import import_ as import_router
from app.routers import activities as activities_router
from app.routers import upload


logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        seed_categories(db)
        # Auto-generate daily snapshots for all families
        try:
            auto_generate_daily_snapshots(db)
        except Exception as e:
            logger.warning(f"自动快照生成失败: {e}")
    finally:
        db.close()

    if settings.ENVIRONMENT == "production" and settings.CORS_ORIGINS == ["*"]:
        logger.warning("生产环境 CORS_ORIGINS 设置为 ['*']，建议配置具体域名。")

    yield


app = FastAPI(title="Numina - 家庭资产可视化", version="1.0.0", lifespan=lifespan)

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
app.include_router(activities_router.router, prefix="/api/v1")
app.include_router(upload.router, prefix="/api/v1")

# Serve uploaded files
upload_dir = Path(os.getenv("UPLOAD_DIR", "./data/uploads"))
upload_dir.mkdir(parents=True, exist_ok=True)
app.mount("/uploads", StaticFiles(directory=str(upload_dir)), name="uploads")


@app.get("/api/health")
def health():
    return {"status": "ok"}
