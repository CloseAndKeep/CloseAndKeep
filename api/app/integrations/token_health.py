"""Flag dead CRM OAuth tokens, journal the expiry, and email reconnect once."""

from __future__ import annotations

import logging
from datetime import UTC, datetime

from sqlalchemy.orm import Session

from ..config import settings
from ..models import CrmReminderEventModel, IntegrationConnectionModel, UserModel
from ..order_email import send_crm_reconnect

logger = logging.getLogger(__name__)

TOKEN_STATUS_OK = "ok"
TOKEN_STATUS_NEEDS_RECONNECT = "needs_reconnect"
TOKEN_EXPIRED_STATUS = "token_expired"

_CRM_LABELS = {
    "salesforce": "Salesforce",
    "hubspot": "HubSpot",
}

_AUTH_FAILURE_STATUSES = frozenset({400, 401, 403})


def provider_label(provider: str) -> str:
    return _CRM_LABELS.get(provider, (provider or "CRM").title())


def is_auth_refresh_failure(exc: BaseException) -> bool:
    """True for OAuth token-endpoint auth failures (not timeouts or 5xx)."""
    response = getattr(exc, "response", None)
    status = getattr(response, "status_code", None)
    if status in _AUTH_FAILURE_STATUSES:
        return True
    return isinstance(exc, ValueError)


def mark_tokens_healthy(connection: IntegrationConnectionModel, db: Session) -> None:
    """Clear reconnect flags after a successful OAuth connect or refresh."""
    connection.token_status = TOKEN_STATUS_OK
    connection.token_error_at = None
    connection.reconnect_email_sent_at = None
    connection.updated_at = datetime.now(UTC)
    db.add(connection)
    db.commit()
    db.refresh(connection)


def handle_refresh_failure(connection: IntegrationConnectionModel, db: Session) -> None:
    """Clear tokens, journal login-expired, and email the owner once.

    Does not log token values. Email is attempted only while
    ``reconnect_email_sent_at`` is unset; it is stamped when send succeeds.
    """
    now = datetime.now(UTC)
    already_flagged = connection.token_status == TOKEN_STATUS_NEEDS_RECONNECT
    logger.warning(
        "CRM token refresh failed connection_id=%s provider=%s already_flagged=%s",
        connection.id,
        connection.provider,
        already_flagged,
    )

    connection.token_status = TOKEN_STATUS_NEEDS_RECONNECT
    connection.token_error_at = connection.token_error_at or now
    connection.access_token_encrypted = None
    connection.refresh_token_encrypted = None
    connection.updated_at = now

    if not already_flagged:
        event = CrmReminderEventModel(
            connection_id=connection.id,
            owner_user_id=connection.owner_user_id,
            prospect_id=None,
            provider=connection.provider,
            external_event_key=f"token_expired:{connection.id}:{now.isoformat()}",
            stage_name="login expired",
            status=TOKEN_EXPIRED_STATUS,
            email_sent_at=None,
        )
        db.add(event)

    db.add(connection)
    db.commit()
    db.refresh(connection)

    if connection.reconnect_email_sent_at is not None:
        return

    owner = db.get(UserModel, connection.owner_user_id)
    if owner is None or not (owner.email or "").strip():
        return

    integrations_url = f"{settings.web_base_url.rstrip('/')}/integrations"
    sent = send_crm_reconnect(
        to_email=owner.email,
        provider_label=provider_label(connection.provider),
        integrations_url=integrations_url,
    )
    if sent:
        connection.reconnect_email_sent_at = datetime.now(UTC)
        connection.updated_at = datetime.now(UTC)
        db.add(connection)
        db.commit()
        db.refresh(connection)
