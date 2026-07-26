from datetime import datetime
from zoneinfo import ZoneInfo

from app.core.config import settings


def format_local_time(dt: datetime) -> str:
    local = dt.astimezone(ZoneInfo(settings.DISPLAY_TIMEZONE))
    # %-I isn't portable (fails on Windows) — strip the leading zero manually instead.
    return local.strftime("%I:%M %p").lstrip("0")


def eta_text(eta_start: datetime | None, eta_end: datetime | None) -> str:
    """
    Pre-formatted, already-in-local-time ETA text — used by both the
    greeting (greeting_service.py) and order_to_read (schemas/order.py)
    so every channel (chat/voice/calls, via order_to_read's eta_text
    field) gets the SAME ready-made string, never a raw UTC datetime the
    model would have to convert itself. That conversion was a real bug:
    the call agent was reading eta_start's raw UTC value as if it were
    already local time, producing nonsense like "9 AM tomorrow" for an
    order placed thirty minutes earlier the same afternoon.
    """
    if eta_start and eta_end:
        return f"between {format_local_time(eta_start)} and {format_local_time(eta_end)}"
    if eta_start:
        return f"ready by {format_local_time(eta_start)}"
    return "not available yet"
