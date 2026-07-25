import uuid
from datetime import datetime
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.config import settings
from app.models.conversation import Conversation, Message
from app.models.order import Order, OrderItem
from app.models.user import User

# Orders in these states aren't "active" for greeting purposes — nothing
# left to report on.
_INACTIVE_STATUS_CODES = {"delivered", "cancelled"}


def _format_time(dt: datetime) -> str:
    local = dt.astimezone(ZoneInfo(settings.DISPLAY_TIMEZONE))
    # %-I isn't portable (fails on Windows) — strip the leading zero manually instead.
    return local.strftime("%I:%M %p").lstrip("0")


def _format_qty(value: float) -> str:
    return f"{value:g}"


def _eta_text(order: Order) -> str:
    if order.eta_start and order.eta_end:
        return f"between {_format_time(order.eta_start)} and {_format_time(order.eta_end)}"
    if order.eta_start:
        return f"ready by {_format_time(order.eta_start)}"
    return "not available yet"


def _item_list_text(order: Order) -> str:
    parts = [f"{_format_qty(float(i.quantity))} {i.product.unit} {i.product.name}" for i in order.items]
    return ", ".join(parts) if parts else "—"


async def _get_active_order(db: AsyncSession, user_id: uuid.UUID) -> Order | None:
    result = await db.execute(
        select(Order)
        .options(
            selectinload(Order.status),
            selectinload(Order.items).selectinload(OrderItem.product),
            selectinload(Order.outlet),
        )
        .where(Order.user_id == user_id)
        .order_by(Order.created_at.desc())
    )
    for order in result.scalars().all():
        if order.status.code not in _INACTIVE_STATUS_CODES:
            return order
    return None


def _build_greeting_text(user: User, order: Order | None) -> str:
    first_name = user.name.split()[0] if user.name else "there"

    if order is None:
        return (
            f"Welcome back, {first_name}! Great to see you again. I can help you:\n"
            f"• Place an order\n"
            f"• Track an existing order\n"
            f"• Manage your cart\n"
            f"• Answer questions about our products\n"
            f"• Get support with any issue\n\n"
            f"What can I help you with today?"
        )

    outlet_name = order.outlet.name if order.outlet else "—"

    return (
        f"Welcome back, {first_name}! Here's where things stand with order #{order.order_number}:\n"
        f"• Status: {order.status.label}\n"
        f"• Items: {_item_list_text(order)}\n"
        f"• Outlet: {outlet_name}\n"
        f"• ETA: {_eta_text(order)}\n\n"
        f"Is there anything else I can help you with today?"
    )


async def start_conversation_with_greeting(db: AsyncSession, user: User) -> tuple[uuid.UUID, str]:
    """
    Deliberately NOT an LLM call. Every fact in the greeting (name, order
    number, status, items, outlet, ETA) is already known with certainty
    from the database — routing it through the model would only add
    latency, cost, and a chance of the wording drifting from the actual
    data. The greeting is persisted as the conversation's first message, so
    when the customer's real first message arrives, the model already has
    it as context and won't re-greet.
    """
    conversation = Conversation(user_id=user.id, channel="chat")
    db.add(conversation)
    await db.flush()

    order = await _get_active_order(db, user.id)
    greeting_text = _build_greeting_text(user, order)

    db.add(Message(conversation_id=conversation.id, role="assistant", content=greeting_text))
    await db.commit()

    return conversation.id, greeting_text
