from pydantic import BaseModel, EmailStr, validator
from typing import Optional
from datetime import datetime


class TenantCreate(BaseModel):
    name: str
    slug: Optional[str] = None


class TenantOut(BaseModel):
    id: int
    name: str
    slug: str
    plan: str
    is_active: bool
    created_at: datetime

    class Config:
        from_attributes = True


class UserRegister(BaseModel):
    email: EmailStr
    password: str
    full_name: Optional[str] = None
    phone: Optional[str] = None
    tenant_name: str

    @validator("password")
    def password_strength(cls, v):
        if len(v) < 8:
            raise ValueError("Password must be at least 8 characters")
        return v


class UserLogin(BaseModel):
    email: EmailStr
    password: str


class UserOut(BaseModel):
    id: int
    email: str
    full_name: Optional[str]
    phone: Optional[str]
    is_active: bool
    is_verified: bool
    tenant_id: int
    created_at: datetime

    class Config:
        from_attributes = True


class UserUpdate(BaseModel):
    full_name: Optional[str] = None
    phone: Optional[str] = None


class PasswordChange(BaseModel):
    current_password: str
    new_password: str

    @validator("new_password")
    def password_strength(cls, v):
        if len(v) < 8:
            raise ValueError("Password must be at least 8 characters")
        return v


class PasswordReset(BaseModel):
    token: str
    new_password: str


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    user: UserOut


class RefreshTokenRequest(BaseModel):
    refresh_token: str