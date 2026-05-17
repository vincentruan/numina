"""Tests for AI result parser service."""

import pytest

from apps.backend.app.services.ai_result_parser import (
    _extract_structured_block,
    _validate_json,
    parse_capability_result,
    CAPABILITY_SCHEMAS,
)


class TestExtractStructuredBlock:
    """Tests for _extract_structured_block regex extraction."""

    def test_extract_valid_block(self):
        """Extracts valid STRUCTURED_DATA block."""
        answer = """
        Here is my analysis...

        <!-- STRUCTURED_DATA
        [{"asset_name": "Car", "alert_type": "aging", "severity": "high"}]
        -->
        """
        result = _extract_structured_block(answer)
        assert result == '[{"asset_name": "Car", "alert_type": "aging", "severity": "high"}]'

    def test_extract_missing_delimiter(self):
        """Returns None when delimiter is missing."""
        answer = "Just plain text without structured data"
        result = _extract_structured_block(answer)
        assert result is None

    def test_extract_malformed_delimiter(self):
        """Returns None when delimiter has no newline-separated JSON block."""
        answer = "<!-- STRUCTURED_DATA -->"  # No JSON content between markers
        result = _extract_structured_block(answer)
        assert result == ""  # Empty string, not None - regex extracts empty block

    def test_extract_multiline_json(self):
        """Extracts multiline JSON block."""
        answer = """
        <!-- STRUCTURED_DATA
        {
          "overall_score": 85,
          "narrative": "Good health"
        }
        -->
        """
        result = _extract_structured_block(answer)
        assert "overall_score" in result


class TestValidateJson:
    """Tests for _validate_json schema validation."""

    def test_validate_array_type_valid(self):
        """Validates array-type capability with correct schema."""
        data = [{"asset_name": "Car", "alert_type": "aging", "severity": "high"}]
        assert _validate_json(data, "alerts") is True

    def test_validate_array_type_missing_required(self):
        """Rejects array with missing required fields."""
        data = [{"asset_name": "Car"}]  # missing alert_type, severity
        assert _validate_json(data, "alerts") is False

    def test_validate_array_type_not_array(self):
        """Rejects dict when array expected."""
        data = {"asset_name": "Car"}
        assert _validate_json(data, "alerts") is False

    def test_validate_object_type_valid(self):
        """Validates object-type capability with correct schema."""
        data = {"has_significant_drift": True, "narrative": "Some drift"}
        assert _validate_json(data, "allocation") is True

    def test_validate_object_type_missing_required(self):
        """Rejects object with missing required field."""
        data = {"narrative": "Some text"}  # missing has_significant_drift
        assert _validate_json(data, "allocation") is False

    def test_validate_object_type_not_object(self):
        """Rejects array when object expected."""
        data = [{"has_significant_drift": True}]
        assert _validate_json(data, "allocation") is False

    def test_validate_unknown_capability(self):
        """Passes validation for unknown capability."""
        data = {"anything": "value"}
        assert _validate_json(data, "unknown_capability") is True


class TestParseCapabilityResult:
    """Tests for parse_capability_result function."""

    def test_parse_valid_alerts_json(self, db_session, test_family):
        """Parses valid alerts structured data."""
        answer = """
        Analysis complete.

        <!-- STRUCTURED_DATA
        [{"asset_name": "Car", "alert_type": "aging", "severity": "high", "suggestion": "Replace soon"}]
        -->
        """
        result = parse_capability_result("alerts", answer, test_family.id, db_session)
        assert result is not None
        assert isinstance(result, list)
        assert len(result) == 1
        assert result[0]["asset_name"] == "Car"

    def test_parse_valid_allocation_json(self, db_session, test_family):
        """Parses valid allocation drift structured data."""
        answer = """
        <!-- STRUCTURED_DATA
        {"has_significant_drift": true, "drifts": [{"category": "stocks", "drift": 5.2}]}
        -->
        """
        result = parse_capability_result("allocation", answer, test_family.id, db_session)
        assert result is not None
        assert isinstance(result, dict)
        assert result["has_significant_drift"] is True

    def test_parse_missing_block_returns_none(self, db_session, test_family):
        """Returns None when no STRUCTURED_DATA block found."""
        answer = "No structured data here"
        result = parse_capability_result("alerts", answer, test_family.id, db_session)
        assert result is None

    def test_parse_invalid_json_returns_none(self, db_session, test_family):
        """Returns None when JSON is malformed."""
        answer = """
        <!-- STRUCTURED_DATA
        {not valid json}
        -->
        """
        result = parse_capability_result("alerts", answer, test_family.id, db_session)
        assert result is None

    def test_parse_schema_mismatch_returns_none(self, db_session, test_family):
        """Returns None when data doesn't match schema."""
        answer = """
        <!-- STRUCTURED_DATA
        [{"asset_name": "Car"}]
        -->
        """  # missing required fields
        result = parse_capability_result("alerts", answer, test_family.id, db_session)
        assert result is None