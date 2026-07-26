import asyncio
import base64
import json
import logging
import uuid

from fastapi import WebSocket, WebSocketDisconnect
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.llm import knowledge_base, tool_executor
from app.llm.call_system_prompt import CALL_SYSTEM_PROMPT
from app.llm.call_tool_schemas import CALL_TOOL_FUNCTIONS
from app.models.conversation import Conversation, Message
from app.models.user import User
from app.services import auth_service, voice_service
from deepgram.agent.v1.types import (
    AgentV1ConversationText,
    AgentV1Error,
    AgentV1FunctionCallRequest,
    AgentV1InjectAgentMessage,
    AgentV1SendFunctionCallResponse,
    AgentV1Settings,
    AgentV1SettingsAgent,
    AgentV1SettingsAudio,
)

logger = logging.getLogger(__name__)

# A tool call (DB query + the round trip through Deepgram's pipeline) can
# take a few real seconds — confirmed directly on a live call. Without
# this, the caller hears dead air the whole time, which reads as "the call
# dropped" over the phone (no visual "Thinking…" indicator exists here the
# way the browser voice UI has). Sent via InjectAgentMessage right when a
# FunctionCallRequest arrives, behavior="queue" so it never interrupts
# speech already in flight, just plays next.
_FILLER_PHRASE = "One moment, let me check that for you."

GREETING_TEXT = (
    "Thanks for calling Local Butcher! I can answer general questions right away — for your cart, "
    "orders, or account, just tell me your registered mobile number first. How can I help?"
)

# Flux's English model — see backend CLAUDE.md's "Voice layer" for why the
# call channel stays English-only (Aura, the TTS side below, has no Hindi
# voice, so a Hindi-capable STT model would only be understood one-way).
_LISTEN_MODEL = "flux-general-en"

# Exotel's documented constraint on inbound media chunk sizes (16-bit mono
# PCM) — see developer.exotel.com/docs/agentstream/developer-guide. Deepgram
# doesn't know or care about this; see _flush_aligned_audio below.
_EXOTEL_CHUNK_ALIGNMENT = 320


def _build_settings() -> AgentV1Settings:
    # `agent` is constructed as a real AgentV1SettingsAgent instance, not a
    # plain dict, deliberately — AgentV1Settings.agent is typed as
    # Union[AgentV1SettingsAgent, AgentV1SettingsAgentContext, str], and
    # AgentV1SettingsAgent subclasses AgentV1SettingsAgentContext with an
    # identical field set (no discriminating literal between them), so a
    # dict here would rely on pydantic's union-resolution ordering picking
    # the right one. Passing an already-built instance sidesteps that
    # ambiguity entirely.
    sample_rate = settings.CALL_AUDIO_SAMPLE_RATE
    audio = AgentV1SettingsAudio(
        input={"encoding": "linear16", "sample_rate": sample_rate},
        output={"encoding": "linear16", "sample_rate": sample_rate, "container": "none"},
    )
    agent = AgentV1SettingsAgent(
        listen={"provider": {"type": "deepgram", "version": "v2", "model": _LISTEN_MODEL}},
        think={
            "provider": {"type": "google", "model": settings.VOICE_AGENT_GEMINI_MODEL},
            "prompt": CALL_SYSTEM_PROMPT,
            "functions": CALL_TOOL_FUNCTIONS,
        },
        speak={"provider": {"type": "deepgram", "model": settings.VOICE_AGENT_TTS_VOICE}},
        greeting=GREETING_TEXT,
    )
    return AgentV1Settings(audio=audio, agent=agent)


class _CallState:
    """
    Mutable state shared between the two relay tasks in bridge_call() below.
    Nothing here is ever trusted from the model or from Exotel beyond the
    stream_sid needed to address audio back to the right call — verified_user
    is only ever set from a real auth_service.get_user_by_phone() lookup,
    the same rule tool_executor.execute_tool already enforces for chat/voice.
    """

    def __init__(self) -> None:
        self.stream_sid: str | None = None
        self.verified_user: User | None = None
        self.conversation_id: uuid.UUID | None = None
        # See _flush_aligned_audio below — Deepgram's TTS output arrives in
        # arbitrarily-sized chunks that need re-aligning before Exotel will
        # play them back cleanly.
        self.output_buffer = bytearray()


