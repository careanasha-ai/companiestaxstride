"""
Foreign Exchange Rate Service
Fetches live rates, caches them in-memory for 1 hour to avoid hammering free APIs.
Falls back to hardcoded rates if all providers fail.
"""
import asyncio
import httpx
from decimal import Decimal
from datetime import datetime, timedelta
from typing import Dict, Optional
from loguru import logger


# ─── In-memory cache ──────────────────────────────────────────────────────────

_rate_cache: Dict[str, Decimal] = {}
_cache_timestamp: Optional[datetime] = None
_CACHE_TTL_MINUTES = 60

# Fallback rates (GBP base) — updated periodically as a safety net
_FALLBACK_RATES_TO_GBP: Dict[str, Decimal] = {
    "GBP": Decimal("1.000000"),
    "USD": Decimal("0.790000"),
    "EUR": Decimal("0.850000"),
    "CAD": Decimal("0.580000"),
    "AUD": Decimal("0.510000"),
    "JPY": Decimal("0.005200"),
    "CHF": Decimal("0.880000"),
    "SEK": Decimal("0.073000"),
    "NOK": Decimal("0.073000"),
    "DKK": Decimal("0.114000"),
    "NZD": Decimal("0.470000"),
    "SGD": Decimal("0.580000"),
    "HKD": Decimal("0.101000"),
    "INR": Decimal("0.009500"),
    "CNY": Decimal("0.109000"),
    "MXN": Decimal("0.046000"),
    "BRL": Decimal("0.155000"),
    "ZAR": Decimal("0.042000"),
    "AED": Decimal("0.215000"),
    "SAR": Decimal("0.211000"),
    "PLN": Decimal("0.196000"),
    "CZK": Decimal("0.034000"),
    "HUF": Decimal("0.002100"),
    "RON": Decimal("0.171000"),
    "BGN": Decimal("0.435000"),
    "HRK": Decimal("0.113000"),
    "TRY": Decimal("0.024000"),
    "RUB": Decimal("0.008600"),
    "KRW": Decimal("0.000590"),
    "THB": Decimal("0.021500"),
    "MYR": Decimal("0.168000"),
    "IDR": Decimal("0.000049"),
    "PHP": Decimal("0.013500"),
    "VND": Decimal("0.000031"),
    "ILS": Decimal("0.210000"),
    "CLP": Decimal("0.000840"),
    "COP": Decimal("0.000190"),
    "PEN": Decimal("0.205000"),
    "ARS": Decimal("0.000870"),
    "PKR": Decimal("0.002800"),
    "BDT": Decimal("0.007100"),
    "EGP": Decimal("0.016200"),
    "NGN": Decimal("0.000490"),
    "KES": Decimal("0.006100"),
    "GHS": Decimal("0.051000"),
    "MAD": Decimal("0.077000"),
}


class FXService:
    """
    Multi-provider FX rate service with caching.
    Providers tried in order:
    1. exchangerate-api.com (free tier, 1500 req/month)
    2. open.er-api.com (free, no key needed)
    3. Fallback hardcoded rates
    """

    async def _fetch_from_exchangerate_api(self) -> Optional[Dict[str, Decimal]]:
        """Provider 1: exchangerate-api.com (GBP base)."""
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(
                    "https://open.er-api.com/v6/latest/GBP"
                )
                if response.status_code == 200:
                    data = response.json()
                    if data.get("result") == "success":
                        rates = data.get("rates", {})
                        return {
                            currency: Decimal(str(1 / rate)) if rate else Decimal("1")
                            for currency, rate in rates.items()
                            if rate and rate > 0
                        }
        except Exception as e:
            logger.warning(f"FX provider 1 failed: {e}")
        return None

    async def _fetch_from_frankfurter(self) -> Optional[Dict[str, Decimal]]:
        """Provider 2: frankfurter.app (ECB rates, free, no key)."""
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(
                    "https://api.frankfurter.app/latest?from=GBP"
                )
                if response.status_code == 200:
                    data = response.json()
                    rates = data.get("rates", {})
                    result = {"GBP": Decimal("1.000000")}
                    for currency, rate in rates.items():
                        if rate and rate > 0:
                            # rates are "1 GBP = X currency", we want "1 X = Y GBP"
                            result[currency] = Decimal(str(1 / rate))
                    return result
        except Exception as e:
            logger.warning(f"FX provider 2 failed: {e}")
        return None

    async def _refresh_cache(self):
        """Refresh the rate cache from providers."""
        global _rate_cache, _cache_timestamp

        rates = await self._fetch_from_exchangerate_api()
        if not rates:
            rates = await self._fetch_from_frankfurter()
        if not rates:
            logger.warning("All FX providers failed — using fallback rates")
            rates = _FALLBACK_RATES_TO_GBP.copy()

        _rate_cache = rates
        _cache_timestamp = datetime.utcnow()
        logger.info(f"FX rates refreshed: {len(rates)} currencies cached")

    def _is_cache_valid(self) -> bool:
        if not _cache_timestamp or not _rate_cache:
            return False
        return datetime.utcnow() - _cache_timestamp < timedelta(minutes=_CACHE_TTL_MINUTES)

    async def get_rate_to_gbp(self, from_currency: str) -> Decimal:
        """
        Get exchange rate: 1 unit of from_currency = X GBP.
        Returns Decimal("1.0") for GBP.
        """
        from_currency = from_currency.upper().strip()
        if from_currency == "GBP":
            return Decimal("1.000000")

        if not self._is_cache_valid():
            await self._refresh_cache()

        rate = _rate_cache.get(from_currency)
        if rate:
            return rate

        # Try fallback
        fallback = _FALLBACK_RATES_TO_GBP.get(from_currency)
        if fallback:
            logger.warning(f"Using fallback rate for {from_currency}: {fallback}")
            return fallback

        logger.error(f"No FX rate found for {from_currency} — defaulting to 1.0")
        return Decimal("1.000000")

    async def convert_to_gbp(
        self, amount: Decimal, from_currency: str
    ) -> tuple[Decimal, Decimal]:
        """
        Convert amount to GBP.
        Returns (gbp_amount, exchange_rate).
        """
        if from_currency.upper() == "GBP":
            return amount, Decimal("1.000000")

        rate = await self.get_rate_to_gbp(from_currency)
        gbp_amount = (amount * rate).quantize(Decimal("0.01"))
        return gbp_amount, rate

    async def get_all_rates(self) -> Dict[str, Decimal]:
        """Get all cached rates (for display purposes)."""
        if not self._is_cache_valid():
            await self._refresh_cache()
        return dict(_rate_cache)

    def get_cache_age_minutes(self) -> Optional[float]:
        if not _cache_timestamp:
            return None
        return (datetime.utcnow() - _cache_timestamp).total_seconds() / 60


fx_service = FXService()