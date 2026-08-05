"""Circuit breaker unified module.

This module provides a single three-state FSM (closed/open/half_open) with
thin per-entity adapters. All circuit breaker transition logic lives in the
FSM core; adapters handle entity-specific field mapping and side effects.
"""

from apps.backend.app.services.circuit_breaker.config import CircuitBreakerConfig
from apps.backend.app.services.circuit_breaker.fsm import CircuitBreakerFSM, Transition
from apps.backend.app.services.circuit_breaker.types import FailureKind, State

__all__ = [
    "CircuitBreakerFSM",
    "CircuitBreakerConfig",
    "FailureKind",
    "State",
    "Transition",
]
