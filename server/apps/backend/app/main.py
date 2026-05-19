import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.middleware.base import BaseHTTPMiddleware

from apps.backend.app.config import settings
from apps.backend.app.core.logging_config import setup_logging
from apps.backend.app.database import SessionLocal, engine
from apps.backend.app.error_handlers import (
    app_error_handler,
    http_exception_handler,
    storage_error_handler,
    validation_error_handler,
)
from apps.backend.app.errors.exceptions import AppError
from apps.backend.app.middleware.family_context import FamilyContextMiddleware
from apps.backend.app.middleware.rate_limit import RateLimitMiddleware
from apps.backend.app.middleware.request_id import RequestIDMiddleware
from apps.backend.app.models.activity import Activity  # noqa: F401
from apps.backend.app.models.ai_allocation_target import (
    AIAllocationTarget,  # noqa: F401
)
from apps.backend.app.models.ai_asset_alert import AIAssetAlert  # noqa: F401
from apps.backend.app.models.ai_chat_message import AIChatMessage  # noqa: F401
from apps.backend.app.models.ai_chat_session import AIChatSession  # noqa: F401
from apps.backend.app.models.ai_disposal_suggestion import (
    AIDisposalSuggestion,  # noqa: F401
)
from apps.backend.app.models.ai_report import AIReport  # noqa: F401
from apps.backend.app.models.ai_spending_leak import AISpendingLeak  # noqa: F401
from apps.backend.app.models.ai_ws_ticket import AIWsTicket  # noqa: F401
from apps.backend.app.models.asset import Asset  # noqa: F401
from apps.backend.app.models.blind_box_config import BlindBoxConfig  # noqa: F401
from apps.backend.app.models.blind_box_draw import BlindBoxDraw  # noqa: F401
from apps.backend.app.models.blind_box_gift import BlindBoxGift  # noqa: F401
from apps.backend.app.models.bonus_draw import BonusDraw  # noqa: F401
from apps.backend.app.models.cached_file import CachedFile  # noqa: F401
from apps.backend.app.models.category import Category  # noqa: F401
from apps.backend.app.models.category_financial_default import (
    CategoryFinancialDefault,  # noqa: F401
)
from apps.backend.app.models.child_milestone import ChildMilestone  # noqa: F401
from apps.backend.app.models.child_wish import ChildWish  # noqa: F401
from apps.backend.app.models.chore import ChoreInstance, ChoreTemplate  # noqa: F401
from apps.backend.app.models.coin_transaction import CoinTransaction  # noqa: F401
from apps.backend.app.models.currency import Currency  # noqa: F401
from apps.backend.app.models.exchange_rate import ExchangeRate  # noqa: F401
from apps.backend.app.models.family import Family  # noqa: F401
from apps.backend.app.models.file_remote_location import (
    FileRemoteLocation,  # noqa: F401
)
from apps.backend.app.models.liability import Liability  # noqa: F401
from apps.backend.app.models.notification_channel import (
    NotificationChannel,  # noqa: F401
)
from apps.backend.app.models.notification_config import NotificationConfig  # noqa: F401
from apps.backend.app.models.notification_subscription import (
    NotificationSubscription,  # noqa: F401
)
from apps.backend.app.models.payment_record import PaymentRecord  # noqa: F401
from apps.backend.app.models.reminder import Reminder  # noqa: F401
from apps.backend.app.models.revoked_token import RevokedToken  # noqa: F401
from apps.backend.app.models.security_audit_log import SecurityAuditLog  # noqa: F401
from apps.backend.app.models.snapshot import AssetSnapshot  # noqa: F401
from apps.backend.app.models.storage_backend import StorageBackend  # noqa: F401
from apps.backend.app.models.sync_event import SyncEvent  # noqa: F401
from apps.backend.app.models.tag import Tag  # noqa: F401

