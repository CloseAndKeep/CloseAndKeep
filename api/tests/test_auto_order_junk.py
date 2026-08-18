"""Hold CRM auto-order when email/address is junk (feature #14)."""

from __future__ import annotations

from unittest.mock import patch

import pytest

from sqlalchemy import func, select

from app.db import SessionLocal
from app.integrations.contact_quality import (
    ADDRESS_BLANK,
    ADDRESS_JUNK,
    ADDRESS_USABLE,
    crm_address_quality,
    is_junk_crm_email,
)
from app.integrations.crypto import encrypt_token
from app.integrations.reminders import process_stage_completed_reminder
from app.models import CrmReminderEventModel, GiftOrderModel, IntegrationConnectionModel, UserModel


@pytest.mark.parametrize(
    ("email", "expected"),
    [
        (None, True),
        ("", True),
        ("   ", True),
        ("not-an-email", True),
        ("006abc@unknown.salesforce", True),
        ("12345@unknown.hubspot", True),
        ("noreply@acme.com", True),
        ("no-reply@acme.com", True),
        ("noreply+sales@acme.com", True),
        ("donotreply@acme.com", True),
        ("do-not-reply@acme.com", True),
        ("alex@acme.com", False),
        ("Jordan.Buyer@Example.COM", False),
    ],
)
def test_is_junk_crm_email(email, expected):
    assert is_junk_crm_email(email) is expected


def test_blank_address_is_not_junk():
    assert crm_address_quality() == ADDRESS_BLANK
    assert crm_address_quality(company="Acme Corp") == ADDRESS_BLANK
    assert crm_address_quality(blob="") == ADDRESS_BLANK
    assert crm_address_quality(blob="   ") == ADDRESS_BLANK


def test_incomplete_or_fake_address_is_junk():
    assert crm_address_quality(street="123 Main St") == ADDRESS_JUNK
    assert crm_address_quality(street="123 Main St", city="Springfield") == ADDRESS_JUNK
    assert (
        crm_address_quality(
            street="123 Fake Street",
            city="Springfield",
            state="IL",
            postal_code="62704",
        )
        == ADDRESS_JUNK
    )
    assert (
        crm_address_quality(
            street="n/a",
            city="n/a",
            state="n/a",
            postal_code="00000",
        )
        == ADDRESS_JUNK
    )
    assert crm_address_quality(blob="123 Main") == ADDRESS_JUNK
    assert crm_address_quality(blob="n/a") == ADDRESS_JUNK
    assert crm_address_quality(blob="123 Fake St, Springfield, IL 62704") == ADDRESS_JUNK


def test_complete_address_is_usable():
    assert (
        crm_address_quality(
            street="123 Main St",
            city="Springfield",
            state="IL",
            postal_code="62704",
        )
        == ADDRESS_USABLE
    )
    assert crm_address_quality(blob="123 Main St\nSpringfield, IL 62704") == ADDRESS_USABLE
    assert (
        crm_address_quality(
            street="123 Main St",
            blob="123 Main St\nSpringfield, IL 62704",
        )
        == ADDRESS_USABLE
    )


