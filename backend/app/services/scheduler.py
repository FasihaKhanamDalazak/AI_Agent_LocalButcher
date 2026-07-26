import asyncio
import logging

from fastapi import FastAPI

from app.core.config import settings
from app.db.session import AsyncSessionLocal
from app.services import order_service

logger = logging.getLogger(__name__)


async def _run_forever() -> None:
    while True:
        await asyncio.sleep(settings.AUTO_PROGRESS_CHECK_INTERVAL_SECONDS)
        try:
            async with AsyncSessionLocal() as db:
                updated = await order_service.auto_progress_orders(db)
                if updated:
                    logger.info("auto-progressed %d order(s)", updated)
        except Exception:
            # A single bad tick (e.g. a transient DB hiccup) must never kill
            # the loop — there's no supervisor restarting this task, so an
            # unhandled exception here would silently stop all future
            # auto-progression for the rest of the process's life.
            logger.exception("order auto-progression tick failed")


def start(app: FastAPI) -> None:
    """Called from main.py's lifespan — see there for the matching cancel on shutdown."""
    if not settings.AUTO_PROGRESS_ORDERS:
        logger.info("AUTO_PROGRESS_ORDERS is false — order auto-progression disabled")
        return
    app.state.order_auto_progress_task = asyncio.create_task(_run_forever())


async def stop(app: FastAPI) -> None:
    task = getattr(app.state, "order_auto_progress_task", None)
    if task is None:
        return
    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        pass
