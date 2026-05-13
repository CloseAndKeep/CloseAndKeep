from pydantic import BaseModel
from dotenv import load_dotenv
import os


load_dotenv()


class Settings(BaseModel):
    app_name: str = os.getenv("APP_NAME", "CloseAndKeep API")
    app_env: str = os.getenv("APP_ENV", "development")
    api_base_url: str = os.getenv("API_BASE_URL", "http://localhost:8000")
    web_base_url: str = os.getenv("WEB_BASE_URL", "http://localhost:3000")
    database_url: str = os.getenv("DATABASE_URL", "sqlite:///./closeandkeep.db")
    session_cookie_name: str = os.getenv("SESSION_COOKIE_NAME", "closeandkeep_session")
    session_cookie_secure: bool = os.getenv("SESSION_COOKIE_SECURE", "false").lower() == "true"
    session_ttl_hours: int = int(os.getenv("SESSION_TTL_HOURS", "24"))
    session_refresh_threshold_minutes: int = int(os.getenv("SESSION_REFRESH_THRESHOLD_MINUTES", "60"))
    admin_emails: set[str] = {
        email.strip().lower()
        for email in os.getenv("ADMIN_EMAILS", "").split(",")
        if email.strip()
    }
    stripe_secret_key: str = os.getenv("STRIPE_SECRET_KEY", "")
    stripe_webhook_secret: str = os.getenv("STRIPE_WEBHOOK_SECRET", "")
    stripe_price_id: str = os.getenv("STRIPE_PRICE_ID", "")
    resend_api_key: str = os.getenv("RESEND_API_KEY", "")
    resend_from: str = os.getenv("RESEND_FROM", "onboarding@resend.dev")
    order_notification_to: str = (
        os.getenv("ORDER_NOTIFICATION_TO", "CloseAndKeep@gmail.com").strip()
        or "CloseAndKeep@gmail.com"
    )
    cors_origins: list[str] = [
        origin.strip()
        for origin in os.getenv(
            "CORS_ORIGINS",
            "http://localhost:3000,http://127.0.0.1:3000",
        ).split(",")
        if origin.strip()
    ]


settings = Settings()
