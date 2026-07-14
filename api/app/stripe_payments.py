"""Stripe one-time Checkout for gift orders."""

from __future__ import annotations

import time

import stripe
from fastapi import HTTPException
from sqlalchemy.orm import Session

from .config import GIFT_CATALOG, settings, stripe_price_for_gift
from .models import GiftOrderModel, ProspectModel, UserModel
from .order_email import send_new_order_notification


def _field(obj: object, key: str, default: object | None = None) -> object | None:
    """Read a field from a Stripe object or plain dict.

    stripe-python 15's ``StripeObject`` no longer supports dict-style ``.get()``,
    so this reads via subscript and falls back to ``default`` when the key is
    absent (works for both ``StripeObject`` and plain ``dict``).
    """
    try:
        return obj[key]  # type: ignore[index]
    except (KeyError, TypeError):
        return default


def ensure_stripe_configured() -> None:
    if not settings.stripe_secret_key:
        raise HTTPException(status_code=503, detail="Payments are not configured.")
    stripe.api_key = settings.stripe_secret_key


def ensure_stripe_webhook_configured() -> None:
    if not settings.stripe_secret_key or not settings.stripe_webhook_secret:
        raise HTTPException(status_code=503, detail="Payment webhooks are not configured.")
    stripe.api_key = settings.stripe_secret_key


# Cache live Stripe price lookups so the public /gifts endpoint does not hit
# Stripe on every page load. (price_id -> (fetched_at_monotonic, unit_amount, currency))
_PRICE_CACHE: dict[str, tuple[float, int | None, str | None]] = {}
_PRICE_CACHE_TTL_SECONDS = 300


def _price_amount(price_id: str) -> tuple[int | None, str | None]:
    now = time.monotonic()
    cached = _PRICE_CACHE.get(price_id)
    if cached and now - cached[0] < _PRICE_CACHE_TTL_SECONDS:
        return cached[1], cached[2]
    price = stripe.Price.retrieve(price_id)
    unit_amount = _field(price, "unit_amount")
    currency = _field(price, "currency")
    _PRICE_CACHE[price_id] = (now, unit_amount, currency)
    return unit_amount, currency


def list_gift_prices() -> list[dict]:
    """Return the catalog with live Stripe unit amounts.

    Amounts are `None` when Stripe is not configured or a price lookup fails, so
    the UI can fall back gracefully instead of showing a hardcoded number.
    """
    stripe_ready = bool(settings.stripe_secret_key)
    if stripe_ready:
        stripe.api_key = settings.stripe_secret_key

    amount_by_price: dict[str, tuple[int | None, str | None]] = {}
    results: list[dict] = []
    for item in GIFT_CATALOG:
        gift_id = str(item["id"])
        price_id = stripe_price_for_gift(gift_id)
        unit_amount: int | None = None
        currency: str | None = None
        if stripe_ready and price_id:
            if price_id not in amount_by_price:
                try:
                    amount_by_price[price_id] = _price_amount(price_id)
                except Exception:
                    amount_by_price[price_id] = (None, None)
            unit_amount, currency = amount_by_price[price_id]
        results.append(
            {
                "gift_id": gift_id,
                "cookie_count": int(item["cookie_count"]),
                "unit_amount": unit_amount,
                "currency": currency,
            }
        )
    return results


def resolve_stripe_price_id(gift_id: str) -> str:
    price_id = stripe_price_for_gift(gift_id)
    if not price_id:
        raise HTTPException(
            status_code=503,
            detail=f"No Stripe price configured for gift '{gift_id}'.",
        )
    return price_id


def mark_order_paid(order: GiftOrderModel, db: Session) -> GiftOrderModel:
    if order.payment_status == "paid":
        return order

    order.payment_status = "paid"
    order.status = "queued"
    db.add(order)
    db.commit()
    db.refresh(order)

    prospect = db.get(ProspectModel, order.prospect_id)
    owner = db.get(UserModel, order.owner_user_id)
    if prospect and owner:
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
            placed_by_email=owner.email,
        )
    return order


def sync_order_payment_from_stripe(order: GiftOrderModel, db: Session) -> GiftOrderModel:
    if order.payment_status == "paid" or not order.stripe_checkout_session_id:
        return order

    ensure_stripe_configured()
    session = stripe.checkout.Session.retrieve(order.stripe_checkout_session_id)
    if _field(session, "payment_status") == "paid":
        return mark_order_paid(order, db)
    return order


def _ensure_stripe_customer(current_user: UserModel, db: Session) -> str:
    """Return the user's Stripe customer id, creating and persisting one if needed.

    Reusing a single customer per user keeps their orders grouped in the Stripe
    dashboard instead of creating a fresh guest customer on every checkout.
    """
    if current_user.stripe_customer_id:
        return current_user.stripe_customer_id

    customer = stripe.Customer.create(
        email=current_user.email,
        metadata={"user_id": str(current_user.id)},
    )
    current_user.stripe_customer_id = customer["id"]
    db.add(current_user)
    db.commit()
    db.refresh(current_user)
    return current_user.stripe_customer_id


def _reuse_open_checkout_session(order: GiftOrderModel) -> str | None:
    """Return the URL of the order's existing Checkout Session if it is still open.

    Prevents repeated checkout attempts from creating multiple payable sessions
    for the same order (which could let a user be charged more than once).
    """
    if not order.stripe_checkout_session_id:
        return None
    try:
        session = stripe.checkout.Session.retrieve(order.stripe_checkout_session_id)
    except stripe.error.StripeError:
        return None
    if _field(session, "status") == "open" and _field(session, "url"):
        return session["url"]
    return None


def create_checkout_session_for_order(
    order: GiftOrderModel,
    current_user: UserModel,
    db: Session,
) -> str:
    if order.payment_status == "paid":
        raise HTTPException(status_code=400, detail="This order is already paid.")
    if order.status not in {"pending_payment"}:
        raise HTTPException(status_code=400, detail="This order cannot be paid.")

    ensure_stripe_configured()

    reusable_url = _reuse_open_checkout_session(order)
    if reusable_url:
        return reusable_url

    price_id = resolve_stripe_price_id(order.gift_id)

    customer_id = _ensure_stripe_customer(current_user, db)

    session_params: dict = {
        "mode": "payment",
        "line_items": [{"price": price_id, "quantity": 1}],
        "success_url": f"{settings.web_base_url}/orders/{order.id}?payment=success",
        "cancel_url": f"{settings.web_base_url}/orders/{order.id}?payment=cancel",
        "metadata": {
            "gift_order_id": str(order.id),
            "user_id": str(current_user.id),
        },
        "customer": customer_id,
        "allow_promotion_codes": True,
    }

    session = stripe.checkout.Session.create(**session_params)
    order.stripe_checkout_session_id = session["id"]
    order.stripe_price_id = price_id
    db.add(order)
    db.commit()
    db.refresh(order)
    return session["url"]


def fulfill_order_from_checkout_session(session: dict, db: Session) -> None:
    if _field(session, "mode") != "payment":
        return

    metadata = _field(session, "metadata", {}) or {}
    gift_order_id = _field(metadata, "gift_order_id")
    if not gift_order_id:
        return

    try:
        order_id = int(gift_order_id)
    except ValueError:
        return

    order = db.get(GiftOrderModel, order_id)
    if not order:
        return

    if _field(session, "id"):
        order.stripe_checkout_session_id = session["id"]
    mark_order_paid(order, db)
