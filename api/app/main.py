from contextlib import asynccontextmanager
from datetime import datetime
from secrets import token_urlsafe

import bcrypt
from fastapi import Depends, FastAPI, File, HTTPException, Response, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import PlainTextResponse
from pydantic import BaseModel, EmailStr, Field, field_validator, model_validator
import stripe
from sqlalchemy import select
from sqlalchemy.orm import Session

from .config import is_known_gift, settings
from .csv_import import (
    DEFAULT_IMPORT_NOTE,
    example_csv,
    parse_gift_orders_csv,
    template_csv,
)
from .db import SessionLocal
from .models import GiftOrderModel, ProspectModel, UserModel
from .order_email import send_orderer_address_received
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
    password: str = Field(min_length=8)


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


def get_current_user(request: Request, response: Response, db: Session = Depends(get_db)) -> UserModel:
    session_id = request.cookies.get(settings.session_cookie_name)
    session = refresh_session_if_needed(session_id)
    if not session:
        raise HTTPException(status_code=401, detail="Not authenticated.")

    user = db.get(UserModel, session.user_id)
    if not user:
        delete_session(session.session_id)
        response.delete_cookie(key=settings.session_cookie_name)
        raise HTTPException(status_code=401, detail="Not authenticated.")

    user = _sync_admin_role(user, db)
    _set_session_cookie(response, session.session_id, persistent=user.role != "guest")
    return user


def get_current_admin(current_user: UserModel = Depends(get_current_user)) -> UserModel:
    if current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Admin access required.")
    return current_user


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "env": settings.app_env}


@app.get("/gifts", response_model=list[GiftCatalogItem])
def list_gifts() -> list[GiftCatalogItem]:
    return [GiftCatalogItem(**item) for item in list_gift_prices()]


@app.post("/auth/login")
def login(payload: LoginRequest, request: Request, response: Response, db: Session = Depends(get_db)) -> dict[str, str]:
    email = _normalize_email(payload.email)
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
    existing = db.scalar(select(UserModel).where(UserModel.email == email))
    if existing:
        raise HTTPException(status_code=409, detail="Email already in use.")

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
    current_user: UserModel = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> GiftOrderCreateResponse:
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
        token = token_urlsafe(32)
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
    file: UploadFile = File(...),
    current_user: UserModel = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> GiftOrderImportResponse:
    """Create multiple cookie orders from a CSV upload.

    Columns: Name, Email, Cookies (1 / 4 / 12), Address (optional).
    Rows without an address request shipping from the recipient via email after
    payment is authorized. Guests cannot import.
    """
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
                    address_request_token=token_urlsafe(32),
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
    order = db.scalar(
        select(GiftOrderModel).where(GiftOrderModel.address_request_token == token)
    )
    if not order:
        raise HTTPException(status_code=404, detail="This address link is invalid or has expired.")
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
    order = db.scalar(
        select(GiftOrderModel).where(GiftOrderModel.address_request_token == token)
    )
    if not order:
        raise HTTPException(status_code=404, detail="This address link is invalid or has expired.")
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
    if payload.recipient_name:
        order.recipient_name = payload.recipient_name
    order.shipping_address = address
    db.add(order)
    db.commit()
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
    current_user: UserModel = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> StripeCheckoutResponse:
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
