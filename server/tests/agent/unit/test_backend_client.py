"""Unit tests for backend client tenant boundary helpers."""

import pytest

from apps.agent.core.backend_client import _validate_family_id


class TestFamilyIdValidation:
    def test_accepts_backend_snowflake_family_id(self):
        assert _validate_family_id("1987654321098765432") == "1987654321098765432"

    def test_accepts_legacy_prefixed_family_id(self):
        assert _validate_family_id("fam-golden-001") == "fam-golden-001"

    @pytest.mark.parametrize(
        "family_id",
        [
            "",
            "../123",
            "123abc",
            "fam-",
            "family 123",
        ],
    )
    def test_rejects_invalid_family_id(self, family_id):
        with pytest.raises(ValueError):
            _validate_family_id(family_id)
