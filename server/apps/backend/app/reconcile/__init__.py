"""Desired State Reconciliation — ensures all system resources match expected state.

Unlike simple seed/bootstrap (which only checks "does it exist?"), reconciliation
performs full state comparison: define desired → inspect current → diff → apply → verify.

Each resource declares whether it is critical (blocks startup) or non-critical
(disables feature on failure). All operations are idempotent and safe for
concurrent multi-instance startup via distributed locking.
"""

from apps.backend.app.reconcile.runner import DesiredStateRunner, RunMode

__all__ = ["DesiredStateRunner", "RunMode"]