async def _get_or_create_conversation(db: AsyncSession, state: _CallState) -> uuid.UUID:
    if state.conversation_id is None:
        conversation = Conversation(user_id=state.verified_user.id, channel="call")
        db.add(conversation)
        await db.commit()
        await db.refresh(conversation)
        state.conversation_id = conversation.id
    return state.conversation_id


async def _persist_turn(db: AsyncSession, state: _CallState, role: str, content: str) -> None:
    # Only logged from the moment of verification onward — turns before that
    # have no user_id to attach to (Conversation.user_id is NOT NULL, same as
    # chat/voice) and are deliberately not retroactively backfilled once
    # verified. A known gap, not worth the extra state to close for a first
    # cut — see backend CLAUDE.md's "Known placeholders" section for the
    # project's existing convention on this kind of tradeoff.
    if state.verified_user is None:
        return
    conversation_id = await _get_or_create_conversation(db, state)
    db.add(Message(conversation_id=conversation_id, role=role, content=content))
    await db.commit()


async def _dispatch_function(db: AsyncSession, state: _CallState, name: str, args: dict) -> dict:
    if name == "verify_phone_number":
        phone = str(args.get("phone_number") or "")
        user = await auth_service.get_user_by_phone(db, phone) if phone else None
        if user is None:
            return {"verified": False}
        state.verified_user = user
        return {"verified": True, "name": user.name}

    if name == "search_knowledge_base":
        query = str(args.get("query") or "")
        return {"results": knowledge_base.search(query)}

    if state.verified_user is None:
        return {
            "error": "not_verified",
            "message": "This caller hasn't verified their phone number yet — ask for it and call verify_phone_number first.",
        }

    return await tool_executor.execute_tool(db, state.verified_user, name, args)


async def _relay_exotel_to_deepgram(exotel_ws: WebSocket, dg_socket, state: _CallState) -> None:
    while True:
        raw = await exotel_ws.receive_text()
        message = json.loads(raw)
        event = message.get("event")

        if event == "start":
            state.stream_sid = message["stream_sid"]
            # Logged deliberately — if Exotel's actual media_format doesn't
            # match CALL_AUDIO_SAMPLE_RATE (what we told Deepgram to input/
            # output at), audio will play back pitch-shifted/distorted. This
            # is the fastest way to confirm or rule that out from a real call.
            logger.info(
                "call started: from=%s media_format=%s",
                message.get("start", {}).get("from"),
                message.get("start", {}).get("media_format"),
            )
        elif event == "media":
            payload = message["media"]["payload"]
            await dg_socket.send_media(base64.b64decode(payload))
        elif event == "stop":
            return
        # "connected" and anything else: nothing to do.


async def _flush_aligned_audio(exotel_ws: WebSocket, state: _CallState, *, final: bool = False) -> None:
    """
    Deepgram's TTS output arrives as arbitrarily-sized byte messages with no
    relationship to Exotel's chunk-size requirement (see
    _EXOTEL_CHUNK_ALIGNMENT above) — sending each one straight through as
    its own "media" frame caused audible glitching/distortion on a real
    test call, since most of them land on the wrong byte boundary. This
    buffers in state.output_buffer and only ever sends whole multiples of
    320 bytes, carrying any remainder forward to the next message.

    On `final` (the call ending), a trailing partial remainder is
    zero-padded (silence) up to the next multiple rather than dropped, so
    the last fraction of a second of speech is never silently lost.
    """
    buffer = state.output_buffer
    if final and len(buffer) % _EXOTEL_CHUNK_ALIGNMENT:
        buffer.extend(b"\x00" * (_EXOTEL_CHUNK_ALIGNMENT - len(buffer) % _EXOTEL_CHUNK_ALIGNMENT))

    aligned_len = len(buffer) - (len(buffer) % _EXOTEL_CHUNK_ALIGNMENT)
    if aligned_len == 0 or state.stream_sid is None:
        return

    chunk = bytes(buffer[:aligned_len])
    state.output_buffer = buffer[aligned_len:]
    await exotel_ws.send_text(
        json.dumps(
            {
                "event": "media",
                "stream_sid": state.stream_sid,
                "media": {"payload": base64.b64encode(chunk).decode("ascii")},
            }
        )
    )


