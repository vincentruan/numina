"""StreamBridge abstraction for Numina AI task resilience.

Self-contained implementation — no DeerFlow dependency.
Provides StreamBridge protocol and NuminaRedisStreamBridge (cross-process
production with tenant isolation), plus factory/config utilities.

The bridge decouples agent workers (event producers) from SSE endpoints
(event consumers), enabling cross-process SSE reconnection via Redis Streams.

Production always uses NuminaRedisStreamBridge.  A test-only
``MemoryStreamBridge`` lives under ``tests/agent/helpers/`` for unit tests
that should not depend on Redis.
"""

from __future__ import annotations

from .base import (
    END_SENTINEL,
    HEARTBEAT_SENTINEL,
    StreamBridge,
    StreamEvent,
    StreamGap,
    StreamItem,
)
from .config import StreamBridgeConfig
from .factory import make_stream_bridge
from .redis import NuminaRedisStreamBridge, RedisStreamBridge

__all__ = [
    "END_SENTINEL",
    "HEARTBEAT_SENTINEL",
    "NuminaRedisStreamBridge",
    "RedisStreamBridge",
    "StreamBridge",
    "StreamBridgeConfig",
    "StreamEvent",
    "StreamGap",
    "StreamItem",
    "make_stream_bridge",
]
