from contextlib import asynccontextmanager
from datetime import datetime

import bcrypt
from fastapi import Depends, FastAPI, HTTPException, Response, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, EmailStr, Field, field_validator
import stripe
from sqlalchemy import select
from sqlalchemy.orm import Session

from .config import is_known_gift, settings
from .db import SessionLocal
from .models import GiftOrderModel, ProspectModel, UserModel
from .session_store import delete_session, purge_expired_sessions, refresh_session_if_needed, rotate_session
from .stripe_payments import (
    create_checkout_session_for_order,
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
    shipping_address: str = Field(min_length=1, max_length=1000)
    note: str = Field(min_length=1, max_length=1000)

    @field_validator("recipient_name", "shipping_address", "note")
    @classmethod
    def _reject_blank(cls, value: str) -> str:
        # min_length only guards raw length; reject whitespace-only values so a
        # gift never ships without a recipient, address, or note on the gift.
        if not value.strip():
            raise ValueError("must not be blank")
        return value


class GiftOrderResponse(BaseModel):
    id: int
    prospect_id: int
    gift_id: str
    recipient_name: str
    shipping_address: str
    note: str
    status: str
    payment_status: str
    tracking_number: str | None = None
    requested_at: datetime


class GiftOrderCreateResponse(GiftOrderResponse):
    checkout_url: str | None = None


class StripeCheckoutResponse(BaseModel):
    checkout_url: str


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
    status: str | None = Field(default=None, pattern="^(queued|ordered|shipped|delivered|canceled)$")
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


def _set_session_cookie(response: Response, session_id: str) -> None:
    response.set_cookie(
        key=settings.session_cookie_name,
        value=session_id,
        httponly=True,
        secure=settings.session_cookie_secure,
        samesite="lax",
        max_age=60 * 60 * settings.session_ttl_hours,
    )


def _normalize_email(email: str) -> str:
    return email.strip().lower()


def _sync_admin_role(user: UserModel, db: Session) -> UserModel:
    expected_role = "admin" if user.email in settings.admin_emails else "user"
    if user.role != expected_role:
        user.role = expected_role
        db.add(user)
        db.commit()
        db.refresh(user)
    return user


def _gift_order_response(order: GiftOrderModel) -> GiftOrderResponse:
    return GiftOrderResponse(
        id=order.id,
        prospect_id=order.prospect_id,
        gift_id=order.gift_id,
        recipient_name=order.recipient_name,
        shipping_address=order.shipping_address,
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
    _set_session_cookie(response, session.session_id)
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
    if not user or not verify_password(payload.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Invalid email or password.")

    user = _sync_admin_role(user, db)
    previous_session_id = request.cookies.get(settings.session_cookie_name)
    session = rotate_session(previous_session_id, user.id)
    _set_session_cookie(response, session.session_id)
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
    session = rotate_session(previous_session_id, user.id)
    _set_session_cookie(response, session.session_id)
    return {"message": "Signed up."}


@app.post("/auth/logout")
def logout(request: Request, response: Response) -> dict[str, str]:
    session_id = request.cookies.get(settings.session_cookie_name)
    delete_session(session_id)
    response.delete_cookie(key=settings.session_cookie_name)
    return {"message": "Logged out."}


@app.get("/auth/me")
def me(current_user: UserModel = Depends(get_current_user)) -> dict[str, str | int]:
    return {"user_id": current_user.id, "email": current_user.email, "role": current_user.role}


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

    order = GiftOrderModel(
        owner_user_id=current_user.id,
        prospect_id=payload.prospect_id,
        gift_id=payload.gift_id.strip(),
        recipient_name=payload.recipient_name.strip(),
        shipping_address=payload.shipping_address.strip(),
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
        if order.payment_status != "paid" and payload.status != "canceled":
            raise HTTPException(
                status_code=400,
                detail="Order must be paid before it can move through fulfillment.",
            )
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
