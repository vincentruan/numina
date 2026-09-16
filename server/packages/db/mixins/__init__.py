"""Shared ORM mixins for the Numina data model."""

from packages.db.mixins.archivable import ArchivableMixin
from packages.db.mixins.circuit_breaker import CircuitBreakerMixin

__all__ = ["CircuitBreakerMixin", "ArchivableMixin"]