def _seed_crm(user_id: int, *, provider: str = "salesforce") -> int:
    db = SessionLocal()
    try:
        if provider == "hubspot":
            row = IntegrationConnectionModel(
                owner_user_id=user_id,
                provider="hubspot",
                external_org_id="12345678",
                instance_url="https://api.hubapi.com",
                access_token_encrypted=encrypt_token("access-token"),
                refresh_token_encrypted=encrypt_token("refresh-token"),
                trigger_stage_name="Demo Completed",
                enabled=True,
            )
        else:
            row = IntegrationConnectionModel(
                owner_user_id=user_id,
                provider="salesforce",
                external_org_id="00DTESTORG",
                instance_url="https://example.my.salesforce.com",
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


def _enable_auto_order(user_id: int, *, monthly: bool = True) -> None:
    db = SessionLocal()
    try:
        user = db.get(UserModel, user_id)
        assert user is not None
        user.auto_order_enabled = True
        user.auto_order_gift_id = "cookies-4"
        if monthly:
            user.billing_mode = "monthly"
            user.stripe_customer_id = "cus_test_123"
            user.stripe_default_payment_method_id = "pm_test_card"
        db.add(user)
        db.commit()
    finally:
        db.close()


def _run_reminder(
    connection_id: int,
    *,
    opportunity_id: str,
    contact_email: str,
    contact_name: str = "Alex Buyer",
    **cookie_fields,
) -> dict:
    db = SessionLocal()
    try:
        connection = db.get(IntegrationConnectionModel, connection_id)
        assert connection is not None
        return process_stage_completed_reminder(
            db,
            connection=connection,
            opportunity_id=opportunity_id,
            stage_name="Demo Completed",
            contact_name=contact_name,
            contact_email=contact_email,
            **cookie_fields,
        )
    finally:
        db.close()


def _event_status(opportunity_id: str) -> str | None:
    db = SessionLocal()
    try:
        return db.scalar(
            select(CrmReminderEventModel.status).where(
                CrmReminderEventModel.external_event_key == opportunity_id
            )
        )
    finally:
        db.close()


def _order_count() -> int:
    db = SessionLocal()
    try:
        return int(db.scalar(select(func.count()).select_from(GiftOrderModel)) or 0)
    finally:
        db.close()


def test_junk_email_without_address_holds_and_emails_ae(auth_client, monkeypatch):
    me = auth_client.get("/auth/me").json()
    connection_id = _seed_crm(me["user_id"])
    _enable_auto_order(me["user_id"])

    held: list[dict] = []
    monkeypatch.setattr(
        "app.integrations.reminders.send_auto_order_held_junk",
        lambda **kwargs: held.append(kwargs),
    )
    monkeypatch.setattr("app.integrations.reminders.send_auto_order_checkout", lambda **_k: None)
    monkeypatch.setattr("app.integrations.reminders.send_cookie_reminder", lambda **_k: None)

    body = _run_reminder(connection_id, opportunity_id="006NOEMAIL", contact_email="")
    assert body["status"] == "held_junk"
    assert body.get("reason") == "junk_email_no_address"
    assert "order_id" not in body
    assert _order_count() == 0
    assert _event_status("006NOEMAIL") == "held_junk"
    assert len(held) == 1
    assert held[0]["prospect_name"] == "Alex Buyer"
    assert held[0]["crm_name"] == "Salesforce"
    assert f"prospect_id={body['prospect_id']}" in held[0]["order_url"]
    assert held[0]["to_email"].lower() == "seller@example.com"


def test_noreply_email_without_address_holds(auth_client, monkeypatch):
    me = auth_client.get("/auth/me").json()
    connection_id = _seed_crm(me["user_id"])
    _enable_auto_order(me["user_id"])
    held: list[dict] = []
    monkeypatch.setattr(
        "app.integrations.reminders.send_auto_order_held_junk",
        lambda **kwargs: held.append(kwargs),
    )

    body = _run_reminder(
        connection_id, opportunity_id="006NOREPLY", contact_email="noreply@acme.com"
    )
    assert body["status"] == "held_junk"
    assert _order_count() == 0
    assert len(held) == 1


def test_invalid_email_without_address_holds(auth_client, monkeypatch):
    me = auth_client.get("/auth/me").json()
    connection_id = _seed_crm(me["user_id"])
    _enable_auto_order(me["user_id"])
    monkeypatch.setattr("app.integrations.reminders.send_auto_order_held_junk", lambda **_k: None)

    body = _run_reminder(
        connection_id, opportunity_id="006BADEMAIL", contact_email="not-an-email"
    )
    assert body["status"] == "held_junk"
    assert _order_count() == 0


def test_held_event_dedupes_by_opportunity(auth_client, monkeypatch):
    me = auth_client.get("/auth/me").json()
    connection_id = _seed_crm(me["user_id"])
    _enable_auto_order(me["user_id"])
    held: list[dict] = []
    monkeypatch.setattr(
        "app.integrations.reminders.send_auto_order_held_junk",
        lambda **kwargs: held.append(kwargs),
    )

    first = _run_reminder(connection_id, opportunity_id="006HOLDDEDUP", contact_email="")
    second = _run_reminder(connection_id, opportunity_id="006HOLDDEDUP", contact_email="")
    assert first["status"] == "held_junk"
    assert second["status"] == "duplicate"
    assert len(held) == 1
    assert _event_status("006HOLDDEDUP") == "held_junk"


def test_junk_email_with_usable_address_still_auto_orders(auth_client, stripe_stub, monkeypatch):
    me = auth_client.get("/auth/me").json()
    connection_id = _seed_crm(me["user_id"])
    _enable_auto_order(me["user_id"])
    held: list[dict] = []
    monkeypatch.setattr(
        "app.integrations.reminders.send_auto_order_held_junk",
        lambda **kwargs: held.append(kwargs),
    )
    monkeypatch.setattr(
        "app.stripe_payments.send_recipient_address_request",
        lambda **_k: None,
    )

    body = _run_reminder(
        connection_id,
        opportunity_id="006JUNKMAILADDR",
        contact_email="",
        cookie_street="123 Main St",
        cookie_city="Springfield",
        cookie_state="IL",
        cookie_postal_code="62704",
    )
    assert body["status"] == "auto_ordered"
    assert body.get("has_shipping_address") is True
    assert held == []
    assert _order_count() == 1
    assert _event_status("006JUNKMAILADDR") == "auto_ordered"


def test_good_email_junk_address_falls_back_to_address_request(
    auth_client, stripe_stub, monkeypatch
):
    me = auth_client.get("/auth/me").json()
    connection_id = _seed_crm(me["user_id"])
    _enable_auto_order(me["user_id"])
    address_mails: list[dict] = []
    monkeypatch.setattr(
        "app.stripe_payments.send_recipient_address_request",
        lambda **kwargs: address_mails.append(kwargs),
    )
    monkeypatch.setattr("app.integrations.reminders.send_auto_order_held_junk", lambda **_k: None)

    body = _run_reminder(
        connection_id,
        opportunity_id="006JUNKADDR",
        contact_email="alex@acme.com",
        cookie_street="123 Main St",
    )
    assert body["status"] == "auto_ordered"
    assert body.get("has_shipping_address") is False
    assert _event_status("006JUNKADDR") == "auto_ordered"

    orders = auth_client.get("/gift-orders").json()
    match = next(o for o in orders if o["id"] == body["order_id"])
    assert match["status"] == "no_address"
    assert not (match.get("shipping_address") or "").strip()
    assert match["recipient_email"] == "alex@acme.com"
    assert len(address_mails) == 1


def test_good_email_fake_complete_address_is_not_shipped(
    auth_client, stripe_stub, monkeypatch
):
    me = auth_client.get("/auth/me").json()
    connection_id = _seed_crm(me["user_id"])
    _enable_auto_order(me["user_id"])
    monkeypatch.setattr(
        "app.stripe_payments.send_recipient_address_request",
        lambda **_k: None,
    )

    body = _run_reminder(
        connection_id,
        opportunity_id="006FAKEADDR",
        contact_email="alex@acme.com",
        cookie_street="123 Fake Street",
        cookie_city="Test",
        cookie_state="XX",
        cookie_postal_code="00000",
    )
    assert body["status"] == "auto_ordered"
    assert body.get("has_shipping_address") is False
    orders = auth_client.get("/gift-orders").json()
    match = next(o for o in orders if o["id"] == body["order_id"])
    assert match["status"] == "no_address"
    assert "Fake" not in (match.get("shipping_address") or "")


def test_hubspot_missing_email_holds_same_logic(auth_client, monkeypatch):
    me = auth_client.get("/auth/me").json()
    connection_id = _seed_crm(me["user_id"], provider="hubspot")
    _enable_auto_order(me["user_id"])
    held: list[dict] = []
    monkeypatch.setattr(
        "app.integrations.reminders.send_auto_order_held_junk",
        lambda **kwargs: held.append(kwargs),
    )

    body = _run_reminder(
        connection_id,
        opportunity_id="987650014",
        contact_name="Jordan Buyer",
        contact_email="",
    )
    assert body["status"] == "held_junk"
    assert _order_count() == 0
    assert _event_status("987650014") == "held_junk"
    assert len(held) == 1
    assert held[0]["crm_name"] == "HubSpot"


def test_events_endpoint_holds_noreply_email(auth_client, monkeypatch):
    me = auth_client.get("/auth/me").json()
    connection_id = _seed_crm(me["user_id"])
    _enable_auto_order(me["user_id"])
    held: list[dict] = []
    monkeypatch.setattr(
        "app.integrations.reminders.send_auto_order_held_junk",
        lambda **kwargs: held.append(kwargs),
    )

    with patch("app.main.sf.verify_webhook_secret", return_value=True):
        resp = auth_client.post(
            "/integrations/salesforce/events",
            json={
                "connection_id": connection_id,
                "opportunity_id": "006HTTPNOREPLY",
                "stage_name": "Demo Completed",
                "contact_name": "Alex Buyer",
                "contact_email": "noreply@acme.com",
            },
            headers={"X-Webhook-Secret": "test-secret"},
        )

    assert resp.status_code == 200, resp.text
    assert resp.json()["status"] == "held_junk"
    assert _order_count() == 0
    assert len(held) == 1


def test_held_junk_email_helper_notifies_ae(monkeypatch):
    import app.order_email as oe

    captured: dict = {}

    def fake_send(**kwargs):
        captured.update(kwargs)

    monkeypatch.setattr(oe, "_send", fake_send)
    oe.send_auto_order_held_junk(
        to_email="AE@Example.COM",
        prospect_name="Alex Buyer",
        crm_name="Salesforce",
        order_url="https://example.com/orders/new?prospect_id=9&from=sf_reminder",
    )
    assert captured["to"] == "ae@example.com"
    assert captured["subject"] == "Auto-order held — fix contact for Alex Buyer"
    assert captured["context"] == "auto-order-held-junk"
    assert "Alex Buyer" in captured["text_body"]
    assert "Salesforce" in captured["text_body"]
    assert "Send cookies" in captured["html_body"]
    assert "prospect_id=9" in captured["html_body"]
