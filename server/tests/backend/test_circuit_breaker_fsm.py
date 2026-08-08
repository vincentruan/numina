"""Unit tests for the pure circuit breaker FSM.

These tests verify the state machine logic without any database dependency.
Uses simple dataclass mocks instead of SQLAlchemy entities.
"""

from dataclasses import dataclass
from datetime import datetime, timedelta

import pytest

from apps.backend.app.services.circuit_breaker.config import CircuitBreakerConfig
from apps.backend.app.services.circuit_breaker.fsm import CircuitBreakerFSM
from apps.backend.app.services.circuit_breaker.types import FailureKind, State


@dataclass
class MockEntity:
    """Mock entity satisfying CircuitBreakerFields protocol."""

    circuit_state: str = "closed"
    circuit_reason: str | None = None
    failure_count: int = 0
    last_failure_at: datetime | None = None
    last_failure_type: str | None = None
    half_open_success_count: int = 0
    half_open_failure_count: int = 0
    half_open_window_start: datetime | None = None


@pytest.fixture
def default_config() -> CircuitBreakerConfig:
    """Default config matching Impl 2 (WebSearch)."""
    return CircuitBreakerConfig(
        transient_failure_threshold=5,
        half_open_success_threshold=3,
        recovery_cooldown_seconds=60,
    )


@pytest.fixture
def impl1_config() -> CircuitBreakerConfig:
    """Config matching Impl 1 (AI Provider)."""
    return CircuitBreakerConfig(
        transient_failure_threshold=5,
        half_open_success_threshold=3,
        half_open_window_seconds=300,
        half_open_success_rate_threshold=0.8,
        recovery_cooldown_seconds=60,
    )


class TestRecordFailure:
    """Tests for record_failure transitions."""

    def test_permanent_failure_opens_immediately(
        self, default_config: CircuitBreakerConfig
    ) -> None:
        """Permanent auth failure should open circuit immediately."""
        entity = MockEntity()
        now = datetime.now()

        transition = CircuitBreakerFSM.record_failure(
            entity, FailureKind.PERMANENT_AUTH, default_config, now
        )

        assert transition.old_state == State.CLOSED
        assert transition.new_state == State.OPEN
        assert transition.changed is True
        assert transition.reason == "permanent_auth"
        assert entity.circuit_state == "open"
        assert entity.circuit_reason == "permanent_auth"

    def test_transient_failure_below_threshold_stays_closed(
        self, default_config: CircuitBreakerConfig
    ) -> None:
        """Transient failure below threshold should stay closed."""
        entity = MockEntity()
        now = datetime.now()

        transition = CircuitBreakerFSM.record_failure(
            entity, FailureKind.TRANSIENT_RATE_LIMIT, default_config, now
        )

        assert transition.old_state == State.CLOSED
        assert transition.new_state == State.CLOSED
        assert transition.changed is False
        assert entity.circuit_state == "closed"
        assert entity.failure_count == 1

    def test_transient_failure_at_threshold_opens(
        self, default_config: CircuitBreakerConfig
    ) -> None:
        """Transient failures reaching threshold should open circuit."""
        entity = MockEntity(failure_count=4)
        now = datetime.now()

        transition = CircuitBreakerFSM.record_failure(
            entity, FailureKind.TRANSIENT_RATE_LIMIT, default_config, now
        )

        assert transition.old_state == State.CLOSED
        assert transition.new_state == State.OPEN
        assert transition.changed is True
        assert entity.circuit_state == "open"
        assert entity.failure_count == 5

    def test_half_open_failure_reopens_immediately(
        self, default_config: CircuitBreakerConfig
    ) -> None:
        """Failure during half_open should immediately re-open."""
        entity = MockEntity(
            circuit_state="half_open",
            half_open_window_start=datetime.now(),
        )
        now = datetime.now()

        transition = CircuitBreakerFSM.record_failure(
            entity, FailureKind.TRANSIENT_SERVER, default_config, now
        )

        assert transition.old_state == State.HALF_OPEN
        assert transition.new_state == State.OPEN
        assert transition.changed is True
        assert entity.circuit_state == "open"
        assert entity.half_open_success_count == 0


class TestRecordSuccess:
    """Tests for record_success transitions."""

    def test_success_in_closed_decays_failure_count(
        self, default_config: CircuitBreakerConfig
    ) -> None:
        """Success in closed state should decay failure count."""
        entity = MockEntity(failure_count=3)
        now = datetime.now()

        transition = CircuitBreakerFSM.record_success(entity, default_config, now)

        assert transition.old_state == State.CLOSED
        assert transition.new_state == State.CLOSED
        assert transition.changed is False
        assert entity.failure_count == 2

    def test_half_open_success_below_threshold_stays_half_open(
        self, default_config: CircuitBreakerConfig
    ) -> None:
        """Success in half_open below threshold should stay half_open."""
        entity = MockEntity(
            circuit_state="half_open",
            half_open_success_count=1,
            half_open_window_start=datetime.now(),
        )
        now = datetime.now()

        transition = CircuitBreakerFSM.record_success(entity, default_config, now)

        assert transition.old_state == State.HALF_OPEN
        assert transition.new_state == State.HALF_OPEN
        assert transition.changed is False
        assert entity.half_open_success_count == 2

    def test_half_open_success_threshold_closes(
        self, default_config: CircuitBreakerConfig
    ) -> None:
        """Success reaching threshold in half_open should close circuit."""
        entity = MockEntity(
            circuit_state="half_open",
            half_open_success_count=2,
            half_open_window_start=datetime.now(),
        )
        now = datetime.now()

        transition = CircuitBreakerFSM.record_success(entity, default_config, now)

        assert transition.old_state == State.HALF_OPEN
        assert transition.new_state == State.CLOSED
        assert transition.changed is True
        assert entity.circuit_state == "closed"
        assert entity.failure_count == 0
        assert entity.half_open_success_count == 0


