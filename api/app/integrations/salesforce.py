"""Salesforce OAuth, REST helpers, and stage-event intake."""

from __future__ import annotations

import base64
import hashlib
import hmac
import logging
import secrets
from datetime import UTC, datetime
from typing import Any
from urllib.parse import urlencode

import httpx
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..config import settings
from ..models import IntegrationConnectionModel
from .crypto import decrypt_token, encrypt_token
from .reminders import (
    PROVIDER_SALESFORCE,
    ensure_crm_auto_order_defaults,
    process_stage_completed_reminder,
)

logger = logging.getLogger(__name__)


def salesforce_configured() -> bool:
    return bool(settings.salesforce_client_id and settings.salesforce_client_secret)


def redirect_uri() -> str:
    if settings.salesforce_redirect_uri:
        return settings.salesforce_redirect_uri
    return f"{settings.api_base_url.rstrip('/')}/integrations/salesforce/callback"


def _state_secret() -> bytes:
    raw = settings.integration_token_fernet_key or settings.salesforce_client_secret or "dev"
    return hashlib.sha256(raw.encode("utf-8")).digest()


def make_pkce_pair() -> tuple[str, str]:
    """Return (code_verifier, code_challenge) for S256 PKCE."""
    # token_urlsafe(64) is ~86 chars; PKCE allows 43–128.
    code_verifier = secrets.token_urlsafe(64)
    digest = hashlib.sha256(code_verifier.encode("ascii")).digest()
    code_challenge = base64.urlsafe_b64encode(digest).rstrip(b"=").decode("ascii")
    return code_verifier, code_challenge


def sign_oauth_state(user_id: int, code_verifier: str) -> str:
    nonce = secrets.token_urlsafe(16)
    payload = f"{user_id}:{nonce}:{code_verifier}"
    sig = hmac.new(_state_secret(), payload.encode("utf-8"), hashlib.sha256).hexdigest()
    return f"{payload}:{sig}"


