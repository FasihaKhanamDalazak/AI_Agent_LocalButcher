from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from pydantic import BaseModel, Field

from app.schemas.order import OrderRead, order_to_read

if TYPE_CHECKING:
    from app.models.order import Order


class StaffOrderStatusUpdate(BaseModel):
    status_code: str = Field(min_length=1, max_length=30)


class StaffOrderRead(OrderRead):
    # Fields customer-facing OrderRead deliberately omits — staff need to
    # know which customer an order belongs to and how to reach them;
    # customers never see another customer's identifier or another
    # outlet's internal name this way.
    user_id: uuid.UUID
    customer_name: str
    customer_phone: str | None
    outlet_name: str


def staff_order_to_read(order: "Order") -> StaffOrderRead:
    base = order_to_read(order)
    return StaffOrderRead(
        **base.model_dump(),
        user_id=order.user_id,
        customer_name=order.user.name,
        customer_phone=order.user.phone,
        outlet_name=order.outlet.name,
    )
