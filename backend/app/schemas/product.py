import uuid

from pydantic import BaseModel, ConfigDict

from app.schemas.outlet import OutletRead


class ProductRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    category: str
    description: str | None
    unit: str
    price: float
    max_qty_per_order: float
    is_active: bool


class AvailabilityResult(BaseModel):
    product_id: uuid.UUID
    outlet_id: uuid.UUID
    outlet_name: str
    available: bool
    quantity_available: float

    # Populated only when the assigned outlet can't cover the requested
    # quantity — this is what powers "Banjara Hills has it instead."
    alternate_outlet: OutletRead | None = None
    alternate_outlet_distance_km: float | None = None
    alternate_covers_delivery: bool | None = None
