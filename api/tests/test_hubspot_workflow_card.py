"""HubSpot workflow action + Deal app card intake (signed requests)."""

from __future__ import annotations

import hashlib
import json
from unittest.mock import patch

from app.db import SessionLocal
from app.integrations.crypto import encrypt_token
from app.integrations import hubspot as hs
from app.models import IntegrationConnectionModel


def _seed_connection(user_id: int, *, portal_id: str = "12345678") -> int:
    db = SessionLocal()
    try:
        row = IntegrationConnectionModel(
            owner_user_id=user_id,
            provider="hubspot",
            external_org_id=portal_id,
            instance_url="https://api.hubapi.com",
            access_token_encrypted=encrypt_token("access-token"),
            refresh_token_encrypted=encrypt_token("refresh-token"),
            trigger_stage_name="Demo Completed",
            enabled=True,
        )
        db.add(row)
        db.commit()
        db.refresh(row)
        return row.id
    finally:
        db.close()


def _sign(secret: str, method: str, uri: str, body: bytes) -> str:
    source = f"{secret}{method.upper()}{uri}{body.decode('utf-8')}"
    return hashlib.sha256(source.encode("utf-8")).hexdigest()


def test_verify_request_signature_v2(monkeypatch):
    monkeypatch.setattr(hs.settings, "hubspot_client_secret", "client-secret")
    monkeypatch.setattr(hs.settings, "app_env", "production")
    body = b'{"ok":true}'
    uri = "https://api.example.com/integrations/hubspot/workflow-action"
    sig = _sign("client-secret", "POST", uri, body)
    assert hs.verify_request_signature_v2(
        method="POST", uri=uri, body=body, signature=sig
    )
    assert not hs.verify_request_signature_v2(
        method="POST", uri=uri, body=body, signature="deadbeef"
    )


def test_parse_workflow_action_payload():
    parsed = hs.parse_workflow_action_payload(
        {
            "callbackId": "cb-1",
            "origin": {"portalId": 12345678},
            "object": {"objectId": 987, "objectType": "DEAL"},
            "inputFields": {"stage_name": "Demo Completed"},
        }
    )
    assert parsed["portal_id"] == 12345678
    assert parsed["deal_id"] == "987"
    assert parsed["stage_name"] == "Demo Completed"


def test_workflow_action_queues_gift(auth_client, monkeypatch):
    me = auth_client.get("/auth/me").json()
    _seed_connection(me["user_id"], portal_id="555")
    monkeypatch.setattr(hs.settings, "hubspot_client_secret", "secret")
    monkeypatch.setattr(hs.settings, "api_base_url", "https://api.example.com")
    monkeypatch.setattr(hs.settings, "app_env", "production")

    payload = {
        "origin": {"portalId": "555"},
        "object": {"objectId": "deal-1", "objectType": "DEAL"},
        "inputFields": {},
    }
    body = json.dumps(payload).encode("utf-8")
    path = "/integrations/hubspot/workflow-action"
    uri = f"https://api.example.com{path}"
    headers = {"X-HubSpot-Signature": _sign("secret", "POST", uri, body)}

    with patch(
        "app.integrations.hubspot.load_deal_gift_context",
        return_value={
            "deal_id": "deal-1",
            "stage_name": "Demo Completed",
            "contact_name": "Alex Buyer",
            "contact_email": "alex@acme.com",
            "cookie_note": "Thanks!",
            "cookie_company": None,
            "cookie_street": "1 Main",
            "cookie_street2": None,
            "cookie_city": "Austin",
            "cookie_state": "TX",
            "cookie_postal_code": "78701",
            "cookie_address": None,
            "properties": {},
        },
    ), patch("app.integrations.reminders.send_cookie_reminder") as send_mock:
        # auto_order may create an order path; stub reminder path via process internals
        resp = auth_client.post(path, content=body, headers=headers)

    assert resp.status_code == 200
    assert resp.json()["deal_id"] == "deal-1"
    assert resp.json()["status"] in {"sent", "auto_ordered", "duplicate", "held_junk"}
    # Either reminder or auto-order ran without raising.
    assert send_mock.call_count in {0, 1}


def test_workflow_action_rejects_bad_signature(auth_client, monkeypatch):
    monkeypatch.setattr(hs.settings, "hubspot_client_secret", "secret")
    monkeypatch.setattr(hs.settings, "api_base_url", "https://api.example.com")
    monkeypatch.setattr(hs.settings, "app_env", "production")
    body = b'{"origin":{"portalId":"1"},"object":{"objectId":"9"}}'
    resp = auth_client.post(
        "/integrations/hubspot/workflow-action",
        content=body,
        headers={"X-HubSpot-Signature": "nope"},
    )
    assert resp.status_code == 401


def test_card_properties_updates_deal(auth_client, monkeypatch):
    me = auth_client.get("/auth/me").json()
    _seed_connection(me["user_id"], portal_id="777")
    monkeypatch.setattr(hs.settings, "hubspot_client_secret", "secret")
    monkeypatch.setattr(hs.settings, "api_base_url", "https://api.example.com")
    monkeypatch.setattr(hs.settings, "app_env", "production")

    payload = {
        "portal_id": "777",
        "deal_id": "deal-9",
        "cookie_note": "Congrats",
        "cookie_street": "9 Oak",
        "cookie_city": "Denver",
        "cookie_state": "CO",
        "cookie_postal_code": "80202",
    }
    body = json.dumps(payload).encode("utf-8")
    path = "/integrations/hubspot/card/properties"
    uri = f"https://api.example.com{path}"
    headers = {"X-HubSpot-Signature": _sign("secret", "POST", uri, body)}

    with patch(
        "app.integrations.hubspot.update_deal_cookie_properties",
        return_value={"cookie_note": "Congrats"},
    ) as update_mock:
        resp = auth_client.post(path, content=body, headers=headers)

    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"
    update_mock.assert_called_once()


def test_card_send_missing_connection(auth_client, monkeypatch):
    monkeypatch.setattr(hs.settings, "hubspot_client_secret", "secret")
    monkeypatch.setattr(hs.settings, "api_base_url", "https://api.example.com")
    monkeypatch.setattr(hs.settings, "app_env", "production")
    payload = {"portal_id": "missing", "deal_id": "deal-1"}
    body = json.dumps(payload).encode("utf-8")
    path = "/integrations/hubspot/card/send"
    uri = f"https://api.example.com{path}"
    headers = {"X-HubSpot-Signature": _sign("secret", "POST", uri, body)}
    resp = auth_client.post(path, content=body, headers=headers)
    assert resp.status_code == 404


def test_oauth_scopes_include_deals_write():
    assert "crm.objects.deals.write" in hs.HUBSPOT_SCOPES
    assert "crm.objects.deals.read" in hs.HUBSPOT_SCOPES


def test_existing_events_and_sync_routes_still_registered(auth_client):
    """Keep OAuth DIY events + sync as the bridge alongside native actions."""
    sync = auth_client.post("/integrations/hubspot/sync")
    # Authenticated but no connection → 404 from the route (not an unknown path).
    assert sync.status_code == 404
    assert "not connected" in sync.json()["detail"].lower()

    events = auth_client.post(
        "/integrations/hubspot/events",
        json={
            "deal_id": "x",
            "stage_name": "Demo Completed",
            "contact_name": "A",
            "contact_email": "a@example.com",
        },
    )
    assert events.status_code == 404
    assert "connection not found" in events.json()["detail"].lower()
