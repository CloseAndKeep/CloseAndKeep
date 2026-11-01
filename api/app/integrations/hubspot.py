"""HubSpot OAuth, REST helpers, and deal-stage event intake."""

from __future__ import annotations

import base64
import hashlib
import hmac
import logging
import secrets
import time
from datetime import UTC, datetime, timedelta
from typing import Any
from urllib.parse import urlencode

import httpx
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from ..config import settings
from ..models import IntegrationConnectionModel, OAuthStateModel
from .check_setup import build_setup_report
from .crypto import decrypt_token, encrypt_token
from .reminders import (
    PROVIDER_HUBSPOT,
    default_stage_recipes,
    ensure_crm_auto_order_defaults,
    match_stage_recipe,
    process_stage_completed_reminder,
    recipe_stage_names,
)
from .token_health import handle_refresh_failure, is_auth_refresh_failure, mark_tokens_healthy

logger = logging.getLogger(__name__)

HUBSPOT_API = "https://api.hubapi.com"
HUBSPOT_AUTH = "https://app.hubspot.com/oauth/authorize"
HUBSPOT_TOKEN = "https://api.hubapi.com/oauth/v1/token"
# Deals + contacts + deal schema so Check setup can read cookie_* properties.
HUBSPOT_SCOPES = (
    "oauth crm.objects.deals.read crm.schemas.deals.read crm.objects.contacts.read"
)
# HubSpot search allows 5 filterGroups. Each recipe stage is its own group
# because the stage-entry property name depends on the stage id.
_SEARCH_FILTER_GROUP_LIMIT = 5
_SEARCH_PAGE_LIMIT = 100
_MAX_DEALS_PER_POLL = 400
_OAUTH_STATE_TTL_SECONDS = 15 * 60
_SIGNATURE_MAX_AGE_MS = 5 * 60 * 1000
_CONTACT_LOOKUP_LIMIT = 10
_RATE_LIMIT_ATTEMPTS = 3


def hubspot_configured() -> bool:
    return bool(settings.hubspot_client_id and settings.hubspot_client_secret)


def redirect_uri() -> str:
    if settings.hubspot_redirect_uri:
        return settings.hubspot_redirect_uri
    return f"{settings.api_base_url.rstrip('/')}/integrations/hubspot/callback"


def webhook_validation_uri(path: str, query: str = "") -> str:
    """Public URL HubSpot signed. Uses API_BASE_URL, not the proxy host."""
    base = settings.api_base_url.rstrip("/")
    uri = f"{base}{path}"
    if query:
        uri = f"{uri}?{query}"
    return uri


def _state_secret() -> bytes:
    raw = settings.integration_token_fernet_key or settings.hubspot_client_secret or "dev"
    return hashlib.sha256(raw.encode("utf-8")).digest()


def _as_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def make_pkce_pair() -> tuple[str, str]:
    """Return (code_verifier, S256 code_challenge)."""
    verifier = secrets.token_urlsafe(64)
    digest = hashlib.sha256(verifier.encode("ascii")).digest()
    challenge = base64.urlsafe_b64encode(digest).rstrip(b"=").decode("ascii")
    return verifier, challenge


def sign_oauth_state(db: Session, user_id: int) -> tuple[str, str]:
    """Persist a single-use nonce and return (state, code_verifier)."""
    now = datetime.now(UTC)
    db.execute(delete(OAuthStateModel).where(OAuthStateModel.expires_at < now))
    nonce = secrets.token_urlsafe(16)
    verifier, _challenge = make_pkce_pair()
    expires = now + timedelta(seconds=_OAUTH_STATE_TTL_SECONDS)
    db.add(
        OAuthStateModel(
            nonce=nonce,
            user_id=user_id,
            provider=PROVIDER_HUBSPOT,
            code_verifier=verifier,
            expires_at=expires,
        )
    )
    db.commit()
    expiry_ts = int(expires.timestamp())
    payload = f"{user_id}:{nonce}:{expiry_ts}"
    sig = hmac.new(_state_secret(), payload.encode("utf-8"), hashlib.sha256).hexdigest()
    return f"{payload}:{sig}", verifier


