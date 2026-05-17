"""AI capability result writer — persist structured results to DB tables.

Each capability has its own writer function with replace strategy:
- Clear previous results for family+capability
- Bulk insert new structured records
"""

import logging
from collections.abc import Callable
from typing import Any

from sqlalchemy.orm import Session

from apps.backend.app.models.ai_allocation_drift_result import AIAllocationDriftResult
from apps.backend.app.models.ai_asset_alert import AIAssetAlert
from apps.backend.app.models.ai_disposal_suggestion import AIDisposalSuggestion
from apps.backend.app.models.ai_liability_result import AILiabilityResult
from apps.backend.app.models.ai_report import AIReport
from apps.backend.app.models.ai_spending_leak import AISpendingLeak
from apps.backend.app.models.asset import Asset
from apps.backend.app.utils.snowflake import next_id

logger = logging.getLogger(__name__)


def _validate_asset_ownership(asset_id: int | None, family_id: int, db: Session) -> int | None:
    """Validate that an asset belongs to the family.

    Returns the asset_id if valid, None otherwise.
    """
    if asset_id is None:
        return None
    asset = db.query(Asset).filter(
        Asset.id == asset_id,
        Asset.family_id == family_id,
        Asset.is_archived.is_(False),
    ).first()
    return asset.id if asset else None


def write_alerts_results(family_id: int, results: list[dict], db: Session) -> int:
    """Write alerts results to ai_asset_alerts table.

    Replace strategy: clear previous non-dismissed alerts first.
    """
    try:
        # Clear previous non-dismissed alerts for this family
        db.query(AIAssetAlert).filter(
            AIAssetAlert.family_id == family_id,
            AIAssetAlert.is_dismissed.is_(False),
        ).delete()

        if not results:
            db.commit()
            return 0

        # Bulk insert new alerts
        count = 0
        for r in results:
            asset_id = r.get("asset_id")
            validated_asset_id = _validate_asset_ownership(asset_id, family_id, db)
            alert = AIAssetAlert(
                id=next_id(),
                family_id=family_id,
                asset_id=validated_asset_id,  # Only set if owned by family
                asset_name=r.get("asset_name", ""),
                alert_type=r.get("alert_type", "aging"),
                severity=r.get("severity", "medium"),
                suggestion=r.get("suggestion"),
                remaining_life_days=r.get("remaining_life_days"),
                daily_cost=r.get("daily_cost"),
            )
            db.add(alert)
            count += 1

        db.commit()
        logger.info(f"[alerts] wrote {count} alerts for family {family_id}")
        return count
    except Exception as e:
        db.rollback()
        logger.error(f"[alerts] failed to write alerts for family {family_id}: {e}")
        raise


def write_disposal_results(family_id: int, results: list[dict], db: Session) -> int:
    """Write disposal suggestions to ai_disposal_suggestions table.

    Replace strategy: clear previous non-dismissed suggestions first.
    """
    try:
        # Clear previous non-dismissed suggestions for this family
        db.query(AIDisposalSuggestion).filter(
            AIDisposalSuggestion.family_id == family_id,
            AIDisposalSuggestion.is_dismissed.is_(False),
        ).delete()

        if not results:
            db.commit()
            return 0

        # Bulk insert new suggestions
        count = 0
        for r in results:
            asset_id = r.get("asset_id")
            validated_asset_id = _validate_asset_ownership(asset_id, family_id, db)
            suggestion = AIDisposalSuggestion(
                id=next_id(),
                family_id=family_id,
                asset_id=validated_asset_id,  # Only set if owned by family
                asset_name=r.get("asset_name", ""),
                category_name=r.get("category_name"),
                inefficiency_score=r.get("inefficiency_score", 0),
                suggested_channel=r.get("suggested_channel"),
                estimated_resale_range=r.get("estimated_resale_range"),
                suggestion=r.get("suggestion"),
                daily_cost=r.get("daily_cost"),
            )
            db.add(suggestion)
            count += 1

        db.commit()
        logger.info(f"[disposal] wrote {count} suggestions for family {family_id}")
        return count
    except Exception as e:
        db.rollback()
        logger.error(f"[disposal] failed to write suggestions for family {family_id}: {e}")
        raise


