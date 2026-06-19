from fastapi import APIRouter, Depends, HTTPException, status, Query, BackgroundTasks, Request, Header
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
from app.services.shopify.webhook_service import shopify_webhook_service
from app.services.shopify.vat_aggregator import vat_aggregator
from app.services.shopify.fx_service import fx_service
from app.schemas.integration import (
    IntegrationOut, ShopifyTransactionOut,
    ShopifySyncResult, VATSummaryFromShopify
)

router = APIRouter(prefix="/integrations", tags=["Integrations"])


# ─── LIST / DISCONNECT ────────────────────────────────────────────────────────

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


# ─── SHOPIFY OAUTH ────────────────────────────────────────────────────────────

@router.get("/shopify/install")
async def shopify_install(
    shop: str = Query(..., description="mystore.myshopify.com"),
    company_id: int = Query(...),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Step 1: Initiate Shopify OAuth install."""
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
    """Step 2: Handle Shopify OAuth callback — exchange code, save integration, register webhooks."""
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

        # Register webhooks for real-time sync
        webhook_base = settings.FRONTEND_URL.replace("3000", "8000")
        webhook_result = await shopify_webhook_service.register_webhooks(
            shop=shop,
            access_token=integration.access_token,
            webhook_base_url=webhook_base,
        )

        return {
            "message": f"Shopify store '{integration.shop_name}' connected successfully",
            "integration_id": integration.id,
            "shop": integration.shop_domain,
            "webhooks_registered": webhook_result.get("registered", []),
            "webhooks_failed": webhook_result.get("failed", []),
        }
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


# ─── SHOPIFY WEBHOOK RECEIVER ─────────────────────────────────────────────────

@router.post("/shopify/webhook")
async def shopify_webhook_receiver(
    request: Request,
    db: AsyncSession = Depends(get_db),
    x_shopify_topic: Optional[str] = Header(None),
    x_shopify_shop_domain: Optional[str] = Header(None),
    x_shopify_hmac_sha256: Optional[str] = Header(None),
):
    """
    Receive real-time Shopify webhook events.
    Handles: orders/create, orders/updated, orders/paid,
             orders/cancelled, refunds/create, app/uninstalled
    """
    if not x_shopify_topic or not x_shopify_shop_domain:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Missing Shopify webhook headers",
        )

    raw_payload = await request.body()
    try:
        import json
        payload = json.loads(raw_payload)
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid JSON payload",
        )

    result = await shopify_webhook_service.handle_event(
        db=db,
        shop_domain=x_shopify_shop_domain,
        topic=x_shopify_topic,
        payload=payload,
        raw_payload=raw_payload,
        hmac_header=x_shopify_hmac_sha256 or "",
    )

    return {"status": "ok", "result": result}


# ─── SHOPIFY SYNC (MANUAL BULK) ───────────────────────────────────────────────

@router.post("/shopify/{integration_id}/sync")
async def sync_shopify_orders(
    integration_id: int,
    since_date: Optional[date] = Query(None, description="Sync orders from this date (YYYY-MM-DD)"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Manually sync Shopify orders (bulk historical import)."""
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

    integration.sync_status = "syncing"
    await db.flush()

    try:
        sync_result = await shopify_service.sync_orders(
            db=db,
            integration=integration,
            since_date=since_date,
        )
        return {"message": "Sync completed", **sync_result}
    except Exception as e:
        integration.sync_status = "error"
        integration.sync_error = str(e)
        await db.flush()
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(e))


# ─── TRANSACTIONS ─────────────────────────────────────────────────────────────

