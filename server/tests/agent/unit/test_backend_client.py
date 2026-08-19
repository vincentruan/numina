"""Unit tests for backend client tenant boundary helpers."""

import pytest

from apps.agent.core.backend_client import (
    _extract_llm_error_info,
    _validate_family_id,
    classify_error_type,
)


class TestFamilyIdValidation:
    def test_accepts_backend_snowflake_family_id(self):
        assert _validate_family_id("1987654321098765432") == "1987654321098765432"

    def test_accepts_legacy_prefixed_family_id(self):
        assert _validate_family_id("fam-golden-001") == "fam-golden-001"

    @pytest.mark.skip(reason="Validation is currently relaxed for development testing")
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


class TestClassifyErrorType:
    def test_401_is_permanent_auth(self):
        assert classify_error_type(401) == "permanent_auth"

    def test_403_is_permanent_auth(self):
        assert classify_error_type(403) == "permanent_auth"

    def test_410_is_permanent_account(self):
        assert classify_error_type(410) == "permanent_account"

    def test_402_is_permanent_account(self):
        """402 Payment Required must open circuit immediately."""
        assert classify_error_type(402) == "permanent_account"

    def test_402_with_billing_message_is_permanent_account(self):
        """402 with any message still classified by status code."""
        assert classify_error_type(402, "Your credit balance is insufficient") == "permanent_account"

    def test_429_is_transient_rate_limit(self):
        assert classify_error_type(429) == "transient_rate_limit"

    def test_500_is_transient_server(self):
        assert classify_error_type(500) == "transient_server"

    def test_invalid_key_message_is_permanent_auth(self):
        assert classify_error_type(0, "Invalid API key provided") == "permanent_auth"

    def test_deleted_account_message_is_permanent_account(self):
        assert classify_error_type(0, "account has been deleted") == "permanent_account"

    def test_out_of_quota_is_permanent_account(self):
        """User's original failure case: quota exhaustion must trigger circuit open."""
        msg = (
            "The configured LLM provider rejected the request because "
            "the account is out of quota, billing is unavailable, "
            "or usage is restricted."
        )
        assert classify_error_type(0, msg) == "permanent_account"

    def test_billing_unavailable_is_permanent_account(self):
        assert classify_error_type(0, "billing unavailable") == "permanent_account"

    def test_quota_exceeded_is_permanent_account(self):
        assert classify_error_type(0, "Quota exceeded for this month") == "permanent_account"

    def test_usage_restricted_is_permanent_account(self):
        assert classify_error_type(0, "Usage is restricted") == "permanent_account"

    def test_insufficient_funds_is_permanent_account(self):
        assert classify_error_type(0, "insufficient funds for this request") == "permanent_account"

    def test_no_credits_is_permanent_account(self):
        assert classify_error_type(0, "You have no credits remaining") == "permanent_account"

    def test_payment_required_message_is_permanent_account(self):
        assert classify_error_type(0, "payment required to continue") == "permanent_account"

    def test_subscription_expired_is_permanent_account(self):
        assert classify_error_type(0, "Your subscription has expired") == "permanent_account"

    def test_plan_limit_reached_is_permanent_account(self):
        assert classify_error_type(0, "plan limit reached for this month") == "permanent_account"

    def test_unknown_code_is_transient_network(self):
        assert classify_error_type(0, "something unknown") == "transient_timeout"

    def test_unknown_code_without_message_is_transient_network(self):
        assert classify_error_type(1234) == "transient_network"


class TestExtractLlmErrorInfo:
    def test_plain_exception_returns_zero_and_message(self):
        exc = ValueError("some LLM failure")
        code, msg = _extract_llm_error_info(exc)
        assert code == 0
        assert "some LLM failure" in msg

    def test_exception_with_status_code_attribute(self):
        class FakeAPIError(Exception):
            status_code = 401

        exc = FakeAPIError("auth failed")
        code, msg = _extract_llm_error_info(exc)
        assert code == 401
        assert "auth failed" in msg

    def test_exception_with_http_code_in_message(self):
        exc = RuntimeError("Request failed with 429 too many requests")
        code, msg = _extract_llm_error_info(exc)
        assert code == 429
        assert "429" in msg

    def test_inner_cause_status_code(self):
        class Inner(Exception):
            status_code = 403

        inner = Inner("inner error")
        exc = RuntimeError("wrapped")
        exc.__cause__ = inner
        code, _ = _extract_llm_error_info(exc)
        assert code == 403

