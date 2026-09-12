from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


class JobOut(BaseModel):
    id: UUID
    type: str
    status: str
    entity_kind: str | None
    entity_id: UUID | None
    progress: int
    message: str | None
    error: str | None
    result: dict | None
    started_at: datetime | None
    finished_at: datetime | None
    created_at: datetime

    model_config = {"from_attributes": True}
