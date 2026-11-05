"""HubSpot Demo Completed → cookie reminder tests."""

from __future__ import annotations

from unittest.mock import patch

from conftest import signup
from app.db import SessionLocal
from app.integrations.crypto import encrypt_token
from app.models import IntegrationConnectionModel


def _seed_connection(user_id: int, *, stage: str = "Demo Completed") -> int:
    db = SessionLocal()
    try:
        row = IntegrationConnectionModel(
            owner_user_id=user_id,
            provider="hubspot",
            external_org_id="12345678",
            instance_url="https://api.hubapi.com",
            access_token_encrypted=encrypt_token("access-token"),
            refresh_token_encrypted=encrypt_token("refresh-token"),
            trigger_stage_name=stage,
            enabled=True,
        )
        db.add(row)
        db.commit()
        db.refresh(row)
        return row.id
    finally:
        db.close()


def test_demo_completed_event_sends_reminder_and_creates_prospect(auth_client, monkeypatch):
    me = auth_client.get("/auth/me").json()
    connection_id = _seed_connection(me["user_id"])

    sent: list[dict] = []

    def _fake_send(**kwargs):
        sent.append(kwargs)

    with patch("app.main.hs.verify_webhook_secret", return_value=True), patch(
        "app.integrations.reminders.send_cookie_reminder", side_effect=_fake_send
    ):
        resp = auth_client.post(
            "/integrations/hubspot/events",
            json={
                "connection_id": connection_id,
                "deal_id": "987654321",
                "stage_name": "Demo Completed",
                "contact_name": "Jordan Buyer",
                "contact_email": "jordan@acme.com",
            },
            headers={"X-Webhook-Secret": "test-secret"},
        )

    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "sent"
    assert body["prospect_id"]
    assert len(sent) == 1
    assert "Jordan Buyer" in sent[0]["prospect_name"]
    assert sent[0]["crm_name"] == "HubSpot"
    assert f"prospect_id={body['prospect_id']}" in sent[0]["order_url"]
    assert "from=hs_reminder" in sent[0]["order_url"]

    prospects = auth_client.get("/prospects").json()
    assert any(p["id"] == body["prospect_id"] and p["email"] == "jordan@acme.com" for p in prospects)


def test_demo_completed_event_dedupes(auth_client):
    me = auth_client.get("/auth/me").json()
    connection_id = _seed_connection(me["user_id"])

    with patch("app.main.hs.verify_webhook_secret", return_value=True), patch(
        "app.integrations.reminders.send_cookie_reminder"
    ) as send_mock:
        first = auth_client.post(
            "/integrations/hubspot/events",
            json={
                "connection_id": connection_id,
                "deal_id": "deal-dedup",
                "stage_name": "Demo Completed",
                "contact_name": "Sam",
                "contact_email": "sam@example.com",
            },
        )
        second = auth_client.post(
            "/integrations/hubspot/events",
            json={
                "connection_id": connection_id,
                "deal_id": "deal-dedup",
                "stage_name": "Demo Completed",
                "contact_name": "Sam",
                "contact_email": "sam@example.com",
            },
        )

    assert first.status_code == 200
    assert first.json()["status"] == "sent"
    assert second.status_code == 200
    assert second.json()["status"] == "duplicate"
    assert send_mock.call_count == 1


def test_stage_mismatch_ignored(auth_client):
    me = auth_client.get("/auth/me").json()
    connection_id = _seed_connection(me["user_id"])

    with patch("app.main.hs.verify_webhook_secret", return_value=True), patch(
        "app.integrations.reminders.send_cookie_reminder"
    ) as send_mock:
        resp = auth_client.post(
            "/integrations/hubspot/events",
            json={
                "connection_id": connection_id,
                "deal_id": "deal-wrong-stage",
                "stage_name": "Appointments scheduled",
                "contact_name": "Sam",
                "contact_email": "sam@example.com",
            },
        )

    assert resp.status_code == 200
    assert resp.json()["status"] == "ignored"
    send_mock.assert_not_called()


