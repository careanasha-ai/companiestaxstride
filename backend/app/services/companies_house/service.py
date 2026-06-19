from typing import Optional, Dict, Any, List
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from datetime import date, datetime
import json

from app.services.companies_house.client import companies_house_client
from app.db.models.company import Company
from app.db.models.user import Tenant
from app.schemas.company import CompanyCreate, CompanyUpdate
from loguru import logger


class CompaniesHouseService:

    async def search(self, query: str, items_per_page: int = 20) -> Dict[str, Any]:
        """Search Companies House — free, no auth required."""
        data = await companies_house_client.search_companies(query, items_per_page)
        items = data.get("items", [])
        results = []
        for item in items:
            addr = item.get("address", {})
            results.append({
                "company_number": item.get("company_number"),
                "company_name": item.get("title"),
                "company_status": item.get("company_status"),
                "company_type": item.get("company_type"),
                "date_of_creation": item.get("date_of_creation"),
                "registered_office_address": {
                    "address_line_1": addr.get("address_line_1"),
                    "address_line_2": addr.get("address_line_2"),
                    "locality": addr.get("locality"),
                    "postal_code": addr.get("postal_code"),
                    "country": addr.get("country"),
                },
                "sic_codes": item.get("sic_codes", []),
            })
        return {
            "total_results": data.get("total_results", 0),
            "items_per_page": data.get("items_per_page", 20),
            "start_index": data.get("start_index", 0),
            "items": results,
        }

    async def get_company_detail(self, company_number: str) -> Dict[str, Any]:
        """Get full company profile — free."""
        profile = await companies_house_client.get_company(company_number)
        officers_data = await companies_house_client.get_company_officers(company_number)
        psc_data = await companies_house_client.get_persons_with_significant_control(company_number)
        filing_data = await companies_house_client.get_filing_history(company_number, items_per_page=10)

        addr = profile.get("registered_office_address", {})
        return {
            "company_number": profile.get("company_number"),
            "company_name": profile.get("company_name"),
            "company_status": profile.get("company_status"),
            "company_type": profile.get("type"),
            "date_of_creation": profile.get("date_of_creation"),
            "date_of_cessation": profile.get("date_of_cessation"),
            "registered_office_address": addr,
            "sic_codes": profile.get("sic_codes", []),
            "accounts": profile.get("accounts"),
            "confirmation_statement": profile.get("confirmation_statement"),
            "jurisdiction": profile.get("jurisdiction"),
            "has_been_liquidated": profile.get("has_been_liquidated"),
            "has_charges": profile.get("has_charges"),
            "has_insolvency_history": profile.get("has_insolvency_history"),
            "officers": officers_data.get("items", [])[:10],
            "persons_with_significant_control": psc_data.get("items", []),
            "filing_history": filing_data.get("items", []),
        }

    async def get_filing_history(
        self,
        company_number: str,
        category: Optional[str] = None,
        page: int = 1,
        per_page: int = 25,
    ) -> Dict[str, Any]:
        """Get filing history — free."""
        start_index = (page - 1) * per_page
        data = await companies_house_client.get_filing_history(
            company_number, category=category,
            items_per_page=per_page, start_index=start_index
        )
        return data

    async def add_company_to_tenant(
        self,
        db: AsyncSession,
        tenant_id: int,
        payload: CompanyCreate,
    ) -> Company:
        """Add a Companies House company to a tenant's account."""
        # Check if already added
        result = await db.execute(
            select(Company).where(
                Company.tenant_id == tenant_id,
                Company.company_number == payload.company_number.upper(),
            )
        )
        existing = result.scalar_one_or_none()
        if existing:
            return existing

        # Fetch from CH API
        profile = await companies_house_client.get_company(payload.company_number)
        addr = profile.get("registered_office_address", {})
        accounts = profile.get("accounts", {})
        cs = profile.get("confirmation_statement", {})

        def parse_date(d: Optional[str]) -> Optional[date]:
            if not d:
                return None
            try:
                return datetime.strptime(d, "%Y-%m-%d").date()
            except Exception:
                return None

        company = Company(
            tenant_id=tenant_id,
            company_number=profile.get("company_number", "").upper(),
            company_name=profile.get("company_name", ""),
            company_type=profile.get("type"),
            company_status=profile.get("company_status"),
            date_of_creation=parse_date(profile.get("date_of_creation")),
            registered_address_line1=addr.get("address_line_1"),
            registered_address_line2=addr.get("address_line_2"),
            registered_address_city=addr.get("locality"),
            registered_address_county=addr.get("region"),
            registered_address_postcode=addr.get("postal_code"),
            registered_address_country=addr.get("country"),
            sic_codes=json.dumps(profile.get("sic_codes", [])),
            accounting_reference_day=accounts.get("accounting_reference_date", {}).get("day"),
            accounting_reference_month=accounts.get("accounting_reference_date", {}).get("month"),
            next_accounts_due=parse_date(accounts.get("next_due")),
            last_accounts_made_up_to=parse_date(accounts.get("last_accounts", {}).get("made_up_to")),
            next_confirmation_statement_due=parse_date(cs.get("next_due")),
            last_confirmation_statement_made_up_to=parse_date(cs.get("last_made_up_to")),
            vat_number=payload.vat_number,
            utr=payload.utr,
            vat_scheme=payload.vat_scheme,
            vat_flat_rate_percentage=payload.vat_flat_rate_percentage,
            is_vat_registered=bool(payload.vat_number),
            last_synced_at=datetime.utcnow(),
        )
        db.add(company)
        await db.flush()
        await db.refresh(company)
        logger.info(f"Added company {company.company_number} to tenant {tenant_id}")
        return company

    async def sync_company(self, db: AsyncSession, company: Company) -> Company:
        """Re-sync company data from Companies House."""
        profile = await companies_house_client.get_company(company.company_number)
        addr = profile.get("registered_office_address", {})
        accounts = profile.get("accounts", {})
        cs = profile.get("confirmation_statement", {})

        def parse_date(d):
            if not d:
                return None
            try:
                return datetime.strptime(d, "%Y-%m-%d").date()
            except Exception:
                return None

        company.company_name = profile.get("company_name", company.company_name)
        company.company_status = profile.get("company_status", company.company_status)
        company.registered_address_line1 = addr.get("address_line_1")
        company.registered_address_city = addr.get("locality")
        company.registered_address_postcode = addr.get("postal_code")
        company.sic_codes = json.dumps(profile.get("sic_codes", []))
        company.next_accounts_due = parse_date(accounts.get("next_due"))
        company.next_confirmation_statement_due = parse_date(cs.get("next_due"))
        company.last_synced_at = datetime.utcnow()

        await db.flush()
        await db.refresh(company)
        return company


companies_house_service = CompaniesHouseService()