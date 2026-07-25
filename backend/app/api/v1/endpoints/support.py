import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.db.session import get_db
from app.models.user import User
from app.schemas.support import SupportTicketCreate, SupportTicketRead
from app.services import support_service

router = APIRouter()


@router.get("", response_model=list[SupportTicketRead])
async def list_tickets(current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    return await support_service.list_tickets(db, current_user.id)


@router.post("", response_model=SupportTicketRead, status_code=status.HTTP_201_CREATED)
async def create_ticket(
    data: SupportTicketCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    try:
        return await support_service.create_ticket(db, current_user.id, data.issue_text, data.order_id)
    except support_service.OrderNotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Order not found")


@router.get("/{ticket_id}", response_model=SupportTicketRead)
async def get_ticket(
    ticket_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    try:
        return await support_service.get_ticket(db, current_user.id, ticket_id)
    except support_service.TicketNotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Ticket not found")