def test_webhook_rejects_bad_secret(auth_client, monkeypatch):
    me = auth_client.get("/auth/me").json()
    connection_id = _seed_connection(me["user_id"])
    monkeypatch.setattr("app.integrations.hubspot.settings.hubspot_webhook_secret", "expected")
    monkeypatch.setattr("app.integrations.hubspot.settings.app_env", "production")

    resp = auth_client.post(
        "/integrations/hubspot/events",
        json={
            "connection_id": connection_id,
            "deal_id": "deal-x",
            "stage_name": "Demo Completed",
            "contact_name": "Sam",
            "contact_email": "sam@example.com",
        },
        headers={"X-Webhook-Secret": "wrong"},
    )
    assert resp.status_code == 401


def test_connect_requires_hubspot_config(auth_client, monkeypatch):
    monkeypatch.setattr("app.config.settings.hubspot_client_id", "")
    monkeypatch.setattr("app.config.settings.hubspot_client_secret", "")
    resp = auth_client.get("/integrations/hubspot/connect")
    assert resp.status_code == 503


def test_oauth_state_is_single_use_and_expires(monkeypatch):
    from app.db import SessionLocal
    from app.integrations.hubspot import sign_oauth_state, verify_oauth_state

    db = SessionLocal()
    try:
        state, verifier = sign_oauth_state(db, 99)
        assert verifier
        first = verify_oauth_state(db, state)
        assert first is not None
        assert first[0] == 99
        assert first[1] == verifier
        assert verify_oauth_state(db, state) is None
        assert verify_oauth_state(db, "tampered") is None

        monkeypatch.setattr("app.integrations.hubspot._OAUTH_STATE_TTL_SECONDS", -5)
        expired, _expired_verifier = sign_oauth_state(db, 99)
        assert verify_oauth_state(db, expired) is None
    finally:
        db.close()


def test_disconnect_removes_connection(auth_client):
    me = auth_client.get("/auth/me").json()
    connection_id = _seed_connection(me["user_id"])
    deleted = auth_client.delete(f"/integrations/{connection_id}")
    assert deleted.status_code == 200
    providers = [row["provider"] for row in auth_client.get("/integrations").json()]
    assert "hubspot" not in providers


def test_scoped_to_owner(make_client):
    owner = signup(make_client(), "hs-owner@example.com")
    other = signup(make_client(), "hs-other@example.com")
    owner_id = owner.get("/auth/me").json()["user_id"]
    connection_id = _seed_connection(owner_id)

    owner_providers = [r["provider"] for r in owner.get("/integrations").json()]
    assert "hubspot" in owner_providers
    assert other.get("/integrations").json() == []
    assert other.delete(f"/integrations/{connection_id}").status_code == 404


def test_event_requires_connection_or_portal(auth_client, monkeypatch):
    me = auth_client.get("/auth/me").json()
    _seed_connection(me["user_id"])
    monkeypatch.setattr("app.integrations.hubspot.settings.hubspot_webhook_secret", "expected")
    monkeypatch.setattr("app.integrations.hubspot.settings.app_env", "development")
    resp = auth_client.post(
        "/integrations/hubspot/events",
        json={
            "deal_id": "deal-x",
            "stage_name": "Demo Completed",
            "contact_name": "Sam",
            "contact_email": "sam@example.com",
        },
        headers={"X-Webhook-Secret": "expected"},
    )
    assert resp.status_code == 400


def test_webhook_secret_required_when_unset(auth_client, monkeypatch):
    me = auth_client.get("/auth/me").json()
    connection_id = _seed_connection(me["user_id"])
    monkeypatch.setattr("app.integrations.hubspot.settings.hubspot_webhook_secret", "")
    monkeypatch.setattr("app.integrations.hubspot.settings.app_env", "development")
    resp = auth_client.post(
        "/integrations/hubspot/events",
        json={
            "connection_id": connection_id,
            "deal_id": "deal-x",
            "stage_name": "Demo Completed",
            "contact_name": "Sam",
            "contact_email": "sam@example.com",
        },
    )
    assert resp.status_code == 401


