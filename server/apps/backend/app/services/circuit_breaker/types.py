"""Enumerations for the unified circuit breaker FSM."""

from enum import StrEnum


class State(StrEnum):
    """Three-state circuit breaker states."""

    CLOSED = "closed"  # healthy, full traffic
    OPEN = "open"  # tripped, zero traffic
    HALF_OPEN = "half_open"  # probing recovery, limited traffic


class FailureKind(StrEnum):
    """Unified failure classification.

    Permanent errors open immediately with no auto-recovery.
    Transient errors accumulate toward threshold.
    """

    TRANSIENT_RATE_LIMIT = "transient_rate_limit"
    TRANSIENT_SERVER = "transient_server"
    TRANSIENT_TIMEOUT = "transient_timeout"
    TRANSIENT_NETWORK = "transient_network"
    PERMANENT_AUTH = "permanent_auth"
    PERMANENT_ACCOUNT = "permanent_account"

    @property
    def is_permanent(self) -> bool:
        """Return True if this failure kind should open the circuit immediately."""
        return self.value.startswith("permanent_")
