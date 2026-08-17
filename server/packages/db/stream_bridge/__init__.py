"""StreamBridge abstraction for Numina AI task resilience.

Re-exports DeerFlow's StreamBridge protocol and provides Numina-specific
implementations with tenant isolation (family_id in Redis keys).

The bridge decouples agent workers (event producers) from SSE endpoints
(event consumers), enabling cross-process SSE reconnection via Redis Streams.
"""

from __future__ import annotations

# Re-export DeerFlow's base protocol
from deerflow.runtime.stream_bridge import (
    END_SENTINEL,
    HEARTBEAT_SENTINEL,
    MemoryStreamBridge,
    StreamBridge,
    StreamEvent,
    StreamGap,
    StreamItem,
)
from deerflow.runtime.stream_bridge import (
    make_stream_bridge as deerflow_make_stream_bridge,
)

# Numina-specific Redis implementation with tenant isolation
# Import directly from .redis since DeerFlow intentionally doesn't export it
# (redis is an optional dependency)
from .config import StreamBridgeConfig
from .factory import make_stream_bridge
from .redis import NuminaRedisStreamBridge

__all__ = [
    "END_SENTINEL",
    "HEARTBEAT_SENTINEL",
    "MemoryStreamBridge",
    "NuminaRedisStreamBridge",
    "StreamBridge",
    "StreamBridgeConfig",
    "StreamEvent",
    "StreamGap",
    "StreamItem",
    "deerflow_make_stream_bridge",
    "make_stream_bridge",
]
