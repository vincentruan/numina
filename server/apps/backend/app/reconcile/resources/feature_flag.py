"""FeatureFlagResource — manages feature availability based on resource state."""

from __future__ import annotations

import logging
from collections.abc import Callable

from sqlalchemy.orm import Session

from apps.backend.app.reconcile.base import Resource
from apps.backend.app.reconcile.types import (
    FailureAction,
    ResourceResult,
    ResourceStatus,
    ResourceType,
)

logger = logging.getLogger(__name__)

# In-memory feature flag registry (runtime state)
_feature_flags: dict[str, bool] = {}
_disabled_reasons: dict[str, str] = {}


def is_feature_enabled(flag_name: str) -> bool:
    """Check if a feature is enabled. Defaults to True if not explicitly disabled."""
    return _feature_flags.get(flag_name, True)


def get_disabled_reason(flag_name: str) -> str | None:
    """Get the reason a feature was disabled, if any."""
    return _disabled_reasons.get(flag_name)


def disable_feature(flag_name: str, reason: str) -> None:
    """Disable a feature flag with a reason."""
    _feature_flags[flag_name] = False
    _disabled_reasons[flag_name] = reason
    logger.warning(f"Feature '{flag_name}' disabled: {reason}")


def enable_feature(flag_name: str) -> None:
    """Re-enable a previously disabled feature."""
    _feature_flags[flag_name] = True
    _disabled_reasons.pop(flag_name, None)
    logger.info(f"Feature '{flag_name}' re-enabled")


def get_all_flags() -> dict[str, dict]:
    """Return all known feature flags with their state."""
    all_flags = {}
    for name, enabled in _feature_flags.items():
        all_flags[name] = {
            "enabled": enabled,
            "reason": _disabled_reasons.get(name),
        }
    return all_flags


class FeatureFlagResource(Resource):
    """Manages a feature flag based on a condition check.

    When the condition is not met, the feature is disabled (not the startup).
    When the condition is met, the feature is enabled.
    """

    def __init__(
        self,
        name: str,
        flag_name: str,
        *,
        condition_fn: Callable[[Session | None], bool],
        desired_version: str = "1",
        disable_reason: str = "Required resource unavailable",
        recovery_hint: str | None = None,
    ):
        super().__init__(
            name=name,
            resource_type=ResourceType.FEATURE_FLAG,
            desired_version=desired_version,
            critical=False,
            failure_action=FailureAction.DISABLE_FEATURE,
            feature_flag=flag_name,
            offline_hint=recovery_hint,
        )
        self._flag_name = flag_name
        self._condition_fn = condition_fn
        self._disable_reason = disable_reason
        self._recovery_hint = recovery_hint

    def check(self, db: Session | None = None) -> ResourceResult:
        try:
            condition_met = self._condition_fn(db)
        except Exception as e:
            return self._drifted(
                current_version="error",
                metadata={"error": str(e)},
            )

        if condition_met:
            return self._verified(current_version="enabled")

        return self._drifted(
            current_version="disabled",
            metadata={"reason": self._disable_reason},
        )

    def apply(self, db: Session | None = None) -> ResourceResult:
        try:
            condition_met = self._condition_fn(db)
        except Exception as e:
            disable_feature(self._flag_name, f"{self._disable_reason} (check error: {e})")
            result = self._make_result(
                status=ResourceStatus.FAILED,
                current_version="disabled",
                feature_disabled=self._flag_name,
                error=str(e),
                remediation_hint=self._recovery_hint,
            )
            return result

        if condition_met:
            enable_feature(self._flag_name)
            return self._verified(current_version="enabled")

        disable_feature(self._flag_name, self._disable_reason)
        result = self._make_result(
            status=ResourceStatus.VERIFIED,
            current_version="disabled",
            feature_disabled=self._flag_name,
            metadata={"action": "feature_disabled", "reason": self._disable_reason},
        )
        return result

    def verify(self, db: Session | None = None) -> ResourceResult:
        return self.check(db)
