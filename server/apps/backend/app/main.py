import logging
import os
import secrets
import time
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from apps.backend.app.bootstrap import run_bootstrap
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

# Import all models so Base.metadata knows about them
from apps.backend.app.models.activity import Activity
from apps.backend.app.models.ai_chat_message import AIChatMessage
from apps.backend.app.models.ai_chat_session import AIChatSession
from apps.backend.app.models.ai_report import AIReport
from apps.backend.app.models.asset import Asset
from apps.backend.app.models.blind_box_config import BlindBoxConfig
from apps.backend.app.models.blind_box_draw import BlindBoxDraw
from apps.backend.app.models.blind_box_gift import BlindBoxGift
from apps.backend.app.models.bonus_draw import BonusDraw
from apps.backend.app.models.cached_file import CachedFile
from apps.backend.app.models.category import Category
from apps.backend.app.models.category_financial_default import (
    CategoryFinancialDefault,
)
from apps.backend.app.models.child_milestone import ChildMilestone
from apps.backend.app.models.child_wish import ChildWish
from apps.backend.app.models.chore import ChoreInstance, ChoreTemplate
from apps.backend.app.models.coin_transaction import CoinTransaction
from apps.backend.app.models.currency import Currency
from apps.backend.app.models.exchange_rate import ExchangeRate
from apps.backend.app.models.family import Family
from apps.backend.app.models.family_setting import FamilySetting
from apps.backend.app.models.file_remote_location import (
    FileRemoteLocation,
)
from apps.backend.app.models.liability import Liability
from apps.backend.app.models.literacy_badge import (
    LiteracyBadge,
    LiteracyBadgeDefinition,
)
from apps.backend.app.models.literacy_report import LiteracyWeeklyReport
from apps.backend.app.models.literacy_scenario import (
    LiteracyScenario,
    LiteracyScenarioTemplate,
)
from apps.backend.app.models.manifesto import (
    FamilyManifesto,
    ManifestoFeedback,
    ManifestoSignature,
    ManifestoVersion,
)
from apps.backend.app.models.notification_channel import (
    NotificationChannel,
)
from apps.backend.app.models.notification_config import NotificationConfig
from apps.backend.app.models.notification_subscription import (
    NotificationSubscription,
)
from apps.backend.app.models.payment_record import PaymentRecord
from apps.backend.app.models.reminder import Reminder
from apps.backend.app.models.revoked_token import RevokedToken
from apps.backend.app.models.security_audit_log import SecurityAuditLog
from apps.backend.app.models.snapshot import AssetSnapshot
from apps.backend.app.models.storage_backend import StorageBackend
from apps.backend.app.models.sync_event import SyncEvent
from apps.backend.app.models.tag import Tag
from apps.backend.app.models.user import User
from apps.backend.app.models.user_setting import UserSetting
from apps.backend.app.models.valuation import AssetValuation
from apps.backend.app.models.wish import Wish
from apps.backend.app.responses import EnvelopeResponse
from apps.backend.app.routers import activities as activities_router
from apps.backend.app.routers import admin_ai_extraction as admin_ai_extraction_router
from apps.backend.app.routers import admin_audit_logs as admin_audit_logs_router
from apps.backend.app.routers import ai_agents as ai_agents_router
from apps.backend.app.routers import ai_agents_internal as ai_agents_internal_router
from apps.backend.app.routers import ai_asr as ai_asr_router
from apps.backend.app.routers import ai_chat as ai_chat_router
from apps.backend.app.routers import ai_config as ai_config_router
from apps.backend.app.routers import ai_context as ai_context_router
from apps.backend.app.routers import ai_finance_coach as ai_finance_coach_router
from apps.backend.app.routers import ai_input_polish as ai_input_polish_router
from apps.backend.app.routers import ai_internal as ai_internal_router
from apps.backend.app.routers import ai_literacy_report as ai_literacy_report_router
from apps.backend.app.routers import ai_mcp as ai_mcp_router
from apps.backend.app.routers import ai_report as ai_report_router
from apps.backend.app.routers import ai_skills as ai_skills_router
from apps.backend.app.routers import ai_suggest as ai_suggest_router
from apps.backend.app.routers import ai_tasks as ai_tasks_router
from apps.backend.app.routers import ai_threads as ai_threads_router
from apps.backend.app.routers import ai_time_machine as ai_time_machine_router
from apps.backend.app.routers import ai_web_search as ai_web_search_router
from apps.backend.app.routers import ai_wish_advice as ai_wish_advice_router
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
from apps.backend.app.routers import child_manifesto as child_manifesto_router
from apps.backend.app.routers import child_wishes as child_wishes_router
from apps.backend.app.routers import children as children_router
from apps.backend.app.routers import chores as chores_router
from apps.backend.app.routers import coins as coins_router
from apps.backend.app.routers import currencies as currencies_router
from apps.backend.app.routers import device as device_router
from apps.backend.app.routers import export as export_router
from apps.backend.app.routers import family_config as family_config_router
from apps.backend.app.routers import files as files_router
from apps.backend.app.routers import import_ as import_router
from apps.backend.app.routers import import_report as import_report_router
from apps.backend.app.routers import literacy_child as literacy_child_router
from apps.backend.app.routers import literacy_parent as literacy_parent_router
from apps.backend.app.routers import manifesto as manifesto_router
from apps.backend.app.routers import mcp_internal as mcp_internal_router
from apps.backend.app.routers import milestones as milestones_router
from apps.backend.app.routers import (
    notification_channels as notification_channels_router,
)
from apps.backend.app.routers import notification_config as notification_config_router
from apps.backend.app.routers import reminders as reminders_router
from apps.backend.app.routers import storage_backend as storage_backend_router
from apps.backend.app.routers import treasures as treasures_router
from apps.backend.app.routers import uploads as uploads_serve_router
from apps.backend.app.routers import user_config as user_config_router
from apps.backend.app.services.db_migrate import run_schema_migration
from apps.backend.app.services.exchange_rate import ExchangeRateService
from apps.backend.app.services.snapshot import auto_generate_daily_snapshots
from apps.backend.app.services.storage.base import StorageError

