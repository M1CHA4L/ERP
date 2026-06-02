from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class FileAssetRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    owner_type: str
    owner_id: UUID
    file_type: str
    file_name: str
    mime_type: str | None
    size_bytes: int | None
    version: int
    uploaded_by: UUID
    created_at: datetime