@router.get("/shopify/{integration_id}/transactions", response_model=List[ShopifyTransactionOut])
async def list_shopify_transactions(
    integration_id: int,
    page: int = Query(1, ge=1),
    per_page: int = Query(50, ge=1, le=200),
    from_date: Optional[date] = Query(None),
    to_date: Optional[date] = Query(None),
    sale_type: Optional[str] = Query(None, description="uk, eu, export"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """List synced Shopify transactions with filtering."""
    int_result = await db.execute(
        select(Integration).where(
            Integration.id == integration_id,
            Integration.tenant_id == current_user.tenant_id,
        )
    )
    if not int_result.scalar_one_or_none():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Integration not found")

    from datetime import datetime
    query = select(ShopifyTransaction).where(
        ShopifyTransaction.integration_id == integration_id
    )
    if from_date:
        query = query.where(
            ShopifyTransaction.order_date >= datetime.combine(from_date, datetime.min.time())
        )
    if to_date:
        query = query.where(
            ShopifyTransaction.order_date <= datetime.combine(to_date, datetime.max.time())
        )
    if sale_type == "uk":
        query = query.where(ShopifyTransaction.is_uk_sale == True)
    elif sale_type == "eu":
        query = query.where(ShopifyTransaction.is_eu_sale == True)
    elif sale_type == "export":
        query = query.where(ShopifyTransaction.is_export == True)

    query = query.order_by(ShopifyTransaction.order_date.desc())
    query = query.offset((page - 1) * per_page).limit(per_page)

    result = await db.execute(query)
    transactions = result.scalars().all()
    return [ShopifyTransactionOut.model_validate(t) for t in transactions]


# ─── VAT AGGREGATION (PRE-FILL MTD BOXES) ────────────────────────────────────

@router.get("/shopify/{integration_id}/vat-aggregation")
async def get_vat_aggregation(
    integration_id: int,
    period_start: date = Query(..., description="VAT period start YYYY-MM-DD"),
    period_end: date = Query(..., description="VAT period end YYYY-MM-DD"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Aggregate Shopify sales for a VAT period and pre-fill MTD return boxes 1-9.
    Returns full breakdown: UK/EU/export sales, per-country, per-currency.
    """
    int_result = await db.execute(
        select(Integration).where(
            Integration.id == integration_id,
            Integration.tenant_id == current_user.tenant_id,
            Integration.provider == "shopify",
        )
    )
    integration = int_result.scalar_one_or_none()
    if not integration:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Integration not found")

    if not integration.company_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Integration not linked to a company",
        )

    try:
        result = await vat_aggregator.aggregate(
            db=db,
            company_id=integration.company_id,
            period_start=period_start,
            period_end=period_end,
            integration_ids=[integration_id],
        )
        return vat_aggregator.to_dict(result)
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


@router.post("/shopify/{integration_id}/vat-aggregation/apply")
async def apply_vat_aggregation_to_return(
    integration_id: int,
    period_start: date = Query(...),
    period_end: date = Query(...),
    vat_return_id: int = Query(..., description="VAT return ID to pre-fill"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Apply Shopify VAT aggregation to an existing VAT return draft.
    Pre-fills boxes 1, 3, 5, 6, 8 from Shopify data.
    Boxes 4 and 7 (purchases) must be entered manually.
    """
    from app.db.models.company import VATReturn

    int_result = await db.execute(
        select(Integration).where(
            Integration.id == integration_id,
            Integration.tenant_id == current_user.tenant_id,
        )
    )
    integration = int_result.scalar_one_or_none()
    if not integration:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Integration not found")

    vr_result = await db.execute(
        select(VATReturn).where(VATReturn.id == vat_return_id)
    )
    vat_return = vr_result.scalar_one_or_none()
    if not vat_return:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="VAT return not found")
    if vat_return.status != "draft":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only draft VAT returns can be pre-filled",
        )

    agg_result = await vat_aggregator.aggregate(
        db=db,
        company_id=integration.company_id,
        period_start=period_start,
        period_end=period_end,
        integration_ids=[integration_id],
    )

    boxes = agg_result.boxes
    vat_return.box1_vat_due_sales = boxes.box1_vat_due_sales
    vat_return.box2_vat_due_acquisitions = boxes.box2_vat_due_acquisitions
    vat_return.box3_total_vat_due = boxes.box3_total_vat_due
    vat_return.box5_net_vat_due = boxes.box5_net_vat_due
    vat_return.box6_total_sales = boxes.box6_total_sales
    vat_return.box8_total_supplies = boxes.box8_total_supplies
    vat_return.source = "shopify"
    vat_return.notes = (
        f"Pre-filled from Shopify data ({agg_result.breakdown.total_orders} orders). "
        "Box 4 and Box 7 require manual entry."
    )

    await db.flush()
    await db.refresh(vat_return)

    from app.schemas.company import VATReturnOut
    return {
        "message": "VAT return pre-filled from Shopify data",
        "vat_return": VATReturnOut.model_validate(vat_return),
        "warnings": agg_result.warnings,
        "notes": agg_result.notes,
        "transaction_count": len(agg_result.transaction_ids),
    }


# ─── FX RATES ─────────────────────────────────────────────────────────────────

@router.get("/fx-rates")
async def get_fx_rates(
    current_user: User = Depends(get_current_user),
):
    """Get current FX rates used for GBP conversion."""
    rates = await fx_service.get_all_rates()
    cache_age = fx_service.get_cache_age_minutes()
    return {
        "base": "GBP",
        "rates": {k: str(v) for k, v in rates.items()},
        "cache_age_minutes": round(cache_age, 1) if cache_age else None,
        "note": "Rates show: 1 unit of currency = X GBP",
    }


# ─── LEGACY VAT SUMMARY ───────────────────────────────────────────────────────

@router.get("/shopify/{integration_id}/vat-summary")
async def get_shopify_vat_summary(
    integration_id: int,
    period_start: date = Query(...),
    period_end: date = Query(...),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Simple VAT summary (use /vat-aggregation for full MTD box pre-fill)."""
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