logger = logging.getLogger(__name__)


def _wait_for_database(max_retries: int = 10, base_delay: float = 1.0) -> None:
    """Wait for database to become available with exponential backoff.

    Retries the initial connection to handle transient failures when
    PostgreSQL is starting up or temporarily unreachable.  SQLite is
    always available locally so the check is skipped entirely.
    """
    if engine.dialect.name == "sqlite":
        return

    from sqlalchemy import text
    from sqlalchemy.exc import OperationalError

    for attempt in range(1, max_retries + 1):
        try:
            with engine.connect() as conn:
                conn.execute(text("SELECT 1"))
            return
        except OperationalError:
            if attempt == max_retries:
                logger.error(f"数据库连接失败，已重试 {max_retries} 次，放弃启动")
                raise
            delay = min(base_delay * (2 ** (attempt - 1)), 30)
            logger.warning(
                f"数据库连接失败 (尝试 {attempt}/{max_retries})，{delay:.1f}s 后重试..."
            )
            time.sleep(delay)


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

    # SQLite-only fail-fast: partial unique indexes (e.g. device_sessions
    # active-row uniqueness, users.username NOT NULL) require SQLite ≥ 3.8.0.
    # Skipped on other backends (Postgres, MySQL) since they don't have the
    # same version floor. Fails the lifespan early so the schema migration
    # below can't produce a confusing CREATE INDEX error first.
    if engine.dialect.name == "sqlite":
        import sqlite3

        sqlite_version = tuple(int(p) for p in sqlite3.sqlite_version.split("."))
        if sqlite_version < (3, 8, 0):
            raise RuntimeError(
                f"SQLite {sqlite3.sqlite_version} too old; partial unique indexes "
                f"require ≥ 3.8.0. Upgrade libsqlite3 in the runtime image."
            )

    # Wait for database to become available (handles transient connection failures)
    _wait_for_database()

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
    if not any(
        [
            migration_summary.get("tables_created"),
            migration_summary.get("columns_added"),
            migration_summary.get("indexes_added"),
            migration_summary.get("errors"),
        ]
    ):
        logger.info("数据库结构已完整，无需迁移")

    # Refuse to boot if legacy storage env vars are still set. This check lives
    # in lifespan (not module import time) so the Alembic CLI can still run
    # migrations while legacy vars are present.
    from packages.core.settings import check_legacy_storage_env_vars

    legacy_storage_vars = check_legacy_storage_env_vars()
    if legacy_storage_vars:
        raise RuntimeError(
            "检测到已废弃的远程存储环境变量: "
            f"{', '.join(legacy_storage_vars)}。\n"
            "远程备份已改为按家庭维度配置，请在「设置 → 家庭管理 → 家庭远程备份」中配置，"
            "并删除上述环境变量后重新启动。"
        )

    db = SessionLocal()
    try:
        # --- Desired State Reconciliation ---
        if not settings.DISABLE_RECONCILE:
            from apps.backend.app.reconcile.lock import create_lock_provider
            from apps.backend.app.reconcile.registry import get_all_resources
            from apps.backend.app.reconcile.runner import DesiredStateRunner, RunMode

            reconcile_mode = RunMode.NORMAL
            if settings.RECONCILE_MODE:
                reconcile_mode = RunMode(settings.RECONCILE_MODE)

            lock_provider = create_lock_provider(engine)
            resources = get_all_resources()
            runner = DesiredStateRunner(
                resources=resources,
                engine=engine,
                db=db,
                mode=reconcile_mode,
                lock_provider=lock_provider,
            )
            report = runner.run()

            if not report.success:
                logger.error(report.summary_text())
                raise RuntimeError(
                    f"系统状态协调失败: {report.critical_failures} 个关键资源未就绪。"
                    "请查看日志获取修复步骤。"
                )
            if report.features_disabled:
                logger.warning(
                    f"部分功能已降级禁用: {', '.join(report.features_disabled)}"
                )
        else:
            run_bootstrap(db)

        # Auto-generate daily snapshots for all families
        try:
            auto_generate_daily_snapshots(db)
        except Exception as e:
            logger.warning(f"自动快照生成失败: {e}")
        # Fetch exchange rates immediately if none exist
        # Skip in CI to avoid slow external API calls during bootstrap
        if not os.environ.get("SKIP_INITIAL_EXCHANGE_RATE_FETCH"):
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

    from apps.backend.app.services.mcp_tool_registry import validate_registry

    validate_registry()
    logger.info("MCP tool registry validated")

    yield


