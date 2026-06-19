from fastapi import APIRouter
from app.api.v1.endpoints import auth, companies, filings, vat, payments, integrations

api_router = APIRouter(prefix="/api/v1")

api_router.include_router(auth.router)
api_router.include_router(companies.router)
api_router.include_router(filings.router)
api_router.include_router(vat.router)
api_router.include_router(payments.router)
api_router.include_router(integrations.router)