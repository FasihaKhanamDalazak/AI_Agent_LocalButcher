import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.db.session import get_db
from app.models.user import User
from app.schemas.address import AddressCreate, AddressRead, AddressUpdate
from app.services import address_service

router = APIRouter()


@router.get("", response_model=list[AddressRead])
async def list_addresses(current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    return await address_service.list_addresses(db, current_user.id)


@router.post("", response_model=AddressRead, status_code=status.HTTP_201_CREATED)
async def create_address(
    data: AddressCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    try:
        return await address_service.create_address(
            db, current_user.id, data.label, data.address_text, data.lat, data.lng, data.is_default
        )
    except address_service.AddressLimitReachedError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"You can save up to {address_service.MAX_ADDRESSES_PER_USER} addresses — "
            "delete one before adding another.",
        )
    except address_service.DuplicateLabelError as e:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail=f"An address labeled '{e.label}' already exists."
        )


@router.patch("/{address_id}", response_model=AddressRead)
async def update_address(
    address_id: uuid.UUID,
    data: AddressUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    try:
        return await address_service.update_address(
            db,
            current_user.id,
            address_id,
            label=data.label,
            address_text=data.address_text,
            lat=data.lat,
            lng=data.lng,
            is_default=data.is_default,
        )
    except address_service.AddressNotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Address not found")
    except address_service.DuplicateLabelError as e:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail=f"An address labeled '{e.label}' already exists."
        )


@router.delete("/{address_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_address(
    address_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    try:
        await address_service.delete_address(db, current_user.id, address_id)
    except address_service.AddressNotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Address not found")
    except address_service.AddressInUseError:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Cannot delete an address that's used by an existing order",
        )
