from sqlalchemy import Column, Integer, String, Boolean, DateTime, Text, ForeignKey, Date, Numeric, JSON
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.db.database import Base


class Filing(Base):
    """Tracks all Companies House and HMRC filings."""
    __tablename__ = "filings"

    id = Column(Integer, primary_key=True, index=True)
    company_id = Column(Integer, ForeignKey("companies.id"), nullable=False, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)

    # Filing type
    filing_type = Column(String(50), nullable=False)
    # Types: confirmation_statement, annual_accounts, vat_return, ct600

    # Filing details
    reference_number = Column(String(100), nullable=True)  # CH transaction ID
    made_up_to_date = Column(Date, nullable=True)
    period_start = Column(Date, nullable=True)
    period_end = Column(Date, nullable=True)

    # Status workflow
    status = Column(String(50), default="draft")
    # draft -> pending_payment -> paid -> submitted -> accepted / rejected

    # Filing data (JSON payload sent to CH/HMRC)
    filing_data = Column(JSON, nullable=True)

    # Response from CH/HMRC
    submission_response = Column(JSON, nullable=True)
    transaction_id = Column(String(255), nullable=True)
    barcode = Column(String(100), nullable=True)

    # Dates
    submitted_at = Column(DateTime(timezone=True), nullable=True)
    accepted_at = Column(DateTime(timezone=True), nullable=True)
    rejected_at = Column(DateTime(timezone=True), nullable=True)
    rejection_reason = Column(Text, nullable=True)

    # Payment link
    payment_id = Column(Integer, ForeignKey("payments.id"), nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # Relationships
    company = relationship("Company", back_populates="filings")
    user = relationship("User", back_populates="filings")
    payment = relationship("Payment", back_populates="filings")


class ConfirmationStatement(Base):
    """CS01 - Confirmation Statement specific data."""
    __tablename__ = "confirmation_statements"

    id = Column(Integer, primary_key=True, index=True)
    filing_id = Column(Integer, ForeignKey("filings.id"), nullable=False, unique=True)

    made_up_to_date = Column(Date, nullable=False)
    trading_on_confirmation = Column(Boolean, default=True)

    # Registered office
    registered_office_is_same = Column(Boolean, default=True)

    # SIC codes confirmed
    sic_codes_confirmed = Column(Boolean, default=True)
    sic_codes = Column(JSON, nullable=True)

    # Share capital
    statement_of_capital_confirmed = Column(Boolean, default=True)
    share_capital_data = Column(JSON, nullable=True)

    # Shareholders
    shareholders_data = Column(JSON, nullable=True)

    # PSC (Persons with Significant Control)
    psc_confirmed = Column(Boolean, default=True)
    psc_data = Column(JSON, nullable=True)

    # Directors
    directors_confirmed = Column(Boolean, default=True)
    directors_data = Column(JSON, nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())


class AnnualAccounts(Base):
    """AA - Annual Accounts specific data."""
    __tablename__ = "annual_accounts"

    id = Column(Integer, primary_key=True, index=True)
    filing_id = Column(Integer, ForeignKey("filings.id"), nullable=False, unique=True)

    # Period
    accounts_type = Column(String(50), nullable=True)
    # micro-entity, small, full, dormant

    period_start = Column(Date, nullable=False)
    period_end = Column(Date, nullable=False)

    # Balance sheet
    fixed_assets = Column(Numeric(15, 2), nullable=True)
    current_assets = Column(Numeric(15, 2), nullable=True)
    creditors_within_one_year = Column(Numeric(15, 2), nullable=True)
    net_current_assets = Column(Numeric(15, 2), nullable=True)
    total_assets_less_liabilities = Column(Numeric(15, 2), nullable=True)
    creditors_after_one_year = Column(Numeric(15, 2), nullable=True)
    net_assets = Column(Numeric(15, 2), nullable=True)

    # Capital and reserves
    called_up_share_capital = Column(Numeric(15, 2), nullable=True)
    profit_loss_account = Column(Numeric(15, 2), nullable=True)
    shareholders_funds = Column(Numeric(15, 2), nullable=True)

    # P&L (for small/full accounts)
    turnover = Column(Numeric(15, 2), nullable=True)
    gross_profit = Column(Numeric(15, 2), nullable=True)
    operating_profit = Column(Numeric(15, 2), nullable=True)
    profit_before_tax = Column(Numeric(15, 2), nullable=True)
    tax_on_profit = Column(Numeric(15, 2), nullable=True)
    profit_after_tax = Column(Numeric(15, 2), nullable=True)

    # Audit
    audit_exempt = Column(Boolean, default=True)
    audit_exemption_statement = Column(Text, nullable=True)

    # Director approval
    director_name = Column(String(255), nullable=True)
    approved_date = Column(Date, nullable=True)

    # Opt out of P&L publication (new ECCT Act 2023 rule from April 2028)
    opt_out_pl_publication = Column(Boolean, default=False)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())