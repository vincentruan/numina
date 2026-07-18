"""Tests for AI result writer service.

U7: 5 外扩 trigger skill writers (alerts/disposal/spending_leak/allocation/liability)
removed; only ``write_report_results`` remains. ``_validate_asset_ownership`` helper
was deleted with the trigger writers (it had no other callers).
"""

import pytest
from unittest.mock import MagicMock

from apps.backend.app.services.ai_result_writer import (
    write_report_results,
    write_capability_results,
)


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
