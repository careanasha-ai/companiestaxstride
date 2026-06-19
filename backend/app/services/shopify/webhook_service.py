"""
Shopify Webhook Service

Handles real-time order events from Shopify:
- orders/create   → import new order immediately
- orders/updated  → update existing order
- orders/paid     → mark order as paid
- orders/cancelled → mark as cancelled
- refunds/create  → handle refund

Shopify sends webhooks signed with HMAC-SHA256 using the API secret.
"""
import hmac
import hashlib
import base64
import json
from decimal import Decimal
from datetime import datetime
from typing import Dict, Any, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_
from app.db.models.integration import Integration, ShopifyTransaction
from app.services.shopify.classifier import sale_classifier
from app.services.shopify.fx_service import fx_service
from app.core.config import settings
from loguru import logger


class ShopifyWebhookService:

    def verify_webhook(self, payload: bytes, hmac_header: str, api_secret: str) -> bool:
        """
        Verify Shopify webhook HMAC signature.
        Shopify signs with HMAC-SHA256 using the shared secret.
        """
        digest = hmac.new(
            api_secret.encode("utf-8"),
            payload,
            hashlib.sha256,
        ).digest()
        computed = base64.b64encode(digest).decode("utf-8")
        return hmac.compare_digest(computed, hmac_header)

    async def handle_event(
        self,
        db: AsyncSession,
        shop_domain: str,
        topic: str,
        payload: Dict[str, Any],
        raw_payload: bytes,
        hmac_header: str,
    ) -> Dict[str, Any]:
        """
        Route a Shopify webhook event to the appropriate handler.
        Returns a result dict with status and details.
        """
        # Find integration by shop domain
        result = await db.execute(
            select(Integration).where(
                and_(
                    Integration.shop_domain == shop_domain,
                    Integration.provider == "shopify",
                    Integration.is_active == True,
                )
            )
        )
        integration = result.scalar_one_or_none()
        if not integration:
            logger.warning(f"Webhook received for unknown shop: {shop_domain}")
            return {"status": "ignored", "reason": "shop not found"}

        # Verify HMAC
        if not self.verify_webhook(raw_payload, hmac_header, settings.SHOPIFY_API_SECRET):
            logger.error(f"Invalid HMAC for webhook from {shop_domain}")
            return {"status": "error", "reason": "invalid signature"}

        logger.info(f"Shopify webhook: {topic} from {shop_domain}")

        # Route to handler
        handlers = {
            "orders/create": self._handle_order_create,
            "orders/updated": self._handle_order_updated,
            "orders/paid": self._handle_order_paid,
            "orders/cancelled": self._handle_order_cancelled,
            "orders/fulfilled": self._handle_order_fulfilled,
            "refunds/create": self._handle_refund_create,
            "app/uninstalled": self._handle_app_uninstalled,
        }

        handler = handlers.get(topic)
        if not handler:
            logger.info(f"No handler for topic: {topic}")
            return {"status": "ignored", "reason": f"no handler for {topic}"}

        return await handler(db, integration, payload)

    async def _handle_order_create(
        self,
        db: AsyncSession,
        integration: Integration,
        order: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Handle orders/create webhook — import new order."""
        shopify_id = str(order.get("id", ""))
        if not shopify_id:
            return {"status": "error", "reason": "no order id"}

        # Check if already exists
        existing = await db.execute(
            select(ShopifyTransaction).where(
                ShopifyTransaction.shopify_order_id == shopify_id
            )
        )
        if existing.scalar_one_or_none():
            return {"status": "skipped", "reason": "already imported"}

        txn = await self._build_transaction(integration, order)
        if txn:
            db.add(txn)
            await db.flush()
            logger.info(f"Webhook: imported order {shopify_id} for shop {integration.shop_domain}")
            return {"status": "created", "order_id": shopify_id, "transaction_id": txn.id}

        return {"status": "error", "reason": "failed to build transaction"}

    async def _handle_order_updated(
        self,
        db: AsyncSession,
        integration: Integration,
        order: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Handle orders/updated webhook — update existing order."""
        shopify_id = str(order.get("id", ""))
        result = await db.execute(
            select(ShopifyTransaction).where(
                ShopifyTransaction.shopify_order_id == shopify_id
            )
        )
        txn = result.scalar_one_or_none()

        if not txn:
            # Order not yet imported — import it now
            return await self._handle_order_create(db, integration, order)

        # Update financial status
        txn.financial_status = order.get("financial_status", txn.financial_status)
        txn.fulfillment_status = order.get("fulfillment_status", txn.fulfillment_status)
        await db.flush()
        return {"status": "updated", "order_id": shopify_id}

    async def _handle_order_paid(
        self,
        db: AsyncSession,
        integration: Integration,
        order: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Handle orders/paid webhook."""
        shopify_id = str(order.get("id", ""))
        result = await db.execute(
            select(ShopifyTransaction).where(
                ShopifyTransaction.shopify_order_id == shopify_id
            )
        )
        txn = result.scalar_one_or_none()
        if txn:
            txn.financial_status = "paid"
            await db.flush()
            return {"status": "updated", "order_id": shopify_id, "financial_status": "paid"}

        # Not yet imported — import now
        return await self._handle_order_create(db, integration, order)

    async def _handle_order_cancelled(
        self,
        db: AsyncSession,
        integration: Integration,
        order: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Handle orders/cancelled webhook."""
        shopify_id = str(order.get("id", ""))
        result = await db.execute(
            select(ShopifyTransaction).where(
                ShopifyTransaction.shopify_order_id == shopify_id
            )
        )
        txn = result.scalar_one_or_none()
        if txn:
            txn.financial_status = "cancelled"
            await db.flush()
            return {"status": "updated", "order_id": shopify_id, "financial_status": "cancelled"}
        return {"status": "skipped", "reason": "order not found"}

    async def _handle_order_fulfilled(
        self,
        db: AsyncSession,
        integration: Integration,
        order: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Handle orders/fulfilled webhook."""
        shopify_id = str(order.get("id", ""))
        result = await db.execute(
            select(ShopifyTransaction).where(
                ShopifyTransaction.shopify_order_id == shopify_id
            )
        )
        txn = result.scalar_one_or_none()
        if txn:
            txn.fulfillment_status = "fulfilled"
            await db.flush()
        return {"status": "updated", "order_id": shopify_id}

    async def _handle_refund_create(
        self,
        db: AsyncSession,
        integration: Integration,
        refund: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Handle refunds/create webhook.
        Updates the transaction's financial status and adjusts VAT amounts.
        """
        order_id = str(refund.get("order_id", ""))
        result = await db.execute(
            select(ShopifyTransaction).where(
                ShopifyTransaction.shopify_order_id == order_id
            )
        )
        txn = result.scalar_one_or_none()
        if not txn:
            return {"status": "skipped", "reason": "order not found"}

        # Calculate refund amount
        refund_line_items = refund.get("refund_line_items", [])
        transactions = refund.get("transactions", [])

        total_refund = sum(
            Decimal(str(t.get("amount", 0)))
            for t in transactions
            if t.get("kind") == "refund"
        )

        # Determine if full or partial refund
        if total_refund >= Decimal(str(txn.total_price or 0)):
            txn.financial_status = "refunded"
        else:
            txn.financial_status = "partially_refunded"

        await db.flush()
        logger.info(f"Webhook: refund processed for order {order_id}, amount: {total_refund}")
        return {
            "status": "updated",
            "order_id": order_id,
            "refund_amount": str(total_refund),
            "new_status": txn.financial_status,
        }

    async def _handle_app_uninstalled(
        self,
        db: AsyncSession,
        integration: Integration,
        payload: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Handle app/uninstalled — deactivate integration."""
        integration.is_active = False
        integration.access_token = None
        integration.sync_status = "idle"
        await db.flush()
        logger.info(f"Shopify app uninstalled for shop: {integration.shop_domain}")
        return {"status": "deactivated", "shop": integration.shop_domain}

    async def _build_transaction(
        self,
        integration: Integration,
        order: Dict[str, Any],
    ) -> Optional[ShopifyTransaction]:
        """Build a ShopifyTransaction from a Shopify order dict."""
        try:
            shopify_id = str(order["id"])
            currency = order.get("currency", "GBP")

            # Financials
            total_price = Decimal(str(order.get("total_price", "0")))
            subtotal = Decimal(str(order.get("subtotal_price", "0")))
            discount = Decimal(str(order.get("total_discounts", "0")))

            shipping_set = order.get("total_shipping_price_set", {})
            shipping = Decimal(str(
                shipping_set.get("shop_money", {}).get("amount", "0")
            ))

            # VAT from tax lines
            tax_lines = order.get("tax_lines", [])
            vat_amount = sum(
                Decimal(str(t.get("price", "0"))) for t in tax_lines
            )
            vat_rate = Decimal("20.00")
            if tax_lines:
                rate_val = tax_lines[0].get("rate", 0.20)
                vat_rate = (Decimal(str(rate_val)) * 100).quantize(Decimal("0.01"))

            # FX conversion
            total_price_gbp, exchange_rate = await fx_service.convert_to_gbp(
                total_price, currency
            )

            # Classify sale
            classification = sale_classifier.classify_from_order(order)

            # Customer info
            customer = order.get("customer") or {}
            shipping_addr = order.get("shipping_address") or order.get("billing_address") or {}
            customer_name = (
                f"{customer.get('first_name', '')} {customer.get('last_name', '')}".strip()
                or shipping_addr.get("name")
                or None
            )

            # Parse order date
            created_at_str = order.get("created_at", "")
            try:
                order_date = datetime.fromisoformat(
                    created_at_str.replace("Z", "+00:00")
                )
            except Exception:
                order_date = datetime.utcnow()

            return ShopifyTransaction(
                integration_id=integration.id,
                company_id=integration.company_id,
                shopify_order_id=shopify_id,
                shopify_order_number=str(order.get("order_number", "")),
                order_date=order_date,
                customer_name=customer_name,
                customer_email=customer.get("email"),
                customer_country=classification.country_name,
                customer_country_code=classification.country_code,
                subtotal=subtotal,
                shipping=shipping,
                discount=discount,
                total_price=total_price,
                currency=currency,
                exchange_rate=exchange_rate,
                total_price_gbp=total_price_gbp,
                vat_amount=vat_amount,
                vat_rate=vat_rate,
                is_uk_sale=classification.is_uk_sale,
                is_eu_sale=classification.is_eu_sale,
                is_export=classification.is_export,
                financial_status=order.get("financial_status", "paid"),
                fulfillment_status=order.get("fulfillment_status"),
                line_items=order.get("line_items", []),
            )
        except Exception as e:
            logger.error(f"Error building transaction from order {order.get('id')}: {e}")
            return None

    async def register_webhooks(
        self,
        shop: str,
        access_token: str,
        webhook_base_url: str,
    ) -> Dict[str, Any]:
        """
        Register all required webhooks with Shopify.
        Called after OAuth install.
        """
        import httpx

        topics = [
            "orders/create",
            "orders/updated",
            "orders/paid",
            "orders/cancelled",
            "orders/fulfilled",
            "refunds/create",
            "app/uninstalled",
        ]

        registered = []
        failed = []

        async with httpx.AsyncClient(timeout=30.0) as client:
            for topic in topics:
                try:
                    response = await client.post(
                        f"https://{shop}/admin/api/2024-01/webhooks.json",
                        headers={
                            "X-Shopify-Access-Token": access_token,
                            "Content-Type": "application/json",
                        },
                        json={
                            "webhook": {
                                "topic": topic,
                                "address": f"{webhook_base_url}/api/v1/integrations/shopify/webhook",
                                "format": "json",
                            }
                        },
                    )
                    if response.status_code in (200, 201):
                        registered.append(topic)
                        logger.info(f"Registered webhook: {topic} for {shop}")
                    else:
                        failed.append({"topic": topic, "error": response.text})
                        logger.warning(f"Failed to register webhook {topic}: {response.text}")
                except Exception as e:
                    failed.append({"topic": topic, "error": str(e)})

        return {
            "registered": registered,
            "failed": failed,
            "total": len(topics),
        }


shopify_webhook_service = ShopifyWebhookService()