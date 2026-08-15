"""Numina-specific Redis Streams stream bridge with tenant isolation.

Wraps DeerFlow's RedisStreamBridge to add Numina-specific key prefixing.
Redis keys are namespaced as ``numina:stream:{run_id}`` where run_id is the
AITask primary key. Family_id is carried in event data for application-level
tenant isolation (queries scoped by family_id in AITask table).
"""

from __future__ import annotations

import logging
from typing import Any

from deerflow.runtime.stream_bridge.redis import RedisStreamBridge

logger = logging.getLogger(__name__)


class NuminaRedisStreamBridge(RedisStreamBridge):
    """Numina-flavored Redis Streams stream bridge.

    Inherits all of DeerFlow's RedisStreamBridge logic (XADD/XREAD, heartbeat,
    StreamGap detection, 24h TTL) and customizes the key prefix to
    ``numina:stream`` for Numina-specific Redis namespace isolation.

    The run_id parameter is the AITask primary key (task_id). Family_id is
    carried in event data payloads for application-level tenant isolation
    (backend queries scope by family_id in the AITask table).

    This is a thin subclass: no behavioral changes, just a different key prefix.
    """

    def __init__(
        self,
        *,
        redis_url: str,
        queue_maxsize: int = 256,
        stream_ttl_seconds: int = 86400,
        max_connections: int | None = None,
    ) -> None:
        """Initialize Numina Redis stream bridge.

        Args:
            redis_url: Redis connection URL (e.g., ``redis://redis:6379/0``).
            queue_maxsize: Max events retained per stream (default 256).
            stream_ttl_seconds: Stream TTL in seconds (default 86400 = 24h).
            max_connections: Max Redis connection pool size (None = unbounded).
        """
        super().__init__(
            redis_url=redis_url,
            queue_maxsize=queue_maxsize,
            key_prefix="numina:stream",  # Numina-specific namespace
            stream_ttl_seconds=stream_ttl_seconds,
            max_connections=max_connections,
        )

