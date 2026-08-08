"""Pure three-state circuit breaker FSM.

This module contains the core state machine logic with zero database
dependencies. It operates on any object satisfying the CircuitBreakerFields
protocol via structural typing (duck typing).
"""

from dataclasses import dataclass
from datetime import datetime

from apps.backend.app.services.circuit_breaker.config import CircuitBreakerConfig
from apps.backend.app.services.circuit_breaker.types import FailureKind, State


@dataclass
class Transition:
    """Result of a state transition.

    Attributes:
        old_state: The state before the transition.
        new_state: The state after the transition.
        changed: Whether the state actually changed.
        reason: Optional reason for the transition (e.g., failure type).
    """

    old_state: State
    new_state: State
    changed: bool
    reason: str | None = None


class CircuitBreakerFSM:
    """Pure three-state FSM.

    Stateless - all state lives in the entity fields passed in/out via
    method arguments. The FSM answers: "given current fields and an event,
    what fields should change?" It does NOT persist anything.

    The entity must have these fields (CircuitBreakerFields protocol):
        circuit_state: str
        circuit_reason: str | None
        failure_count: int
        last_failure_at: datetime | None
        last_failure_type: str | None
        half_open_success_count: int
        half_open_failure_count: int
        half_open_window_start: datetime | None
    """

    @staticmethod
    def record_failure(
        entity: object,
        failure_type: FailureKind,
        config: CircuitBreakerConfig,
        now: datetime,
    ) -> Transition:
        """Record a failure event.

        Transitions:
        - half_open -> open (immediate re-open on any failure)
        - closed -> open (when permanent failure OR transient threshold reached)
        - closed -> closed (transient failure below threshold)
        """
        old_state = State(entity.circuit_state)  # type: ignore[attr-defined]

        # Update failure metadata
        entity.last_failure_type = failure_type.value  # type: ignore[attr-defined]
        entity.last_failure_at = now  # type: ignore[attr-defined]

        # Half-open failure: immediately re-open
        if old_state == State.HALF_OPEN:
            entity.half_open_failure_count += 1  # type: ignore[attr-defined]
            entity.circuit_state = State.OPEN.value  # type: ignore[attr-defined]
            entity.circuit_reason = failure_type.value  # type: ignore[attr-defined]
            entity.half_open_success_count = 0  # type: ignore[attr-defined]
            entity.half_open_window_start = None  # type: ignore[attr-defined]
            return Transition(
                old_state=old_state,
                new_state=State.OPEN,
                changed=True,
                reason=failure_type.value,
            )

        # Closed state: accumulate transient failures
        if old_state == State.CLOSED:
            entity.failure_count += 1  # type: ignore[attr-defined]

            # Permanent failure opens immediately
            if failure_type.is_permanent:
                entity.circuit_state = State.OPEN.value  # type: ignore[attr-defined]
                entity.circuit_reason = failure_type.value  # type: ignore[attr-defined]
                return Transition(
                    old_state=old_state,
                    new_state=State.OPEN,
                    changed=True,
                    reason=failure_type.value,
                )

            # Transient threshold reached
            if entity.failure_count >= config.transient_failure_threshold:  # type: ignore[attr-defined]
                entity.circuit_state = State.OPEN.value  # type: ignore[attr-defined]
                entity.circuit_reason = failure_type.value  # type: ignore[attr-defined]
                return Transition(
                    old_state=old_state,
                    new_state=State.OPEN,
                    changed=True,
                    reason=failure_type.value,
                )

            # Below threshold: stay closed
            return Transition(
                old_state=old_state,
                new_state=State.CLOSED,
                changed=False,
            )

        # Open state: no change (shouldn't normally receive failures)
        return Transition(
            old_state=old_state,
            new_state=State.OPEN,
            changed=False,
        )

    @staticmethod
    def record_success(
        entity: object,
        config: CircuitBreakerConfig,
        now: datetime,  # noqa: ARG004 - kept for API consistency
    ) -> Transition:
        """Record a success event.

        Transitions:
        - half_open -> closed (when success count threshold reached)
        - half_open -> half_open (success but threshold not yet reached)
        - closed -> closed (success with failure count decay)
        """
        old_state = State(entity.circuit_state)  # type: ignore[attr-defined]

        # Half-open success
        if old_state == State.HALF_OPEN:
            entity.half_open_success_count += 1  # type: ignore[attr-defined]

            # Threshold reached: close the circuit
            if entity.half_open_success_count >= config.half_open_success_threshold:  # type: ignore[attr-defined]
                entity.circuit_state = State.CLOSED.value  # type: ignore[attr-defined]
                entity.circuit_reason = None  # type: ignore[attr-defined]
                entity.failure_count = 0  # type: ignore[attr-defined]
                entity.half_open_success_count = 0  # type: ignore[attr-defined]
                entity.half_open_failure_count = 0  # type: ignore[attr-defined]
                entity.half_open_window_start = None  # type: ignore[attr-defined]
                entity.last_failure_type = None  # type: ignore[attr-defined]
                entity.last_failure_at = None  # type: ignore[attr-defined]
                return Transition(
                    old_state=old_state,
                    new_state=State.CLOSED,
                    changed=True,
                )

            # Below threshold: stay half-open
            return Transition(
                old_state=old_state,
                new_state=State.HALF_OPEN,
                changed=False,
            )

        # Closed state: decay failure count on success
        if old_state == State.CLOSED:
            if entity.failure_count > 0:  # type: ignore[attr-defined]
                entity.failure_count = max(0, entity.failure_count - 1)  # type: ignore[attr-defined]
                if entity.failure_count == 0:  # type: ignore[attr-defined]
                    entity.last_failure_type = None  # type: ignore[attr-defined]
                    entity.last_failure_at = None  # type: ignore[attr-defined]
                    entity.circuit_reason = None  # type: ignore[attr-defined]
            return Transition(
                old_state=old_state,
                new_state=State.CLOSED,
                changed=False,
            )

        # Open state: no change
        return Transition(
            old_state=old_state,
            new_state=State.OPEN,
            changed=False,
        )

    @staticmethod
    def attempt_recovery(
        entity: object,
        config: CircuitBreakerConfig,
        now: datetime,
    ) -> Transition:
        """Check if an open circuit should transition to half_open.

        This is called when checking provider availability. If enough time
        has passed since the last failure (per recovery_cooldown_seconds),
        transition to half_open to probe recovery.

        Returns:
            Transition with changed=True if moved to half_open.
        """
        old_state = State(entity.circuit_state)  # type: ignore[attr-defined]

        if old_state != State.OPEN:
            return Transition(
                old_state=old_state,
                new_state=old_state,
                changed=False,
            )

        # Permanent failures don't auto-recover
        if entity.circuit_reason and entity.circuit_reason.startswith("permanent_"):  # type: ignore[attr-defined]
            return Transition(
                old_state=old_state,
                new_state=old_state,
                changed=False,
            )

        # Check cooldown
        if entity.last_failure_at:  # type: ignore[attr-defined]
            elapsed = (now - entity.last_failure_at).total_seconds()  # type: ignore[attr-defined]
            if elapsed < config.recovery_cooldown_seconds:
                return Transition(
                    old_state=old_state,
                    new_state=State.OPEN,
                    changed=False,
                )

        # Transition to half_open
        entity.circuit_state = State.HALF_OPEN.value  # type: ignore[attr-defined]
        entity.half_open_success_count = 0  # type: ignore[attr-defined]
        entity.half_open_failure_count = 0  # type: ignore[attr-defined]
        entity.half_open_window_start = now  # type: ignore[attr-defined]
        return Transition(
            old_state=old_state,
            new_state=State.HALF_OPEN,
            changed=True,
        )

    @staticmethod
    def transition_to_half_open(entity: object, now: datetime) -> Transition:
        """Execute the open → half_open transition without trigger checks.

        Adapters with custom recovery triggers (e.g. AIProvider's schedule
        matching) call this after determining recovery should proceed.
        The FSM handles the state mutation; the adapter provides the trigger.
        """
        old_state = State(entity.circuit_state)  # type: ignore[attr-defined]
        entity.circuit_state = State.HALF_OPEN.value  # type: ignore[attr-defined]
        entity.half_open_success_count = 0  # type: ignore[attr-defined]
        entity.half_open_failure_count = 0  # type: ignore[attr-defined]
        entity.half_open_window_start = now  # type: ignore[attr-defined]
        return Transition(
            old_state=old_state,
            new_state=State.HALF_OPEN,
            changed=True,
        )

    @staticmethod
    def evaluate_half_open_window(
        entity: object,
        config: CircuitBreakerConfig,
        now: datetime,
    ) -> Transition:
        """Check if the half_open window has expired and decide outcome.

        When the window expires, calculate success rate. If above threshold,
        close the circuit. Otherwise, re-open it.

        This is used by Impl 1 (AI Provider) which uses success-rate based
        resolution rather than count-based.

        Note: If the window expires with zero recorded results (no successes,
        no failures), the success rate defaults to 0.0 — below any reasonable
        threshold — so the circuit re-opens. This is deliberate: absence of
        evidence is not evidence of recovery.

        Returns:
            Transition describing the outcome (close or re-open).
        """
        old_state = State(entity.circuit_state)  # type: ignore[attr-defined]

        if old_state != State.HALF_OPEN:
            return Transition(
                old_state=old_state,
                new_state=old_state,
                changed=False,
            )

        # Check if window expired
        window_start = entity.half_open_window_start  # type: ignore[attr-defined]
        if not window_start:
            return Transition(
                old_state=old_state,
                new_state=old_state,
                changed=False,
            )

        elapsed = (now - window_start).total_seconds()
        if elapsed < config.half_open_window_seconds:
            return Transition(
                old_state=old_state,
                new_state=old_state,
                changed=False,
            )

        # Window expired: calculate success rate
        total = entity.half_open_success_count + entity.half_open_failure_count  # type: ignore[attr-defined]
        success_rate = (
            entity.half_open_success_count / total if total > 0 else 0.0  # type: ignore[attr-defined]
        )

        if success_rate >= config.half_open_success_rate_threshold:
            # Success: close circuit
            entity.circuit_state = State.CLOSED.value  # type: ignore[attr-defined]
            entity.circuit_reason = None  # type: ignore[attr-defined]
            entity.failure_count = 0  # type: ignore[attr-defined]
            entity.half_open_success_count = 0  # type: ignore[attr-defined]
            entity.half_open_failure_count = 0  # type: ignore[attr-defined]
            entity.half_open_window_start = None  # type: ignore[attr-defined]
            entity.last_failure_type = None  # type: ignore[attr-defined]
            entity.last_failure_at = None  # type: ignore[attr-defined]
            return Transition(
                old_state=old_state,
                new_state=State.CLOSED,
                changed=True,
            )
        else:
            # Failure: re-open circuit
            entity.circuit_state = State.OPEN.value  # type: ignore[attr-defined]
            entity.circuit_reason = "transient"  # type: ignore[attr-defined]
            entity.half_open_window_start = None  # type: ignore[attr-defined]
            return Transition(
                old_state=old_state,
                new_state=State.OPEN,
                changed=True,
                reason="transient",
            )

    @staticmethod
    def reset(entity: object) -> Transition:
        """Manual reset to closed state.

        Clears all counters and failure metadata.
        """
        old_state = State(entity.circuit_state)  # type: ignore[attr-defined]

        entity.circuit_state = State.CLOSED.value  # type: ignore[attr-defined]
        entity.circuit_reason = None  # type: ignore[attr-defined]
        entity.failure_count = 0  # type: ignore[attr-defined]
        entity.last_failure_type = None  # type: ignore[attr-defined]
        entity.last_failure_at = None  # type: ignore[attr-defined]
        entity.half_open_success_count = 0  # type: ignore[attr-defined]
        entity.half_open_failure_count = 0  # type: ignore[attr-defined]
        entity.half_open_window_start = None  # type: ignore[attr-defined]

        return Transition(
            old_state=old_state,
            new_state=State.CLOSED,
            changed=old_state != State.CLOSED,
        )
