"""Tests for AI result writer service."""

import pytest
from unittest.mock import MagicMock, patch

from apps.backend.app.services.ai_result_writer import (
    _validate_asset_ownership,
    write_alerts_results,
    write_disposal_results,
    write_spending_leak_results,
    write_report_results,
    write_allocation_drift_results,
    write_liability_results,
    write_capability_results,
)


class TestValidateAssetOwnership:
    """Tests for _validate_asset_ownership function."""

    def test_returns_none_for_null_asset_id(self, db_session, test_family):
        """Returns None when asset_id is None."""
        result = _validate_asset_ownership(None, test_family.id, db_session)
        assert result is None

    def test_returns_id_for_owned_asset(self, db_session, test_family, test_asset):
        """Returns asset_id when asset belongs to family."""
        result = _validate_asset_ownership(test_asset.id, test_family.id, db_session)
        assert result == test_asset.id

    def test_returns_none_for_other_family_asset(self, db_session, test_family, other_family_asset):
        """Returns None when asset belongs to different family."""
        result = _validate_asset_ownership(other_family_asset.id, test_family.id, db_session)
        assert result is None

    def test_returns_none_for_archived_asset(self, db_session, test_family, archived_asset):
        """Returns None when asset is archived."""
        result = _validate_asset_ownership(archived_asset.id, test_family.id, db_session)
        assert result is None

    def test_returns_none_for_nonexistent_asset(self, db_session, test_family):
        """Returns None when asset doesn't exist."""
        result = _validate_asset_ownership(999999999, test_family.id, db_session)
        assert result is None


class TestWriteAlertsResults:
    """Tests for write_alerts_results function."""

    def test_writes_valid_results(self, db_session, test_family, test_asset):
        """Writes valid alerts to database."""
        results = [
            {
                "asset_id": test_asset.id,
                "asset_name": test_asset.name,
                "alert_type": "aging",
                "severity": "high",
                "suggestion": "Replace soon",
            }
        ]
        count = write_alerts_results(test_family.id, results, db_session)
        assert count == 1

    def test_handles_empty_results(self, db_session, test_family):
        """Handles empty results list."""
        count = write_alerts_results(test_family.id, [], db_session)
        assert count == 0

    def test_replaces_previous_results(self, db_session, test_family, test_asset):
        """Replaces previous alerts (clear before insert)."""
        # Write first batch
        write_alerts_results(test_family.id, [{"asset_name": "Old", "alert_type": "aging", "severity": "low"}], db_session)

        # Write second batch
        count = write_alerts_results(test_family.id, [{"asset_name": "New", "alert_type": "aging", "severity": "high"}], db_session)
        assert count == 1

    def test_skips_unowned_assets(self, db_session, test_family, other_family_asset):
        """Skips results with asset_id not owned by family."""
        results = [
            {
                "asset_id": other_family_asset.id,  # Different family
                "asset_name": "Other Asset",
                "alert_type": "aging",
                "severity": "high",
            }
        ]
        count = write_alerts_results(test_family.id, results, db_session)
        assert count == 1  # Still writes, but asset_id is None

    def test_rollback_on_error(self, db_session, test_family):
        """Rolls back on database error."""
        from unittest.mock import MagicMock

        # Simulate error by making commit fail
        original_commit = db_session.commit
        db_session.commit = MagicMock(side_effect=Exception("DB error"))
        db_session.rollback = MagicMock()

        results = [{"asset_name": "Test", "alert_type": "aging", "severity": "high"}]

        with pytest.raises(Exception):
            write_alerts_results(test_family.id, results, db_session)

        # Verify rollback was called
        db_session.rollback.assert_called()
        db_session.commit = original_commit


class TestWriteDisposalResults:
    """Tests for write_disposal_results function."""

    def test_writes_valid_results(self, db_session, test_family, test_asset):
        """Writes valid disposal suggestions."""
        results = [
            {
                "asset_id": test_asset.id,
                "asset_name": test_asset.name,
                "inefficiency_score": 75,
            }
        ]
        count = write_disposal_results(test_family.id, results, db_session)
        assert count == 1

    def test_handles_empty_results(self, db_session, test_family):
        """Handles empty results."""
        count = write_disposal_results(test_family.id, [], db_session)
        assert count == 0


class TestWriteSpendingLeakResults:
    """Tests for write_spending_leak_results function."""

    def test_writes_valid_results(self, db_session, test_family, test_asset):
        """Writes valid spending leaks."""
        results = [
            {
                "asset_id": test_asset.id,
                "asset_name": test_asset.name,
                "leak_type": "high_idle_cost",
                "severity": "medium",
            }
        ]
        count = write_spending_leak_results(test_family.id, results, db_session)
        assert count == 1

    def test_handles_empty_results(self, db_session, test_family):
        """Handles empty results."""
        count = write_spending_leak_results(test_family.id, [], db_session)
        assert count == 0


class TestWriteReportResults:
    """Tests for write_report_results function."""

    def test_writes_valid_report(self, db_session, test_family):
        """Writes valid report."""
        results = {"overall_score": 85, "data_completeness_score": 90}
        count = write_report_results(test_family.id, results, db_session)
        assert count == 1

    def test_handles_empty_results(self, db_session, test_family):
        """Handles empty dict."""
        count = write_report_results(test_family.id, {}, db_session)
        assert count == 0


class TestWriteAllocationDriftResults:
    """Tests for write_allocation_drift_results function."""

    def test_writes_valid_drift(self, db_session, test_family):
        """Writes valid allocation drift."""
        results = {"has_significant_drift": True, "drifts": [{"category": "stocks", "drift": 5}]}
        count = write_allocation_drift_results(test_family.id, results, db_session)
        assert count == 1

    def test_handles_empty_results(self, db_session, test_family):
        """Handles empty dict."""
        count = write_allocation_drift_results(test_family.id, {}, db_session)
        assert count == 0


class TestWriteLiabilityResults:
    """Tests for write_liability_results function."""

    def test_writes_valid_liability(self, db_session, test_family):
        """Writes valid liability result."""
        results = {
            "has_liabilities": True,
            "total_remaining": 50000,
            "recommended_strategy": "avalanche",
        }
        count = write_liability_results(test_family.id, results, db_session)
        assert count == 1

    def test_handles_empty_results(self, db_session, test_family):
        """Handles empty dict."""
        count = write_liability_results(test_family.id, {}, db_session)
        assert count == 0


class TestWriteCapabilityResults:
    """Tests for write_capability_results dispatcher."""

    def test_dispatches_to_correct_writer(self, db_session, test_family):
        """Dispatches to correct writer based on capability."""
        count = write_capability_results("report", test_family.id, {"overall_score": 80}, db_session)
        assert count == 1

    def test_returns_zero_for_unknown_capability(self, db_session, test_family):
        """Returns 0 for unknown capability."""
        count = write_capability_results("unknown", test_family.id, {}, db_session)
        assert count == 0