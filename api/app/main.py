from contextlib import asynccontextmanager
from datetime import datetime

import bcrypt
from fastapi import Depends, FastAPI, HTTPException, Response, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, EmailStr, Field
import stripe
from sqlalchemy import select
from sqlalchemy.orm import Session

from .config import settings
from .db import SessionLocal
from .models import GiftOrderModel, ProspectModel, UserModel
from .order_email import send_new_order_notification
from .session_store import delete_session, purge_expired_sessions, refresh_session_if_needed, rotate_session


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


class GiftOrderResponse(BaseModel):
    id: int
    prospect_id: int
    gift_id: str
    recipient_name: str
    shipping_address: str
    note: str
    status: str
    requested_at: datetime


class BillingStatusResponse(BaseModel):
    email: str
    subscription_status: str
    subscription_plan: str
    has_payment_method: bool


class StripeCheckoutResponse(BaseModel):
    checkout_url: str


class StripePortalResponse(BaseModel):
    portal_url: str


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


def _ensure_stripe_configured() -> None:
    if not settings.stripe_secret_key or not settings.stripe_price_id:
        raise HTTPException(status_code=503, detail="Billing is not configured.")
    stripe.api_key = settings.stripe_secret_key


def _ensure_stripe_webhook_configured() -> None:
    if not settings.stripe_secret_key or not settings.stripe_webhook_secret:
        raise HTTPException(status_code=503, detail="Billing webhook is not configured.")
    stripe.api_key = settings.stripe_secret_key


def _sync_subscription_from_stripe_customer(user: UserModel, db: Session) -> UserModel:
    if not user.stripe_customer_id:
        return user

    _ensure_stripe_configured()
    subscriptions = stripe.Subscription.list(customer=user.stripe_customer_id, limit=1)
    if subscriptions.data:
        latest = subscriptions.data[0]
        price_id = latest["items"]["data"][0]["price"]["id"] if latest["items"]["data"] else ""
        user.subscription_status = latest["status"]
        user.subscription_plan = "individual" if price_id == settings.stripe_price_id else "paid"
    else:
        user.subscription_status = "inactive"
        user.subscription_plan = "free"
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


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


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "env": settings.app_env}


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


