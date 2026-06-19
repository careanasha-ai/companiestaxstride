from sqlalchemy import Column, Integer, String, Boolean, DateTime, Text, ForeignKey
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.db.database import Base


class Tenant(Base):
    """A tenant represents a business/individual account."""
    __tablename__ = "tenants"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), nullable=False)
    slug = Column(String(100), unique=True, index=True, nullable=False)
    plan = Column(String(50), default="free")  # free, pay_per_use
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # Relationships
    users = relationship("User", back_populates="tenant", cascade="all, delete-orphan")
    companies = relationship("Company", back_populates="tenant", cascade="all, delete-orphan")
    payments = relationship("Payment", back_populates="tenant", cascade="all, delete-orphan")
    integrations = relationship("Integration", back_populates="tenant", cascade="all, delete-orphan")


class User(Base):
    """Individual user within a tenant."""
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id"), nullable=False, index=True)
    email = Column(String(255), unique=True, index=True, nullable=False)
    hashed_password = Column(String(255), nullable=False)
    full_name = Column(String(255), nullable=True)
    phone = Column(String(50), nullable=True)
    is_active = Column(Boolean, default=True)
    is_verified = Column(Boolean, default=False)
    email_verification_token = Column(String(255), nullable=True)
    password_reset_token = Column(String(255), nullable=True)
    password_reset_expires = Column(DateTime(timezone=True), nullable=True)

    # HMRC OAuth tokens
    hmrc_access_token = Column(Text, nullable=True)
    hmrc_refresh_token = Column(Text, nullable=True)
    hmrc_token_expires = Column(DateTime(timezone=True), nullable=True)

    # Stripe customer
    stripe_customer_id = Column(String(255), nullable=True)
    paypal_payer_id = Column(String(255), nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    last_login = Column(DateTime(timezone=True), nullable=True)

    # Relationships
    tenant = relationship("Tenant", back_populates="users")
    filings = relationship("Filing", back_populates="user", cascade="all, delete-orphan")
    payments = relationship("Payment", back_populates="user", cascade="all, delete-orphan")