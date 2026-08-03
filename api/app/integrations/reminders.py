"""Process CRM stage events into cookie-order reminders or auto-orders."""

from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta
from secrets import randbelow, token_urlsafe

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ..config import settings
from ..models import (
    CrmReminderEventModel,
    GiftOrderModel,
    IntegrationConnectionModel,
    ProspectModel,
    UserModel,
)
from ..order_email import send_auto_order_checkout, send_cookie_reminder
from ..stripe_payments import (
    AUTO_ORDER_GIFT_IDS,
    create_checkout_session_for_order,
    prepare_monthly_owed_order,
    user_has_saved_payment_method,
    user_uses_monthly_billing,
    _gift_label,
)

logger = logging.getLogger(__name__)

PROVIDER_SALESFORCE = "salesforce"
PROVIDER_HUBSPOT = "hubspot"

_CRM_LABELS = {
    PROVIDER_SALESFORCE: "Salesforce",
    PROVIDER_HUBSPOT: "HubSpot",
}
_REMINDER_FROM = {
    PROVIDER_SALESFORCE: "sf_reminder",
    PROVIDER_HUBSPOT: "hs_reminder",
}

DEFAULT_AUTO_ORDER_NOTE = (
    "Thanks for meeting with us — enjoy these cookies!"
)


def upsert_prospect_from_crm(
    db: Session,
    *,
    owner_user_id: int,
    provider: str,
    external_id: str,
    name: str,
    email: str,
) -> ProspectModel:
    """Create or update a prospect keyed by CRM opportunity/deal id."""
    existing = db.scalar(
        select(ProspectModel).where(
            ProspectModel.owner_user_id == owner_user_id,
            ProspectModel.crm_provider == provider,
            ProspectModel.crm_external_id == external_id,
        )
    )
    crm_label = _CRM_LABELS.get(provider, provider.title())
    clean_name = (name or "").strip() or f"{crm_label} contact"
    clean_email = (
        (email or "").strip().lower() or f"{external_id.lower()}@unknown.{provider}"
    )

    if existing:
        existing.name = clean_name
        existing.email = clean_email
        db.flush()
        return existing

    prospect = ProspectModel(
        owner_user_id=owner_user_id,
        name=clean_name,
        email=clean_email,
        deal_status="open",
        crm_provider=provider,
        crm_external_id=external_id,
    )
    db.add(prospect)
    db.flush()
    return prospect


def _mint_address_token() -> tuple[str, datetime]:
    token = token_urlsafe(32)
    expires = datetime.now(UTC) + timedelta(days=settings.address_request_ttl_days)
    return token, expires


def _mint_redeem_code(db: Session) -> str:
    """Allocate a short human redeem code like CK-48291 (matches main.py)."""
    for _ in range(40):
        code = f"CK-{randbelow(100_000):05d}"
        exists = db.scalar(
            select(GiftOrderModel.id).where(GiftOrderModel.redeem_code == code).limit(1)
        )
        if not exists:
            return code
    raise RuntimeError("Unable to mint redeem code")


def _create_auto_order(
    db: Session,
    *,
    owner: UserModel,
    prospect: ProspectModel,
) -> dict:
    """Create an address-request gift order for CRM auto-order."""
    gift_id = (owner.auto_order_gift_id or "").strip()
    if gift_id not in AUTO_ORDER_GIFT_IDS:
        return {"status": "error", "reason": "invalid_auto_order_gift"}

    recipient_email = (prospect.email or "").strip().lower()
    if not recipient_email or recipient_email.endswith("@unknown.salesforce") or recipient_email.endswith(
        "@unknown.hubspot"
    ):
        # Still create — redeem code works without email; skip email send later.
        pass

    token, expires_at = _mint_address_token()
    order = GiftOrderModel(
        owner_user_id=owner.id,
        prospect_id=prospect.id,
        gift_id=gift_id,
        recipient_name=prospect.name,
        shipping_address=None,
        recipient_email=recipient_email or None,
        note=DEFAULT_AUTO_ORDER_NOTE,
        status="no_address",
        payment_status="pending",
        address_request_token=token,
        redeem_code=_mint_redeem_code(db),
        address_request_expires_at=expires_at,
        address_request_sent_at=None,
    )
    db.add(order)
    db.commit()
    db.refresh(order)

    order_url = f"{settings.web_base_url.rstrip('/')}/orders/{order.id}"
    monthly = user_uses_monthly_billing(owner) and user_has_saved_payment_method(owner)

    if monthly:
        order = prepare_monthly_owed_order(order, db)
        return {
            "status": "auto_ordered",
            "order_id": order.id,
            "billing": "monthly",
            "payment_status": order.payment_status,
            "order_url": order_url,
        }

    try:
        checkout_url = create_checkout_session_for_order(order, owner, db)
    except Exception:
        logger.exception("Auto-order checkout failed order_id=%s", order.id)
        db.delete(order)
        db.commit()
        return {"status": "error", "reason": "checkout_failed"}

    send_auto_order_checkout(
        to_email=owner.email,
        prospect_name=prospect.name,
        gift_label=_gift_label(gift_id),
        checkout_url=checkout_url,
        order_url=order_url,
    )
    return {
        "status": "auto_ordered",
        "order_id": order.id,
        "billing": "per_order",
        "checkout_url": checkout_url,
        "order_url": order_url,
    }


