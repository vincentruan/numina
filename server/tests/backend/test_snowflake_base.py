"""Test SnowflakeBase serialization behavior."""
from pydantic import BaseModel

from apps.backend.app.schemas.base import SnowflakeBase


class MockResponse(SnowflakeBase):
    id: int
    family_id: int
    other_id: int
    name: str
    count: int  # Not an ID field


def test_snowflake_base_serializes_ids_to_strings():
    """All fields named 'id' or ending in '_id' become strings in JSON."""
    obj = MockResponse(
        id=123456789012345,
        family_id=987654321098765,
        other_id=111222333444555,
        name="test",
        count=42,
    )

    data = obj.model_dump()

    assert data["id"] == "123456789012345"
    assert data["family_id"] == "987654321098765"
    assert data["other_id"] == "111222333444555"
    assert data["name"] == "test"
    assert data["count"] == 42  # Not converted


def test_plain_base_model_keeps_int():
    """Plain BaseModel does NOT convert IDs to strings."""

    class PlainResponse(BaseModel):
        id: int

    obj = PlainResponse(id=123456789012345)
    data = obj.model_dump()

    assert data["id"] == 123456789012345  # Still int
    assert isinstance(data["id"], int)
