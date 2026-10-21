"""HubSpot Marketplace install, signed card status, and dealstage webhooks."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from unittest.mock import patch

from fastapi.testclient import TestClient

from app.db import SessionLocal
from app.integrations import hubspot as hs
from app.integrations.crypto import encrypt_token
from app.models import HubSpotPendingInstallModel, IntegrationConnectionModel
from conftest import signup


def _seed_connection(user_id: int, *, portal: str = "12345678") -> int:
    db = SessionLocal()
    try:
        row = IntegrationConnectionModel(
            owner_user_id=user_id,
            provider="hubspot",
            external_org_id=portal,
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


def _configure_signature(monkeypatch):
    monkeypatch.setattr(hs.settings, "hubspot_client_secret", "test-secret")
    monkeypatch.setattr(hs.settings, "api_base_url", "http://testserver")
    monkeypatch.setattr(hs.settings, "app_env", "production")


def _signed_headers(method: str, path: str, body: bytes) -> dict[str, str]:
    timestamp = str(int(datetime.now(UTC).timestamp() * 1000))
    uri = f"http://testserver{path}"
    signature = hs.hubspot_v3_signature(
        method=method, uri=uri, body=body.decode("utf-8"), timestamp=timestamp
    )
    return {
        "X-HubSpot-Signature-v3": signature,
        "X-HubSpot-Request-Timestamp": timestamp,
        "Content-Type": "application/json",
    }


def _fake_hubspot(connection, db, method, path, json_body=None, params=None):
    if path == "/crm/v3/pipelines/deals":
        return {
            "results": [
                {"stages": [{"id": "stage-demo", "label": "Demo Completed"}]}
            ]
        }
    if path.startswith("/crm/v4/objects/deals/"):
        return {"results": [{"toObjectId": "55"}]}
    if path.startswith("/crm/v3/objects/contacts/"):
        return {
            "properties": {
                "firstname": "Jordan",
                "lastname": "Buyer",
                "email": "jordan@acme.com",
            }
        }
    if path.startswith("/crm/v3/objects/deals/"):
        return {
            "properties": {
                "dealname": "Acme expansion",
                "dealstage": "stage-demo",
                "cookie_note": "Thanks for the demo",
                "cookie_street": "1 Main St",
                "cookie_city": "Austin",
                "cookie_state": "TX",
                "cookie_postal_code": "78701",
            }
        }
    raise AssertionError(path)


def test_signature_decodes_hubspot_query_characters():
    uri = "https://api.example.com/hook?email=a%40b.com"
    assert hs.normalize_hubspot_request_uri(uri) == "https://api.example.com/hook?email=a@b.com"


def test_marketplace_callback_claim_links_portal(auth_client, monkeypatch):
    me = auth_client.get("/auth/me").json()
    monkeypatch.setattr(
        "app.main.hs.exchange_code_for_tokens",
        lambda code: {
            "access_token": "access-from-hs",
            "refresh_token": "refresh-from-hs",
            "hub_id": 424242,
        },
    )
    from app.main import app

    with TestClient(app, follow_redirects=False) as raw:
        resp = raw.get("/integrations/hubspot/callback?code=marketplace-code")
    assert resp.status_code in (302, 307)
    location = resp.headers["location"]
    assert "/integrations/hubspot/finish/" in location
    code = location.rstrip("/").split("/")[-1]

    claim = auth_client.post("/integrations/hubspot/claim", json={"code": code})
    assert claim.status_code == 200
    assert claim.json()["portal_id"] == "424242"
    rows = auth_client.get("/integrations").json()
    assert rows[0]["provider"] == "hubspot"
    assert rows[0]["external_org_id"] == "424242"

    again = auth_client.post("/integrations/hubspot/claim", json={"code": code})
    assert again.status_code == 400
    assert me["user_id"]


def test_signed_state_still_connects_without_claim(auth_client, monkeypatch):
    me = auth_client.get("/auth/me").json()
    monkeypatch.setattr(
        "app.main.hs.exchange_code_for_tokens",
        lambda code: {
            "access_token": "access-from-hs",
            "refresh_token": "refresh-from-hs",
            "hub_id": 777,
        },
    )
    state = hs.sign_oauth_state(me["user_id"])
    from app.main import app

    with TestClient(app, follow_redirects=False) as raw:
        resp = raw.get(f"/integrations/hubspot/callback?code=abc&state={state}")
    assert resp.status_code in (302, 307)
    assert "connected=hubspot" in resp.headers["location"]
    rows = auth_client.get("/integrations").json()
    assert rows[0]["external_org_id"] == "777"


def test_claim_rejects_portal_owned_by_someone_else(auth_client, make_client, monkeypatch):
    other = signup(make_client(), "hs-other-portal@example.com")
    other_id = other.get("/auth/me").json()["user_id"]
    _seed_connection(other_id, portal="424242")
    monkeypatch.setattr(
        "app.main.hs.exchange_code_for_tokens",
        lambda code: {
            "access_token": "access-from-hs",
            "refresh_token": "refresh-from-hs",
            "hub_id": 424242,
        },
    )
    from app.main import app

    with TestClient(app, follow_redirects=False) as raw:
        resp = raw.get("/integrations/hubspot/callback?code=taken")
    code = resp.headers["location"].rstrip("/").split("/")[-1]
    claim = auth_client.post("/integrations/hubspot/claim", json={"code": code})
    assert claim.status_code == 409
    assert auth_client.get("/integrations").json() == []


def test_claim_rejects_expired_code(auth_client):
    me = auth_client.get("/auth/me").json()
    raw_code = "expired-install-code"
    db = SessionLocal()
    try:
        db.add(
            HubSpotPendingInstallModel(
                code_hash=hs._hash_install_code(raw_code),
                portal_id="55",
                access_token_encrypted=encrypt_token("access"),
                refresh_token_encrypted=encrypt_token("refresh"),
                expires_at=datetime.now(UTC) - timedelta(minutes=5),
            )
        )
        db.commit()
    finally:
        db.close()

    resp = auth_client.post("/integrations/hubspot/claim", json={"code": raw_code})
    assert resp.status_code == 400
    assert me["user_id"]


def test_native_webhook_orders_on_recipe_stage(auth_client, monkeypatch):
    me = auth_client.get("/auth/me").json()
    _seed_connection(me["user_id"])
    _configure_signature(monkeypatch)
    body = (
        b'[{"subscriptionType":"deal.propertyChange","propertyName":"dealstage",'
        b'"propertyValue":"stage-demo","objectId":987,"portalId":12345678}]'
    )
    sent: list[dict] = []

    with patch("app.integrations.hubspot.hubspot_request", side_effect=_fake_hubspot), patch(
        "app.integrations.reminders.send_cookie_reminder",
        side_effect=lambda **kwargs: sent.append(kwargs),
    ):
        resp = auth_client.post(
            "/integrations/hubspot/webhooks",
            content=body,
            headers=_signed_headers("POST", "/integrations/hubspot/webhooks", body),
        )

    assert resp.status_code == 200
    assert resp.json()["results"][0]["status"] == "sent"
    assert sent and sent[0]["crm_name"] == "HubSpot"


def test_native_webhook_rejects_bad_signature(auth_client, monkeypatch):
    me = auth_client.get("/auth/me").json()
    _seed_connection(me["user_id"])
    _configure_signature(monkeypatch)
    body = b'[{"subscriptionType":"deal.propertyChange","propertyName":"dealstage","propertyValue":"stage-demo","objectId":1,"portalId":12345678}]'
    headers = _signed_headers("POST", "/integrations/hubspot/webhooks", body)
    headers["X-HubSpot-Signature-v3"] = "not-the-signature"
    resp = auth_client.post(
        "/integrations/hubspot/webhooks",
        content=body,
        headers=headers,
    )
    assert resp.status_code == 401


def test_native_webhook_unknown_portal_is_ignored(auth_client, monkeypatch):
    _configure_signature(monkeypatch)
    body = (
        b'[{"subscriptionType":"deal.propertyChange","propertyName":"dealstage",'
        b'"propertyValue":"stage-demo","objectId":5,"portalId":999}]'
    )
    resp = auth_client.post(
        "/integrations/hubspot/webhooks",
        content=body,
        headers=_signed_headers("POST", "/integrations/hubspot/webhooks", body),
    )
    assert resp.status_code == 200
    assert resp.json()["results"][0]["reason"] == "unknown_portal"


def test_card_status_requires_signature_and_reports_deal(auth_client, monkeypatch):
    me = auth_client.get("/auth/me").json()
    _seed_connection(me["user_id"])
    _configure_signature(monkeypatch)
    path = "/integrations/hubspot/card?portalId=12345678&dealId=987"
    denied = auth_client.get(path)
    assert denied.status_code == 401

    ok = auth_client.get(path, headers=_signed_headers("GET", path, b""))
    assert ok.status_code == 200
    body = ok.json()
    assert body["linked"] is True
    assert body["deal"]["id"] == "987"
    assert body["deal"]["status"] is None

    missing = "/integrations/hubspot/card?portalId=does-not-exist"
    unlinked = auth_client.get(missing, headers=_signed_headers("GET", missing, b""))
    assert unlinked.status_code == 200
    assert unlinked.json()["linked"] is False
