from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class OperationLogRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    user_id: UUID
    module: str
    action: str
    target_type: str
    target_id: UUID | None
    before_data: dict | None
    after_data: dict | None
    ip_address: str | None
    user_agent: str | None
    created_at: datetime
