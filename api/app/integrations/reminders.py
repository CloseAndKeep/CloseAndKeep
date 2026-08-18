"""Process CRM stage events into cookie-order reminders or auto-orders."""

from __future__ import annotations

import json
import logging
from datetime import UTC, datetime, timedelta
from secrets import randbelow, token_urlsafe
from typing import Any

from fastapi import HTTPException
from sqlalchemy import func, or_, select
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
from ..order_email import (
    send_auto_order_checkout,
    send_auto_order_held_junk,
    send_cookie_reminder,
)
from ..shipping_address import (
    empty_shipping_address_values,
    parts_from_cookie_fields,
    shipping_address_values,
)
from ..stripe_payments import (
    AUTO_ORDER_GIFT_IDS,
    create_checkout_session_for_order,
    prepare_monthly_owed_order,
    user_has_saved_payment_method,
    user_uses_monthly_billing,
    _gift_label,
)
from .contact_quality import (
    ADDRESS_USABLE,
    crm_address_quality,
    is_junk_crm_email,
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

MAX_STAGE_RECIPES = 12
DEFAULT_TRIGGER_STAGE = "Demo Completed"

# Default window; override with REGIFT_WINDOW_DAYS. Enforced in code (no migration).
DEFAULT_REGIFT_WINDOW_DAYS = 90
REGIFT_SKIP_STATUS = "skipped_regift"
RETRYABLE_EVENT_STATUSES = frozenset({"error", "held", "held_junk"})
_SUCCESSFUL_PAYMENT_STATUSES = frozenset({"paid", "authorized", "owed"})
_SUCCESSFUL_ORDER_STATUSES = frozenset({"queued", "shipped", "delivered"})
_PLACEHOLDER_EMAIL_SUFFIXES = ("@unknown.salesforce", "@unknown.hubspot")


def event_is_retryable(status: str) -> bool:
    return (status or "").strip() in RETRYABLE_EVENT_STATUSES


def _regift_window_days() -> int:
    try:
        days = int(settings.regift_window_days)
    except (TypeError, ValueError):
        days = DEFAULT_REGIFT_WINDOW_DAYS
    return max(1, days)


def _real_recipient_email(email: str | None) -> str | None:
    cleaned = (email or "").strip().lower()
    if not cleaned or any(cleaned.endswith(suffix) for suffix in _PLACEHOLDER_EMAIL_SUFFIXES):
        return None
    return cleaned


def find_recent_successful_gift(
    db: Session,
    *,
    owner_user_id: int,
    email: str | None,
    prospect_id: int | None,
    now: datetime | None = None,
) -> GiftOrderModel | None:
    """Return the newest successful gift for this person inside the re-gift window."""
    when = now or datetime.now(UTC)
    cutoff = when - timedelta(days=_regift_window_days())
    real_email = _real_recipient_email(email)

    identity: list = []
    if prospect_id is not None:
        identity.append(GiftOrderModel.prospect_id == prospect_id)
    if real_email:
        identity.append(func.lower(GiftOrderModel.recipient_email) == real_email)
        same_email_prospects = select(ProspectModel.id).where(
            ProspectModel.owner_user_id == owner_user_id,
            func.lower(ProspectModel.email) == real_email,
        )
        identity.append(GiftOrderModel.prospect_id.in_(same_email_prospects))
    if not identity:
        return None

    return db.scalar(
        select(GiftOrderModel)
        .where(
            GiftOrderModel.owner_user_id == owner_user_id,
            GiftOrderModel.requested_at >= cutoff,
            or_(
                GiftOrderModel.payment_status.in_(_SUCCESSFUL_PAYMENT_STATUSES),
                GiftOrderModel.status.in_(_SUCCESSFUL_ORDER_STATUSES),
            ),
            or_(*identity),
        )
        .order_by(GiftOrderModel.requested_at.desc())
        .limit(1)
    )


def _skipped_regift_result(
    *,
    event: CrmReminderEventModel,
    recent: GiftOrderModel,
) -> dict:
    return {
        "status": REGIFT_SKIP_STATUS,
        "reason": "recent_gift",
        "event_id": event.id,
        "prospect_id": event.prospect_id,
        "recent_order_id": recent.id,
        "window_days": _regift_window_days(),
    }


def default_stage_recipes() -> list[dict[str, str | None]]:
    """First-connect recipes: Demo / Closed Won / Renewal → pack."""
    return [
        {"stage_name": "Demo Completed", "gift_id": "cookies-4", "note": None},
        {"stage_name": "Closed Won", "gift_id": "cookies-12", "note": None},
        {"stage_name": "Renewal", "gift_id": "cookies-4", "note": None},
    ]


def parse_stored_recipes(raw: object) -> list[dict[str, str | None]]:
    """Normalize persisted JSON into valid stage recipes (skip junk rows)."""
    if not raw:
        return []
    payload: Any = raw
    if isinstance(payload, str):
        try:
            payload = json.loads(payload)
        except json.JSONDecodeError:
            return []
    if not isinstance(payload, list):
        return []
    out: list[dict[str, str | None]] = []
    seen: set[str] = set()
    for item in payload:
        if not isinstance(item, dict):
            continue
        stage = str(item.get("stage_name") or "").strip()
        gift = str(item.get("gift_id") or "").strip()
        note_raw = item.get("note")
        note = str(note_raw).strip() if note_raw else None
        if not stage or gift not in AUTO_ORDER_GIFT_IDS:
            continue
        key = stage.casefold()
        if key in seen:
            continue
        seen.add(key)
        out.append(
            {
                "stage_name": stage[:255],
                "gift_id": gift,
                "note": (note[:1000] if note else None),
            }
        )
        if len(out) >= MAX_STAGE_RECIPES:
            break
    return out


def effective_stage_recipes(
    connection: IntegrationConnectionModel,
    *,
    fallback_gift_id: str | None = None,
) -> list[dict[str, str | None]]:
    """Stored recipes, or a single fallback from trigger_stage_name."""
    parsed = parse_stored_recipes(getattr(connection, "stage_recipes", None))
    if parsed:
        return parsed
    stage = (connection.trigger_stage_name or DEFAULT_TRIGGER_STAGE).strip()
    if not stage:
        stage = DEFAULT_TRIGGER_STAGE
    gift = (fallback_gift_id or "").strip()
    if gift not in AUTO_ORDER_GIFT_IDS:
        gift = "cookies-4"
    return [{"stage_name": stage, "gift_id": gift, "note": None}]


def match_stage_recipe(
    connection: IntegrationConnectionModel,
    stage_name: str,
    *,
    fallback_gift_id: str | None = None,
) -> dict[str, str | None] | None:
    """Return the recipe whose stage matches incoming (case-insensitive)."""
    incoming = (stage_name or "").strip()
    if not incoming:
        return None
    wanted = incoming.casefold()
    for recipe in effective_stage_recipes(connection, fallback_gift_id=fallback_gift_id):
        if str(recipe["stage_name"]).casefold() == wanted:
            return recipe
    return None


def recipe_stage_names(connection: IntegrationConnectionModel) -> list[str]:
    return [str(recipe["stage_name"]) for recipe in effective_stage_recipes(connection)]


def ensure_crm_auto_order_defaults(db: Session, user_id: int) -> None:
    """Turn on auto-order with a default pack when a user first connects a CRM."""
    user = db.get(UserModel, user_id)
    if user is None:
        return
    changed = False
    if not user.auto_order_enabled:
        user.auto_order_enabled = True
        changed = True
    if (user.auto_order_gift_id or "").strip() not in AUTO_ORDER_GIFT_IDS:
        user.auto_order_gift_id = "cookies-4"
        changed = True
    if changed:
        db.add(user)
        db.commit()


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


def _clean_note(note: str | None) -> str:
    cleaned = (note or "").strip()
    if not cleaned:
        return DEFAULT_AUTO_ORDER_NOTE
    return cleaned[:1000]


def _create_auto_order(
    db: Session,
    *,
    owner: UserModel,
    prospect: ProspectModel,
    gift_id: str | None = None,
    cookie_note: str | None = None,
    cookie_company: str | None = None,
    cookie_street: str | None = None,
    cookie_street2: str | None = None,
    cookie_city: str | None = None,
    cookie_state: str | None = None,
    cookie_postal_code: str | None = None,
    cookie_country: str | None = None,
    cookie_address: str | None = None,
) -> dict:
    """Create a gift order from a CRM stage hit, using CRM note/address when present."""
    chosen = (gift_id or "").strip()
    if chosen not in AUTO_ORDER_GIFT_IDS:
        chosen = (owner.auto_order_gift_id or "").strip()
    if chosen not in AUTO_ORDER_GIFT_IDS:
        chosen = "cookies-4"
    gift_id = chosen

    recipient_email = (prospect.email or "").strip().lower()
    email_junk = is_junk_crm_email(recipient_email)
    order_email = None if email_junk else (recipient_email or None)

    note = _clean_note(cookie_note)
    address_quality = crm_address_quality(
        company=cookie_company,
        street=cookie_street,
        street2=cookie_street2,
        city=cookie_city,
        state=cookie_state,
        postal_code=cookie_postal_code,
        country=cookie_country,
        blob=cookie_address,
    )
    if address_quality == ADDRESS_USABLE:
        address_values = shipping_address_values(
            parts=parts_from_cookie_fields(
                company=cookie_company,
                street=cookie_street,
                street2=cookie_street2,
                city=cookie_city,
                state=cookie_state,
                postal_code=cookie_postal_code,
                country=cookie_country,
            ),
            blob=cookie_address,
        )
        has_address = bool((address_values.get("shipping_address") or "").strip())
    else:
        # Blank = request address from recipient. Junk parts are ignored
        # so we never ship to an incomplete or fake CRM address.
        address_values = empty_shipping_address_values()
        has_address = False

    if email_junk and not has_address:
        return {
            "status": "held_junk",
            "reason": "junk_email_no_address",
            "has_shipping_address": False,
        }

    if has_address:
        order = GiftOrderModel(
            owner_user_id=owner.id,
            prospect_id=prospect.id,
            gift_id=gift_id,
            recipient_name=prospect.name,
            **address_values,
            recipient_email=order_email,
            note=note,
            status="pending_payment",
            payment_status="pending",
        )
    else:
        token, expires_at = _mint_address_token()
        order = GiftOrderModel(
            owner_user_id=owner.id,
            prospect_id=prospect.id,
            gift_id=gift_id,
            recipient_name=prospect.name,
            **empty_shipping_address_values(),
            recipient_email=order_email,
            note=note,
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
        try:
            order = prepare_monthly_owed_order(order, db)
        except HTTPException as exc:
            logger.warning(
                "Auto-order blocked by spending limit order_id=%s detail=%s",
                order.id,
                exc.detail,
            )
            db.delete(order)
            db.commit()
            return {
                "status": "error",
                "reason": "spending_limit",
                "detail": exc.detail,
            }
        return {
            "status": "auto_ordered",
            "order_id": order.id,
            "billing": "monthly",
            "payment_status": order.payment_status,
            "order_status": order.status,
            "has_shipping_address": has_address,
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
        "order_status": order.status,
        "has_shipping_address": has_address,
    }


def process_stage_completed_reminder(
    db: Session,
    *,
    connection: IntegrationConnectionModel,
    opportunity_id: str,
    stage_name: str,
    contact_name: str,
    contact_email: str,
    cookie_note: str | None = None,
    cookie_company: str | None = None,
    cookie_street: str | None = None,
    cookie_street2: str | None = None,
    cookie_city: str | None = None,
    cookie_state: str | None = None,
    cookie_postal_code: str | None = None,
    cookie_country: str | None = None,
    cookie_address: str | None = None,
) -> dict:
    """Upsert prospect, dedupe by opportunity, then auto-order or email reminder.

    When auto-order is enabled, CRM cookie note / address fill the gift order
    (address present → ready to pay/ship; blank address → request from recipient).
    Junk email plus no usable address holds the auto-order (``held_junk``);
    junk address parts are ignored so we ask the recipient instead.
    A successful gift to the same person inside the re-gift window is skipped.

    Returns a small status dict for API/logging. Does not raise on email transport
    failure (Resend is best-effort, matching other order emails).
    """
    incoming = (stage_name or "").strip()
    recipe = match_stage_recipe(connection, incoming)
    if recipe is None:
        expected = recipe_stage_names(connection)
        return {
            "status": "ignored",
            "reason": "stage_mismatch",
            "expected": expected[0] if len(expected) == 1 else expected,
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
        owner = db.get(UserModel, connection.owner_user_id)
        prospect = (
            db.get(ProspectModel, existing_event.prospect_id)
            if existing_event.prospect_id
            else None
        )
        recent = (
            find_recent_successful_gift(
                db,
                owner_user_id=connection.owner_user_id,
                email=(prospect.email if prospect else None) or contact_email,
                prospect_id=existing_event.prospect_id,
            )
            if owner
            else None
        )
        if recent is not None:
            if existing_event.status not in {"auto_ordered", REGIFT_SKIP_STATUS}:
                existing_event.status = REGIFT_SKIP_STATUS
                db.add(existing_event)
                db.commit()
            return _skipped_regift_result(event=existing_event, recent=recent)
        return {
            "status": "duplicate",
            "event_id": existing_event.id,
            "prospect_id": existing_event.prospect_id,
            "retryable": event_is_retryable(existing_event.status),
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

    gift_id = str(recipe["gift_id"])
    if not parse_stored_recipes(getattr(connection, "stage_recipes", None)):
        profile_gift = (owner.auto_order_gift_id or "").strip()
        if profile_gift in AUTO_ORDER_GIFT_IDS:
            gift_id = profile_gift
    recipe_note = recipe.get("note")
    note_for_order = cookie_note if (cookie_note or "").strip() else recipe_note

    from_param = _REMINDER_FROM.get(connection.provider, "crm_reminder")
    order_url = (
        f"{settings.web_base_url.rstrip('/')}/orders/new"
        f"?prospect_id={prospect.id}&from={from_param}&gift_id={gift_id}"
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

    if owner.auto_order_enabled:
        recent = find_recent_successful_gift(
            db,
            owner_user_id=owner.id,
            email=prospect.email or contact_email,
            prospect_id=prospect.id,
        )
        if recent is not None:
            event.status = REGIFT_SKIP_STATUS
            event.email_sent_at = None
            db.add(event)
            db.commit()
            logger.info(
                "CRM auto-order skipped re-gift connection_id=%s opportunity=%s prospect_id=%s recent_order_id=%s",
                connection.id,
                opportunity_id,
                prospect.id,
                recent.id,
            )
            return _skipped_regift_result(event=event, recent=recent)

        auto_result = _create_auto_order(
            db,
            owner=owner,
            prospect=prospect,
            gift_id=gift_id,
            cookie_note=note_for_order,
            cookie_company=cookie_company,
            cookie_street=cookie_street,
            cookie_street2=cookie_street2,
            cookie_city=cookie_city,
            cookie_state=cookie_state,
            cookie_postal_code=cookie_postal_code,
            cookie_country=cookie_country,
            cookie_address=cookie_address,
        )
        result_status = auto_result.get("status")
        if result_status == "auto_ordered":
            event.status = "auto_ordered"
        elif result_status == "held_junk":
            event.status = "held_junk"
            send_auto_order_held_junk(
                to_email=owner.email,
                prospect_name=prospect.name,
                crm_name=_CRM_LABELS.get(connection.provider, connection.provider.title()),
                order_url=order_url,
            )
        else:
            event.status = "error"
        db.add(event)
        db.commit()
        logger.info(
            "CRM auto-order connection_id=%s opportunity=%s prospect_id=%s result=%s has_address=%s",
            connection.id,
            opportunity_id,
            prospect.id,
            auto_result.get("status"),
            auto_result.get("has_shipping_address"),
        )
        return {
            **auto_result,
            "event_id": event.id,
            "prospect_id": prospect.id,
            "order_url": auto_result.get("order_url") or order_url,
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


def list_crm_reminder_events(
    db: Session,
    *,
    owner_user_id: int,
    retryable_only: bool = False,
    limit: int = 50,
) -> list[CrmReminderEventModel]:
    """Owner-scoped CRM event journal (newest first)."""
    stmt = (
        select(CrmReminderEventModel)
        .where(CrmReminderEventModel.owner_user_id == owner_user_id)
        .order_by(CrmReminderEventModel.created_at.desc())
        .limit(max(1, min(limit, 100)))
    )
    if retryable_only:
        stmt = stmt.where(CrmReminderEventModel.status.in_(RETRYABLE_EVENT_STATUSES))
    return list(db.scalars(stmt).all())


def retry_failed_auto_order(
    db: Session,
    *,
    event: CrmReminderEventModel,
) -> dict:
    """Retry `_create_auto_order` for an error/held event. Does not retry successes."""
    if not event_is_retryable(event.status):
        raise HTTPException(
            status_code=400,
            detail="Only failed or held auto-orders can be retried.",
        )

    owner = db.get(UserModel, event.owner_user_id)
    if owner is None:
        raise HTTPException(status_code=404, detail="Owner not found.")

    prospect = db.get(ProspectModel, event.prospect_id) if event.prospect_id else None
    if prospect is None:
        raise HTTPException(status_code=400, detail="Prospect is missing for this event.")

    recent = find_recent_successful_gift(
        db,
        owner_user_id=owner.id,
        email=prospect.email,
        prospect_id=prospect.id,
    )
    if recent is not None:
        event.status = REGIFT_SKIP_STATUS
        db.add(event)
        db.commit()
        return _skipped_regift_result(event=event, recent=recent)

    auto_result = _create_auto_order(db, owner=owner, prospect=prospect)
    result_status = auto_result.get("status")
    if result_status == "auto_ordered":
        event.status = "auto_ordered"
    elif result_status == "held_junk":
        event.status = "held_junk"
    else:
        event.status = "error"
    db.add(event)
    db.commit()
    logger.info(
        "CRM auto-order retry event_id=%s prospect_id=%s result=%s",
        event.id,
        prospect.id,
        auto_result.get("status"),
    )
    return {
        **auto_result,
        "event_id": event.id,
        "prospect_id": prospect.id,
    }
