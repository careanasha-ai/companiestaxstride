from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import Optional, List

from app.db.database import get_db
from app.db.models.user import User
from app.db.models.company import Company
from app.core.dependencies import get_current_user, get_optional_user
from app.services.companies_house.service import companies_house_service
from app.schemas.company import (
    CompanyCreate, CompanyUpdate, CompanyOut,
    CompanySearchResult, CompanyDetail
)

router = APIRouter(prefix="/companies", tags=["Companies House"])


# ─── FREE PUBLIC ENDPOINTS ────────────────────────────────────────────────────

@router.get("/search")
async def search_companies(
    q: str = Query(..., min_length=2, description="Company name or number"),
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    _: Optional[User] = Depends(get_optional_user),
):
    """
    Search Companies House — FREE, no authentication required.
    Returns company name, number, status, address, SIC codes.
    """
    try:
        results = await companies_house_service.search(
            query=q, items_per_page=per_page
        )
        return results
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Companies House API error: {str(e)}",
        )


@router.get("/lookup/{company_number}")
async def get_company_detail(
    company_number: str,
    _: Optional[User] = Depends(get_optional_user),
):
    """
    Get full company profile — FREE, no authentication required.
    Includes officers, PSC, filing history, accounts dates.
    """
    try:
        detail = await companies_house_service.get_company_detail(company_number)
        return detail
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Companies House API error: {str(e)}",
        )


@router.get("/lookup/{company_number}/filing-history")
async def get_filing_history(
    company_number: str,
    category: Optional[str] = Query(None, description="accounts, confirmation-statement, etc."),
    page: int = Query(1, ge=1),
    per_page: int = Query(25, ge=1, le=100),
    _: Optional[User] = Depends(get_optional_user),
):
    """Get filing history — FREE."""
    try:
        data = await companies_house_service.get_filing_history(
            company_number, category=category, page=page, per_page=per_page
        )
        return data
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(e))


@router.get("/lookup/{company_number}/officers")
async def get_officers(
    company_number: str,
    _: Optional[User] = Depends(get_optional_user),
):
    """Get company officers — FREE."""
    from app.services.companies_house.client import companies_house_client
    try:
        return await companies_house_client.get_company_officers(company_number)
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(e))


@router.get("/lookup/{company_number}/psc")
async def get_psc(
    company_number: str,
    _: Optional[User] = Depends(get_optional_user),
):
    """Get Persons with Significant Control — FREE."""
    from app.services.companies_house.client import companies_house_client
    try:
        return await companies_house_client.get_persons_with_significant_control(company_number)
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(e))


# ─── AUTHENTICATED ENDPOINTS (MY COMPANIES) ──────────────────────────────────

@router.get("/my", response_model=List[CompanyOut])
async def list_my_companies(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """List all companies linked to the current user's tenant."""
    result = await db.execute(
        select(Company).where(
            Company.tenant_id == current_user.tenant_id,
            Company.is_active == True,
        )
    )
    companies = result.scalars().all()
    return [CompanyOut.model_validate(c) for c in companies]


@router.post("/my", response_model=CompanyOut, status_code=status.HTTP_201_CREATED)
async def add_company(
    payload: CompanyCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Add a Companies House company to your account."""
    try:
        company = await companies_house_service.add_company_to_tenant(
            db=db,
            tenant_id=current_user.tenant_id,
            payload=payload,
        )
        return CompanyOut.model_validate(company)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )


@router.get("/my/{company_id}", response_model=CompanyOut)
async def get_my_company(
    company_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get a specific company from your account."""
    result = await db.execute(
        select(Company).where(
            Company.id == company_id,
            Company.tenant_id == current_user.tenant_id,
        )
    )
    company = result.scalar_one_or_none()
    if not company:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Company not found")
    return CompanyOut.model_validate(company)


@router.put("/my/{company_id}", response_model=CompanyOut)
async def update_company(
    company_id: int,
    payload: CompanyUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Update company VAT/UTR details."""
    result = await db.execute(
        select(Company).where(
            Company.id == company_id,
            Company.tenant_id == current_user.tenant_id,
        )
    )
    company = result.scalar_one_or_none()
    if not company:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Company not found")

    for field, value in payload.model_dump(exclude_none=True).items():
        setattr(company, field, value)

    if payload.vat_number:
        company.is_vat_registered = True

    await db.flush()
    await db.refresh(company)
    return CompanyOut.model_validate(company)


@router.post("/my/{company_id}/sync", response_model=CompanyOut)
async def sync_company(
    company_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Re-sync company data from Companies House."""
    result = await db.execute(
        select(Company).where(
            Company.id == company_id,
            Company.tenant_id == current_user.tenant_id,
        )
    )
    company = result.scalar_one_or_none()
    if not company:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Company not found")

    try:
        company = await companies_house_service.sync_company(db, company)
        return CompanyOut.model_validate(company)
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(e))


@router.delete("/my/{company_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_company(
    company_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Remove a company from your account (soft delete)."""
    result = await db.execute(
        select(Company).where(
            Company.id == company_id,
            Company.tenant_id == current_user.tenant_id,
        )
    )
    company = result.scalar_one_or_none()
    if not company:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Company not found")
    company.is_active = False
    await db.flush()