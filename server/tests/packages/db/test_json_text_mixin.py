"""Tests for packages.db.mixins.json_text — round-trip and edge cases."""

from __future__ import annotations

import pytest
from packages.db.mixins.json_text import json_text


class _MockModel:
    """Minimal ORM-like model using a real class statement (not type()) so
    the property descriptor protocol is exercised properly."""

    col: str | None = None
    prop = json_text("col")


class _MockModelInitial:
    """Same but with a pre-populated column value."""

    def __init__(self, initial: str) -> None:
        self.col = initial
    prop = json_text("col")


# ---------------------------------------------------------------------------
# Read path
# ---------------------------------------------------------------------------


def test_null_column_returns_none() -> None:
    m = _MockModel()
    assert m.prop is None


def test_empty_string_returns_none() -> None:
    m = _MockModelInitial("")
    assert m.prop is None


def test_valid_json_dict() -> None:
    m = _MockModelInitial('{"x": 42, "y": [1, 2, 3]}')
    assert m.prop == {"x": 42, "y": [1, 2, 3]}


def test_valid_json_list() -> None:
    m = _MockModelInitial('[1, "two", true]')
    assert m.prop == [1, "two", True]


def test_invalid_json_returns_none() -> None:
    m = _MockModelInitial("{not valid json")
    assert m.prop is None


def test_whitespace_only_returns_none() -> None:
    m = _MockModelInitial("   ")
    assert m.prop is None


# ---------------------------------------------------------------------------
# Write path
# ---------------------------------------------------------------------------


def test_write_dict_roundtrips() -> None:
    m = _MockModel()
    m.prop = {"key": "value", "num": 7}
    assert m.col == '{"key": "value", "num": 7}'
    assert m.prop == {"key": "value", "num": 7}


def test_write_list_roundtrips() -> None:
    m = _MockModel()
    m.prop = [1, "two", True]
    assert m.col == '[1, "two", true]'
    assert m.prop == [1, "two", True]


def test_write_none_clears_column() -> None:
    m = _MockModelInitial("{}")
    m.prop = None
    assert m.col is None


def test_write_preserves_chinese_chars() -> None:
    m = _MockModel()
    m.prop = {"greeting": "你好世界"}
    assert "你好世界" in m.col  # ensure_ascii=False keeps CJK characters
    assert m.prop == {"greeting": "你好世界"}


# ---------------------------------------------------------------------------
# Direct fget/fset (no property accessor) — ensures the helper itself works
# ---------------------------------------------------------------------------


def test_fget_calls_json_loads() -> None:
    prop = json_text("col")
    m = _MockModelInitial('{"a": 1}')
    assert prop.fget(m) == {"a": 1}  # type: ignore[attr-defined]


def test_fset_calls_json_dumps() -> None:
    prop = json_text("col")
    m = _MockModel()
    prop.fset(m, {"a": 1})  # type: ignore[attr-defined]
    assert m.col == '{"a": 1}'
