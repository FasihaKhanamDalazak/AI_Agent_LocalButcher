from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.core.rate_limit import limiter
from app.core.security import create_access_token
from app.db.session import get_db
from app.models.user import User
from app.schemas.auth import Token
from app.schemas.user import UserCreate, UserRead
from app.services import auth_service

router = APIRouter()


# Stricter than the app default (60/minute) — these are the two endpoints
# a brute-force/credential-stuffing attempt would actually hit.
@router.post("/register", response_model=Token, status_code=status.HTTP_201_CREATED)
@limiter.limit("10/minute")
async def register(request: Request, data: UserCreate, db: AsyncSession = Depends(get_db)):
    try:
        user = await auth_service.register_user(db, data)
    except auth_service.EmailAlreadyRegisteredError:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Email already registered")
    except auth_service.PhoneAlreadyRegisteredError:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Phone number already registered")
    return Token(access_token=create_access_token(subject=str(user.id)))


@router.post("/login", response_model=Token)
@limiter.limit("10/minute")
async def login(request: Request, form_data: OAuth2PasswordRequestForm = Depends(), db: AsyncSession = Depends(get_db)):
    # form_data.username carries the email — this is standard OAuth2 password
    # flow shape, which is also what makes Swagger's "Authorize" button work
    # out of the box for testing in /docs.
    try:
        user = await auth_service.authenticate_user(db, form_data.username, form_data.password)
    except auth_service.InvalidCredentialsError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return Token(access_token=create_access_token(subject=str(user.id)))


@router.get("/me", response_model=UserRead)
async def read_current_user(current_user: User = Depends(get_current_user)):
    return current_user
