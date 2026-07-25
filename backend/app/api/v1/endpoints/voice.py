import asyncio
import base64
import json
import uuid

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app.api.deps import get_user_from_token
from app.db.session import AsyncSessionLocal
from app.services import chat_service, greeting_service, voice_service

router = APIRouter()


async def _send_json(websocket: WebSocket, payload: dict) -> None:
    await websocket.send_text(json.dumps(payload))


async def _speak(websocket: WebSocket, conversation_id: uuid.UUID, text: str) -> None:
    audio = await voice_service.text_to_speech(text)
    await _send_json(
        websocket,
        {
            "type": "assistant_reply",
            "text": text,
            "conversation_id": str(conversation_id),
            "audio_base64": base64.b64encode(audio).decode("ascii"),
        },
    )


@router.websocket("/stream")
async def voice_stream(websocket: WebSocket):
    """
    Real-time voice conversation with the same Local Butcher agent used by
    the text chat — no file upload, no request/response turns. The client
    streams raw audio bytes (linear16 PCM, 16kHz, mono — see
    voice_service.open_transcription_stream) continuously over this socket;
    Deepgram transcribes it live and tells us when the customer has
    actually finished a sentence (speech_final), at which point the
    recognized text is run through chat_service.send_message exactly as a
    normal text message would be — the chat/tool/security logic is
    entirely unchanged. The reply comes back as text plus spoken audio,
    both over this same socket, so a future UI can display and play them
    together.

    Auth: browsers can't set an Authorization header on a WebSocket
    handshake, so the JWT is passed as a query param instead
    (?token=...) and resolved through the same get_user_from_token used
    by the header-based REST auth — same security guarantee, different
    transport.
    """
    token = websocket.query_params.get("token")

    async with AsyncSessionLocal() as db:
        user = await get_user_from_token(token, db) if token else None
        if user is None:
            await websocket.close(code=4401, reason="invalid or missing token")
            return

        await websocket.accept()

        conversation_id_raw = websocket.query_params.get("conversation_id")
        conversation_id = uuid.UUID(conversation_id_raw) if conversation_id_raw else None

        try:
            if conversation_id is None:
                conversation_id, greeting_text = await greeting_service.start_conversation_with_greeting(db, user)
                await _speak(websocket, conversation_id, greeting_text)

            async with voice_service.open_transcription_stream() as dg_socket:

                async def forward_audio():
                    while True:
                        chunk = await websocket.receive_bytes()
                        await dg_socket.send_media(chunk)

                async def handle_transcripts():
                    nonlocal conversation_id
                    buffer_parts: list[str] = []
                    async for msg in dg_socket:
                        if getattr(msg, "type", None) != "Results":
                            continue
                        alt = msg.channel.alternatives[0]
                        transcript = alt.transcript
                        if not transcript:
                            continue

                        if msg.is_final:
                            buffer_parts.append(transcript)
                            await _send_json(websocket, {"type": "final_transcript", "text": transcript})
                        else:
                            await _send_json(websocket, {"type": "interim_transcript", "text": transcript})

                        if msg.speech_final and buffer_parts:
                            user_text = " ".join(buffer_parts).strip()
                            buffer_parts.clear()
                            if user_text:
                                conversation_id, reply_text = await chat_service.send_message(
                                    db, user, conversation_id, user_text
                                )
                                await _speak(websocket, conversation_id, reply_text)

                forward_task = asyncio.create_task(forward_audio())
                transcript_task = asyncio.create_task(handle_transcripts())
                done, pending = await asyncio.wait(
                    {forward_task, transcript_task}, return_when=asyncio.FIRST_COMPLETED
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
        except Exception as e:
            try:
                await _send_json(websocket, {"type": "error", "message": str(e)})
                await websocket.close(code=1011, reason="internal error")
            except Exception:
                pass