# Import all models so Base.metadata knows about them
from apps.backend.app.models.user import User  # noqa: F401
from apps.backend.app.models.valuation import AssetValuation  # noqa: F401
from apps.backend.app.models.wish import Wish  # noqa: F401
from apps.backend.app.responses import EnvelopeResponse
from apps.backend.app.routers import activities as activities_router
from apps.backend.app.routers import ai_alerts as ai_alerts_router
from apps.backend.app.routers import ai_allocation as ai_allocation_router
from apps.backend.app.routers import ai_capabilities as ai_capabilities_router
from apps.backend.app.routers import ai_chat as ai_chat_router
from apps.backend.app.routers import ai_config as ai_config_router
from apps.backend.app.routers import ai_disposal as ai_disposal_router
from apps.backend.app.routers import ai_internal as ai_internal_router
from apps.backend.app.routers import ai_liability as ai_liability_router
from apps.backend.app.routers import ai_mcp as ai_mcp_router
from apps.backend.app.routers import ai_report as ai_report_router
from apps.backend.app.routers import ai_skills as ai_skills_router
from apps.backend.app.routers import ai_spending_leaks as ai_spending_leaks_router
from apps.backend.app.routers import ai_suggest as ai_suggest_router
from apps.backend.app.routers import ai_tasks as ai_tasks_router
from apps.backend.app.routers import ai_time_machine as ai_time_machine_router
from apps.backend.app.routers import (
    assets,
    auth,
    captcha,
    categories,
    dashboard,
    family,
    liabilities,
    tags,
    upload,
    wishes,
)
from apps.backend.app.routers import assets_analysis as assets_analysis_router
from apps.backend.app.routers import blind_box as blind_box_router
from apps.backend.app.routers import calendar as calendar_router
from apps.backend.app.routers import challenge_grants as challenge_grants_router
from apps.backend.app.routers import child_blind_box as child_blind_box_router
from apps.backend.app.routers import child_wishes as child_wishes_router
from apps.backend.app.routers import children as children_router
from apps.backend.app.routers import chores as chores_router
from apps.backend.app.routers import coins as coins_router
from apps.backend.app.routers import currencies as currencies_router
from apps.backend.app.routers import device as device_router
from apps.backend.app.routers import export as export_router
from apps.backend.app.routers import files as files_router
from apps.backend.app.routers import import_ as import_router
from apps.backend.app.routers import import_report as import_report_router
from apps.backend.app.routers import milestones as milestones_router
from apps.backend.app.routers import (
    notification_channels as notification_channels_router,
)
from apps.backend.app.routers import notification_config as notification_config_router
from apps.backend.app.routers import notifications as notifications_router
from apps.backend.app.routers import reminders as reminders_router
from apps.backend.app.routers import treasures as treasures_router
from apps.backend.app.seed.currencies import seed_currencies
from apps.backend.app.seed.invitation_codes import seed_invitation_codes
from apps.backend.app.seed.storage_backends import seed_storage_backends
from apps.backend.app.services.db_migrate import run_schema_migration
from apps.backend.app.services.exchange_rate import ExchangeRateService
from apps.backend.app.services.snapshot import auto_generate_daily_snapshots
from apps.backend.app.services.storage.base import StorageError

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Initialize Snowflake ID generator before any DB operations
    from apps.backend.app.utils.snowflake import init_snowflake
    init_snowflake()

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

    # Run schema migration with distributed locking (handles all DB types)
    logger.info("执行数据库结构对齐检查...")
    migration_summary = run_schema_migration(engine)
    if migration_summary.get("tables_created"):
        logger.info(f"新建表: {migration_summary['tables_created']}")
    if migration_summary.get("columns_added"):
        logger.info(f"新增字段: {migration_summary['columns_added']}")
    if migration_summary.get("indexes_added"):
        logger.info(f"新增索引: {migration_summary['indexes_added']}")
    if migration_summary.get("errors"):
        logger.warning(f"迁移错误: {migration_summary['errors']}")
    if not any([
        migration_summary.get("tables_created"),
        migration_summary.get("columns_added"),
        migration_summary.get("indexes_added"),
        migration_summary.get("errors"),
    ]):
        logger.info("数据库结构已完整，无需迁移")

    db = SessionLocal()
    try:
        seed_currencies(db)
        seed_invitation_codes(db)
        seed_storage_backends(db)
        from apps.backend.app.seed.category_financial_defaults import (
            seed_category_financial_defaults,
        )
        seed_category_financial_defaults(db)
        # Auto-generate daily snapshots for all families
        try:
            auto_generate_daily_snapshots(db)
        except Exception as e:
            logger.warning(f"自动快照生成失败: {e}")
        # Fetch exchange rates immediately if none exist
        try:
            from apps.backend.app.models.exchange_rate import ExchangeRate

            has_rates = db.query(ExchangeRate).first() is not None
            if not has_rates:
                logger.info("首次启动，立即获取汇率数据...")
                ExchangeRateService.fetch_and_store_rates(db)
        except Exception as e:
            logger.warning(f"初始汇率获取失败: {e}")
    finally:
        db.close()

    # CORS validation is now enforced in config.py

    # Security logging is now configured via setup_logging()
    if settings.ENABLE_SECURITY_LOGGING:
        logger.info("安全日志已启用（使用统一日志配置）")

    yield


