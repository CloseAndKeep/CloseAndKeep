"""HubSpot OAuth, REST helpers, and deal-stage event intake."""

from __future__ import annotations

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
from .reminders import PROVIDER_HUBSPOT, process_stage_completed_reminder

logger = logging.getLogger(__name__)

HUBSPOT_API = "https://api.hubapi.com"
HUBSPOT_AUTH = "https://app.hubspot.com/oauth/authorize"
HUBSPOT_TOKEN = "https://api.hubapi.com/oauth/v1/token"
# Deals + contacts + companies so we can map Demo Completed → prospect fields.
HUBSPOT_SCOPES = "oauth crm.objects.deals.read crm.objects.contacts.read crm.objects.companies.read"


def hubspot_configured() -> bool:
    return bool(settings.hubspot_client_id and settings.hubspot_client_secret)


def redirect_uri() -> str:
    if settings.hubspot_redirect_uri:
        return settings.hubspot_redirect_uri
    return f"{settings.api_base_url.rstrip('/')}/integrations/hubspot/callback"


def _state_secret() -> bytes:
    raw = settings.integration_token_fernet_key or settings.hubspot_client_secret or "dev"
    return hashlib.sha256(raw.encode("utf-8")).digest()


def sign_oauth_state(user_id: int) -> str:
    nonce = secrets.token_urlsafe(16)
    payload = f"{user_id}:{nonce}"
    sig = hmac.new(_state_secret(), payload.encode("utf-8"), hashlib.sha256).hexdigest()
    return f"{payload}:{sig}"


