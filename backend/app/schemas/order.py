from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from pydantic import BaseModel, Field

if TYPE_CHECKING:
    from app.models.order import Order


class CheckoutRequest(BaseModel):
    outlet_id: uuid.UUID
    fulfillment_type: str = Field(pattern="^(delivery|pickup)$")
    address_id: uuid.UUID | None = None  # required when fulfillment_type == "delivery"


class OrderItemModify(BaseModel):
    quantity: float = Field(gt=0)


class OrderItemRead(BaseModel):
    id: uuid.UUID
    product_id: uuid.UUID
    quantity: float
    price_at_order: float


class OrderRead(BaseModel):
    id: uuid.UUID
    order_number: int
    outlet_id: uuid.UUID
    address_id: uuid.UUID | None
    fulfillment_type: str
    total_amount: float
    status: str
    eta_start: datetime | None
    eta_end: datetime | None
    created_at: datetime
    items: list[OrderItemRead]


def order_to_read(order: "Order") -> OrderRead:
    """
    Single source of truth for turning an Order ORM object into the API
    shape. Used by the REST endpoints AND the LLM tool executor, so a
    customer gets an identical order representation whether they're using
    /docs or the chat assistant.
    """
    return OrderRead(
        id=order.id,
        order_number=order.order_number,
        outlet_id=order.outlet_id,
        address_id=order.address_id,
        fulfillment_type=order.fulfillment_type,
        total_amount=float(order.total_amount),
        status=order.status.code,
        eta_start=order.eta_start,
        eta_end=order.eta_end,
        created_at=order.created_at,
        items=[
            OrderItemRead(
                id=i.id,
                product_id=i.product_id,
                quantity=float(i.quantity),
                price_at_order=float(i.price_at_order),
            )
            for i in order.items
        ],
    )