def process_stage_completed_reminder(
    db: Session,
    *,
    connection: IntegrationConnectionModel,
    opportunity_id: str,
    stage_name: str,
    contact_name: str,
    contact_email: str,
) -> dict:
    """Upsert prospect, dedupe by opportunity, then auto-order or email reminder.

    Returns a small status dict for API/logging. Does not raise on email transport
    failure (Resend is best-effort, matching other order emails).
    """
    trigger = (connection.trigger_stage_name or "Demo Completed").strip()
    incoming = (stage_name or "").strip()
    if incoming.casefold() != trigger.casefold():
        return {
            "status": "ignored",
            "reason": "stage_mismatch",
            "expected": trigger,
            "got": incoming,
        }

    if not connection.enabled:
        return {"status": "ignored", "reason": "connection_disabled"}

    opportunity_id = (opportunity_id or "").strip()
    if not opportunity_id:
        return {"status": "error", "reason": "missing_opportunity_id"}

    existing_event = db.scalar(
        select(CrmReminderEventModel).where(
            CrmReminderEventModel.connection_id == connection.id,
            CrmReminderEventModel.external_event_key == opportunity_id,
        )
    )
    if existing_event:
        return {
            "status": "duplicate",
            "event_id": existing_event.id,
            "prospect_id": existing_event.prospect_id,
        }

    prospect = upsert_prospect_from_crm(
        db,
        owner_user_id=connection.owner_user_id,
        provider=connection.provider,
        external_id=opportunity_id,
        name=contact_name,
        email=contact_email,
    )

    owner = db.get(UserModel, connection.owner_user_id)
    if not owner:
        return {"status": "error", "reason": "owner_missing"}

    from_param = _REMINDER_FROM.get(connection.provider, "crm_reminder")
    order_url = (
        f"{settings.web_base_url.rstrip('/')}/orders/new"
        f"?prospect_id={prospect.id}&from={from_param}"
    )

    now = datetime.now(UTC)
    event = CrmReminderEventModel(
        connection_id=connection.id,
        owner_user_id=connection.owner_user_id,
        prospect_id=prospect.id,
        provider=connection.provider,
        external_event_key=opportunity_id,
        stage_name=incoming,
        status="sent",
        email_sent_at=now,
    )
    db.add(event)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        existing_event = db.scalar(
            select(CrmReminderEventModel).where(
                CrmReminderEventModel.connection_id == connection.id,
                CrmReminderEventModel.external_event_key == opportunity_id,
            )
        )
        return {
            "status": "duplicate",
            "event_id": existing_event.id if existing_event else None,
            "prospect_id": existing_event.prospect_id if existing_event else prospect.id,
        }
    db.refresh(event)
    db.refresh(prospect)

    if owner.auto_order_enabled and (owner.auto_order_gift_id or "") in AUTO_ORDER_GIFT_IDS:
        auto_result = _create_auto_order(db, owner=owner, prospect=prospect)
        event.status = "auto_ordered" if auto_result.get("status") == "auto_ordered" else "error"
        db.add(event)
        db.commit()
        logger.info(
            "CRM auto-order connection_id=%s opportunity=%s prospect_id=%s result=%s",
            connection.id,
            opportunity_id,
            prospect.id,
            auto_result.get("status"),
        )
        return {
            **auto_result,
            "event_id": event.id,
            "prospect_id": prospect.id,
        }

    send_cookie_reminder(
        to_email=owner.email,
        prospect_name=prospect.name,
        stage_name=incoming,
        order_url=order_url,
        crm_name=_CRM_LABELS.get(connection.provider, connection.provider.title()),
    )

    logger.info(
        "CRM cookie reminder sent connection_id=%s opportunity=%s prospect_id=%s",
        connection.id,
        opportunity_id,
        prospect.id,
    )
    return {
        "status": "sent",
        "event_id": event.id,
        "prospect_id": prospect.id,
        "order_url": order_url,
    }
