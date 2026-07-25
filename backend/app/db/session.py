from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.config import settings

# Supabase's Session pooler requires SSL. Passed here (not as a URL query
# param) because asyncpg's SQLAlchemy dialect expects it as a connect arg.
_connect_args = {"ssl": "require"} if settings.ENVIRONMENT != "test" else {}

engine = create_async_engine(
    settings.DATABASE_URL,
    echo=settings.DEBUG,
    pool_pre_ping=True,  # detects stale/dropped connections before using them
    connect_args=_connect_args,
)

AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    autoflush=False,
    autocommit=False,
    expire_on_commit=False,
)


async def get_db():
    """FastAPI dependency — yields a session, always closes it after the request."""
    async with AsyncSessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()
