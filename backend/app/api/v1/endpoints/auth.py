from fastapi import APIRouter, Depends, HTTPException, status, BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from datetime import datetime, timedelta
import secrets
import re

from app.db.database import get_db
from app.db.models.user import User, Tenant
from app.core.security import (
    verify_password, get_password_hash,
    create_access_token, create_refresh_token, verify_refresh_token
)
from app.core.dependencies import get_current_user
from app.schemas.user import (
    UserRegister, UserLogin, UserOut, TokenResponse,
    RefreshTokenRequest, UserUpdate, PasswordChange
)
from loguru import logger

router = APIRouter(prefix="/auth", tags=["Authentication"])


def slugify(text: str) -> str:
    text = text.lower().strip()
    text = re.sub(r"[^\w\s-]", "", text)
    text = re.sub(r"[\s_-]+", "-", text)
    return text[:50]


@router.post("/register", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
async def register(payload: UserRegister, db: AsyncSession = Depends(get_db)):
    """Register a new user and create their tenant."""
    # Check email uniqueness
    result = await db.execute(select(User).where(User.email == payload.email))
    if result.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Email already registered",
        )

    # Create tenant
    base_slug = slugify(payload.tenant_name)
    slug = base_slug
    counter = 1
    while True:
        existing = await db.execute(select(Tenant).where(Tenant.slug == slug))
        if not existing.scalar_one_or_none():
            break
        slug = f"{base_slug}-{counter}"
        counter += 1

    tenant = Tenant(name=payload.tenant_name, slug=slug)
    db.add(tenant)
    await db.flush()

    # Create user
    user = User(
        tenant_id=tenant.id,
        email=payload.email,
        hashed_password=get_password_hash(payload.password),
        full_name=payload.full_name,
        phone=payload.phone,
        is_active=True,
        is_verified=False,
        email_verification_token=secrets.token_urlsafe(32),
    )
    db.add(user)
    await db.flush()
    await db.refresh(user)

    access_token = create_access_token(user.id, tenant_id=str(tenant.id))
    refresh_token = create_refresh_token(user.id)

    logger.info(f"New user registered: {user.email} (tenant: {tenant.slug})")
    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        user=UserOut.model_validate(user),
    )


@router.post("/login", response_model=TokenResponse)
async def login(payload: UserLogin, db: AsyncSession = Depends(get_db)):
    """Login with email and password."""
    result = await db.execute(select(User).where(User.email == payload.email))
    user = result.scalar_one_or_none()

    if not user or not verify_password(payload.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
        )
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account is deactivated",
        )

    user.last_login = datetime.utcnow()
    await db.flush()

    access_token = create_access_token(user.id, tenant_id=str(user.tenant_id))
    refresh_token = create_refresh_token(user.id)

    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        user=UserOut.model_validate(user),
    )


@router.post("/refresh", response_model=TokenResponse)
async def refresh_token(payload: RefreshTokenRequest, db: AsyncSession = Depends(get_db)):
    """Refresh access token using refresh token."""
    token_data = verify_refresh_token(payload.refresh_token)
    user_id = token_data.get("sub")

    result = await db.execute(select(User).where(User.id == int(user_id)))
    user = result.scalar_one_or_none()
    if not user or not user.is_active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")

    access_token = create_access_token(user.id, tenant_id=str(user.tenant_id))
    new_refresh = create_refresh_token(user.id)

    return TokenResponse(
        access_token=access_token,
        refresh_token=new_refresh,
        user=UserOut.model_validate(user),
    )


@router.get("/me", response_model=UserOut)
async def get_me(current_user: User = Depends(get_current_user)):
    """Get current user profile."""
    return UserOut.model_validate(current_user)


@router.put("/me", response_model=UserOut)
async def update_me(
    payload: UserUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Update current user profile."""
    if payload.full_name is not None:
        current_user.full_name = payload.full_name
    if payload.phone is not None:
        current_user.phone = payload.phone
    await db.flush()
    await db.refresh(current_user)
    return UserOut.model_validate(current_user)


@router.post("/change-password", status_code=status.HTTP_204_NO_CONTENT)
async def change_password(
    payload: PasswordChange,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Change user password."""
    if not verify_password(payload.current_password, current_user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Current password is incorrect",
        )
    current_user.hashed_password = get_password_hash(payload.new_password)
    await db.flush()