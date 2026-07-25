from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import hash_password, verify_password
from app.models.user import User
from app.schemas.user import UserCreate


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
