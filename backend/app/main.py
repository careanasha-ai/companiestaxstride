from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.responses import JSONResponse
from contextlib import asynccontextmanager
from loguru import logger
import time

from app.core.config import settings
from app.api.v1.router import api_router
from app.db.database import init_db, close_db


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup and shutdown events."""
    logger.info(f"Starting {settings.APP_NAME} API...")
    await init_db()
    logger.info("Database ready")
    yield
    logger.info("Shutting down...")
    await close_db()


app = FastAPI(
    title=settings.APP_NAME,
    description="""
## CompaniesHouse Tax Stride API

A comprehensive UK compliance platform for:
- 🏢 **Companies House** — Search, lookup, file Confirmation Statements & Annual Accounts
- 💷 **VAT** — MTD-compliant VAT return management and submission
- 🛒 **Shopify** — Auto-import sales data for VAT calculation
- 💳 **Payments** — Stripe & PayPal for pay-per-submission model

### Free Tier
All lookup and data endpoints are free and require no authentication.

### Paid Submissions
Filing submissions require payment via Stripe or PayPal.
    """,
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
    lifespan=lifespan,
)

# ─── MIDDLEWARE ───────────────────────────────────────────────────────────────

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def add_process_time_header(request: Request, call_next):
    start_time = time.time()
    response = await call_next(request)
    process_time = time.time() - start_time
    response.headers["X-Process-Time"] = str(round(process_time * 1000, 2))
    return response


@app.middleware("http")
async def log_requests(request: Request, call_next):
    logger.info(f"→ {request.method} {request.url.path}")
    response = await call_next(request)
    logger.info(f"← {response.status_code} {request.url.path}")
    return response


# ─── EXCEPTION HANDLERS ───────────────────────────────────────────────────────

@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.error(f"Unhandled exception: {exc}", exc_info=True)
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"detail": "An internal server error occurred"},
    )


# ─── ROUTES ───────────────────────────────────────────────────────────────────

app.include_router(api_router)


@app.get("/", tags=["Health"])
async def root():
    return {
        "name": settings.APP_NAME,
        "version": "1.0.0",
        "status": "running",
        "docs": "/docs",
        "environment": settings.APP_ENV,
    }


@app.get("/health", tags=["Health"])
async def health_check():
    """Health check endpoint for Railway."""
    return {
        "status": "healthy",
        "service": "api",
        "version": "1.0.0",
    }


@app.get("/api/v1/pricing", tags=["Public"])
async def get_pricing_public():
    """Public pricing endpoint — no auth required."""
    return {
        "confirmation_statement": {
            "amount": settings.PRICE_CONFIRMATION_STATEMENT,
            "amount_display": f"£{settings.PRICE_CONFIRMATION_STATEMENT / 100:.2f}",
            "description": "Confirmation Statement (CS01) Filing",
        },
        "annual_accounts": {
            "amount": settings.PRICE_ANNUAL_ACCOUNTS,
            "amount_display": f"£{settings.PRICE_ANNUAL_ACCOUNTS / 100:.2f}",
            "description": "Annual Accounts (AA) Filing",
        },
        "vat_return": {
            "amount": settings.PRICE_VAT_RETURN,
            "amount_display": f"£{settings.PRICE_VAT_RETURN / 100:.2f}",
            "description": "VAT Return Submission (MTD)",
        },
        "ct600": {
            "amount": settings.PRICE_CT600,
            "amount_display": f"£{settings.PRICE_CT600 / 100:.2f}",
            "description": "Corporation Tax (CT600) Submission",
        },
        "currency": "GBP",
        "note": "All data lookups and reports are completely free. Pay only when you submit.",
    }