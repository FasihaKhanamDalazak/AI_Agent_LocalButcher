from deepgram import AsyncDeepgramClient

from app.core.config import settings

# Shared by voice_service.py (browser voice), telephony_service.py (phone
# calls), and app/llm/deepgram_chat_client.py (text chat) — split out into
# its own module specifically to avoid a circular import
# (deepgram_chat_client needs a Deepgram client but chat_service, which it
# feeds into, is also imported by voice_service for HISTORY_MESSAGE_LIMIT).
_client: AsyncDeepgramClient | None = None


def get_client() -> AsyncDeepgramClient:
    global _client
    if _client is None:
        _client = AsyncDeepgramClient(api_key=settings.DEEPGRAM_API_KEY)
    return _client