class TestAttemptRecovery:
    """Tests for attempt_recovery transitions."""

    def test_open_to_half_open_on_recovery_time(
        self, default_config: CircuitBreakerConfig
    ) -> None:
        """Open circuit should transition to half_open after cooldown."""
        entity = MockEntity(
            circuit_state="open",
            last_failure_at=datetime.now() - timedelta(seconds=120),
        )
        now = datetime.now()

        transition = CircuitBreakerFSM.attempt_recovery(entity, default_config, now)

        assert transition.old_state == State.OPEN
        assert transition.new_state == State.HALF_OPEN
        assert transition.changed is True
        assert entity.circuit_state == "half_open"
        assert entity.half_open_success_count == 0

    def test_permanent_failure_no_recovery(
        self, default_config: CircuitBreakerConfig
    ) -> None:
        """Permanent failure should not auto-recover."""
        entity = MockEntity(
            circuit_state="open",
            circuit_reason="permanent_auth",
            last_failure_at=datetime.now() - timedelta(seconds=120),
        )
        now = datetime.now()

        transition = CircuitBreakerFSM.attempt_recovery(entity, default_config, now)

        assert transition.changed is False
        assert entity.circuit_state == "open"

    def test_before_cooldown_stays_open(
        self, default_config: CircuitBreakerConfig
    ) -> None:
        """Before cooldown elapsed should stay open."""
        entity = MockEntity(
            circuit_state="open",
            last_failure_at=datetime.now() - timedelta(seconds=30),
        )
        now = datetime.now()

        transition = CircuitBreakerFSM.attempt_recovery(entity, default_config, now)

        assert transition.changed is False
        assert entity.circuit_state == "open"


class TestTransitionToHalfOpen:
    """Tests for transition_to_half_open (adapter trigger delegation)."""

    def test_open_transitions_to_half_open(self) -> None:
        """transition_to_half_open should set state and reset counters."""
        entity = MockEntity(
            circuit_state="open",
            circuit_reason="transient_rate_limit",
            half_open_success_count=5,
            half_open_failure_count=3,
        )
        now = datetime.now()

        transition = CircuitBreakerFSM.transition_to_half_open(entity, now)

        assert transition.old_state == State.OPEN
        assert transition.new_state == State.HALF_OPEN
        assert transition.changed is True
        assert entity.circuit_state == "half_open"
        assert entity.half_open_success_count == 0
        assert entity.half_open_failure_count == 0
        assert entity.half_open_window_start == now


class TestEvaluateHalfOpenWindow:
    """Tests for evaluate_half_open_window (Impl 1 specific)."""

    def test_window_expiry_success_rate_closes(
        self, impl1_config: CircuitBreakerConfig
    ) -> None:
        """Window expiry with high success rate should close."""
        entity = MockEntity(
            circuit_state="half_open",
            half_open_success_count=8,
            half_open_failure_count=2,
            half_open_window_start=datetime.now() - timedelta(seconds=360),
        )
        now = datetime.now()

        transition = CircuitBreakerFSM.evaluate_half_open_window(
            entity, impl1_config, now
        )

        assert transition.old_state == State.HALF_OPEN
        assert transition.new_state == State.CLOSED
        assert transition.changed is True
        assert entity.circuit_state == "closed"

    def test_window_expiry_failure_reopens(
        self, impl1_config: CircuitBreakerConfig
    ) -> None:
        """Window expiry with low success rate should re-open."""
        entity = MockEntity(
            circuit_state="half_open",
            half_open_success_count=2,
            half_open_failure_count=8,
            half_open_window_start=datetime.now() - timedelta(seconds=360),
        )
        now = datetime.now()

        transition = CircuitBreakerFSM.evaluate_half_open_window(
            entity, impl1_config, now
        )

        assert transition.old_state == State.HALF_OPEN
        assert transition.new_state == State.OPEN
        assert transition.changed is True
        assert entity.circuit_state == "open"
        assert transition.reason == "transient"

    def test_window_expiry_zero_results_reopens(
        self, impl1_config: CircuitBreakerConfig
    ) -> None:
        """Window expiry with zero results should re-open (no evidence of recovery)."""
        entity = MockEntity(
            circuit_state="half_open",
            half_open_success_count=0,
            half_open_failure_count=0,
            half_open_window_start=datetime.now() - timedelta(seconds=360),
        )
        now = datetime.now()

        transition = CircuitBreakerFSM.evaluate_half_open_window(
            entity, impl1_config, now
        )

        assert transition.changed is True
        assert entity.circuit_state == "open"
        assert transition.reason == "transient"


class TestReset:
    """Tests for reset transition."""

    def test_reset_clears_all_state(self) -> None:
        """Reset should clear all failure metadata."""
        entity = MockEntity(
            circuit_state="open",
            circuit_reason="transient_rate_limit",
            failure_count=10,
            last_failure_at=datetime.now(),
            last_failure_type="transient_rate_limit",
        )

        transition = CircuitBreakerFSM.reset(entity)

        assert transition.old_state == State.OPEN
        assert transition.new_state == State.CLOSED
        assert transition.changed is True
        assert entity.circuit_state == "closed"
        assert entity.circuit_reason is None
        assert entity.failure_count == 0
        assert entity.last_failure_type is None
        assert entity.last_failure_at is None