def verify_oauth_state(db: Session, state: str) -> tuple[int, str] | None:
    """Return (user_id, code_verifier) once. Expired or replayed state fails."""
    parts = (state or "").split(":")
    if len(parts) != 4:
        return None
    user_id_s, nonce, expiry_s, sig = parts
    payload = f"{user_id_s}:{nonce}:{expiry_s}"
    expected = hmac.new(_state_secret(), payload.encode("utf-8"), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(expected, sig):
        return None
    try:
        user_id = int(user_id_s)
        expiry_ts = int(expiry_s)
    except ValueError:
        return None
    if expiry_ts < int(datetime.now(UTC).timestamp()):
        db.execute(delete(OAuthStateModel).where(OAuthStateModel.nonce == nonce))
        db.commit()
        return None
    row = db.get(OAuthStateModel, nonce)
    if row is None or row.user_id != user_id or row.provider != PROVIDER_HUBSPOT:
        return None
    verifier = row.code_verifier or ""
    if _as_utc(row.expires_at) < datetime.now(UTC) or not verifier:
        db.execute(delete(OAuthStateModel).where(OAuthStateModel.nonce == nonce))
        db.commit()
        return None
    deleted = db.execute(delete(OAuthStateModel).where(OAuthStateModel.nonce == nonce))
    db.commit()
    if deleted.rowcount == 0:
        return None
    return user_id, verifier


def build_authorize_url(db: Session, user_id: int) -> str:
    state, verifier = sign_oauth_state(db, user_id)
    challenge = base64.urlsafe_b64encode(
        hashlib.sha256(verifier.encode("ascii")).digest()
    ).rstrip(b"=").decode("ascii")
    params = {
        "client_id": settings.hubspot_client_id,
        "redirect_uri": redirect_uri(),
        "scope": HUBSPOT_SCOPES,
        "state": state,
        "code_challenge": challenge,
        "code_challenge_method": "S256",
    }
    return f"{HUBSPOT_AUTH}?{urlencode(params)}"


def exchange_code_for_tokens(code: str, *, code_verifier: str) -> dict[str, Any]:
    data = {
        "grant_type": "authorization_code",
        "code": code,
        "client_id": settings.hubspot_client_id,
        "client_secret": settings.hubspot_client_secret,
        "redirect_uri": redirect_uri(),
        "code_verifier": code_verifier,
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


def fetch_access_token_info(access_token: str) -> dict[str, Any]:
    """Portal id lives here. The token response itself does not include hub_id.

    The token is a path segment. Failures raise ValueError so logs never include it.
    """
    with httpx.Client(timeout=30.0) as client:
        resp = client.get(f"{HUBSPOT_API}/oauth/v1/access-tokens/{access_token}")
    if resp.status_code >= 400:
        raise ValueError(f"HubSpot token info failed with status {resp.status_code}.")
    payload = resp.json()
    if not isinstance(payload, dict):
        raise ValueError("HubSpot token info was not an object.")
    return payload


def _portal_id_from_payload(token_payload: dict[str, Any], access_token: str) -> str:
    hub_id = token_payload.get("hub_id") or token_payload.get("hubId")
    if hub_id is None and access_token:
        info = fetch_access_token_info(access_token)
        hub_id = info.get("hub_id") or info.get("hubId")
    if hub_id is None:
        raise ValueError("HubSpot did not return a portal id.")
    return str(hub_id)


def upsert_connection_from_oauth(
    db: Session,
    *,
    user_id: int,
    token_payload: dict[str, Any],
) -> IntegrationConnectionModel:
    access = token_payload.get("access_token") or ""
    refresh = token_payload.get("refresh_token") or ""
    portal_id = _portal_id_from_payload(token_payload, access)

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
    connection.external_org_id = portal_id
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
        if access and not connection.external_org_id:
            try:
                connection.external_org_id = _portal_id_from_payload(payload, access)
            except ValueError:
                logger.warning(
                    "HubSpot portal id lookup failed connection_id=%s",
                    connection.id,
                )
        mark_tokens_healthy(connection, db)
    except Exception as exc:
        if is_auth_refresh_failure(exc):
            handle_refresh_failure(connection, db)
        raise


def _retry_delay_seconds(resp: httpx.Response, attempt: int) -> float:
    raw = resp.headers.get("Retry-After")
    try:
        delay = float(raw) if raw is not None else float(attempt + 1)
    except (TypeError, ValueError):
        delay = float(attempt + 1)
    return min(max(delay, 0.0), 5.0)


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
    refreshed = False
    with httpx.Client(timeout=30.0) as client:
        resp: httpx.Response | None = None
        for attempt in range(_RATE_LIMIT_ATTEMPTS + 1):
            resp = client.request(method, url, headers=headers, json=json_body, params=params)
            if resp.status_code == 401 and not refreshed:
                _refresh_connection_tokens(connection, db)
                headers = _access_headers(connection)
                refreshed = True
                continue
            if resp.status_code == 429 and attempt < _RATE_LIMIT_ATTEMPTS:
                time.sleep(_retry_delay_seconds(resp, attempt))
                continue
            break
        assert resp is not None
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


def _stage_ids_for_labels(
    pairs: list[tuple[str, str]], labels: list[str]
) -> list[str]:
    """Every stage id whose label matches, including the same label in two pipelines."""
    wanted = {label.casefold() for label in labels}
    ids: list[str] = []
    seen: set[str] = set()
    for stage_id, label in pairs:
        if label.casefold() in wanted and stage_id not in seen:
            seen.add(stage_id)
            ids.append(stage_id)
    return ids


def check_setup(connection: IntegrationConnectionModel, db: Session) -> dict[str, Any]:
    """Inspect deal properties and pipelines for cookie_* fields and recipe stages."""
    try:
        raw = hubspot_request(connection, db, "GET", "/crm/v3/properties/deals")
        present = {
            str(item.get("name") or "").strip()
            for item in (raw.get("results") or [])
            if item.get("name")
        }
        pairs = _pipeline_stage_pairs(connection, db)
        known = {label.casefold() for _stage_id, label in pairs}
        stage_names = recipe_stage_names(connection)
        missing_stages = [name for name in stage_names if name.casefold() not in known]
        stage = (connection.trigger_stage_name or "Demo Completed").strip()
    except httpx.HTTPStatusError as exc:
        if exc.response.status_code == 401:
            raise ValueError("HubSpot token is invalid or expired.") from exc
        if exc.response.status_code == 403:
            raise ValueError(
                "HubSpot is missing crm.schemas.deals.read. Reconnect HubSpot to grant it."
            ) from exc
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
        unknown_stage=bool(missing_stages),
        extra_messages=extra or None,
        missing_stages=missing_stages,
    )


def _contact_fields(props: dict[str, Any]) -> dict[str, str]:
    first = str(props.get("firstname") or "").strip()
    last = str(props.get("lastname") or "").strip()
    return {
        "name": f"{first} {last}".strip(),
        "email": str(props.get("email") or "").strip(),
    }


def _contact_for_deal(
    connection: IntegrationConnectionModel, db: Session, deal_id: str
) -> dict[str, str]:
    """First associated contact that has an email, else the first contact."""
    assoc = hubspot_request(
        connection,
        db,
        "GET",
        f"/crm/v4/objects/deals/{deal_id}/associations/contacts",
    )
    contact_ids: list[str] = []
    for row in assoc.get("results") or []:
        contact_id = str(row.get("toObjectId") or row.get("id") or "")
        if contact_id and contact_id not in contact_ids:
            contact_ids.append(contact_id)
        if len(contact_ids) >= _CONTACT_LOOKUP_LIMIT:
            break
    fallback = {"name": "", "email": ""}
    for contact_id in contact_ids:
        contact = hubspot_request(
            connection,
            db,
            "GET",
            f"/crm/v3/objects/contacts/{contact_id}",
            params={"properties": "firstname,lastname,email"},
        )
        parsed = _contact_fields(contact.get("properties") or {})
        if not fallback["name"] and not fallback["email"]:
            fallback = parsed
        if parsed["email"]:
            return parsed
    return fallback


def _cookie_property_names() -> list[str]:
    names: list[str] = []
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


def _cookie_from_props(props: dict[str, Any]) -> dict[str, str | None]:
    def read(name: str) -> str | None:
        if not name:
            return None
        value = str(props.get(name) or "").strip()
        return value or None

    return {
        "cookie_note": read(settings.hubspot_cookie_note_property or ""),
        "cookie_company": read(settings.hubspot_cookie_company_property or ""),
        "cookie_street": read(settings.hubspot_cookie_street_property or ""),
        "cookie_street2": read(settings.hubspot_cookie_street2_property or ""),
        "cookie_city": read(settings.hubspot_cookie_city_property or ""),
        "cookie_state": read(settings.hubspot_cookie_state_property or ""),
        "cookie_postal_code": read(settings.hubspot_cookie_postal_code_property or ""),
        "cookie_address": read(settings.hubspot_cookie_address_property or ""),
    }


def _stage_entered_property(stage_id: str) -> str:
    return f"hs_v2_date_entered_{stage_id}"


def _entered_ms(props: dict[str, Any], stage_id: str) -> int:
    raw = props.get(_stage_entered_property(stage_id))
    try:
        return int(raw)
    except (TypeError, ValueError):
        return 0


def _search_deals_entered(
    connection: IntegrationConnectionModel,
    db: Session,
    *,
    stage_ids: list[str],
    since_ms: int,
    properties: list[str],
) -> tuple[list[dict[str, Any]], bool]:
    """Page deals that entered one of stage_ids at or after since_ms.

    Returns (deals, truncated). Truncated means the per-sync cap stopped the scan.
    """
    deals: list[dict[str, Any]] = []
    seen: set[str] = set()
    truncated = False
    for offset in range(0, len(stage_ids), _SEARCH_FILTER_GROUP_LIMIT):
        chunk = stage_ids[offset : offset + _SEARCH_FILTER_GROUP_LIMIT]
        chunk_props = list(properties)
        for stage_id in chunk:
            entered = _stage_entered_property(stage_id)
            if entered not in chunk_props:
                chunk_props.append(entered)
        after: str | None = None
        while True:
            search_body: dict[str, Any] = {
                "filterGroups": [
                    {
                        "filters": [
                            {
                                "propertyName": "dealstage",
                                "operator": "EQ",
                                "value": stage_id,
                            },
                            {
                                "propertyName": _stage_entered_property(stage_id),
                                "operator": "GTE",
                                "value": str(since_ms),
                            },
                        ]
                    }
                    for stage_id in chunk
                ],
                "properties": chunk_props,
                "limit": _SEARCH_PAGE_LIMIT,
            }
            if after:
                search_body["after"] = after
            raw = hubspot_request(
                connection,
                db,
                "POST",
                "/crm/v3/objects/deals/search",
                json_body=search_body,
            )
            for record in raw.get("results") or []:
                deal_id = str(record.get("id") or "")
                if not deal_id or deal_id in seen:
                    continue
                seen.add(deal_id)
                deals.append(record)
                if len(deals) >= _MAX_DEALS_PER_POLL:
                    return deals, True
            after = str(((raw.get("paging") or {}).get("next") or {}).get("after") or "")
            if not after:
                break
    return deals, truncated


def poll_demo_completed(connection: IntegrationConnectionModel, db: Session) -> list[dict]:
    """Poll deals that entered a recipe stage since the last poll."""
    started = datetime.now(UTC)
    wanted_labels = recipe_stage_names(connection)
    pairs = _pipeline_stage_pairs(connection, db)
    label_by_id = {stage_id: label for stage_id, label in pairs}
    stage_ids = _stage_ids_for_labels(pairs, wanted_labels)
    if not stage_ids:
        logger.warning(
            "HubSpot stage labels %r not found in deal pipelines connection_id=%s",
            wanted_labels,
            connection.id,
        )
        connection.last_polled_at = started
        connection.updated_at = started
        db.commit()
        return []

    since = connection.last_polled_at
    if since is None:
        since = started.replace(hour=0, minute=0, second=0, microsecond=0)
    since_ms = int(_as_utc(since).timestamp() * 1000)

    deal_properties = ["dealname", "dealstage", *_cookie_property_names()]
    deals, truncated = _search_deals_entered(
        connection,
        db,
        stage_ids=stage_ids,
        since_ms=since_ms,
        properties=deal_properties,
    )
    deals.sort(
        key=lambda record: _entered_ms(
            record.get("properties") or {},
            str((record.get("properties") or {}).get("dealstage") or ""),
        )
    )
    if len(deals) > _MAX_DEALS_PER_POLL:
        deals = deals[:_MAX_DEALS_PER_POLL]
        truncated = True

    results: list[dict] = []
    for record in deals:
        deal_id = str(record.get("id") or "")
        props = record.get("properties") or {}
        stage_id = str(props.get("dealstage") or "")
        contact = _contact_for_deal(connection, db, deal_id)
        deal_name = str(props.get("dealname") or "")
        cookies = _cookie_from_props(props)
        results.append(
            process_stage_completed_reminder(
                db,
                connection=connection,
                opportunity_id=deal_id,
                stage_name=label_by_id.get(stage_id, wanted_labels[0]),
                contact_name=contact["name"] or deal_name,
                contact_email=contact["email"],
                cookie_note=cookies["cookie_note"],
                cookie_company=cookies["cookie_company"],
                cookie_street=cookies["cookie_street"],
                cookie_street2=cookies["cookie_street2"],
                cookie_city=cookies["cookie_city"],
                cookie_state=cookies["cookie_state"],
                cookie_postal_code=cookies["cookie_postal_code"],
                cookie_address=cookies["cookie_address"],
            )
        )

    if truncated and deals:
        last_ms = _entered_ms(
            (deals[-1].get("properties") or {}),
            str((deals[-1].get("properties") or {}).get("dealstage") or ""),
        )
        # Keep the previous cursor when the entry time is missing so the rest
        # of the window is searched again instead of skipped.
        cursor = (
            datetime.fromtimestamp(last_ms / 1000, tz=UTC) if last_ms else connection.last_polled_at
        )
    else:
        cursor = started
    if cursor is not None:
        connection.last_polled_at = cursor
    connection.updated_at = datetime.now(UTC)
    db.commit()
    return results


def verify_webhook_secret(provided: str | None) -> bool:
    """Shared secret for a custom workflow POST. Empty secret is rejected."""
    expected = (settings.hubspot_webhook_secret or "").strip()
    provided_s = (provided or "").strip()
    if not expected or not provided_s or len(provided_s) != len(expected):
        return False
    return hmac.compare_digest(provided_s, expected)


def _signature_uri(uri: str) -> str:
    """HubSpot decodes a fixed set of percent-encodings before signing."""
    for encoded, decoded in (
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
    ):
        uri = uri.replace(encoded, decoded)
    return uri


def verify_hubspot_signature(
    *,
    method: str,
    uri: str,
    body: bytes,
    timestamp: str | None,
    signature: str | None,
) -> bool:
    """HubSpot v3 signature: base64 HMAC-SHA256 of method + URI + raw body + timestamp."""
    secret = (settings.hubspot_client_secret or "").strip()
    provided = (signature or "").strip()
    if not secret or not timestamp or not provided:
        return False
    try:
        ts_ms = int(timestamp)
    except ValueError:
        return False
    now_ms = int(datetime.now(UTC).timestamp() * 1000)
    if now_ms - ts_ms > _SIGNATURE_MAX_AGE_MS:
        return False
    signed_uri = _signature_uri(uri)
    source = method.upper().encode("utf-8") + signed_uri.encode("utf-8") + body + timestamp.encode("utf-8")
    digest = hmac.new(secret.encode("utf-8"), source, hashlib.sha256).digest()
    expected = base64.b64encode(digest).decode("ascii")
    if len(expected) != len(provided):
        return False
    return hmac.compare_digest(expected, provided)


def _enabled_connections_for_portal(
    db: Session, portal_id: str
) -> list[IntegrationConnectionModel]:
    return list(
        db.scalars(
            select(IntegrationConnectionModel).where(
                IntegrationConnectionModel.provider == PROVIDER_HUBSPOT,
                IntegrationConnectionModel.external_org_id == portal_id,
                IntegrationConnectionModel.enabled.is_(True),
            )
        ).all()
    )


def _fetch_deal_properties(
    connection: IntegrationConnectionModel, db: Session, deal_id: str
) -> dict[str, Any]:
    names = ["dealname", "dealstage", *_cookie_property_names()]
    raw = hubspot_request(
        connection,
        db,
        "GET",
        f"/crm/v3/objects/deals/{deal_id}",
        params={"properties": ",".join(names)},
    )
    props = raw.get("properties") or {}
    return props if isinstance(props, dict) else {}


def ingest_webhook_batch(db: Session, events: list[Any]) -> list[dict]:
    """Native HubSpot dealstage webhooks. Unknown portals are ignored, not guessed."""
    results: list[dict] = []
    connections: dict[str, IntegrationConnectionModel | None] = {}
    portal_reasons: dict[str, str] = {}
    labels_by_connection: dict[int, dict[str, str]] = {}

    for event in events:
        if not isinstance(event, dict):
            results.append({"status": "ignored", "reason": "malformed"})
            continue
        if str(event.get("propertyName") or "") != "dealstage":
            results.append({"status": "ignored", "reason": "not_dealstage"})
            continue
        portal_id = str(event.get("portalId") or event.get("portal_id") or "")
        deal_id = str(event.get("objectId") or "")
        stage_value = str(event.get("propertyValue") or "")
        if not portal_id or not deal_id or not stage_value:
            results.append({"status": "ignored", "reason": "missing_fields"})
            continue
        if portal_id not in connections:
            matches = _enabled_connections_for_portal(db, portal_id)
            if len(matches) == 1:
                connections[portal_id] = matches[0]
            else:
                connections[portal_id] = None
                portal_reasons[portal_id] = (
                    "ambiguous_portal" if len(matches) > 1 else "unknown_portal"
                )
                if len(matches) > 1:
                    logger.warning(
                        "HubSpot webhook portal_id=%s matched %s connections",
                        portal_id,
                        len(matches),
                    )
        connection = connections[portal_id]
        if connection is None:
            results.append(
                {
                    "status": "ignored",
                    "reason": portal_reasons.get(portal_id, "unknown_portal"),
                    "portal_id": portal_id,
                }
            )
            continue
        if connection.id not in labels_by_connection:
            pairs = _pipeline_stage_pairs(connection, db)
            labels_by_connection[connection.id] = {stage_id: label for stage_id, label in pairs}
        label = labels_by_connection[connection.id].get(stage_value)
        if not label:
            results.append(
                {"status": "ignored", "reason": "unknown_stage", "deal_id": deal_id}
            )
            continue
        if match_stage_recipe(connection, label) is None:
            results.append(
                {"status": "ignored", "reason": "stage_mismatch", "deal_id": deal_id}
            )
            continue
        try:
            props = _fetch_deal_properties(connection, db, deal_id)
            contact = _contact_for_deal(connection, db, deal_id)
            cookies = _cookie_from_props(props)
            deal_name = str(props.get("dealname") or "")
            results.append(
                process_stage_completed_reminder(
                    db,
                    connection=connection,
                    opportunity_id=deal_id,
                    stage_name=label,
                    contact_name=contact["name"] or deal_name or deal_id,
                    contact_email=contact["email"],
                    cookie_note=cookies["cookie_note"],
                    cookie_company=cookies["cookie_company"],
                    cookie_street=cookies["cookie_street"],
                    cookie_street2=cookies["cookie_street2"],
                    cookie_city=cookies["cookie_city"],
                    cookie_state=cookies["cookie_state"],
                    cookie_postal_code=cookies["cookie_postal_code"],
                    cookie_address=cookies["cookie_address"],
                )
            )
        except Exception:
            logger.exception(
                "HubSpot webhook deal ingest failed portal_id=%s deal_id=%s",
                portal_id,
                deal_id,
            )
            results.append({"status": "error", "reason": "ingest_failed", "deal_id": deal_id})
    return results
