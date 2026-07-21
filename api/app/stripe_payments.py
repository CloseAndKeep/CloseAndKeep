"""Stripe one-time Checkout for gift orders."""

from __future__ import annotations

import logging
import time
from datetime import UTC, datetime

import stripe
from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from .config import GIFT_CATALOG, settings, stripe_price_for_gift
from .models import GiftOrderModel, ProspectModel, UserModel
from .order_email import send_recipient_address_request

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
    if prospect and owner:
        # Payment is done; hand off to fulfillment (email today, bakery API later).
        from .fulfillment import dispatch_queued_fulfillment

        dispatch_queued_fulfillment(order, prospect=prospect, owner=owner, db=db)
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


def _orders_sharing_checkout_session(
    session_id: str | None, db: Session
) -> list[GiftOrderModel]:
    if not session_id:
        return []
    return list(
        db.scalars(
            select(GiftOrderModel).where(GiftOrderModel.stripe_checkout_session_id == session_id)
        ).all()
    )


def _orders_from_checkout_metadata(session: object, db: Session) -> list[GiftOrderModel]:
    """Resolve orders from Checkout metadata when session-id lookup finds none."""
    metadata = _field(session, "metadata", {}) or {}
    order_ids: list[int] = []
    multi = _field(metadata, "gift_order_ids")
    if multi:
        for part in str(multi).split(","):
            part = part.strip()
            if part.isdigit():
                order_ids.append(int(part))
    single = _field(metadata, "gift_order_id")
    if single:
        try:
            oid = int(str(single))
        except ValueError:
            oid = None
        if oid is not None and oid not in order_ids:
            order_ids.append(oid)

    orders: list[GiftOrderModel] = []
    for order_id in order_ids:
        order = db.get(GiftOrderModel, order_id)
        if order:
            orders.append(order)
    return orders


def sync_order_payment_from_stripe(order: GiftOrderModel, db: Session) -> GiftOrderModel:
    if order.payment_status == "paid" or not order.stripe_checkout_session_id:
        return order

    ensure_stripe_configured()
    session = stripe.checkout.Session.retrieve(
        order.stripe_checkout_session_id,
        expand=["payment_intent"],
    )

    if _field(session, "payment_status") == "paid":
        # Batch checkouts share one session — mark every linked order paid.
        siblings = _orders_sharing_checkout_session(order.stripe_checkout_session_id, db)
        targets = siblings or [order]
        for sibling in targets:
            mark_order_paid(sibling, db)
        db.refresh(order)
        return order

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
                "gift_order_ids": str(order.id),
                "user_id": str(current_user.id),
                "defer_capture": "true",
            },
            "customer": customer_id,
            "allow_promotion_codes": True,
            # Authorize now; capture only after the recipient submits an address.
            "payment_intent_data": {"capture_method": "manual"},
        }
        session = stripe.checkout.Session.create(**session_params)
        order.stripe_checkout_session_id = session["id"]
        order.stripe_price_id = price_id
        db.add(order)
        db.commit()
        db.refresh(order)
        return session["url"]

    return create_checkout_session_for_orders([order], current_user, db)


