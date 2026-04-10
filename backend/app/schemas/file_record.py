from pydantic import BaseModel


class FileRecordResponse(BaseModel):
    file_id: str
    url: str
    filename: str
    size_bytes: int

    model_config = {"from_attributes": True}
