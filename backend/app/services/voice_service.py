from deepgram import AsyncDeepgramClient

from app.core.config import settings

_client: AsyncDeepgramClient | None = None


def get_client() -> AsyncDeepgramClient:
    # Shared with app.services.telephony_service (the phone-call agent) —
    # one lazily-created client per process, same API key.
    global _client
    if _client is None:
        _client = AsyncDeepgramClient(api_key=settings.DEEPGRAM_API_KEY)
    return _client


def open_transcription_stream(sample_rate: int = 16000):
    """
    Live streaming speech-to-text connection to Deepgram, tuned for a
    conversational voice agent (not a transcription/captioning use case):
    interim_results so a caller can show live "as you speak" text,
    endpointing so Deepgram tells us when the customer has actually
    stopped talking (speech_final) rather than us guessing from silence
    ourselves. Returns an async context manager — use as
    `async with open_transcription_stream() as socket:`.
    """
    return get_client().listen.v1.connect(
        model="nova-3",
        encoding="linear16",
        sample_rate=sample_rate,
        channels=1,
        interim_results=True,
        smart_format=True,
        punctuate=True,
        endpointing=300,
    )


async def text_to_speech(text: str) -> bytes:
    """
    WAV bytes for `text`, via Deepgram's TTS REST API (Aura) — the one-shot
    `speak.v1.audio.generate` endpoint, not the streaming Voice Agent
    telephony_service.py uses for phone calls (this is a single
    request/response synthesis, not a live bidirectional session, so the
    simpler REST call is the right fit here).

    Replaced pyttsx3 (local, free, but Windows-only — wrapped SAPI5 via
    COM) specifically because it couldn't run on the Linux host this app
    deploys to; reuses the same VOICE_AGENT_TTS_VOICE the call agent
    already uses, one less TTS system/voice choice to maintain.
    """
    chunks = [
        chunk
        async for chunk in get_client().speak.v1.audio.generate(
            text=text,
            model=settings.VOICE_AGENT_TTS_VOICE,
            # `container` only applies to non-compressed encodings — Deepgram
            # rejects container="wav" with the API's default encoding (mp3),
            # so encoding must be given explicitly here, not left implicit.
            encoding="linear16",
            container="wav",
        )
    ]
    return b"".join(chunks)
