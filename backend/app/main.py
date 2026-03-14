from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.database import Base, SessionLocal, engine
from app.seed.categories import seed_categories

# Import all models so Base.metadata knows about them
from app.models.user import User  # noqa: F401
from app.models.family import Family  # noqa: F401
from app.models.category import Category  # noqa: F401
from app.models.asset import Asset  # noqa: F401
from app.models.liability import Liability  # noqa: F401
from app.models.snapshot import AssetSnapshot  # noqa: F401
from app.models.tag import Tag  # noqa: F401

from app.routers import auth, assets, liabilities, categories, tags, dashboard, family


@asynccontextmanager
async def lifespan(app: FastAPI):
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        seed_categories(db)
    finally:
        db.close()
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


@app.get("/api/health")
def health():
    return {"status": "ok"}
