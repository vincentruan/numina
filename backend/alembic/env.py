"""Alembic 迁移环境配置"""

from logging.config import fileConfig

from alembic import context

from app.db import get_engine
from app.database import Base
from app.config import settings

# Import all models
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
from app.models.ai_ws_ticket import AIWsTicket  # noqa: F401

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