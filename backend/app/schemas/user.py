import uuid

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class UserCreate(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    email: EmailStr
    # Required (not optional) and E.164-shaped — this is the number the
    # future Twilio calling feature will match an inbound caller against,
    # so an unvalidated/missing phone here would silently break that
    # lookup later. Existing accounts predating this rule can still have
    # phone=None (see UserRead) — this constraint only applies going
    # forward, at signup.
    phone: str = Field(pattern=r"^\+[1-9]\d{7,14}$")
    password: str = Field(min_length=8, max_length=128)
    preferred_language: str = "en"


class UserRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    email: EmailStr
    phone: str | None
    preferred_language: str
    # Included so the frontend can show/hide the staff dashboard link —
    # a user's own role is not sensitive relative to themselves, unlike
    # exposing another user's data would be.
    role: str
