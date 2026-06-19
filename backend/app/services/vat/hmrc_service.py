import httpx
from typing import Optional, Dict, Any, List
from datetime import datetime
from app.core.config import settings
from app.db.models.company import VATReturn
from app.db.models.user import User
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from loguru import logger


class HMRCVATService:
    """
    HMRC Making Tax Digital (MTD) VAT API client.
    Docs: https://developer.service.hmrc.gov.uk/api-documentation/docs/api/service/vat-api
    """

    def __init__(self):
        self.base_url = settings.HMRC_API_URL
        self.client_id = settings.HMRC_CLIENT_ID
        self.client_secret = settings.HMRC_CLIENT_SECRET

    def get_auth_url(self, state: str) -> str:
        """Generate HMRC OAuth2 authorization URL."""
        base = (
            "https://test-www.tax.service.gov.uk"
            if settings.HMRC_SANDBOX
            else "https://www.tax.service.gov.uk"
        )
        return (
            f"{base}/oauth/authorize"
            f"?response_type=code"
            f"&client_id={self.client_id}"
            f"&scope=read:vat+write:vat"
            f"&redirect_uri={settings.HMRC_REDIRECT_URI}"
            f"&state={state}"
        )

    async def exchange_code(self, code: str) -> Dict[str, Any]:
        """Exchange authorization code for access/refresh tokens."""
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self.base_url}/oauth/token",
                data={
                    "grant_type": "authorization_code",
                    "code": code,
                    "redirect_uri": settings.HMRC_REDIRECT_URI,
                    "client_id": self.client_id,
                    "client_secret": self.client_secret,
                },
                headers={"Content-Type": "application/x-www-form-urlencoded"},
            )
            response.raise_for_status()
            return response.json()

    async def refresh_token(self, refresh_token: str) -> Dict[str, Any]:
        """Refresh an expired HMRC access token."""
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self.base_url}/oauth/token",
                data={
                    "grant_type": "refresh_token",
                    "refresh_token": refresh_token,
                    "client_id": self.client_id,
                    "client_secret": self.client_secret,
                },
                headers={"Content-Type": "application/x-www-form-urlencoded"},
            )
            response.raise_for_status()
            return response.json()

    def _get_headers(self, access_token: str, gov_client_id: Optional[str] = None) -> Dict:
        """Build HMRC API request headers (MTD fraud prevention headers required)."""
        headers = {
            "Authorization": f"Bearer {access_token}",
            "Accept": "application/vnd.hmrc.1.0+json",
            "Content-Type": "application/json",
            # MTD Fraud Prevention Headers (required in production)
            "Gov-Client-Connection-Method": "WEB_APP_VIA_SERVER",
            "Gov-Client-Public-IP": "0.0.0.0",
            "Gov-Client-Timezone": "UTC+00:00",
            "Gov-Vendor-Version": "companiestaxstride=1.0.0",
            "Gov-Vendor-Product-Name": "CompaniesHouse Tax Stride",
        }
        if gov_client_id:
            headers["Gov-Client-User-IDs"] = f"os=user:{gov_client_id}"
        return headers

    async def get_vat_obligations(
        self,
        vrn: str,
        access_token: str,
        from_date: Optional[str] = None,
        to_date: Optional[str] = None,
        status: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Get VAT return obligations (open/fulfilled periods).
        vrn: VAT Registration Number
        """
        params = {}
        if from_date:
            params["from"] = from_date
        if to_date:
            params["to"] = to_date
        if status:
            params["status"] = status  # O=open, F=fulfilled

        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{self.base_url}/organisations/vat/{vrn}/obligations",
                headers=self._get_headers(access_token),
                params=params,
            )
            response.raise_for_status()
            return response.json()

    async def get_vat_return(
        self, vrn: str, period_key: str, access_token: str
    ) -> Dict[str, Any]:
        """Retrieve a submitted VAT return."""
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{self.base_url}/organisations/vat/{vrn}/returns/{period_key}",
                headers=self._get_headers(access_token),
            )
            response.raise_for_status()
            return response.json()

    async def submit_vat_return(
        self,
        vrn: str,
        vat_return: VATReturn,
        access_token: str,
        finalised: bool = True,
    ) -> Dict[str, Any]:
        """
        Submit a VAT return to HMRC MTD.
        This is a paid action — payment must be confirmed before calling.
        """
        payload = {
            "periodKey": vat_return.period_key,
            "vatDueSales": float(vat_return.box1_vat_due_sales),
            "vatDueAcquisitions": float(vat_return.box2_vat_due_acquisitions),
            "totalVatDue": float(vat_return.box3_total_vat_due),
            "vatReclaimedCurrPeriod": float(vat_return.box4_vat_reclaimed),
            "netVatDue": float(vat_return.box5_net_vat_due),
            "totalValueSalesExVAT": int(vat_return.box6_total_sales),
            "totalValuePurchasesExVAT": int(vat_return.box7_total_purchases),
            "totalValueGoodsSuppliedExVAT": int(vat_return.box8_total_supplies),
            "totalAcquisitionsExVAT": int(vat_return.box9_total_acquisitions),
            "finalised": finalised,
        }

        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self.base_url}/organisations/vat/{vrn}/returns",
                headers=self._get_headers(access_token),
                json=payload,
            )
            response.raise_for_status()
            result = response.json()

        # Update VAT return record
        vat_return.status = "submitted"
        vat_return.submitted_at = datetime.utcnow()
        vat_return.hmrc_receipt_id = result.get("paymentIndicator")
        vat_return.hmrc_correlation_id = result.get("processingDate")

        logger.info(f"VAT return submitted for VRN {vrn}, period {vat_return.period_key}")
        return result

    async def get_vat_liabilities(
        self, vrn: str, from_date: str, to_date: str, access_token: str
    ) -> Dict[str, Any]:
        """Get VAT liabilities (amounts owed to HMRC)."""
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{self.base_url}/organisations/vat/{vrn}/liabilities",
                headers=self._get_headers(access_token),
                params={"from": from_date, "to": to_date},
            )
            response.raise_for_status()
            return response.json()

    async def get_vat_payments(
        self, vrn: str, from_date: str, to_date: str, access_token: str
    ) -> Dict[str, Any]:
        """Get VAT payments made to HMRC."""
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{self.base_url}/organisations/vat/{vrn}/payments",
                headers=self._get_headers(access_token),
                params={"from": from_date, "to": to_date},
            )
            response.raise_for_status()
            return response.json()


hmrc_vat_service = HMRCVATService()