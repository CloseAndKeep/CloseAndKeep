"""Persist and list failed ops new-order notifications (not seller emails)."""

from __future__ import annotations

import logging
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from .models import GiftOrderModel, NotifyDeadLetterModel, ProspectModel, UserModel

logger = logging.getLogger(__name__)

OPS_NEW_ORDER_CONTEXT = "ops-new-order"
MONEY_PAYMENT_STATUSES = frozenset({"paid", "authorized", "owed"})
MAX_NOTIFY_ATTEMPTS = 8
_ERROR_MAX = 1000


def order_has_fulfillable_money(order: GiftOrderModel) -> bool:
    status = (getattr(order, "payment_status", None) or "").strip().lower()
    return status in MONEY_PAYMENT_STATUSES


def ops_new_order_kwargs(
    order: GiftOrderModel,
    prospect: ProspectModel,
    owner: UserModel,
) -> dict:
    return {
        "order_id": order.id,
        "requested_at": order.requested_at,
        "gift_id": order.gift_id,
        "recipient_name": order.recipient_name,
        "shipping_address": order.shipping_address or "",
        "note": order.note,
        "status": order.status,
        "prospect_name": prospect.name,
        "prospect_email": prospect.email,
        "prospect_deal_status": prospect.deal_status,
        "placed_by_email": owner.email,
        "payment_status": order.payment_status,
    }


def _clip_error(last_error: str | None) -> str | None:
    if not last_error:
        return None
    text = last_error.strip()
    if not text:
        return None
    return text[:_ERROR_MAX]


def record_ops_notify_dead_letter(
    db: Session | None,
    order: GiftOrderModel,
    *,
    last_error: str | None,
) -> None:
    """Enqueue a pending ops-new-order retry. Never raises to the caller."""
    if db is None or order is None or not getattr(order, "id", None):
        return
    if not order_has_fulfillable_money(order):
        return
    now = datetime.now(UTC)
    error = _clip_error(last_error) or "Ops new-order email was not accepted"
    try:
        existing = db.scalar(
            select(NotifyDeadLetterModel).where(
                NotifyDeadLetterModel.order_id == order.id,
                NotifyDeadLetterModel.context == OPS_NEW_ORDER_CONTEXT,
            )
        )
        if existing:
            if existing.status != "pending":
                return
            existing.last_error = error
            existing.last_attempt_at = now
            db.add(existing)
            db.commit()
            return
        db.add(
            NotifyDeadLetterModel(
                order_id=order.id,
                context=OPS_NEW_ORDER_CONTEXT,
                last_error=error,
                last_attempt_at=now,
                attempt_count=1,
                status="pending",
            )
        )
        db.commit()
    except IntegrityError:
        db.rollback()
        logger.info(
            "Ops notify dead letter already exists for order_id=%s", order.id
        )
    except Exception:
        db.rollback()
        logger.exception(
            "Failed to persist ops notify dead letter for order_id=%s", order.id
        )


def list_ops_notify_dead_letters(db: Session, *, limit: int = 50) -> dict:
    """Tiny internal list of pending/failed ops notify rows (not a seller view)."""
    cap = max(1, min(int(limit), 200))
    rows = db.scalars(
        select(NotifyDeadLetterModel)
        .where(NotifyDeadLetterModel.status.in_(["pending", "failed"]))
        .order_by(NotifyDeadLetterModel.created_at.desc())
        .limit(cap)
    ).all()
    return {
        "items": [
            {
                "id": row.id,
                "order_id": row.order_id,
                "context": row.context,
                "status": row.status,
                "attempt_count": row.attempt_count,
                "last_error": row.last_error,
                "last_attempt_at": (
                    row.last_attempt_at.isoformat() if row.last_attempt_at else None
                ),
            }
            for row in rows
        ]
    }
