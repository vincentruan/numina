from pydantic import BaseModel

from apps.backend.app.schemas.base import SnowflakeBase


class TagCreate(BaseModel):
    name: str
    color: str = "#6366F1"


class TagUpdate(BaseModel):
    name: str | None = None
    color: str | None = None


class TagResponse(SnowflakeBase):
    id: int
    family_id: int
    name: str
    color: str
