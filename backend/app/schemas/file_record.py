from pydantic import BaseModel, ConfigDict


class FileRecordResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    file_id: str
    url: str
    filename: str
    size_bytes: int
