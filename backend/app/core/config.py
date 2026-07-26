from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """
    All configuration is read from environment variables (or a local .env file).
    Nothing here is hardcoded — this is what makes the same codebase work in
    development, staging, and production just by swapping env vars.
    """

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    APP_NAME: str = "Local Butcher AI Backend"
    ENVIRONMENT: str = "development"
    DEBUG: bool = True

    # Async URL used by the running app, sync URL used only by Alembic migrations
    DATABASE_URL: str
    DATABASE_URL_SYNC: str

    JWT_SECRET_KEY: str
    JWT_ALGORITHM: str = "HS256"
    JWT_ACCESS_TOKEN_EXPIRE_MINUTES: int = 1440

    CORS_ORIGINS: list[str] = ["http://localhost:3000"]

    GEMINI_API_KEY: str
    DEEPGRAM_API_KEY: str
    # "gemini-flash-latest" is an ALIAS Google maintains and repoints to
    # their current recommended Flash model as new ones ship — not a
    # pinned version. Pinning an exact version (e.g. "gemini-2.5-flash")
    # WILL eventually 404 when Google retires it, exactly as happened
    # already. The alias trades a small amount of version control for not
    # breaking in production every few months. If you ever need to pin a
    # specific version deliberately (e.g. to freeze behavior for a demo),
    # override GEMINI_MODEL in .env — check https://ai.google.dev/gemini-api/docs/models
    # for current options.
    GEMINI_MODEL: str = "gemini-flash-latest"

    # Placeholder ETA heuristic — see order_service.checkout(). Tune these
    # or replace the whole calculation once real logistics data exists.
    ORDER_PREP_MINUTES: int = 20
    DELIVERY_WINDOW_MIN_MINUTES: int = 30
    DELIVERY_WINDOW_MAX_MINUTES: int = 60

    # There's no real staff/logistics operation behind this project yet
    # (see order_service.auto_progress_orders) — orders would otherwise
    # sit in "pending" forever with nothing to move them along, which reads
    # as broken rather than as an intentional placeholder. Set
    # AUTO_PROGRESS_ORDERS=false to disable entirely (e.g. once real staff
    # processing exists) without touching code.
    AUTO_PROGRESS_ORDERS: bool = True
    AUTO_PROGRESS_PACKED_MINUTES: int = 10
    AUTO_PROGRESS_OUT_FOR_DELIVERY_MINUTES: int = 20
    AUTO_PROGRESS_DELIVERED_MINUTES: int = 30
    # How often the background check runs — deliberately much shorter than
    # the thresholds above so each order's own 10/20/30-minute marks land
    # close to on-time regardless of when it was placed, not just on a
    # fixed wall-clock schedule unrelated to individual orders.
    AUTO_PROGRESS_CHECK_INTERVAL_SECONDS: int = 60

    # Used only to format times for display (e.g. in the greeting). All
    # timestamps are stored in UTC regardless of this setting.
    DISPLAY_TIMEZONE: str = "Asia/Kolkata"

    # No currency field exists anywhere in the schema — prices are stored
    # as plain numbers. This is purely a display label, used in the chat
    # grounding note and the system prompt so amounts are always shown
    # consistently instead of the model guessing a symbol from context.
    CURRENCY_LABEL: str = "Rs."

    # Phone-call agent (Exotel <-> Deepgram Voice Agent bridge, app/services/
    # telephony_service.py). Exotel has no HMAC request signing like Twilio —
    # Basic Auth on the WebSocket handshake is its only documented option, a
    # shared secret configured on both this app and Exotel's dashboard.
    EXOTEL_BASIC_AUTH_USERNAME: str = ""
    EXOTEL_BASIC_AUTH_PASSWORD: str = ""
    # Discovered in practice: the Voicebot Applet's config UI doesn't expose
    # a Basic Auth field at all until Exotel support enables the Stream/
    # Voicebot Applet feature on the account (see README's phone-call
    # section). Defaults to REQUIRED (secure by default) — only flip this to
    # false in .env, deliberately, for local testing against an account
    # that can't configure Basic Auth yet. Every connection accepted while
    # false logs a loud warning (see calls.py) so this is never silently on.
    EXOTEL_REQUIRE_AUTH: bool = True
    # Deepgram's managed Google provider needs a model from its own supported
    # list, not the "gemini-flash-latest" alias used elsewhere in this project
    # (see GEMINI_MODEL above) — Deepgram rejects the alias. Pinned deliberately.
    VOICE_AGENT_GEMINI_MODEL: str = "gemini-2.5-flash"
    # Aura has no Hindi voice, only English/Spanish — the call channel is
    # English-only end to end (Flux STT + Aura TTS), unlike text chat's
    # multi-language support. See system_prompt.py's call-specific variant.
    # Helena over the default-sounding Asteria (Deepgram's own docs describe
    # Asteria as "advertising/energetic" — not what a customer-service call
    # wants); Helena is "Caring, Natural, Positive, Friendly, Raspy". See
    # developers.deepgram.com/docs/tts-models for the full voice gallery if
    # this needs revisiting.
    VOICE_AGENT_TTS_VOICE: str = "aura-2-helena-en"
    # Deepgram's Settings message uses this for both audio input and output
    # — MUST match what Exotel actually sends/expects or audio comes out
    # pitch/speed-distorted (confirmed via a real call's logged `start`
    # event: media_format sample_rate was 8000 despite Exotel's docs
    # describing an 8k/16k/24k choice — this account's Voicebot Applet UI
    # has no sample-rate selector at all, so 8000 is not a choice here, it's
    # the only option). If a future account/plan exposes that selector,
    # verify the real value from a live call's logged media_format before
    # assuming a higher rate is safe to switch to.
    CALL_AUDIO_SAMPLE_RATE: int = 8000


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
