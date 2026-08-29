"""StreamBridge abstraction for Numina AI task resilience.

Self-contained implementation — no DeerFlow dependency.
Provides StreamBridge protocol, MemoryStreamBridge (in-process dev),
NuminaRedisStreamBridge (cross-process production with tenant isolation),
and factory/config utilities.

The bridge decouples agent workers (event producers) from SSE endpoints
(event consumers), enabling cross-process SSE reconnection via Redis Streams.
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
from .memory import MemoryStreamBridge
from .redis import NuminaRedisStreamBridge, RedisStreamBridge

__all__ = [
    "END_SENTINEL",
    "HEARTBEAT_SENTINEL",
    "MemoryStreamBridge",
    "NuminaRedisStreamBridge",
    "RedisStreamBridge",
    "StreamBridge",
    "StreamBridgeConfig",
    "StreamEvent",
    "StreamGap",
    "StreamItem",
    "make_stream_bridge",
]
