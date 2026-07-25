import uuid
from datetime import datetime, timedelta, timezone
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.config import settings
from app.models.audit import AuditLog
from app.models.cart import CartItem
from app.models.order import Order, OrderItem, OrderStatus
from app.models.outlet import Outlet
from app.models.product import OutletStock, Product
from app.models.user import Address
from app.services import cart_service
from app.services.cart_service import QuantityLimitError  # re-raised as-is, same meaning here
from app.utils.geo import haversine_km


class EmptyCartError(Exception):
    pass


class AddressRequiredError(Exception):
    pass


class AddressNotFoundError(Exception):
    pass


class OutletNotFoundError(Exception):
    pass


class AddressMissingLocationError(Exception):
    """Address exists and is owned by the user, but has no lat/lng on file — can't validate delivery range."""


class DeliveryOutOfRangeError(Exception):
    def __init__(self, outlet_name: str, distance_km: float, radius_km: float):
        self.outlet_name = outlet_name
        self.distance_km = distance_km
        self.radius_km = radius_km
        super().__init__(f"{outlet_name} delivers within {radius_km} km; address is {distance_km:.1f} km away")


class OrderNotFoundError(Exception):
    pass


class ItemNotInOrderError(Exception):
    pass


class CannotRemoveLastItemError(Exception):
    pass


class OrderNotCancellableError(Exception):
    def __init__(self, status_label: str):
        self.status_label = status_label
        super().__init__(f"Order cannot be cancelled from status '{status_label}'")


class OrderNotModifiableError(Exception):
    def __init__(self, status_label: str):
        self.status_label = status_label
        super().__init__(f"Order cannot be modified from status '{status_label}'")


class InsufficientStockError(Exception):
    def __init__(self, product_id: uuid.UUID, product_name: str, available: float):
        self.product_id = product_id
        self.product_name = product_name
        self.available = available
        super().__init__(f"Only {available} of {product_name} available")


class InvalidStatusCodeError(Exception):
    def __init__(self, status_code: str):
        self.status_code = status_code
        super().__init__(f"'{status_code}' is not a valid order status")


async def _get_status_by_code(db: AsyncSession, code: str) -> OrderStatus:
    result = await db.execute(select(OrderStatus).where(OrderStatus.code == code))
    row = result.scalar_one_or_none()
    if row is None:
        # Missing seed data is a setup bug, not a user-facing error.
        raise RuntimeError(f"order_statuses is missing the required '{code}' row — did the seed migration run?")
    return row


async def _get_status_by_code_or_none(db: AsyncSession, code: str) -> OrderStatus | None:
    """Used for staff-supplied status codes, where an unknown code is a normal user error, not a bug."""
    result = await db.execute(select(OrderStatus).where(OrderStatus.code == code))
    return result.scalar_one_or_none()


def _calculate_eta(fulfillment_type: str) -> tuple[datetime | None, datetime | None]:
    """
    Placeholder heuristic: prep time + a delivery window, from now. No real
    logistics/rider-tracking data exists yet — replace this function when
    it does. Everything downstream reads from order.eta_start/eta_end, so
    that swap won't touch any calling code.
    """
    now = datetime.now(timezone.utc)
    prep = timedelta(minutes=settings.ORDER_PREP_MINUTES)

    if fulfillment_type == "pickup":
        return now + prep, None  # single "ready by" time, no window

    window_min = timedelta(minutes=settings.DELIVERY_WINDOW_MIN_MINUTES)
    window_max = timedelta(minutes=settings.DELIVERY_WINDOW_MAX_MINUTES)
    return now + prep + window_min, now + prep + window_max


async def _lock_stock_row(db: AsyncSession, outlet_id: uuid.UUID, product_id: uuid.UUID) -> OutletStock | None:
    result = await db.execute(
        select(OutletStock)
        .where(OutletStock.outlet_id == outlet_id, OutletStock.product_id == product_id)
        .with_for_update()
    )
    return result.scalar_one_or_none()


async def get_order(db: AsyncSession, user_id: uuid.UUID, order_id: uuid.UUID) -> Order:
    result = await db.execute(
        select(Order)
        .options(selectinload(Order.items), selectinload(Order.status))
        .where(Order.id == order_id, Order.user_id == user_id)
    )
    order = result.scalar_one_or_none()
    if order is None:
        raise OrderNotFoundError()
    return order


async def get_order_by_id(db: AsyncSession, order_id: uuid.UUID) -> Order:
    """
    Staff-only lookup — deliberately NOT scoped to a user_id, since staff
    need to look up any customer's order. Only ever call this from behind
    get_current_staff_user; never expose it to a customer-facing endpoint.
    """
    result = await db.execute(
        select(Order).options(selectinload(Order.items), selectinload(Order.status)).where(Order.id == order_id)
    )
    order = result.scalar_one_or_none()
    if order is None:
        raise OrderNotFoundError()
    return order


async def list_orders(db: AsyncSession, user_id: uuid.UUID) -> list[Order]:
    result = await db.execute(
        select(Order)
        .options(selectinload(Order.items), selectinload(Order.status))
        .where(Order.user_id == user_id)
        .order_by(Order.created_at.desc())
    )
    return list(result.scalars().all())


