import hmac
import hashlib
import base64
import httpx
from typing import Optional, Dict, Any, List
from datetime import datetime, date
from decimal import Decimal
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_
from app.core.config import settings
from app.db.models.integration import Integration, ShopifyTransaction
from app.db.models.company import Company
from app.services.shopify.classifier import sale_classifier
from app.services.shopify.fx_service import fx_service
from loguru import logger


class ShopifyService:

    def _get_install_url(self, shop: str, state: str) -> str:
        """Generate Shopify OAuth install URL."""
        scopes = settings.SHOPIFY_SCOPES
        redirect_uri = settings.SHOPIFY_REDIRECT_URI
        client_id = settings.SHOPIFY_API_KEY
        return (
            f"https://{shop}/admin/oauth/authorize"
            f"?client_id={client_id}"
            f"&scope={scopes}"
            f"&redirect_uri={redirect_uri}"
            f"&state={state}"
        )

    def _verify_hmac(self, params: Dict[str, str]) -> bool:
        """Verify Shopify HMAC signature on OAuth callback."""
        hmac_value = params.pop("hmac", "")
        sorted_params = "&".join(
            f"{k}={v}" for k, v in sorted(params.items())
        )
        digest = hmac.new(
            settings.SHOPIFY_API_SECRET.encode("utf-8"),
            sorted_params.encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()
        return hmac.compare_digest(digest, hmac_value)

    async def exchange_token(self, shop: str, code: str) -> str:
        """Exchange OAuth code for permanent access token."""
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"https://{shop}/admin/oauth/access_token",
                json={
                    "client_id": settings.SHOPIFY_API_KEY,
                    "client_secret": settings.SHOPIFY_API_SECRET,
                    "code": code,
                },
            )
            response.raise_for_status()
            return response.json()["access_token"]

    async def get_shop_info(self, shop: str, access_token: str) -> Dict[str, Any]:
        """Get Shopify shop details."""
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"https://{shop}/admin/api/2024-01/shop.json",
                headers={"X-Shopify-Access-Token": access_token},
            )
            response.raise_for_status()
            return response.json().get("shop", {})

    async def install(
        self,
        db: AsyncSession,
        tenant_id: int,
        company_id: int,
        shop: str,
        code: str,
    ) -> Integration:
        """Complete Shopify OAuth and save integration."""
        access_token = await self.exchange_token(shop, code)
        shop_info = await self.get_shop_info(shop, access_token)

        # Check if integration already exists
        result = await db.execute(
            select(Integration).where(
                and_(
                    Integration.tenant_id == tenant_id,
                    Integration.provider == "shopify",
                    Integration.shop_domain == shop,
                )
            )
        )
        integration = result.scalar_one_or_none()

        if integration:
            integration.access_token = access_token
            integration.is_active = True
            integration.sync_status = "idle"
        else:
            integration = Integration(
                tenant_id=tenant_id,
                company_id=company_id,
                provider="shopify",
                access_token=access_token,
                shop_domain=shop,
                shop_name=shop_info.get("name"),
                is_active=True,
                auto_sync=True,
                config={
                    "currency": shop_info.get("currency"),
                    "timezone": shop_info.get("iana_timezone"),
                    "country_code": shop_info.get("country_code"),
                },
            )
            db.add(integration)

        await db.flush()
        await db.refresh(integration)
        logger.info(f"Shopify integration installed for tenant {tenant_id}: {shop}")
        return integration

    async def sync_orders(
        self,
        db: AsyncSession,
        integration: Integration,
        since_date: Optional[date] = None,
        limit: int = 250,
    ) -> Dict[str, Any]:
        """Sync Shopify orders and calculate VAT."""
        shop = integration.shop_domain
        token = integration.access_token

        params = {
            "limit": limit,
            "status": "any",
            "financial_status": "paid,partially_refunded",
        }
        if since_date:
            params["created_at_min"] = since_date.isoformat()
        elif integration.last_synced_at:
            params["created_at_min"] = integration.last_synced_at.isoformat()

        orders_synced = 0
        orders_skipped = 0
        total_sales = Decimal("0")
        total_vat = Decimal("0")
        errors = []

        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.get(
                f"https://{shop}/admin/api/2024-01/orders.json",
                headers={"X-Shopify-Access-Token": token},
                params=params,
            )
            response.raise_for_status()
            orders = response.json().get("orders", [])

        for order in orders:
            try:
                shopify_id = str(order["id"])

                # Skip if already imported
                existing = await db.execute(
                    select(ShopifyTransaction).where(
                        ShopifyTransaction.shopify_order_id == shopify_id
                    )
                )
                if existing.scalar_one_or_none():
                    orders_skipped += 1
                    continue

                # Parse financials
                currency = order.get("currency", "GBP")
                total_price = Decimal(str(order.get("total_price", "0")))
                subtotal = Decimal(str(order.get("subtotal_price", "0")))
                shipping = Decimal(str(order.get("total_shipping_price_set", {})
                                   .get("shop_money", {}).get("amount", "0")))
                discount = Decimal(str(order.get("total_discounts", "0")))

                # VAT from tax lines
                tax_lines = order.get("tax_lines", [])
                vat_amount = sum(
                    Decimal(str(t.get("price", "0"))) for t in tax_lines
                )
                vat_rate = Decimal("20.00")
                if tax_lines:
                    vat_rate = (Decimal(str(tax_lines[0].get("rate", 0.20))) * 100).quantize(Decimal("0.01"))

                # Currency conversion using live FX service
                total_price_gbp, exchange_rate = await fx_service.convert_to_gbp(
                    total_price, currency
                )

                # Classify sale using classifier
                classification = sale_classifier.classify_from_order(order)

                # Customer info
                shipping_addr = order.get("shipping_address") or order.get("billing_address") or {}
                customer = order.get("customer") or {}
                customer_name = (
                    f"{customer.get('first_name', '')} {customer.get('last_name', '')}".strip()
                    or shipping_addr.get("name")
                    or None
                )

                # Parse order date
                created_at_str = order.get("created_at", "")
                try:
                    order_date = datetime.fromisoformat(created_at_str.replace("Z", "+00:00"))
                except Exception:
                    order_date = datetime.utcnow()

                transaction = ShopifyTransaction(
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
                    financial_status=order.get("financial_status"),
                    fulfillment_status=order.get("fulfillment_status"),
                    line_items=order.get("line_items", []),
                )
                db.add(transaction)
                orders_synced += 1
                total_sales += total_price_gbp
                total_vat += vat_amount

            except Exception as e:
                logger.error(f"Error processing Shopify order {order.get('id')}: {e}")
                errors.append(str(e))

        # Update integration sync timestamp
        integration.last_synced_at = datetime.utcnow()
        integration.sync_status = "idle"
        await db.flush()

        return {
            "orders_synced": orders_synced,
            "orders_skipped": orders_skipped,
            "total_sales_gbp": total_sales,
            "total_vat_gbp": total_vat,
            "errors": errors,
        }

    async def get_vat_summary(
        self,
        db: AsyncSession,
        integration_id: int,
        period_start: date,
        period_end: date,
    ) -> Dict[str, Any]:
        """Summarise Shopify sales for a VAT period."""
        from sqlalchemy import func, and_

        result = await db.execute(
            select(
                func.count(ShopifyTransaction.id).label("count"),
                func.sum(ShopifyTransaction.total_price_gbp).label("total_sales"),
                func.sum(ShopifyTransaction.vat_amount).label("total_vat"),
                func.sum(
                    ShopifyTransaction.total_price_gbp.filter(
                        ShopifyTransaction.is_uk_sale == True
                    )
                ).label("uk_sales"),
                func.sum(
                    ShopifyTransaction.total_price_gbp.filter(
                        ShopifyTransaction.is_eu_sale == True
                    )
                ).label("eu_sales"),
                func.sum(
                    ShopifyTransaction.total_price_gbp.filter(
                        ShopifyTransaction.is_export == True
                    )
                ).label("export_sales"),
            ).where(
                and_(
                    ShopifyTransaction.integration_id == integration_id,
                    ShopifyTransaction.order_date >= datetime.combine(period_start, datetime.min.time()),
                    ShopifyTransaction.order_date <= datetime.combine(period_end, datetime.max.time()),
                )
            )
        )
        row = result.one()

        total_sales = Decimal(str(row.total_sales or 0))
        total_vat = Decimal(str(row.total_vat or 0))
        uk_sales = Decimal(str(row.uk_sales or 0))
        eu_sales = Decimal(str(row.eu_sales or 0))
        export_sales = Decimal(str(row.export_sales or 0))

        return {
            "period_start": period_start.isoformat(),
            "period_end": period_end.isoformat(),
            "total_sales_gbp": total_sales,
            "total_vat_collected": total_vat,
            "uk_sales": uk_sales,
            "eu_sales": eu_sales,
            "export_sales": export_sales,
            "suggested_box1": total_vat,
            "suggested_box6": total_sales,
            "transaction_count": row.count or 0,
        }

    


shopify_service = ShopifyService()