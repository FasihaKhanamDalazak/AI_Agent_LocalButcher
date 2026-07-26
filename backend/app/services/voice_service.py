import asyncio
import base64
import io
import json
import logging
import uuid
import wave

from deepgram import AsyncDeepgramClient
from deepgram.agent.v1.types import (
    AgentV1AgentAudioDone,
    AgentV1ConversationText,
    AgentV1Error,
    AgentV1FunctionCallRequest,
    AgentV1SendFunctionCallResponse,
    AgentV1Settings,
    AgentV1SettingsAgent,
    AgentV1SettingsAudio,
)
from fastapi import WebSocket, WebSocketDisconnect
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.llm import tool_executor
from app.llm.browser_voice_system_prompt import BROWSER_VOICE_SYSTEM_PROMPT
from app.llm.tool_schemas import PLAIN_JSON_TOOL_DECLARATIONS
from app.models.conversation import Message
from app.models.user import User
from app.services import greeting_service
from app.services.chat_service import HISTORY_MESSAGE_LIMIT

logger = logging.getLogger(__name__)

_client: AsyncDeepgramClient | None = None


def get_client() -> AsyncDeepgramClient:
    # Shared with app.services.telephony_service (the phone-call agent) —
    # one lazily-created client per process, same API key.
    global _client
    if _client is None:
        _client = AsyncDeepgramClient(api_key=settings.DEEPGRAM_API_KEY)
    return _client


# Matches useVoiceChat.js's TARGET_SAMPLE_RATE exactly — the browser
# captures and expects audio at this rate with no negotiation, unlike the
# phone channel where CALL_AUDIO_SAMPLE_RATE had to be discovered from a
# live call. Changing this needs a matching frontend change, not just a
# config value here.
_SAMPLE_RATE = 16000
# English-only — see browser_voice_system_prompt.py's "Language" section
# for why (Aura has no Hindi/Telugu voice, same constraint as phone calls).
_LISTEN_MODEL = "flux-general-en"


def _wrap_pcm16_as_wav(pcm_bytes: bytes) -> bytes:
    """
    Deepgram's Voice Agent streams raw PCM audio in arbitrarily-sized
    chunks (container="none" in _build_settings below) — there's no single
    "one WAV file per reply" concept at the protocol level, unlike the old
    one-shot speak.v1.audio.generate REST call this replaced. Buffered
    bytes for one agent turn (see _relay_deepgram_to_browser) are wrapped
    into a real WAV file here so the existing frontend contract
    (useVoiceChat.js's `new Audio("data:audio/wav;base64,...")`) needs no
    changes at all.
    """
    buffer = io.BytesIO()
    with wave.open(buffer, "wb") as wav_file:
        wav_file.setnchannels(1)
        wav_file.setsampwidth(2)  # 16-bit
        wav_file.setframerate(_SAMPLE_RATE)
        wav_file.writeframes(pcm_bytes)
    return buffer.getvalue()


async def _load_agent_history(db: AsyncSession, conversation_id: uuid.UUID) -> list[dict]:
    """
    Only called when CONTINUING an existing conversation (conversation_id
    already provided — e.g. the customer typed a few messages, then
    switched to voice, same conversationId shared by ChatPage.jsx's
    useChat/useVoiceChat). Without this, the Voice Agent would start with
    no memory of anything said before it, even though the conversation
    clearly continues on screen. Same HISTORY_MESSAGE_LIMIT and shape as
    chat_service._load_history, just Deepgram's plain-dict history-message
    format instead of google.genai's typed Content objects.
    """
    result = await db.execute(
        select(Message)
        .where(Message.conversation_id == conversation_id)
        .order_by(Message.created_at.desc())
        .limit(HISTORY_MESSAGE_LIMIT)
    )
    rows = list(reversed(result.scalars().all()))
    return [{"type": "History", "role": m.role, "content": m.content} for m in rows]


