from pydantic import BaseModel, validator
from typing import Optional, List, Dict, Any
from datetime import date, datetime
from decimal import Decimal


class ConfirmationStatementCreate(BaseModel):
    company_id: int
    made_up_to_date: date
    trading_on_confirmation: bool = True
    registered_office_is_same: bool = True
    sic_codes_confirmed: bool = True
    sic_codes: Optional[List[str]] = None
    statement_of_capital_confirmed: bool = True
    share_capital_data: Optional[Dict[str, Any]] = None
    shareholders_data: Optional[List[Dict[str, Any]]] = None
    psc_confirmed: bool = True
    psc_data: Optional[List[Dict[str, Any]]] = None
    directors_confirmed: bool = True
    directors_data: Optional[List[Dict[str, Any]]] = None


class AnnualAccountsCreate(BaseModel):
    company_id: int
    accounts_type: str  # micro-entity, small, full, dormant
    period_start: date
    period_end: date

    # Balance sheet
    fixed_assets: Optional[Decimal] = None
    current_assets: Optional[Decimal] = None
    creditors_within_one_year: Optional[Decimal] = None
    net_current_assets: Optional[Decimal] = None
    total_assets_less_liabilities: Optional[Decimal] = None
    creditors_after_one_year: Optional[Decimal] = None
    net_assets: Optional[Decimal] = None

    # Capital and reserves
    called_up_share_capital: Optional[Decimal] = None
    profit_loss_account: Optional[Decimal] = None
    shareholders_funds: Optional[Decimal] = None

    # P&L
    turnover: Optional[Decimal] = None
    gross_profit: Optional[Decimal] = None
    operating_profit: Optional[Decimal] = None
    profit_before_tax: Optional[Decimal] = None
    tax_on_profit: Optional[Decimal] = None
    profit_after_tax: Optional[Decimal] = None

    # Audit
    audit_exempt: bool = True
    audit_exemption_statement: Optional[str] = None

    # Director approval
    director_name: Optional[str] = None
    approved_date: Optional[date] = None

    # ECCT Act 2023 - opt out of P&L publication
    opt_out_pl_publication: bool = False

    @validator("accounts_type")
    def validate_accounts_type(cls, v):
        allowed = ["micro-entity", "small", "full", "dormant"]
        if v not in allowed:
            raise ValueError(f"accounts_type must be one of: {allowed}")
        return v


class FilingOut(BaseModel):
    id: int
    company_id: int
    user_id: int
    filing_type: str
    reference_number: Optional[str]
    made_up_to_date: Optional[date]
    period_start: Optional[date]
    period_end: Optional[date]
    status: str
    transaction_id: Optional[str]
    barcode: Optional[str]
    submitted_at: Optional[datetime]
    accepted_at: Optional[datetime]
    rejected_at: Optional[datetime]
    rejection_reason: Optional[str]
    payment_id: Optional[int]
    created_at: datetime

    class Config:
        from_attributes = True


class FilingListItem(BaseModel):
    id: int
    filing_type: str
    status: str
    made_up_to_date: Optional[date]
    period_start: Optional[date]
    period_end: Optional[date]
    submitted_at: Optional[datetime]
    created_at: datetime
    company_name: Optional[str] = None
    company_number: Optional[str] = None

    class Config:
        from_attributes = True


class FilingStatusUpdate(BaseModel):
    status: str
    transaction_id: Optional[str] = None
    barcode: Optional[str] = None
    rejection_reason: Optional[str] = None