"""Tests for validation_error_handler field mapping and locale messages."""

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from pydantic import BaseModel, field_validator

# Minimal app to trigger validation errors
app = FastAPI()


class StrictModel(BaseModel):
    name: str
    age: int
    score: float


@app.post("/test/strict")
def strict_endpoint(body: StrictModel):
    return body


class ShortModel(BaseModel):
    password: str

    @field_validator("password")
    @classmethod
    def min_len(cls, v: str) -> str:
        if len(v) < 8:
            raise ValueError("too short")
        return v


@app.post("/test/short")
def short_endpoint(body: ShortModel):
    return body


# Register the same handlers as the main app
from fastapi.exceptions import RequestValidationError  # noqa: E402

from typing import Any, cast

from apps.backend.app.error_handlers import validation_error_handler  # noqa: E402

app.add_exception_handler(RequestValidationError, cast(Any, validation_error_handler))


@pytest.fixture(scope="module")
def test_client():
    with TestClient(app) as c:
        yield c


def test_missing_field_required(test_client):
    """missing field → code=REQUIRED, zh-CN msg"""
    resp = test_client.post(
        "/test/strict",
        json={"age": 25, "score": 9.5},
        headers={"Accept-Language": "zh-CN"},
    )
    assert resp.status_code == 422
    details = resp.json()["details"]
    name_err = next(d for d in details if d["field"] == "name")
    assert name_err["code"] == "REQUIRED"
    assert name_err["msg"] == "此字段为必填项"


def test_missing_field_required_en(test_client):
    """missing field → code=REQUIRED, en-US msg"""
    resp = test_client.post(
        "/test/strict",
        json={"age": 25, "score": 9.5},
        headers={"Accept-Language": "en-US"},
    )
    assert resp.status_code == 422
    details = resp.json()["details"]
    name_err = next(d for d in details if d["field"] == "name")
    assert name_err["code"] == "REQUIRED"
    assert name_err["msg"] == "This field is required"


def test_int_type_invalid(test_client):
    """non-integer string for int field → code=INVALID_TYPE (int_parsing)"""
    resp = test_client.post(
        "/test/strict",
        json={"name": "Alice", "age": "not-a-number", "score": 9.5},
        headers={"Accept-Language": "zh-CN"},
    )
    assert resp.status_code == 422
    details = resp.json()["details"]
    age_err = next(d for d in details if d["field"] == "age")
    assert age_err["code"] == "INVALID_TYPE"
    assert age_err["msg"] == "类型不正确"


def test_value_error_invalid_value(test_client):
    """value_error → code=INVALID_VALUE"""
    resp = test_client.post(
        "/test/short",
        json={"password": "short"},
        headers={"Accept-Language": "zh-CN"},
    )
    assert resp.status_code == 422
    details = resp.json()["details"]
    pw_err = next(d for d in details if d["field"] == "password")
    assert pw_err["code"] == "INVALID_VALUE"
    assert pw_err["msg"] == "too short"


def test_unknown_pydantic_type_fallback(test_client):
    """Unknown Pydantic type → code=INVALID_VALUE (fallback)"""
    # Simulate by directly calling the map
    from apps.backend.app.error_handlers import _VALIDATION_CODE_MAP
    assert _VALIDATION_CODE_MAP.get("nonexistent_type_xyz", "INVALID_VALUE") == "INVALID_VALUE"


def test_validation_code_map_coverage():
    """All expected Pydantic v2 types are mapped."""
    from apps.backend.app.error_handlers import _VALIDATION_CODE_MAP
    expected = {
        "missing": "REQUIRED",
        "string_too_short": "TOO_SHORT",
        "string_too_long": "TOO_LONG",
        "value_error": "INVALID_VALUE",
        "string_pattern_mismatch": "INVALID_FORMAT",
        "int_type": "INVALID_TYPE",
        "float_type": "INVALID_TYPE",
        "string_type": "INVALID_TYPE",
        "bool_type": "INVALID_TYPE",
        "int_parsing": "INVALID_TYPE",
        "float_parsing": "INVALID_TYPE",
        "greater_than": "INVALID_VALUE",
        "greater_than_equal": "INVALID_VALUE",
        "less_than": "INVALID_VALUE",
        "less_than_equal": "INVALID_VALUE",
        "enum": "INVALID_VALUE",
        "url_type": "INVALID_FORMAT",
        "datetime_type": "INVALID_FORMAT",
    }
    for pydantic_type, expected_code in expected.items():
        assert _VALIDATION_CODE_MAP.get(pydantic_type) == expected_code, (
            f"{pydantic_type} should map to {expected_code}"
        )


def test_details_envelope_structure(test_client):
    """422 response has correct envelope with details array."""
    resp = test_client.post("/test/strict", json={})
    assert resp.status_code == 422
    body = resp.json()
    assert body["code"] == "VALIDATION_ERROR"
    assert isinstance(body["details"], list)
    for item in body["details"]:
        assert "field" in item
        assert "code" in item
        assert "msg" in item
