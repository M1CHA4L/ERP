from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field


class TimelineItem(BaseModel):
    occurred_at: datetime | None
    category: str
    title: str
    description: str | None = None
    status: str | None = None
    entity_type: str
    entity_id: UUID | None = None
    meta: dict[str, Any] = Field(default_factory=dict)
