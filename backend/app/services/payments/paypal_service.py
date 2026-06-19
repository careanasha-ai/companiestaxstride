import httpx
import base64
from typing import Optional, Dict, Any
from app.core.config import settings
from app.db.models.payment import Payment
from app.db.models.user import User
from sqlalchemy.ext.asyncio import AsyncSession
from loguru import logger
from datetime import datetime

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

PAYPAL_BASE = (
    "https://api-m.sandbox.paypal.com"
    if settings.PAYPAL_MODE == "sandbox"
    else "https://api-m.paypal.com"
)


class PayPalService:

    async def _get_access_token(self) -> str:
        """Get PayPal OAuth2 access token."""
        credentials = f"{settings.PAYPAL_CLIENT_ID}:{settings.PAYPAL_CLIENT_SECRET}"
        encoded = base64.b64encode(credentials.encode()).decode()
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{PAYPAL_BASE}/v1/oauth2/token",
                headers={
                    "Authorization": f"Basic {encoded}",
                    "Content-Type": "application/x-www-form-urlencoded",
                },
                data={"grant_type": "client_credentials"},
            )
            response.raise_for_status()
            return response.json()["access_token"]

    async def create_order(
        self,
        filing_type: str,
        user: User,
        db: AsyncSession,
        filing_id: Optional[int] = None,
        company_id: Optional[int] = None,
    ) -> Dict[str, Any]:
        """Create a PayPal order for a submission."""
        amount_pence = PRICES.get(filing_type)
        if not amount_pence:
            raise ValueError(f"Unknown filing type: {filing_type}")

        amount_gbp = f"{amount_pence / 100:.2f}"
        description = DESCRIPTIONS.get(filing_type, filing_type)
        access_token = await self._get_access_token()

        order_payload = {
            "intent": "CAPTURE",
            "purchase_units": [
                {
                    "amount": {
                        "currency_code": "GBP",
                        "value": amount_gbp,
                    },
                    "description": description,
                    "custom_id": f"user_{user.id}_filing_{filing_id or 'new'}",
                }
            ],
            "application_context": {
                "brand_name": "CompaniesHouse Tax Stride",
                "landing_page": "BILLING",
                "user_action": "PAY_NOW",
                "return_url": f"{settings.FRONTEND_URL}/payments/paypal/success",
                "cancel_url": f"{settings.FRONTEND_URL}/payments/paypal/cancel",
            },
        }

        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{PAYPAL_BASE}/v2/checkout/orders",
                headers={
                    "Authorization": f"Bearer {access_token}",
                    "Content-Type": "application/json",
                },
                json=order_payload,
            )
            response.raise_for_status()
            order = response.json()

        # Find approve URL
        approve_url = next(
            (link["href"] for link in order.get("links", []) if link["rel"] == "approve"),
            None,
        )

        # Create payment record
        payment = Payment(
            tenant_id=user.tenant_id,
            user_id=user.id,
            filing_type=filing_type,
            amount=amount_pence,
            currency="GBP",
            provider="paypal",
            paypal_order_id=order["id"],
            status="pending",
            description=description,
        )
        db.add(payment)
        await db.flush()
        await db.refresh(payment)

        return {
            "order_id": order["id"],
            "approve_url": approve_url,
            "amount": float(amount_gbp),
            "currency": "GBP",
            "payment_id": payment.id,
        }

    async def capture_order(
        self, order_id: str, db: AsyncSession
    ) -> Dict[str, Any]:
        """Capture an approved PayPal order."""
        access_token = await self._get_access_token()

        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{PAYPAL_BASE}/v2/checkout/orders/{order_id}/capture",
                headers={
                    "Authorization": f"Bearer {access_token}",
                    "Content-Type": "application/json",
                },
            )
            response.raise_for_status()
            capture_data = response.json()

        # Update payment record
        from sqlalchemy import select
        result = await db.execute(
            select(Payment).where(Payment.paypal_order_id == order_id)
        )
        payment = result.scalar_one_or_none()
        if payment:
            capture_units = capture_data.get("purchase_units", [{}])
            captures = capture_units[0].get("payments", {}).get("captures", [{}])
            capture_id = captures[0].get("id") if captures else None
            payment.status = "succeeded"
            payment.paypal_capture_id = capture_id
            payment.paid_at = datetime.utcnow()
            await db.flush()
            logger.info(f"PayPal payment {payment.id} captured")

        return {
            "status": capture_data.get("status"),
            "order_id": order_id,
            "payment_id": payment.id if payment else None,
        }

    async def handle_webhook(self, payload: Dict, db: AsyncSession):
        """Handle PayPal IPN/webhook events."""
        event_type = payload.get("event_type", "")
        resource = payload.get("resource", {})

        if event_type == "PAYMENT.CAPTURE.COMPLETED":
            order_id = resource.get("supplementary_data", {}).get(
                "related_ids", {}
            ).get("order_id")
            if order_id:
                await self.capture_order(order_id, db)

        logger.info(f"PayPal webhook handled: {event_type}")


paypal_service = PayPalService()