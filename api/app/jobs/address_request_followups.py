"""Address-request follow-ups and expired-hold sweep.

Sends a recipient reminder after N hours, then cancels holds past
``address_request_expires_at`` and emails the AE (seller) once.

Run via cron:
  python -m app.jobs.address_request_followups

Or POST /internal/jobs/address-request-followups with CRON_SECRET.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta

from sqlalchemy import or_, select, update
from sqlalchemy.orm import Session

from ..config import settings
from ..db import SessionLocal
from ..models import GiftOrderModel, UserModel
from ..order_email import send_recipient_address_followup
from ..stripe_payments import (
    _address_form_url,
    _gift_label,
    _redeem_page_url,
    expire_address_request_hold,
    notify_seller_address_hold_expired,
)

logger = logging.getLogger(__name__)


def send_due_address_request_followups(db: Session) -> dict[str, int]:
    """Email recipients who never submitted an address after the follow-up window."""
    now = datetime.now(UTC)
    hours = max(1, int(settings.address_request_followup_hours))
    cutoff = now - timedelta(hours=hours)

    candidates = db.scalars(
        select(GiftOrderModel).where(
            GiftOrderModel.status == "no_address",
            GiftOrderModel.payment_status.in_(["authorized", "owed"]),
            or_(
                GiftOrderModel.shipping_address.is_(None),
                GiftOrderModel.shipping_address == "",
            ),
            GiftOrderModel.address_request_token.is_not(None),
            GiftOrderModel.redeem_code.is_not(None),
            GiftOrderModel.recipient_email.is_not(None),
            GiftOrderModel.address_request_sent_at.is_not(None),
            GiftOrderModel.address_request_sent_at <= cutoff,
            GiftOrderModel.address_request_followup_sent_at.is_(None),
            or_(
                GiftOrderModel.address_request_expires_at.is_(None),
                GiftOrderModel.address_request_expires_at > now,
            ),
        )
    ).all()

    sent = 0
    skipped = 0
    for order in candidates:
        # Claim first so overlapping cron runs cannot double-email.
        result = db.execute(
            update(GiftOrderModel)
            .where(
                GiftOrderModel.id == order.id,
                GiftOrderModel.status == "no_address",
                GiftOrderModel.payment_status.in_(["authorized", "owed"]),
                GiftOrderModel.address_request_followup_sent_at.is_(None),
                or_(
                    GiftOrderModel.shipping_address.is_(None),
                    GiftOrderModel.shipping_address == "",
                ),
            )
            .values(address_request_followup_sent_at=now)
        )
        db.commit()
        if result.rowcount == 0:
            skipped += 1
            continue

        db.refresh(order)
        if not order.address_request_token or not order.redeem_code or not order.recipient_email:
            skipped += 1
            continue

        owner = db.get(UserModel, order.owner_user_id)
        try:
            send_recipient_address_followup(
                recipient_name=order.recipient_name,
                recipient_email=order.recipient_email,
                address_form_url=_address_form_url(order.address_request_token),
                redeem_url=_redeem_page_url(),
                redeem_code=order.redeem_code,
                gift_label=_gift_label(order.gift_id),
                note=order.note,
                sender_name=owner.name if owner else None,
                sender_company=owner.company if owner else None,
                sender_avatar_data=owner.avatar_data if owner else None,
                sender_avatar_content_type=owner.avatar_content_type if owner else None,
            )
            sent += 1
        except Exception:
            logger.exception(
                "Address-request follow-up failed for order_id=%s", order.id
            )
            skipped += 1

    expiry = expire_due_address_request_holds(db)
    return {"sent": sent, "skipped": skipped, "candidates": len(candidates), **expiry}


def expire_due_address_request_holds(db: Session) -> dict[str, int]:
    """Cancel holds past address_request_expires_at and email the AE once.

    Approach B: expire_address_request_hold returns True only on the
    no_address+(authorized|owed) → canceled transition, so a later webhook
    or public-token hit will not send a second seller email.
    """
    now = datetime.now(UTC)
    candidates = db.scalars(
        select(GiftOrderModel).where(
            GiftOrderModel.status == "no_address",
            GiftOrderModel.payment_status.in_(["authorized", "owed"]),
            GiftOrderModel.address_request_expires_at.is_not(None),
            GiftOrderModel.address_request_expires_at <= now,
        )
    ).all()

    expired = 0
    expired_notified = 0
    for order in candidates:
        try:
            canceled = expire_address_request_hold(order, db)
        except Exception:
            logger.exception(
                "Failed to expire address-request hold for order_id=%s", order.id
            )
            continue
        if not canceled:
            continue
        expired += 1
        try:
            notify_seller_address_hold_expired(order, db)
            expired_notified += 1
        except Exception:
            logger.exception(
                "Seller address-hold expiry email failed for order_id=%s", order.id
            )

    return {"expired": expired, "expired_notified": expired_notified}


def main() -> None:
    logging.basicConfig(level=logging.INFO)
    with SessionLocal() as db:
        result = send_due_address_request_followups(db)
    logger.info("Address-request follow-ups: %s", result)


if __name__ == "__main__":
    main()
