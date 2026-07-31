"""Alembic 迁移环境配置"""

from logging.config import fileConfig

from alembic import context

from apps.backend.app.config import settings
from apps.backend.app.database import Base
from apps.backend.app.db import get_engine
from apps.backend.app.models.ai_agent import AIAgent
from apps.backend.app.models.ai_provider_config import (
    AIProviderConfig,
    AIProviderTestResult,
)

# Alembic env imports models for SQLAlchemy registration, not direct use
from apps.backend.app.models.asset import Asset
from apps.backend.app.models.asset_lifecycle_event import (
    AssetLifecycleEvent,
)
from apps.backend.app.models.category import Category
from apps.backend.app.models.child_economy_config import (
    ChildEconomyConfig,
)
from apps.backend.app.models.child_wish import ChildWish
from apps.backend.app.models.child_wish_cost_history import (
    ChildWishCostHistory,
)
from apps.backend.app.models.family_invitation_code import (
    FamilyInvitationCode,
)
from apps.backend.app.models.family_mcp_server import FamilyMCPServer
from apps.backend.app.models.family_web_search_provider import (
    FamilyWebSearchProvider,
)
from apps.backend.app.models.liability import Liability
from apps.backend.app.models.manifesto import (
    FamilyManifesto,
    ManifestoFeedback,
    ManifestoSignature,
    ManifestoVersion,
)
from apps.backend.app.models.payment_record import PaymentRecord

# Import all models
from apps.backend.app.models.skill_registry import SkillRegistry
from apps.backend.app.models.tag import Tag
from apps.backend.app.models.valuation import AssetValuation
from apps.backend.app.models.wish import Wish

# Models migrated to packages/db/models (Unit 3+)
from packages.db.models import (
    CachedFile,
    FileRemoteLocation,
    StorageBackend,
)
from packages.db.models.ai_task import AITask
from packages.db.models.asset_snapshot import AssetSnapshot
from packages.db.models.currency import Currency
from packages.db.models.device_session import DeviceSession
from packages.db.models.exchange_rate import ExchangeRate
from packages.db.models.family import Family
from packages.db.models.notification_channel import NotificationChannel
from packages.db.models.notification_channel_config import (
    NotificationChannelConfig,
)
from packages.db.models.notification_config import NotificationConfig
from packages.db.models.notification_subscription import (
    NotificationSubscription,
)
from packages.db.models.reminder import Reminder
from packages.db.models.reminder_notification import ReminderNotification
from packages.db.models.revoked_token import RevokedToken
from packages.db.models.security_audit_log import SecurityAuditLog
from packages.db.models.user import User

config = context.config
config.set_main_option("sqlalchemy.url", settings.DATABASE_URL)

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    """离线迁移模式：生成 SQL 脚本"""
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """在线迁移模式：直接执行迁移"""
    # 使用工厂创建 engine，确保连接参数与应用一致
    connectable = get_engine(settings.DATABASE_URL)

    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()