"""Resource base class — the contract every resource handler must implement."""

from __future__ import annotations

import abc
from typing import TYPE_CHECKING

from apps.backend.app.reconcile.types import (
    FailureAction,
    ResourceResult,
    ResourceStatus,
    ResourceType,
)

if TYPE_CHECKING:
    from sqlalchemy.orm import Session


class Resource(abc.ABC):
    """Base class for all reconcilable resources.

    Subclasses implement check/apply/verify to define how the resource
    reaches its desired state. The runner calls these in sequence.
    """

    def __init__(
        self,
        name: str,
        resource_type: ResourceType,
        desired_version: str,
        *,
        critical: bool = True,
        failure_action: FailureAction = FailureAction.FAIL_STARTUP,
        feature_flag: str | None = None,
        offline_hint: str | None = None,
    ):
        self.name = name
        self.resource_type = resource_type
        self.desired_version = desired_version
        self.critical = critical
        self.failure_action = failure_action
        self.feature_flag = feature_flag
        self.offline_hint = offline_hint

    @abc.abstractmethod
    def check(self, db: Session | None = None) -> ResourceResult:
        """Inspect current state and compare with desired state.

        Returns a result with status VERIFIED (already correct),
        DRIFTED (needs apply), or FAILED (cannot determine).
        """

    @abc.abstractmethod
    def apply(self, db: Session | None = None) -> ResourceResult:
        """Bring the resource to desired state.

        Only called when check() returns DRIFTED.
        Must be idempotent — safe to call multiple times.
        """

    @abc.abstractmethod
    def verify(self, db: Session | None = None) -> ResourceResult:
        """Confirm the resource is in desired state after apply.

        Called after apply() to confirm success. Should be a pure read.
        """

    def _make_result(self, **kwargs) -> ResourceResult:
        """Helper to create a ResourceResult pre-filled with resource metadata."""
        return ResourceResult(
            resource_name=self.name,
            resource_type=self.resource_type,
            desired_version=self.desired_version,
            critical=self.critical,
            **kwargs,
        )

    def _verified(self, current_version: str | None = None, **kwargs) -> ResourceResult:
        return self._make_result(
            status=ResourceStatus.VERIFIED,
            current_version=current_version or self.desired_version,
            **kwargs,
        )

    def _drifted(self, current_version: str | None = None, **kwargs) -> ResourceResult:
        return self._make_result(
            status=ResourceStatus.DRIFTED,
            current_version=current_version,
            **kwargs,
        )

    def _failed(self, error: str, **kwargs) -> ResourceResult:
        return self._make_result(
            status=ResourceStatus.FAILED,
            error=error,
            remediation_hint=kwargs.pop("remediation_hint", self.offline_hint),
            **kwargs,
        )
