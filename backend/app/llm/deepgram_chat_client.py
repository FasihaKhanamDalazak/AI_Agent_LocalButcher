import asyncio
import json
import logging
import re
import uuid

from deepgram.agent.v1.types import (
    AgentV1AgentAudioDone,
    AgentV1ConversationText,
    AgentV1Error,
    AgentV1FunctionCallRequest,
    AgentV1InjectUserMessage,
    AgentV1SendFunctionCallResponse,
    AgentV1Settings,
    AgentV1SettingsAgent,
    AgentV1SettingsAudio,
)
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.llm.gemini_client import AssistantUnavailableError  # re-used as-is, same meaning here
from app.llm.system_prompt import SYSTEM_PROMPT
from app.llm.tool_executor import execute_tool
from app.llm.tool_schemas import PLAIN_JSON_TOOL_DECLARATIONS
from app.models.conversation import Message
from app.models.user import User
from app.services.deepgram_client import get_client

logger = logging.getLogger(__name__)

# Text chat's own GEMINI_API_KEY quota is the free tier's 20 requests/day
# (see gemini_client.AssistantUnavailableError) — this routes text chat
# through Deepgram's managed Google integration instead (no API key of
# ours involved at all, per Deepgram's docs), the same infra already
# proven out for browser voice and phone calls, specifically to get text
# chat off that quota. No real audio in or out here — InjectUserMessage
# skips straight to the "think" step, and any audio Deepgram still
# generates (it's fundamentally an audio product) is received and
# discarded, never sent anywhere.
HISTORY_MESSAGE_LIMIT = 20

# A fixed, minimal audio config is required by AgentV1Settings's schema
# even though no audio actually flows in either direction on this channel
# — reuses browser voice's rate purely because it's a value already proven
# to build valid settings, not because it means anything here.
_UNUSED_SAMPLE_RATE = 16000

# Discovered directly in testing, not documented: Deepgram's Voice Agent
# expects to receive SOME audio periodically even when the conversation is
# driven entirely through InjectUserMessage — a simple no-tool-call reply
# completed fine without ever sending audio, but a reply requiring a
# function-call round trip (slower — think, call out, wait, think again)
# hit CLIENT_MESSAGE_TIMEOUT before finishing. _send_keep_alive_silence
# below runs concurrently with the main event loop for exactly this reason.
_KEEP_ALIVE_SILENCE_CHUNK = b"\x00\x00" * 1600  # 100ms of silence at 16kHz/16-bit mono
_KEEP_ALIVE_INTERVAL_SECONDS = 0.5


# Matches a fragment that opens with a Markdown list marker ("- ", "* ",
# "1. ") — Deepgram's Voice Agent splits one reply into several
# ConversationText fragments at sentence/utterance boundaries (proven
# already for the voice channels — see backend CLAUDE.md's "Voice layer"
# — same product, same behavior here). That's harmless when the text is
# only ever spoken aloud, but text chat renders the reassembled string as
# real Markdown: a plain " ".join collapsed every newline the model wrote
# between list bullets into a single space, turning a real multi-line
# list into one run-on "* item * item * item" paragraph that no longer
# parses as a list. Re-inserting a newline specifically before a fragment
# that starts a new list item (and only there — normal sentences still
# join with a space, so ordinary prose doesn't get a stray line break per
# sentence) restores the structure the model actually wrote.
_LIST_ITEM_START_RE = re.compile(r"^(?:[-*]\s|\d+\.\s)")


def _join_reply_fragments(parts: list[str]) -> str:
    result = ""
    for part in parts:
        if not result:
            result = part
        elif _LIST_ITEM_START_RE.match(part.lstrip()):
            result += "\n" + part
        else:
            result += " " + part
    return result


