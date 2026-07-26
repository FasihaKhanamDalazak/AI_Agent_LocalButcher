import logging
import uuid

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from limits import RateLimitItemPerMinute, storage, strategies

from app.api.deps import get_user_from_token
from app.db.session import AsyncSessionLocal
from app.services import voice_service

router = APIRouter()
logger = logging.getLogger(__name__)

# slowapi's decorator only covers regular HTTP routes, not WebSockets, but
# this is the single most expensive endpoint in the app (continuous
# Deepgram audio streaming) — worth a basic guard against a client rapidly
# opening connections. Limits new CONNECTIONS per user, not messages within
# one; a real conversation is one long-lived connection, so this doesn't
# affect normal use. Same in-memory/single-instance caveat as the app's
# main rate limiter.
_connection_storage = storage.MemoryStorage()
_connection_limiter = strategies.FixedWindowRateLimiter(_connection_storage)
_connection_rate = RateLimitItemPerMinute(5)


@router.websocket("/stream")
async def voice_stream(websocket: WebSocket):
    """
    Real-time voice conversation with the same Local Butcher agent used by
    text chat. Auth: browsers can't set an Authorization header on a
    WebSocket handshake, so the JWT is passed as a query param instead
    (?token=...) and resolved through the same get_user_from_token used
    by the header-based REST auth — same security guarantee, different
    transport.

    All the actual bridging (Deepgram's Voice Agent API — STT+Gemini+TTS
    together, see backend CLAUDE.md's "Voice layer") lives in
    voice_service.bridge_browser_voice; this endpoint only handles auth,
    rate limiting, and the accept/error-redaction contract, matching
    calls.py's thin-endpoint pattern.
    """
    token = websocket.query_params.get("token")

    async with AsyncSessionLocal() as db:
        user = await get_user_from_token(token, db) if token else None
        if user is None:
            await websocket.close(code=4401, reason="invalid or missing token")
            return

        if not _connection_limiter.hit(_connection_rate, str(user.id)):
            await websocket.close(code=4429, reason="too many connection attempts, slow down")
            return

        await websocket.accept()

        conversation_id_raw = websocket.query_params.get("conversation_id")
        conversation_id = uuid.UUID(conversation_id_raw) if conversation_id_raw else None

        try:
            await voice_service.bridge_browser_voice(websocket, db, user, conversation_id)
        except WebSocketDisconnect:
            pass
        except Exception:
            # Same redaction contract as main.py's REST-side handler: the
            # real exception is always logged server-side, but the client
            # only ever gets a generic message.
            logger.exception("Unhandled exception on voice WS for user %s", user.id)
            try:
                await websocket.close(code=1011, reason="internal error")
            except Exception:
                pass
