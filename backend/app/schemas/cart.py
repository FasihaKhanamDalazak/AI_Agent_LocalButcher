from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from pydantic import BaseModel, ConfigDict, Field

if TYPE_CHECKING:
    from app.models.cart import CartItem
    from app.models.product import Product


class CartItemCreate(BaseModel):
    product_id: uuid.UUID
    quantity: float = Field(gt=0)


class CartItemUpdate(BaseModel):
    quantity: float = Field(gt=0)


class CartItemReadDetailed(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    product_id: uuid.UUID
    quantity: float
    product_name: str
    unit: str
    price: float
    line_total: float


class CartRead(BaseModel):
    items: list[CartItemReadDetailed]
    subtotal: float


def cart_item_to_detailed(item: "CartItem", product: "Product") -> CartItemReadDetailed:
    """Shared by the REST cart endpoints and the LLM tool executor."""
    return CartItemReadDetailed(
        id=item.id,
        product_id=item.product_id,
        quantity=float(item.quantity),
        product_name=product.name,
        unit=product.unit,
        price=float(product.price),
        line_total=round(float(item.quantity) * float(product.price), 2),
    )
