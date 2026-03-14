from pydantic import BaseModel


class TagCreate(BaseModel):
    name: str
    color: str = "#6366F1"


class TagUpdate(BaseModel):
    name: str | None = None
    color: str | None = None


class TagResponse(BaseModel):
    id: str
    family_id: str
    name: str
    color: str

    model_config = {"from_attributes": True}
