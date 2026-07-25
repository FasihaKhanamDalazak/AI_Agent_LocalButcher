import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.db.session import get_db
from app.models.user import User
from app.schemas.outlet import OutletDistance, OutletRead
from app.services import outlet_service

router = APIRouter()


@router.get("", response_model=list[OutletRead])
async def list_outlets(db: AsyncSession = Depends(get_db)):
    return await outlet_service.list_outlets(db)


# Registered before /{outlet_id} on purpose — otherwise FastAPI would try
# to parse "nearest" as a UUID path param and this route would never match.
@router.get("/nearest", response_model=OutletDistance)
async def nearest_outlet(
    address_id: uuid.UUID = Query(...),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    try:
        outlet, distance = await outlet_service.get_nearest_outlet(db, current_user.id, address_id)
    except outlet_service.AddressNotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Address not found")
    except outlet_service.NoActiveOutletsError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No active outlets available")

    return OutletDistance(**OutletRead.model_validate(outlet).model_dump(), distance_km=round(distance, 2))


@router.get("/{outlet_id}", response_model=OutletRead)
async def get_outlet(outlet_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    outlet = await outlet_service.get_outlet(db, outlet_id)
    if outlet is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Outlet not found")
    return outlet
