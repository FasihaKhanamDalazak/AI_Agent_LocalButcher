import re
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.llm.deepgram_chat_client import run_conversation_turn
from app.llm.gemini_client import AssistantUnavailableError  # noqa: F401 - re-exported for callers
from app.llm.safety_filter import filter_reply
from app.models.conversation import Conversation, Message
from app.models.user import User
from app.services import cart_service

# Only the last N *text* turns are replayed to the model as context — no
# vector memory, no tool-call replay across requests. This mirrors the
# design-phase decision to keep memory structured and explainable: the
# effects of a tool call (an order created, a cart updated) are already
# durable in the database; what gets replayed here is just the conversation
# text so the model has continuity, not the mechanics of how it got there.
HISTORY_MESSAGE_LIMIT = 20

FOLLOW_UP_CHIP_LIMIT = 2

# Matches the "[[FOLLOWUPS: a | b]]" marker system_prompt.py instructs the
# model to end its reply with. Parsed out of the SAME reply rather than a
# second Gemini call — the free tier's 20 requests/day makes a follow-up
# call per turn too expensive. re.DOTALL so a suggestion can't accidentally
# break the match if the model wraps text oddly.
_FOLLOWUP_MARKER_RE = re.compile(r"\n*\[\[FOLLOWUPS:(.*?)\]\]\s*$", re.IGNORECASE | re.DOTALL)


def _extract_follow_ups(reply_text: str) -> tuple[str, list[str]]:
    """
    If the model skips the marker or malforms it, this just yields zero
    chips for that turn — never an error. The visible reply is returned
    unchanged in that case (nothing to strip).
    """
    match = _FOLLOWUP_MARKER_RE.search(reply_text)
    if not match:
        return reply_text, []
    cleaned = reply_text[: match.start()].rstrip()
    follow_ups = [item.strip() for item in match.group(1).split("|") if item.strip()]
    return cleaned, follow_ups[:FOLLOW_UP_CHIP_LIMIT]


class ConversationNotFoundError(Exception):
    pass


async def _get_or_create_conversation(
    db: AsyncSession, user_id: uuid.UUID, conversation_id: uuid.UUID | None
) -> Conversation:
    if conversation_id is None:
        conversation = Conversation(user_id=user_id, channel="chat")
        db.add(conversation)
        await db.commit()
        await db.refresh(conversation)
        return conversation

    result = await db.execute(
        select(Conversation).where(Conversation.id == conversation_id, Conversation.user_id == user_id)
    )
    conversation = result.scalar_one_or_none()
    if conversation is None:
        raise ConversationNotFoundError()
    return conversation


def _format_qty(value) -> str:
    return f"{float(value):g}"


async def _build_cart_grounding_note(db: AsyncSession, user_id: uuid.UUID) -> str:
    """
    Verified, freshly-queried cart state, injected into every turn — not
    trusted from conversation history. This exists specifically because
    text-only history means the model otherwise has to trust its own past
    paraphrase of what's in the cart, which is exactly what caused it to
    defensively re-add an item on a later "proceed to checkout" turn
    instead of trusting it was already there.
    """
    rows = await cart_service.get_cart(db, user_id)
    if not rows:
        return "Current cart: empty."
    parts = [f"{_format_qty(item.quantity)} {product.unit} {product.name}" for item, product in rows]
    subtotal = sum(float(item.quantity) * float(product.price) for item, product in rows)
    return f"Current cart: {', '.join(parts)} (subtotal {settings.CURRENCY_LABEL} {subtotal:.2f})."


async def send_message(
    db: AsyncSession, user: User, conversation_id: uuid.UUID | None, message: str
) -> tuple[uuid.UUID, str, list[str]]:
    conversation = await _get_or_create_conversation(db, user.id, conversation_id)

    grounding_note = await _build_cart_grounding_note(db, user.id)
    grounded_message = (
        f"[Automated context, not from the customer — {grounding_note}]\n\n{message}"
    )

    # History is loaded internally by run_conversation_turn now (Deepgram's
    # own message format, not google.genai's types.Content) — see
    # deepgram_chat_client.py.
    reply_text = await run_conversation_turn(db, user, conversation.id, grounded_message)
    reply_text, follow_ups = _extract_follow_ups(reply_text)
    reply_text = filter_reply(reply_text)

    # Persist the ORIGINAL message, not the grounded wrapper — a fresh
    # grounding note gets built every turn, so storing it would just
    # accumulate stale duplicates in history for no benefit. follow_ups is
    # UI-only (chips) and, like the greeting's, deliberately not persisted.
    db.add(Message(conversation_id=conversation.id, role="user", content=message))
    db.add(Message(conversation_id=conversation.id, role="assistant", content=reply_text))
    await db.commit()

    return conversation.id, reply_text, follow_ups
