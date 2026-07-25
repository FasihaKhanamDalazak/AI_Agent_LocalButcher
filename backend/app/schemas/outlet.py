import uuid
from datetime import time

from pydantic import BaseModel, ConfigDict


class OutletRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    area: str
    city: str
    address_text: str
    lat: float
    lng: float
    phone: str
    opening_time: time
    closing_time: time
    delivery_radius_km: float
    is_active: bool


class OutletDistance(OutletRead):
    distance_km: float
