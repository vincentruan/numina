"""System bootstrap — one-time initialization of data required for the system to run.

Unlike Alembic migrations (which handle schema changes), bootstrap ensures that
essential runtime data exists: system categories, currencies, builtin agents,
builtin skills, invitation codes, storage backends, etc.

All bootstrap functions are idempotent — safe to run on every startup.
They use SQLAlchemy ORM for PostgreSQL + SQLite compatibility.
"""

from sqlalchemy.orm import Session

from apps.backend.app.core.logging_config import get_logger

logger = get_logger(__name__)


def run_bootstrap(db: Session) -> None:
    """Execute all system bootstrap steps in dependency order."""
    from apps.backend.app.bootstrap.agents import bootstrap_agents
    from apps.backend.app.bootstrap.categories import bootstrap_categories
    from apps.backend.app.bootstrap.category_financial_defaults import (
        bootstrap_category_financial_defaults,
    )
    from apps.backend.app.bootstrap.currencies import bootstrap_currencies
    from apps.backend.app.bootstrap.invitation_codes import bootstrap_invitation_codes
    from apps.backend.app.bootstrap.skills import bootstrap_skills
    from apps.backend.app.bootstrap.storage_backends import bootstrap_storage_backends

    bootstrap_categories(db)
    bootstrap_currencies(db)
    bootstrap_invitation_codes(db)
    bootstrap_storage_backends(db)
    bootstrap_category_financial_defaults(db)
    bootstrap_agents(db)
    bootstrap_skills(db)

    logger.info("系统初始化数据检查完成")
