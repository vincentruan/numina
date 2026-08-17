"""Numina-specific Redis Streams stream bridge with tenant isolation.

Wraps DeerFlow's RedisStreamBridge to add Numina-specific key prefixing with
family_id-based tenant isolation. Redis keys are namespaced as
``numina:stream:{family_id}:{run_id}`` to prevent cross-tenant data leakage.
"""

from __future__ import annotations

import logging

from deerflow.runtime.stream_bridge.redis import RedisStreamBridge

logger = logging.getLogger(__name__)


class NuminaRedisStreamBridge(RedisStreamBridge):
    """Numina-flavored Redis Streams stream bridge with tenant isolation.

    Inherits all of DeerFlow's RedisStreamBridge logic (XADD/XREAD, heartbeat,
    StreamGap detection, 24h TTL) and customizes the key format to include
    family_id for strict tenant isolation at the Redis level.

    Key format: ``numina:stream:{family_id}:{run_id}``
    This ensures that even if two families somehow share a run_id (unlikely with
    Snowflake IDs), their streams remain separate in Redis.
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

    def _stream_key(self, run_id: str) -> str:
        """Build tenant-scoped Redis stream key.

        Overrides DeerFlow's _stream_key to include family_id in the key.
        The run_id is expected to be in format "family_id:run_id" or just "run_id".
        If family_id is not included in run_id, uses "0" as default.

        Key format: ``numina:stream:{family_id}:{run_id}``

        Args:
            run_id: Either "family_id:run_id" or just "run_id".

        Returns:
            Redis key string with tenant isolation.
        """
        # Parse run_id to extract family_id if present
        if ":" in run_id:
            family_id, actual_run_id = run_id.split(":", 1)
        else:
            # Fallback: use "0" as default family_id if not provided
            # This maintains backward compatibility but should be avoided
            family_id = "0"
            actual_run_id = run_id

        return f"numina:stream:{family_id}:{actual_run_id}"

