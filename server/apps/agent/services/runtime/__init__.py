"""Numina runtime layer — StreamBridge, RunManager, SSE gateway, sandbox, and GC.

This package wraps DeerFlow's runtime classes with Numina-specific multi-tenant
(family_id) integration and FastAPI lifecycle management.

# [Copied from DeerFlow Reference] — re-exports from deerflow.runtime
# [Integrated with Numina Multi-Tenant] — Numina-specific extensions

Submodules are imported lazily (by the caller) rather than eagerly here,
because later tasks in this implementation phase create new files that the
index cannot resolve until they exist.
"""

from deerflow.runtime import (
    END_SENTINEL,
    HEARTBEAT_SENTINEL,
    ConflictError,
    DisconnectMode,
    MemoryStreamBridge,
    RunContext,
    RunManager,
    RunRecord,
    RunStatus,
    StreamBridge,
    StreamEvent,
    UnsupportedStrategyError,
    run_agent,
)

from .gc import drain_inflight_runs, reconcile_orphaned_runs, schedule_run_cleanup
from .lifespan import get_run_manager, get_stream_bridge, init_runtime, shutdown_runtime
from .sandbox_provider import NuminaLocalSandboxProvider, acquire_family_sandbox
from .sse_gateway import format_sse, sse_consumer, start_run
from .subagent_registry import FamilySubagentRegistry, get_family_subagent_registry
from .worker import run_agent

__all__ = [
    # DeerFlow re-exports
    "ConflictError",
    "DisconnectMode",
    "END_SENTINEL",
    "HEARTBEAT_SENTINEL",
    "MemoryStreamBridge",
    "RunContext",
    "RunManager",
    "RunRecord",
    "RunStatus",
    "StreamBridge",
    "StreamEvent",
    "UnsupportedStrategyError",
    "run_agent",
    # Numina extensions
    "drain_inflight_runs",
    "FamilySubagentRegistry",
    "format_sse",
    "get_family_subagent_registry",
    "get_run_manager",
    "get_stream_bridge",
    "init_runtime",
    "NuminaLocalSandboxProvider",
    "acquire_family_sandbox",
    "reconcile_orphaned_runs",
    "run_agent",
    "schedule_run_cleanup",
    "shutdown_runtime",
    "sse_consumer",
    "start_run",
]
