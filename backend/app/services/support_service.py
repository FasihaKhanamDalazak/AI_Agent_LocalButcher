import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.order import Order
from app.models.support import SupportTicket


class OrderNotFoundError(Exception):
    pass


class TicketNotFoundError(Exception):
    pass


async def create_ticket(
    db: AsyncSession, user_id: uuid.UUID, issue_text: str, order_id: uuid.UUID | None
) -> SupportTicket:
    if order_id is not None:
        order = await db.get(Order, order_id)
        if order is None or order.user_id != user_id:
            raise OrderNotFoundError()

    try:
        ticket = SupportTicket(user_id=user_id, order_id=order_id, issue_text=issue_text, status="open")
        db.add(ticket)
        await db.commit()
        await db.refresh(ticket)
    except Exception:
        await db.rollback()
        raise
    return ticket


async def list_tickets(db: AsyncSession, user_id: uuid.UUID) -> list[SupportTicket]:
    result = await db.execute(
        select(SupportTicket).where(SupportTicket.user_id == user_id).order_by(SupportTicket.created_at.desc())
    )
    return list(result.scalars().all())


async def get_ticket(db: AsyncSession, user_id: uuid.UUID, ticket_id: uuid.UUID) -> SupportTicket:
    result = await db.execute(
        select(SupportTicket).where(SupportTicket.id == ticket_id, SupportTicket.user_id == user_id)
    )
    ticket = result.scalar_one_or_none()
    if ticket is None:
        raise TicketNotFoundError()
    return ticket
