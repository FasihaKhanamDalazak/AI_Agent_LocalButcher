import logging
import re

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import hash_password, verify_password
from app.models.user import User
from app.schemas.user import UserCreate

logger = logging.getLogger(__name__)


class EmailAlreadyRegisteredError(Exception):
    pass


class PhoneAlreadyRegisteredError(Exception):
    pass


class InvalidCredentialsError(Exception):
    pass


async def register_user(db: AsyncSession, data: UserCreate) -> User:
    existing = await db.execute(select(User).where(User.email == data.email))
    if existing.scalar_one_or_none() is not None:
        raise EmailAlreadyRegisteredError()

    # phone is now required at signup (see UserCreate) and unique at the DB
    # level — worth checking explicitly, the same as email above, now that
    # a collision is a realistic case rather than two NULLs (which Postgres
    # never treats as a uniqueness conflict).
    existing_phone = await db.execute(select(User).where(User.phone == data.phone))
    if existing_phone.scalar_one_or_none() is not None:
        raise PhoneAlreadyRegisteredError()

    user = User(
        name=data.name,
        email=data.email,
        phone=data.phone,
        password_hash=hash_password(data.password),
        preferred_language=data.preferred_language,
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user


async def authenticate_user(db: AsyncSession, email: str, password: str) -> User:
    result = await db.execute(select(User).where(User.email == email))
    user = result.scalar_one_or_none()
    if user is None or not verify_password(password, user.password_hash):
        raise InvalidCredentialsError()
    return user


def _normalize_phone(raw: str) -> str:
    # Stored phones are a plain 10-digit Indian mobile number, no country
    # code (see UserCreate.phone's pattern, and migration
    # e2c525353f62_strip_country_code_from_phone_numbers for why the
    # earlier E.164 convention was dropped — it only ever created a way
    # for a caller's spoken number to mismatch what's stored, confirmed
    # directly: verification worked once, then failed on a second real
    # call with no code change in between, traced to this). Strip
    # everything but digits, then take the LAST 10 — robust to a caller
    # saying "+91"/"091" out of habit, or Deepgram transcribing either
    # into the string, without needing to special-case them: whatever
    # comes before the actual 10-digit mobile number just falls away.
    digits = re.sub(r"\D", "", raw)
    return digits[-10:]


async def get_user_by_phone(db: AsyncSession, phone: str) -> User | None:
    """
    Looks up a registered user by phone number — used by the call agent's
    verification step (see app/services/telephony_service.py) after the
    caller states their registered mobile number out loud. Never called
    with anything from a JWT-authenticated request; this IS the
    authentication step for that channel, not a lookup scoped to an
    already-known user.
    """
    normalized = _normalize_phone(phone)
    result = await db.execute(select(User).where(User.phone == normalized))
    user = result.scalar_one_or_none()
    # Logged deliberately — a phone number isn't a secret the way a
    # password is (we already log it elsewhere, e.g. the call `start`
    # event's `from` field), and this is the only way to actually see what
    # the model passed through when verification unexpectedly fails, since
    # there was previously zero visibility into the raw vs. normalized
    # value at the one place they can diverge from what was intended.
    logger.info(
        "get_user_by_phone: raw=%r normalized=%r matched=%s",
        phone,
        normalized,
        user is not None,
    )
    return user
