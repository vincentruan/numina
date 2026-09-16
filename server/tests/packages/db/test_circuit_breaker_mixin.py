"""Tests for CircuitBreakerMixin column inheritance and defaults.

Verifies that all three provider models expose the 9 FSM columns with
correct types, defaults, and nullability after the mixin extraction.
"""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from packages.db.mixins import CircuitBreakerMixin

# Backend models registered on the shared Base — imported for metadata.
from apps.backend.app.models.ai_provider_config import AIProviderConfig
from apps.backend.app.models.family_web_search_provider import FamilyWebSearchProvider
from apps.backend.app.models.asr_provider_config import ASRProviderConfig

# Column names the mixin must provide.
MIXIN_COLUMNS = [
    "circuit_state",
    "circuit_reason",
    "recovery_schedule",
    "last_failure_type",
    "half_open_success_count",
    "half_open_failure_count",
    "half_open_window_start",
    "failure_count",
    "last_failure_at",
]


class TestMixinColumnsPresent:
    """Each model using the mixin must have all 9 FSM columns."""

    @pytest.mark.parametrize(
        "model_cls",
        [AIProviderConfig, FamilyWebSearchProvider, ASRProviderConfig],
        ids=["AIProviderConfig", "FamilyWebSearchProvider", "ASRProviderConfig"],
    )
    def test_all_nine_columns_exist(self, model_cls):
        mapper = model_cls.__table__
        col_names = {c.name for c in mapper.columns}
        for col_name in MIXIN_COLUMNS:
            assert col_name in col_names, (
                f"{model_cls.__name__} missing column {col_name!r}"
            )


class TestMixinDefaults:
    """Defaults must match the original inline definitions."""

    def _col(self, model_cls, name):
        return model_cls.__table__.columns[name]

    @pytest.mark.parametrize(
        "model_cls",
        [AIProviderConfig, FamilyWebSearchProvider, ASRProviderConfig],
    )
    def test_circuit_state_default_closed(self, model_cls):
        col = self._col(model_cls, "circuit_state")
        assert col.default.arg == "closed"
        assert col.nullable is False

    @pytest.mark.parametrize(
        "model_cls",
        [AIProviderConfig, FamilyWebSearchProvider, ASRProviderConfig],
    )
    def test_nullable_string_columns(self, model_cls):
        for name in ("circuit_reason", "recovery_schedule", "last_failure_type"):
            col = self._col(model_cls, name)
            assert col.nullable is True

    @pytest.mark.parametrize(
        "model_cls",
        [AIProviderConfig, FamilyWebSearchProvider, ASRProviderConfig],
    )
    def test_integer_counters_default_zero(self, model_cls):
        for name in (
            "half_open_success_count",
            "half_open_failure_count",
            "failure_count",
        ):
            col = self._col(model_cls, name)
            assert col.default.arg == 0
            assert col.nullable is False

    @pytest.mark.parametrize(
        "model_cls",
        [AIProviderConfig, FamilyWebSearchProvider, ASRProviderConfig],
    )
    def test_datetime_columns_nullable(self, model_cls):
        for name in ("half_open_window_start", "last_failure_at"):
            col = self._col(model_cls, name)
            assert col.nullable is True


class TestMixinFSMOperations:
    """CircuitBreakerFSM must work on mixin-equipped model instances."""

    def test_record_failure_on_ai_provider(self, packages_db):
        """Simulate a transient failure cycle on AIProviderConfig."""
        from apps.backend.app.services.circuit_breaker.config import CircuitBreakerConfig
        from apps.backend.app.services.circuit_breaker.fsm import CircuitBreakerFSM
        from apps.backend.app.services.circuit_breaker.types import FailureKind

        config = CircuitBreakerConfig()
        now = datetime(2026, 9, 15, tzinfo=timezone.utc)

        cfg = AIProviderConfig(
            id=1,
            family_id=1,
            name="test",
            provider="openai",
        )
        packages_db.add(cfg)
        packages_db.flush()

        assert cfg.circuit_state == "closed"

        # Record failures up to threshold
        for _ in range(config.transient_failure_threshold):
            t = CircuitBreakerFSM.record_failure(cfg, FailureKind.TRANSIENT_RATE_LIMIT, config, now)

        assert cfg.circuit_state == "open"
        assert cfg.circuit_reason == "transient_rate_limit"
        assert cfg.failure_count == config.transient_failure_threshold

    def test_reset_clears_all_fields(self, packages_db):
        """FSM.reset() must zero all counters on any mixin model."""
        from apps.backend.app.services.circuit_breaker.fsm import CircuitBreakerFSM

        provider = FamilyWebSearchProvider(
            id=1,
            family_id=1,
            provider_name="test",
        )
        packages_db.add(provider)
        packages_db.flush()

        # Manually set some state
        provider.circuit_state = "open"
        provider.circuit_reason = "transient"
        provider.failure_count = 5
        provider.last_failure_type = "transient_rate_limit"
        packages_db.flush()

        CircuitBreakerFSM.reset(provider)

        assert provider.circuit_state == "closed"
        assert provider.circuit_reason is None
        assert provider.failure_count == 0
        assert provider.last_failure_type is None
        assert provider.last_failure_at is None
        assert provider.half_open_success_count == 0
        assert provider.half_open_failure_count == 0
        assert provider.half_open_window_start is None

    def test_asr_provider_has_full_fsm_fields(self, packages_db):
        """ASRProviderConfig gains the 6 new FSM fields via the mixin."""
        asr = ASRProviderConfig(
            id=1,
            family_id=1,
            name="test-asr",
            provider="openai",
        )
        packages_db.add(asr)
        packages_db.flush()

        # All mixin fields should have their defaults
        assert asr.circuit_state == "closed"
        assert asr.circuit_reason is None
        assert asr.recovery_schedule is None
        assert asr.last_failure_type is None
        assert asr.half_open_success_count == 0
        assert asr.half_open_failure_count == 0
        assert asr.half_open_window_start is None
        assert asr.failure_count == 0
        assert asr.last_failure_at is None
