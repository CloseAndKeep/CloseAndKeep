"""Salesforce Demo Completed → cookie reminder tests."""

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
            provider="salesforce",
            external_org_id="00DTESTORG",
            instance_url="https://example.my.salesforce.com",
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

    monkeypatch.setenv("SALESFORCE_WEBHOOK_SECRET", "test-secret")
    # Reload settings pickup is not automatic; patch verify instead via secret env
    # by calling the endpoint after patching verify_webhook_secret.
    with patch("app.main.sf.verify_webhook_secret", return_value=True), patch(
        "app.integrations.reminders.send_cookie_reminder", side_effect=_fake_send
    ):
        resp = auth_client.post(
            "/integrations/salesforce/events",
            json={
                "connection_id": connection_id,
                "opportunity_id": "006OPPORTUNITY1",
                "stage_name": "Demo Completed",
                "contact_name": "Alex Buyer",
                "contact_email": "alex@acme.com",
                "contact_title": "VP Sales",
                "company": "Acme Co",
            },
            headers={"X-Webhook-Secret": "test-secret"},
        )

    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "sent"
    assert body["prospect_id"]
    assert len(sent) == 1
    assert "Alex Buyer" in sent[0]["prospect_name"]
    assert f"prospect_id={body['prospect_id']}" in sent[0]["order_url"]
    assert "from=sf_reminder" in sent[0]["order_url"]

    prospects = auth_client.get("/prospects").json()
    assert any(p["id"] == body["prospect_id"] and p["email"] == "alex@acme.com" for p in prospects)


def test_demo_completed_event_dedupes(auth_client):
    me = auth_client.get("/auth/me").json()
    connection_id = _seed_connection(me["user_id"])

    with patch("app.main.sf.verify_webhook_secret", return_value=True), patch(
        "app.integrations.reminders.send_cookie_reminder"
    ) as send_mock:
        first = auth_client.post(
            "/integrations/salesforce/events",
            json={
                "connection_id": connection_id,
                "opportunity_id": "006DEDUP",
                "stage_name": "Demo Completed",
                "contact_name": "Sam",
                "contact_email": "sam@example.com",
                "company": "Example",
            },
        )
        second = auth_client.post(
            "/integrations/salesforce/events",
            json={
                "connection_id": connection_id,
                "opportunity_id": "006DEDUP",
                "stage_name": "Demo Completed",
                "contact_name": "Sam",
                "contact_email": "sam@example.com",
                "company": "Example",
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

    with patch("app.main.sf.verify_webhook_secret", return_value=True), patch(
        "app.integrations.reminders.send_cookie_reminder"
    ) as send_mock:
        resp = auth_client.post(
            "/integrations/salesforce/events",
            json={
                "connection_id": connection_id,
                "opportunity_id": "006WRONGSTAGE",
                "stage_name": "Prospecting",
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
    monkeypatch.setattr("app.integrations.salesforce.settings.salesforce_webhook_secret", "expected")
    monkeypatch.setattr("app.integrations.salesforce.settings.app_env", "production")

    resp = auth_client.post(
        "/integrations/salesforce/events",
        json={
            "connection_id": connection_id,
            "opportunity_id": "006X",
            "stage_name": "Demo Completed",
            "contact_name": "Sam",
            "contact_email": "sam@example.com",
        },
        headers={"X-Webhook-Secret": "wrong"},
    )
    assert resp.status_code == 401


def test_list_and_update_integration(auth_client):
    me = auth_client.get("/auth/me").json()
    connection_id = _seed_connection(me["user_id"])

    listed = auth_client.get("/integrations")
    assert listed.status_code == 200
    assert len(listed.json()) == 1
    assert listed.json()[0]["id"] == connection_id

    patched = auth_client.patch(
        f"/integrations/{connection_id}",
        json={"trigger_stage_name": "Demo Completed", "enabled": True},
    )
    assert patched.status_code == 200
    assert patched.json()["trigger_stage_name"] == "Demo Completed"


def test_guest_cannot_list_integrations(client):
    client.post("/auth/guest")
    resp = client.get("/integrations")
    assert resp.status_code == 403


def test_connect_requires_salesforce_config(auth_client, monkeypatch):
    monkeypatch.setattr("app.config.settings.salesforce_client_id", "")
    monkeypatch.setattr("app.config.settings.salesforce_client_secret", "")
    resp = auth_client.get("/integrations/salesforce/connect")
    assert resp.status_code == 503


def test_oauth_state_roundtrip():
    from app.integrations.salesforce import sign_oauth_state, verify_oauth_state

    state = sign_oauth_state(42)
    assert verify_oauth_state(state) == 42
    assert verify_oauth_state("tampered") is None


def test_disconnect_removes_connection(auth_client):
    me = auth_client.get("/auth/me").json()
    connection_id = _seed_connection(me["user_id"])
    deleted = auth_client.delete(f"/integrations/{connection_id}")
    assert deleted.status_code == 200
    assert auth_client.get("/integrations").json() == []


def test_scoped_to_owner(make_client):
    owner = signup(make_client(), "sf-owner@example.com")
    other = signup(make_client(), "sf-other@example.com")
    owner_id = owner.get("/auth/me").json()["user_id"]
    connection_id = _seed_connection(owner_id)

    assert len(owner.get("/integrations").json()) == 1
    assert other.get("/integrations").json() == []
    assert other.delete(f"/integrations/{connection_id}").status_code == 404
