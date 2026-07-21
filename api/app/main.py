from contextlib import asynccontextmanager
from datetime import UTC, datetime, timedelta
from secrets import token_urlsafe
import re

import bcrypt
from fastapi import Depends, FastAPI, File, HTTPException, Response, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import PlainTextResponse, RedirectResponse
from pydantic import BaseModel, EmailStr, Field, field_validator, model_validator
import stripe
from sqlalchemy import or_, select, update
from sqlalchemy.orm import Session

from .api_keys import (
    authenticate_api_key,
    create_api_key,
    list_api_keys,
    revoke_api_key,
)
from .config import is_known_gift, settings
from .csv_import import (
    DEFAULT_IMPORT_NOTE,
    example_csv,
    parse_gift_orders_csv,
    template_csv,
)
from .db import SessionLocal
from .integrations import hubspot as hs
from .integrations import salesforce as sf
from .integrations.reminders import (
    PROVIDER_HUBSPOT,
    PROVIDER_SALESFORCE,
    process_stage_completed_reminder,
)
from .models import (
    ApiKeyModel,
    GiftOrderModel,
    IntegrationConnectionModel,
    ProspectModel,
    UserModel,
)
from .order_email import send_orderer_address_received
from .rate_limit import client_ip, limiter
from .session_store import (
    create_session,
    delete_session,
    get_session,
    purge_expired_sessions,
    purge_orphaned_guests,
    refresh_session_if_needed,
    rotate_session,
)
from .stripe_payments import (
    cancel_payment_authorization,
    capture_authorized_order,
    create_checkout_session_for_order,
    create_checkout_session_for_orders,
    ensure_stripe_webhook_configured,
    expire_authorization_for_payment_intent,
    fulfill_order_from_checkout_session,
    list_gift_prices,
    sync_order_payment_from_stripe,
)


# bcrypt only uses the first 72 bytes of a password and modern versions raise
# ValueError instead of silently truncating, so we truncate here before hashing
# and verifying. Existing `$2b$` hashes produced by passlib remain compatible.
_BCRYPT_MAX_PASSWORD_BYTES = 72


def _password_bytes(password: str) -> bytes:
    return password.encode("utf-8")[:_BCRYPT_MAX_PASSWORD_BYTES]


def hash_password(password: str) -> str:
    return bcrypt.hashpw(_password_bytes(password), bcrypt.gensalt()).decode("utf-8")


def verify_password(password: str, password_hash: str) -> bool:
    try:
        return bcrypt.checkpw(_password_bytes(password), password_hash.encode("utf-8"))
    except ValueError:
        return False


@asynccontextmanager
async def lifespan(_: FastAPI):
    purge_expired_sessions()
    purge_orphaned_guests()
    yield


app = FastAPI(title=settings.app_name, lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class SignupRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1)

    @field_validator("password")
    @classmethod
    def _password_policy(cls, value: str) -> str:
        if len(value) < settings.password_min_length:
            raise ValueError(
                f"Password must be at least {settings.password_min_length} characters."
            )
        if not re.search(r"[A-Za-z]", value) or not re.search(r"\d", value):
            raise ValueError("Password must include at least one letter and one number.")
        return value


