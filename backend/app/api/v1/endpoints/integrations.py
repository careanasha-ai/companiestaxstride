from fastapi import APIRouter, Depends, HTTPException, status, Query, BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_
from typing import Optional, List
from datetime import date

from app.db.database import get_db
from app.db.models.user import User
from app.db.models.integration import Integration, ShopifyTransaction
from app.db.models.company import Company
from app.core.dependencies import get_current_user
from app.core.config import settings
from app.services.shopify.service import shopify_service
from app.schemas.integration import (
    IntegrationOut, ShopifyTransactionOut,
    ShopifySyncResult, VATSummaryFromShopify
)

router = APIRouter(prefix="/integrations", tags=["Integrations"])


# ─── LIST INTEGRATIONS ────────────────────────────────────────────────────────

@router.get("/", response_model=List[IntegrationOut])
async def list_integrations(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """List all integrations for the current tenant."""
    result = await db.execute(
        select(Integration).where(
            Integration.tenant_id == current_user.tenant_id,
            Integration.is_active == True,
        )
    )
    integrations = result.scalars().all()
    return [IntegrationOut.model_validate(i) for i in integrations]


@router.delete("/{integration_id}", status_code=status.HTTP_204_NO_CONTENT)
async def disconnect_integration(
    integration_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Disconnect an integration."""
    result = await db.execute(
        select(Integration).where(
            Integration.id == integration_id,
            Integration.tenant_id == current_user.tenant_id,
        )
    )
    integration = result.scalar_one_or_none()
    if not integration:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Integration not found")
    integration.is_active = False
    integration.access_token = None
    integration.refresh_token = None
    await db.flush()


# ─── SHOPIFY ──────────────────────────────────────────────────────────────────

@router.get("/shopify/install")
async def shopify_install(
    shop: str = Query(..., description="mystore.myshopify.com"),
    company_id: int = Query(...),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Step 1: Initiate Shopify OAuth install.
    Returns the Shopify authorization URL to redirect the user to.
    """
    # Verify company belongs to tenant
    result = await db.execute(
        select(Company).where(
            Company.id == company_id,
            Company.tenant_id == current_user.tenant_id,
        )
    )
    if not result.scalar_one_or_none():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Company not found")

    import secrets
    state = secrets.token_urlsafe(16)
    install_url = shopify_service._get_install_url(shop, state)

    return {
        "install_url": install_url,
        "state": state,
        "message": "Redirect user to install_url to authorize Shopify access",
    }


@router.get("/shopify/callback")
async def shopify_callback(
    code: str = Query(...),
    shop: str = Query(...),
    state: str = Query(...),
    hmac: str = Query(...),
    timestamp: str = Query(...),
    company_id: int = Query(...),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Step 2: Handle Shopify OAuth callback.
    Exchanges code for access token and saves integration.
    """
    # Verify HMAC
    params = {"code": code, "shop": shop, "state": state, "timestamp": timestamp}
    if not shopify_service._verify_hmac({**params, "hmac": hmac}):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid Shopify HMAC signature",
        )

    try:
        integration = await shopify_service.install(
            db=db,
            tenant_id=current_user.tenant_id,
            company_id=company_id,
            shop=shop,
            code=code,
        )
        return {
            "message": f"Shopify store '{integration.shop_name}' connected successfully",
            "integration_id": integration.id,
            "shop": integration.shop_domain,
        }
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.post("/shopify/{integration_id}/sync")
async def sync_shopify_orders(
    integration_id: int,
    background_tasks: BackgroundTasks,
    since_date: Optional[date] = Query(None, description="Sync orders from this date (YYYY-MM-DD)"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Sync Shopify orders for VAT calculation.
    Runs in background for large stores.
    """
    result = await db.execute(
        select(Integration).where(
            Integration.id == integration_id,
            Integration.tenant_id == current_user.tenant_id,
            Integration.provider == "shopify",
            Integration.is_active == True,
        )
    )
    integration = result.scalar_one_or_none()
    if not integration:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Shopify integration not found")

    # Update sync status
    integration.sync_status = "syncing"
    await db.flush()

    try:
        sync_result = await shopify_service.sync_orders(
            db=db,
            integration=integration,
            since_date=since_date,
        )
        return {
            "message": "Sync completed",
            **sync_result,
        }
    except Exception as e:
        integration.sync_status = "error"
        integration.sync_error = str(e)
        await db.flush()
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(e))


@router.get("/shopify/{integration_id}/transactions", response_model=List[ShopifyTransactionOut])
async def list_shopify_transactions(
    integration_id: int,
    page: int = Query(1, ge=1),
    per_page: int = Query(50, ge=1, le=200),
    from_date: Optional[date] = Query(None),
    to_date: Optional[date] = Query(None),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """List synced Shopify transactions."""
    # Verify integration ownership
    int_result = await db.execute(
        select(Integration).where(
            Integration.id == integration_id,
            Integration.tenant_id == current_user.tenant_id,
        )
    )
    if not int_result.scalar_one_or_none():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Integration not found")

    query = select(ShopifyTransaction).where(
        ShopifyTransaction.integration_id == integration_id
    )
    if from_date:
        from datetime import datetime
        query = query.where(
            ShopifyTransaction.order_date >= datetime.combine(from_date, datetime.min.time())
        )
    if to_date:
        from datetime import datetime
        query = query.where(
            ShopifyTransaction.order_date <= datetime.combine(to_date, datetime.max.time())
        )

    query = query.order_by(ShopifyTransaction.order_date.desc())
    query = query.offset((page - 1) * per_page).limit(per_page)

    result = await db.execute(query)
    transactions = result.scalars().all()
    return [ShopifyTransactionOut.model_validate(t) for t in transactions]


@router.get("/shopify/{integration_id}/vat-summary")
async def get_shopify_vat_summary(
    integration_id: int,
    period_start: date = Query(..., description="VAT period start (YYYY-MM-DD)"),
    period_end: date = Query(..., description="VAT period end (YYYY-MM-DD)"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Get VAT summary from Shopify data for a specific period.
    Returns suggested VAT return box values.
    """
    int_result = await db.execute(
        select(Integration).where(
            Integration.id == integration_id,
            Integration.tenant_id == current_user.tenant_id,
        )
    )
    if not int_result.scalar_one_or_none():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Integration not found")

    try:
        summary = await shopify_service.get_vat_summary(
            db=db,
            integration_id=integration_id,
            period_start=period_start,
            period_end=period_end,
        )
        return summary
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))