def test_portal_id_routes_and_ambiguous_portal_conflicts(make_client, monkeypatch):
    monkeypatch.setattr("app.integrations.hubspot.settings.hubspot_webhook_secret", "expected")
    owner = signup(make_client(), "hs-portal-a@example.com")
    other = signup(make_client(), "hs-portal-b@example.com")
    owner_id = owner.get("/auth/me").json()["user_id"]
    other_id = other.get("/auth/me").json()["user_id"]
    _seed_connection(owner_id)
    body = {
        "portal_id": "12345678",
        "deal_id": "deal-portal",
        "stage_name": "Demo Completed",
        "contact_name": "Sam",
        "contact_email": "sam@example.com",
    }
    with patch("app.main.hs.verify_webhook_secret", return_value=True), patch(
        "app.integrations.reminders.send_cookie_reminder"
    ):
        routed = owner.post("/integrations/hubspot/events", json=body)
    assert routed.status_code == 200, routed.text
    assert routed.json()["status"] == "sent"

    _seed_connection(other_id)
    conflict = owner.post(
        "/integrations/hubspot/events",
        json=body,
        headers={"X-Webhook-Secret": "expected"},
    )
    assert conflict.status_code == 409


def test_callback_stores_portal_id(auth_client, monkeypatch):
    from app.db import SessionLocal
    from app.integrations.hubspot import sign_oauth_state

    me = auth_client.get("/auth/me").json()
    db = SessionLocal()
    try:
        state, _verifier = sign_oauth_state(db, me["user_id"])
    finally:
        db.close()

    def _exchange(code, *, code_verifier):
        assert code == "auth-code"
        assert code_verifier
        return {"access_token": "atk", "refresh_token": "rtk"}

    def _info(token):
        assert token == "atk"
        return {"hub_id": 4242}

    monkeypatch.setattr("app.main.hs.exchange_code_for_tokens", _exchange)
    monkeypatch.setattr("app.main.hs.fetch_access_token_info", _info)
    resp = auth_client.get(
        "/integrations/hubspot/callback",
        params={"code": "auth-code", "state": state},
        follow_redirects=False,
    )
    assert resp.status_code in {302, 307}
    assert "connected=hubspot" in resp.headers["location"]
    rows = auth_client.get("/integrations").json()
    hubspot = next(row for row in rows if row["provider"] == "hubspot")
    assert hubspot["external_org_id"] == "4242"


def test_poll_uses_stage_entry_and_every_pipeline(auth_client, monkeypatch):
    from app.integrations.hubspot import poll_demo_completed

    me = auth_client.get("/auth/me").json()
    connection_id = _seed_connection(me["user_id"])
    searches: list[dict] = []

    def _fake_request(_connection, _db, method, path, **kwargs):
        if path == "/crm/v3/pipelines/deals":
            return {
                "results": [
                    {
                        "stages": [
                            {"id": "demo-a", "label": "Demo Completed"},
                            {"id": "won", "label": "Closed Won"},
                        ]
                    },
                    {"stages": [{"id": "demo-b", "label": "Demo Completed"}]},
                ]
            }
        if path == "/crm/v3/objects/deals/search":
            body = kwargs.get("json_body") or {}
            searches.append(body)
            if len(searches) == 1:
                return {
                    "results": [
                        {
                            "id": "501",
                            "properties": {
                                "dealname": "Acme",
                                "dealstage": "demo-a",
                                "hs_v2_date_entered_demo-a": "1700000000000",
                            },
                        }
                    ],
                    "paging": {"next": {"after": "cursor-2"}},
                }
            return {
                "results": [
                    {
                        "id": "502",
                        "properties": {
                            "dealname": "Beta",
                            "dealstage": "demo-b",
                            "hs_v2_date_entered_demo-b": "1700000001000",
                        },
                    }
                ]
            }
        if path.startswith("/crm/v4/objects/deals/") and path.endswith("/associations/contacts"):
            return {"results": []}
        raise AssertionError(path)

    db = SessionLocal()
    try:
        connection = db.get(IntegrationConnectionModel, connection_id)
        assert connection is not None
        with patch("app.integrations.hubspot.hubspot_request", side_effect=_fake_request), patch(
            "app.integrations.hubspot.process_stage_completed_reminder",
            return_value={"status": "sent"},
        ) as process:
            results = poll_demo_completed(connection, db)
        assert len(results) == 2
        assert process.call_count == 2
        stage_ids = [
            group["filters"][0]["value"] for group in searches[0]["filterGroups"]
        ]
        assert stage_ids == ["demo-a", "demo-b"]
        assert searches[1]["after"] == "cursor-2"
        assert all(
            filt["propertyName"].startswith("hs_v2_date_entered_")
            for body in searches
            for group in body["filterGroups"]
            for filt in group["filters"]
            if filt["operator"] == "GTE"
        )
        assert "hs_lastmodifieddate" not in str(searches)
        db.refresh(connection)
        assert connection.last_polled_at is not None
    finally:
        db.close()


