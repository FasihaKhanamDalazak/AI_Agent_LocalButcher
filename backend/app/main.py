import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, status

# Without this, Python's root logger defaults to WARNING with no handler —
# every logger.info() call across the app (e.g. telephony_service.py's
# call-diagnostics logging) silently vanishes even though uvicorn's OWN
# access/error logs still show (uvicorn configures its loggers separately).
# Discovered the hard way debugging a live phone call with "missing" logs
# that were actually just never emitted.
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware

from app.api.v1.router import api_router
from app.core.config import settings
from app.core.rate_limit import limiter
from app.services import scheduler

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    scheduler.start(app)
    yield
    await scheduler.stop(app)


def create_app() -> FastAPI:
    app = FastAPI(
        title=settings.APP_NAME,
        version="0.1.0",
        docs_url="/docs" if settings.DEBUG else None,
        redoc_url=None,
        lifespan=lifespan,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.CORS_ORIGINS,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
    app.add_middleware(SlowAPIMiddleware)

    # Last resort: anything that isn't a deliberate HTTPException (a 404,
    # a validation error, etc. — those already get FastAPI's own handling)
    # ends up here instead of leaking a raw traceback to the client. Logged
    # server-side so it's not silently swallowed, but the client only ever
    # sees a generic message — never exception internals, stack traces, or
    # anything that could hint at schema/implementation details.
    @app.exception_handler(Exception)
    async def unhandled_exception_handler(request: Request, exc: Exception):
        logger.exception("Unhandled exception on %s %s", request.method, request.url.path)
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={"detail": "An unexpected error occurred."},
        )

    app.include_router(api_router, prefix="/api/v1")

    @app.get("/health", tags=["system"])
    async def health_check():
        return {"status": "ok", "environment": settings.ENVIRONMENT}

    return app


app = create_app()
