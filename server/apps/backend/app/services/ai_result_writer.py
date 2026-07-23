"""AI capability result writer — persist structured results to DB tables.

Each capability has its own writer function with replace strategy:
- Clear previous results for family+capability
- Bulk insert new structured records
"""

import logging
from collections.abc import Callable
from typing import Any

from sqlalchemy.orm import Session

from apps.backend.app.models.ai_report import AIReport
from apps.backend.app.utils.snowflake import next_id

logger = logging.getLogger(__name__)


def write_report_results(
    family_id: int,
    results: dict,
    db: Session,
    *,
    markdown_file_path: str | None = None,
) -> int:
    """Write report results to ai_reports table.

    Replace strategy: clear previous reports for this family first.

    Args:
        markdown_file_path: Optional relative path to the step-1 markdown audit
            file under the tenant reports directory (U4 step 7 — persisted so
            the frontend can fall back to the markdown even if step-3 JSON
            parsing failed on a later render).
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
            markdown_file_path=markdown_file_path,
        )
        db.add(report)
        db.commit()
        logger.info(f"[report] wrote report for family {family_id}")
        return 1
    except Exception as e:
        db.rollback()
        logger.error(f"[report] failed to write report for family {family_id}: {e}")
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
        capability: Capability name (currently only ``report``; the 5 trigger
            capabilities were removed in U7 and regress to numina SOUL)
        family_id: Family ID
        results: Structured data (list for array-type, dict for object-type)
        db: Database session

    Returns:
        Number of records written
    """
    writers: dict[str, Callable[[int, Any, Session], int]] = {
        "report": write_report_results,
    }

    writer = writers.get(capability)
    if not writer:
        logger.warning(f"[{capability}] no writer registered, skipping")
        return 0

    return writer(family_id, results, db)