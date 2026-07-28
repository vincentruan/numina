"""Resource registry — declares all desired-state resources for this project.

This is the single source of truth for what the system expects at startup.
Add new resources here; the runner will reconcile them automatically.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from apps.backend.app.reconcile.resources import (
    DatabaseSeedResource,
    DirectoryResource,
    FeatureFlagResource,
)
from apps.backend.app.reconcile.types import FailureAction, ResourceStatus
from packages.core.settings import settings

if TYPE_CHECKING:
    from apps.backend.app.reconcile.base import Resource


def _data_root() -> Path:
    return Path(settings.DATA_ROOT)


# ---------------------------------------------------------------------------
# Directory resources
# ---------------------------------------------------------------------------

def _directory_resources() -> list[Resource]:
    root = _data_root()
    return [
        DirectoryResource(
            name="data_root",
            path=root,
            critical=True,
        ),
        DirectoryResource(
            name="data_db",
            path=root / "db",
            critical=True,
        ),
        DirectoryResource(
            name="data_workspaces",
            path=root / "workspaces",
            critical=True,
        ),
        DirectoryResource(
            name="data_logs",
            path=Path(settings.LOG_DIR),
            critical=False,
            failure_action=FailureAction.WARN_ONLY,
        ),
        DirectoryResource(
            name="data_cache",
            path=root / "cache",
            critical=False,
            failure_action=FailureAction.WARN_ONLY,
        ),
    ]


# ---------------------------------------------------------------------------
# Database seed resources (wrapping existing bootstrap functions)
# ---------------------------------------------------------------------------

def _db_seed_resources() -> list[Resource]:
    """Wrap existing bootstrap functions as reconcilable resources."""
    from sqlalchemy.orm import Session

    from apps.backend.app.reconcile.types import ResourceResult, ResourceType

    def _check_categories(db: Session) -> ResourceResult | None:
        from apps.backend.app.models.category import Category
        count = db.query(Category).filter(Category.is_system.is_(True)).count()
        if count >= 23:
            return None  # verified (default)
        return ResourceResult(
            resource_name="seed_categories",
            resource_type=ResourceType.DATABASE_SEED,
            desired_version="1",
            status=ResourceStatus.DRIFTED,
            current_version=f"count={count}",
            critical=True,
        )

    def _apply_categories(db: Session) -> ResourceResult | None:
        from apps.backend.app.bootstrap.categories import bootstrap_categories
        bootstrap_categories(db)
        return None

    def _check_currencies(db: Session) -> ResourceResult | None:
        from apps.backend.app.models.currency import Currency
        count = db.query(Currency).filter(Currency.is_favorite.is_(True)).count()
        if count >= 13:
            return None
        return ResourceResult(
            resource_name="seed_currencies",
            resource_type=ResourceType.DATABASE_SEED,
            desired_version="1",
            status=ResourceStatus.DRIFTED,
            current_version=f"count={count}",
            critical=True,
        )

    def _apply_currencies(db: Session) -> ResourceResult | None:
        from apps.backend.app.bootstrap.currencies import bootstrap_currencies
        bootstrap_currencies(db)
        return None

    def _check_invitation_codes(db: Session) -> ResourceResult | None:
        from apps.backend.app.bootstrap.invitation_codes import (
            bootstrap_invitation_codes,
        )
        # Invitation codes are environment-dependent; always run the idempotent bootstrap
        bootstrap_invitation_codes(db)
        return None

    def _check_storage_backends(db: Session) -> ResourceResult | None:
        from apps.backend.app.bootstrap.storage_backends import (
            bootstrap_storage_backends,
        )
        bootstrap_storage_backends(db)
        return None

    def _check_category_financial_defaults(db: Session) -> ResourceResult | None:
        from apps.backend.app.models.category_financial_default import (
            CategoryFinancialDefault,
        )
        count = db.query(CategoryFinancialDefault).count()
        if count >= 20:
            return None
        return ResourceResult(
            resource_name="seed_category_financial_defaults",
            resource_type=ResourceType.DATABASE_SEED,
            desired_version="1",
            status=ResourceStatus.DRIFTED,
            current_version=f"count={count}",
            critical=False,
        )

    def _apply_category_financial_defaults(db: Session) -> ResourceResult | None:
        from apps.backend.app.bootstrap.category_financial_defaults import (
            bootstrap_category_financial_defaults,
        )
        bootstrap_category_financial_defaults(db)
        return None

    def _check_agents(db: Session) -> ResourceResult | None:
        from apps.backend.app.constants.system_ids import NUMINA_AGENT_ID
        from apps.backend.app.models.ai_agent import AIAgent
        existing = db.query(AIAgent).filter(AIAgent.id == NUMINA_AGENT_ID).first()
        if existing:
            return None
        return ResourceResult(
            resource_name="seed_agents",
            resource_type=ResourceType.DATABASE_SEED,
            desired_version="1",
            status=ResourceStatus.DRIFTED,
            current_version=None,
            critical=True,
        )

    def _apply_agents(db: Session) -> ResourceResult | None:
        from apps.backend.app.bootstrap.agents import bootstrap_agents
        bootstrap_agents(db)
        return None

    def _check_skills(db: Session) -> ResourceResult | None:
        # bootstrap_skills() is a permanent no-op (file-system skills replaced DB
        # registry rows in U5). Desired state = 0 rows — always satisfied.
        return None

    def _apply_skills(db: Session) -> ResourceResult | None:
        return None

    return [
        DatabaseSeedResource(
            name="seed_categories",
            desired_version="1",
            critical=True,
            check_fn=_check_categories,
            apply_fn=_apply_categories,
        ),
        DatabaseSeedResource(
            name="seed_currencies",
            desired_version="1",
            critical=True,
            check_fn=_check_currencies,
            apply_fn=_apply_currencies,
        ),
        DatabaseSeedResource(
            name="seed_invitation_codes",
            desired_version="1",
            critical=False,
            failure_action=FailureAction.WARN_ONLY,
            check_fn=_check_invitation_codes,
        ),
        DatabaseSeedResource(
            name="seed_storage_backends",
            desired_version="1",
            critical=False,
            failure_action=FailureAction.WARN_ONLY,
            check_fn=_check_storage_backends,
        ),
        DatabaseSeedResource(
            name="seed_category_financial_defaults",
            desired_version="1",
            critical=False,
            failure_action=FailureAction.WARN_ONLY,
            check_fn=_check_category_financial_defaults,
            apply_fn=_apply_category_financial_defaults,
        ),
        DatabaseSeedResource(
            name="seed_agents",
            desired_version="1",
            critical=True,
            check_fn=_check_agents,
            apply_fn=_apply_agents,
        ),
        DatabaseSeedResource(
            name="seed_skills",
            desired_version="1",
            critical=True,
            check_fn=_check_skills,
            apply_fn=_apply_skills,
        ),
    ]


# ---------------------------------------------------------------------------
# Feature flag resources
# ---------------------------------------------------------------------------

def _feature_flag_resources() -> list[Resource]:
    def _check_ai_available(db) -> bool:
        return bool(settings.AI_ENCRYPTION_KEY)

    def _check_storage_configured(db) -> bool:
        return bool(settings.STORAGE_BACKEND_TYPE)

    return [
        FeatureFlagResource(
            name="flag_ai_features",
            flag_name="ai_features",
            condition_fn=_check_ai_available,
            disable_reason="AI_ENCRYPTION_KEY not configured",
            recovery_hint="Set AI_ENCRYPTION_KEY in environment to enable AI features.",
        ),
        FeatureFlagResource(
            name="flag_remote_storage",
            flag_name="remote_storage",
            condition_fn=_check_storage_configured,
            disable_reason="No STORAGE_BACKEND_TYPE configured",
            recovery_hint="Set STORAGE_BACKEND_TYPE to 'github' or 'webdav' to enable remote storage sync.",
        ),
    ]


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def get_all_resources() -> list[Resource]:
    """Build the complete list of desired-state resources in dependency order."""
    resources: list[Resource] = []
    resources.extend(_directory_resources())
    resources.extend(_db_seed_resources())
    resources.extend(_feature_flag_resources())
    return resources
