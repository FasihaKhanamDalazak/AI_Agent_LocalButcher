import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class SupportTicketCreate(BaseModel):
    order_id: uuid.UUID | None = None
    issue_text: str = Field(min_length=1, max_length=2000)


class SupportTicketRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    order_id: uuid.UUID | None
    issue_text: str
    status: str
    created_at: datetime
