from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import Optional, List
from datetime import datetime, date

from app.db.database import get_db
from app.db.models.user import User
from app.db.models.company import Company, VATReturn
from app.core.dependencies import get_current_user
from app.services.vat.hmrc_service import hmrc_vat_service
from app.schemas.company import VATReturnCreate, VATReturnOut

router = APIRouter(prefix="/vat", tags=["VAT"])


async def _get_vat_company(db: AsyncSession, company_id: int, tenant_id: int) -> Company:
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
    if not company.is_vat_registered or not company.vat_number:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Company is not VAT registered. Add a VAT number first.",
        )
    return company


# ─── FREE: VAT NUMBER VALIDATION ─────────────────────────────────────────────

@router.get("/validate/{vat_number}")
async def validate_vat_number(vat_number: str):
    """
    Validate a UK VAT number — FREE, no authentication required.
    Checks format and optionally verifies against HMRC.
    """
    import re
    # UK VAT number format: GB followed by 9 digits, or GB + 12 digits
    clean = vat_number.upper().replace(" ", "").replace("-", "")
    if clean.startswith("GB"):
        clean = clean[2:]

    pattern = r"^\d{9}(\d{3})?$"
    is_valid_format = bool(re.match(pattern, clean))

    return {
        "vat_number": vat_number,
        "normalised": f"GB{clean}",
        "is_valid_format": is_valid_format,
        "message": "Valid UK VAT number format" if is_valid_format else "Invalid VAT number format",
    }


# ─── HMRC OAUTH ───────────────────────────────────────────────────────────────

@router.get("/hmrc/auth-url")
async def get_hmrc_auth_url(
    current_user: User = Depends(get_current_user),
):
    """Get HMRC OAuth2 authorization URL to connect MTD."""
    import secrets
    state = secrets.token_urlsafe(16)
    auth_url = hmrc_vat_service.get_auth_url(state)
    return {"auth_url": auth_url, "state": state}


@router.get("/hmrc/callback")
async def hmrc_oauth_callback(
    code: str,
    state: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Handle HMRC OAuth2 callback and store tokens."""
    try:
        tokens = await hmrc_vat_service.exchange_code(code)
        current_user.hmrc_access_token = tokens.get("access_token")
        current_user.hmrc_refresh_token = tokens.get("refresh_token")
        expires_in = tokens.get("expires_in", 14400)
        from datetime import timedelta
        current_user.hmrc_token_expires = datetime.utcnow() + timedelta(seconds=expires_in)
        await db.flush()
        return {"message": "HMRC account connected successfully"}
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"HMRC OAuth error: {str(e)}",
        )


# ─── VAT OBLIGATIONS (FREE LOOKUP) ───────────────────────────────────────────

@router.get("/obligations/{company_id}")
async def get_vat_obligations(
    company_id: int,
    from_date: Optional[str] = Query(None, description="YYYY-MM-DD"),
    to_date: Optional[str] = Query(None, description="YYYY-MM-DD"),
    obligation_status: Optional[str] = Query(None, alias="status", description="O=open, F=fulfilled"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get VAT return obligations from HMRC — FREE lookup."""
    company = await _get_vat_company(db, company_id, current_user.tenant_id)

    if not current_user.hmrc_access_token:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="HMRC account not connected. Please connect via /vat/hmrc/auth-url",
        )

    try:
        data = await hmrc_vat_service.get_vat_obligations(
            vrn=company.vat_number,
            access_token=current_user.hmrc_access_token,
            from_date=from_date,
            to_date=to_date,
            status=obligation_status,
        )
        return data
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(e))


# ─── VAT RETURNS (CRUD) ───────────────────────────────────────────────────────