def test_native_webhook_verifies_signature_and_maps_stage(auth_client, monkeypatch):
    import base64
    import hashlib
    import hmac
    import json
    from datetime import UTC, datetime

    from app.integrations.hubspot import webhook_validation_uri

    me = auth_client.get("/auth/me").json()
    _seed_connection(me["user_id"])
    monkeypatch.setattr("app.integrations.hubspot.settings.hubspot_client_secret", "hs-secret")
    payload = [
        {
            "portalId": 12345678,
            "objectId": 777,
            "propertyName": "dealstage",
            "propertyValue": "demo-a",
            "subscriptionType": "object.propertyChange",
        }
    ]
    body = json.dumps(payload).encode()
    timestamp = str(int(datetime.now(UTC).timestamp() * 1000))
    uri = webhook_validation_uri("/integrations/hubspot/events")
    source = f"POST{uri}{body.decode()}{timestamp}".encode()
    signature = base64.b64encode(
        hmac.new(b"hs-secret", source, hashlib.sha256).digest()
    ).decode()

    def _fake_request(_connection, _db, method, path, **_kwargs):
        if path == "/crm/v3/pipelines/deals":
            return {"results": [{"stages": [{"id": "demo-a", "label": "Demo Completed"}]}]}
        if path == "/crm/v3/objects/deals/777":
            return {"properties": {"dealname": "Acme", "dealstage": "demo-a", "cookie_note": "Thanks"}}
        if path.endswith("/associations/contacts"):
            return {
                "results": [
                    {"toObjectId": 1},
                    {"toObjectId": 2},
                ]
            }
        if path == "/crm/v3/objects/contacts/1":
            return {"properties": {"firstname": "No", "lastname": "Email", "email": ""}}
        if path == "/crm/v3/objects/contacts/2":
            return {"properties": {"firstname": "Jordan", "lastname": "Buyer", "email": "jordan@acme.com"}}
        raise AssertionError(path)

    with patch("app.integrations.hubspot.hubspot_request", side_effect=_fake_request), patch(
        "app.integrations.reminders.send_cookie_reminder"
    ) as send_mock:
        resp = auth_client.post(
            "/integrations/hubspot/events",
            content=body,
            headers={
                "Content-Type": "application/json",
                "X-HubSpot-Request-Timestamp": timestamp,
                "X-HubSpot-Signature-v3": signature,
            },
        )
    assert resp.status_code == 200, resp.text
    result = resp.json()["results"][0]
    assert result["status"] == "sent"
    assert send_mock.call_args.kwargs["prospect_name"].startswith("Jordan")

    rejected = auth_client.post(
        "/integrations/hubspot/events",
        content=body,
        headers={
            "Content-Type": "application/json",
            "X-HubSpot-Request-Timestamp": timestamp,
            "X-HubSpot-Signature-v3": "not-a-signature",
        },
    )
    assert rejected.status_code == 401
