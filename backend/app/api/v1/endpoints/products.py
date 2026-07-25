import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.db.session import get_db
from app.models.user import User
from app.schemas.product import AvailabilityResult, ProductRead
from app.services import availability_service, product_service

router = APIRouter()


@router.get("", response_model=list[ProductRead])
async def list_products(category: str | None = Query(default=None), db: AsyncSession = Depends(get_db)):
    return await product_service.list_products(db, category=category)


@router.get("/{product_id}/availability", response_model=AvailabilityResult)
async def check_availability(
    product_id: uuid.UUID,
    outlet_id: uuid.UUID = Query(...),
    quantity: float = Query(default=1, gt=0),
    address_id: uuid.UUID | None = Query(default=None),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    try:
        return await availability_service.check_availability(
            db, product_id, outlet_id, quantity, address_id=address_id, user_id=current_user.id
        )
    except availability_service.OutletNotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Outlet not found")
