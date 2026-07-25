import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.db.session import get_db
from app.models.user import User
from app.schemas.cart import CartItemCreate, CartItemUpdate, CartRead, CartItemReadDetailed, cart_item_to_detailed
from app.services import cart_service

router = APIRouter()
_to_detailed = cart_item_to_detailed  # local alias, keeps the calls below unchanged


@router.get("", response_model=CartRead)
async def get_cart(current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    rows = await cart_service.get_cart(db, current_user.id)
    items = [_to_detailed(item, product) for item, product in rows]
    return CartRead(items=items, subtotal=round(sum(i.line_total for i in items), 2))


@router.post("/items", response_model=CartItemReadDetailed, status_code=status.HTTP_201_CREATED)
async def add_item(
    data: CartItemCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    try:
        item, product = await cart_service.add_to_cart(db, current_user.id, data.product_id, data.quantity)
    except cart_service.ProductNotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Product not found")
    except cart_service.QuantityLimitError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Maximum allowed quantity for this product is {e.limit}",
        )
    return _to_detailed(item, product)


@router.patch("/items/{item_id}", response_model=CartItemReadDetailed)
async def update_item(
    item_id: uuid.UUID,
    data: CartItemUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    try:
        item, product = await cart_service.update_cart_item(db, current_user.id, item_id, data.quantity)
    except cart_service.CartItemNotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Cart item not found")
    except cart_service.QuantityLimitError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Maximum allowed quantity for this product is {e.limit}",
        )
    return _to_detailed(item, product)


@router.delete("/items/{item_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_item(
    item_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    try:
        await cart_service.remove_from_cart(db, current_user.id, item_id)
    except cart_service.CartItemNotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Cart item not found")
