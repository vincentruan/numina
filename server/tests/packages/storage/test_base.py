"""Tests for packages.storage.base — 错误层级与 StorageBackend 抽象接口。"""

from __future__ import annotations

import pytest

from packages.storage.base import (
    StorageAuthError,
    StorageBackend,
    StorageConflictError,
    StorageConnectionError,
    StorageError,
    StorageRateLimitError,
)


class TestErrorHierarchy:
    """所有具体错误都应继承自 StorageError（进而继承自 Exception）。"""

    @pytest.mark.parametrize(
        "exc_cls",
        [
            StorageRateLimitError,
            StorageConflictError,
            StorageConnectionError,
            StorageAuthError,
        ],
    )
    def test_concrete_errors_subclass_storage_error(self, exc_cls):
        assert issubclass(exc_cls, StorageError)
        assert issubclass(exc_cls, Exception)

    def test_storage_error_is_exception(self):
        assert issubclass(StorageError, Exception)

    def test_sibling_errors_are_distinct(self):
        # 兄弟类互不继承，便于精确 except
        assert not issubclass(StorageAuthError, StorageConnectionError)
        assert not issubclass(StorageConnectionError, StorageAuthError)
        assert not issubclass(StorageConflictError, StorageRateLimitError)


class TestStorageRateLimitError:
    """StorageRateLimitError 携带 reset_at（Unix epoch 秒）。"""

    def test_default_message_and_reset_at_none(self):
        err = StorageRateLimitError()
        assert str(err) == "Rate limit exceeded"
        assert err.reset_at is None

    def test_custom_message_and_reset_at(self):
        err = StorageRateLimitError("slow down", reset_at=1_700_000_000)
        assert str(err) == "slow down"
        assert err.reset_at == 1_700_000_000

    def test_catchable_as_storage_error(self):
        with pytest.raises(StorageError):
            raise StorageRateLimitError(reset_at=123)


class _DummyBackend(StorageBackend):
    """最小可实例化的具体 backend，用于测试默认属性。"""

    async def save(self, content, filename, date_dir, family_id="", user_id=""):
        return "x"

    async def delete(self, remote_path):
        return None

    def get_url(self, remote_path):
        return f"/{remote_path}"


class TestStorageBackendInterface:
    """抽象接口的默认行为与抽象方法约束。"""

    def test_default_write_delay_range(self):
        assert _DummyBackend().write_delay_range == (0.2, 1.0)

    def test_write_delay_range_is_tuple_of_floats(self):
        lo, hi = _DummyBackend().write_delay_range
        assert isinstance(lo, float) and isinstance(hi, float)
        assert lo < hi

    def test_cannot_instantiate_abstract_backend(self):
        with pytest.raises(TypeError):
            StorageBackend()  # type: ignore[abstract]

    def test_subclass_missing_methods_stays_abstract(self):
        class _Incomplete(StorageBackend):
            async def save(self, content, filename, date_dir, family_id="", user_id=""):
                return "x"

        with pytest.raises(TypeError):
            _Incomplete()  # type: ignore[abstract]
