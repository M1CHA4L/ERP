from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class PrintJobRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    print_no: str
    document_type: str
    target_type: str
    target_id: UUID | None = None
    template_version: str
    printed_by: UUID | None = None
    printed_at: datetime
    snapshot: dict | None = None
    remark: str | None = None
