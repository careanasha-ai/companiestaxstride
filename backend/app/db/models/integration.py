from sqlalchemy import Column, Integer, String, Boolean, DateTime, Text, ForeignKey, JSON, Numeric
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.db.database import Base


class Integration(Base):
    """Third-party integrations per tenant (Shopify, Xero, etc.)."""
    __tablename__ = "integrations"

    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id"), nullable=False, index=True)
    company_id = Column(Integer, ForeignKey("companies.id"), nullable=True, index=True)

    # Integration type
    provider = Column(String(50), nullable=False)
    # shopify, ebay, woocommerce, xero, quickbooks, sage

    # OAuth tokens
    access_token = Column(Text, nullable=True)
    refresh_token = Column(Text, nullable=True)
    token_expires_at = Column(DateTime(timezone=True), nullable=True)
    token_scope = Column(Text, nullable=True)

    # Provider-specific identifiers
    shop_domain = Column(String(255), nullable=True)       # Shopify: mystore.myshopify.com
    shop_name = Column(String(255), nullable=True)
    external_account_id = Column(String(255), nullable=True)  # Xero org ID, QB realm ID

    # Sync settings
    is_active = Column(Boolean, default=True)
    auto_sync = Column(Boolean, default=True)
    sync_from_date = Column(DateTime(timezone=True), nullable=True)
    last_synced_at = Column(DateTime(timezone=True), nullable=True)
    sync_status = Column(String(50), default="idle")  # idle, syncing, error
    sync_error = Column(Text, nullable=True)

    # Config
    config = Column(JSON, nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # Relationships
    tenant = relationship("Tenant", back_populates="integrations")
    transactions = relationship("ShopifyTransaction", back_populates="integration", cascade="all, delete-orphan")


class ShopifyTransaction(Base):
    """Imported Shopify orders/transactions for VAT calculation."""
    __tablename__ = "shopify_transactions"

    id = Column(Integer, primary_key=True, index=True)
    integration_id = Column(Integer, ForeignKey("integrations.id"), nullable=False, index=True)
    company_id = Column(Integer, ForeignKey("companies.id"), nullable=False, index=True)

    # Shopify order data
    shopify_order_id = Column(String(100), nullable=False, unique=True)
    shopify_order_number = Column(String(50), nullable=True)
    order_date = Column(DateTime(timezone=True), nullable=False)

    # Customer
    customer_name = Column(String(255), nullable=True)
    customer_email = Column(String(255), nullable=True)
    customer_country = Column(String(100), nullable=True)
    customer_country_code = Column(String(10), nullable=True)

    # Financials
    subtotal = Column(Numeric(15, 2), default=0)
    shipping = Column(Numeric(15, 2), default=0)
    discount = Column(Numeric(15, 2), default=0)
    total_price = Column(Numeric(15, 2), default=0)
    currency = Column(String(10), default="GBP")
    exchange_rate = Column(Numeric(10, 6), default=1)
    total_price_gbp = Column(Numeric(15, 2), default=0)

    # VAT
    vat_amount = Column(Numeric(15, 2), default=0)
    vat_rate = Column(Numeric(5, 2), default=20)
    is_uk_sale = Column(Boolean, default=True)
    is_eu_sale = Column(Boolean, default=False)
    is_export = Column(Boolean, default=False)

    # Status
    financial_status = Column(String(50), nullable=True)  # paid, refunded, partially_refunded
    fulfillment_status = Column(String(50), nullable=True)

    # Line items
    line_items = Column(JSON, nullable=True)

    # VAT period assignment
    vat_period_key = Column(String(20), nullable=True)
    vat_return_id = Column(Integer, ForeignKey("vat_returns.id"), nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # Relationships
    integration = relationship("Integration", back_populates="transactions")