def _build_settings(*, greeting_text: str | None, history: list[dict]) -> AgentV1Settings:
    audio = AgentV1SettingsAudio(
        input={"encoding": "linear16", "sample_rate": _SAMPLE_RATE},
        output={"encoding": "linear16", "sample_rate": _SAMPLE_RATE, "container": "none"},
    )
    agent_kwargs: dict = {
        "listen": {"provider": {"type": "deepgram", "version": "v2", "model": _LISTEN_MODEL}},
        "think": {
            "provider": {"type": "google", "model": settings.VOICE_AGENT_GEMINI_MODEL},
            "prompt": BROWSER_VOICE_SYSTEM_PROMPT,
            # No verify_phone_number here (unlike call_tool_schemas.CALL_TOOL_FUNCTIONS)
            # — the browser customer is already JWT-authenticated, so every
            # tool is available immediately.
            "functions": PLAIN_JSON_TOOL_DECLARATIONS,
        },
        "speak": {"provider": {"type": "deepgram", "model": settings.VOICE_AGENT_TTS_VOICE}},
    }
    if greeting_text:
        agent_kwargs["greeting"] = greeting_text
    if history:
        agent_kwargs["context"] = {"messages": history}
    agent = AgentV1SettingsAgent(**agent_kwargs)
    return AgentV1Settings(audio=audio, agent=agent)


class _BrowserVoiceState:
    def __init__(self, conversation_id: uuid.UUID, *, has_pending_greeting: bool) -> None:
        self.conversation_id = conversation_id
        self.output_buffer = bytearray()
        # Paired with the next AgentAudioDone to build one assistant_reply
        # message (text + audio together, matching the old one-shot
        # contract) — see _relay_deepgram_to_browser. Deepgram can emit
        # MULTIPLE ConversationText(assistant) fragments for what's one
        # continuous spoken turn (observed directly in testing: "Your cart
        # is currently empty." then "Is there anything I can help you add?"
        # as two separate events, both audible back-to-back in a single
        # AgentAudioDone-bounded audio clip) — accumulated here rather than
        # overwritten, so the displayed text always matches the full audio.
        self.pending_assistant_text: str | None = None
        # greeting_service.start_conversation_with_greeting already
        # persists the greeting as the conversation's first Message row
        # itself (deliberately — so the model has it as context on the
        # customer's real first turn, see that function's docstring).
        # Deepgram ALSO emits a real ConversationText(assistant) event for
        # the configured static greeting (confirmed directly in testing —
        # earlier code wrongly assumed it wouldn't, and separately preset
        # pending_assistant_text with the greeting text, which then got the
        # real event's text concatenated onto it, duplicating the whole
        # greeting in what the customer saw and heard). Without this flag,
        # the bridge would persist the greeting a SECOND time once that
        # event's audio flushes. The greeting is always the very first
        # non-empty AgentAudioDone flush in a new conversation, so tracking
        # that — not "did a ConversationText event fire" — is what
        # correctly identifies it to skip the duplicate persist.
        self.has_pending_greeting = has_pending_greeting


async def _persist_turn(db: AsyncSession, state: _BrowserVoiceState, role: str, content: str) -> None:
    db.add(Message(conversation_id=state.conversation_id, role=role, content=content))
    await db.commit()


async def _send_json(websocket: WebSocket, payload: dict) -> None:
    await websocket.send_text(json.dumps(payload))


async def _relay_browser_to_deepgram(websocket: WebSocket, dg_socket) -> None:
    while True:
        chunk = await websocket.receive_bytes()
        await dg_socket.send_media(chunk)


