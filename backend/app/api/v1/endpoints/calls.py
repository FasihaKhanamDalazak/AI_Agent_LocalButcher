import base64
import binascii
import hmac
import logging

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from limits import RateLimitItemPerMinute, storage, strategies

from app.core.config import settings
from app.db.session import AsyncSessionLocal
from app.services import telephony_service

router = APIRouter()
logger = logging.getLogger(__name__)

# Same rationale and pattern as voice.py's connection limiter: slowapi only
# covers regular HTTP routes, and a live call already bounds concurrency far
# more than a browser tab would — this just guards against a rapid-reconnect
# loop, not normal call volume.
_connection_storage = storage.MemoryStorage()
_connection_limiter = strategies.FixedWindowRateLimiter(_connection_storage)
_connection_rate = RateLimitItemPerMinute(10)


def _basic_auth_ok(websocket: WebSocket) -> bool:
    # Exotel has no HMAC request signing (unlike Twilio) — Basic Auth on the
    # handshake is its documented alternative (IP whitelisting being the
    # other, not used here). Fail CLOSED if the shared secret isn't
    # configured at all — an empty expected username/password must never be
    # treated as "auth disabled".
    if not settings.EXOTEL_BASIC_AUTH_USERNAME or not settings.EXOTEL_BASIC_AUTH_PASSWORD:
        return False

    header = websocket.headers.get("authorization")
    if not header or not header.startswith("Basic "):
        return False

    try:
        decoded = base64.b64decode(header[len("Basic "):]).decode("utf-8")
        username, _, password = decoded.partition(":")
    except (binascii.Error, UnicodeDecodeError):
        return False

    # Constant-time comparison — a naive `==` here would leak timing
    # information about the shared secret to anyone probing this endpoint.
    return hmac.compare_digest(username, settings.EXOTEL_BASIC_AUTH_USERNAME) and hmac.compare_digest(
        password, settings.EXOTEL_BASIC_AUTH_PASSWORD
    )


@router.websocket("/stream")
async def calls_stream(websocket: WebSocket):
    """
    Exotel's Voicebot/AgentStream applet connects here for the lifetime of
    one phone call (see developer.exotel.com/docs/agentstream/developer-guide
    and app/services/telephony_service.py for the full protocol/bridge). No
    incoming-call webhook exists or is needed — routing a phone number to
    this WS is configured entirely in Exotel's own dashboard.

    Auth is HTTP Basic on the handshake, not a JWT — the caller isn't a
    logged-in app user yet (that's the whole point of the phone-verification
    flow in telephony_service.py); Exotel itself is what's being
    authenticated here, the same way it authenticates any custom endpoint it
    calls out to.
    """
    if not settings.EXOTEL_REQUIRE_AUTH:
        # Deliberate, explicit opt-out (EXOTEL_REQUIRE_AUTH=false in .env) —
        # see config.py. Never the default; logged loudly every single
        # connection so this can't go unnoticed in server logs.
        logger.warning(
            "calls WS accepted WITHOUT auth (EXOTEL_REQUIRE_AUTH=false) — remote=%s",
            websocket.client.host if websocket.client else "unknown",
        )
    elif not _basic_auth_ok(websocket):
        await websocket.close(code=4401, reason="invalid or missing credentials")
        return

    # Keyed on remote host since, unlike voice.py's browser clients, there's
    # no authenticated user yet to key on at connection time.
    client_key = websocket.client.host if websocket.client else "unknown"
    if not _connection_limiter.hit(_connection_rate, client_key):
        await websocket.close(code=4429, reason="too many connection attempts, slow down")
        return

    await websocket.accept()

    async with AsyncSessionLocal() as db:
        try:
            await telephony_service.bridge_call(websocket, db)
        except WebSocketDisconnect:
            pass
        except Exception:
            # Same redaction contract as voice.py and main.py: log the real
            # exception server-side, never leak it to Exotel/the caller.
            logger.exception("Unhandled exception on calls WS")
            try:
                await websocket.close(code=1011, reason="internal error")
            except Exception:
                pass
