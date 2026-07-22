"""Tests for packages.core.snowflake — Snowflake ID 生成器.

覆盖:
  - resolve_machine_id 优先级: 环境变量 > IP 派生 > 回退 1
  - resolve_machine_id 环境变量掩码 (& 1023) 与非法值报错
  - next_id 唯一性 / 单调性 / machine_id 位段编码
  - _SnowflakeGenerator 序列号递增与跨毫秒重置
"""

from __future__ import annotations

import socket
import threading

import pytest

from packages.core import snowflake
from packages.core.snowflake import (
    _EPOCH_MS,
    _MACHINE_ID_SHIFT,
    _MAX_MACHINE_ID,
    _MAX_SEQUENCE,
    _TIMESTAMP_SHIFT,
    _SnowflakeGenerator,
    resolve_machine_id,
)

# ---------------------------------------------------------------------------
# resolve_machine_id — 优先级与掩码
# ---------------------------------------------------------------------------


def test_resolve_machine_id_env_var_wins(monkeypatch):
    """环境变量优先, 且按 10bit 掩码 (& 1023)."""
    monkeypatch.setenv("SNOWFLAKE_MACHINE_ID", "42")
    assert resolve_machine_id() == 42


def test_resolve_machine_id_env_var_masked_to_10_bits(monkeypatch):
    """超出 1023 的环境变量值会被 & 1023 截断."""
    monkeypatch.setenv("SNOWFLAKE_MACHINE_ID", "2048")  # 0b100000000000 -> &1023 == 0
    assert resolve_machine_id() == 0
    monkeypatch.setenv("SNOWFLAKE_MACHINE_ID", "1023")
    assert resolve_machine_id() == 1023
    monkeypatch.setenv("SNOWFLAKE_MACHINE_ID", "1024")
    assert resolve_machine_id() == 0


def test_resolve_machine_id_env_var_invalid_raises(monkeypatch):
    """非整数环境变量应抛 ValueError."""
    monkeypatch.setenv("SNOWFLAKE_MACHINE_ID", "not-an-int")
    with pytest.raises(ValueError, match="SNOWFLAKE_MACHINE_ID"):
        resolve_machine_id()


def test_resolve_machine_id_ip_derived(monkeypatch):
    """无环境变量时, 从 IP 的第三/四段派生: (parts[2]*256 + parts[3]) % 1024."""
    monkeypatch.delenv("SNOWFLAKE_MACHINE_ID", raising=False)
    monkeypatch.setattr(socket, "gethostname", lambda: "testhost")
    # 10.0.1.200 -> (1*256 + 200) % 1024 = 456
    monkeypatch.setattr(socket, "gethostbyname", lambda h: "10.0.1.200")
    assert resolve_machine_id() == (1 * 256 + 200) % 1024


def test_resolve_machine_id_ip_derived_mod_1024(monkeypatch):
    """IP 派生值对 1024 取模."""
    monkeypatch.delenv("SNOWFLAKE_MACHINE_ID", raising=False)
    monkeypatch.setattr(socket, "gethostname", lambda: "testhost")
    # (3*256 + 255) = 1023 -> %1024 == 1023
    monkeypatch.setattr(socket, "gethostbyname", lambda h: "192.168.3.255")
    assert resolve_machine_id() == 1023


def test_resolve_machine_id_ip_non_ipv4_falls_back(monkeypatch):
    """gethostbyname 返回非 IPv4 (非 4 段) 时回退为 1."""
    monkeypatch.delenv("SNOWFLAKE_MACHINE_ID", raising=False)
    monkeypatch.setattr(socket, "gethostname", lambda: "testhost")
    monkeypatch.setattr(socket, "gethostbyname", lambda h: "localhost")  # 无点分四段
    assert resolve_machine_id() == 1


def test_resolve_machine_id_oserror_falls_back_to_1(monkeypatch):
    """gethostbyname 抛 OSError 时回退为 1."""
    monkeypatch.delenv("SNOWFLAKE_MACHINE_ID", raising=False)
    monkeypatch.setattr(socket, "gethostname", lambda: "testhost")

    def _raise(_host):
        raise OSError("name resolution failed")

    monkeypatch.setattr(socket, "gethostbyname", _raise)
    assert resolve_machine_id() == 1


# ---------------------------------------------------------------------------
# _SnowflakeGenerator.next_id — 唯一性 / 单调性 / 位段
# ---------------------------------------------------------------------------


def _decode(snowflake_id: int) -> tuple[int, int, int]:
    """拆出 (timestamp_ms_since_epoch, machine_id, sequence)."""
    sequence = snowflake_id & _MAX_SEQUENCE
    machine_id = (snowflake_id >> _MACHINE_ID_SHIFT) & _MAX_MACHINE_ID
    timestamp = (snowflake_id >> _TIMESTAMP_SHIFT) + _EPOCH_MS
    return timestamp, machine_id, sequence


def test_next_id_uniqueness_many():
    """单线程连续生成 10000 个 ID 应全部唯一."""
    gen = _SnowflakeGenerator(machine_id=7)
    ids = {gen.next_id() for _ in range(10000)}
    assert len(ids) == 10000


def test_next_id_monotonic_increasing():
    """同一毫秒内序列号递增 -> ID 单调递增."""
    gen = _SnowflakeGenerator(machine_id=1)
    prev = -1
    for _ in range(5000):
        cur = gen.next_id()
        assert cur > prev
        prev = cur


def test_next_id_encodes_machine_id():
    """生成的 ID 应正确编码 machine_id 位段."""
    gen = _SnowflakeGenerator(machine_id=123)
    _ts, machine_id, _seq = _decode(gen.next_id())
    assert machine_id == 123


