import uuid

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class UserCreate(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    email: EmailStr
    # Required (not optional) — this is the number the phone-call agent
    # matches an inbound caller against (see auth_service.get_user_by_phone),
    # so an unvalidated/missing phone here would silently break that lookup
    # later. Plain 10-digit Indian mobile number, no country code and no
    # "+" — deliberately NOT E.164 (this project's earlier convention):
    # this is the only market served (see backend CLAUDE.md), so a country
    # code only ever added a way for a caller's spoken number and the
    # stored value to mismatch, with zero actual benefit. Every Indian
    # mobile number starts with 6-9 per the TRAI numbering plan. Existing
    # accounts predating this rule can still have phone=None (see
    # UserRead) — this constraint only applies going forward, at signup.
    phone: str = Field(pattern=r"^[6-9]\d{9}$")
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
