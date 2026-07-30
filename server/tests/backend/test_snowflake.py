"""Tests for the Snowflake ID generator."""

import os
import threading
from unittest.mock import patch


def test_next_id_returns_positive_int():
    """Basic functionality: next_id() returns a positive integer."""
    from apps.backend.app.utils.snowflake import next_id

    id_ = next_id()
    assert isinstance(id_, int)
    assert id_ > 0


def test_snowflake_uniqueness():
    """10000 sequential IDs are all unique."""
    from apps.backend.app.utils.snowflake import next_id

    ids = [next_id() for _ in range(10000)]
    assert len(set(ids)) == 10000


def test_snowflake_monotonic():
    """IDs are non-decreasing (monotonic)."""
    from apps.backend.app.utils.snowflake import next_id

    ids = [next_id() for _ in range(1000)]
    for a, b in zip(ids, ids[1:], strict=False):
        assert b > a


def test_snowflake_concurrent_uniqueness():
    """10 threads × 100 IDs each — all 1000 IDs are unique."""
    from apps.backend.app.utils.snowflake import next_id

    results: list[int] = []
    lock = threading.Lock()

    def generate():
        local = [next_id() for _ in range(100)]
        with lock:
            results.extend(local)

    threads = [threading.Thread(target=generate) for _ in range(10)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert len(results) == 1000
    assert len(set(results)) == 1000


def test_resolve_machine_id_from_env():
    """SNOWFLAKE_MACHINE_ID env var takes priority."""
    from apps.backend.app.utils.snowflake import resolve_machine_id

    with patch.dict(os.environ, {"SNOWFLAKE_MACHINE_ID": "42"}):
        assert resolve_machine_id() == 42


def test_resolve_machine_id_clamps_to_10_bits():
    """Values > 1023 are masked to 10 bits (& 0x3FF)."""
    from apps.backend.app.utils.snowflake import resolve_machine_id

    # 1025 in binary is 10000000001 — masked to 10 bits = 1
    with patch.dict(os.environ, {"SNOWFLAKE_MACHINE_ID": "1025"}):
        assert resolve_machine_id() == (1025 & 0x3FF)


def test_resolve_machine_id_fallback():
    """Falls back to 1 when env var is unset and IP resolution fails."""
    from apps.backend.app.utils.snowflake import resolve_machine_id

    env = {k: v for k, v in os.environ.items() if k != "SNOWFLAKE_MACHINE_ID"}

    with patch.dict(os.environ, env, clear=True), patch("packages.core.snowflake.socket.gethostbyname", side_effect=OSError("no network")):
        assert resolve_machine_id() == 1