async def _relay_deepgram_to_browser(
    db: AsyncSession, websocket: WebSocket, dg_socket, user: User, state: _BrowserVoiceState
) -> None:
    async for msg in dg_socket:
        if isinstance(msg, bytes):
            state.output_buffer.extend(msg)
            continue

        if isinstance(msg, AgentV1FunctionCallRequest):
            for call in msg.functions:
                try:
                    args = json.loads(call.arguments) if call.arguments else {}
                except json.JSONDecodeError:
                    args = {}
                # Straight to tool_executor, no verification gate and no
                # special-cased tools (contrast telephony_service.
                # _dispatch_function) — `user` is already a real,
                # JWT-authenticated User, never anything model-supplied.
                result = await tool_executor.execute_tool(db, user, call.name, args)
                await dg_socket.send_function_call_response(
                    AgentV1SendFunctionCallResponse(id=call.id, name=call.name, content=json.dumps(result))
                )
            continue

        if isinstance(msg, AgentV1ConversationText):
            if msg.role == "user":
                await _persist_turn(db, state, "user", msg.content)
                await _send_json(websocket, {"type": "final_transcript", "text": msg.content})
            else:
                state.pending_assistant_text = (
                    f"{state.pending_assistant_text} {msg.content}" if state.pending_assistant_text else msg.content
                )
            continue

        if isinstance(msg, AgentV1AgentAudioDone):
            if state.output_buffer:
                wav_bytes = _wrap_pcm16_as_wav(bytes(state.output_buffer))
                state.output_buffer = bytearray()
                reply_text = state.pending_assistant_text or ""
                # Persisted here, once per logical reply (not per fragment,
                # matching chat_service's one-row-per-turn convention) —
                # except the very first flush of a new conversation, which
                # is always the greeting: greeting_service already
                # persisted it once, so this skip prevents a duplicate row
                # (see _BrowserVoiceState.has_pending_greeting).
                if state.has_pending_greeting:
                    state.has_pending_greeting = False
                else:
                    await _persist_turn(db, state, "assistant", reply_text)
                await _send_json(
                    websocket,
                    {
                        "type": "assistant_reply",
                        "text": reply_text,
                        "conversation_id": str(state.conversation_id),
                        "audio_base64": base64.b64encode(wav_bytes).decode("ascii"),
                    },
                )
                state.pending_assistant_text = None
            continue

        if isinstance(msg, AgentV1Error):
            logger.error("Deepgram Voice Agent error on browser voice: %s (%s)", msg.description, msg.code)
            continue

        # Welcome, SettingsApplied, AgentThinking/StartedSpeaking,
        # UserStartedSpeaking, LatencyReport, Warning, History, *Updated —
        # informational only, nothing for the bridge to act on. Notably no
        # interim/partial transcript events exist in this protocol (unlike
        # the old raw Listen API's interim_results) — the frontend's
        # "Listening…" placeholder covers the gap with no code change
        # needed, but live word-by-word captions while speaking are gone.


async def bridge_browser_voice(
    websocket: WebSocket, db: AsyncSession, user: User, conversation_id: uuid.UUID | None
) -> None:
    """
    Real-time browser voice chat over WS /api/v1/chat/voice/stream —
    bridges mic audio to Deepgram's Voice Agent API (STT+Gemini+TTS
    together, the same product the phone-call agent uses — see backend
    CLAUDE.md's "Voice layer" for why this replaced the earlier separate
    STT -> chat_service -> TTS pipeline: real Gemini quota pressure and
    response latency on direct calls). Unlike the phone channel, the
    browser customer is ALREADY authenticated (JWT) before this is ever
    called — every tool is available immediately, no verification gate —
    and prior conversation history is preloaded so switching from typing
    to talking mid-conversation isn't starting from a blank slate.
    """
    greeting_text: str | None = None
    if conversation_id is None:
        conversation_id, greeting_text, _follow_ups = await greeting_service.start_conversation_with_greeting(
            db, user
        )

    history = [] if greeting_text else await _load_agent_history(db, conversation_id)

    state = _BrowserVoiceState(conversation_id, has_pending_greeting=greeting_text is not None)

    client = get_client()
    async with client.agent.v1.connect() as dg_socket:
        await dg_socket.send_settings(_build_settings(greeting_text=greeting_text, history=history))

        try:
            browser_task = asyncio.create_task(_relay_browser_to_deepgram(websocket, dg_socket))
            deepgram_task = asyncio.create_task(_relay_deepgram_to_browser(db, websocket, dg_socket, user, state))
            done, pending = await asyncio.wait(
                {browser_task, deepgram_task}, return_when=asyncio.FIRST_COMPLETED
            )
            for task in pending:
                task.cancel()
            if pending:
                await asyncio.gather(*pending, return_exceptions=True)
            for task in done:
                exc = task.exception()
                if exc is not None and not isinstance(exc, WebSocketDisconnect):
                    raise exc
        except WebSocketDisconnect:
            pass
