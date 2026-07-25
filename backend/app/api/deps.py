import uuid

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.db.session import get_db
from app.models.user import User

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login")


async def get_user_from_token(token: str, db: AsyncSession) -> User | None:
    """
    The single place a JWT is turned into a User — shared by the normal
    header-based REST auth (get_current_user, below) and the WebSocket
    voice endpoint, which can't use an Authorization header (browsers
    don't support custom headers on the WebSocket handshake) and instead
    passes the token as a query param. Returns None on any failure rather
    than raising, so each caller decides how to react (HTTPException for
    REST, closing the socket for WebSocket).
    """
    try:
        payload = jwt.decode(token, settings.JWT_SECRET_KEY, algorithms=[settings.JWT_ALGORITHM])
        user_id_raw = payload.get("sub")
        if user_id_raw is None:
            return None
        user_id = uuid.UUID(user_id_raw)
    except (JWTError, ValueError):
        return None

    result = await db.execute(select(User).where(User.id == user_id))
    return result.scalar_one_or_none()


async def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: AsyncSession = Depends(get_db),
) -> User:
    """
    Every endpoint that needs to know "who is asking" depends on this —
    directly or indirectly through a service function. It's the ONLY place
    a user id is derived from a token; nothing downstream ever accepts a
    user_id from a request body or query param. This is the mechanism
    behind the security guardrail from the design phase: an LLM tool like
    get_order_status() takes an order_id, but the user_id it's scoped to
    always comes from here, never from the LLM's function call arguments.
    """
    user = await get_user_from_token(token, db)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return user


async def get_current_staff_user(current_user: User = Depends(get_current_user)) -> User:
    """
    Layers on top of get_current_user — proves who's asking, THEN checks
    they're allowed to act as staff. There's no separate staff login or
    token type; a staff member logs in exactly like a customer, and the
    only difference is this check. Promoting a user to "staff" is a direct
    DB edit (see app/models/user.py) — no API path sets it.
    """
    if current_user.role != "staff":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Staff access required")
    return current_user
