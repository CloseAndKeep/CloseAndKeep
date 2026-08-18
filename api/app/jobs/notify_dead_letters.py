"""Retry failed ops new-order Resend notifications.

Run via cron:
  python -m app.jobs.notify_dead_letters

Or POST /internal/jobs/notify-dead-letters with CRON_SECRET.
GET the same path for a tiny pending/failed list (ops only).
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta

from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from ..db import SessionLocal
from ..models import GiftOrderModel, NotifyDeadLetterModel, ProspectModel, UserModel
from ..notify_dead_letter import (
    MAX_NOTIFY_ATTEMPTS,
    MONEY_PAYMENT_STATUSES,
    OPS_NEW_ORDER_CONTEXT,
    ops_new_order_kwargs,
)
from ..order_email import send_new_order_notification

logger = logging.getLogger(__name__)


def retry_notify_dead_letters(
    db: Session,
    *,
    min_interval: timedelta = timedelta(minutes=5),
    max_attempts: int = MAX_NOTIFY_ATTEMPTS,
) -> dict[str, int]:
    """Re-send pending ops new-order emails and mark sent or increment attempts."""
    now = datetime.now(UTC)
    cap = max(1, int(max_attempts))
    candidates = db.scalars(
        select(NotifyDeadLetterModel).where(
            NotifyDeadLetterModel.status == "pending",
            NotifyDeadLetterModel.context == OPS_NEW_ORDER_CONTEXT,
            NotifyDeadLetterModel.attempt_count < cap,
        )
    ).all()

    retried = 0
    sent = 0
    failed = 0
    skipped = 0

    for row in candidates:
        last = row.last_attempt_at
        if last is not None and min_interval.total_seconds() > 0:
            if last.tzinfo is None:
                last = last.replace(tzinfo=UTC)
            if last > now - min_interval:
                skipped += 1
                continue

        result = db.execute(
            update(NotifyDeadLetterModel)
            .where(
                NotifyDeadLetterModel.id == row.id,
                NotifyDeadLetterModel.status == "pending",
                NotifyDeadLetterModel.attempt_count < cap,
            )
            .values(
                attempt_count=NotifyDeadLetterModel.attempt_count + 1,
                last_attempt_at=now,
            )
        )
        db.commit()
        if result.rowcount == 0:
            skipped += 1
            continue

        db.refresh(row)
        retried += 1
        error: str | None = None
        ok = False
        try:
            order = db.get(GiftOrderModel, row.order_id)
            if order is None:
                error = "Order is missing"
            elif (order.payment_status or "").strip().lower() not in MONEY_PAYMENT_STATUSES:
                error = f"Order payment_status is {order.payment_status!r}"
            else:
                prospect = db.get(ProspectModel, order.prospect_id)
                owner = db.get(UserModel, order.owner_user_id)
                if prospect is None or owner is None:
                    error = "Prospect or owner is missing"
                else:
                    ok = send_new_order_notification(
                        **ops_new_order_kwargs(order, prospect, owner)
                    )
                    if ok is not True:
                        error = "Ops new-order email was not accepted"
        except Exception as exc:
            logger.exception(
                "Ops notify dead-letter retry failed for order_id=%s", row.order_id
            )
            ok = False
            error = f"{type(exc).__name__}: {exc}"

        if ok is True:
            row.status = "sent"
            row.last_error = None
            sent += 1
        else:
            row.last_error = (error or "Ops new-order email was not accepted")[:1000]
            if row.attempt_count >= cap:
                row.status = "failed"
                failed += 1
        db.add(row)
        db.commit()

    pending = db.scalar(
        select(func.count(NotifyDeadLetterModel.id)).where(
            NotifyDeadLetterModel.status == "pending",
            NotifyDeadLetterModel.context == OPS_NEW_ORDER_CONTEXT,
        )
    )
    return {
        "retried": retried,
        "sent": sent,
        "failed": failed,
        "skipped": skipped,
        "candidates": len(candidates),
        "pending": int(pending or 0),
    }


def main() -> None:
    logging.basicConfig(level=logging.INFO)
    with SessionLocal() as db:
        result = retry_notify_dead_letters(db)
    logger.info("Notify dead letters: %s", result)


if __name__ == "__main__":
    main()