async def _load_history(db: AsyncSession, conversation_id: uuid.UUID) -> list[dict]:
    result = await db.execute(
        select(Message)
        .where(Message.conversation_id == conversation_id)
        .order_by(Message.created_at.desc())
        .limit(HISTORY_MESSAGE_LIMIT)
    )
    rows = list(reversed(result.scalars().all()))
    return [{"type": "History", "role": m.role, "content": m.content} for m in rows]


def _build_settings(history: list[dict]) -> AgentV1Settings:
    audio = AgentV1SettingsAudio(
        input={"encoding": "linear16", "sample_rate": _UNUSED_SAMPLE_RATE},
        output={"encoding": "linear16", "sample_rate": _UNUSED_SAMPLE_RATE, "container": "none"},
    )
    agent_kwargs: dict = {
        "think": {
            "provider": {"type": "google", "model": settings.VOICE_AGENT_GEMINI_MODEL},
            # The real text-chat prompt, unchanged — multi-language and the
            # [[FOLLOWUPS: ...]] marker both still make sense here, unlike
            # the voice channels, since nothing about this path ever
            # touches spoken audio the customer actually hears.
            "prompt": SYSTEM_PROMPT,
            "functions": PLAIN_JSON_TOOL_DECLARATIONS,
        },
    }
    if history:
        agent_kwargs["context"] = {"messages": history}
    agent = AgentV1SettingsAgent(**agent_kwargs)
    return AgentV1Settings(audio=audio, agent=agent)


async def _send_keep_alive_silence(dg_socket) -> None:
    while True:
        await dg_socket.send_media(_KEEP_ALIVE_SILENCE_CHUNK)
        await asyncio.sleep(_KEEP_ALIVE_INTERVAL_SECONDS)


async def run_conversation_turn(
    db: AsyncSession, user: User, conversation_id: uuid.UUID, user_message: str
) -> str:
    """
    Deepgram-backed equivalent of gemini_client.run_conversation_turn —
    same contract (return the final reply text, execute any tool calls
    against `user` via the shared tool_executor, raise
    AssistantUnavailableError on failure) so chat_service.send_message
    barely changes to call this instead.
    """
    history = await _load_history(db, conversation_id)
    client = get_client()

    try:
        async with client.agent.v1.connect() as dg_socket:
            await dg_socket.send_settings(_build_settings(history))
            await dg_socket.send_inject_user_message(AgentV1InjectUserMessage(content=user_message))

            keep_alive_task = asyncio.create_task(_send_keep_alive_silence(dg_socket))
            try:
                reply_parts: list[str] = []
                async for msg in dg_socket:
                    if isinstance(msg, bytes):
                        continue  # audio generated but never used on this text-only channel

                    if isinstance(msg, AgentV1FunctionCallRequest):
                        for call in msg.functions:
                            try:
                                args = json.loads(call.arguments) if call.arguments else {}
                            except json.JSONDecodeError:
                                args = {}
                            result = await execute_tool(db, user, call.name, args)
                            await dg_socket.send_function_call_response(
                                AgentV1SendFunctionCallResponse(id=call.id, name=call.name, content=json.dumps(result))
                            )
                        continue

                    if isinstance(msg, AgentV1ConversationText) and msg.role == "assistant":
                        # Same multi-fragment behavior discovered building
                        # the voice channels — accumulate, don't overwrite.
                        reply_parts.append(msg.content)
                        continue

                    if isinstance(msg, AgentV1AgentAudioDone):
                        break  # the reply (and its unused audio) is complete

                    if isinstance(msg, AgentV1Error):
                        logger.error("Deepgram Voice Agent error on text chat: %s (%s)", msg.description, msg.code)
                        raise AssistantUnavailableError()

                return _join_reply_fragments(reply_parts)
            finally:
                keep_alive_task.cancel()
                try:
                    await keep_alive_task
                except asyncio.CancelledError:
                    pass
    except AssistantUnavailableError:
        raise
    except Exception as e:
        logger.exception("Deepgram-backed text chat turn failed")
        raise AssistantUnavailableError() from e
