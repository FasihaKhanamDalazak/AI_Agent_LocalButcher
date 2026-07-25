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

    # Used only to format times for display (e.g. in the greeting). All
    # timestamps are stored in UTC regardless of this setting.
    DISPLAY_TIMEZONE: str = "Asia/Kolkata"

    # No currency field exists anywhere in the schema — prices are stored
    # as plain numbers. This is purely a display label, used in the chat
    # grounding note and the system prompt so amounts are always shown
    # consistently instead of the model guessing a symbol from context.
    CURRENCY_LABEL: str = "Rs."


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
