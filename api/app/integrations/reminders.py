"""Process CRM stage events into cookie-order reminder emails."""

from __future__ import annotations

import logging
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ..models import (
    CrmReminderEventModel,
    IntegrationConnectionModel,
    ProspectModel,
    UserModel,
)
from ..order_email import send_cookie_reminder
from ..config import settings

logger = logging.getLogger(__name__)

PROVIDER_SALESFORCE = "salesforce"


def upsert_prospect_from_crm(
    db: Session,
    *,
    owner_user_id: int,
    provider: str,
    external_id: str,
    name: str,
    email: str,
    title: str = "",
    company: str = "",
) -> ProspectModel:
    """Create or update a prospect keyed by CRM opportunity/contact id."""
    existing = db.scalar(
        select(ProspectModel).where(
            ProspectModel.owner_user_id == owner_user_id,
            ProspectModel.crm_provider == provider,
            ProspectModel.crm_external_id == external_id,
        )
    )
    clean_name = (name or "").strip() or "Salesforce contact"
    clean_email = (email or "").strip().lower() or f"{external_id.lower()}@unknown.salesforce"
    clean_title = (title or "").strip() or "—"
    clean_company = (company or "").strip() or "—"

    if existing:
        existing.name = clean_name
        existing.email = clean_email
        existing.title = clean_title
        existing.company = clean_company
        db.flush()
        return existing

    prospect = ProspectModel(
        owner_user_id=owner_user_id,
        name=clean_name,
        email=clean_email,
        title=clean_title,
        company=clean_company,
        deal_status="open",
        crm_provider=provider,
        crm_external_id=external_id,
    )
    db.add(prospect)
    db.flush()
    return prospect


def process_stage_completed_reminder(
    db: Session,
    *,
    connection: IntegrationConnectionModel,
    opportunity_id: str,
    stage_name: str,
    contact_name: str,
    contact_email: str,
    contact_title: str = "",
    company: str = "",
) -> dict:
    """Upsert prospect, dedupe by opportunity, and email the salesperson immediately.

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
        title=contact_title,
        company=company,
    )

    owner = db.get(UserModel, connection.owner_user_id)
    if not owner:
        return {"status": "error", "reason": "owner_missing"}

    order_url = (
        f"{settings.web_base_url.rstrip('/')}/orders/new"
        f"?prospect_id={prospect.id}&from=sf_reminder"
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

    send_cookie_reminder(
        to_email=owner.email,
        prospect_name=prospect.name,
        prospect_company=prospect.company,
        prospect_title=prospect.title,
        stage_name=incoming,
        order_url=order_url,
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