def test_next_id_machine_id_masked_in_generator():
    """构造器对 machine_id 做 & 1023 掩码."""
    gen = _SnowflakeGenerator(machine_id=2048)  # &1023 == 0
    _ts, machine_id, _seq = _decode(gen.next_id())
    assert machine_id == 0


def test_next_id_sequence_increments_within_same_ms(monkeypatch):
    """固定时间戳下, 连续调用应递增 sequence 位段."""
    gen = _SnowflakeGenerator(machine_id=5)
    fixed_ms = 1_700_000_000_000
    monkeypatch.setattr(snowflake.time, "time", lambda: fixed_ms / 1000.0)

    id1 = gen.next_id()
    id2 = gen.next_id()
    id3 = gen.next_id()
    assert _decode(id1)[2] == 0
    assert _decode(id2)[2] == 1
    assert _decode(id3)[2] == 2
    # 三个 ID 的时间戳与 machine 位段一致
    assert _decode(id1)[:2] == _decode(id2)[:2] == _decode(id3)[:2]


def test_next_id_sequence_resets_on_new_ms(monkeypatch):
    """跨毫秒后 sequence 重置为 0."""
    gen = _SnowflakeGenerator(machine_id=5)
    current = {"ms": 1_700_000_000_000}
    monkeypatch.setattr(snowflake.time, "time", lambda: current["ms"] / 1000.0)

    first = gen.next_id()
    assert _decode(first)[2] == 0
    gen.next_id()  # sequence -> 1
    # 推进 1ms
    current["ms"] += 1
    third = gen.next_id()
    assert _decode(third)[2] == 0
    assert _decode(third)[0] == current["ms"]


def test_next_id_sequence_overflow_waits_for_next_ms(monkeypatch):
    """sequence 溢出 (4095->0) 时应自旋等待到下一毫秒, 保证唯一."""
    gen = _SnowflakeGenerator(machine_id=9)
    current = {"ms": 1_700_000_000_000}

    def _fake_time():
        return current["ms"] / 1000.0

    monkeypatch.setattr(snowflake.time, "time", _fake_time)

    # 填满当前毫秒的所有 sequence (0..4095)
    seen = {gen.next_id() for _ in range(_MAX_SEQUENCE + 1)}
    assert len(seen) == _MAX_SEQUENCE + 1

    # 下一次调用会触发 sequence 溢出 -> 自旋等待; 我们在另一个线程推进时钟
    def _advance_clock():
        # 给生成器一点时间进入自旋, 再推进 1ms
        import time as _t

        _t.sleep(0.05)
        current["ms"] += 1

    advancer = threading.Thread(target=_advance_clock)
    advancer.start()
    overflow_id = gen.next_id()  # 应等到新毫秒后返回
    advancer.join(timeout=5)

    assert overflow_id not in seen
    assert _decode(overflow_id)[0] == current["ms"]
    assert _decode(overflow_id)[2] == 0


def test_next_id_clock_rollback_waits(monkeypatch):
    """时钟回拨 (now < last_ms) 时应自旋等待时钟追平."""
    gen = _SnowflakeGenerator(machine_id=3)
    current = {"ms": 1_700_000_000_000}
    monkeypatch.setattr(snowflake.time, "time", lambda: current["ms"] / 1000.0)

    first = gen.next_id()
    # 回拨时钟 5ms
    current["ms"] -= 5

    def _restore_clock():
        import time as _t

        _t.sleep(0.05)
        current["ms"] += 5  # 恢复到 last_ms

    restorer = threading.Thread(target=_restore_clock)
    restorer.start()
    second = gen.next_id()  # 应等待时钟追平后返回
    restorer.join(timeout=5)

    assert second > first


def test_next_id_thread_safety_uniqueness():
    """多线程并发生成 ID 应全部唯一 (锁保护)."""
    gen = _SnowflakeGenerator(machine_id=11)
    results: list[int] = []
    lock = threading.Lock()

    def _worker():
        local = [gen.next_id() for _ in range(1000)]
        with lock:
            results.extend(local)

    threads = [threading.Thread(target=_worker) for _ in range(8)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert len(results) == 8000
    assert len(set(results)) == 8000


# ---------------------------------------------------------------------------
# 模块级 next_id / init_snowflake — 单例行为
# ---------------------------------------------------------------------------


@pytest.fixture()
def _reset_global_generator(monkeypatch):
    """每个测试后重置模块级 _generator, 避免污染其他测试."""
    yield
    monkeypatch.setattr(snowflake, "_generator", None)


def test_module_next_id_auto_initializes(_reset_global_generator, monkeypatch):
    """模块级 next_id 在未显式 init 时自动初始化并返回合法 ID."""
    monkeypatch.setattr(snowflake, "_generator", None)
    monkeypatch.setenv("SNOWFLAKE_MACHINE_ID", "77")
    new_id = snowflake.next_id()
    assert isinstance(new_id, int)
    _ts, machine_id, _seq = _decode(new_id)
    assert machine_id == 77


def test_init_snowflake_idempotent(_reset_global_generator, monkeypatch):
    """init_snowflake 多次调用不会覆盖已初始化的生成器."""
    monkeypatch.setattr(snowflake, "_generator", None)
    monkeypatch.setenv("SNOWFLAKE_MACHINE_ID", "1")
    snowflake.init_snowflake()
    first_gen = snowflake._generator
    assert first_gen is not None
    monkeypatch.setenv("SNOWFLAKE_MACHINE_ID", "2")
    snowflake.init_snowflake()  # 不应重建
    assert snowflake._generator is first_gen
