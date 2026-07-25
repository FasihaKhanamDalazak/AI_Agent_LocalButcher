import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.cart import CartItem
from app.models.product import Product


class ProductNotFoundError(Exception):
    pass


class CartItemNotFoundError(Exception):
    pass


class QuantityLimitError(Exception):
    def __init__(self, limit: float):
        self.limit = limit
        super().__init__(f"Maximum allowed quantity is {limit}")


async def _get_active_product(db: AsyncSession, product_id: uuid.UUID) -> Product:
    product = await db.get(Product, product_id)
    if product is None or not product.is_active:
        raise ProductNotFoundError()
    return product


async def get_cart(db: AsyncSession, user_id: uuid.UUID) -> list[tuple[CartItem, Product]]:
    result = await db.execute(
        select(CartItem, Product)
        .join(Product, Product.id == CartItem.product_id)
        .where(CartItem.user_id == user_id)
        .order_by(CartItem.created_at)
    )
    return [(item, product) for item, product in result.all()]


async def add_to_cart(
    db: AsyncSession, user_id: uuid.UUID, product_id: uuid.UUID, quantity: float
) -> tuple[CartItem, Product]:
    product = await _get_active_product(db, product_id)
    max_qty = float(product.max_qty_per_order)

    if quantity > max_qty:
        raise QuantityLimitError(max_qty)

    result = await db.execute(
        select(CartItem).where(CartItem.user_id == user_id, CartItem.product_id == product_id)
    )
    existing = result.scalar_one_or_none()

    if existing is not None:
        new_qty = float(existing.quantity) + quantity
        if new_qty > max_qty:
            raise QuantityLimitError(max_qty)
        existing.quantity = new_qty
        await db.commit()
        await db.refresh(existing)
        return existing, product

    item = CartItem(user_id=user_id, product_id=product_id, quantity=quantity)
    db.add(item)
    await db.commit()
    await db.refresh(item)
    return item, product


async def update_cart_item(
    db: AsyncSession, user_id: uuid.UUID, item_id: uuid.UUID, quantity: float
) -> tuple[CartItem, Product]:
    result = await db.execute(select(CartItem).where(CartItem.id == item_id, CartItem.user_id == user_id))
    item = result.scalar_one_or_none()
    if item is None:
        raise CartItemNotFoundError()

    product = await _get_active_product(db, item.product_id)
    max_qty = float(product.max_qty_per_order)
    if quantity > max_qty:
        raise QuantityLimitError(max_qty)

    item.quantity = quantity
    await db.commit()
    await db.refresh(item)
    return item, product


async def remove_from_cart(db: AsyncSession, user_id: uuid.UUID, item_id: uuid.UUID) -> None:
    result = await db.execute(select(CartItem).where(CartItem.id == item_id, CartItem.user_id == user_id))
    item = result.scalar_one_or_none()
    if item is None:
        raise CartItemNotFoundError()
    await db.delete(item)
    await db.commit()
