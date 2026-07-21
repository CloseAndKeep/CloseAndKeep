"""Stripe one-time Checkout for gift orders."""

from __future__ import annotations

import logging
import time
from datetime import UTC, datetime

import stripe
from fastapi import HTTPException
from sqlalchemy.orm import Session

from .config import GIFT_CATALOG, settings, stripe_price_for_gift
from .models import GiftOrderModel, ProspectModel, UserModel
from .order_email import send_new_order_notification, send_recipient_address_request

logger = logging.getLogger(__name__)


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


def _address_form_url(token: str) -> str:
    return f"{settings.web_base_url.rstrip('/')}/ship/{token}"


def _payment_intent_id_from_session(session: object) -> str | None:
    pi = _field(session, "payment_intent")
    if isinstance(pi, str) and pi:
        return pi
    if pi is not None:
        pi_id = _field(pi, "id")
        if isinstance(pi_id, str) and pi_id:
            return pi_id
    return None


def _session_defers_capture(session: object, order: GiftOrderModel) -> bool:
    """True when this checkout only authorized funds (manual capture)."""
    metadata = _field(session, "metadata", {}) or {}
    if _field(metadata, "defer_capture") == "true":
        return True
    # Fallback: address-request orders always use authorize-then-capture.
    return bool(order.recipient_email) and order.status == "no_address" and not order.shipping_address


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
    if prospect and owner and (order.shipping_address or "").strip():
        send_new_order_notification(
            order_id=order.id,
            requested_at=order.requested_at,
            gift_id=order.gift_id,
            recipient_name=order.recipient_name,
            shipping_address=order.shipping_address or "",
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


def mark_order_authorized(
    order: GiftOrderModel,
    db: Session,
    *,
    payment_intent_id: str | None = None,
) -> GiftOrderModel:
    """Record a successful card authorization (funds held, not captured yet)."""
    if order.payment_status == "paid":
        return order

    if payment_intent_id:
        order.stripe_payment_intent_id = payment_intent_id
    order.payment_status = "authorized"
    # Stay on no_address until the recipient submits a ship-to.
    if order.status != "no_address" and not (order.shipping_address or "").strip():
        order.status = "no_address"
    db.add(order)
    db.commit()
    db.refresh(order)

    # Email the recipient only after authorization succeeds (and only once).
    if (
        order.address_request_token
        and order.recipient_email
        and order.address_request_sent_at is None
    ):
        send_recipient_address_request(
            recipient_name=order.recipient_name,
            recipient_email=order.recipient_email,
            address_form_url=_address_form_url(order.address_request_token),
            gift_id=order.gift_id,
            note=order.note,
        )
        order.address_request_sent_at = datetime.now(UTC)
        db.add(order)
        db.commit()
        db.refresh(order)

    return order


def capture_authorized_order(order: GiftOrderModel, db: Session) -> GiftOrderModel:
    """Capture a previously authorized PaymentIntent and queue the order."""
    if order.payment_status == "paid":
        return order
    if order.payment_status != "authorized":
        raise HTTPException(
            status_code=400,
            detail="Payment has not been authorized for this order yet.",
        )
    if not (order.shipping_address or "").strip():
        raise HTTPException(
            status_code=400,
            detail="A shipping address is required before capturing payment.",
        )

    ensure_stripe_configured()

    pi_id = order.stripe_payment_intent_id
    if not pi_id and order.stripe_checkout_session_id:
        session = stripe.checkout.Session.retrieve(order.stripe_checkout_session_id)
        pi_id = _payment_intent_id_from_session(session)
        if pi_id:
            order.stripe_payment_intent_id = pi_id
            db.add(order)
            db.commit()

    if not pi_id:
        raise HTTPException(
            status_code=503,
            detail="Unable to capture payment: missing Stripe payment intent.",
        )

    try:
        intent = stripe.PaymentIntent.retrieve(pi_id)
        status = _field(intent, "status")
        if status == "requires_capture":
            stripe.PaymentIntent.capture(pi_id)
        elif status == "succeeded":
            pass
        else:
            raise HTTPException(
                status_code=400,
                detail=f"Payment cannot be captured (status: {status}).",
            )
    except HTTPException:
        raise
    except stripe.error.StripeError as exc:
        logger.exception("Stripe capture failed for order_id=%s", order.id)
        raise HTTPException(status_code=502, detail="Unable to capture payment.") from exc

    return mark_order_paid(order, db)


def cancel_payment_authorization(order: GiftOrderModel) -> None:
    """Release an uncaptured authorization when an order is canceled."""
    if order.payment_status != "authorized" or not order.stripe_payment_intent_id:
        return
    try:
        ensure_stripe_configured()
        intent = stripe.PaymentIntent.retrieve(order.stripe_payment_intent_id)
        if _field(intent, "status") == "requires_capture":
            stripe.PaymentIntent.cancel(order.stripe_payment_intent_id)
    except Exception:
        logger.exception(
            "Failed to cancel authorization for order_id=%s pi=%s",
            order.id,
            order.stripe_payment_intent_id,
        )


def sync_order_payment_from_stripe(order: GiftOrderModel, db: Session) -> GiftOrderModel:
    if order.payment_status == "paid" or not order.stripe_checkout_session_id:
        return order

    ensure_stripe_configured()
    session = stripe.checkout.Session.retrieve(
        order.stripe_checkout_session_id,
        expand=["payment_intent"],
    )

    if _field(session, "payment_status") == "paid":
        return mark_order_paid(order, db)

    if order.payment_status == "authorized":
        return order

    if _session_defers_capture(session, order):
        pi = _field(session, "payment_intent")
        pi_status = _field(pi, "status") if pi is not None and not isinstance(pi, str) else None
        if isinstance(pi, str):
            try:
                intent = stripe.PaymentIntent.retrieve(pi)
                pi_status = _field(intent, "status")
            except stripe.error.StripeError:
                pi_status = None
        if pi_status in {"requires_capture", "succeeded"} or _field(session, "status") == "complete":
            return mark_order_authorized(
                order,
                db,
                payment_intent_id=_payment_intent_id_from_session(session),
            )

    return order


def _ensure_stripe_customer(current_user: UserModel, db: Session) -> str:
    """Return the user's Stripe customer id, creating and persisting one if needed.

    Reusing a single customer per user keeps their orders grouped in the Stripe
    dashboard instead of creating a fresh guest customer on every checkout.
    """
    if current_user.stripe_customer_id:
        # Verify the stored id still resolves in the current Stripe mode. A
        # customer created under test keys does not exist once live keys are in
        # use (Stripe returns "No such customer"), so fall through and mint a
        # fresh one instead of failing checkout.
        try:
            existing = stripe.Customer.retrieve(current_user.stripe_customer_id)
            if not _field(existing, "deleted"):
                return current_user.stripe_customer_id
        except stripe.error.InvalidRequestError:
            pass

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
    if order.payment_status == "authorized":
        raise HTTPException(
            status_code=400,
            detail="Payment is already authorized. Waiting for the recipient's shipping address.",
        )

    defer_capture = (
        order.status == "no_address"
        and bool(order.recipient_email)
        and not (order.shipping_address or "").strip()
    )

    if defer_capture:
        if order.status != "no_address":
            raise HTTPException(status_code=400, detail="This order cannot be paid.")
    else:
        if not (order.shipping_address or "").strip():
            raise HTTPException(
                status_code=400,
                detail="Waiting for the recipient to submit a shipping address before payment.",
            )
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
            "defer_capture": "true" if defer_capture else "false",
        },
        "customer": customer_id,
        "allow_promotion_codes": True,
    }
    if defer_capture:
        # Authorize now; capture only after the recipient submits an address.
        session_params["payment_intent_data"] = {"capture_method": "manual"}

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
        db.add(order)
        db.commit()
        db.refresh(order)

    pi_id = _payment_intent_id_from_session(session)

    if _session_defers_capture(session, order) or _field(metadata, "defer_capture") == "true":
        # Funds are held; do not charge or notify ops until address + capture.
        mark_order_authorized(order, db, payment_intent_id=pi_id)
        return

    mark_order_paid(order, db)