def verify_oauth_state(state: str) -> int | None:
    parts = (state or "").split(":")
    if len(parts) != 3:
        return None
    user_id_s, nonce, sig = parts
    payload = f"{user_id_s}:{nonce}"
    expected = hmac.new(_state_secret(), payload.encode("utf-8"), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(expected, sig):
        return None
    try:
        return int(user_id_s)
    except ValueError:
        return None


def build_authorize_url(user_id: int) -> str:
    params = {
        "client_id": settings.hubspot_client_id,
        "redirect_uri": redirect_uri(),
        "scope": HUBSPOT_SCOPES,
        "state": sign_oauth_state(user_id),
    }
    return f"{HUBSPOT_AUTH}?{urlencode(params)}"


def exchange_code_for_tokens(code: str) -> dict[str, Any]:
    data = {
        "grant_type": "authorization_code",
        "code": code,
        "client_id": settings.hubspot_client_id,
        "client_secret": settings.hubspot_client_secret,
        "redirect_uri": redirect_uri(),
    }
    with httpx.Client(timeout=30.0) as client:
        resp = client.post(HUBSPOT_TOKEN, data=data)
        resp.raise_for_status()
        return resp.json()


def refresh_access_token(refresh_token: str) -> dict[str, Any]:
    data = {
        "grant_type": "refresh_token",
        "refresh_token": refresh_token,
        "client_id": settings.hubspot_client_id,
        "client_secret": settings.hubspot_client_secret,
    }
    with httpx.Client(timeout=30.0) as client:
        resp = client.post(HUBSPOT_TOKEN, data=data)
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
    hub_id = token_payload.get("hub_id") or token_payload.get("hubId")
    org_id = str(hub_id) if hub_id is not None else None

    existing = db.scalar(
        select(IntegrationConnectionModel).where(
            IntegrationConnectionModel.owner_user_id == user_id,
            IntegrationConnectionModel.provider == PROVIDER_HUBSPOT,
        )
    )
    if existing:
        connection = existing
    else:
        connection = IntegrationConnectionModel(
            owner_user_id=user_id,
            provider=PROVIDER_HUBSPOT,
            trigger_stage_name="Demo Completed",
            enabled=True,
        )
        db.add(connection)

    connection.instance_url = HUBSPOT_API
    connection.external_org_id = org_id or connection.external_org_id
    if access:
        connection.access_token_encrypted = encrypt_token(access)
    if refresh:
        connection.refresh_token_encrypted = encrypt_token(refresh)
    connection.enabled = True
    connection.updated_at = datetime.now(UTC)
    db.commit()
    db.refresh(connection)
    return connection


def _access_headers(connection: IntegrationConnectionModel) -> dict[str, str]:
    if not connection.access_token_encrypted:
        raise ValueError("HubSpot connection has no access token.")
    access = decrypt_token(connection.access_token_encrypted)
    return {"Authorization": f"Bearer {access}", "Content-Type": "application/json"}


def _refresh_connection_tokens(connection: IntegrationConnectionModel, db: Session) -> None:
    if not connection.refresh_token_encrypted:
        raise ValueError("HubSpot connection has no refresh token.")
    refresh = decrypt_token(connection.refresh_token_encrypted)
    payload = refresh_access_token(refresh)
    access = payload.get("access_token") or ""
    if access:
        connection.access_token_encrypted = encrypt_token(access)
    new_refresh = payload.get("refresh_token")
    if new_refresh:
        connection.refresh_token_encrypted = encrypt_token(new_refresh)
    hub_id = payload.get("hub_id") or payload.get("hubId")
    if hub_id is not None:
        connection.external_org_id = str(hub_id)
    connection.updated_at = datetime.now(UTC)
    db.commit()
    db.refresh(connection)


def hubspot_request(
    connection: IntegrationConnectionModel,
    db: Session,
    method: str,
    path: str,
    *,
    json_body: dict | None = None,
    params: dict | None = None,
) -> Any:
    url = f"{HUBSPOT_API}{path}"
    headers = _access_headers(connection)
    with httpx.Client(timeout=30.0) as client:
        resp = client.request(method, url, headers=headers, json=json_body, params=params)
        if resp.status_code == 401:
            _refresh_connection_tokens(connection, db)
            headers = _access_headers(connection)
            resp = client.request(method, url, headers=headers, json=json_body, params=params)
        resp.raise_for_status()
        if resp.status_code == 204 or not resp.content:
            return {}
        return resp.json()


def _stage_id_for_label(connection: IntegrationConnectionModel, db: Session, label: str) -> str | None:
    """Resolve a deal-stage display label to HubSpot's internal stage id."""
    wanted = label.strip().casefold()
    pipelines = hubspot_request(connection, db, "GET", "/crm/v3/pipelines/deals")
    for pipeline in pipelines.get("results") or []:
        for stage in pipeline.get("stages") or []:
            stage_label = str(stage.get("label") or "")
            if stage_label.casefold() == wanted:
                return str(stage.get("id") or "") or None
    return None


def _contact_for_deal(
    connection: IntegrationConnectionModel, db: Session, deal_id: str
) -> dict[str, str]:
    assoc = hubspot_request(
        connection,
        db,
        "GET",
        f"/crm/v4/objects/deals/{deal_id}/associations/contacts",
    )
    results = assoc.get("results") or []
    if not results:
        return {"name": "", "email": "", "title": "", "company": ""}

    contact_id = str(results[0].get("toObjectId") or results[0].get("id") or "")
    if not contact_id:
        return {"name": "", "email": "", "title": "", "company": ""}

    contact = hubspot_request(
        connection,
        db,
        "GET",
        f"/crm/v3/objects/contacts/{contact_id}",
        params={
            "properties": "firstname,lastname,email,jobtitle,company",
        },
    )
    props = contact.get("properties") or {}
    first = (props.get("firstname") or "").strip()
    last = (props.get("lastname") or "").strip()
    name = f"{first} {last}".strip()
    return {
        "name": name,
        "email": (props.get("email") or "").strip(),
        "title": (props.get("jobtitle") or "").strip(),
        "company": (props.get("company") or "").strip(),
    }


def poll_demo_completed(connection: IntegrationConnectionModel, db: Session) -> list[dict]:
    """Poll HubSpot deals in the trigger stage modified since last poll; send reminders."""
    stage_label = (connection.trigger_stage_name or "Demo Completed").strip()
    stage_id = _stage_id_for_label(connection, db, stage_label)
    if not stage_id:
        logger.warning(
            "HubSpot stage label %r not found in deal pipelines connection_id=%s",
            stage_label,
            connection.id,
        )
        connection.last_polled_at = datetime.now(UTC)
        connection.updated_at = datetime.now(UTC)
        db.commit()
        return []

    since = connection.last_polled_at
    if since is None:
        since = datetime.now(UTC).replace(hour=0, minute=0, second=0, microsecond=0)
    since_ms = int(since.timestamp() * 1000)

    search_body = {
        "filterGroups": [
            {
                "filters": [
                    {
                        "propertyName": "dealstage",
                        "operator": "EQ",
                        "value": stage_id,
                    },
                    {
                        "propertyName": "hs_lastmodifieddate",
                        "operator": "GTE",
                        "value": since_ms,
                    },
                ]
            }
        ],
        "properties": ["dealname", "dealstage"],
        "sorts": [{"propertyName": "hs_lastmodifieddate", "direction": "ASCENDING"}],
        "limit": 50,
    }
    raw = hubspot_request(
        connection, db, "POST", "/crm/v3/objects/deals/search", json_body=search_body
    )
    results: list[dict] = []
    for record in raw.get("results") or []:
        deal_id = str(record.get("id") or "")
        if not deal_id:
            continue
        props = record.get("properties") or {}
        contact = _contact_for_deal(connection, db, deal_id)
        deal_name = str(props.get("dealname") or "")
        results.append(
            process_stage_completed_reminder(
                db,
                connection=connection,
                opportunity_id=deal_id,
                stage_name=stage_label,
                contact_name=contact["name"] or deal_name,
                contact_email=contact["email"],
                contact_title=contact["title"],
                company=contact["company"],
            )
        )
    connection.last_polled_at = datetime.now(UTC)
    connection.updated_at = datetime.now(UTC)
    db.commit()
    return results


def verify_webhook_secret(provided: str | None) -> bool:
    expected = settings.hubspot_webhook_secret
    if not expected:
        # In development, allow events when no secret is configured so local
        # testing works; production should always set HUBSPOT_WEBHOOK_SECRET.
        return settings.app_env.lower() != "production"
    if not provided:
        return False
    return hmac.compare_digest(provided.strip(), expected)