async def checkout(
    db: AsyncSession,
    user_id: uuid.UUID,
    outlet_id: uuid.UUID,
    fulfillment_type: str,
    address_id: uuid.UUID | None,
) -> Order:
    if fulfillment_type == "delivery" and address_id is None:
        raise AddressRequiredError()

    outlet = await db.get(Outlet, outlet_id)
    if outlet is None:
        raise OutletNotFoundError()

    if address_id is not None:
        address = await db.get(Address, address_id)
        if address is None or address.user_id != user_id:
            raise AddressNotFoundError()

        # Local Butcher only serves within each outlet's delivery radius —
        # validated here (not just left to get_nearest_outlet upstream) so
        # a stale/guessed outlet_id can never produce an undeliverable
        # order. Addresses added via chat never get coordinates (the model
        # never fabricates lat/lng — see add_address), so this must be a
        # hard requirement, never silently skipped, or an unvalidated
        # address would sail through checkout with no range check at all.
        if fulfillment_type == "delivery":
            if address.lat is None or address.lng is None:
                raise AddressMissingLocationError(address.label)
            distance = haversine_km(address.lat, address.lng, outlet.lat, outlet.lng)
            if distance > outlet.delivery_radius_km:
                raise DeliveryOutOfRangeError(outlet.name, distance, outlet.delivery_radius_km)

    cart_rows = await cart_service.get_cart(db, user_id)
    if not cart_rows:
        raise EmptyCartError()

    try:
        total = Decimal("0")
        locked_items: list[tuple[Product, Decimal]] = []

        # Lock and validate every line before writing anything — if any one
        # item is short, the whole checkout fails and nothing is deducted.
        for cart_item, product in cart_rows:
            qty = Decimal(str(cart_item.quantity))
            stock = await _lock_stock_row(db, outlet_id, product.id)
            available = stock.quantity if stock else Decimal("0")
            if available < qty:
                raise InsufficientStockError(product.id, product.name, float(available))

            stock.quantity = available - qty
            stock.version += 1
            locked_items.append((product, qty))
            total += product.price * qty

        pending_status = await _get_status_by_code(db, "pending")
        eta_start, eta_end = _calculate_eta(fulfillment_type)

        order = Order(
            user_id=user_id,
            outlet_id=outlet_id,
            address_id=address_id,
            status_id=pending_status.id,
            fulfillment_type=fulfillment_type,
            total_amount=total,
            eta_start=eta_start,
            eta_end=eta_end,
        )
        db.add(order)
        await db.flush()  # assigns order.id without committing yet

        for product, qty in locked_items:
            db.add(OrderItem(order_id=order.id, product_id=product.id, quantity=qty, price_at_order=product.price))

        for cart_item, _ in cart_rows:
            await db.delete(cart_item)

        db.add(
            AuditLog(
                entity_type="order",
                entity_id=order.id,
                action="created",
                actor_user_id=user_id,
                details={"outlet_id": str(outlet_id), "total_amount": float(total)},
            )
        )

        await db.commit()
    except Exception:
        await db.rollback()
        raise

    return await get_order(db, user_id, order.id)


async def _restore_stock_and_cancel(db: AsyncSession, order: Order, actor_user_id: uuid.UUID) -> None:
    """Shared by cancel_order (customer) and set_order_status (staff) so the stock-restore logic never drifts apart between the two paths."""
    for item in order.items:
        stock = await _lock_stock_row(db, order.outlet_id, item.product_id)
        if stock is None:
            # Defensive: the stock row shouldn't be gone, but don't lose
            # the restore if it somehow is.
            stock = OutletStock(outlet_id=order.outlet_id, product_id=item.product_id, quantity=0, version=0)
            db.add(stock)
            await db.flush()
        stock.quantity = stock.quantity + item.quantity
        stock.version += 1

    cancelled_status = await _get_status_by_code(db, "cancelled")
    order.status_id = cancelled_status.id

    db.add(AuditLog(entity_type="order", entity_id=order.id, action="cancelled", actor_user_id=actor_user_id, details=None))


async def cancel_order(db: AsyncSession, user_id: uuid.UUID, order_id: uuid.UUID) -> Order:
    order = await get_order(db, user_id, order_id)
    if not order.status.is_cancellable:
        raise OrderNotCancellableError(order.status.label)

    try:
        await _restore_stock_and_cancel(db, order, user_id)
        await db.commit()
    except Exception:
        await db.rollback()
        raise

    return await get_order(db, user_id, order.id)


