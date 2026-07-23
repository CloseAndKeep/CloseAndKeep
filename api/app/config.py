from pydantic import BaseModel
from dotenv import load_dotenv
import os


load_dotenv()


def _env_bool(name: str, default: str) -> bool:
    return os.getenv(name, default).lower() == "true"


def _default_session_cookie_secure() -> str:
    # Fail closed in production: HTTPS-only cookies unless explicitly overridden.
    env = os.getenv("APP_ENV", "development").lower()
    return "true" if env == "production" else "false"


class Settings(BaseModel):
    app_name: str = os.getenv("APP_NAME", "CloseAndKeep API")
    app_env: str = os.getenv("APP_ENV", "development")
    api_base_url: str = os.getenv("API_BASE_URL", "http://localhost:8000")
    web_base_url: str = os.getenv("WEB_BASE_URL", "http://localhost:3000")
    database_url: str = os.getenv("DATABASE_URL", "sqlite:///./closeandkeep.db")
    session_cookie_name: str = os.getenv("SESSION_COOKIE_NAME", "closeandkeep_session")
    session_cookie_secure: bool = _env_bool(
        "SESSION_COOKIE_SECURE", _default_session_cookie_secure()
    )
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
    # Sliding-window limits for API-key create and gift-order create paths.
    rate_limit_api_key_create: int = int(os.getenv("RATE_LIMIT_API_KEY_CREATE", "10"))
    rate_limit_api_key_create_window_seconds: int = int(
        os.getenv("RATE_LIMIT_API_KEY_CREATE_WINDOW_SECONDS", "3600")
    )
    rate_limit_order_create: int = int(os.getenv("RATE_LIMIT_ORDER_CREATE", "30"))
    rate_limit_order_create_window_seconds: int = int(
        os.getenv("RATE_LIMIT_ORDER_CREATE_WINDOW_SECONDS", "60")
    )
    rate_limit_order_create_ip: int = int(os.getenv("RATE_LIMIT_ORDER_CREATE_IP", "60"))
    rate_limit_order_create_ip_window_seconds: int = int(
        os.getenv("RATE_LIMIT_ORDER_CREATE_IP_WINDOW_SECONDS", "60")
    )
    # Auth endpoints (login / signup / guest) — IP + email buckets.
    rate_limit_auth_ip: int = int(os.getenv("RATE_LIMIT_AUTH_IP", "30"))
    rate_limit_auth_ip_window_seconds: int = int(
        os.getenv("RATE_LIMIT_AUTH_IP_WINDOW_SECONDS", "60")
    )
    rate_limit_auth_email: int = int(os.getenv("RATE_LIMIT_AUTH_EMAIL", "10"))
    rate_limit_auth_email_window_seconds: int = int(
        os.getenv("RATE_LIMIT_AUTH_EMAIL_WINDOW_SECONDS", "60")
    )
    # Shared rate-limit store for multi-worker / multi-instance deploys.
    # When unset, counters stay in-process (fine for a single uvicorn worker).
    redis_url: str = os.getenv("REDIS_URL", "").strip()
    # When true, trust the first X-Forwarded-For hop (only behind a proxy that
    # overwrites that header). Leave false for direct exposure.
    trust_proxy: bool = _env_bool("TRUST_PROXY", "false")
    # CSV import caps (bytes of upload body, and max data rows after parse).
    csv_import_max_bytes: int = int(os.getenv("CSV_IMPORT_MAX_BYTES", str(256 * 1024)))
    csv_import_max_rows: int = int(os.getenv("CSV_IMPORT_MAX_ROWS", "100"))
    # Address-request links expire with the Stripe authorize hold (~7 days).
    address_request_ttl_days: int = int(os.getenv("ADDRESS_REQUEST_TTL_DAYS", "7"))
    # Signup password policy (min length; must include a letter and a digit).
    password_min_length: int = int(os.getenv("PASSWORD_MIN_LENGTH", "12"))
    # Salesforce Connected App + cookie-reminder webhooks.
    salesforce_client_id: str = os.getenv("SALESFORCE_CLIENT_ID", "").strip()
    salesforce_client_secret: str = os.getenv("SALESFORCE_CLIENT_SECRET", "").strip()
    salesforce_redirect_uri: str = os.getenv(
        "SALESFORCE_REDIRECT_URI",
        "",
    ).strip()
    salesforce_login_url: str = os.getenv(
        "SALESFORCE_LOGIN_URL", "https://login.salesforce.com"
    ).strip().rstrip("/")
    salesforce_webhook_secret: str = os.getenv("SALESFORCE_WEBHOOK_SECRET", "").strip()
    # HubSpot private app / OAuth app + cookie-reminder webhooks.
    hubspot_client_id: str = os.getenv("HUBSPOT_CLIENT_ID", "").strip()
    hubspot_client_secret: str = os.getenv("HUBSPOT_CLIENT_SECRET", "").strip()
    hubspot_redirect_uri: str = os.getenv("HUBSPOT_REDIRECT_URI", "").strip()
    hubspot_webhook_secret: str = os.getenv("HUBSPOT_WEBHOOK_SECRET", "").strip()
    # Fernet key for encrypting CRM OAuth tokens at rest.
    integration_token_fernet_key: str = os.getenv("INTEGRATION_TOKEN_FERNET_KEY", "").strip()


# Canonical cookie-pack catalog. This is the single source of truth for which
# gift ids the API will accept; anything not listed here is rejected before it
# can reach Stripe.
GIFT_CATALOG: tuple[dict[str, object], ...] = (
    {"id": "cookies-4", "cookie_count": 4},
    {"id": "cookies-12", "cookie_count": 12},
)

KNOWN_GIFT_IDS: frozenset[str] = frozenset(str(item["id"]) for item in GIFT_CATALOG)

_GIFT_PRICE_ENV_KEYS: dict[str, str] = {
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
