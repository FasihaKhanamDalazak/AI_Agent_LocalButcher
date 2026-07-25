import asyncio
import os
import tempfile

import pyttsx3
from deepgram import AsyncDeepgramClient

from app.core.config import settings

_client: AsyncDeepgramClient | None = None


def _get_client() -> AsyncDeepgramClient:
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
    return _get_client().listen.v1.connect(
        model="nova-3",
        encoding="linear16",
        sample_rate=sample_rate,
        channels=1,
        interim_results=True,
        smart_format=True,
        punctuate=True,
        endpointing=300,
    )


def _synthesize_sync(text: str) -> bytes:
    # A fresh engine per call, run inside asyncio.to_thread (below) — pyttsx3
    # wraps Windows SAPI5 via COM, which is thread-affine; reusing one engine
    # instance across the thread-pool's worker threads is not safe, but a
    # new instance per call on whichever thread runs it is.
    engine = pyttsx3.init()
    fd, path = tempfile.mkstemp(suffix=".wav")
    os.close(fd)
    try:
        engine.save_to_file(text, path)
        engine.runAndWait()
        with open(path, "rb") as f:
            return f.read()
    finally:
        os.remove(path)


async def text_to_speech(text: str) -> bytes:
    """WAV bytes for `text`, spoken with the local OS voice. Never touches the network."""
    return await asyncio.to_thread(_synthesize_sync, text)
