import uuid

from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=4000)
    conversation_id: uuid.UUID | None = None  # omit to start a new conversation


class ChatResponse(BaseModel):
    conversation_id: uuid.UUID
    reply: str


class GreetingResponse(BaseModel):
    conversation_id: uuid.UUID
    greeting: str
    follow_ups: list[str]
