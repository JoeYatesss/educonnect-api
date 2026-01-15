from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    # Supabase
    supabase_url: str
    supabase_service_role_key: str
    supabase_jwt_secret: str

    # Stripe
    stripe_secret_key: str = ""  # Required for payments
    stripe_webhook_secret: str = ""
    # Stripe Price IDs (different for test vs live mode)
    stripe_price_id_gbp: str = ""  # Required in production
    stripe_price_id_eur: str = ""  # Required in production
    stripe_price_id_usd: str = ""  # Required in production

    # Email
    resend_api_key: str
    team_email: str = "team@educonnectchina.com"

    # CORS
    allowed_origins: str = "http://localhost:3000"

    # App
    app_name: str = "EduConnect API"
    debug: bool = False

    class Config:
        env_file = ".env"
        case_sensitive = False
        extra = "ignore"  # Ignore extra fields in .env

    @property
    def allowed_origins_list(self) -> list[str]:
        return [origin.strip() for origin in self.allowed_origins.split(",")]


@lru_cache()
def get_settings() -> Settings:
    return Settings()
