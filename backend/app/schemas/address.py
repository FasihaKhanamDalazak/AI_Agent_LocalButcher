import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class AddressCreate(BaseModel):
    label: str = Field(min_length=1, max_length=50)
    address_text: str = Field(min_length=1, max_length=500)
    lat: float | None = None
    lng: float | None = None
    is_default: bool = False


class AddressUpdate(BaseModel):
    label: str | None = Field(default=None, min_length=1, max_length=50)
    address_text: str | None = Field(default=None, min_length=1, max_length=500)
    lat: float | None = None
    lng: float | None = None
    is_default: bool | None = None


class AddressRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    label: str
    address_text: str
    lat: float | None
    lng: float | None
    is_default: bool
    created_at: datetime