@app.get("/billing/me", response_model=BillingStatusResponse)
def billing_me(
    current_user: UserModel = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> BillingStatusResponse:
    user = _sync_subscription_from_stripe_customer(current_user, db)
    return BillingStatusResponse(
        email=user.email,
        subscription_status=user.subscription_status,
        subscription_plan=user.subscription_plan,
        has_payment_method=user.subscription_status in {"active", "trialing", "past_due"},
    )


@app.post("/billing/checkout", response_model=StripeCheckoutResponse)
def create_checkout_session(
    current_user: UserModel = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> StripeCheckoutResponse:
    _ensure_stripe_configured()

    customer_id = current_user.stripe_customer_id
    if not customer_id:
        customer = stripe.Customer.create(email=current_user.email, metadata={"user_id": str(current_user.id)})
        customer_id = customer["id"]
        current_user.stripe_customer_id = customer_id
        db.add(current_user)
        db.commit()
        db.refresh(current_user)

    session = stripe.checkout.Session.create(
        mode="subscription",
        customer=customer_id,
        line_items=[{"price": settings.stripe_price_id, "quantity": 1}],
        success_url=f"{settings.web_base_url}/billing?checkout=success",
        cancel_url=f"{settings.web_base_url}/billing?checkout=cancel",
        allow_promotion_codes=True,
    )
    return StripeCheckoutResponse(checkout_url=session["url"])


@app.post("/billing/portal", response_model=StripePortalResponse)
def create_customer_portal_session(current_user: UserModel = Depends(get_current_user)) -> StripePortalResponse:
    _ensure_stripe_configured()
    if not current_user.stripe_customer_id:
        raise HTTPException(status_code=400, detail="No Stripe customer found for this account.")
    session = stripe.billing_portal.Session.create(
        customer=current_user.stripe_customer_id,
        return_url=f"{settings.web_base_url}/billing",
    )
    return StripePortalResponse(portal_url=session["url"])


@app.post("/billing/webhook")
async def stripe_webhook(request: Request, db: Session = Depends(get_db)) -> dict[str, bool]:
    _ensure_stripe_webhook_configured()
    payload = await request.body()
    signature = request.headers.get("Stripe-Signature")
    if not signature:
        raise HTTPException(status_code=400, detail="Missing Stripe signature.")
    try:
        event = stripe.Webhook.construct_event(payload, signature, settings.stripe_webhook_secret)
    except stripe.error.SignatureVerificationError:
        raise HTTPException(status_code=400, detail="Invalid Stripe signature.")

    event_type = event["type"]
    data_object = event["data"]["object"]

    if event_type in {"checkout.session.completed", "customer.subscription.updated", "customer.subscription.created"}:
        customer_id = data_object.get("customer")
        status = data_object.get("status")
        if event_type == "checkout.session.completed":
            subscription_id = data_object.get("subscription")
            if subscription_id:
                subscription = stripe.Subscription.retrieve(subscription_id)
                status = subscription["status"]
                price_id = (
                    subscription["items"]["data"][0]["price"]["id"] if subscription["items"]["data"] else ""
                )
            else:
                price_id = ""
        else:
            price_id = data_object["items"]["data"][0]["price"]["id"] if data_object["items"]["data"] else ""

        if customer_id:
            user = db.scalar(select(UserModel).where(UserModel.stripe_customer_id == customer_id))
            if user:
                user.subscription_status = status or "inactive"
                user.subscription_plan = "individual" if price_id == settings.stripe_price_id else "paid"
                db.add(user)
                db.commit()

    if event_type in {"customer.subscription.deleted"}:
        customer_id = data_object.get("customer")
        if customer_id:
            user = db.scalar(select(UserModel).where(UserModel.stripe_customer_id == customer_id))
            if user:
                user.subscription_status = "canceled"
                user.subscription_plan = "free"
                db.add(user)
                db.commit()

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


@app.post("/gift-orders", response_model=GiftOrderResponse, status_code=201)
def create_gift_order(
    payload: GiftOrderCreateRequest,
    current_user: UserModel = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> GiftOrderResponse:
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
        status="queued",
    )
    db.add(order)
    db.commit()
    db.refresh(order)

    send_new_order_notification(
        order_id=order.id,
        requested_at=order.requested_at,
        gift_id=order.gift_id,
        recipient_name=order.recipient_name,
        shipping_address=order.shipping_address,
        note=order.note,
        status=order.status,
        prospect_name=prospect.name,
        prospect_company=prospect.company,
        prospect_title=prospect.title,
        prospect_email=prospect.email,
        prospect_deal_status=prospect.deal_status,
        placed_by_email=current_user.email,
    )

    return GiftOrderResponse(
        id=order.id,
        prospect_id=order.prospect_id,
        gift_id=order.gift_id,
        recipient_name=order.recipient_name,
        shipping_address=order.shipping_address,
        note=order.note,
        status=order.status,
        requested_at=order.requested_at,
    )


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
    return [
        GiftOrderResponse(
            id=record.id,
            prospect_id=record.prospect_id,
            gift_id=record.gift_id,
            recipient_name=record.recipient_name,
            shipping_address=record.shipping_address,
            note=record.note,
            status=record.status,
            requested_at=record.requested_at,
        )
        for record in records
    ]


@app.get("/gift-orders/{order_id}", response_model=GiftOrderResponse)
def get_gift_order(
    order_id: int,
    current_user: UserModel = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> GiftOrderResponse:
    order = db.get(GiftOrderModel, order_id)
    if not order or order.owner_user_id != current_user.id:
        raise HTTPException(status_code=404, detail="Gift order not found.")
    return GiftOrderResponse(
        id=order.id,
        prospect_id=order.prospect_id,
        gift_id=order.gift_id,
        recipient_name=order.recipient_name,
        shipping_address=order.shipping_address,
        note=order.note,
        status=order.status,
        requested_at=order.requested_at,
    )
