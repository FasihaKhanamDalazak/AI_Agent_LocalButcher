from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from pydantic import BaseModel, Field

from app.utils.time_format import eta_text as _eta_text

if TYPE_CHECKING:
    from app.models.order import Order


class CheckoutRequest(BaseModel):
    # Local Butcher is delivery-only — no pickup option. address_id is
    # always required (order_service.checkout still re-validates this
    # server-side rather than trusting the schema alone).
    outlet_id: uuid.UUID
    address_id: uuid.UUID


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
    status_label: str
    is_modifiable: bool
    is_cancellable: bool
    eta_start: datetime | None
    eta_end: datetime | None
    # Pre-formatted, already-in-local-time (e.g. "between 2:52 PM and
    # 3:02 PM") — see app/utils/time_format.py's docstring for why this
    # exists alongside the raw UTC datetimes above: a real bug had the
    # call agent reading eta_start's raw UTC value as if it were already
    # local time. Every chat/voice/call channel should read and speak
    # THIS field verbatim, never compute/convert eta_start/eta_end itself
    # (see the system prompts' "How to use tools" sections).
    eta_text: str
    created_at: datetime
    items: list[OrderItemRead]


def order_to_read(order: "Order") -> OrderRead:
    """
    Single source of truth for turning an Order ORM object into the API
    shape. Used by the REST endpoints AND the LLM tool executor, so a
    customer gets an identical order representation whether they're using
    /docs or the chat assistant.

    is_modifiable/is_cancellable are the SAME order_statuses flags that
    order_service already enforces server-side (OrderNotModifiableError /
    OrderNotCancellableError) — exposed here so a UI can hide edit/cancel
    controls for orders that can't accept them, instead of showing
    controls that always fail.
    """
    return OrderRead(
        id=order.id,
        order_number=order.order_number,
        outlet_id=order.outlet_id,
        address_id=order.address_id,
        fulfillment_type=order.fulfillment_type,
        total_amount=float(order.total_amount),
        status=order.status.code,
        status_label=order.status.label,
        is_modifiable=order.status.is_modifiable,
        is_cancellable=order.status.is_cancellable,
        eta_start=order.eta_start,
        eta_end=order.eta_end,
        eta_text=_eta_text(order.eta_start, order.eta_end),
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
