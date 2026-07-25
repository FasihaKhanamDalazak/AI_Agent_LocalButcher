import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_staff_user
from app.db.session import get_db
from app.models.user import User
from app.schemas.staff import StaffOrderRead, StaffOrderStatusUpdate, staff_order_to_read
from app.services import order_service

router = APIRouter()


@router.get("/orders/{order_id}", response_model=StaffOrderRead)
async def get_order(
    order_id: uuid.UUID,
    current_staff: User = Depends(get_current_staff_user),
    db: AsyncSession = Depends(get_db),
):
    try:
        order = await order_service.get_order_by_id(db, order_id)
    except order_service.OrderNotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Order not found")
    return staff_order_to_read(order)


@router.patch("/orders/{order_id}/status", response_model=StaffOrderRead)
async def update_order_status(
    order_id: uuid.UUID,
    data: StaffOrderStatusUpdate,
    current_staff: User = Depends(get_current_staff_user),
    db: AsyncSession = Depends(get_db),
):
    try:
        order = await order_service.set_order_status(db, order_id, data.status_code, current_staff.id)
    except order_service.OrderNotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Order not found")
    except order_service.InvalidStatusCodeError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    return staff_order_to_read(order)
