import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.outlet import Outlet
from app.models.product import OutletStock
from app.models.user import Address
from app.utils.geo import haversine_km


class OutletNotFoundError(Exception):
    pass


async def check_availability(
    db: AsyncSession,
    product_id: uuid.UUID,
    outlet_id: uuid.UUID,
    quantity: float,
    address_id: uuid.UUID | None = None,
    user_id: uuid.UUID | None = None,
) -> dict:
    """
    Checks stock at `outlet_id` first. If it can't cover `quantity`, searches
    every other active outlet for the nearest one that can — nearest to the
    customer's address if one was supplied, otherwise nearest to the
    original outlet. This is the function behind:

        "2kg lamb isn't available at your outlet, but Banjara Hills has it —
         want me to check delivery from there?"
    """
    outlet = await db.get(Outlet, outlet_id)
    if outlet is None:
        raise OutletNotFoundError()

    result = await db.execute(
        select(OutletStock).where(
            OutletStock.outlet_id == outlet_id,
            OutletStock.product_id == product_id,
        )
    )
    stock = result.scalar_one_or_none()
    available_qty = float(stock.quantity) if stock else 0.0

    response: dict = {
        "product_id": product_id,
        "outlet_id": outlet_id,
        "outlet_name": outlet.name,
        "available": available_qty >= quantity,
        "quantity_available": available_qty,
        "alternate_outlet": None,
        "alternate_outlet_distance_km": None,
        "alternate_covers_delivery": None,
    }
    if response["available"]:
        return response

    # Not enough at the assigned outlet — look for the nearest outlet that
    # actually has it, rather than just reporting "out of stock."
    alt_result = await db.execute(
        select(Outlet)
        .join(OutletStock, OutletStock.outlet_id == Outlet.id)
        .where(
            OutletStock.product_id == product_id,
            OutletStock.outlet_id != outlet_id,
            OutletStock.quantity >= quantity,
            Outlet.is_active == True,  # noqa: E712
        )
    )
    candidates = list(alt_result.scalars().all())
    if not candidates:
        return response

    # Prefer distance from the customer's own address (and only their own —
    # ownership is checked here, never trust an address_id blindly).
    address = None
    if address_id is not None and user_id is not None:
        address = await db.get(Address, address_id)
        if address is not None and address.user_id != user_id:
            address = None

    if address is not None and address.lat is not None and address.lng is not None:
        origin_lat, origin_lng = address.lat, address.lng
    else:
        origin_lat, origin_lng = outlet.lat, outlet.lng

    scored = [(o, haversine_km(origin_lat, origin_lng, o.lat, o.lng)) for o in candidates]
    scored.sort(key=lambda pair: pair[1])
    nearest_outlet, distance = scored[0]

    response["alternate_outlet"] = nearest_outlet
    response["alternate_outlet_distance_km"] = round(distance, 2)
    response["alternate_covers_delivery"] = distance <= nearest_outlet.delivery_radius_km

    return response
