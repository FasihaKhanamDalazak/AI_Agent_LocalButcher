import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.outlet import Outlet
from app.models.user import Address
from app.utils.geo import haversine_km


class AddressNotFoundError(Exception):
    pass


class AddressMissingLocationError(Exception):
    """Address exists and is owned by the user, but has no lat/lng on file."""


class NoActiveOutletsError(Exception):
    pass


async def list_outlets(db: AsyncSession) -> list[Outlet]:
    result = await db.execute(select(Outlet).where(Outlet.is_active == True).order_by(Outlet.name))  # noqa: E712
    return list(result.scalars().all())


async def get_outlet(db: AsyncSession, outlet_id: uuid.UUID) -> Outlet | None:
    return await db.get(Outlet, outlet_id)


async def get_nearest_outlet(
    db: AsyncSession, user_id: uuid.UUID, address_id: uuid.UUID
) -> tuple[Outlet, float, bool]:
    """
    Returns (outlet, distance_km, in_range). Prefers the nearest outlet
    that can ACTUALLY deliver to this address (distance <= its own
    delivery_radius_km) — not just the geographically closest one, since
    a closer outlet with a small radius might not reach while a slightly
    farther one with a bigger radius does. If no outlet can deliver here
    at all, returns the closest one anyway with in_range=False so the
    caller can still say "the nearest we have is X, but that's out of
    range" instead of just failing silently.
    """
    address = await db.get(Address, address_id)
    # Ownership check happens here, not just "does this address exist" —
    # nobody can probe outlet distances using someone else's saved address.
    if address is None or address.user_id != user_id:
        raise AddressNotFoundError()
    if address.lat is None or address.lng is None:
        raise AddressMissingLocationError()

    outlets = await list_outlets(db)
    if not outlets:
        raise NoActiveOutletsError()

    scored = [(o, haversine_km(address.lat, address.lng, o.lat, o.lng)) for o in outlets]
    scored.sort(key=lambda pair: pair[1])

    for outlet, distance in scored:
        if distance <= outlet.delivery_radius_km:
            return outlet, distance, True

    nearest_outlet, nearest_distance = scored[0]
    return nearest_outlet, nearest_distance, False
