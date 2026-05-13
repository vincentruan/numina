"""Thread-safe Snowflake ID generator.

64-bit structure:
  41 bits — milliseconds since EPOCH (2024-01-01 00:00:00 UTC)
  10 bits — machine_id (0-1023)
  12 bits — sequence (0-4095, resets per millisecond)
"""

import os
import socket
import threading
import time

# Custom epoch: 2024-01-01 00:00:00 UTC in milliseconds
_EPOCH_MS = 1704067200000

_MACHINE_ID_BITS = 10
_SEQUENCE_BITS = 12

_MAX_MACHINE_ID = (1 << _MACHINE_ID_BITS) - 1  # 1023
_MAX_SEQUENCE = (1 << _SEQUENCE_BITS) - 1       # 4095

_MACHINE_ID_SHIFT = _SEQUENCE_BITS              # 12
_TIMESTAMP_SHIFT = _MACHINE_ID_BITS + _SEQUENCE_BITS  # 22


def resolve_machine_id() -> int:
    """Resolve machine_id with priority: env var > IP-derived > fallback 1."""
    env_val = os.environ.get("SNOWFLAKE_MACHINE_ID")
    if env_val is not None:
        try:
            return int(env_val) & _MAX_MACHINE_ID
        except ValueError:
            raise ValueError(
                f"SNOWFLAKE_MACHINE_ID must be an integer, got: {env_val!r}"
            ) from None

    try:
        hostname = socket.gethostname()
        ip = socket.gethostbyname(hostname)
        parts = ip.split(".")
        if len(parts) == 4:
            derived = (int(parts[2]) * 256 + int(parts[3])) % 1024
            return derived
    except OSError:
        pass

    return 1


class _SnowflakeGenerator:
    def __init__(self, machine_id: int) -> None:
        self._machine_id = machine_id & _MAX_MACHINE_ID
        self._sequence = 0
        self._last_ms = -1
        self._lock = threading.Lock()

    def next_id(self) -> int:
        with self._lock:
            now = int(time.time() * 1000)

            if now < self._last_ms:
                while now < self._last_ms:
                    now = int(time.time() * 1000)

            if now == self._last_ms:
                self._sequence = (self._sequence + 1) & _MAX_SEQUENCE
                if self._sequence == 0:
                    while now <= self._last_ms:
                        now = int(time.time() * 1000)
            else:
                self._sequence = 0

            self._last_ms = now

            return (
                ((now - _EPOCH_MS) << _TIMESTAMP_SHIFT)
                | (self._machine_id << _MACHINE_ID_SHIFT)
                | self._sequence
            )


_generator: _SnowflakeGenerator | None = None
_init_lock = threading.Lock()


def init_snowflake() -> None:
    """Initialize the global generator. Call once at startup."""
    global _generator
    with _init_lock:
        if _generator is None:
            _generator = _SnowflakeGenerator(resolve_machine_id())


def next_id() -> int:
    """Generate the next Snowflake ID. Thread-safe; auto-initializes if needed."""
    if _generator is None:
        init_snowflake()
    assert _generator is not None
    return _generator.next_id()
