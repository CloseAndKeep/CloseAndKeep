"""Stripe one-time Checkout for gift orders."""

from __future__ import annotations

import stripe
from fastapi import HTTPException
from sqlalchemy.orm import Session

from .config import settings, stripe_price_for_gift
from .models import GiftOrderModel, ProspectModel, UserModel
from .order_email import send_new_order_notification


def ensure_stripe_configured() -> None:
    if not settings.stripe_secret_key:
        raise HTTPException(status_code=503, detail="Payments are not configured.")
    stripe.api_key = settings.stripe_secret_key


def ensure_stripe_webhook_configured() -> None:
    if not settings.stripe_secret_key or not settings.stripe_webhook_secret:
        raise HTTPException(status_code=503, detail="Payment webhooks are not configured.")
    stripe.api_key = settings.stripe_secret_key


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
    if session.get("payment_status") == "paid":
        return mark_order_paid(order, db)
    return order


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
    price_id = resolve_stripe_price_id(order.gift_id)

    session_params: dict = {
        "mode": "payment",
        "line_items": [{"price": price_id, "quantity": 1}],
        "success_url": f"{settings.web_base_url}/orders/{order.id}?payment=success",
        "cancel_url": f"{settings.web_base_url}/orders/{order.id}?payment=cancel",
        "metadata": {
            "gift_order_id": str(order.id),
            "user_id": str(current_user.id),
        },
        "allow_promotion_codes": True,
    }
    if current_user.stripe_customer_id:
        session_params["customer"] = current_user.stripe_customer_id
    else:
        session_params["customer_email"] = current_user.email

    session = stripe.checkout.Session.create(**session_params)
    order.stripe_checkout_session_id = session["id"]
    order.stripe_price_id = price_id
    db.add(order)
    db.commit()
    db.refresh(order)
    return session["url"]


def fulfill_order_from_checkout_session(session: dict, db: Session) -> None:
    if session.get("mode") != "payment":
        return

    gift_order_id = session.get("metadata", {}).get("gift_order_id")
    if not gift_order_id:
        return

    try:
        order_id = int(gift_order_id)
    except ValueError:
        return

    order = db.get(GiftOrderModel, order_id)
    if not order:
        return

    if session.get("id"):
        order.stripe_checkout_session_id = session["id"]
    mark_order_paid(order, db)
