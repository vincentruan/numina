"""Tests for packages.db 模型的唯一约束与基本持久化行为。

通过 packages_db（隔离 in-memory SQLite，SAVEPOINT 隔离）插入数据，
验证 RevokedToken / ExchangeRate / Currency 的唯一约束在违反时抛 IntegrityError。
"""

from __future__ import annotations

from datetime import datetime

import pytest
from sqlalchemy.exc import IntegrityError

from packages.db.models.currency import Currency
from packages.db.models.exchange_rate import ExchangeRate
from packages.db.models.revoked_token import RevokedToken


def _flush_expecting_integrity_error(session):
    with pytest.raises(IntegrityError):
        session.flush()


class TestRevokedToken:
    """RevokedToken.id 无默认值（普通 Integer PK），需显式传入。"""

    def _make(self, id_: int, jti: str | None, user_id: str | None = "u1") -> RevokedToken:
        return RevokedToken(id=id_, jti=jti, user_id=user_id, revoked_at=1000.0, expires_at=2000.0)

    def test_insert_and_query(self, packages_db):
        packages_db.add(self._make(1, "jti-abc"))
        packages_db.flush()
        row = packages_db.query(RevokedToken).filter_by(jti="jti-abc").one()
        assert row.user_id == "u1"
        assert row.expires_at == 2000.0

    def test_jti_unique_constraint(self, packages_db):
        packages_db.add(self._make(1, "dup-jti"))
        packages_db.flush()
        packages_db.add(self._make(2, "dup-jti"))
        _flush_expecting_integrity_error(packages_db)

    def test_jti_nullable_allows_multiple_nulls(self, packages_db):
        # jti 可空；SQLite 唯一约束允许多个 NULL
        packages_db.add(self._make(1, None))
        packages_db.add(self._make(2, None))
        packages_db.flush()  # 不抛错

    def test_user_id_index_not_unique(self, packages_db):
        # 同一 user_id 可有多条吊销记录
        packages_db.add(self._make(1, "jti-1", user_id="same-user"))
        packages_db.add(self._make(2, "jti-2", user_id="same-user"))
        packages_db.flush()


class TestExchangeRate:
    """ExchangeRate: unique(target_currency, fetched_at)。"""

    def _make(self, target: str, fetched_at: datetime, rate: float = 7.1) -> ExchangeRate:
        return ExchangeRate(base_currency="CNY", target_currency=target, rate=rate, fetched_at=fetched_at)

    def test_insert_and_defaults(self, packages_db):
        r = self._make("USD", datetime(2026, 7, 22, 8, 0, 0))
        packages_db.add(r)
        packages_db.flush()
        assert r.id is not None
        assert r.base_currency == "CNY"  # 列默认值

    def test_unique_target_currency_and_fetched_at(self, packages_db):
        ts = datetime(2026, 7, 22, 8, 0, 0)
        packages_db.add(self._make("USD", ts))
        packages_db.flush()
        packages_db.add(self._make("USD", ts))  # 同币种同时间 → 冲突
        _flush_expecting_integrity_error(packages_db)

    def test_same_currency_different_time_allowed(self, packages_db):
        packages_db.add(self._make("USD", datetime(2026, 7, 22, 8, 0, 0)))
        packages_db.add(self._make("USD", datetime(2026, 7, 22, 9, 0, 0)))
        packages_db.flush()

    def test_different_currency_same_time_allowed(self, packages_db):
        ts = datetime(2026, 7, 22, 8, 0, 0)
        packages_db.add(self._make("USD", ts))
        packages_db.add(self._make("EUR", ts))
        packages_db.flush()


class TestCurrency:
    """Currency: code 唯一且非空。"""

    def _make(self, code: str, name_en: str = "X") -> Currency:
        return Currency(
            code=code,
            name_zh=f"{code}名",
            name_en=name_en,
            symbol="$",
            flag_emoji="F",
        )

    def test_insert_and_defaults(self, packages_db):
        c = self._make("USD", "US Dollar")
        packages_db.add(c)
        packages_db.flush()
        assert c.id is not None
        assert c.is_favorite is False  # 列默认值
        assert c.sort_order == 999

    def test_code_unique_constraint(self, packages_db):
        packages_db.add(self._make("USD"))
        packages_db.flush()
        packages_db.add(self._make("USD"))  # 重复 code → 冲突
        _flush_expecting_integrity_error(packages_db)

    def test_code_not_null(self, packages_db):
        c = Currency(code=None, name_zh="x", name_en="x", symbol="$", flag_emoji="F")  # type: ignore[arg-type]
        packages_db.add(c)
        _flush_expecting_integrity_error(packages_db)

    def test_distinct_codes_allowed(self, packages_db):
        for code in ("USD", "EUR", "JPY"):
            packages_db.add(self._make(code))
        packages_db.flush()
        assert packages_db.query(Currency).count() == 3
