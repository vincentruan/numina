from apps.backend.app.schemas.base import SnowflakeBase


class FileRecordResponse(SnowflakeBase):
    file_id: int
    url: str
    filename: str
    size_bytes: int
