from fastapi import APIRouter, Depends, HTTPException, status, Request, Header
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import Optional, List

from app.db.database import get_db
from app.db.models.user import User
from app.db.models.payment import Payment
from app.core.dependencies import get_current_user
from app.core.config import settings
from app.services.payments.stripe_service import stripe_service
from app.services.payments.paypal_service import paypal_service
from app.schemas.payment import (
    StripePaymentIntentCreate, StripePaymentIntentOut,
    PayPalOrderCreate, PayPalOrderOut,
    PayPalCaptureRequest, PaymentOut, PricingOut
)

router = APIRouter(prefix="/payments", tags=["Payments"])


# ─── PRICING (FREE) ───────────────────────────────────────────────────────────

@router.get("/pricing", response_model=PricingOut)
async def get_pricing():
    """Get current submission pricing — FREE, no auth required."""
    return PricingOut(
        confirmation_statement=settings.PRICE_CONFIRMATION_STATEMENT,
        annual_accounts=settings.PRICE_ANNUAL_ACCOUNTS,
        vat_return=settings.PRICE_VAT_RETURN,
        ct600=settings.PRICE_CT600,
        currency="GBP",
    )


# ─── PAYMENT HISTORY ──────────────────────────────────────────────────────────

@router.get("/history", response_model=List[PaymentOut])
async def get_payment_history(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get payment history for the current user."""
    result = await db.execute(
        select(Payment)
        .where(
            Payment.user_id == current_user.id,
            Payment.status.in_(["succeeded", "refunded"]),
        )
        .order_by(Payment.created_at.desc())
    )
    payments = result.scalars().all()
    return [PaymentOut.model_validate(p) for p in payments]


# ─── STRIPE ───────────────────────────────────────────────────────────────────

@router.post("/stripe/create-intent", response_model=StripePaymentIntentOut)
async def create_stripe_payment_intent(
    payload: StripePaymentIntentCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Create a Stripe PaymentIntent for a submission."""
    try:
        result = await stripe_service.create_payment_intent(
            filing_type=payload.filing_type,
            user=current_user,
            db=db,
            filing_id=payload.filing_id,
            company_id=payload.company_id,
        )
        return StripePaymentIntentOut(
            client_secret=result["client_secret"],
            payment_intent_id=result["payment_intent_id"],
            amount=result["amount"],
            currency=result["currency"],
            publishable_key=result["publishable_key"],
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(e))


@router.post("/stripe/webhook")
async def stripe_webhook(
    request: Request,
    stripe_signature: Optional[str] = Header(None, alias="stripe-signature"),
    db: AsyncSession = Depends(get_db),
):
    """Handle Stripe webhook events."""
    if not stripe_signature:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Missing Stripe signature")

    payload = await request.body()
    try:
        await stripe_service.handle_webhook(payload, stripe_signature, db)
        return {"status": "ok"}
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


@router.post("/stripe/confirm/{payment_intent_id}")
async def confirm_stripe_payment(
    payment_intent_id: str,
    filing_id: Optional[int] = None,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Confirm a Stripe payment succeeded and update filing status to 'paid'.
    Called from frontend after successful payment.
    """
    result = await db.execute(
        select(Payment).where(
            Payment.stripe_payment_intent_id == payment_intent_id,
            Payment.user_id == current_user.id,
        )
    )
    payment = result.scalar_one_or_none()
    if not payment:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Payment not found")

    if payment.status == "succeeded" and filing_id:
        from app.db.models.filing import Filing
        filing_result = await db.execute(
            select(Filing).where(Filing.id == filing_id)
        )
        filing = filing_result.scalar_one_or_none()
        if filing and filing.status == "pending_payment":
            filing.status = "paid"
            filing.payment_id = payment.id
            await db.flush()

    return {"status": payment.status, "payment_id": payment.id}


# ─── PAYPAL ───────────────────────────────────────────────────────────────────

@router.post("/paypal/create-order", response_model=PayPalOrderOut)
async def create_paypal_order(
    payload: PayPalOrderCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Create a PayPal order for a submission."""
    try:
        result = await paypal_service.create_order(
            filing_type=payload.filing_type,
            user=current_user,
            db=db,
            filing_id=payload.filing_id,
            company_id=payload.company_id,
        )
        return PayPalOrderOut(
            order_id=result["order_id"],
            approve_url=result["approve_url"],
            amount=result["amount"],
            currency=result["currency"],
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(e))


@router.post("/paypal/capture")
async def capture_paypal_order(
    payload: PayPalCaptureRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Capture an approved PayPal order and mark filing as paid."""
    try:
        result = await paypal_service.capture_order(payload.order_id, db)

        if payload.filing_id and result.get("payment_id"):
            from app.db.models.filing import Filing
            filing_result = await db.execute(
                select(Filing).where(Filing.id == payload.filing_id)
            )
            filing = filing_result.scalar_one_or_none()
            if filing and filing.status in ("draft", "pending_payment"):
                filing.status = "paid"
                filing.payment_id = result["payment_id"]
                await db.flush()

        return result
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(e))


@router.post("/paypal/webhook")
async def paypal_webhook(
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """Handle PayPal webhook/IPN events."""
    payload = await request.json()
    try:
        await paypal_service.handle_webhook(payload, db)
        return {"status": "ok"}
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))