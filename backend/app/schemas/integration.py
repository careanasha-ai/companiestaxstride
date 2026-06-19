from pydantic import BaseModel
from typing import Optional, List, Dict, Any
from datetime import datetime
from decimal import Decimal


class ShopifyInstallRequest(BaseModel):
    shop: str  # mystore.myshopify.com
    company_id: int


class ShopifyCallbackRequest(BaseModel):
    code: str
    shop: str
    state: str
    hmac: str
    timestamp: str


class IntegrationOut(BaseModel):
    id: int
    tenant_id: int
    company_id: Optional[int]
    provider: str
    shop_domain: Optional[str]
    shop_name: Optional[str]
    is_active: bool
    auto_sync: bool
    last_synced_at: Optional[datetime]
    sync_status: str
    sync_error: Optional[str]
    created_at: datetime

    class Config:
        from_attributes = True


class ShopifyTransactionOut(BaseModel):
    id: int
    shopify_order_id: str
    shopify_order_number: Optional[str]
    order_date: datetime
    customer_name: Optional[str]
    customer_country: Optional[str]
    subtotal: Decimal
    shipping: Decimal
    discount: Decimal
    total_price: Decimal
    currency: str
    total_price_gbp: Decimal
    vat_amount: Decimal
    vat_rate: Decimal
    is_uk_sale: bool
    is_eu_sale: bool
    is_export: bool
    financial_status: Optional[str]
    vat_period_key: Optional[str]

    class Config:
        from_attributes = True


class ShopifySyncResult(BaseModel):
    orders_synced: int
    orders_skipped: int
    total_sales_gbp: Decimal
    total_vat_gbp: Decimal
    date_range_start: Optional[str]
    date_range_end: Optional[str]
    errors: List[str] = []


class VATSummaryFromShopify(BaseModel):
    period_start: str
    period_end: str
    total_sales_gbp: Decimal
    total_vat_collected: Decimal
    uk_sales: Decimal
    eu_sales: Decimal
    export_sales: Decimal
    suggested_box1: Decimal
    suggested_box6: Decimal
    transaction_count: int