"""Behavioral configuration for circuit breaker instances."""

from dataclasses import dataclass


@dataclass(frozen=True)
class CircuitBreakerConfig:
    """Per-implementation behavioral knobs.

    The FSM is identical across all implementations; only the thresholds
    and recovery policy differ. Each adapter provides its own config.
    """

    # Failure threshold before opening circuit (for transient failures)
    transient_failure_threshold: int = 5

    # Success count threshold before closing circuit (from half_open)
    half_open_success_threshold: int = 3

    # Half-open window duration in seconds (Impl 1: 5-minute window)
    half_open_window_seconds: int = 300

    # Success rate threshold for half-open window expiry (Impl 1: 80%)
    half_open_success_rate_threshold: float = 0.8

    # Time-based cooldown before attempting recovery (Impl 2: 60 seconds)
    recovery_cooldown_seconds: int = 60

    # Auto-recovery time for temporary open states (Impl 3: rate_limited)
    auto_recovery_seconds: int | None = None

    # Whether this circuit requires manual reset (Impl 3: circuit_open)
    requires_manual_reset: bool = False
