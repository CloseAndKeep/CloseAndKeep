"""Month-end charge + pre-charge reminder for monthly billing users.

Run via cron (typically twice near month end):
  python -m app.jobs.monthly_billing

Or POST /internal/jobs/monthly-billing with CRON_SECRET.

Behavior:
- On the last calendar day (UTC): charge each monthly user with owed orders.
- On the 3rd-to-last calendar day (UTC): email a balance-due reminder.
- Other days: no-op (safe to schedule daily).
"""

from __future__ import annotations

import calendar
import logging
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..db import SessionLocal
from ..models import UserModel
from ..order_email import send_monthly_balance_reminder
from ..stripe_payments import (
    BILLING_MODE_MONTHLY,
    charge_owed_balance,
    list_owed_orders_for_user,
    monthly_balance_for_user,
)

logger = logging.getLogger(__name__)


def _days_in_month(year: int, month: int) -> int:
    return calendar.monthrange(year, month)[1]


def _profile_url() -> str:
    from ..config import settings

    return f"{settings.web_base_url.rstrip('/')}/profile"


def run_monthly_billing_job(
    db: Session,
    *,
    now: datetime | None = None,
    force_charge: bool = False,
    force_reminder: bool = False,
) -> dict[str, int | str]:
    """Run reminder and/or charge windows for monthly billing."""
    stamp = now or datetime.now(UTC)
    if stamp.tzinfo is None:
        stamp = stamp.replace(tzinfo=UTC)

    last_day = _days_in_month(stamp.year, stamp.month)
    reminder_day = max(1, last_day - 2)
    is_charge_day = force_charge or stamp.day == last_day
    is_reminder_day = force_reminder or stamp.day == reminder_day

    if not is_charge_day and not is_reminder_day:
        return {
            "status": "noop",
            "day": stamp.day,
            "last_day": last_day,
            "reminders_sent": 0,
            "charged_users": 0,
            "failed_users": 0,
            "skipped_users": 0,
        }

    users = list(
        db.scalars(
            select(UserModel).where(UserModel.billing_mode == BILLING_MODE_MONTHLY)
        ).all()
    )

    reminders_sent = 0
    charged_users = 0
    failed_users = 0
    skipped_users = 0

    for user in users:
        owed = list_owed_orders_for_user(user.id, db)
        if not owed:
            skipped_users += 1
            continue

        amount, currency, order_count = monthly_balance_for_user(user.id, db)
        if amount <= 0 or order_count <= 0:
            skipped_users += 1
            continue

        if is_reminder_day and not is_charge_day:
            try:
                send_monthly_balance_reminder(
                    orderer_email=user.email,
                    amount_cents=amount,
                    currency=currency,
                    order_count=order_count,
                    profile_url=_profile_url(),
                )
                reminders_sent += 1
            except Exception:
                logger.exception(
                    "Monthly balance reminder failed user_id=%s", user.id
                )
                failed_users += 1
            continue

        if is_charge_day:
            try:
                result = charge_owed_balance(user, db, notify_on_failure=True)
                if result.get("status") == "paid":
                    charged_users += 1
                else:
                    skipped_users += 1
            except Exception:
                logger.exception("Monthly charge failed user_id=%s", user.id)
                failed_users += 1

    return {
        "status": "ok",
        "day": stamp.day,
        "last_day": last_day,
        "reminders_sent": reminders_sent,
        "charged_users": charged_users,
        "failed_users": failed_users,
        "skipped_users": skipped_users,
    }


def main() -> None:
    logging.basicConfig(level=logging.INFO)
    with SessionLocal() as db:
        result = run_monthly_billing_job(db)
    logger.info("Monthly billing job: %s", result)


if __name__ == "__main__":
    main()