app = FastAPI(
    title="Numina - 家庭资产可视化",
    version="1.0.0",
    lifespan=lifespan,
    default_response_class=EnvelopeResponse,
    redirect_slashes=False,
)

app.add_exception_handler(AppError, app_error_handler)
app.add_exception_handler(RequestValidationError, validation_error_handler)
app.add_exception_handler(StarletteHTTPException, http_exception_handler)
app.add_exception_handler(StorageError, storage_error_handler)


# Catch-all exception handler for unhandled errors
async def catch_all_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    logger.exception(f"Unhandled exception on {request.url.path}: {exc}")
    request_id = getattr(request.state, "request_id", "unknown")
    # Include traceback only in development for debugging
    traceback_info = None
    if settings.ENVIRONMENT == "development":
        import traceback
        traceback_info = traceback.format_exc()
    return JSONResponse(
        status_code=500,
        content={
            "code": "INTERNAL_ERROR",
            "message": str(exc) if settings.ENVIRONMENT == "development" else "Internal server error",
            "traceback": traceback_info,
            "data": None,
            "request_id": request_id,
        },
    )


app.add_exception_handler(Exception, catch_all_exception_handler)


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Add security headers to all responses (defense in depth).

    These headers provide additional protection even when Nginx/Cloudflare
    handles the primary security layer.
    """

    async def dispatch(self, request, call_next):
        try:
            response = await call_next(request)

            # Skip for health check (minimal overhead)
            if request.url.path == "/api/health":
                return response

            # X-Content-Type-Options: Prevent MIME type sniffing
            response.headers["X-Content-Type-Options"] = "nosniff"

            # X-Frame-Options: Prevent clickjacking
            response.headers["X-Frame-Options"] = "DENY"

            # X-XSS-Protection: Legacy XSS filter (modern browsers use CSP)
            response.headers["X-XSS-Protection"] = "1; mode=block"

            # Referrer-Policy: Control referrer information
            response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"

            # Permissions-Policy: Disable unnecessary browser features
            response.headers["Permissions-Policy"] = (
                "geolocation=(), microphone=(), camera=()"
            )

            # Content-Security-Policy: XSS protection
            # Note: Vue SPA requires 'unsafe-inline' for styles/scripts
            # This is a trade-off: CSP strictness vs SPA functionality
            # Future: use nonce-based CSP for stricter protection
            # In development, allow cross-origin API calls (e.g. Vite dev server → backend)
            connect_src = "'self' http://localhost:8000 http://127.0.0.1:8000" if settings.ENVIRONMENT == "development" else "'self'"
            csp_policy = (
                "default-src 'self'; "
                "script-src 'self' 'unsafe-inline'; "  # Vue SPA needs inline scripts
                "style-src 'self' 'unsafe-inline'; "  # shareImage.ts needs inline styles
                "img-src 'self' data: https:; "  # Allow base64 and HTTPS images
                "font-src 'self'; "
                f"connect-src {connect_src}; "
                "frame-ancestors 'none'; "  # Equivalent to X-Frame-Options: DENY
                "base-uri 'self'; "
                "form-action 'self'; "
            )
            response.headers["Content-Security-Policy"] = csp_policy

            # HSTS: Force HTTPS (only in production with HTTPS)
            # Note: Cloudflare handles HTTPS, but this adds defense in depth
            if settings.ENVIRONMENT == "production":
                response.headers["Strict-Transport-Security"] = (
                    "max-age=31536000; includeSubDomains"
                )

            # Cache-Control: Prevent sensitive data caching
            # Only apply to API endpoints (static files handled by Nginx)
            # Exclude stable read-only endpoints that intentionally use private, max-age=300
            # to allow browser caching (data changes rarely and is family-scoped).
            _CACHEABLE_API_PATHS = {
                "/api/v1/categories",
                "/api/v1/family/members",
                "/api/v1/family/info",
                "/api/v1/family/",
            }
            if (
                request.url.path.startswith("/api/")
                and request.url.path not in _CACHEABLE_API_PATHS
            ):
                response.headers["Cache-Control"] = (
                    "no-store, no-cache, must-revalidate"
                )

            return response
        except Exception as e:
            logger.exception(
                f"SecurityHeadersMiddleware error on {request.url.path}: {e}"
            )
            raise


# Add rate limiting middleware (first to execute on request)
app.add_middleware(RateLimitMiddleware)

# Inject family_id from JWT into request.state for all authenticated routes
app.add_middleware(FamilyContextMiddleware)

# Add security headers middleware (last to modify response)
app.add_middleware(SecurityHeadersMiddleware)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(RequestIDMiddleware)

app.include_router(auth.router, prefix="/api/v1")
app.include_router(assets.router, prefix="/api/v1")
app.include_router(liabilities.router, prefix="/api/v1")
app.include_router(categories.router, prefix="/api/v1")
app.include_router(tags.router, prefix="/api/v1")
app.include_router(dashboard.router, prefix="/api/v1")
app.include_router(family.router, prefix="/api/v1")
app.include_router(export_router.router, prefix="/api/v1")
app.include_router(import_router.router, prefix="/api/v1")
app.include_router(import_report_router.router, prefix="/api/v1")
app.include_router(wishes.router, prefix="/api/v1")
app.include_router(currencies_router.router, prefix="/api/v1")
app.include_router(activities_router.router, prefix="/api/v1")
app.include_router(upload.router, prefix="/api/v1")
app.include_router(captcha.router, prefix="/api/v1")
app.include_router(files_router.router, prefix="/api/v1")
# Register more specific AI routes first to avoid prefix conflicts
app.include_router(ai_capabilities_router.router, prefix="/api/v1")
app.include_router(ai_config_router.router, prefix="/api/v1")
app.include_router(ai_internal_router.router, prefix="/api/v1")
app.include_router(ai_report_router.router, prefix="/api/v1")
app.include_router(ai_suggest_router.router, prefix="/api/v1")
app.include_router(ai_alerts_router.router, prefix="/api/v1")
app.include_router(ai_spending_leaks_router.router, prefix="/api/v1")
app.include_router(ai_disposal_router.router, prefix="/api/v1")
app.include_router(ai_liability_router.router, prefix="/api/v1")
app.include_router(ai_allocation_router.router, prefix="/api/v1")
app.include_router(ai_chat_router.router, prefix="/api/v1")
app.include_router(ai_chat_router.sessions_router, prefix="/api/v1")
app.include_router(children_router.router, prefix="/api/v1")
app.include_router(chores_router.router, prefix="/api/v1")
app.include_router(coins_router.router, prefix="/api/v1")
app.include_router(child_wishes_router.router, prefix="/api/v1")
app.include_router(milestones_router.router, prefix="/api/v1")
app.include_router(notifications_router.router, prefix="/api/v1")
app.include_router(treasures_router.router, prefix="/api/v1")
app.include_router(calendar_router.router, prefix="/api/v1")
app.include_router(blind_box_router.router, prefix="/api/v1")
app.include_router(child_blind_box_router.router, prefix="/api/v1")
app.include_router(challenge_grants_router.router, prefix="/api/v1")
app.include_router(challenge_grants_router.child_router, prefix="/api/v1")
app.include_router(device_router.router, prefix="/api/v1")
app.include_router(assets_analysis_router.router, prefix="/api/v1")
app.include_router(ai_tasks_router.router, prefix="/api/v1")
app.include_router(ai_time_machine_router.router, prefix="/api/v1")
app.include_router(notification_channels_router.router, prefix="/api/v1")
app.include_router(notification_config_router.router, prefix="/api/v1")
app.include_router(reminders_router.router, prefix="/api/v1")
app.include_router(ai_mcp_router.router, prefix="/api/v1")
app.include_router(ai_skills_router.router, prefix="/api/v1")

# Serve uploaded files
# Serve uploaded files — mount only the uploads subtree, not the entire workspace
# (workspace also contains chat JSONL which must not be publicly accessible)
upload_static_dir = Path(settings.UPLOAD_DIR) / "uploads"
upload_static_dir.mkdir(parents=True, exist_ok=True)
app.mount("/uploads", StaticFiles(directory=str(upload_static_dir)), name="uploads")


@app.get("/api/health")
def health():
    return JSONResponse({"status": "ok"})
