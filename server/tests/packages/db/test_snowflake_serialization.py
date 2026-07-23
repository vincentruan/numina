"""Tests for the Snowflake ID 序列化契约。

数据层：packages.db 各模型的 id / *_id 列为 BigInteger，存储为 int，
默认值由 packages.core.snowflake.next_id 生成（> 2^53 的 64 位整数）。

序列化层：apps.backend.app.schemas.base.SnowflakeBase 在 JSON 输出时把
所有名为 id 或以 _id 结尾的 int 字段转成 str，避免 JS Number 精度丢失。
"""

from __future__ import annotations

import pytest
from sqlalchemy import BigInteger, inspect

from apps.backend.app.schemas.base import SnowflakeBase
from packages.core.snowflake import next_id
from packages.db.models.currency import Currency
from packages.db.models.exchange_rate import ExchangeRate
from packages.db.models.family import Family
from packages.db.models.user import User


class TestSnowflakeNextId:
    """next_id 生成器的输出特征。"""

    def test_returns_int(self):
        assert isinstance(next_id(), int)

    def test_exceeds_js_safe_integer(self):
        # 64 位 snowflake id 必须 > 2^53，才需要 str 序列化
        assert next_id() > 2**53

    def test_monotonic_increasing(self):
        ids = [next_id() for _ in range(100)]
        assert ids == sorted(ids)
        assert len(set(ids)) == 100  # 无重复


class TestModelIdColumnTypes:
    """关键模型的 id 列必须是 BigInteger（存 int）。"""

    @pytest.mark.parametrize("model", [Currency, ExchangeRate, Family, User])
    def test_id_column_is_biginteger(self, model):
        mapper = inspect(model)
        id_col = mapper.columns["id"]
        assert isinstance(id_col.type, BigInteger), f"{model.__name__}.id 应为 BigInteger"

    @pytest.mark.parametrize("model", [Currency, ExchangeRate, Family, User])
    def test_id_column_has_next_id_default(self, model):
        mapper = inspect(model)
        id_col = mapper.columns["id"]
        assert id_col.default is not None
        # default 是 next_id 的可调用包装
        assert getattr(id_col.default.arg, "__name__", "") == "next_id"

    def test_user_family_id_is_biginteger_fk(self):
        mapper = inspect(User)
        fam_col = mapper.columns["family_id"]
        assert isinstance(fam_col.type, BigInteger)


class TestModelIdStorage:
    """插入 DB 后 id 以 int 存储，且默认由 next_id 生成。"""

    def test_currency_default_id_is_int(self, packages_db):
        c = Currency(code="USD", name_zh="美元", name_en="US Dollar", symbol="$", flag_emoji="US")
        packages_db.add(c)
        packages_db.flush()
        assert isinstance(c.id, int)
        assert c.id > 2**53

    def test_exchange_rate_default_id_is_int(self, packages_db):
        from datetime import datetime

        r = ExchangeRate(target_currency="EUR", rate=7.8, fetched_at=datetime(2026, 7, 22))
        packages_db.add(r)
        packages_db.flush()
        assert isinstance(r.id, int)
        assert r.id > 2**53

    def test_explicit_int_id_preserved(self, packages_db):
        explicit = next_id()
        c = Currency(
            id=explicit, code="JPY", name_zh="日元", name_en="Yen", symbol="¥", flag_emoji="JP"
        )
        packages_db.add(c)
        packages_db.flush()
        assert c.id == explicit


class _SampleSchema(SnowflakeBase):
    id: int
    family_id: int
    user_id: int
    name: str
    count: int  # 非 id 字段，不应被 str 化
    parent_id: int | None = None


class TestSnowflakeBaseSerialization:
    """SnowflakeBase 把 id / *_id int 字段序列化为 str。"""

    def _make(self) -> _SampleSchema:
        return _SampleSchema(
            id=next_id(),
            family_id=next_id(),
            user_id=next_id(),
            name="测试",
            count=7,
            parent_id=None,
        )

    def test_id_fields_serialized_to_str(self):
        data = self._make().model_dump(mode="json")
        assert isinstance(data["id"], str)
        assert isinstance(data["family_id"], str)
        assert isinstance(data["user_id"], str)

    def test_non_id_int_field_stays_int(self):
        data = self._make().model_dump(mode="json")
        # count 不以 _id 结尾也不叫 id，保持 int
        assert isinstance(data["count"], int)
        assert data["count"] == 7

    def test_str_fields_unchanged(self):
        data = self._make().model_dump(mode="json")
        assert data["name"] == "测试"

    def test_none_id_field_stays_none(self):
        data = self._make().model_dump(mode="json")
        assert data["parent_id"] is None

    def test_serialized_id_matches_int_value(self):
        schema = self._make()
        data = schema.model_dump(mode="json")
        assert data["id"] == str(schema.id)
        assert int(data["family_id"]) == schema.family_id

    def test_from_attributes_orm_mode(self, packages_db):
        """from_attributes=True：可直接从 ORM 对象构造 schema。"""
        c = Currency(code="GBP", name_zh="英镑", name_en="Pound", symbol="£", flag_emoji="GB")
        packages_db.add(c)
        packages_db.flush()

        class _CurrencySchema(SnowflakeBase):
            id: int
            code: str

        schema = _CurrencySchema.model_validate(c)
        assert schema.id == c.id
        assert schema.model_dump(mode="json")["id"] == str(c.id)
