from datetime import datetime
from typing import Annotated
from uuid import UUID

from pydantic import BaseModel, StringConstraints

from app.models import Priority, QuestionStatus, RequirementStatus


class QuestionAnswerOut(BaseModel):
    id: UUID
    answer: str
    answered_at: datetime

    model_config = {"from_attributes": True}


class QuestionOut(BaseModel):
    id: UUID
    tender_id: UUID
    requirement_id: UUID
    requirement_code: str
    requirement_status: RequirementStatus
    is_mandatory: bool
    text: str
    priority: Priority
    status: QuestionStatus
    answer: QuestionAnswerOut | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class QuestionAnswerIn(BaseModel):
    answer: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=4000)]
