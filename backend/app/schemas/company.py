from pydantic import BaseModel, validator
from typing import Optional, List
from datetime import date, datetime
from decimal import Decimal


class CompanySearchResult(BaseModel):
    company_number: str
    company_name: str
    company_status: Optional[str]
    company_type: Optional[str]
    date_of_creation: Optional[str]
    registered_office_address: Optional[dict]
    sic_codes: Optional[List[str]]


class CompanyDetail(BaseModel):
    company_number: str
    company_name: str
    company_status: Optional[str]
    company_type: Optional[str]
    date_of_creation: Optional[str]
    date_of_cessation: Optional[str]
    registered_office_address: Optional[dict]
    sic_codes: Optional[List[str]]
    accounts: Optional[dict]
    confirmation_statement: Optional[dict]
    officers: Optional[List[dict]]
    persons_with_significant_control: Optional[List[dict]]
    filing_history: Optional[List[dict]]


class CompanyCreate(BaseModel):
    company_number: str
    vat_number: Optional[str] = None
    utr: Optional[str] = None
    vat_scheme: Optional[str] = None
    vat_flat_rate_percentage: Optional[Decimal] = None


class CompanyUpdate(BaseModel):
    vat_number: Optional[str] = None
    utr: Optional[str] = None
    vat_scheme: Optional[str] = None
    vat_flat_rate_percentage: Optional[Decimal] = None
    is_vat_registered: Optional[bool] = None
    is_dormant: Optional[bool] = None


class CompanyOut(BaseModel):
    id: int
    tenant_id: int
    company_number: str
    company_name: str
    company_type: Optional[str]
    company_status: Optional[str]
    date_of_creation: Optional[date]
    registered_address_line1: Optional[str]
    registered_address_city: Optional[str]
    registered_address_postcode: Optional[str]
    vat_number: Optional[str]
    utr: Optional[str]
    is_vat_registered: bool
    is_dormant: bool
    next_confirmation_statement_due: Optional[date]
    next_accounts_due: Optional[date]
    last_synced_at: Optional[datetime]
    created_at: datetime

    class Config:
        from_attributes = True


class VATReturnCreate(BaseModel):
    period_key: str
    period_start: date
    period_end: date
    due_date: Optional[date] = None
    box1_vat_due_sales: Decimal = Decimal("0.00")
    box2_vat_due_acquisitions: Decimal = Decimal("0.00")
    box3_total_vat_due: Decimal = Decimal("0.00")
    box4_vat_reclaimed: Decimal = Decimal("0.00")
    box5_net_vat_due: Decimal = Decimal("0.00")
    box6_total_sales: Decimal = Decimal("0.00")
    box7_total_purchases: Decimal = Decimal("0.00")
    box8_total_supplies: Decimal = Decimal("0.00")
    box9_total_acquisitions: Decimal = Decimal("0.00")
    source: Optional[str] = "manual"
    notes: Optional[str] = None

    @validator("box3_total_vat_due", always=True)
    def calc_box3(cls, v, values):
        b1 = values.get("box1_vat_due_sales", Decimal("0"))
        b2 = values.get("box2_vat_due_acquisitions", Decimal("0"))
        return b1 + b2

    @validator("box5_net_vat_due", always=True)
    def calc_box5(cls, v, values):
        b3 = values.get("box3_total_vat_due", Decimal("0"))
        b4 = values.get("box4_vat_reclaimed", Decimal("0"))
        return abs(b3 - b4)


class VATReturnOut(BaseModel):
    id: int
    company_id: int
    period_key: str
    period_start: date
    period_end: date
    due_date: Optional[date]
    box1_vat_due_sales: Decimal
    box2_vat_due_acquisitions: Decimal
    box3_total_vat_due: Decimal
    box4_vat_reclaimed: Decimal
    box5_net_vat_due: Decimal
    box6_total_sales: Decimal
    box7_total_purchases: Decimal
    box8_total_supplies: Decimal
    box9_total_acquisitions: Decimal
    status: str
    submitted_at: Optional[datetime]
    hmrc_receipt_id: Optional[str]
    source: Optional[str]
    notes: Optional[str]
    created_at: datetime

    class Config:
        from_attributes = True