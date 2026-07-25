from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.db.session import get_db
from app.models.user import User
from app.schemas.chat import ChatRequest, ChatResponse, GreetingResponse
from app.services import chat_service, greeting_service

router = APIRouter()


@router.get("/greeting", response_model=GreetingResponse)
async def get_greeting(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Call this the instant the chat widget opens, before the customer has
    typed anything — it starts a new conversation and returns the
    proactive "Welcome back" greeting. Use the returned conversation_id
    for every subsequent POST /chat call in that session.
    """
    conversation_id, greeting = await greeting_service.start_conversation_with_greeting(db, current_user)
    return GreetingResponse(conversation_id=conversation_id, greeting=greeting)


@router.post("", response_model=ChatResponse)
async def chat(
    data: ChatRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    try:
        conversation_id, reply = await chat_service.send_message(
            db, current_user, data.conversation_id, data.message
        )
    except chat_service.ConversationNotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Conversation not found")
    return ChatResponse(conversation_id=conversation_id, reply=reply)
