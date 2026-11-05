"""HubSpot OAuth, REST helpers, and deal-stage event intake."""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import logging
import secrets
from datetime import UTC, datetime, timedelta
from typing import Any
from urllib.parse import urlencode

import httpx
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..config import settings
from ..models import CrmReminderEventModel, HubSpotPendingInstallModel, IntegrationConnectionModel
from .check_setup import build_setup_report
from .crypto import decrypt_token, encrypt_token
from .reminders import (
    PROVIDER_HUBSPOT,
    default_stage_recipes,
    ensure_crm_auto_order_defaults,
    process_stage_completed_reminder,
    recipe_stage_names,
)
from .token_health import handle_refresh_failure, is_auth_refresh_failure, mark_tokens_healthy

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
    created = existing is None
    if existing:
        connection = existing
    else:
        connection = IntegrationConnectionModel(
            owner_user_id=user_id,
            provider=PROVIDER_HUBSPOT,
            trigger_stage_name="Demo Completed",
            stage_recipes=default_stage_recipes(),
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
    connection.token_status = "ok"
    connection.token_error_at = None
    connection.reconnect_email_sent_at = None
    connection.updated_at = datetime.now(UTC)
    db.commit()
    db.refresh(connection)
    if created:
        ensure_crm_auto_order_defaults(db, user_id)
    return connection


def _access_headers(connection: IntegrationConnectionModel) -> dict[str, str]:
    if not connection.access_token_encrypted:
        raise ValueError("HubSpot connection has no access token.")
    access = decrypt_token(connection.access_token_encrypted)
    return {"Authorization": f"Bearer {access}", "Content-Type": "application/json"}


def _refresh_connection_tokens(connection: IntegrationConnectionModel, db: Session) -> None:
    try:
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
        mark_tokens_healthy(connection, db)
    except Exception as exc:
        if is_auth_refresh_failure(exc):
            handle_refresh_failure(connection, db)
        raise


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


def _required_cookie_properties() -> list[str]:
    return [
        prop
        for prop in (
            settings.hubspot_cookie_note_property,
            settings.hubspot_cookie_company_property,
            settings.hubspot_cookie_street_property,
            settings.hubspot_cookie_city_property,
            settings.hubspot_cookie_state_property,
            settings.hubspot_cookie_postal_code_property,
        )
        if prop
    ]


def _stage_id_for_label(connection: IntegrationConnectionModel, db: Session, label: str) -> str | None:
    """Resolve a deal-stage display label to HubSpot's internal stage id."""
    wanted = label.strip().casefold()
    for stage_id, stage_label in _pipeline_stage_pairs(connection, db):
        if stage_label.casefold() == wanted:
            return stage_id
    return None


def check_setup(connection: IntegrationConnectionModel, db: Session) -> dict[str, Any]:
    """Inspect deal properties and pipelines for cookie_* fields and the trigger stage."""
    try:
        raw = hubspot_request(connection, db, "GET", "/crm/v3/properties/deals")
        present = {
            str(item.get("name") or "").strip()
            for item in (raw.get("results") or [])
            if item.get("name")
        }
        stage = (connection.trigger_stage_name or "Demo Completed").strip()
        unknown_stage = _stage_id_for_label(connection, db, stage) is None
    except httpx.HTTPStatusError as exc:
        if exc.response.status_code == 401:
            raise ValueError("HubSpot token is invalid or expired.") from exc
        raise

    extra: list[str] = []
    legacy = settings.hubspot_cookie_address_property
    address_props = [
        prop
        for prop in (
            settings.hubspot_cookie_street_property,
            settings.hubspot_cookie_city_property,
            settings.hubspot_cookie_state_property,
            settings.hubspot_cookie_postal_code_property,
        )
        if prop
    ]
    if legacy and legacy in present and any(prop not in present for prop in address_props):
        extra.append(
            f"{legacy} is present as a fallback. "
            "Split street/city/state/ZIP fields are still recommended."
        )

    return build_setup_report(
        provider=PROVIDER_HUBSPOT,
        object_label="Deal",
        trigger_stage_name=stage,
        missing_fields=[prop for prop in _required_cookie_properties() if prop not in present],
        unknown_stage=unknown_stage,
        extra_messages=extra or None,
    )


def _pipeline_stage_pairs(
    connection: IntegrationConnectionModel, db: Session
) -> list[tuple[str, str]]:
    """Return (stage_id, label) pairs from all deal pipelines."""
    pipelines = hubspot_request(connection, db, "GET", "/crm/v3/pipelines/deals")
    pairs: list[tuple[str, str]] = []
    for pipeline in pipelines.get("results") or []:
        for stage in pipeline.get("stages") or []:
            stage_id = str(stage.get("id") or "")
            stage_label = str(stage.get("label") or "")
            if stage_id and stage_label:
                pairs.append((stage_id, stage_label))
    return pairs


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
        return {"name": "", "email": ""}

    contact_id = str(results[0].get("toObjectId") or results[0].get("id") or "")
    if not contact_id:
        return {"name": "", "email": ""}

    contact = hubspot_request(
        connection,
        db,
        "GET",
        f"/crm/v3/objects/contacts/{contact_id}",
        params={
            "properties": "firstname,lastname,email",
        },
    )
    props = contact.get("properties") or {}
    first = (props.get("firstname") or "").strip()
    last = (props.get("lastname") or "").strip()
    name = f"{first} {last}".strip()
    return {
        "name": name,
        "email": (props.get("email") or "").strip(),
    }


def poll_demo_completed(connection: IntegrationConnectionModel, db: Session) -> list[dict]:
    """Poll HubSpot deals in recipe stages modified since last poll; send reminders."""
    wanted_labels = recipe_stage_names(connection)
    pairs = _pipeline_stage_pairs(connection, db)
    label_by_id = {stage_id: label for stage_id, label in pairs}
    id_by_label = {label.casefold(): stage_id for stage_id, label in pairs}
    stage_ids = [
        stage_id
        for label in wanted_labels
        if (stage_id := id_by_label.get(label.casefold()))
    ]
    if not stage_ids:
        logger.warning(
            "HubSpot stage labels %r not found in deal pipelines connection_id=%s",
            wanted_labels,
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

    note_prop = settings.hubspot_cookie_note_property or ""
    company_prop = settings.hubspot_cookie_company_property or ""
    street_prop = settings.hubspot_cookie_street_property or ""
    street2_prop = settings.hubspot_cookie_street2_property or ""
    city_prop = settings.hubspot_cookie_city_property or ""
    state_prop = settings.hubspot_cookie_state_property or ""
    postal_prop = settings.hubspot_cookie_postal_code_property or ""
    address_prop = settings.hubspot_cookie_address_property or ""
    deal_properties = _deal_property_names()

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
            for stage_id in stage_ids
        ],
        "properties": deal_properties,
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
        cookie_note = str(props.get(note_prop) or "") if note_prop else ""
        cookie_company = str(props.get(company_prop) or "") if company_prop else ""
        cookie_street = str(props.get(street_prop) or "") if street_prop else ""
        cookie_street2 = str(props.get(street2_prop) or "") if street2_prop else ""
        cookie_city = str(props.get(city_prop) or "") if city_prop else ""
        cookie_state = str(props.get(state_prop) or "") if state_prop else ""
        cookie_postal = str(props.get(postal_prop) or "") if postal_prop else ""
        cookie_address = str(props.get(address_prop) or "") if address_prop else ""
        results.append(
            process_stage_completed_reminder(
                db,
                connection=connection,
                opportunity_id=deal_id,
                stage_name=label_by_id.get(str(props.get("dealstage") or ""), wanted_labels[0]),
                contact_name=contact["name"] or deal_name,
                contact_email=contact["email"],
                cookie_note=cookie_note or None,
                cookie_company=cookie_company or None,
                cookie_street=cookie_street or None,
                cookie_street2=cookie_street2 or None,
                cookie_city=cookie_city or None,
                cookie_state=cookie_state or None,
                cookie_postal_code=cookie_postal or None,
                cookie_address=cookie_address or None,
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


_HUBSPOT_URI_DECODE = (
    ("%3A", ":"),
    ("%2F", "/"),
    ("%3F", "?"),
    ("%40", "@"),
    ("%21", "!"),
    ("%24", "$"),
    ("%27", "'"),
    ("%28", "("),
    ("%29", ")"),
    ("%2A", "*"),
    ("%2C", ","),
    ("%3B", ";"),
)
_SIGNATURE_MAX_AGE_MS = 5 * 60 * 1000
_PENDING_INSTALL_TTL = timedelta(minutes=30)

_DEAL_STATUS_LABELS = {
    "sent": "Reminder sent. Open CloseAndKeep to send the cookies.",
    "auto_ordered": "Cookie order created for this deal.",
    "held_junk": "Waiting on a usable email or address before sending cookies.",
    "error": "The last cookie attempt failed. Retry it from CloseAndKeep Integrations.",
    "skipped_regift": "Skipped. This person was gifted recently.",
}


def _deal_property_names() -> list[str]:
    names = ["dealname", "dealstage"]
    for prop in (
        settings.hubspot_cookie_note_property,
        settings.hubspot_cookie_company_property,
        settings.hubspot_cookie_street_property,
        settings.hubspot_cookie_street2_property,
        settings.hubspot_cookie_city_property,
        settings.hubspot_cookie_state_property,
        settings.hubspot_cookie_postal_code_property,
        settings.hubspot_cookie_address_property,
    ):
        if prop and prop not in names:
            names.append(prop)
    return names


def _cookie_fields_from_props(props: dict[str, Any]) -> dict[str, str | None]:
    def _value(name: str) -> str | None:
        if not name:
            return None
        raw = str(props.get(name) or "").strip()
        return raw or None

    return {
        "cookie_note": _value(settings.hubspot_cookie_note_property or ""),
        "cookie_company": _value(settings.hubspot_cookie_company_property or ""),
        "cookie_street": _value(settings.hubspot_cookie_street_property or ""),
        "cookie_street2": _value(settings.hubspot_cookie_street2_property or ""),
        "cookie_city": _value(settings.hubspot_cookie_city_property or ""),
        "cookie_state": _value(settings.hubspot_cookie_state_property or ""),
        "cookie_postal_code": _value(settings.hubspot_cookie_postal_code_property or ""),
        "cookie_address": _value(settings.hubspot_cookie_address_property or ""),
    }


def normalize_hubspot_request_uri(uri: str) -> str:
    """Decode the query characters HubSpot decodes before signing a v3 request."""
    uri = (uri or "").split("#", 1)[0]
    query_pos = uri.find("?")
    if query_pos == -1:
        return uri
    path = uri[: query_pos + 1]
    query = uri[query_pos + 1 :]
    for encoded, decoded in _HUBSPOT_URI_DECODE:
        query = query.replace(encoded, decoded).replace(encoded.lower(), decoded)
    return path + query


def public_request_uri(path: str, query: str = "") -> str:
    """Public URL HubSpot signed. Uses API_BASE_URL, not the internal proxy host."""
    base = settings.api_base_url.rstrip("/")
    uri = f"{base}{path}"
    if query:
        uri = f"{uri}?{query}"
    return uri


def hubspot_v3_signature(*, method: str, uri: str, body: str, timestamp: str) -> str:
    source = f"{method.upper()}{normalize_hubspot_request_uri(uri)}{body}{timestamp}"
    digest = hmac.new(
        settings.hubspot_client_secret.encode("utf-8"),
        source.encode("utf-8"),
        hashlib.sha256,
    ).digest()
    return base64.b64encode(digest).decode("ascii")


def verify_hubspot_v3_signature(
    *,
    method: str,
    uri: str,
    body: str,
    timestamp: str | None,
    signature: str | None,
    now_ms: int | None = None,
) -> bool:
    """Validate X-HubSpot-Signature-v3. Unsigned requests are allowed only outside production."""
    if not settings.hubspot_client_secret:
        return settings.app_env.lower() != "production"
    if not signature or not timestamp:
        return False
    try:
        ts = int(timestamp)
    except ValueError:
        return False
    now = now_ms if now_ms is not None else int(datetime.now(UTC).timestamp() * 1000)
    if now - ts > _SIGNATURE_MAX_AGE_MS:
        return False
    expected = hubspot_v3_signature(method=method, uri=uri, body=body, timestamp=timestamp)
    if len(expected) != len(signature):
        return False
    return hmac.compare_digest(expected, signature)


def _hash_install_code(code: str) -> str:
    return hashlib.sha256(code.encode("utf-8")).hexdigest()


def _as_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value


def create_pending_install(db: Session, token_payload: dict[str, Any]) -> str:
    """Store marketplace OAuth tokens behind a one-time code. Returns the raw code."""
    access = token_payload.get("access_token") or ""
    refresh = token_payload.get("refresh_token") or ""
    if not access:
        raise ValueError("HubSpot did not return an access token.")
    hub_id = token_payload.get("hub_id") or token_payload.get("hubId")
    portal_id = str(hub_id) if hub_id is not None else ""
    code = secrets.token_urlsafe(32)
    row = HubSpotPendingInstallModel(
        code_hash=_hash_install_code(code),
        portal_id=portal_id or None,
        access_token_encrypted=encrypt_token(access),
        refresh_token_encrypted=encrypt_token(refresh) if refresh else None,
        expires_at=datetime.now(UTC) + _PENDING_INSTALL_TTL,
    )
    db.add(row)
    db.commit()
    return code


def claim_pending_install(db: Session, *, user_id: int, code: str) -> IntegrationConnectionModel:
    """Attach a marketplace install to the signed-in CloseAndKeep user."""
    digest = _hash_install_code((code or "").strip())
    row = db.scalar(
        select(HubSpotPendingInstallModel).where(HubSpotPendingInstallModel.code_hash == digest)
    )
    if row is None or _as_utc(row.expires_at) < datetime.now(UTC):
        if row is not None:
            db.delete(row)
            db.commit()
        raise ValueError("install_expired")

    portal_id = (row.portal_id or "").strip()
    if portal_id:
        other = db.scalar(
            select(IntegrationConnectionModel).where(
                IntegrationConnectionModel.provider == PROVIDER_HUBSPOT,
                IntegrationConnectionModel.external_org_id == portal_id,
                IntegrationConnectionModel.owner_user_id != user_id,
            )
        )
        if other is not None:
            db.delete(row)
            db.commit()
            raise PermissionError("portal_taken")

    payload = {
        "access_token": decrypt_token(row.access_token_encrypted),
        "refresh_token": (
            decrypt_token(row.refresh_token_encrypted) if row.refresh_token_encrypted else ""
        ),
        "hub_id": portal_id or None,
    }
    connection = upsert_connection_from_oauth(db, user_id=user_id, token_payload=payload)
    pending = db.get(HubSpotPendingInstallModel, row.id)
    if pending is not None:
        db.delete(pending)
        db.commit()
    return connection


def connection_for_portal(db: Session, portal_id: str) -> IntegrationConnectionModel | None:
    portal = (portal_id or "").strip()
    if not portal:
        return None
    return db.scalar(
        select(IntegrationConnectionModel).where(
            IntegrationConnectionModel.provider == PROVIDER_HUBSPOT,
            IntegrationConnectionModel.external_org_id == portal,
            IntegrationConnectionModel.enabled.is_(True),
        )
    )


def card_status(db: Session, *, portal_id: str, deal_id: str | None) -> dict[str, Any]:
    """Account link + latest cookie action for a deal card. No tokens or owner emails."""
    connection = connection_for_portal(db, portal_id)
    if connection is None:
        return {"linked": False, "portal_id": (portal_id or "").strip() or None}
    payload: dict[str, Any] = {
        "linked": True,
        "portal_id": connection.external_org_id,
        "token_status": connection.token_status,
        "recipe_stages": recipe_stage_names(connection),
    }
    deal = (deal_id or "").strip()
    if deal:
        event = db.scalar(
            select(CrmReminderEventModel).where(
                CrmReminderEventModel.connection_id == connection.id,
                CrmReminderEventModel.external_event_key == deal,
            )
        )
        status = event.status if event else None
        payload["deal"] = {
            "id": deal,
            "status": status,
            "status_label": _DEAL_STATUS_LABELS.get(status or "", None),
        }
    return payload


def parse_webhook_events(body_text: str) -> list[dict[str, Any]]:
    try:
        payload = json.loads(body_text or "[]")
    except json.JSONDecodeError as exc:
        raise ValueError("invalid_json") from exc
    if isinstance(payload, dict):
        return [payload]
    if isinstance(payload, list) and all(isinstance(item, dict) for item in payload):
        return payload
    raise ValueError("invalid_json")


def _is_deal_stage_event(event: dict[str, Any]) -> bool:
    kind = str(event.get("subscriptionType") or "")
    prop = str(event.get("propertyName") or "")
    if prop != "dealstage":
        return False
    if kind == "deal.propertyChange":
        return True
    if kind != "object.propertyChange":
        return False
    object_type = str(event.get("objectType") or event.get("objectTypeId") or "").casefold()
    return object_type in {"deal", "deals", "0-3"}


def _stage_label_for_value(
    connection: IntegrationConnectionModel, db: Session, property_value: str
) -> str | None:
    raw = property_value.strip()
    if not raw:
        return None
    for stage_id, label in _pipeline_stage_pairs(connection, db):
        if stage_id == raw or label.casefold() == raw.casefold():
            return label
    return None


def ingest_native_webhook_events(db: Session, events: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Turn HubSpot dealstage webhooks into the same cookie intake as Sync now."""
    return [_ingest_native_webhook_event(db, event) for event in events]


def _ingest_native_webhook_event(db: Session, event: dict[str, Any]) -> dict[str, Any]:
    if not _is_deal_stage_event(event):
        return {"status": "ignored", "reason": "unsupported_event"}

    portal_id = str(event.get("portalId") or event.get("portal_id") or "").strip()
    deal_id = str(event.get("objectId") or event.get("object_id") or "").strip()
    connection = connection_for_portal(db, portal_id)
    if connection is None:
        return {"status": "ignored", "reason": "unknown_portal", "portal_id": portal_id or None}
    if not deal_id:
        return {"status": "ignored", "reason": "missing_deal"}

    stage_label = _stage_label_for_value(
        connection, db, str(event.get("propertyValue") or "")
    )
    if not stage_label:
        return {"status": "ignored", "reason": "unknown_stage", "deal_id": deal_id}

    deal = hubspot_request(
        connection,
        db,
        "GET",
        f"/crm/v3/objects/deals/{deal_id}",
        params={"properties": ",".join(_deal_property_names())},
    )
    props = deal.get("properties") or {}
    contact = _contact_for_deal(connection, db, deal_id)
    email = (contact.get("email") or "").strip()
    if "@" not in email:
        return {"status": "ignored", "reason": "missing_contact", "deal_id": deal_id}

    deal_name = str(props.get("dealname") or "").strip()
    fields = _cookie_fields_from_props(props)
    return process_stage_completed_reminder(
        db,
        connection=connection,
        opportunity_id=deal_id,
        stage_name=stage_label,
        contact_name=(contact.get("name") or "").strip() or deal_name or "HubSpot contact",
        contact_email=email,
        cookie_note=fields["cookie_note"],
        cookie_company=fields["cookie_company"],
        cookie_street=fields["cookie_street"],
        cookie_street2=fields["cookie_street2"],
        cookie_city=fields["cookie_city"],
        cookie_state=fields["cookie_state"],
        cookie_postal_code=fields["cookie_postal_code"],
        cookie_address=fields["cookie_address"],
    )