async def set_order_status(db: AsyncSession, order_id: uuid.UUID, status_code: str, actor_user_id: uuid.UUID) -> Order:
    """
    Staff-only status override. Unlike the customer-facing cancel/modify
    paths, this ignores is_modifiable/is_cancellable — staff need to be able
    to force a state regardless (e.g. mark something "packed" even though
    that state isn't customer-cancellable). Cancelling through this path
    still goes through the shared stock-restore logic, so inventory can
    never go out of sync no matter which door someone cancelled through.
    """
    order = await get_order_by_id(db, order_id)
    new_status = await _get_status_by_code_or_none(db, status_code)
    if new_status is None:
        raise InvalidStatusCodeError(status_code)

    try:
        if status_code == "cancelled":
            await _restore_stock_and_cancel(db, order, actor_user_id)
        else:
            order.status_id = new_status.id
            db.add(
                AuditLog(
                    entity_type="order",
                    entity_id=order.id,
                    action="status_updated",
                    actor_user_id=actor_user_id,
                    details={"new_status": status_code},
                )
            )
        await db.commit()
    except Exception:
        await db.rollback()
        raise

    return await get_order_by_id(db, order_id)


async def update_order_item(
    db: AsyncSession, user_id: uuid.UUID, order_id: uuid.UUID, item_id: uuid.UUID, new_quantity: float
) -> Order:
    order = await get_order(db, user_id, order_id)
    if not order.status.is_modifiable:
        raise OrderNotModifiableError(order.status.label)

    item = next((i for i in order.items if i.id == item_id), None)
    if item is None:
        raise ItemNotInOrderError()

    product = await db.get(Product, item.product_id)
    max_qty = float(product.max_qty_per_order)
    if new_quantity > max_qty:
        raise QuantityLimitError(max_qty)

    new_qty_decimal = Decimal(str(new_quantity))
    delta = new_qty_decimal - item.quantity  # positive = needs more stock, negative = returns stock

    try:
        stock = await _lock_stock_row(db, order.outlet_id, item.product_id)
        available = stock.quantity if stock else Decimal("0")

        if delta > 0 and available < delta:
            raise InsufficientStockError(product.id, product.name, float(available))

        if stock is not None:
            stock.quantity = available - delta
            stock.version += 1

        order.total_amount = order.total_amount + (item.price_at_order * delta)
        item.quantity = new_qty_decimal

        db.add(
            AuditLog(
                entity_type="order",
                entity_id=order.id,
                action="modified",
                actor_user_id=user_id,
                details={"item_id": str(item_id), "new_quantity": new_quantity},
            )
        )

        await db.commit()
    except Exception:
        await db.rollback()
        raise

    return await get_order(db, user_id, order.id)


async def remove_order_item(db: AsyncSession, user_id: uuid.UUID, order_id: uuid.UUID, item_id: uuid.UUID) -> Order:
    order = await get_order(db, user_id, order_id)
    if not order.status.is_modifiable:
        raise OrderNotModifiableError(order.status.label)

    item = next((i for i in order.items if i.id == item_id), None)
    if item is None:
        raise ItemNotInOrderError()

    if len(order.items) == 1:
        # Removing the only item would leave an empty order — cancel instead.
        raise CannotRemoveLastItemError()

    try:
        stock = await _lock_stock_row(db, order.outlet_id, item.product_id)
        if stock is not None:
            stock.quantity = stock.quantity + item.quantity
            stock.version += 1

        order.total_amount = order.total_amount - (item.price_at_order * item.quantity)
        await db.delete(item)

        db.add(
            AuditLog(
                entity_type="order",
                entity_id=order.id,
                action="modified",
                actor_user_id=user_id,
                details={"removed_item_id": str(item_id)},
            )
        )

        await db.commit()
    except Exception:
        await db.rollback()
        raise

    return await get_order(db, user_id, order.id)


async def reorder(
    db: AsyncSession, user_id: uuid.UUID, order_id: uuid.UUID | None
) -> tuple[list[tuple[CartItem, Product]], list[dict]]:
    """
    Copies items from a previous order back into the customer's CURRENT
    cart — it does not re-checkout automatically. The customer still
    reviews and confirms, same as adding anything else. If order_id is
    omitted, uses the customer's most recently placed order.

    Returns (added, skipped): `added` is what actually landed in the cart;
    `skipped` explains anything that couldn't be added (product no longer
    available, would exceed the per-order quantity limit) so the caller
    can tell the customer honestly rather than silently dropping items.
    """
    if order_id is not None:
        order = await get_order(db, user_id, order_id)
    else:
        orders = await list_orders(db, user_id)
        if not orders:
            raise OrderNotFoundError()
        order = orders[0]

    added: list[tuple[CartItem, Product]] = []
    skipped: list[dict] = []

    for item in order.items:
        try:
            cart_item, product = await cart_service.add_to_cart(db, user_id, item.product_id, float(item.quantity))
            added.append((cart_item, product))
        except cart_service.ProductNotFoundError:
            skipped.append({"product_id": str(item.product_id), "reason": "no longer available"})
        except cart_service.QuantityLimitError as e:
            # Don't auto-cap and re-add here — if the customer already has
            # some of this product in their cart, a second add() would add
            # e.limit on TOP of that, potentially exceeding the limit again.
            # Safer to skip and let the customer adjust manually.
            skipped.append(
                {"product_id": str(item.product_id), "reason": f"would exceed the maximum allowed quantity ({e.limit})"}
            )

    return added, skipped
