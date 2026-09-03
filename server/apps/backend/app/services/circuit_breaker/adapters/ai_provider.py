"""AI Provider Config circuit breaker adapter."""

from datetime import UTC, datetime, timedelta

from sqlalchemy.orm import Session

from apps.backend.app.models.ai_provider_config import AIProviderConfig
from apps.backend.app.services.circuit_breaker.adapters.base import (
    CircuitBreakerAdapter,
)
from apps.backend.app.services.circuit_breaker.config import CircuitBreakerConfig
from apps.backend.app.services.circuit_breaker.fsm import CircuitBreakerFSM, Transition
from apps.backend.app.services.circuit_breaker.types import FailureKind, State


class AIProviderAdapter(CircuitBreakerAdapter):
    """Adapter for AIProviderConfig entity.

    Uses schedule-based recovery with 5-minute half_open window and
    success-rate based resolution (80% threshold).

    Delegates record_failure and evaluate_half_open_window to the shared FSM.
    Keeps custom attempt_recovery (schedule-based, not cooldown-based) and
    record_half_open_result (per-result recording, not window-based).

    Syncs legacy boolean fields (circuit_open, circuit_open_until) via
    on_transition() on every state change.
    """

    # Fallback recovery cooldown when both recovery_schedule and
    # circuit_open_until are NULL (e.g. permanent_account opens the circuit
    # with no recovery trigger).  Prevents providers from being stuck in
    # "open" forever — after this many seconds since last_failure_at the
    # circuit transitions to half_open for a single recovery probe.
    DEFAULT_RECOVERY_COOLDOWN_SECONDS = 24 * 3600  # 24 hours

    def __init__(self, config_id: int, family_id: int) -> None:
        self._config_id = config_id
        self._family_id = family_id
        self._config: AIProviderConfig | None = None

    def bind(self, entity: object) -> None:
        """Bind a pre-loaded AIProviderConfig to skip the DB query."""
        self._config = entity  # type: ignore[assignment]

    def get_config(self) -> CircuitBreakerConfig:
        """Return config matching AI Provider behavior."""
        return CircuitBreakerConfig(
            transient_failure_threshold=5,
            half_open_success_threshold=3,  # Not used (uses rate-based)
            half_open_window_seconds=300,  # 5-minute window
            half_open_success_rate_threshold=0.8,  # 80% success rate
            recovery_cooldown_seconds=60,  # Not used (uses schedule-based)
        )

    def load_entity(self, db: Session) -> AIProviderConfig | None:
        """Load config by ID with family isolation and row lock.

        If bind() was already called, returns the bound entity without
        a redundant DB query.
        """
        if self._config is not None:
            return self._config
        self._config = (
            db.query(AIProviderConfig)
            .filter(
                AIProviderConfig.id == self._config_id,
                AIProviderConfig.family_id == self._family_id,
            )
            .with_for_update()
            .first()
        )
        return self._config

    def persist(self, db: Session) -> None:
        """Commit changes to DB."""
        db.commit()

    def on_transition(self, transition: Transition, db: Session) -> None:
        """Sync legacy boolean fields on every state transition.

        circuit_open: True when open or half_open, False when closed.
        circuit_open_until: None for permanent failures (manual recovery),
            now+1h for transient failures (auto-recovery fallback).
        circuit_reason: normalized to "transient" for transient failures
            (agent-facing API), while last_failure_type retains the specific
            FailureKind for diagnostics.
        """
        del db  # unused
        if self._config is None:
            return

        new_state = transition.new_state

        # Sync circuit_open boolean
        self._config.circuit_open = new_state in (State.OPEN, State.HALF_OPEN)

        if new_state == State.OPEN:
            failure_type = self._config.last_failure_type
            if failure_type and failure_type.startswith("permanent_"):
                self._config.circuit_open_until = None  # Manual recovery only
            else:
                self._config.circuit_open_until = datetime.now(UTC).replace(
                    tzinfo=None
                ) + timedelta(hours=1)
                # Normalize circuit_reason to "transient" for agent-facing API
                self._config.circuit_reason = "transient"
        elif new_state == State.CLOSED:
            self._config.circuit_open_until = None

    def record_failure(self, failure_type: str, db: Session) -> dict:
        """Record a failure event. Delegates to shared FSM."""
        entity = self.load_entity(db)
        if entity is None:
            return {
                "circuit_state": "closed",
                "circuit_reason": None,
                "failure_count": 0,
            }

        config = self.get_config()
        transition = CircuitBreakerFSM.record_failure(
            entity,
            FailureKind(failure_type),
            config,
            datetime.now(UTC).replace(tzinfo=None),
        )

        if transition.changed:
            self.on_transition(transition, db)
        self.persist(db)
        return self._status(entity)

    def attempt_recovery(self, db: Session) -> bool:
        """Check if open circuit should transition to half_open.

        Uses recovery_schedule matching (e.g., ":01,:31" for minute patterns)
        or legacy circuit_open_until expiration as triggers. State mutation
        is delegated to FSM.transition_to_half_open; legacy field sync via
        on_transition().

        When both triggers are absent (e.g. ``permanent_account`` sets
        ``circuit_open_until=None`` and ``recovery_schedule`` is never
        configured), falls back to a time-based cooldown of
        ``DEFAULT_RECOVERY_COOLDOWN_SECONDS`` (24 h) since ``last_failure_at``
        so providers don't stay stuck in "open" forever.
        """
        if self._config is None:
            self.load_entity(db)
        if self._config is None:
            return False

        if self._config.circuit_state != "open":
            return False

        now = datetime.now(UTC).replace(tzinfo=None)

        # Check recovery schedule first (adapter-specific trigger)
        schedule_match = (
            self._config.recovery_schedule
            and _check_recovery_schedule_match(self._config.recovery_schedule, now)
        )

        # Check legacy circuit_open_until expiration (adapter-specific trigger)
        legacy_expired = (
            self._config.circuit_open_until is not None
            and self._config.circuit_open_until <= now
        )

        # Fallback: when both primary triggers are absent (e.g. permanent_account
        # with no recovery_schedule), use a generous time-based cooldown since
        # last_failure_at so the provider eventually gets a recovery probe.
        fallback_cooldown_expired = (
            not schedule_match
            and not legacy_expired
            and not self._config.recovery_schedule
            and self._config.circuit_open_until is None
            and self._config.last_failure_at is not None
            and now - self._config.last_failure_at.replace(tzinfo=None)
            >= timedelta(seconds=self.DEFAULT_RECOVERY_COOLDOWN_SECONDS)
        )

        if not schedule_match and not legacy_expired and not fallback_cooldown_expired:
            return False

        # Delegate state mutation to FSM
        transition = CircuitBreakerFSM.transition_to_half_open(self._config, now)

        # Adapter-specific: clear legacy circuit_open_until on expiration path
        if legacy_expired and not schedule_match:
            self._config.circuit_open_until = None

        # Sync legacy boolean fields
        self.on_transition(transition, db)
        db.commit()
        return True

    def evaluate_half_open_window(self, db: Session) -> Transition | None:
        """Check if half_open window expired and decide outcome.

        Delegates to shared FSM for rate-based evaluation, then syncs
        legacy fields via on_transition().

        Returns Transition if window expired, None otherwise.
        """
        entity = self.load_entity(db)
        if entity is None:
            return None

        if entity.circuit_state != "half_open":
            return None

        config = self.get_config()
        transition = CircuitBreakerFSM.evaluate_half_open_window(
            entity, config, datetime.now(UTC).replace(tzinfo=None)
        )

        if transition.changed:
            self.on_transition(transition, db)
            self.persist(db)
            return transition

        return None

    def record_half_open_result(self, success: bool, db: Session) -> dict:
        """Record a result during half_open state.

        Failure path delegates to FSM (half_open → open immediate re-open).
        Success path is adapter-specific: just increment the counter.
        The AIProvider uses rate-based window evaluation (evaluate_half_open_window),
        not count-based threshold, so success doesn't close the circuit here.

        Returns status dict with updated counts.
        """
        if self._config is None:
            self.load_entity(db)
        if self._config is None:
            return {"circuit_state": "closed", "half_open_success_count": 0}

        if self._config.circuit_state != "half_open":
            # Return current state but don't record
            return {
                "circuit_state": self._config.circuit_state,
                "half_open_success_count": self._config.half_open_success_count,
                "half_open_failure_count": self._config.half_open_failure_count,
            }

        if success:
            # Adapter-specific: just increment; rate-based evaluation is separate
            self._config.half_open_success_count = (
                self._config.half_open_success_count or 0
            ) + 1
        else:
            # Delegate to FSM: half_open → open on any failure
            transition = CircuitBreakerFSM.record_failure(
                self._config,
                FailureKind.TRANSIENT_SERVER,
                self.get_config(),
                datetime.now(UTC).replace(tzinfo=None),
            )
            # Sync legacy boolean fields via on_transition
            if transition.changed:
                self.on_transition(transition, db)

        db.commit()
        return {
            "ok": True,
            "half_open_success_count": self._config.half_open_success_count,
            "half_open_failure_count": self._config.half_open_failure_count,
            "circuit_state": self._config.circuit_state,
        }


def _check_recovery_schedule_match(schedule: str, now: datetime) -> bool:
    """Check if current time matches recovery schedule pattern.

    Schedule format: comma-separated minute patterns like ":01,:31"
    Matches if current minute ends with any of the patterns.
    """
    if not schedule:
        return False

    patterns = [p.strip() for p in schedule.split(",")]
    current_minute = now.minute

    for pattern in patterns:
        if pattern.startswith(":"):
            # Pattern like ":01" means minute ends with "01"
            suffix = pattern[1:]
            if str(current_minute).zfill(2).endswith(suffix):
                return True

    return False
