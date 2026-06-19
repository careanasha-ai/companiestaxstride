from sqlalchemy import Column, Integer, String, Boolean, DateTime, Text, ForeignKey, Date, Numeric
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.db.database import Base


class Company(Base):
    """A UK registered company linked to a tenant."""
    __tablename__ = "companies"

    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id"), nullable=False, index=True)

    # Companies House data
    company_number = Column(String(20), nullable=False, index=True)
    company_name = Column(String(500), nullable=False)
    company_type = Column(String(100), nullable=True)
    company_status = Column(String(100), nullable=True)
    date_of_creation = Column(Date, nullable=True)
    date_of_cessation = Column(Date, nullable=True)

    # Registered address
    registered_address_line1 = Column(String(255), nullable=True)
    registered_address_line2 = Column(String(255), nullable=True)
    registered_address_city = Column(String(100), nullable=True)
    registered_address_county = Column(String(100), nullable=True)
    registered_address_postcode = Column(String(20), nullable=True)
    registered_address_country = Column(String(100), nullable=True)

    # SIC codes
    sic_codes = Column(Text, nullable=True)  # JSON array stored as text

    # Accounting reference date
    accounting_reference_day = Column(Integer, nullable=True)
    accounting_reference_month = Column(Integer, nullable=True)

    # Next filing dates
    next_confirmation_statement_due = Column(Date, nullable=True)
    next_accounts_due = Column(Date, nullable=True)
    last_confirmation_statement_made_up_to = Column(Date, nullable=True)
    last_accounts_made_up_to = Column(Date, nullable=True)

    # VAT
    vat_number = Column(String(50), nullable=True)
    vat_scheme = Column(String(100), nullable=True)  # standard, flat_rate, cash_accounting
    vat_flat_rate_percentage = Column(Numeric(5, 2), nullable=True)

    # Corporation Tax
    utr = Column(String(20), nullable=True)  # Unique Taxpayer Reference

    # Flags
    is_active = Column(Boolean, default=True)
    is_dormant = Column(Boolean, default=False)
    is_vat_registered = Column(Boolean, default=False)

    # Metadata
    last_synced_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # Relationships
    tenant = relationship("Tenant", back_populates="companies")
    filings = relationship("Filing", back_populates="company", cascade="all, delete-orphan")
    vat_returns = relationship("VATReturn", back_populates="company", cascade="all, delete-orphan")


class VATReturn(Base):
    """VAT return periods and data."""
    __tablename__ = "vat_returns"

    id = Column(Integer, primary_key=True, index=True)
    company_id = Column(Integer, ForeignKey("companies.id"), nullable=False, index=True)

    # Period
    period_key = Column(String(20), nullable=False)  # HMRC period key e.g. 23AA
    period_start = Column(Date, nullable=False)
    period_end = Column(Date, nullable=False)
    due_date = Column(Date, nullable=True)

    # VAT boxes (standard 9-box VAT return)
    box1_vat_due_sales = Column(Numeric(15, 2), default=0)         # VAT due on sales
    box2_vat_due_acquisitions = Column(Numeric(15, 2), default=0)  # VAT due on acquisitions
    box3_total_vat_due = Column(Numeric(15, 2), default=0)         # Total VAT due
    box4_vat_reclaimed = Column(Numeric(15, 2), default=0)         # VAT reclaimed
    box5_net_vat_due = Column(Numeric(15, 2), default=0)           # Net VAT payable/reclaimable
    box6_total_sales = Column(Numeric(15, 2), default=0)           # Total value of sales
    box7_total_purchases = Column(Numeric(15, 2), default=0)       # Total value of purchases
    box8_total_supplies = Column(Numeric(15, 2), default=0)        # Total supplies to EC
    box9_total_acquisitions = Column(Numeric(15, 2), default=0)    # Total acquisitions from EC

    # Status
    status = Column(String(50), default="draft")  # draft, submitted, accepted, rejected
    submitted_at = Column(DateTime(timezone=True), nullable=True)
    hmrc_receipt_id = Column(String(255), nullable=True)
    hmrc_correlation_id = Column(String(255), nullable=True)

    # Source data
    source = Column(String(50), nullable=True)  # manual, shopify, xero, quickbooks
    notes = Column(Text, nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # Relationships
    company = relationship("Company", back_populates="vat_returns")