def create_checkout_session_for_orders(
    orders: list[GiftOrderModel],
    current_user: UserModel,
    db: Session,
) -> str:
    """One Checkout Session covering one or more known-address orders.

    Used by CSV import so the buyer enters their card once for every row that
    already has a shipping address. Address-request orders must stay on their
    own authorize-then-capture sessions and must not be passed here.
    """
    if not orders:
        raise HTTPException(status_code=400, detail="No orders to check out.")

    for order in orders:
        if order.payment_status == "paid":
            raise HTTPException(status_code=400, detail="This order is already paid.")
        if order.payment_status == "authorized":
            raise HTTPException(
                status_code=400,
                detail="Payment is already authorized. Waiting for the recipient's shipping address.",
            )
        if not (order.shipping_address or "").strip():
            raise HTTPException(
                status_code=400,
                detail="Waiting for the recipient to submit a shipping address before payment.",
            )
        if order.status not in {"pending_payment"}:
            raise HTTPException(status_code=400, detail="This order cannot be paid.")
        if order.owner_user_id != current_user.id:
            raise HTTPException(status_code=404, detail="Order not found.")

    ensure_stripe_configured()

    # Reuse when every order already points at the same still-open session.
    shared_session_ids = {o.stripe_checkout_session_id for o in orders}
    if len(shared_session_ids) == 1:
        shared_id = next(iter(shared_session_ids))
        if shared_id:
            reusable_url = _reuse_open_checkout_session(orders[0])
            if reusable_url:
                return reusable_url

    line_items: list[dict] = []
    for order in orders:
        price_id = resolve_stripe_price_id(order.gift_id)
        order.stripe_price_id = price_id
        line_items.append({"price": price_id, "quantity": 1})

    customer_id = _ensure_stripe_customer(current_user, db)
    order_ids = ",".join(str(o.id) for o in orders)
    # Stripe metadata values max out at 500 chars; session-id lookup is the
    # primary fulfill path, so truncate ids in metadata if the batch is huge.
    metadata_ids = order_ids if len(order_ids) <= 500 else order_ids[:497] + "..."

    if len(orders) == 1:
        success_url = f"{settings.web_base_url}/orders/{orders[0].id}?payment=success"
        cancel_url = f"{settings.web_base_url}/orders/{orders[0].id}?payment=cancel"
    else:
        success_url = f"{settings.web_base_url}/orders?payment=success"
        cancel_url = f"{settings.web_base_url}/orders?payment=cancel"

    session_params: dict = {
        "mode": "payment",
        "line_items": line_items,
        "success_url": success_url,
        "cancel_url": cancel_url,
        "metadata": {
            "gift_order_id": str(orders[0].id),
            "gift_order_ids": metadata_ids,
            "user_id": str(current_user.id),
            "defer_capture": "false",
        },
        "customer": customer_id,
        "allow_promotion_codes": True,
    }

    session = stripe.checkout.Session.create(**session_params)
    session_id = session["id"]
    for order in orders:
        order.stripe_checkout_session_id = session_id
        db.add(order)
    db.commit()
    for order in orders:
        db.refresh(order)
    return session["url"]


def fulfill_order_from_checkout_session(session: dict, db: Session) -> None:
    if _field(session, "mode") != "payment":
        return

    session_id = _field(session, "id")
    orders = _orders_sharing_checkout_session(
        session_id if isinstance(session_id, str) else None, db
    )
    if not orders:
        orders = _orders_from_checkout_metadata(session, db)
    if not orders:
        return

    if isinstance(session_id, str) and session_id:
        for order in orders:
            order.stripe_checkout_session_id = session_id
            db.add(order)
        db.commit()
        for order in orders:
            db.refresh(order)

    metadata = _field(session, "metadata", {}) or {}
    pi_id = _payment_intent_id_from_session(session)
    defer = _field(metadata, "defer_capture") == "true"
    payment_status = _field(session, "payment_status")

    for order in orders:
        use_defer = defer or _session_defers_capture(session, order)
        if use_defer:
            # Manual capture: Checkout reports unpaid until capture. If the
            # session is already paid, treat it as a completed charge.
            if payment_status == "paid":
                mark_order_paid(order, db)
                continue
            if payment_status not in ("unpaid", "no_payment_required"):
                continue
            pi = _field(session, "payment_intent")
            if pi is not None and not isinstance(pi, str):
                pi_status = _field(pi, "status")
                if pi_status and pi_status not in ("requires_capture", "succeeded"):
                    continue
            # Funds are held; do not charge or notify ops until address + capture.
            mark_order_authorized(order, db, payment_intent_id=pi_id)
        else:
            if payment_status != "paid":
                # Defense in depth: do not queue fulfillment on incomplete payment.
                continue
            mark_order_paid(order, db)
