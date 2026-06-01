"""Core types for the reconciliation framework."""

from __future__ import annotations

import enum
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


class ResourceStatus(enum.StrEnum):
    UNKNOWN = "unknown"
    CHECKING = "checking"
    DRIFTED = "drifted"
    APPLYING = "applying"
    VERIFIED = "verified"
    FAILED = "failed"
    SKIPPED = "skipped"
    DISABLED = "disabled"


class FailureAction(enum.StrEnum):
    FAIL_STARTUP = "fail_startup"
    DISABLE_FEATURE = "disable_feature"
    WARN_ONLY = "warn_only"


class ResourceType(enum.StrEnum):
    DIRECTORY = "directory"
    FILE = "file"
    REMOTE_ASSET = "remote_asset"
    DATABASE_SEED = "database_seed"
    FEATURE_FLAG = "feature_flag"


@dataclass
class ResourceResult:
    """Outcome of a check/apply/verify cycle for one resource."""

    resource_name: str
    resource_type: ResourceType
    desired_version: str
    current_version: str | None = None
    status: ResourceStatus = ResourceStatus.UNKNOWN
    changed: bool = False
    critical: bool = True
    feature_disabled: str | None = None
    error: str | None = None
    remediation_hint: str | None = None
    offline_steps: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)
    checked_at: datetime | None = None
    applied_at: datetime | None = None
    verified_at: datetime | None = None


@dataclass
class ReconcileReport:
    """Aggregate report from a full reconciliation run."""

    mode: str
    started_at: datetime
    finished_at: datetime | None = None
    results: list[ResourceResult] = field(default_factory=list)
    success: bool = True
    critical_failures: int = 0
    warnings: int = 0
    features_disabled: list[str] = field(default_factory=list)

    def to_dict(self) -> list[dict[str, Any]]:
        out = []
        for r in self.results:
            out.append({
                "resource_name": r.resource_name,
                "resource_type": r.resource_type.value,
                "desired_version": r.desired_version,
                "current_version": r.current_version,
                "status": r.status.value,
                "changed": r.changed,
                "critical": r.critical,
                "feature_disabled": r.feature_disabled,
                "error": r.error,
                "remediation_hint": r.remediation_hint,
                "offline_steps": r.offline_steps,
            })
        return out

    def summary_text(self) -> str:
        lines = [
            f"Reconciliation Report ({self.mode})",
            f"  Started:  {self.started_at.isoformat()}",
            f"  Finished: {self.finished_at.isoformat() if self.finished_at else 'N/A'}",
            f"  Total resources: {len(self.results)}",
            f"  Verified: {sum(1 for r in self.results if r.status == ResourceStatus.VERIFIED)}",
            f"  Failed:   {self.critical_failures}",
            f"  Warnings: {self.warnings}",
        ]
        if self.features_disabled:
            lines.append(f"  Features disabled: {', '.join(self.features_disabled)}")

        failed = [r for r in self.results if r.status == ResourceStatus.FAILED]
        if failed:
            lines.append("")
            lines.append("  Failures:")
            for r in failed:
                crit = "[CRITICAL]" if r.critical else "[non-critical]"
                lines.append(f"    {crit} {r.resource_name}: {r.error}")
                if r.remediation_hint:
                    lines.append(f"           Fix: {r.remediation_hint}")
                if r.offline_steps:
                    lines.append("           Offline steps:")
                    for step in r.offline_steps:
                        lines.append(f"             - {step}")
        return "\n".join(lines)
