import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.db.session import get_db
from app.models.order import Order
from app.models.user import User
from app.schemas.order import CheckoutRequest, OrderItemModify, OrderRead, order_to_read
from app.services import order_service

router = APIRouter()
_to_order_read = order_to_read  # local alias, keeps the calls below unchanged


@router.post("/checkout", response_model=OrderRead, status_code=status.HTTP_201_CREATED)
async def checkout(
    data: CheckoutRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    try:
        order = await order_service.checkout(
            db, current_user.id, data.outlet_id, data.fulfillment_type, data.address_id
        )
    except order_service.EmptyCartError:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Cart is empty")
    except order_service.AddressRequiredError:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="address_id is required for delivery")
    except order_service.AddressNotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Address not found")
    except order_service.InsufficientStockError as e:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Only {e.available} of {e.product_name} available at this outlet",
        )
    return _to_order_read(order)


@router.get("", response_model=list[OrderRead])
async def list_orders(current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    orders = await order_service.list_orders(db, current_user.id)
    return [_to_order_read(o) for o in orders]


@router.get("/{order_id}", response_model=OrderRead)
async def get_order(
    order_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    try:
        order = await order_service.get_order(db, current_user.id, order_id)
    except order_service.OrderNotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Order not found")
    return _to_order_read(order)


@router.post("/{order_id}/cancel", response_model=OrderRead)
async def cancel_order(
    order_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    try:
        order = await order_service.cancel_order(db, current_user.id, order_id)
    except order_service.OrderNotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Order not found")
    except order_service.OrderNotCancellableError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Order cannot be cancelled — it is already {e.status_label}",
        )
    return _to_order_read(order)


@router.patch("/{order_id}/items/{item_id}", response_model=OrderRead)
async def update_order_item(
    order_id: uuid.UUID,
    item_id: uuid.UUID,
    data: OrderItemModify,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    try:
        order = await order_service.update_order_item(db, current_user.id, order_id, item_id, data.quantity)
    except order_service.OrderNotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Order not found")
    except order_service.OrderNotModifiableError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Order can no longer be modified — it is already {e.status_label}",
        )
    except order_service.ItemNotInOrderError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Item not found in this order")
    except order_service.QuantityLimitError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Maximum allowed quantity for this product is {e.limit}",
        )
    except order_service.InsufficientStockError as e:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Only {e.available} of {e.product_name} available at this outlet",
        )
    return _to_order_read(order)


@router.delete("/{order_id}/items/{item_id}", response_model=OrderRead)
async def remove_order_item(
    order_id: uuid.UUID,
    item_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    try:
        order = await order_service.remove_order_item(db, current_user.id, order_id, item_id)
    except order_service.OrderNotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Order not found")
    except order_service.OrderNotModifiableError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Order can no longer be modified — it is already {e.status_label}",
        )
    except order_service.ItemNotInOrderError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Item not found in this order")
    except order_service.CannotRemoveLastItemError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot remove the last item in an order — cancel the order instead",
        )
    return _to_order_read(order)
