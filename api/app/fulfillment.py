"""Fulfillment handoff after payment succeeds.

Payment and fulfillment stay decoupled on purpose:

1. Stripe Checkout + webhook mark the order ``paid`` / ``queued``.
2. This module is the only place that should talk to a gift vendor later
   (e.g. a bakery API). Today it only notifies ops by email.

When you add a bakery integration, implement a new provider that submits the
order to the vendor, stores their id (e.g. on ``admin_notes`` or a dedicated
column), and advances ``status`` toward ``ordered`` / ``shipped``. Keep that
logic out of checkout creation and out of the public order API.
"""

from __future__ import annotations

import logging
from typing import Protocol

from sqlalchemy.orm import Session

from .models import GiftOrderModel, ProspectModel, UserModel
from .notify_dead_letter import ops_new_order_kwargs, record_ops_notify_dead_letter
from .order_email import (
    send_new_order_notification,
    send_seller_order_delivered,
    send_seller_order_shipped,
)

logger = logging.getLogger(__name__)


class FulfillmentProvider(Protocol):
    def submit_queued_order(
        self,
        order: GiftOrderModel,
        *,
        prospect: ProspectModel,
        owner: UserModel,
        db: Session,
    ) -> None: ...


class ManualEmailFulfillment:
    """MVP provider: email ops so a human can place the bakery order."""

    def submit_queued_order(
        self,
        order: GiftOrderModel,
        *,
        prospect: ProspectModel,
        owner: UserModel,
        db: Session,
    ) -> None:
        if not (order.shipping_address or "").strip():
            logger.info(
                "Skipping fulfillment notify for order %s (no shipping address yet)",
                order.id,
            )
            return
        last_error: str | None = None
        try:
            ok = send_new_order_notification(
                **ops_new_order_kwargs(order, prospect, owner)
            )
        except Exception as exc:
            logger.exception("Ops new-order notify raised for order %s", order.id)
            ok = False
            last_error = f"{type(exc).__name__}: {exc}"
        if ok is False:
            record_ops_notify_dead_letter(
                db,
                order,
                last_error=last_error or "Ops new-order email was not accepted",
            )


def get_fulfillment_provider() -> FulfillmentProvider:
    # Later: choose BakeryApiFulfillment from settings when configured.
    return ManualEmailFulfillment()


def dispatch_queued_fulfillment(
    order: GiftOrderModel,
    *,
    prospect: ProspectModel,
    owner: UserModel,
    db: Session,
) -> None:
    """Invoke the configured provider after an order becomes paid + queued."""
    try:
        get_fulfillment_provider().submit_queued_order(
            order, prospect=prospect, owner=owner, db=db
        )
    except Exception:
        # Never roll back payment because fulfillment notify failed.
        logger.exception("Fulfillment provider failed for order %s", order.id)


def notify_seller_status_change(
    *,
    previous_status: str,
    new_status: str,
    order_id: int,
    seller_email: str,
    recipient_name: str,
    gift_label: str,
    tracking_number: str | None,
    order_url: str,
) -> None:
    """Email the AE when admin first marks an order shipped or delivered."""
    try:
        if previous_status != "shipped" and new_status == "shipped":
            send_seller_order_shipped(
                order_id=order_id,
                seller_email=seller_email,
                recipient_name=recipient_name,
                gift_label=gift_label,
                tracking_number=tracking_number,
                order_url=order_url,
            )
        elif previous_status != "delivered" and new_status == "delivered":
            send_seller_order_delivered(
                order_id=order_id,
                seller_email=seller_email,
                recipient_name=recipient_name,
                gift_label=gift_label,
                tracking_number=tracking_number,
                order_url=order_url,
            )
    except Exception:
        logger.exception("Seller status email failed for order %s", order_id)
