from pydantic import BaseModel
from typing import Optional, Dict, Any
from datetime import datetime


class PaymentCreate(BaseModel):
    filing_type: str
    provider: str  # stripe, paypal
    company_id: int
    filing_id: Optional[int] = None
    metadata: Optional[Dict[str, Any]] = None


class StripePaymentIntentCreate(BaseModel):
    filing_type: str
    company_id: int
    filing_id: Optional[int] = None


class StripePaymentIntentOut(BaseModel):
    client_secret: str
    payment_intent_id: str
    amount: int
    currency: str
    publishable_key: str


class PayPalOrderCreate(BaseModel):
    filing_type: str
    company_id: int
    filing_id: Optional[int] = None


class PayPalOrderOut(BaseModel):
    order_id: str
    approve_url: str
    amount: float
    currency: str


class PayPalCaptureRequest(BaseModel):
    order_id: str
    filing_id: Optional[int] = None


class PaymentOut(BaseModel):
    id: int
    tenant_id: int
    user_id: int
    filing_type: str
    amount: int
    currency: str
    provider: str
    status: str
    description: Optional[str]
    paid_at: Optional[datetime]
    created_at: datetime

    class Config:
        from_attributes = True


class PricingOut(BaseModel):
    confirmation_statement: int
    annual_accounts: int
    vat_return: int
    ct600: int
    currency: str = "GBP"

    class Config:
        from_attributes = True


class WebhookEvent(BaseModel):
    provider: str
    event_type: str
    payload: Dict[str, Any]