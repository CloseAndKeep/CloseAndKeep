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
    # Default one-time price when a per-pack price env var is not set.
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


# Canonical cookie-pack catalog. This is the single source of truth for which
# gift ids the API will accept; anything not listed here is rejected before it
# can reach Stripe.
GIFT_CATALOG: tuple[dict[str, object], ...] = (
    {"id": "cookies-1", "cookie_count": 1},
    {"id": "cookies-2", "cookie_count": 2},
    {"id": "cookies-4", "cookie_count": 4},
    {"id": "cookies-12", "cookie_count": 12},
)

KNOWN_GIFT_IDS: frozenset[str] = frozenset(str(item["id"]) for item in GIFT_CATALOG)

_GIFT_PRICE_ENV_KEYS: dict[str, str] = {
    "cookies-1": "STRIPE_PRICE_COOKIES_1",
    "cookies-2": "STRIPE_PRICE_COOKIES_2",
    "cookies-4": "STRIPE_PRICE_COOKIES_4",
    "cookies-12": "STRIPE_PRICE_COOKIES_12",
}


def is_known_gift(gift_id: str) -> bool:
    return gift_id in KNOWN_GIFT_IDS


def stripe_price_for_gift(gift_id: str) -> str:
    env_key = _GIFT_PRICE_ENV_KEYS.get(gift_id)
    if env_key:
        specific = os.getenv(env_key, "").strip()
        if specific:
            return specific
    return settings.stripe_price_id


settings = Settings()