def write_spending_leak_results(family_id: int, results: list[dict], db: Session) -> int:
    """Write spending leak results to ai_spending_leaks table.

    Replace strategy: clear previous non-dismissed leaks first.
    """
    try:
        # Clear previous non-dismissed leaks for this family
        db.query(AISpendingLeak).filter(
            AISpendingLeak.family_id == family_id,
            AISpendingLeak.is_dismissed.is_(False),
        ).delete()

        if not results:
            db.commit()
            return 0

        # Bulk insert new leaks
        count = 0
        for r in results:
            asset_id = r.get("asset_id")
            validated_asset_id = _validate_asset_ownership(asset_id, family_id, db)
            leak = AISpendingLeak(
                id=next_id(),
                family_id=family_id,
                asset_id=validated_asset_id,  # Only set if owned by family
                asset_name=r.get("asset_name", ""),
                leak_type=r.get("leak_type", "high_idle_cost"),
                severity=r.get("severity", "medium"),
                estimated_annual_waste=r.get("estimated_annual_waste"),
                suggestion=r.get("suggestion"),
            )
            db.add(leak)
            count += 1

        db.commit()
        logger.info(f"[spending_leak] wrote {count} leaks for family {family_id}")
        return count
    except Exception as e:
        db.rollback()
        logger.error(f"[spending_leak] failed to write leaks for family {family_id}: {e}")
        raise


def write_report_results(family_id: int, results: dict, db: Session) -> int:
    """Write report results to ai_reports table.

    Replace strategy: clear previous reports for this family first.
    """
    try:
        # Clear previous reports for this family
        db.query(AIReport).filter(AIReport.family_id == family_id).delete()

        if not results:
            db.commit()
            return 0

        report = AIReport(
            id=next_id(),
            family_id=family_id,
            report_json=results,
            overall_score=results.get("overall_score"),
            data_completeness_score=results.get("data_completeness_score"),
            status="completed",
        )
        db.add(report)
        db.commit()
        logger.info(f"[report] wrote report for family {family_id}")
        return 1
    except Exception as e:
        db.rollback()
        logger.error(f"[report] failed to write report for family {family_id}: {e}")
        raise


def write_allocation_drift_results(family_id: int, results: dict, db: Session) -> int:
    """Write allocation drift results to ai_allocation_drift_results table.

    Replace strategy: clear previous drift results for this family first.
    """
    try:
        # Clear previous drift results for this family
        db.query(AIAllocationDriftResult).filter(
            AIAllocationDriftResult.family_id == family_id
        ).delete()

        if not results:
            db.commit()
            return 0

        drift_result = AIAllocationDriftResult(
            id=next_id(),
            family_id=family_id,
            has_significant_drift=results.get("has_significant_drift", False),
            narrative=results.get("narrative"),
            drifts_json=results.get("drifts"),
        )
        db.add(drift_result)
        db.commit()
        logger.info(f"[allocation] wrote drift result for family {family_id}")
        return 1
    except Exception as e:
        db.rollback()
        logger.error(f"[allocation] failed to write drift result for family {family_id}: {e}")
        raise


def write_liability_results(family_id: int, results: dict, db: Session) -> int:
    """Write liability advice results to ai_liability_results table.

    Replace strategy: clear previous liability results for this family first.
    """
    try:
        # Clear previous liability results for this family
        db.query(AILiabilityResult).filter(
            AILiabilityResult.family_id == family_id
        ).delete()

        if not results:
            db.commit()
            return 0

        liability_result = AILiabilityResult(
            id=next_id(),
            family_id=family_id,
            has_liabilities=results.get("has_liabilities", False),
            total_remaining=results.get("total_remaining"),
            total_monthly_payment=results.get("total_monthly_payment"),
            liability_count=results.get("liability_count"),
            narrative=results.get("narrative"),
            recommended_strategy=results.get("recommended_strategy"),
            strategies_json=results.get("strategies"),
        )
        db.add(liability_result)
        db.commit()
        logger.info(f"[liability] wrote liability result for family {family_id}")
        return 1
    except Exception as e:
        db.rollback()
        logger.error(f"[liability] failed to write liability result for family {family_id}: {e}")
        raise


# Unified dispatcher
def write_capability_results(
    capability: str,
    family_id: int,
    results: list[dict] | dict,
    db: Session,
) -> int:
    """Dispatch to appropriate writer based on capability.

    Args:
        capability: One of alerts, disposal, spending_leak, report, allocation, liability
        family_id: Family ID
        results: Structured data (list for array-type, dict for object-type)
        db: Database session

    Returns:
        Number of records written
    """
    writers: dict[str, Callable[[int, Any, Session], int]] = {
        "alerts": write_alerts_results,
        "disposal": write_disposal_results,
        "spending_leak": write_spending_leak_results,
        "report": write_report_results,
        "allocation": write_allocation_drift_results,
        "liability": write_liability_results,
    }

    writer = writers.get(capability)
    if not writer:
        logger.warning(f"[{capability}] no writer registered, skipping")
        return 0

    return writer(family_id, results, db)