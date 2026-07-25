import uuid

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import Address


class AddressNotFoundError(Exception):
    pass


class AddressInUseError(Exception):
    pass


async def list_addresses(db: AsyncSession, user_id: uuid.UUID) -> list[Address]:
    result = await db.execute(select(Address).where(Address.user_id == user_id).order_by(Address.created_at))
    return list(result.scalars().all())


async def get_address(db: AsyncSession, user_id: uuid.UUID, address_id: uuid.UUID) -> Address:
    result = await db.execute(select(Address).where(Address.id == address_id, Address.user_id == user_id))
    address = result.scalar_one_or_none()
    if address is None:
        raise AddressNotFoundError()
    return address


async def _unset_other_defaults(db: AsyncSession, user_id: uuid.UUID, except_id: uuid.UUID) -> None:
    result = await db.execute(
        select(Address).where(Address.user_id == user_id, Address.is_default == True, Address.id != except_id)  # noqa: E712
    )
    for addr in result.scalars().all():
        addr.is_default = False


async def create_address(
    db: AsyncSession,
    user_id: uuid.UUID,
    label: str,
    address_text: str,
    lat: float | None,
    lng: float | None,
    is_default: bool,
) -> Address:
    existing = await list_addresses(db, user_id)
    make_default = is_default or not existing  # a user's first address is always their default

    try:
        address = Address(
            user_id=user_id, label=label, address_text=address_text, lat=lat, lng=lng, is_default=make_default
        )
        db.add(address)
        await db.flush()

        if make_default:
            await _unset_other_defaults(db, user_id, except_id=address.id)

        await db.commit()
        await db.refresh(address)
    except Exception:
        await db.rollback()
        raise
    return address


async def update_address(
    db: AsyncSession,
    user_id: uuid.UUID,
    address_id: uuid.UUID,
    label: str | None,
    address_text: str | None,
    lat: float | None,
    lng: float | None,
    is_default: bool | None,
) -> Address:
    address = await get_address(db, user_id, address_id)

    try:
        if label is not None:
            address.label = label
        if address_text is not None:
            address.address_text = address_text
        if lat is not None:
            address.lat = lat
        if lng is not None:
            address.lng = lng

        if is_default is True:
            address.is_default = True
            await _unset_other_defaults(db, user_id, except_id=address.id)
        elif is_default is False:
            address.is_default = False

        await db.commit()
        await db.refresh(address)
    except Exception:
        await db.rollback()
        raise
    return address


async def delete_address(db: AsyncSession, user_id: uuid.UUID, address_id: uuid.UUID) -> None:
    address = await get_address(db, user_id, address_id)
    was_default = address.is_default

    try:
        await db.delete(address)
        await db.flush()

        if was_default:
            remaining = await list_addresses(db, user_id)
            if remaining:
                remaining[0].is_default = True

        await db.commit()
    except IntegrityError:
        # An order still references this address (orders.address_id has no
        # cascade on purpose — deleting an address shouldn't silently orphan
        # order history).
        await db.rollback()
        raise AddressInUseError()
    except Exception:
        await db.rollback()
        raise
