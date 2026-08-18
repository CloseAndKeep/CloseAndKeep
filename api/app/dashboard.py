"""Dashboard aggregates. Gifted = money authorized or fulfillment underway."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from .models import GiftOrderModel, ProspectModel

GIFTED_PAYMENT_STATUSES = frozenset({"authorized", "paid", "owed"})
GIFTED_ORDER_STATUSES = frozenset({"queued", "shipped", "delivered", "no_address"})


def gifted_order_filter():
    """True when an order progressed past an unpaid draft."""
    return or_(
        GiftOrderModel.payment_status.in_(GIFTED_PAYMENT_STATUSES),
        GiftOrderModel.status.in_(GIFTED_ORDER_STATUSES),
    )


def summarize_dashboard(db: Session, owner_user_id: int) -> dict[str, int]:
    prospects = db.execute(
        select(ProspectModel.id, ProspectModel.deal_status).where(
            ProspectModel.owner_user_id == owner_user_id
        )
    ).all()
    gifted_ids = set(
        db.scalars(
            select(GiftOrderModel.prospect_id)
            .where(
                GiftOrderModel.owner_user_id == owner_user_id,
                gifted_order_filter(),
            )
            .distinct()
        ).all()
    )

    open_deals = won = lost = 0
    gifted_won = gifted_lost = ungifted_won = ungifted_lost = 0
    for prospect_id, status in prospects:
        if status == "open":
            open_deals += 1
            continue
        if status == "won":
            won += 1
            if prospect_id in gifted_ids:
                gifted_won += 1
            else:
                ungifted_won += 1
        elif status == "lost":
            lost += 1
            if prospect_id in gifted_ids:
                gifted_lost += 1
            else:
                ungifted_lost += 1

    return {
        "open_deals": open_deals,
        "won": won,
        "lost": lost,
        "total_prospects": len(prospects),
        "gifted_won": gifted_won,
        "gifted_lost": gifted_lost,
        "ungifted_won": ungifted_won,
        "ungifted_lost": ungifted_lost,
    }


NEEDS_ATTENTION_LIMIT = 8
_SHIPPED_LOOKBACK_DAYS = 7
_UNPAID_STATUSES = frozenset({"pending_payment", "no_address"})
_ACTIVE_HOLD_PAYMENTS = frozenset({"authorized", "owed"})


def _attention_item(order: GiftOrderModel) -> dict:
    return {
        "id": order.id,
        "recipient_name": order.recipient_name,
        "status": order.status,
        "href": f"/orders/{order.id}",
    }


def _just_shipped_clauses(now: datetime):
    """All currently shipped, or last 7 days when shipped_at exists."""
    clauses = [GiftOrderModel.status == "shipped"]
    shipped_at = getattr(GiftOrderModel, "shipped_at", None)
    if shipped_at is not None:
        clauses.append(shipped_at >= now - timedelta(days=_SHIPPED_LOOKBACK_DAYS))
    return clauses


def list_needs_attention(
    db: Session, owner_user_id: int, *, limit: int = NEEDS_ATTENTION_LIMIT
) -> dict[str, list[dict]]:
    """Owner-scoped unpaid / no-address / just-shipped lists (capped)."""
    now = datetime.now(UTC)
    owner = GiftOrderModel.owner_user_id == owner_user_id

    unpaid = db.scalars(
        select(GiftOrderModel)
        .where(
            owner,
            GiftOrderModel.payment_status == "pending",
            GiftOrderModel.status.in_(_UNPAID_STATUSES),
        )
        .order_by(GiftOrderModel.requested_at.desc())
        .limit(limit)
    ).all()

    no_address = db.scalars(
        select(GiftOrderModel)
        .where(
            owner,
            GiftOrderModel.status == "no_address",
            GiftOrderModel.payment_status.in_(_ACTIVE_HOLD_PAYMENTS),
            or_(
                GiftOrderModel.address_request_expires_at.is_(None),
                GiftOrderModel.address_request_expires_at > now,
            ),
        )
        .order_by(GiftOrderModel.requested_at.desc())
        .limit(limit)
    ).all()

    just_shipped = db.scalars(
        select(GiftOrderModel)
        .where(owner, *_just_shipped_clauses(now))
        .order_by(GiftOrderModel.requested_at.desc())
        .limit(limit)
    ).all()

    return {
        "unpaid": [_attention_item(order) for order in unpaid],
        "no_address": [_attention_item(order) for order in no_address],
        "just_shipped": [_attention_item(order) for order in just_shipped],
    }
