"""Integration event journal and dead-token reconnect."""

from __future__ import annotations

from unittest.mock import patch

import httpx

from conftest import signup
from app.db import SessionLocal
from app.integrations.crypto import encrypt_token
from app.models import IntegrationConnectionModel


def _seed_connection(
    user_id: int,
    *,
    provider: str = "salesforce",
    stage: str = "Demo Completed",
) -> int:
    db = SessionLocal()
    try:
        row = IntegrationConnectionModel(
            owner_user_id=user_id,
            provider=provider,
            external_org_id="00DTESTORG" if provider == "salesforce" else "12345678",
            instance_url=(
                "https://example.my.salesforce.com"
                if provider == "salesforce"
                else "https://api.hubapi.com"
            ),
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


def _connection(connection_id: int) -> IntegrationConnectionModel:
    db = SessionLocal()
    try:
        row = db.get(IntegrationConnectionModel, connection_id)
        assert row is not None
        db.expunge(row)
        return row
    finally:
        db.close()


def test_list_events_owner_scoped_with_prospect(auth_client, make_client):
    me = auth_client.get("/auth/me").json()
    connection_id = _seed_connection(me["user_id"])

    with patch("app.main.sf.verify_webhook_secret", return_value=True), patch(
        "app.integrations.reminders.send_cookie_reminder"
    ):
        created = auth_client.post(
            "/integrations/salesforce/events",
            json={
                "connection_id": connection_id,
                "opportunity_id": "006JOURNAL1",
                "stage_name": "Demo Completed",
                "contact_name": "Acme",
                "contact_email": "alex@acme.com",
            },
        )
    assert created.status_code == 200
    assert created.json()["status"] == "sent"

    listed = auth_client.get("/integrations/events")
    assert listed.status_code == 200
    events = listed.json()
    assert len(events) == 1
    event = events[0]
    assert event["prospect_name"] == "Acme"
    assert event["stage_name"] == "Demo Completed"
    assert event["status"] == "sent"
    assert event["provider"] == "salesforce"
    assert event["created_at"]
    assert event["prospect_id"] == created.json()["prospect_id"]

    other = signup(make_client(), "journal-other@example.com")
    assert other.get("/integrations/events").json() == []


def test_guest_cannot_list_events(client):
    client.post("/auth/guest")
    resp = client.get("/integrations/events")
    assert resp.status_code == 403


def test_refresh_failure_emails_once_and_flags_connection(auth_client, monkeypatch):
    me = auth_client.get("/auth/me").json()
    connection_id = _seed_connection(me["user_id"])
    emails: list[dict] = []

    def _fake_reconnect(**kwargs):
        emails.append(kwargs)
        return True

    monkeypatch.setattr(
        "app.integrations.token_health.send_crm_reconnect",
        _fake_reconnect,
    )

    def _token_http_client(*_args, **_kwargs):
        class _Client:
            def __enter__(self):
                return self

            def __exit__(self, *_exc):
                return False

            def get(self, url, headers=None, params=None):
                return httpx.Response(
                    401,
                    request=httpx.Request("GET", str(url)),
                    text="invalid_session",
                )

            def post(self, url, data=None):
                return httpx.Response(
                    400,
                    request=httpx.Request("POST", str(url)),
                    text="invalid_grant",
                )

        return _Client()

    with patch("app.integrations.salesforce.httpx.Client", side_effect=_token_http_client):
        first = auth_client.post("/integrations/salesforce/sync")
        second = auth_client.post("/integrations/salesforce/sync")

    assert first.status_code == 502
    assert second.status_code == 502
    assert len(emails) == 1
    assert emails[0]["provider_label"] == "Salesforce"
    assert emails[0]["integrations_url"].endswith("/integrations")

    row = _connection(connection_id)
    assert row.token_status == "needs_reconnect"
    assert row.access_token_encrypted is None
    assert row.refresh_token_encrypted is None
    assert row.reconnect_email_sent_at is not None
    assert row.token_error_at is not None

    listed = auth_client.get("/integrations")
    assert listed.status_code == 200
    assert listed.json()[0]["token_status"] == "needs_reconnect"

    events = auth_client.get("/integrations/events").json()
    assert any(event["status"] == "token_expired" for event in events)
    expired = next(event for event in events if event["status"] == "token_expired")
    assert expired["stage_name"] == "login expired"
    assert expired["provider"] == "salesforce"
    assert expired["prospect_name"] is None


def test_hubspot_refresh_failure_flags_and_dedupes_email(auth_client, monkeypatch):
    me = auth_client.get("/auth/me").json()
    connection_id = _seed_connection(me["user_id"], provider="hubspot")
    emails: list[dict] = []

    monkeypatch.setattr(
        "app.integrations.token_health.send_crm_reconnect",
        lambda **kwargs: emails.append(kwargs) or True,
    )

    request = httpx.Request("POST", "https://api.hubapi.com/oauth/v1/token")
    response = httpx.Response(401, request=request, text="unauthorized")
    error = httpx.HTTPStatusError("unauthorized", request=request, response=response)

    with patch(
        "app.integrations.hubspot.refresh_access_token",
        side_effect=error,
    ):
        from app.db import SessionLocal as _Session
        from app.integrations import hubspot as hs

        db = _Session()
        try:
            row = db.get(IntegrationConnectionModel, connection_id)
            assert row is not None
            try:
                hs._refresh_connection_tokens(row, db)
            except httpx.HTTPStatusError:
                pass
            try:
                hs._refresh_connection_tokens(row, db)
            except (httpx.HTTPStatusError, ValueError):
                pass
        finally:
            db.close()

    assert len(emails) == 1
    assert emails[0]["provider_label"] == "HubSpot"
    row = _connection(connection_id)
    assert row.token_status == "needs_reconnect"
    assert row.access_token_encrypted is None
    assert row.refresh_token_encrypted is None


def test_send_crm_reconnect_links_to_integrations(monkeypatch):
    import app.order_email as oe

    captured: dict = {}

    def _fake_send(**kwargs):
        captured.update(kwargs)
        return True

    monkeypatch.setattr(oe, "_send", _fake_send)
    sent = oe.send_crm_reconnect(
        to_email="AE@Example.COM",
        provider_label="HubSpot",
        integrations_url="https://app.example.com/integrations",
    )
    assert sent is True
    assert captured["to"] == "ae@example.com"
    assert "HubSpot" in captured["subject"]
    assert "https://app.example.com/integrations" in captured["text_body"]
    assert "Reconnect HubSpot" in captured["html_body"]


def test_oauth_upsert_clears_token_health():
    from app.db import SessionLocal as _Session
    from app.integrations.salesforce import upsert_connection_from_oauth
    from app.models import UserModel

    db = _Session()
    try:
        user = UserModel(
            email="reconnect-owner@example.com",
            password_hash="x",
            role="user",
        )
        db.add(user)
        db.commit()
        db.refresh(user)
        connection_id = _seed_connection(user.id)
        row = db.get(IntegrationConnectionModel, connection_id)
        assert row is not None
        row.token_status = "needs_reconnect"
        row.reconnect_email_sent_at = row.created_at
        db.commit()

        upsert_connection_from_oauth(
            db,
            user_id=user.id,
            token_payload={
                "access_token": "new-access",
                "refresh_token": "new-refresh",
                "instance_url": "https://example.my.salesforce.com",
                "id": "https://login.salesforce.com/id/00Dxx/005xx",
            },
        )
        fresh = db.get(IntegrationConnectionModel, connection_id)
        assert fresh is not None
        assert fresh.token_status == "ok"
        assert fresh.token_error_at is None
        assert fresh.reconnect_email_sent_at is None
        assert fresh.access_token_encrypted
        assert fresh.refresh_token_encrypted
    finally:
        db.close()