class ProspectCreateRequest(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    title: str = Field(min_length=1, max_length=255)
    company: str = Field(min_length=1, max_length=255)
    email: EmailStr
    deal_status: str = Field(default="open", pattern="^(open|won|lost)$")


class ProspectResponse(BaseModel):
    id: int
    name: str
    title: str
    company: str
    email: str
    deal_status: str


class DashboardSummaryResponse(BaseModel):
    open_deals: int
    won: int
    lost: int
    total_prospects: int


class GiftOrderCreateRequest(BaseModel):
    prospect_id: int
    gift_id: str = Field(min_length=1, max_length=64)
    recipient_name: str = Field(min_length=1, max_length=255)
    # Required unless request_recipient_address is true (recipient fills it in later).
    shipping_address: str | None = Field(default=None, max_length=1000)
    note: str = Field(min_length=1, max_length=1000)
    # When true, authorize payment at checkout, email the recipient a link to
    # enter shipping, then capture only after they submit. Guests cannot use this.
    request_recipient_address: bool = False
    recipient_email: EmailStr | None = None

    @field_validator("recipient_name", "note")
    @classmethod
    def _reject_blank(cls, value: str) -> str:
        # min_length only guards raw length; reject whitespace-only values so a
        # gift never ships without a recipient or note on the gift.
        if not value.strip():
            raise ValueError("must not be blank")
        return value

    @field_validator("shipping_address")
    @classmethod
    def _strip_address(cls, value: str | None) -> str | None:
        if value is None:
            return None
        stripped = value.strip()
        return stripped or None

    @model_validator(mode="after")
    def _address_or_request(self) -> "GiftOrderCreateRequest":
        if self.request_recipient_address:
            if not self.recipient_email:
                raise ValueError("recipient_email is required when requesting an address from the recipient")
            return self
        if not self.shipping_address:
            raise ValueError("shipping_address is required unless requesting an address from the recipient")
        return self


class GiftOrderResponse(BaseModel):
    id: int
    prospect_id: int
    gift_id: str
    recipient_name: str
    shipping_address: str | None = None
    recipient_email: str | None = None
    note: str
    status: str
    payment_status: str
    tracking_number: str | None = None
    requested_at: datetime


class GiftOrderCreateResponse(GiftOrderResponse):
    checkout_url: str | None = None


class GiftOrderImportRowError(BaseModel):
    row: int
    message: str


class GiftOrderImportResponse(BaseModel):
    created: list[GiftOrderCreateResponse]
    # Single Checkout URL covering every imported row that already has an address.
    batch_checkout_url: str | None = None
    errors: list[GiftOrderImportRowError] = []


class StripeCheckoutResponse(BaseModel):
    checkout_url: str


class AddressRequestPublicResponse(BaseModel):
    recipient_name: str
    gift_id: str
    note: str
    already_submitted: bool = False


class AddressSubmitRequest(BaseModel):
    shipping_address: str = Field(min_length=1, max_length=1000)
    recipient_name: str | None = Field(default=None, max_length=255)

    @field_validator("shipping_address")
    @classmethod
    def _reject_blank_address(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("must not be blank")
        return value

    @field_validator("recipient_name")
    @classmethod
    def _strip_name(cls, value: str | None) -> str | None:
        if value is None:
            return None
        stripped = value.strip()
        return stripped or None


class GiftCatalogItem(BaseModel):
    gift_id: str
    cookie_count: int
    # Live Stripe amount in the smallest currency unit (e.g. cents). None when
    # Stripe is not configured or the price could not be fetched.
    unit_amount: int | None = None
    currency: str | None = None


class ProspectUpdateRequest(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    title: str | None = Field(default=None, min_length=1, max_length=255)
    company: str | None = Field(default=None, min_length=1, max_length=255)
    email: EmailStr | None = None
    deal_status: str | None = Field(default=None, pattern="^(open|won|lost)$")


# Statuses an admin can set while fulfilling a paid order.
ADMIN_ORDER_STATUSES = ("queued", "ordered", "shipped", "delivered", "canceled")


class AdminOrderUpdateRequest(BaseModel):
    status: str | None = Field(
        default=None,
        pattern="^(no_address|pending_payment|queued|ordered|shipped|delivered|canceled)$",
    )
    tracking_number: str | None = Field(default=None, max_length=255)
    admin_notes: str | None = Field(default=None, max_length=2000)


class AdminGiftOrderResponse(GiftOrderResponse):
    admin_notes: str | None = None
    owner_user_id: int
    owner_email: str
    prospect_name: str
    prospect_company: str
    prospect_email: str


class ApiKeyCreateRequest(BaseModel):
    name: str = Field(min_length=1, max_length=120)

    @field_validator("name")
    @classmethod
    def _reject_blank_name(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("must not be blank")
        return value.strip()


class ApiKeyResponse(BaseModel):
    id: int
    name: str
    key_prefix: str
    created_at: datetime
    last_used_at: datetime | None = None
    revoked_at: datetime | None = None


class ApiKeyCreateResponse(ApiKeyResponse):
    """Includes the raw secret once — it cannot be retrieved again."""

    api_key: str


class IntegrationConnectionResponse(BaseModel):
    id: int
    provider: str
    enabled: bool
    trigger_stage_name: str
    external_org_id: str | None = None
    instance_url: str | None = None
    last_polled_at: datetime | None = None
    created_at: datetime
    updated_at: datetime


class IntegrationUpdateRequest(BaseModel):
    trigger_stage_name: str | None = Field(default=None, min_length=1, max_length=255)
    enabled: bool | None = None

    @field_validator("trigger_stage_name")
    @classmethod
    def _strip_stage(cls, value: str | None) -> str | None:
        if value is None:
            return None
        stripped = value.strip()
        if not stripped:
            raise ValueError("trigger_stage_name must not be blank")
        return stripped


class SalesforceConnectResponse(BaseModel):
    authorize_url: str


class HubSpotConnectResponse(BaseModel):
    authorize_url: str


class SalesforceEventRequest(BaseModel):
    """Inbound Demo Completed (or configured stage) event from Salesforce Flow / webhook."""

    opportunity_id: str = Field(min_length=1, max_length=64)
    stage_name: str = Field(default="Demo Completed", min_length=1, max_length=255)
    contact_name: str = Field(min_length=1, max_length=255)
    contact_email: EmailStr
    contact_title: str = Field(default="", max_length=255)
    company: str = Field(default="", max_length=255)
    connection_id: int | None = None
    org_id: str | None = Field(default=None, max_length=64)


class HubSpotEventRequest(BaseModel):
    """Inbound Demo Completed (or configured stage) event from HubSpot workflow / webhook."""

    deal_id: str = Field(min_length=1, max_length=64)
    stage_name: str = Field(default="Demo Completed", min_length=1, max_length=255)
    contact_name: str = Field(min_length=1, max_length=255)
    contact_email: EmailStr
    contact_title: str = Field(default="", max_length=255)
    company: str = Field(default="", max_length=255)
    connection_id: int | None = None
    portal_id: str | None = Field(default=None, max_length=64)


def get_db() -> Session:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def _set_session_cookie(response: Response, session_id: str, *, persistent: bool = True) -> None:
    # Guest sessions use a browser session cookie (no max_age) so closing the
    # browser ends access; registered users get a durable TTL cookie.
    cookie_kwargs: dict = {
        "key": settings.session_cookie_name,
        "value": session_id,
        "httponly": True,
        "secure": settings.session_cookie_secure,
        "samesite": "lax",
    }
    if persistent:
        cookie_kwargs["max_age"] = 60 * 60 * settings.session_ttl_hours
    response.set_cookie(**cookie_kwargs)


def _normalize_email(email: str) -> str:
    return email.strip().lower()


def _address_request_expiry() -> datetime:
    return datetime.now(UTC) + timedelta(days=settings.address_request_ttl_days)


def _mint_address_request_token() -> tuple[str, datetime]:
    return token_urlsafe(32), _address_request_expiry()


def _clear_address_request_token(order: GiftOrderModel) -> None:
    order.address_request_token = None
    order.address_request_expires_at = None


def _address_request_is_expired(order: GiftOrderModel) -> bool:
    expires = order.address_request_expires_at
    if expires is None:
        # Legacy rows without an expiry still work until a hold expires via webhook.
        return False
    if expires.tzinfo is None:
        expires = expires.replace(tzinfo=UTC)
    return expires <= datetime.now(UTC)


def _get_order_by_address_token(token: str, db: Session) -> GiftOrderModel:
    order = db.scalar(
        select(GiftOrderModel).where(GiftOrderModel.address_request_token == token)
    )
    if not order:
        raise HTTPException(status_code=404, detail="This address link is invalid or has expired.")
    if _address_request_is_expired(order):
        _clear_address_request_token(order)
        if order.payment_status == "authorized":
            # Best-effort release; ignore Stripe failures so the link still dies.
            try:
                cancel_payment_authorization(order)
            except HTTPException:
                pass
            order.payment_status = "canceled"
            if order.status == "no_address":
                order.status = "canceled"
        db.add(order)
        db.commit()
        raise HTTPException(status_code=404, detail="This address link is invalid or has expired.")
    return order


def _sync_admin_role(user: UserModel, db: Session) -> UserModel:
    # Guest accounts stay guest — never promote/demote via ADMIN_EMAILS.
    if user.role == "guest":
        return user
    expected_role = "admin" if user.email in settings.admin_emails else "user"
    if user.role != expected_role:
        user.role = expected_role
        db.add(user)
        db.commit()
        db.refresh(user)
    return user


def _discard_empty_guest(user: UserModel | None, db: Session) -> None:
    """Drop a guest account only when it has no gift orders to fulfill.

    Guests who placed orders are kept (their session is already cleared) so
    admins can still ship. The next guest gets a new user id and cannot see
    those orders via owner-scoped list endpoints.
    """
    if user is None or user.role != "guest":
        return
    has_order = db.scalar(
        select(GiftOrderModel.id).where(GiftOrderModel.owner_user_id == user.id).limit(1)
    )
    if has_order:
        return
    db.delete(user)
    db.commit()


def _gift_order_response(order: GiftOrderModel) -> GiftOrderResponse:
    return GiftOrderResponse(
        id=order.id,
        prospect_id=order.prospect_id,
        gift_id=order.gift_id,
        recipient_name=order.recipient_name,
        shipping_address=order.shipping_address,
        recipient_email=order.recipient_email,
        note=order.note,
        status=order.status,
        payment_status=order.payment_status,
        tracking_number=order.tracking_number,
        requested_at=order.requested_at,
    )


def _admin_gift_order_response(
    order: GiftOrderModel, owner: UserModel, prospect: ProspectModel
) -> AdminGiftOrderResponse:
    return AdminGiftOrderResponse(
        id=order.id,
        prospect_id=order.prospect_id,
        gift_id=order.gift_id,
        recipient_name=order.recipient_name,
        shipping_address=order.shipping_address,
        recipient_email=order.recipient_email,
        note=order.note,
        status=order.status,
        payment_status=order.payment_status,
        tracking_number=order.tracking_number,
        admin_notes=order.admin_notes,
        requested_at=order.requested_at,
        owner_user_id=order.owner_user_id,
        owner_email=owner.email if owner else "",
        prospect_name=prospect.name if prospect else "",
        prospect_company=prospect.company if prospect else "",
        prospect_email=prospect.email if prospect else "",
    )


def _order_detail_url(order_id: int) -> str:
    return f"{settings.web_base_url.rstrip('/')}/orders/{order_id}"


def _bearer_token(request: Request) -> str | None:
    header = request.headers.get("Authorization")
    if not header:
        return None
    scheme, _, value = header.partition(" ")
    if scheme.lower() != "bearer" or not value.strip():
        return None
    return value.strip()


def get_current_user(request: Request, response: Response, db: Session = Depends(get_db)) -> UserModel:
    """Authenticate via ``Authorization: Bearer cak_…`` or the session cookie.

    API keys are for server-to-server clients (agents, scripts). The Next.js
    dashboard keeps using HttpOnly cookies. Both resolve to the same user and
    tenancy rules. Admin routes reject API-key auth (see ``get_current_admin``).
    """
    token = _bearer_token(request)
    if token:
        user = authenticate_api_key(token, db)
        if not user:
            raise HTTPException(status_code=401, detail="Invalid or revoked API key.")
        request.state.auth_method = "api_key"
        return _sync_admin_role(user, db)

    session_id = request.cookies.get(settings.session_cookie_name)
    session = refresh_session_if_needed(session_id)
    if not session:
        raise HTTPException(status_code=401, detail="Not authenticated.")

    user = db.get(UserModel, session.user_id)
    if not user:
        delete_session(session.session_id)
        response.delete_cookie(key=settings.session_cookie_name)
        raise HTTPException(status_code=401, detail="Not authenticated.")

    request.state.auth_method = "session"
    user = _sync_admin_role(user, db)
    _set_session_cookie(response, session.session_id, persistent=user.role != "guest")
    return user


def get_current_admin(
    request: Request,
    current_user: UserModel = Depends(get_current_user),
) -> UserModel:
    if getattr(request.state, "auth_method", None) == "api_key":
        raise HTTPException(
            status_code=403,
            detail="Admin endpoints require a browser session, not an API key.",
        )
    if current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Admin access required.")
    return current_user


def _enforce_api_key_create_rate_limit(request: Request, user: UserModel) -> None:
    limiter.check(
        f"api-key-create:user:{user.id}",
        limit=settings.rate_limit_api_key_create,
        window_seconds=settings.rate_limit_api_key_create_window_seconds,
    )
    limiter.check(
        f"api-key-create:ip:{client_ip(request)}",
        limit=settings.rate_limit_api_key_create,
        window_seconds=settings.rate_limit_api_key_create_window_seconds,
    )


def _enforce_order_create_rate_limit(request: Request, user: UserModel) -> None:
    limiter.check(
        f"order-create:user:{user.id}",
        limit=settings.rate_limit_order_create,
        window_seconds=settings.rate_limit_order_create_window_seconds,
    )
    limiter.check(
        f"order-create:ip:{client_ip(request)}",
        limit=settings.rate_limit_order_create_ip,
        window_seconds=settings.rate_limit_order_create_ip_window_seconds,
    )


def _enforce_auth_rate_limit(request: Request, *, email: str | None = None) -> None:
    limiter.check(
        f"auth:ip:{client_ip(request)}",
        limit=settings.rate_limit_auth_ip,
        window_seconds=settings.rate_limit_auth_ip_window_seconds,
    )
    if email:
        limiter.check(
            f"auth:email:{email}",
            limit=settings.rate_limit_auth_email,
            window_seconds=settings.rate_limit_auth_email_window_seconds,
        )


def _api_key_response(record: ApiKeyModel) -> ApiKeyResponse:
    return ApiKeyResponse(
        id=record.id,
        name=record.name,
        key_prefix=record.key_prefix,
        created_at=record.created_at,
        last_used_at=record.last_used_at,
        revoked_at=record.revoked_at,
    )


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "env": settings.app_env}


@app.get("/gifts", response_model=list[GiftCatalogItem])
def list_gifts() -> list[GiftCatalogItem]:
    return [GiftCatalogItem(**item) for item in list_gift_prices()]


@app.post("/auth/login")
def login(payload: LoginRequest, request: Request, response: Response, db: Session = Depends(get_db)) -> dict[str, str]:
    email = _normalize_email(payload.email)
    _enforce_auth_rate_limit(request, email=email)
    user = db.scalar(select(UserModel).where(UserModel.email == email))
    if not user or user.role == "guest" or not verify_password(payload.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Invalid email or password.")

    user = _sync_admin_role(user, db)
    previous_session_id = request.cookies.get(settings.session_cookie_name)
    # Switching from guest → registered account: drop empty guests only.
    previous = get_session(previous_session_id)
    if previous and previous.user_id != user.id:
        previous_user = db.get(UserModel, previous.user_id)
        _discard_empty_guest(previous_user, db)
    session = rotate_session(previous_session_id, user.id)
    _set_session_cookie(response, session.session_id, persistent=True)
    return {"message": "Logged in."}


@app.post("/auth/signup")
def signup(payload: SignupRequest, request: Request, response: Response, db: Session = Depends(get_db)) -> dict[str, str]:
    email = _normalize_email(payload.email)
    _enforce_auth_rate_limit(request, email=email)
    existing = db.scalar(select(UserModel).where(UserModel.email == email))
    if existing:
        # Same status/message shape as a generic failure — avoid email enumeration.
        raise HTTPException(
            status_code=400,
            detail="Unable to create account with these credentials.",
        )

    role = "admin" if email in settings.admin_emails else "user"
    user = UserModel(
        email=email,
        password_hash=hash_password(payload.password),
        role=role,
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    previous_session_id = request.cookies.get(settings.session_cookie_name)
    previous = get_session(previous_session_id)
    if previous and previous.user_id != user.id:
        previous_user = db.get(UserModel, previous.user_id)
        _discard_empty_guest(previous_user, db)
    session = rotate_session(previous_session_id, user.id)
    _set_session_cookie(response, session.session_id, persistent=True)
    return {"message": "Signed up."}


@app.post("/auth/guest")
def guest_login(request: Request, response: Response, db: Session = Depends(get_db)) -> dict[str, str]:
    """Start an ephemeral guest session.

    Each guest gets a fresh user id (so they cannot see prior guest data).
    Gift orders are retained after logout for fulfillment; empty guests are
    cleaned up. Follow-ups are not offered to guests.
    """
    _enforce_auth_rate_limit(request)
    previous_session_id = request.cookies.get(settings.session_cookie_name)
    previous = get_session(previous_session_id)
    if previous:
        previous_user = db.get(UserModel, previous.user_id)
        delete_session(previous_session_id)
        _discard_empty_guest(previous_user, db)

    user = UserModel(
        email=f"guest-{token_urlsafe(12).lower()}@guest.example.com",
        password_hash=hash_password(token_urlsafe(32)),
        role="guest",
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    session = create_session(user.id)
    _set_session_cookie(response, session.session_id, persistent=False)
    return {"message": "Continuing as guest."}


@app.post("/auth/logout")
def logout(request: Request, response: Response, db: Session = Depends(get_db)) -> dict[str, str]:
    session_id = request.cookies.get(settings.session_cookie_name)
    record = get_session(session_id)
    user = db.get(UserModel, record.user_id) if record else None
    delete_session(session_id)
    _discard_empty_guest(user, db)
    response.delete_cookie(key=settings.session_cookie_name)
    return {"message": "Logged out."}


@app.get("/auth/me")
def me(current_user: UserModel = Depends(get_current_user)) -> dict[str, str | int | bool]:
    return {
        "user_id": current_user.id,
        "email": current_user.email,
        "role": current_user.role,
        "is_guest": current_user.role == "guest",
    }


@app.get("/api-keys", response_model=list[ApiKeyResponse])
def get_api_keys(
    current_user: UserModel = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[ApiKeyResponse]:
    if current_user.role == "guest":
        raise HTTPException(
            status_code=403,
            detail="Guest accounts cannot manage API keys.",
        )
    return [_api_key_response(record) for record in list_api_keys(current_user, db)]


@app.post("/api-keys", response_model=ApiKeyCreateResponse, status_code=201)
def post_api_key(
    payload: ApiKeyCreateRequest,
    request: Request,
    current_user: UserModel = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ApiKeyCreateResponse:
    _enforce_api_key_create_rate_limit(request, current_user)
    record, raw_key = create_api_key(owner=current_user, name=payload.name, db=db)
    base = _api_key_response(record)
    return ApiKeyCreateResponse(**base.model_dump(), api_key=raw_key)


@app.delete("/api-keys/{key_id}", response_model=ApiKeyResponse)
def delete_api_key(
    key_id: int,
    current_user: UserModel = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ApiKeyResponse:
    if current_user.role == "guest":
        raise HTTPException(
            status_code=403,
            detail="Guest accounts cannot manage API keys.",
        )
    record = revoke_api_key(owner=current_user, key_id=key_id, db=db)
    return _api_key_response(record)


@app.post("/billing/webhook")
async def stripe_webhook(request: Request, db: Session = Depends(get_db)) -> dict[str, bool]:
    ensure_stripe_webhook_configured()
    payload = await request.body()
    signature = request.headers.get("Stripe-Signature")
    if not signature:
        raise HTTPException(status_code=400, detail="Missing Stripe signature.")
    try:
        event = stripe.Webhook.construct_event(payload, signature, settings.stripe_webhook_secret)
    except stripe.error.SignatureVerificationError:
        raise HTTPException(status_code=400, detail="Invalid Stripe signature.")
    except ValueError:
        # Raised by construct_event when the request body is not valid JSON.
        raise HTTPException(status_code=400, detail="Invalid Stripe webhook payload.")

    if event["type"] == "checkout.session.completed":
        fulfill_order_from_checkout_session(event["data"]["object"], db)
    elif event["type"] == "payment_intent.canceled":
        # Stripe drops uncaptured authorizations (~7 days); keep local state in sync.
        expire_authorization_for_payment_intent(event["data"]["object"], db)

    return {"received": True}


@app.get("/prospects", response_model=list[ProspectResponse])
def list_prospects(current_user: UserModel = Depends(get_current_user), db: Session = Depends(get_db)) -> list[ProspectResponse]:
    records = db.scalars(
        select(ProspectModel).where(ProspectModel.owner_user_id == current_user.id).order_by(ProspectModel.created_at.desc())
    ).all()
    return [
        ProspectResponse(
            id=record.id,
            name=record.name,
            title=record.title,
            company=record.company,
            email=record.email,
            deal_status=record.deal_status,
        )
        for record in records
    ]


@app.post("/prospects", response_model=ProspectResponse, status_code=201)
def create_prospect(
    payload: ProspectCreateRequest,
    current_user: UserModel = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ProspectResponse:
    prospect = ProspectModel(
        owner_user_id=current_user.id,
        name=payload.name.strip(),
        title=payload.title.strip(),
        company=payload.company.strip(),
        email=_normalize_email(str(payload.email)),
        deal_status=payload.deal_status,
    )
    db.add(prospect)
    db.commit()
    db.refresh(prospect)
    return ProspectResponse(
        id=prospect.id,
        name=prospect.name,
        title=prospect.title,
        company=prospect.company,
        email=prospect.email,
        deal_status=prospect.deal_status,
    )


@app.get("/prospects/{prospect_id}", response_model=ProspectResponse)
def get_prospect(
    prospect_id: int,
    current_user: UserModel = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ProspectResponse:
    prospect = db.get(ProspectModel, prospect_id)
    if not prospect or prospect.owner_user_id != current_user.id:
        raise HTTPException(status_code=404, detail="Prospect not found.")
    return ProspectResponse(
        id=prospect.id,
        name=prospect.name,
        title=prospect.title,
        company=prospect.company,
        email=prospect.email,
        deal_status=prospect.deal_status,
    )


@app.patch("/prospects/{prospect_id}", response_model=ProspectResponse)
def update_prospect(
    prospect_id: int,
    payload: ProspectUpdateRequest,
    current_user: UserModel = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ProspectResponse:
    prospect = db.get(ProspectModel, prospect_id)
    if not prospect or prospect.owner_user_id != current_user.id:
        raise HTTPException(status_code=404, detail="Prospect not found.")

    if payload.name is not None:
        prospect.name = payload.name.strip()
    if payload.title is not None:
        prospect.title = payload.title.strip()
    if payload.company is not None:
        prospect.company = payload.company.strip()
    if payload.email is not None:
        prospect.email = _normalize_email(str(payload.email))
    if payload.deal_status is not None:
        prospect.deal_status = payload.deal_status

    db.add(prospect)
    db.commit()
    db.refresh(prospect)
    return ProspectResponse(
        id=prospect.id,
        name=prospect.name,
        title=prospect.title,
        company=prospect.company,
        email=prospect.email,
        deal_status=prospect.deal_status,
    )


@app.get("/dashboard/summary", response_model=DashboardSummaryResponse)
def get_dashboard_summary(
    current_user: UserModel = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> DashboardSummaryResponse:
    records = db.scalars(select(ProspectModel.deal_status).where(ProspectModel.owner_user_id == current_user.id)).all()
    open_deals = sum(1 for status in records if status == "open")
    won = sum(1 for status in records if status == "won")
    lost = sum(1 for status in records if status == "lost")
    return DashboardSummaryResponse(
        open_deals=open_deals,
        won=won,
        lost=lost,
        total_prospects=len(records),
    )


@app.post("/gift-orders", response_model=GiftOrderCreateResponse, status_code=201)
def create_gift_order(
    payload: GiftOrderCreateRequest,
    request: Request,
    current_user: UserModel = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> GiftOrderCreateResponse:
    _enforce_order_create_rate_limit(request, current_user)
    if not is_known_gift(payload.gift_id.strip()):
        raise HTTPException(status_code=400, detail="Unknown gift selection.")

    prospect = db.get(ProspectModel, payload.prospect_id)
    if not prospect or prospect.owner_user_id != current_user.id:
        raise HTTPException(status_code=404, detail="Prospect not found.")

    if payload.request_recipient_address:
        if current_user.role == "guest":
            raise HTTPException(
                status_code=403,
                detail="Guest accounts cannot request a shipping address from the recipient.",
            )
        token, expires_at = _mint_address_request_token()
        order = GiftOrderModel(
            owner_user_id=current_user.id,
            prospect_id=payload.prospect_id,
            gift_id=payload.gift_id.strip(),
            recipient_name=payload.recipient_name.strip(),
            shipping_address=None,
            recipient_email=str(payload.recipient_email).strip().lower(),
            note=payload.note.strip(),
            status="no_address",
            payment_status="pending",
            address_request_token=token,
            address_request_expires_at=expires_at,
            # Email is sent after Stripe authorization succeeds — not yet.
            address_request_sent_at=None,
        )
        db.add(order)
        db.commit()
        db.refresh(order)

        try:
            checkout_url = create_checkout_session_for_order(order, current_user, db)
        except HTTPException:
            db.delete(order)
            db.commit()
            raise

        db.refresh(order)
        response = _gift_order_response(order)
        return GiftOrderCreateResponse(**response.model_dump(), checkout_url=checkout_url)

    order = GiftOrderModel(
        owner_user_id=current_user.id,
        prospect_id=payload.prospect_id,
        gift_id=payload.gift_id.strip(),
        recipient_name=payload.recipient_name.strip(),
        shipping_address=payload.shipping_address.strip() if payload.shipping_address else None,
        note=payload.note.strip(),
        status="pending_payment",
        payment_status="pending",
    )
    db.add(order)
    db.commit()
    db.refresh(order)

    try:
        checkout_url = create_checkout_session_for_order(order, current_user, db)
    except HTTPException:
        # Checkout could not be created (e.g. Stripe not configured). Don't leave
        # behind an unpayable pending order.
        db.delete(order)
        db.commit()
        raise

    db.refresh(order)
    response = _gift_order_response(order)
    return GiftOrderCreateResponse(**response.model_dump(), checkout_url=checkout_url)


def _find_or_create_prospect_for_import(
    *,
    owner: UserModel,
    name: str,
    email: str,
    db: Session,
) -> ProspectModel:
    """Reuse an existing prospect with the same email, otherwise create one."""
    existing = db.scalar(
        select(ProspectModel).where(
            ProspectModel.owner_user_id == owner.id,
            ProspectModel.email == email,
        )
    )
    if existing:
        return existing
    prospect = ProspectModel(
        owner_user_id=owner.id,
        name=name,
        title="Contact",
        company="CSV import",
        email=email,
        deal_status="open",
    )
    db.add(prospect)
    db.flush()
    return prospect


@app.get("/gift-orders/import/template")
def download_gift_order_csv_template(
    current_user: UserModel = Depends(get_current_user),
) -> PlainTextResponse:
    """Blank CSV template (headers only) for bulk cookie orders."""
    _ = current_user
    return PlainTextResponse(
        content=template_csv(),
        media_type="text/csv; charset=utf-8",
        headers={
            "Content-Disposition": 'attachment; filename="cookie-orders-template.csv"',
        },
    )


@app.get("/gift-orders/import/example")
def download_gift_order_csv_example(
    current_user: UserModel = Depends(get_current_user),
) -> PlainTextResponse:
    """Example CSV with headers and sample rows."""
    _ = current_user
    return PlainTextResponse(
        content=example_csv(),
        media_type="text/csv; charset=utf-8",
        headers={
            "Content-Disposition": 'attachment; filename="cookie-orders-example.csv"',
        },
    )


@app.post("/gift-orders/import", response_model=GiftOrderImportResponse, status_code=201)
async def import_gift_orders_csv(
    request: Request,
    file: UploadFile = File(...),
    current_user: UserModel = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> GiftOrderImportResponse:
    """Create multiple cookie orders from a CSV upload.

    Columns: Name, Email, Cookies (1 / 4 / 12), Address (optional).
    Rows without an address request shipping from the recipient via email after
    payment is authorized. Guests cannot import.
    """
    _enforce_order_create_rate_limit(request, current_user)
    if current_user.role == "guest":
        raise HTTPException(
            status_code=403,
            detail="Guest accounts cannot import orders. Please create an account.",
        )

    filename = (file.filename or "").lower()
    if filename and not filename.endswith(".csv"):
        raise HTTPException(status_code=400, detail="Please upload a .csv file.")

    raw = await file.read()
    if not raw:
        raise HTTPException(status_code=400, detail="CSV file is empty.")
    if len(raw) > settings.csv_import_max_bytes:
        raise HTTPException(
            status_code=400,
            detail=(
                f"CSV file is too large "
                f"(max {settings.csv_import_max_bytes // 1024} KB)."
            ),
        )

    parsed_rows, parse_errors = parse_gift_orders_csv(raw)
    if parse_errors:
        raise HTTPException(
            status_code=400,
            detail={
                "message": "CSV validation failed. No orders were created.",
                "errors": [{"row": e.row, "message": e.message} for e in parse_errors],
            },
        )

    created: list[GiftOrderCreateResponse] = []
    staged_orders: list[GiftOrderModel] = []
    batch_checkout_url: str | None = None

    try:
        for row in parsed_rows:
            prospect = _find_or_create_prospect_for_import(
                owner=current_user,
                name=row.recipient_name,
                email=row.recipient_email,
                db=db,
            )
            if row.request_recipient_address:
                token, expires_at = _mint_address_request_token()
                order = GiftOrderModel(
                    owner_user_id=current_user.id,
                    prospect_id=prospect.id,
                    gift_id=row.gift_id,
                    recipient_name=row.recipient_name,
                    shipping_address=None,
                    recipient_email=row.recipient_email,
                    note=DEFAULT_IMPORT_NOTE,
                    status="no_address",
                    payment_status="pending",
                    address_request_token=token,
                    address_request_expires_at=expires_at,
                    address_request_sent_at=None,
                )
            else:
                order = GiftOrderModel(
                    owner_user_id=current_user.id,
                    prospect_id=prospect.id,
                    gift_id=row.gift_id,
                    recipient_name=row.recipient_name,
                    shipping_address=row.shipping_address,
                    recipient_email=row.recipient_email,
                    note=DEFAULT_IMPORT_NOTE,
                    status="pending_payment",
                    payment_status="pending",
                )
            db.add(order)
            staged_orders.append(order)

        db.commit()
        for order in staged_orders:
            db.refresh(order)

        known_address = [
            o for o in staged_orders if o.status == "pending_payment" and o.shipping_address
        ]
        needs_address = [o for o in staged_orders if o.status == "no_address"]

        checkout_by_id: dict[int, str | None] = {}

        if known_address:
            batch_checkout_url = create_checkout_session_for_orders(
                known_address, current_user, db
            )
            for order in known_address:
                db.refresh(order)
                checkout_by_id[order.id] = batch_checkout_url

        for order in needs_address:
            checkout_url = create_checkout_session_for_order(order, current_user, db)
            db.refresh(order)
            checkout_by_id[order.id] = checkout_url

        for order in staged_orders:
            response = _gift_order_response(order)
            created.append(
                GiftOrderCreateResponse(
                    **response.model_dump(),
                    checkout_url=checkout_by_id.get(order.id),
                )
            )
    except Exception:
        # Roll back any orders created for this batch so a failed Stripe setup
        # does not leave unpaid orphans behind.
        for order in staged_orders:
            db_order = db.get(GiftOrderModel, order.id) if order.id else None
            if db_order:
                db.delete(db_order)
        db.commit()
        raise

    return GiftOrderImportResponse(created=created, batch_checkout_url=batch_checkout_url)


@app.get("/public/address-requests/{token}", response_model=AddressRequestPublicResponse)
def get_address_request(token: str, db: Session = Depends(get_db)) -> AddressRequestPublicResponse:
    order = _get_order_by_address_token(token, db)
    return AddressRequestPublicResponse(
        recipient_name=order.recipient_name,
        gift_id=order.gift_id,
        note=order.note,
        already_submitted=order.status != "no_address" or bool(order.shipping_address),
    )


@app.post("/public/address-requests/{token}", response_model=AddressRequestPublicResponse)
def submit_address_request(
    token: str,
    payload: AddressSubmitRequest,
    db: Session = Depends(get_db),
) -> AddressRequestPublicResponse:
    order = _get_order_by_address_token(token, db)
    if order.status != "no_address" or order.shipping_address:
        return AddressRequestPublicResponse(
            recipient_name=order.recipient_name,
            gift_id=order.gift_id,
            note=order.note,
            already_submitted=True,
        )
    if order.payment_status != "authorized":
        raise HTTPException(
            status_code=400,
            detail="This gift is not ready for an address yet. Please try again later.",
        )

    address = payload.shipping_address.strip()
    values: dict[str, str] = {"shipping_address": address}
    if payload.recipient_name:
        values["recipient_name"] = payload.recipient_name.strip()

    # Atomic claim: only one concurrent submit can transition no_address → address set.
    result = db.execute(
        update(GiftOrderModel)
        .where(
            GiftOrderModel.id == order.id,
            GiftOrderModel.status == "no_address",
            GiftOrderModel.payment_status == "authorized",
            or_(
                GiftOrderModel.shipping_address.is_(None),
                GiftOrderModel.shipping_address == "",
            ),
        )
        .values(**values)
    )
    db.commit()
    if result.rowcount == 0:
        db.refresh(order)
        return AddressRequestPublicResponse(
            recipient_name=order.recipient_name,
            gift_id=order.gift_id,
            note=order.note,
            already_submitted=True,
        )

    db.refresh(order)

    try:
        # Capture the held payment now that we have a ship-to address.
        order = capture_authorized_order(order, db)
    except HTTPException:
        # Keep the link usable if capture fails (e.g. expired auth hold).
        order.shipping_address = None
        db.add(order)
        db.commit()
        raise

    # One-time link: clear token after successful capture so PII is not re-fetchable.
    _clear_address_request_token(order)
    db.add(order)
    db.commit()
    db.refresh(order)

    owner = db.get(UserModel, order.owner_user_id)
    if owner:
        send_orderer_address_received(
            order_id=order.id,
            orderer_email=owner.email,
            recipient_name=order.recipient_name,
            shipping_address=address,
            order_url=_order_detail_url(order.id),
        )

    return AddressRequestPublicResponse(
        recipient_name=order.recipient_name,
        gift_id=order.gift_id,
        note=order.note,
        already_submitted=True,
    )


@app.post("/gift-orders/{order_id}/checkout", response_model=StripeCheckoutResponse)
def checkout_gift_order(
    order_id: int,
    request: Request,
    current_user: UserModel = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> StripeCheckoutResponse:
    _enforce_order_create_rate_limit(request, current_user)
    order = db.get(GiftOrderModel, order_id)
    if not order or order.owner_user_id != current_user.id:
        raise HTTPException(status_code=404, detail="Gift order not found.")

    checkout_url = create_checkout_session_for_order(order, current_user, db)
    return StripeCheckoutResponse(checkout_url=checkout_url)


@app.get("/gift-orders", response_model=list[GiftOrderResponse])
def list_gift_orders(
    current_user: UserModel = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[GiftOrderResponse]:
    records = db.scalars(
        select(GiftOrderModel)
        .where(GiftOrderModel.owner_user_id == current_user.id)
        .order_by(GiftOrderModel.requested_at.desc())
    ).all()
    return [_gift_order_response(record) for record in records]


@app.get("/gift-orders/{order_id}", response_model=GiftOrderResponse)
def get_gift_order(
    order_id: int,
    current_user: UserModel = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> GiftOrderResponse:
    order = db.get(GiftOrderModel, order_id)
    if not order or order.owner_user_id != current_user.id:
        raise HTTPException(status_code=404, detail="Gift order not found.")
    order = sync_order_payment_from_stripe(order, db)
    return _gift_order_response(order)


@app.get("/admin/gift-orders", response_model=list[AdminGiftOrderResponse])
def admin_list_gift_orders(
    status: str | None = None,
    _admin: UserModel = Depends(get_current_admin),
    db: Session = Depends(get_db),
) -> list[AdminGiftOrderResponse]:
    query = select(GiftOrderModel).order_by(GiftOrderModel.requested_at.desc())
    if status and status != "all":
        query = query.where(GiftOrderModel.status == status)
    records = db.scalars(query).all()

    responses: list[AdminGiftOrderResponse] = []
    for order in records:
        owner = db.get(UserModel, order.owner_user_id)
        prospect = db.get(ProspectModel, order.prospect_id)
        responses.append(_admin_gift_order_response(order, owner, prospect))
    return responses


@app.get("/admin/gift-orders/{order_id}", response_model=AdminGiftOrderResponse)
def admin_get_gift_order(
    order_id: int,
    _admin: UserModel = Depends(get_current_admin),
    db: Session = Depends(get_db),
) -> AdminGiftOrderResponse:
    order = db.get(GiftOrderModel, order_id)
    if not order:
        raise HTTPException(status_code=404, detail="Gift order not found.")
    owner = db.get(UserModel, order.owner_user_id)
    prospect = db.get(ProspectModel, order.prospect_id)
    return _admin_gift_order_response(order, owner, prospect)


@app.patch("/admin/gift-orders/{order_id}", response_model=AdminGiftOrderResponse)
def admin_update_gift_order(
    order_id: int,
    payload: AdminOrderUpdateRequest,
    _admin: UserModel = Depends(get_current_admin),
    db: Session = Depends(get_db),
) -> AdminGiftOrderResponse:
    order = db.get(GiftOrderModel, order_id)
    if not order:
        raise HTTPException(status_code=404, detail="Gift order not found.")

    if payload.status is not None:
        # Unpaid orders stay in pre-pay statuses (or can be canceled). Paid
        # orders move through fulfillment statuses.
        unpaid_allowed = {"no_address", "pending_payment", "canceled"}
        if order.payment_status != "paid" and payload.status not in unpaid_allowed:
            raise HTTPException(
                status_code=400,
                detail="Order must be paid before it can move through fulfillment.",
            )
        if order.payment_status == "paid" and payload.status in {"no_address", "pending_payment"}:
            raise HTTPException(
                status_code=400,
                detail="Paid orders cannot return to a pre-payment status.",
            )
        if payload.status == "canceled" and order.payment_status == "authorized":
            cancel_payment_authorization(order)
            order.payment_status = "canceled"
            _clear_address_request_token(order)
        order.status = payload.status
    if payload.tracking_number is not None:
        order.tracking_number = payload.tracking_number.strip() or None
    if payload.admin_notes is not None:
        order.admin_notes = payload.admin_notes.strip() or None

    db.add(order)
    db.commit()
    db.refresh(order)

    owner = db.get(UserModel, order.owner_user_id)
    prospect = db.get(ProspectModel, order.prospect_id)
    return _admin_gift_order_response(order, owner, prospect)


def _integration_response(row: IntegrationConnectionModel) -> IntegrationConnectionResponse:
    return IntegrationConnectionResponse(
        id=row.id,
        provider=row.provider,
        enabled=row.enabled,
        trigger_stage_name=row.trigger_stage_name,
        external_org_id=row.external_org_id,
        instance_url=row.instance_url,
        last_polled_at=row.last_polled_at,
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


def _require_registered_user(user: UserModel) -> None:
    if user.role == "guest":
        raise HTTPException(
            status_code=403,
            detail="Integrations are not available for guest accounts.",
        )


@app.get("/integrations", response_model=list[IntegrationConnectionResponse])
def list_integrations(
    current_user: UserModel = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[IntegrationConnectionResponse]:
    _require_registered_user(current_user)
    rows = db.scalars(
        select(IntegrationConnectionModel).where(
            IntegrationConnectionModel.owner_user_id == current_user.id
        )
    ).all()
    return [_integration_response(row) for row in rows]


@app.get("/integrations/salesforce/connect", response_model=SalesforceConnectResponse)
def salesforce_connect(
    current_user: UserModel = Depends(get_current_user),
) -> SalesforceConnectResponse:
    _require_registered_user(current_user)
    if not sf.salesforce_configured():
        raise HTTPException(
            status_code=503,
            detail=(
                "Salesforce is not configured. "
                "Set SALESFORCE_CLIENT_ID and SALESFORCE_CLIENT_SECRET."
            ),
        )
    return SalesforceConnectResponse(authorize_url=sf.build_authorize_url(current_user.id))


@app.get("/integrations/salesforce/callback")
def salesforce_oauth_callback(
    code: str | None = None,
    state: str | None = None,
    error: str | None = None,
    error_description: str | None = None,
    db: Session = Depends(get_db),
):
    from urllib.parse import quote

    web = settings.web_base_url.rstrip("/")
    if error:
        detail = quote(error_description or error, safe="")
        return RedirectResponse(f"{web}/integrations?error={detail}")
    if not code or not state:
        return RedirectResponse(f"{web}/integrations?error=missing_oauth_params")
    user_id = sf.verify_oauth_state(state)
    if user_id is None:
        return RedirectResponse(f"{web}/integrations?error=invalid_oauth_state")
    try:
        tokens = sf.exchange_code_for_tokens(code)
        sf.upsert_connection_from_oauth(db, user_id=user_id, token_payload=tokens)
    except Exception:
        return RedirectResponse(f"{web}/integrations?error=oauth_exchange_failed")
    return RedirectResponse(f"{web}/integrations?connected=salesforce")


@app.patch("/integrations/{connection_id}", response_model=IntegrationConnectionResponse)
def update_integration(
    connection_id: int,
    payload: IntegrationUpdateRequest,
    current_user: UserModel = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> IntegrationConnectionResponse:
    _require_registered_user(current_user)
    row = db.get(IntegrationConnectionModel, connection_id)
    if not row or row.owner_user_id != current_user.id:
        raise HTTPException(status_code=404, detail="Integration not found.")
    if payload.trigger_stage_name is not None:
        row.trigger_stage_name = payload.trigger_stage_name
    if payload.enabled is not None:
        row.enabled = payload.enabled
    row.updated_at = datetime.now(UTC)
    db.commit()
    db.refresh(row)
    return _integration_response(row)


@app.delete("/integrations/{connection_id}", response_model=IntegrationConnectionResponse)
def disconnect_integration(
    connection_id: int,
    current_user: UserModel = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> IntegrationConnectionResponse:
    _require_registered_user(current_user)
    row = db.get(IntegrationConnectionModel, connection_id)
    if not row or row.owner_user_id != current_user.id:
        raise HTTPException(status_code=404, detail="Integration not found.")
    response = _integration_response(row)
    db.delete(row)
    db.commit()
    return response


@app.post("/integrations/salesforce/events")
def salesforce_stage_event(
    payload: SalesforceEventRequest,
    request: Request,
    db: Session = Depends(get_db),
) -> dict:
    """Immediate intake for Demo Completed (or configured stage) from Salesforce Flow."""
    auth = request.headers.get("Authorization", "")
    bearer = auth.removeprefix("Bearer ").strip() if auth.lower().startswith("bearer ") else ""
    secret = request.headers.get("X-Webhook-Secret") or bearer
    if not sf.verify_webhook_secret(secret or None):
        raise HTTPException(status_code=401, detail="Invalid webhook secret.")

    connection: IntegrationConnectionModel | None = None
    if payload.connection_id is not None:
        connection = db.get(IntegrationConnectionModel, payload.connection_id)
    elif payload.org_id:
        connection = db.scalar(
            select(IntegrationConnectionModel).where(
                IntegrationConnectionModel.provider == PROVIDER_SALESFORCE,
                IntegrationConnectionModel.external_org_id == payload.org_id,
                IntegrationConnectionModel.enabled.is_(True),
            )
        )
    else:
        connection = db.scalar(
            select(IntegrationConnectionModel).where(
                IntegrationConnectionModel.provider == PROVIDER_SALESFORCE,
                IntegrationConnectionModel.enabled.is_(True),
            )
        )

    if not connection or connection.provider != PROVIDER_SALESFORCE:
        raise HTTPException(status_code=404, detail="Salesforce connection not found.")

    return process_stage_completed_reminder(
        db,
        connection=connection,
        opportunity_id=payload.opportunity_id,
        stage_name=payload.stage_name,
        contact_name=payload.contact_name,
        contact_email=str(payload.contact_email),
        contact_title=payload.contact_title,
        company=payload.company,
    )


@app.post("/integrations/salesforce/sync")
def salesforce_sync(
    current_user: UserModel = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    """Poll Salesforce for recent Demo Completed opportunities (near-immediate fallback)."""
    _require_registered_user(current_user)
    connection = db.scalar(
        select(IntegrationConnectionModel).where(
            IntegrationConnectionModel.owner_user_id == current_user.id,
            IntegrationConnectionModel.provider == PROVIDER_SALESFORCE,
        )
    )
    if not connection:
        raise HTTPException(status_code=404, detail="Salesforce is not connected.")
    if not connection.enabled:
        raise HTTPException(status_code=400, detail="Salesforce connection is disabled.")
    try:
        results = sf.poll_demo_completed(connection, db)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Salesforce sync failed: {exc}") from exc
    return {"results": results, "count": len(results)}


@app.get("/integrations/hubspot/connect", response_model=HubSpotConnectResponse)
def hubspot_connect(
    current_user: UserModel = Depends(get_current_user),
) -> HubSpotConnectResponse:
    _require_registered_user(current_user)
    if not hs.hubspot_configured():
        raise HTTPException(
            status_code=503,
            detail=(
                "HubSpot is not configured. "
                "Set HUBSPOT_CLIENT_ID and HUBSPOT_CLIENT_SECRET."
            ),
        )
    return HubSpotConnectResponse(authorize_url=hs.build_authorize_url(current_user.id))


@app.get("/integrations/hubspot/callback")
def hubspot_oauth_callback(
    code: str | None = None,
    state: str | None = None,
    error: str | None = None,
    error_description: str | None = None,
    db: Session = Depends(get_db),
):
    from urllib.parse import quote

    web = settings.web_base_url.rstrip("/")
    if error:
        detail = quote(error_description or error, safe="")
        return RedirectResponse(f"{web}/integrations?error={detail}")
    if not code or not state:
        return RedirectResponse(f"{web}/integrations?error=missing_oauth_params")
    user_id = hs.verify_oauth_state(state)
    if user_id is None:
        return RedirectResponse(f"{web}/integrations?error=invalid_oauth_state")
    try:
        tokens = hs.exchange_code_for_tokens(code)
        hs.upsert_connection_from_oauth(db, user_id=user_id, token_payload=tokens)
    except Exception:
        return RedirectResponse(f"{web}/integrations?error=oauth_exchange_failed")
    return RedirectResponse(f"{web}/integrations?connected=hubspot")


@app.post("/integrations/hubspot/events")
def hubspot_stage_event(
    payload: HubSpotEventRequest,
    request: Request,
    db: Session = Depends(get_db),
) -> dict:
    """Immediate intake for Demo Completed (or configured stage) from HubSpot workflow."""
    auth = request.headers.get("Authorization", "")
    bearer = auth.removeprefix("Bearer ").strip() if auth.lower().startswith("bearer ") else ""
    secret = request.headers.get("X-Webhook-Secret") or bearer
    if not hs.verify_webhook_secret(secret or None):
        raise HTTPException(status_code=401, detail="Invalid webhook secret.")

    connection: IntegrationConnectionModel | None = None
    if payload.connection_id is not None:
        connection = db.get(IntegrationConnectionModel, payload.connection_id)
    elif payload.portal_id:
        connection = db.scalar(
            select(IntegrationConnectionModel).where(
                IntegrationConnectionModel.provider == PROVIDER_HUBSPOT,
                IntegrationConnectionModel.external_org_id == payload.portal_id,
                IntegrationConnectionModel.enabled.is_(True),
            )
        )
    else:
        connection = db.scalar(
            select(IntegrationConnectionModel).where(
                IntegrationConnectionModel.provider == PROVIDER_HUBSPOT,
                IntegrationConnectionModel.enabled.is_(True),
            )
        )

    if not connection or connection.provider != PROVIDER_HUBSPOT:
        raise HTTPException(status_code=404, detail="HubSpot connection not found.")

    return process_stage_completed_reminder(
        db,
        connection=connection,
        opportunity_id=payload.deal_id,
        stage_name=payload.stage_name,
        contact_name=payload.contact_name,
        contact_email=str(payload.contact_email),
        contact_title=payload.contact_title,
        company=payload.company,
    )


@app.post("/integrations/hubspot/sync")
def hubspot_sync(
    current_user: UserModel = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    """Poll HubSpot for recent Demo Completed deals (near-immediate fallback)."""
    _require_registered_user(current_user)
    connection = db.scalar(
        select(IntegrationConnectionModel).where(
            IntegrationConnectionModel.owner_user_id == current_user.id,
            IntegrationConnectionModel.provider == PROVIDER_HUBSPOT,
        )
    )
    if not connection:
        raise HTTPException(status_code=404, detail="HubSpot is not connected.")
    if not connection.enabled:
        raise HTTPException(status_code=400, detail="HubSpot connection is disabled.")
    try:
        results = hs.poll_demo_completed(connection, db)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"HubSpot sync failed: {exc}") from exc
    return {"results": results, "count": len(results)}