@router.get("/returns/{company_id}", response_model=List[VATReturnOut])
async def list_vat_returns(
    company_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """List all VAT returns for a company."""
    company = await _get_vat_company(db, company_id, current_user.tenant_id)
    result = await db.execute(
        select(VATReturn)
        .where(VATReturn.company_id == company.id)
        .order_by(VATReturn.period_end.desc())
    )
    returns = result.scalars().all()
    return [VATReturnOut.model_validate(r) for r in returns]


@router.post("/returns/{company_id}", response_model=VATReturnOut, status_code=status.HTTP_201_CREATED)
async def create_vat_return(
    company_id: int,
    payload: VATReturnCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Create a VAT return draft."""
    company = await _get_vat_company(db, company_id, current_user.tenant_id)

    # Check for duplicate period
    existing = await db.execute(
        select(VATReturn).where(
            VATReturn.company_id == company.id,
            VATReturn.period_key == payload.period_key,
        )
    )
    if existing.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"VAT return for period {payload.period_key} already exists",
        )

    vat_return = VATReturn(
        company_id=company.id,
        **payload.model_dump(),
    )
    db.add(vat_return)
    await db.flush()
    await db.refresh(vat_return)
    return VATReturnOut.model_validate(vat_return)


@router.get("/returns/{company_id}/{return_id}", response_model=VATReturnOut)
async def get_vat_return(
    company_id: int,
    return_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get a specific VAT return."""
    company = await _get_vat_company(db, company_id, current_user.tenant_id)
    result = await db.execute(
        select(VATReturn).where(
            VATReturn.id == return_id,
            VATReturn.company_id == company.id,
        )
    )
    vat_return = result.scalar_one_or_none()
    if not vat_return:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="VAT return not found")
    return VATReturnOut.model_validate(vat_return)


@router.put("/returns/{company_id}/{return_id}", response_model=VATReturnOut)
async def update_vat_return(
    company_id: int,
    return_id: int,
    payload: VATReturnCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Update a draft VAT return."""
    company = await _get_vat_company(db, company_id, current_user.tenant_id)
    result = await db.execute(
        select(VATReturn).where(
            VATReturn.id == return_id,
            VATReturn.company_id == company.id,
        )
    )
    vat_return = result.scalar_one_or_none()
    if not vat_return:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="VAT return not found")
    if vat_return.status != "draft":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only draft VAT returns can be edited",
        )

    for field, value in payload.model_dump().items():
        setattr(vat_return, field, value)

    await db.flush()
    await db.refresh(vat_return)
    return VATReturnOut.model_validate(vat_return)


@router.post("/returns/{company_id}/{return_id}/submit", response_model=VATReturnOut)
async def submit_vat_return(
    company_id: int,
    return_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Submit a paid VAT return to HMRC MTD.
    Return must be in 'paid' status.
    """
    company = await _get_vat_company(db, company_id, current_user.tenant_id)

    result = await db.execute(
        select(VATReturn).where(
            VATReturn.id == return_id,
            VATReturn.company_id == company.id,
        )
    )
    vat_return = result.scalar_one_or_none()
    if not vat_return:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="VAT return not found")
    if vat_return.status != "paid":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"VAT return must be paid before submission. Current status: {vat_return.status}",
        )
    if not current_user.hmrc_access_token:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="HMRC account not connected",
        )

    try:
        await hmrc_vat_service.submit_vat_return(
            vrn=company.vat_number,
            vat_return=vat_return,
            access_token=current_user.hmrc_access_token,
        )
        await db.flush()
        await db.refresh(vat_return)
        return VATReturnOut.model_validate(vat_return)
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(e))


# ─── VAT LIABILITIES & PAYMENTS (FREE LOOKUP) ────────────────────────────────

@router.get("/liabilities/{company_id}")
async def get_vat_liabilities(
    company_id: int,
    from_date: str = Query(..., description="YYYY-MM-DD"),
    to_date: str = Query(..., description="YYYY-MM-DD"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get VAT liabilities from HMRC — FREE lookup."""
    company = await _get_vat_company(db, company_id, current_user.tenant_id)
    if not current_user.hmrc_access_token:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="HMRC not connected")
    try:
        return await hmrc_vat_service.get_vat_liabilities(
            company.vat_number, from_date, to_date, current_user.hmrc_access_token
        )
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(e))


@router.get("/payments/{company_id}")
async def get_vat_payments(
    company_id: int,
    from_date: str = Query(..., description="YYYY-MM-DD"),
    to_date: str = Query(..., description="YYYY-MM-DD"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get VAT payments made to HMRC — FREE lookup."""
    company = await _get_vat_company(db, company_id, current_user.tenant_id)
    if not current_user.hmrc_access_token:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="HMRC not connected")
    try:
        return await hmrc_vat_service.get_vat_payments(
            company.vat_number, from_date, to_date, current_user.hmrc_access_token
        )
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(e))