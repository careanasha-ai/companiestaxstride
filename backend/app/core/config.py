from pydantic_settings import BaseSettings
from pydantic import AnyHttpUrl, validator
from typing import List, Optional, Union
import secrets


class Settings(BaseSettings):
    # App
    APP_NAME: str = "CompaniesHouse Tax Stride"
    APP_ENV: str = "development"
    DEBUG: bool = True
    SECRET_KEY: str = secrets.token_urlsafe(32)
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60
    REFRESH_TOKEN_EXPIRE_DAYS: int = 30

    # Database
    DATABASE_URL: str
    DATABASE_URL_SYNC: Optional[str] = None

    # Redis
    REDIS_URL: str = "redis://localhost:6379/0"

    # CORS
    ALLOWED_ORIGINS: Union[str, List[str]] = ["http://localhost:3000"]

    @validator("ALLOWED_ORIGINS", pre=True)
    def parse_cors(cls, v):
        if isinstance(v, str):
            return [i.strip() for i in v.split(",")]
        return v

    # Companies House
    COMPANIES_HOUSE_API_KEY: str = ""
    COMPANIES_HOUSE_BASE_URL: str = "https://api.company-information.service.gov.uk"

    # HMRC
    HMRC_CLIENT_ID: str = ""
    HMRC_CLIENT_SECRET: str = ""
    HMRC_BASE_URL: str = "https://api.service.hmrc.gov.uk"
    HMRC_SANDBOX_URL: str = "https://test-api.service.hmrc.gov.uk"
    HMRC_REDIRECT_URI: str = "http://localhost:8000/api/v1/auth/hmrc/callback"
    HMRC_SANDBOX: bool = True

    @property
    def HMRC_API_URL(self) -> str:
        return self.HMRC_SANDBOX_URL if self.HMRC_SANDBOX else self.HMRC_BASE_URL

    # Stripe
    STRIPE_SECRET_KEY: str = ""
    STRIPE_PUBLISHABLE_KEY: str = ""
    STRIPE_WEBHOOK_SECRET: str = ""

    # Submission Prices (pence)
    PRICE_CONFIRMATION_STATEMENT: int = 1499
    PRICE_ANNUAL_ACCOUNTS: int = 2499
    PRICE_VAT_RETURN: int = 999
    PRICE_CT600: int = 3499

    # PayPal
    PAYPAL_CLIENT_ID: str = ""
    PAYPAL_CLIENT_SECRET: str = ""
    PAYPAL_MODE: str = "sandbox"

    # Shopify
    SHOPIFY_API_KEY: str = ""
    SHOPIFY_API_SECRET: str = ""
    SHOPIFY_SCOPES: str = "read_orders,read_products,read_customers,read_finances"
    SHOPIFY_REDIRECT_URI: str = "http://localhost:8000/api/v1/integrations/shopify/callback"

    # Email
    SENDGRID_API_KEY: str = ""
    FROM_EMAIL: str = "noreply@companiestaxstride.com"
    FROM_NAME: str = "CompaniesHouse Tax Stride"

    # Frontend
    FRONTEND_URL: str = "http://localhost:3000"

    class Config:
        env_file = ".env"
        case_sensitive = True


settings = Settings()