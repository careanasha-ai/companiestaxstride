from sqlalchemy import Column, Integer, String, Boolean, DateTime, Text, ForeignKey, Numeric, JSON
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.db.database import Base


class Payment(Base):
    """Payment records for submissions."""
    __tablename__ = "payments"

    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id"), nullable=False, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)

    # What is being paid for
    filing_type = Column(String(50), nullable=False)
    # confirmation_statement, annual_accounts, vat_return, ct600

    # Amount
    amount = Column(Integer, nullable=False)  # in pence
    currency = Column(String(3), default="GBP")

    # Payment provider
    provider = Column(String(20), nullable=False)  # stripe, paypal

    # Stripe fields
    stripe_payment_intent_id = Column(String(255), nullable=True, unique=True)
    stripe_charge_id = Column(String(255), nullable=True)
    stripe_receipt_url = Column(Text, nullable=True)

    # PayPal fields
    paypal_order_id = Column(String(255), nullable=True, unique=True)
    paypal_capture_id = Column(String(255), nullable=True)

    # Status
    status = Column(String(50), default="pending")
    # pending, processing, succeeded, failed, refunded, cancelled

    # Metadata
    description = Column(Text, nullable=True)
    metadata = Column(JSON, nullable=True)

    # Timestamps
    paid_at = Column(DateTime(timezone=True), nullable=True)
    refunded_at = Column(DateTime(timezone=True), nullable=True)
    refund_amount = Column(Integer, nullable=True)
    refund_reason = Column(Text, nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # Relationships
    tenant = relationship("Tenant", back_populates="payments")
    user = relationship("User", back_populates="payments")
    filings = relationship("Filing", back_populates="payment")


class SubmissionPrice(Base):
    """Configurable submission prices."""
    __tablename__ = "submission_prices"

    id = Column(Integer, primary_key=True, index=True)
    filing_type = Column(String(50), unique=True, nullable=False)
    amount = Column(Integer, nullable=False)  # in pence
    currency = Column(String(3), default="GBP")
    description = Column(String(255), nullable=True)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())