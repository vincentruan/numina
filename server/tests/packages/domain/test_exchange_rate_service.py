"""ExchangeRateService 测试。

覆盖:
- get_rate: CNY 短路返回 1.0；缓存命中（4h TTL 内）；DB 回退；缺汇率返回 (None, None)
- convert: 同币种直通；经 CNY 中间换算；JPY 取整；其他保留 2 位小数
- fetch_and_store_rates: mock httpx.get；写库；跳过 CNY；新增 Currency 行；清缓存；
  httpx 异常返回 False

注意: ExchangeRateService._cache 是类级 dict，每个测试前清空避免交叉污染。
"""
from datetime import datetime, timedelta

import pytest

from packages.db.models.currency import Currency
from packages.db.models.exchange_rate import ExchangeRate
from packages.domain.exchange_rate.service import ExchangeRateService


@pytest.fixture(autouse=True)
def _clear_cache():
    """每个测试前后清空类级缓存，避免跨测试污染。"""
    ExchangeRateService._cache.clear()
    yield
    ExchangeRateService._cache.clear()


def _add_rate(db, target: str, rate: float, fetched_at: datetime | None = None) -> ExchangeRate:
    row = ExchangeRate(
        target_currency=target,
        rate=rate,
        fetched_at=fetched_at or datetime.now(),
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
    # 不应写入缓存
    assert "CNY" not in ExchangeRateService._cache


def test_get_rate_db_fallback_when_cache_empty(packages_db):
    """缓存空 → 查 DB，返回最新 fetched_at 的汇率，并回填缓存。"""
    _add_rate(packages_db, "USD", 7.2)
    rate, fetched_at = ExchangeRateService.get_rate("USD", packages_db)
    assert rate == 7.2
    assert isinstance(fetched_at, datetime)
    # 回填缓存
    assert "USD" in ExchangeRateService._cache
    cached_rate, _, _ = ExchangeRateService._cache["USD"]
    assert cached_rate == 7.2


def test_get_rate_returns_latest_fetched_at_row(packages_db):
    """DB 有多行 → 取 fetched_at 最新的那条。"""
    now = datetime.now()
    _add_rate(packages_db, "USD", 7.0, fetched_at=now - timedelta(days=2))
    _add_rate(packages_db, "USD", 7.5, fetched_at=now - timedelta(days=1))
    rate, _ = ExchangeRateService.get_rate("USD", packages_db)
    assert rate == 7.5


def test_get_rate_cache_hit_within_ttl_skips_db(packages_db):
    """缓存命中（4h TTL 内）→ 直接返回缓存值，不查库。

    预填缓存后删除 DB 行，仍能返回 → 证明走了缓存路径。
    """
    now = datetime.now()
    ExchangeRateService._cache["EUR"] = (9.1, now, now)  # rate, fetched_at, cached_at
    rate, fetched_at = ExchangeRateService.get_rate("EUR", packages_db)
    assert rate == 9.1
    assert fetched_at == now


def test_get_rate_stale_cache_falls_through_to_db(packages_db):
    """缓存过期（cached_at 超过 4h）→ 回退查库并刷新缓存。"""
    stale_cached_at = datetime.now() - timedelta(hours=5)
    ExchangeRateService._cache["GBP"] = (8.0, datetime.now(), stale_cached_at)
    _add_rate(packages_db, "GBP", 8.8)
    rate, _ = ExchangeRateService.get_rate("GBP", packages_db)
    assert rate == 8.8  # 来自 DB，而非过期缓存的 8.0


def test_get_rate_missing_rate_returns_none(packages_db):
    """DB 无该币种 → 返回 (None, None)，不写缓存。"""
    rate, fetched_at = ExchangeRateService.get_rate("XXX", packages_db)
    assert rate is None
    assert fetched_at is None
    assert "XXX" not in ExchangeRateService._cache


# ---------------------------------------------------------------------------
# convert
# ---------------------------------------------------------------------------


def test_convert_same_currency_passthrough(packages_db):
    """同币种 → 原样返回，不查库。"""
    assert ExchangeRateService.convert(100.0, "USD", "USD", packages_db) == 100.0
    assert ExchangeRateService.convert(0.0, "JPY", "JPY", packages_db) == 0.0


def test_convert_via_cny_intermediate_math(packages_db):
    """经 CNY 中间换算: amount/rate_from * rate_to。

    USD→EUR: 100 USD, rate_from=5.0, rate_to=10.0
      → 100/5.0 = 20 CNY → 20*10.0 = 200 EUR
    """
    _add_rate(packages_db, "USD", 5.0)
    _add_rate(packages_db, "EUR", 10.0)
    result = ExchangeRateService.convert(100.0, "USD", "EUR", packages_db)
    assert result == 200.0


def test_convert_from_cny_uses_rate_to(packages_db):
    """CNY→USD: rate_from=1.0，等价于 amount * rate_to。"""
    _add_rate(packages_db, "USD", 0.14)
    result = ExchangeRateService.convert(1000.0, "CNY", "USD", packages_db)
    assert result == round(1000.0 * 0.14, 2)


def test_convert_jpy_rounds_to_integer(packages_db):
    """目标币种 JPY → 四舍五入到整数。"""
    _add_rate(packages_db, "CNY", 1.0)  # 不会用到（CNY 短路），仅为清晰
    _add_rate(packages_db, "JPY", 20.567)
    # CNY→JPY: 100 * 20.567 = 2056.7 → round → 2057
    result = ExchangeRateService.convert(100.0, "CNY", "JPY", packages_db)
    assert result == 2057
    assert isinstance(result, int) or result == int(result)


def test_convert_non_jpy_rounds_to_2dp(packages_db):
    """目标币种非 JPY → 保留 2 位小数。"""
    _add_rate(packages_db, "USD", 3.0)
    _add_rate(packages_db, "EUR", 7.0)
    # USD→EUR: 10/3.0 = 3.333... CNY → *7.0 = 23.333... → 23.33
    result = ExchangeRateService.convert(10.0, "USD", "EUR", packages_db)
    assert result == 23.33


def test_convert_missing_rate_passes_through(packages_db):
    """源币种缺汇率 → 直接返回原始金额，不做换算。"""
    _add_rate(packages_db, "USD", 2.0)
    # XXX 缺汇率 → 不做 1:1 回退，直接返回原始金额 50.0
    result = ExchangeRateService.convert(50.0, "XXX", "USD", packages_db)
    assert result == 50.0


# ---------------------------------------------------------------------------
# fetch_and_store_rates
# ---------------------------------------------------------------------------


class _FakeResponse:
    """模拟 httpx.Response 的最小接口。"""

    def __init__(self, payload: dict):
        self._payload = payload

    def raise_for_status(self):
        return None

    def json(self):
        return self._payload


def test_fetch_and_store_rates_stores_rates_skips_cny(packages_db, monkeypatch):
    """成功获取 → 写入非 CNY 汇率行；CNY 被跳过；返回 True。"""
    payload = {"rates": {"CNY": 1.0, "USD": 7.2, "EUR": 7.8}}
    monkeypatch.setattr(
        "packages.domain.exchange_rate.service.httpx.get",
        lambda *a, **k: _FakeResponse(payload),
    )
    ok = ExchangeRateService.fetch_and_store_rates(packages_db)
    assert ok is True

    targets = {r.target_currency for r in packages_db.query(ExchangeRate).all()}
    assert "USD" in targets
    assert "EUR" in targets
    assert "CNY" not in targets  # CNY 被跳过


def test_fetch_and_store_rates_adds_new_currency_rows(packages_db, monkeypatch):
    """为 rates 中尚未存在的币种新增 Currency 行；已存在的不重复添加。"""
    # 预置一个已存在的 USD Currency
    packages_db.add(Currency(
        code="USD", name_zh="美元", name_en="US Dollar", symbol="$",
        flag_emoji="🇺🇸", is_favorite=True, sort_order=1,
    ))
    packages_db.flush()

    payload = {"rates": {"CNY": 1.0, "USD": 7.2, "ABC": 3.3}}
    monkeypatch.setattr(
        "packages.domain.exchange_rate.service.httpx.get",
        lambda *a, **k: _FakeResponse(payload),
    )
    ok = ExchangeRateService.fetch_and_store_rates(packages_db)
    assert ok is True

    codes = [c.code for c in packages_db.query(Currency).all()]
    # USD 已存在不重复；ABC 新增；CNY 也会被作为新 Currency 添加（不在 existing_codes）
    assert codes.count("USD") == 1
    assert "ABC" in codes


def test_fetch_and_store_rates_clears_cache(packages_db, monkeypatch):
    """成功获取后清空类级缓存。"""
    ExchangeRateService._cache["USD"] = (7.0, datetime.now(), datetime.now())
    payload = {"rates": {"USD": 7.2}}
    monkeypatch.setattr(
        "packages.domain.exchange_rate.service.httpx.get",
        lambda *a, **k: _FakeResponse(payload),
    )
    ExchangeRateService.fetch_and_store_rates(packages_db)
    assert ExchangeRateService._cache == {}


def test_fetch_and_store_rates_returns_false_on_httpx_exception(packages_db, monkeypatch):
    """httpx.get 抛异常 → 返回 False，不写库。"""
    def _boom(*a, **k):
        raise RuntimeError("network down")

    monkeypatch.setattr(
        "packages.domain.exchange_rate.service.httpx.get", _boom
    )
    ok = ExchangeRateService.fetch_and_store_rates(packages_db)
    assert ok is False
    assert packages_db.query(ExchangeRate).count() == 0


def test_fetch_and_store_rates_returns_false_on_http_error(packages_db, monkeypatch):
    """raise_for_status 抛异常 → 返回 False。"""
    class _ErrResponse:
        def raise_for_status(self):
            raise RuntimeError("HTTP 500")

        def json(self):
            return {}

    monkeypatch.setattr(
        "packages.domain.exchange_rate.service.httpx.get",
        lambda *a, **k: _ErrResponse(),
    )
    ok = ExchangeRateService.fetch_and_store_rates(packages_db)
    assert ok is False
