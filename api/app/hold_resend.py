"""In-app queue and one-click resend for expired deferred-address holds.

No schema change: expired / canceled-for-missing-address orders are
``canceled`` + ``canceled``, token cleared, shipping still empty, and a
recipient email was collected for the original ``/ship`` link.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from secrets import randbelow, token_urlsafe

from fastapi import HTTPException
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from .config import settings
from .models import GiftOrderModel, UserModel
from .stripe_payments import (
    assert_spending_limit_allows,
    create_checkout_session_for_order,
    prepare_monthly_owed_order,
    user_has_saved_payment_method,
    user_uses_monthly_billing,
)


def is_expired_address_hold(order: GiftOrderModel) -> bool:
    """True when the ``/ship`` hold died or was canceled before an address arrived."""
    return (
        order.status == "canceled"
        and order.payment_status == "canceled"
        and order.address_request_token is None
        and bool((order.recipient_email or "").strip())
        and not (order.shipping_address or "").strip()
    )


def list_expired_address_holds(user_id: int, db: Session) -> list[GiftOrderModel]:
    """Owner-scoped expired address holds, newest request first."""
    return list(
        db.scalars(
            select(GiftOrderModel)
            .where(
                GiftOrderModel.owner_user_id == user_id,
                GiftOrderModel.status == "canceled",
                GiftOrderModel.payment_status == "canceled",
                GiftOrderModel.address_request_token.is_(None),
                GiftOrderModel.recipient_email.is_not(None),
                GiftOrderModel.recipient_email != "",
                or_(
                    GiftOrderModel.shipping_address.is_(None),
                    GiftOrderModel.shipping_address == "",
                ),
            )
            .order_by(GiftOrderModel.requested_at.desc())
        ).all()
    )


def _mint_address_request_token() -> tuple[str, datetime]:
    expires = datetime.now(UTC) + timedelta(days=settings.address_request_ttl_days)
    return token_urlsafe(32), expires


def _mint_redeem_code(db: Session) -> str:
    for _ in range(40):
        code = f"CK-{randbelow(100_000):05d}"
        exists = db.scalar(
            select(GiftOrderModel.id).where(GiftOrderModel.redeem_code == code).limit(1)
        )
        if exists is None:
            return code
    raise HTTPException(status_code=500, detail="Unable to allocate a redeem code.")


def _uses_monthly_owed(user: UserModel) -> bool:
    return user_uses_monthly_billing(user) and user_has_saved_payment_method(user)


def resend_address_request(
    order_id: int,
    user: UserModel,
    db: Session,
) -> tuple[GiftOrderModel, str | None]:
    """Start a new address-request on an expired-hold order.

    Per-order: new authorize Checkout (does not revive the canceled PaymentIntent).
    Monthly owed: mint a new token and email the recipient — no Checkout.

    Returns ``(order, checkout_url)``. ``checkout_url`` is None for monthly owed.
    """
    order = db.get(GiftOrderModel, order_id)
    if not order or order.owner_user_id != user.id:
        raise HTTPException(status_code=404, detail="Gift order not found.")
    if user.role == "guest":
        raise HTTPException(
            status_code=403,
            detail="Guest accounts cannot request a shipping address from the recipient.",
        )
    if not is_expired_address_hold(order):
        raise HTTPException(
            status_code=400,
            detail="This order does not have an expired address hold to resend.",
        )
    recipient_email = (order.recipient_email or "").strip()
    if not recipient_email:
        raise HTTPException(
            status_code=400,
            detail="A recipient email is required to resend the address request.",
        )

    monthly = _uses_monthly_owed(user)
    if monthly:
        assert_spending_limit_allows(
            user,
            db,
            additional_gift_ids=[order.gift_id],
            blocked_recipient_names=[order.recipient_name],
        )

    token, expires_at = _mint_address_request_token()
    order.address_request_token = token
    order.redeem_code = _mint_redeem_code(db)
    order.address_request_expires_at = expires_at
    order.address_request_sent_at = None
    order.address_request_followup_sent_at = None
    order.status = "no_address"
    order.payment_status = "pending"
    # Dead hold / session must not be reused — Stripe cannot revive a canceled PI.
    order.stripe_payment_intent_id = None
    order.stripe_checkout_session_id = None
    if not monthly:
        order.billing_period = None
    db.add(order)
    db.commit()
    db.refresh(order)

    if monthly:
        order = prepare_monthly_owed_order(order, db)
        return order, None

    checkout_url = create_checkout_session_for_order(order, user, db)
    db.refresh(order)
    return order, checkout_url