app = FastAPI(
    title="Numina - 家庭资产可视化",
    version="1.0.0",
    lifespan=lifespan,
    default_response_class=EnvelopeResponse,
    redirect_slashes=False,
)

app.add_exception_handler(AppError, app_error_handler)  # type: ignore[arg-type]
app.add_exception_handler(RequestValidationError, validation_error_handler)  # type: ignore[arg-type]
app.add_exception_handler(StarletteHTTPException, http_exception_handler)  # type: ignore[arg-type]
app.add_exception_handler(StorageError, storage_error_handler)  # type: ignore[arg-type]


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
            "message": str(exc)
            if settings.ENVIRONMENT == "development"
            else "Internal server error",
            "traceback": traceback_info,
            "data": None,
            "request_id": request_id,
        },
    )


app.add_exception_handler(Exception, catch_all_exception_handler)


class SecurityHeadersMiddleware:
    """Add security headers to all responses (defense in depth).

    These headers provide additional protection even when Nginx/Cloudflare
    handles the primary security layer.

    Uses pure ASGI middleware (not BaseHTTPMiddleware) to avoid buffering
    StreamingResponse bodies. BaseHTTPMiddleware consumes the entire response
    before sending, which breaks SSE/NDJSON streaming.
    """

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        headers_sent = False

        async def send_with_headers(message):
            nonlocal headers_sent
            if message["type"] == "http.response.start" and not headers_sent:
                headers_sent = True
                # Skip for health check (minimal overhead)
                path = scope.get("path", "")
                if path != "/api/health":
                    headers = list(message.get("headers", []))
                    headers.append((b"X-Content-Type-Options", b"nosniff"))
                    headers.append((b"X-Frame-Options", b"DENY"))
                    headers.append((b"X-XSS-Protection", b"1; mode=block"))
                    headers.append(
                        (b"Referrer-Policy", b"strict-origin-when-cross-origin")
                    )
                    headers.append(
                        (
                            b"Permissions-Policy",
                            b"geolocation=(), microphone=(), camera=()",
                        )
                    )

                    # CSP policy with per-request nonce for script-src
                    nonce = secrets.token_urlsafe(16)
                    # Store nonce on request state for downstream handlers
                    if "state" in scope:
                        scope["state"]["csp_nonce"] = nonce
                    nonce_b = nonce.encode()
                    connect_src = (
                        b"'self' http://localhost:8000 http://127.0.0.1:8000"
                        if settings.ENVIRONMENT == "development"
                        else b"'self'"
                    )
                    csp = (
                        b"default-src 'self'; "
                        b"script-src 'self' 'nonce-" + nonce_b + b"'; "
                        b"style-src 'self' 'unsafe-inline'; "
                        b"img-src 'self' data: https:; "
                        b"font-src 'self'; "
                        b"connect-src " + connect_src + b"; "
                        b"frame-ancestors 'none'; "
                        b"base-uri 'self'; "
                        b"form-action 'self';"
                    )
                    headers.append((b"Content-Security-Policy", csp))

                    # HSTS in production
                    if settings.ENVIRONMENT == "production":
                        headers.append(
                            (
                                b"Strict-Transport-Security",
                                b"max-age=31536000; includeSubDomains",
                            )
                        )

                    # Cache-Control for API endpoints (except cacheable ones)
                    # These paths are reference data that changes infrequently and can be cached briefly
                    _CACHEABLE_API_PATHS = {
                        "/api/v1/categories",
                        "/api/v1/family/members",
                        "/api/v1/family/info",
                        "/api/v1/family",  # Root path for family info (no trailing slash per redirect_slashes=False)
                    }
                    if path.startswith("/api/") and path not in _CACHEABLE_API_PATHS:
                        headers.append(
                            (b"Cache-Control", b"no-store, no-cache, must-revalidate")
                        )

                    message["headers"] = headers
            await send(message)

        try:
            await self.app(scope, receive, send_with_headers)
        except Exception as e:
            logger.exception(
                f"SecurityHeadersMiddleware error on {scope.get('path', '')}: {e}"
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
app.include_router(admin_ai_extraction_router.router, prefix="/api/v1")
app.include_router(admin_audit_logs_router.router, prefix="/api/v1")
app.include_router(ai_config_router.router, prefix="/api/v1")
app.include_router(ai_asr_router.router, prefix="/api/v1")
app.include_router(ai_internal_router.router, prefix="/api/v1")
app.include_router(mcp_internal_router.router, prefix="/api/v1")
app.include_router(ai_report_router.router, prefix="/api/v1")
app.include_router(ai_finance_coach_router.router, prefix="/api/v1")
app.include_router(ai_suggest_router.router, prefix="/api/v1")
app.include_router(ai_context_router.router, prefix="/api/v1")
app.include_router(ai_chat_router.router, prefix="/api/v1")
app.include_router(ai_chat_router.sessions_router, prefix="/api/v1")
app.include_router(ai_threads_router.router, prefix="/api/threads")
app.include_router(ai_input_polish_router.router)
app.include_router(children_router.router, prefix="/api/v1")
app.include_router(chores_router.router, prefix="/api/v1")
app.include_router(coins_router.router, prefix="/api/v1")
app.include_router(child_wishes_router.router, prefix="/api/v1")
app.include_router(milestones_router.router, prefix="/api/v1")
app.include_router(treasures_router.router, prefix="/api/v1")
app.include_router(calendar_router.router, prefix="/api/v1")
app.include_router(blind_box_router.router, prefix="/api/v1")
app.include_router(child_blind_box_router.router, prefix="/api/v1")
app.include_router(literacy_child_router.router, prefix="/api/v1")
app.include_router(literacy_parent_router.router, prefix="/api/v1")
app.include_router(ai_literacy_report_router.router, prefix="/api/v1")
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
app.include_router(ai_agents_router.router, prefix="/api/v1")
app.include_router(ai_agents_internal_router.router, prefix="/api/v1")
app.include_router(ai_web_search_router.router, prefix="/api/v1")
app.include_router(ai_wish_advice_router.router, prefix="/api/v1")
app.include_router(family_config_router.router, prefix="/api/v1")
app.include_router(storage_backend_router.router, prefix="/api/v1")
app.include_router(user_config_router.router, prefix="/api/v1")
app.include_router(manifesto_router.router, prefix="/api/v1")
app.include_router(child_manifesto_router.router, prefix="/api/v1")

# Serve uploaded files — authenticated endpoint with tenant isolation
app.include_router(uploads_serve_router.router)


@app.get("/api/health")
def health():
    return JSONResponse({"status": "ok"})
