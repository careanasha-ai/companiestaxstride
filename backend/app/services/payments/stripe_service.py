import stripe
from typing import Optional, Dict, Any
from app.core.config import settings
from app.db.models.payment import Payment
from app.db.models.user import User
from sqlalchemy.ext.asyncio import AsyncSession
from loguru import logger
from datetime import datetime

stripe.api_key = settings.STRIPE_SECRET_KEY

PRICES = {
    "confirmation_statement": settings.PRICE_CONFIRMATION_STATEMENT,
    "annual_accounts": settings.PRICE_ANNUAL_ACCOUNTS,
    "vat_return": settings.PRICE_VAT_RETURN,
    "ct600": settings.PRICE_CT600,
}

DESCRIPTIONS = {
    "confirmation_statement": "Confirmation Statement (CS01) Filing",
    "annual_accounts": "Annual Accounts (AA) Filing",
    "vat_return": "VAT Return Submission",
    "ct600": "Corporation Tax (CT600) Submission",
}


class StripeService:

    async def get_or_create_customer(self, user: User, db: AsyncSession) -> str:
        """Get or create a Stripe customer for the user."""
        if user.stripe_customer_id:
            return user.stripe_customer_id
        customer = stripe.Customer.create(
            email=user.email,
            name=user.full_name or user.email,
            metadata={"user_id": str(user.id), "tenant_id": str(user.tenant_id)},
        )
        user.stripe_customer_id = customer.id
        await db.flush()
        return customer.id

    async def create_payment_intent(
        self,
        filing_type: str,
        user: User,
        db: AsyncSession,
        filing_id: Optional[int] = None,
        company_id: Optional[int] = None,
    ) -> Dict[str, Any]:
        """Create a Stripe PaymentIntent for a submission."""
        amount = PRICES.get(filing_type)
        if not amount:
            raise ValueError(f"Unknown filing type: {filing_type}")

        customer_id = await self.get_or_create_customer(user, db)

        intent = stripe.PaymentIntent.create(
            amount=amount,
            currency="gbp",
            customer=customer_id,
            description=DESCRIPTIONS.get(filing_type, filing_type),
            metadata={
                "filing_type": filing_type,
                "user_id": str(user.id),
                "tenant_id": str(user.tenant_id),
                "filing_id": str(filing_id) if filing_id else "",
                "company_id": str(company_id) if company_id else "",
            },
            automatic_payment_methods={"enabled": True},
        )

        # Create payment record
        payment = Payment(
            tenant_id=user.tenant_id,
            user_id=user.id,
            filing_type=filing_type,
            amount=amount,
            currency="GBP",
            provider="stripe",
            stripe_payment_intent_id=intent.id,
            status="pending",
            description=DESCRIPTIONS.get(filing_type),
        )
        db.add(payment)
        await db.flush()
        await db.refresh(payment)

        return {
            "client_secret": intent.client_secret,
            "payment_intent_id": intent.id,
            "amount": amount,
            "currency": "GBP",
            "publishable_key": settings.STRIPE_PUBLISHABLE_KEY,
            "payment_id": payment.id,
        }

    async def handle_webhook(self, payload: bytes, sig_header: str, db: AsyncSession):
        """Handle Stripe webhook events."""
        try:
            event = stripe.Webhook.construct_event(
                payload, sig_header, settings.STRIPE_WEBHOOK_SECRET
            )
        except stripe.error.SignatureVerificationError:
            raise ValueError("Invalid Stripe webhook signature")

        event_type = event["type"]
        data = event["data"]["object"]

        if event_type == "payment_intent.succeeded":
            await self._handle_payment_succeeded(data, db)
        elif event_type == "payment_intent.payment_failed":
            await self._handle_payment_failed(data, db)
        elif event_type == "charge.refunded":
            await self._handle_refund(data, db)

        logger.info(f"Stripe webhook handled: {event_type}")

    async def _handle_payment_succeeded(self, intent: Dict, db: AsyncSession):
        from sqlalchemy import select
        result = await db.execute(
            select(Payment).where(
                Payment.stripe_payment_intent_id == intent["id"]
            )
        )
        payment = result.scalar_one_or_none()
        if payment:
            payment.status = "succeeded"
            payment.paid_at = datetime.utcnow()
            payment.stripe_charge_id = intent.get("latest_charge")
            await db.flush()
            logger.info(f"Payment {payment.id} succeeded")

    async def _handle_payment_failed(self, intent: Dict, db: AsyncSession):
        from sqlalchemy import select
        result = await db.execute(
            select(Payment).where(
                Payment.stripe_payment_intent_id == intent["id"]
            )
        )
        payment = result.scalar_one_or_none()
        if payment:
            payment.status = "failed"
            await db.flush()

    async def _handle_refund(self, charge: Dict, db: AsyncSession):
        from sqlalchemy import select
        result = await db.execute(
            select(Payment).where(
                Payment.stripe_charge_id == charge["id"]
            )
        )
        payment = result.scalar_one_or_none()
        if payment:
            payment.status = "refunded"
            payment.refunded_at = datetime.utcnow()
            payment.refund_amount = charge.get("amount_refunded")
            await db.flush()


stripe_service = StripeService()