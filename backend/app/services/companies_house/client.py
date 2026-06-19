import httpx
from typing import Optional, Dict, Any, List
from app.core.config import settings
from loguru import logger


class CompaniesHouseClient:
    """
    Client for the Companies House Public Data API.
    Docs: https://developer-specs.company-information.service.gov.uk/
    """

    def __init__(self):
        self.base_url = settings.COMPANIES_HOUSE_BASE_URL
        self.api_key = settings.COMPANIES_HOUSE_API_KEY
        self.auth = (self.api_key, "")  # Basic auth: API key as username, empty password

    def _get_client(self) -> httpx.AsyncClient:
        return httpx.AsyncClient(
            base_url=self.base_url,
            auth=self.auth,
            timeout=30.0,
            headers={"Accept": "application/json"},
        )

    async def search_companies(
        self, query: str, items_per_page: int = 20, start_index: int = 0
    ) -> Dict[str, Any]:
        """Search for companies by name or number."""
        async with self._get_client() as client:
            try:
                response = await client.get(
                    "/search/companies",
                    params={
                        "q": query,
                        "items_per_page": items_per_page,
                        "start_index": start_index,
                    },
                )
                response.raise_for_status()
                return response.json()
            except httpx.HTTPStatusError as e:
                logger.error(f"CH search error: {e.response.status_code} - {e.response.text}")
                raise
            except Exception as e:
                logger.error(f"CH search exception: {e}")
                raise

    async def get_company(self, company_number: str) -> Dict[str, Any]:
        """Get company profile by company number."""
        async with self._get_client() as client:
            response = await client.get(f"/company/{company_number.upper()}")
            response.raise_for_status()
            return response.json()

    async def get_company_officers(
        self, company_number: str, items_per_page: int = 50
    ) -> Dict[str, Any]:
        """Get list of company officers (directors, secretaries)."""
        async with self._get_client() as client:
            response = await client.get(
                f"/company/{company_number.upper()}/officers",
                params={"items_per_page": items_per_page},
            )
            response.raise_for_status()
            return response.json()

    async def get_persons_with_significant_control(
        self, company_number: str
    ) -> Dict[str, Any]:
        """Get PSC (Persons with Significant Control) list."""
        async with self._get_client() as client:
            response = await client.get(
                f"/company/{company_number.upper()}/persons-with-significant-control"
            )
            response.raise_for_status()
            return response.json()

    async def get_filing_history(
        self,
        company_number: str,
        category: Optional[str] = None,
        items_per_page: int = 25,
        start_index: int = 0,
    ) -> Dict[str, Any]:
        """Get filing history for a company."""
        params = {
            "items_per_page": items_per_page,
            "start_index": start_index,
        }
        if category:
            params["category"] = category
        async with self._get_client() as client:
            response = await client.get(
                f"/company/{company_number.upper()}/filing-history",
                params=params,
            )
            response.raise_for_status()
            return response.json()

    async def get_charges(self, company_number: str) -> Dict[str, Any]:
        """Get charges (mortgages) registered against a company."""
        async with self._get_client() as client:
            response = await client.get(
                f"/company/{company_number.upper()}/charges"
            )
            response.raise_for_status()
            return response.json()

    async def get_registered_office_address(
        self, company_number: str
    ) -> Dict[str, Any]:
        """Get registered office address."""
        async with self._get_client() as client:
            response = await client.get(
                f"/company/{company_number.upper()}/registered-office-address"
            )
            response.raise_for_status()
            return response.json()

    async def get_annual_return(self, company_number: str) -> Dict[str, Any]:
        """Get confirmation statement / annual return data."""
        async with self._get_client() as client:
            response = await client.get(
                f"/company/{company_number.upper()}/confirmation-statement"
            )
            response.raise_for_status()
            return response.json()

    async def get_document(self, document_id: str) -> bytes:
        """Download a filed document (PDF)."""
        async with httpx.AsyncClient(
            base_url="https://document-api.company-information.service.gov.uk",
            auth=self.auth,
            timeout=60.0,
        ) as client:
            response = await client.get(f"/document/{document_id}/content")
            response.raise_for_status()
            return response.content

    async def validate_company_number(self, company_number: str) -> bool:
        """Check if a company number is valid and active."""
        try:
            data = await self.get_company(company_number)
            return data.get("company_status") == "active"
        except Exception:
            return False


companies_house_client = CompaniesHouseClient()