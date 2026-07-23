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
from .order_email import send_new_order_notification

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
        del db  # unused today; bakery providers will persist vendor ids here
        if not (order.shipping_address or "").strip():
            logger.info(
                "Skipping fulfillment notify for order %s (no shipping address yet)",
                order.id,
            )
            return
        send_new_order_notification(
            order_id=order.id,
            requested_at=order.requested_at,
            gift_id=order.gift_id,
            recipient_name=order.recipient_name,
            shipping_address=order.shipping_address or "",
            note=order.note,
            status=order.status,
            prospect_name=prospect.name,
            prospect_email=prospect.email,
            prospect_deal_status=prospect.deal_status,
            placed_by_email=owner.email,
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
