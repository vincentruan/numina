"""ExchangeRateService 测试。

覆盖:
- get_rate: CNY 短路返回 1.0；adapter 缓存命中（4h TTL 内）；无 adapter 时 DB 回退；缺汇率返回 (None, None)
- convert: 同币种直通；经 CNY 中间换算；JPY 取整；其他保留 2 位小数
- fetch_and_store_rates (deprecated wrapper): 调用 adapter，触发 DeprecationWarning

注意: ExchangeRateService._cache 已移除；缓存逻辑迁移到 ExchangeRateAdapter。
"""
from datetime import UTC, datetime, timedelta

from packages.core.exchange_rate_adapter import ExchangeRateAdapter
from packages.db.models.exchange_rate import ExchangeRate
from packages.domain.exchange_rate.service import ExchangeRateService


def _add_rate(db, target: str, rate: float, fetched_at: datetime | None = None) -> ExchangeRate:
    row = ExchangeRate(
        target_currency=target,
        rate=rate,
        fetched_at=fetched_at or datetime.now(UTC),
    )
    db.add(row)
    db.flush()
    return row


# ---------------------------------------------------------------------------
# get_rate
# ---------------------------------------------------------------------------


def test_get_rate_cny_shortcut_returns_1(packages_db):
    """CNY 短路: 不查库不查缓存，直接返回 (1.0, now)。"""
    rate, fetched_at = ExchangeRateService.get_rate("CNY", packages_db)
    assert rate == 1.0
    assert isinstance(fetched_at, datetime)


def test_get_rate_db_fallback_when_no_adapter(packages_db):
    """无 adapter → 直接查 DB，返回最新 fetched_at 的汇率。"""
    _add_rate(packages_db, "USD", 7.2)
    rate, fetched_at = ExchangeRateService.get_rate("USD", packages_db)
    assert rate == 7.2
    assert isinstance(fetched_at, datetime)


def test_get_rate_returns_latest_fetched_at_row(packages_db):
    """DB 有多行 → 取 fetched_at 最新的那条。"""
    now = datetime.now(UTC)
    _add_rate(packages_db, "USD", 7.0, fetched_at=now - timedelta(days=2))
    _add_rate(packages_db, "USD", 7.5, fetched_at=now - timedelta(days=1))
    rate, _ = ExchangeRateService.get_rate("USD", packages_db)
    assert rate == 7.5


def test_get_rate_adapter_cache_hit_within_ttl_skips_db(packages_db):
    """adapter 缓存命中（4h TTL 内）→ 直接返回缓存值，不查库。

    预填缓存后删除 DB 行，仍能返回 → 证明走了缓存路径。
    """
    now = datetime.now(UTC)
    adapter = ExchangeRateAdapter()
    adapter._cache["EUR"] = (9.1, now, now)

    # Delete the DB row so a DB query would fail to find it
    packages_db.query(ExchangeRate).delete()
    packages_db.commit()

    rate, fetched_at = ExchangeRateService.get_rate("EUR", packages_db, adapter=adapter)
    assert rate == 9.1
    assert fetched_at == now


def test_get_rate_adapter_stale_cache_falls_through_to_db(packages_db):
    """adapter 缓存过期（cached_at 超过 4h）→ 回退查库并刷新缓存。"""
    stale_cached_at = datetime.now(UTC) - timedelta(hours=5)
    adapter = ExchangeRateAdapter()
    adapter._cache["GBP"] = (8.0, datetime.now(UTC), stale_cached_at)

    _add_rate(packages_db, "GBP", 8.8)
    rate, _ = ExchangeRateService.get_rate("GBP", packages_db, adapter=adapter)
    assert rate == 8.8  # 来自 DB，而非过期缓存的 8.0


def test_get_rate_missing_rate_returns_none(packages_db):
    """DB 无该币种 → 返回 (None, None)，不写缓存。"""
    rate, fetched_at = ExchangeRateService.get_rate("XXX", packages_db)
    assert rate is None
    assert fetched_at is None


# ---------------------------------------------------------------------------
# convert
# ---------------------------------------------------------------------------


def test_convert_same_currency_passthrough(packages_db):
    """同币种 → 原样返回，不查库。"""
    assert ExchangeRateService.convert(100.0, "USD", "USD", packages_db) == 100.0
    assert ExchangeRateService.convert(0.0, "JPY", "JPY", packages_db) == 0.0


def test_convert_via_cny_intermediate_math(packages_db):
    """经 CNY 中间换算: amount/rate_from * rate_to。"""
    _add_rate(packages_db, "USD", 5.0)
    _add_rate(packages_db, "EUR", 10.0)
    adapter = ExchangeRateAdapter()
    result = ExchangeRateService.convert(100.0, "USD", "EUR", packages_db, adapter=adapter)
    assert result == 200.0


def test_convert_from_cny_uses_rate_to(packages_db):
    """CNY→USD: rate_from=1.0，等价于 amount * rate_to。"""
    _add_rate(packages_db, "USD", 0.14)
    adapter = ExchangeRateAdapter()
    result = ExchangeRateService.convert(1000.0, "CNY", "USD", packages_db, adapter=adapter)
    assert result == round(1000.0 * 0.14, 2)


def test_convert_jpy_rounds_to_integer(packages_db):
    """目标币种 JPY → 四舍五入到整数。"""
    _add_rate(packages_db, "JPY", 20.567)
    adapter = ExchangeRateAdapter()
    result = ExchangeRateService.convert(100.0, "CNY", "JPY", packages_db, adapter=adapter)
    assert result == 2057


def test_convert_non_jpy_rounds_to_2dp(packages_db):
    """目标币种非 JPY → 保留 2 位小数。"""
    _add_rate(packages_db, "USD", 3.0)
    _add_rate(packages_db, "EUR", 7.0)
    adapter = ExchangeRateAdapter()
    result = ExchangeRateService.convert(10.0, "USD", "EUR", packages_db, adapter=adapter)
    assert result == 23.33


def test_convert_missing_rate_passes_through(packages_db):
    """源币种缺汇率 → 直接返回原始金额，不做换算。"""
    _add_rate(packages_db, "USD", 2.0)
    adapter = ExchangeRateAdapter()
    # XXX 缺汇率 → 不做 1:1 回退，直接返回原始金额 50.0
    result = ExchangeRateService.convert(50.0, "XXX", "USD", packages_db, adapter=adapter)
    assert result == 50.0


# ---------------------------------------------------------------------------
# fetch_and_store_rates (deprecated wrapper)
# ---------------------------------------------------------------------------


class _FakeResponse:
    """模拟 httpx.Response 的最小接口。"""

    def __init__(self, payload: dict):
        self._payload = payload

    def raise_for_status(self):
        return None

    def json(self):
        return self._payload


def test_deprecated_fetch_and_store_rates_warns(packages_db, monkeypatch):
    """Deprecated wrapper emits DeprecationWarning and delegates to adapter."""
    monkeypatch.setattr(
        "packages.core.exchange_rate_adapter.ExchangeRateAdapter.fetch_and_store_rates",
        lambda self, db: True,
    )
    import warnings
    with warnings.catch_warnings(record=True) as w:
        warnings.simplefilter("always")
        ExchangeRateService.fetch_and_store_rates(packages_db)
        assert len(w) == 1
        assert issubclass(w[0].category, DeprecationWarning)
        assert "ExchangeRateAdapter" in str(w[0].message)
