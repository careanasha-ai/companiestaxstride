from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import Optional, List
from datetime import datetime

from app.db.database import get_db
from app.db.models.user import User
from app.db.models.company import Company
from app.db.models.filing import Filing, ConfirmationStatement, AnnualAccounts
from app.db.models.payment import Payment
from app.core.dependencies import get_current_user
from app.schemas.filing import (
    ConfirmationStatementCreate, AnnualAccountsCreate,
    FilingOut, FilingListItem, FilingStatusUpdate
)

router = APIRouter(prefix="/filings", tags=["Filings"])


def _check_company_ownership(company: Optional[Company], tenant_id: int):
    if not company or company.tenant_id != tenant_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Company not found")


async def _get_company(db: AsyncSession, company_id: int, tenant_id: int) -> Company:
    result = await db.execute(
        select(Company).where(
            Company.id == company_id,
            Company.tenant_id == tenant_id,
            Company.is_active == True,
        )
    )
    company = result.scalar_one_or_none()
    if not company:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Company not found")
    return company


# ─── LIST FILINGS ─────────────────────────────────────────────────────────────

@router.get("/", response_model=List[FilingListItem])
async def list_filings(
    company_id: Optional[int] = Query(None),
    filing_type: Optional[str] = Query(None),
    status_filter: Optional[str] = Query(None, alias="status"),
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """List all filings for the current user's tenant."""
    query = (
        select(Filing, Company.company_name, Company.company_number)
        .join(Company, Filing.company_id == Company.id)
        .where(Company.tenant_id == current_user.tenant_id)
    )
    if company_id:
        query = query.where(Filing.company_id == company_id)
    if filing_type:
        query = query.where(Filing.filing_type == filing_type)
    if status_filter:
        query = query.where(Filing.status == status_filter)

    query = query.order_by(Filing.created_at.desc())
    query = query.offset((page - 1) * per_page).limit(per_page)

    result = await db.execute(query)
    rows = result.all()

    items = []
    for filing, company_name, company_number in rows:
        item = FilingListItem.model_validate(filing)
        item.company_name = company_name
        item.company_number = company_number
        items.append(item)
    return items


@router.get("/{filing_id}", response_model=FilingOut)
async def get_filing(
    filing_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get a specific filing."""
    result = await db.execute(
        select(Filing)
        .join(Company, Filing.company_id == Company.id)
        .where(Filing.id == filing_id, Company.tenant_id == current_user.tenant_id)
    )
    filing = result.scalar_one_or_none()
    if not filing:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Filing not found")
    return FilingOut.model_validate(filing)


# ─── CONFIRMATION STATEMENT ───────────────────────────────────────────────────

@router.post("/confirmation-statement", response_model=FilingOut, status_code=status.HTTP_201_CREATED)
async def create_confirmation_statement(
    payload: ConfirmationStatementCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Create a Confirmation Statement (CS01) draft.
    Payment required before submission.
    """
    company = await _get_company(db, payload.company_id, current_user.tenant_id)

    filing = Filing(
        company_id=company.id,
        user_id=current_user.id,
        filing_type="confirmation_statement",
        made_up_to_date=payload.made_up_to_date,
        status="draft",
        filing_data={
            "made_up_to_date": payload.made_up_to_date.isoformat(),
            "trading_on_confirmation": payload.trading_on_confirmation,
        },
    )
    db.add(filing)
    await db.flush()

    cs = ConfirmationStatement(
        filing_id=filing.id,
        made_up_to_date=payload.made_up_to_date,
        trading_on_confirmation=payload.trading_on_confirmation,
        registered_office_is_same=payload.registered_office_is_same,
        sic_codes_confirmed=payload.sic_codes_confirmed,
        sic_codes=payload.sic_codes,
        statement_of_capital_confirmed=payload.statement_of_capital_confirmed,
        share_capital_data=payload.share_capital_data,
        shareholders_data=payload.shareholders_data,
        psc_confirmed=payload.psc_confirmed,
        psc_data=payload.psc_data,
        directors_confirmed=payload.directors_confirmed,
        directors_data=payload.directors_data,
    )
    db.add(cs)
    await db.flush()
    await db.refresh(filing)
    return FilingOut.model_validate(filing)


@router.post("/confirmation-statement/{filing_id}/submit", response_model=FilingOut)
async def submit_confirmation_statement(
    filing_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Submit a paid Confirmation Statement to Companies House.
    Filing must be in 'paid' status.
    """
    result = await db.execute(
        select(Filing)
        .join(Company, Filing.company_id == Company.id)
        .where(
            Filing.id == filing_id,
            Filing.filing_type == "confirmation_statement",
            Company.tenant_id == current_user.tenant_id,
        )
    )
    filing = result.scalar_one_or_none()
    if not filing:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Filing not found")
    if filing.status != "paid":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Filing must be paid before submission. Current status: {filing.status}",
        )

    # TODO: Integrate with Companies House filing API (WebFiling / XBRL)
    # For now, mark as submitted with a placeholder transaction ID
    import secrets
    filing.status = "submitted"
    filing.submitted_at = datetime.utcnow()
    filing.transaction_id = f"CH-{secrets.token_hex(8).upper()}"
    await db.flush()
    await db.refresh(filing)
    return FilingOut.model_validate(filing)


# ─── ANNUAL ACCOUNTS ──────────────────────────────────────────────────────────

@router.post("/annual-accounts", response_model=FilingOut, status_code=status.HTTP_201_CREATED)
async def create_annual_accounts(
    payload: AnnualAccountsCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Create an Annual Accounts (AA) draft.
    Payment required before submission.
    """
    company = await _get_company(db, payload.company_id, current_user.tenant_id)

    filing = Filing(
        company_id=company.id,
        user_id=current_user.id,
        filing_type="annual_accounts",
        period_start=payload.period_start,
        period_end=payload.period_end,
        status="draft",
        filing_data={
            "accounts_type": payload.accounts_type,
            "period_start": payload.period_start.isoformat(),
            "period_end": payload.period_end.isoformat(),
            "opt_out_pl_publication": payload.opt_out_pl_publication,
        },
    )
    db.add(filing)
    await db.flush()

    aa = AnnualAccounts(
        filing_id=filing.id,
        accounts_type=payload.accounts_type,
        period_start=payload.period_start,
        period_end=payload.period_end,
        fixed_assets=payload.fixed_assets,
        current_assets=payload.current_assets,
        creditors_within_one_year=payload.creditors_within_one_year,
        net_current_assets=payload.net_current_assets,
        total_assets_less_liabilities=payload.total_assets_less_liabilities,
        creditors_after_one_year=payload.creditors_after_one_year,
        net_assets=payload.net_assets,
        called_up_share_capital=payload.called_up_share_capital,
        profit_loss_account=payload.profit_loss_account,
        shareholders_funds=payload.shareholders_funds,
        turnover=payload.turnover,
        gross_profit=payload.gross_profit,
        operating_profit=payload.operating_profit,
        profit_before_tax=payload.profit_before_tax,
        tax_on_profit=payload.tax_on_profit,
        profit_after_tax=payload.profit_after_tax,
        audit_exempt=payload.audit_exempt,
        audit_exemption_statement=payload.audit_exemption_statement,
        director_name=payload.director_name,
        approved_date=payload.approved_date,
        opt_out_pl_publication=payload.opt_out_pl_publication,
    )
    db.add(aa)
    await db.flush()
    await db.refresh(filing)
    return FilingOut.model_validate(filing)


@router.post("/annual-accounts/{filing_id}/submit", response_model=FilingOut)
async def submit_annual_accounts(
    filing_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Submit paid Annual Accounts to Companies House."""
    result = await db.execute(
        select(Filing)
        .join(Company, Filing.company_id == Company.id)
        .where(
            Filing.id == filing_id,
            Filing.filing_type == "annual_accounts",
            Company.tenant_id == current_user.tenant_id,
        )
    )
    filing = result.scalar_one_or_none()
    if not filing:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Filing not found")
    if filing.status != "paid":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Filing must be paid before submission. Current status: {filing.status}",
        )

    import secrets
    filing.status = "submitted"
    filing.submitted_at = datetime.utcnow()
    filing.transaction_id = f"CH-AA-{secrets.token_hex(8).upper()}"
    await db.flush()
    await db.refresh(filing)
    return FilingOut.model_validate(filing)


# ─── FILING DEADLINES DASHBOARD ───────────────────────────────────────────────

@router.get("/deadlines/upcoming")
async def get_upcoming_deadlines(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get upcoming filing deadlines for all companies in the tenant."""
    from datetime import date, timedelta
    today = date.today()
    in_90_days = today + timedelta(days=90)

    result = await db.execute(
        select(Company).where(
            Company.tenant_id == current_user.tenant_id,
            Company.is_active == True,
        )
    )
    companies = result.scalars().all()

    deadlines = []
    for company in companies:
        if company.next_confirmation_statement_due:
            days_left = (company.next_confirmation_statement_due - today).days
            deadlines.append({
                "company_id": company.id,
                "company_name": company.company_name,
                "company_number": company.company_number,
                "filing_type": "confirmation_statement",
                "due_date": company.next_confirmation_statement_due.isoformat(),
                "days_remaining": days_left,
                "is_overdue": days_left < 0,
                "is_urgent": 0 <= days_left <= 30,
            })
        if company.next_accounts_due:
            days_left = (company.next_accounts_due - today).days
            deadlines.append({
                "company_id": company.id,
                "company_name": company.company_name,
                "company_number": company.company_number,
                "filing_type": "annual_accounts",
                "due_date": company.next_accounts_due.isoformat(),
                "days_remaining": days_left,
                "is_overdue": days_left < 0,
                "is_urgent": 0 <= days_left <= 30,
            })

    deadlines.sort(key=lambda x: x["days_remaining"])
    return {"deadlines": deadlines, "total": len(deadlines)}