def verify_oauth_state(state: str) -> tuple[int, str] | None:
    """Return (user_id, code_verifier) when state is valid."""
    parts = (state or "").split(":")
    if len(parts) != 4:
        return None
    user_id_s, nonce, code_verifier, sig = parts
    payload = f"{user_id_s}:{nonce}:{code_verifier}"
    expected = hmac.new(_state_secret(), payload.encode("utf-8"), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(expected, sig):
        return None
    try:
        return int(user_id_s), code_verifier
    except ValueError:
        return None


def build_authorize_url(user_id: int) -> str:
    code_verifier, code_challenge = make_pkce_pair()
    params = {
        "response_type": "code",
        "client_id": settings.salesforce_client_id,
        "redirect_uri": redirect_uri(),
        "scope": "api refresh_token",
        "state": sign_oauth_state(user_id, code_verifier),
        "code_challenge": code_challenge,
        "code_challenge_method": "S256",
    }
    return f"{settings.salesforce_login_url}/services/oauth2/authorize?{urlencode(params)}"


def exchange_code_for_tokens(code: str, *, code_verifier: str) -> dict[str, Any]:
    data = {
        "grant_type": "authorization_code",
        "code": code,
        "client_id": settings.salesforce_client_id,
        "client_secret": settings.salesforce_client_secret,
        "redirect_uri": redirect_uri(),
        "code_verifier": code_verifier,
    }
    with httpx.Client(timeout=30.0) as client:
        resp = client.post(
            f"{settings.salesforce_login_url}/services/oauth2/token",
            data=data,
        )
        resp.raise_for_status()
        return resp.json()


def refresh_access_token(refresh_token: str) -> dict[str, Any]:
    data = {
        "grant_type": "refresh_token",
        "refresh_token": refresh_token,
        "client_id": settings.salesforce_client_id,
        "client_secret": settings.salesforce_client_secret,
    }
    with httpx.Client(timeout=30.0) as client:
        resp = client.post(
            f"{settings.salesforce_login_url}/services/oauth2/token",
            data=data,
        )
        resp.raise_for_status()
        return resp.json()


def upsert_connection_from_oauth(
    db: Session,
    *,
    user_id: int,
    token_payload: dict[str, Any],
) -> IntegrationConnectionModel:
    access = token_payload.get("access_token") or ""
    refresh = token_payload.get("refresh_token") or ""
    instance_url = (token_payload.get("instance_url") or "").rstrip("/")
    # id URL looks like https://login.salesforce.com/id/00Dxx/005xx
    org_id = None
    id_url = token_payload.get("id") or ""
    parts = id_url.rstrip("/").split("/")
    if len(parts) >= 2 and parts[-2].startswith("00D"):
        org_id = parts[-2]

    existing = db.scalar(
        select(IntegrationConnectionModel).where(
            IntegrationConnectionModel.owner_user_id == user_id,
            IntegrationConnectionModel.provider == PROVIDER_SALESFORCE,
        )
    )
    created = existing is None
    if existing:
        connection = existing
    else:
        connection = IntegrationConnectionModel(
            owner_user_id=user_id,
            provider=PROVIDER_SALESFORCE,
            trigger_stage_name="Demo Completed",
            enabled=True,
        )
        db.add(connection)

    connection.instance_url = instance_url or connection.instance_url
    connection.external_org_id = org_id or connection.external_org_id
    if access:
        connection.access_token_encrypted = encrypt_token(access)
    if refresh:
        connection.refresh_token_encrypted = encrypt_token(refresh)
    connection.enabled = True
    connection.updated_at = datetime.now(UTC)
    db.commit()
    db.refresh(connection)
    if created:
        ensure_crm_auto_order_defaults(db, user_id)
    return connection


def _access_headers(connection: IntegrationConnectionModel, db: Session) -> dict[str, str]:
    if not connection.access_token_encrypted:
        raise ValueError("Salesforce connection has no access token.")
    access = decrypt_token(connection.access_token_encrypted)
    return {"Authorization": f"Bearer {access}", "Content-Type": "application/json"}


def _ensure_fresh_token(connection: IntegrationConnectionModel, db: Session) -> dict[str, str]:
    """Return auth headers, refreshing once on 401-class failures during SOQL."""
    return _access_headers(connection, db)


def _refresh_connection_tokens(connection: IntegrationConnectionModel, db: Session) -> None:
    if not connection.refresh_token_encrypted:
        raise ValueError("Salesforce connection has no refresh token.")
    refresh = decrypt_token(connection.refresh_token_encrypted)
    payload = refresh_access_token(refresh)
    access = payload.get("access_token") or ""
    if access:
        connection.access_token_encrypted = encrypt_token(access)
    new_refresh = payload.get("refresh_token")
    if new_refresh:
        connection.refresh_token_encrypted = encrypt_token(new_refresh)
    if payload.get("instance_url"):
        connection.instance_url = str(payload["instance_url"]).rstrip("/")
    connection.updated_at = datetime.now(UTC)
    db.commit()
    db.refresh(connection)


def soql_query(connection: IntegrationConnectionModel, db: Session, query: str) -> dict[str, Any]:
    if not connection.instance_url:
        raise ValueError("Salesforce connection has no instance URL.")
    url = f"{connection.instance_url}/services/data/v59.0/query"
    headers = _ensure_fresh_token(connection, db)
    with httpx.Client(timeout=30.0) as client:
        resp = client.get(url, headers=headers, params={"q": query})
        if resp.status_code == 401:
            _refresh_connection_tokens(connection, db)
            headers = _access_headers(connection, db)
            resp = client.get(url, headers=headers, params={"q": query})
        resp.raise_for_status()
        return resp.json()


def _cookie_field_names() -> tuple[str | None, str | None]:
    note = settings.salesforce_cookie_note_field or None
    address = settings.salesforce_cookie_address_field or None
    return note, address


def _opportunity_select_clause(*, include_cookie_fields: bool) -> str:
    fields = [
        "Id",
        "Name",
        "StageName",
        "ContactId",
        "Contact.Name",
        "Contact.Email",
    ]
    if include_cookie_fields:
        note_field, address_field = _cookie_field_names()
        if note_field:
            fields.append(note_field)
        if address_field:
            fields.append(address_field)
    return ", ".join(fields)


def poll_demo_completed(connection: IntegrationConnectionModel, db: Session) -> list[dict]:
    """Poll Opportunities in the trigger stage modified since last poll; send reminders."""
    stage = (connection.trigger_stage_name or "Demo Completed").replace("'", "\\'")
    since = connection.last_polled_at
    if since is None:
        # First poll: only look back a short window to avoid flooding historical deals.
        since = datetime.now(UTC).replace(hour=0, minute=0, second=0, microsecond=0)
    since_s = since.strftime("%Y-%m-%dT%H:%M:%SZ")
    where = (
        f"WHERE StageName = '{stage}' "
        f"AND SystemModstamp > {since_s} "
        "ORDER BY SystemModstamp ASC "
        "LIMIT 50"
    )
    note_field, address_field = _cookie_field_names()
    include_cookie_fields = bool(note_field or address_field)
    try:
        query = (
            f"SELECT {_opportunity_select_clause(include_cookie_fields=include_cookie_fields)} "
            f"FROM Opportunity {where}"
        )
        raw = soql_query(connection, db, query)
    except httpx.HTTPStatusError as exc:
        # Custom fields may not exist yet in the org — fall back to core fields.
        body = (exc.response.text or "").lower()
        if include_cookie_fields and exc.response.status_code == 400 and "invalid" in body:
            logger.warning(
                "Salesforce cookie fields missing; polling without note/address connection_id=%s",
                connection.id,
            )
            query = (
                f"SELECT {_opportunity_select_clause(include_cookie_fields=False)} "
                f"FROM Opportunity {where}"
            )
            raw = soql_query(connection, db, query)
            note_field, address_field = None, None
        else:
            raise
    results: list[dict] = []
    for record in raw.get("records") or []:
        contact = record.get("Contact") or {}
        cookie_note = str(record.get(note_field) or "") if note_field else ""
        cookie_address = str(record.get(address_field) or "") if address_field else ""
        results.append(
            process_stage_completed_reminder(
                db,
                connection=connection,
                opportunity_id=str(record.get("Id") or ""),
                stage_name=str(record.get("StageName") or stage),
                contact_name=str(contact.get("Name") or record.get("Name") or ""),
                contact_email=str(contact.get("Email") or ""),
                cookie_note=cookie_note or None,
                cookie_address=cookie_address or None,
            )
        )
    connection.last_polled_at = datetime.now(UTC)
    connection.updated_at = datetime.now(UTC)
    db.commit()
    return results


def verify_webhook_secret(provided: str | None) -> bool:
    expected = settings.salesforce_webhook_secret
    if not expected:
        # In development, allow events when no secret is configured so local
        # testing works; production should always set SALESFORCE_WEBHOOK_SECRET.
        return settings.app_env.lower() != "production"
    if not provided:
        return False
    return hmac.compare_digest(provided.strip(), expected)