async def _relay_deepgram_to_exotel(
    db: AsyncSession, exotel_ws: WebSocket, dg_socket, state: _CallState
) -> None:
    async for msg in dg_socket:
        if isinstance(msg, bytes):
            # Synthesized speech from the agent — relayed back to Exotel with
            # identical JSON/base64 framing to what it sent us (see
            # developer.exotel.com/docs/agentstream/developer-guide), after
            # re-aligning to Exotel's required chunk size (_flush_aligned_audio).
            state.output_buffer.extend(msg)
            await _flush_aligned_audio(exotel_ws, state)
            continue

        if isinstance(msg, AgentV1FunctionCallRequest):
            # Said once per batch, not per function — a tool round trip
            # (DB query + Deepgram's own pipeline) takes a few real
            # seconds, confirmed on a live call; without this the caller
            # hears dead air the whole time, which reads as a dropped
            # call over the phone (no visual "Thinking…" indicator exists
            # here the way the browser voice UI has).
            await dg_socket.send_inject_agent_message(
                AgentV1InjectAgentMessage(message=_FILLER_PHRASE, behavior="queue")
            )
            for call in msg.functions:
                try:
                    args = json.loads(call.arguments) if call.arguments else {}
                except json.JSONDecodeError:
                    args = {}
                # _dispatch_function never raises: verify_phone_number and
                # search_knowledge_base are handled directly above, and
                # tool_executor.execute_tool already catches its own
                # ToolExecutionError and returns {"error": ...} instead of
                # propagating it (see tool_executor.py).
                result = await _dispatch_function(db, state, call.name, args)
                await dg_socket.send_function_call_response(
                    AgentV1SendFunctionCallResponse(id=call.id, name=call.name, content=json.dumps(result))
                )
                # Guaranteed, not left to the model's own "think" step —
                # reported separately as sometimes going fully silent
                # right after verification instead of confirming it.
                # This ensures the caller always hears SOMETHING at this
                # specific high-value moment, regardless of what the
                # model decides to do next (e.g. chaining straight into
                # another tool call with no spoken acknowledgment first).
                if call.name == "verify_phone_number" and result.get("verified"):
                    await dg_socket.send_inject_agent_message(
                        AgentV1InjectAgentMessage(
                            message=f"Thanks, {result.get('name', 'there')}, you're verified!",
                            behavior="queue",
                        )
                    )
            continue

        if isinstance(msg, AgentV1ConversationText):
            await _persist_turn(db, state, msg.role, msg.content)
            continue

        if isinstance(msg, AgentV1Error):
            logger.error("Deepgram Voice Agent error on call: %s (%s)", msg.description, msg.code)
            continue

        # Welcome, SettingsApplied, AgentThinking/StartedSpeaking/AudioDone,
        # UserStartedSpeaking, LatencyReport, Warning, History, *Updated —
        # informational only, nothing for the bridge to act on.


async def bridge_call(exotel_ws: WebSocket, db: AsyncSession) -> None:
    """
    The whole phone call, start to end: bridges raw audio between Exotel's
    WebSocket and Deepgram's Voice Agent WebSocket (which itself runs STT,
    the Gemini "think" loop, and TTS — see app/llm/call_system_prompt.py and
    call_tool_schemas.py for what it's configured with), and executes every
    function call the agent makes against the same app.llm.tool_executor
    text chat and browser voice already use, once — and only once — the
    caller has verified a phone number via auth_service.get_user_by_phone.
    """
    state = _CallState()
    client = voice_service.get_client()

    async with client.agent.v1.connect() as dg_socket:
        await dg_socket.send_settings(_build_settings())

        try:
            exotel_task = asyncio.create_task(_relay_exotel_to_deepgram(exotel_ws, dg_socket, state))
            deepgram_task = asyncio.create_task(_relay_deepgram_to_exotel(db, exotel_ws, dg_socket, state))
            done, pending = await asyncio.wait(
                {exotel_task, deepgram_task}, return_when=asyncio.FIRST_COMPLETED
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
        finally:
            # Best-effort — the Exotel socket may already be gone by now
            # (that's often exactly why we got here), in which case there's
            # nothing left to flush audio to anyway.
            try:
                await _flush_aligned_audio(exotel_ws, state, final=True)
            except Exception:
                pass
