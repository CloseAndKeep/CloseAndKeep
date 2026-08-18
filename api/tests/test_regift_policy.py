"""Re-gift window (90 days) and retry of failed CRM auto-orders."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from unittest.mock import patch

from conftest import create_order, create_prospect, mark_order_paid_db, signup
from app.db import SessionLocal
from app.integrations.crypto import encrypt_token
from app.models import (
    CrmReminderEventModel,
    GiftOrderModel,
    IntegrationConnectionModel,
    UserModel,
)


def _seed_crm(user_id: int) -> int:
    db = SessionLocal()
    try:
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


def _post_stage(client, connection_id: int, opportunity_id: str, email: str = "alex@acme.com"):
    with patch("app.main.sf.verify_webhook_secret", return_value=True):
        return client.post(
            "/integrations/salesforce/events",
            json={
                "connection_id": connection_id,
                "opportunity_id": opportunity_id,
                "stage_name": "Demo Completed",
                "contact_name": "Alex Buyer",
                "contact_email": email,
            },
            headers={"X-Webhook-Secret": "test-secret"},
        )


def test_regift_skips_second_opportunity_within_90_days(auth_client, stripe_stub, monkeypatch):
    me = auth_client.get("/auth/me").json()
    connection_id = _seed_crm(me["user_id"])
    _enable_auto_order(me["user_id"])
    monkeypatch.setattr(
        "app.stripe_payments.send_recipient_address_request",
        lambda **_kwargs: None,
    )

    first = _post_stage(auth_client, connection_id, "006REGIFT1")
    assert first.status_code == 200, first.text
    assert first.json()["status"] == "auto_ordered"
    first_order_id = first.json()["order_id"]

    second = _post_stage(auth_client, connection_id, "006REGIFT2")
    assert second.status_code == 200, second.text
    body = second.json()
    assert body["status"] == "skipped_regift"
    assert body["reason"] == "recent_gift"
    assert body["recent_order_id"] == first_order_id
    assert body["window_days"] == 90
    assert "order_id" not in body

    orders = auth_client.get("/gift-orders").json()
    assert len(orders) == 1
    assert orders[0]["id"] == first_order_id


def test_regift_allows_after_window(auth_client, stripe_stub, monkeypatch):
    me = auth_client.get("/auth/me").json()
    connection_id = _seed_crm(me["user_id"])
    _enable_auto_order(me["user_id"])
    monkeypatch.setattr(
        "app.stripe_payments.send_recipient_address_request",
        lambda **_kwargs: None,
    )

    first = _post_stage(auth_client, connection_id, "006WINDOW1")
    assert first.status_code == 200, first.text
    assert first.json()["status"] == "auto_ordered"
    order_id = first.json()["order_id"]

    db = SessionLocal()
    try:
        order = db.get(GiftOrderModel, order_id)
        assert order is not None
        order.requested_at = datetime.now(UTC) - timedelta(days=91)
        db.add(order)
        db.commit()
    finally:
        db.close()

    second = _post_stage(auth_client, connection_id, "006WINDOW2")
    assert second.status_code == 200, second.text
    body = second.json()
    assert body["status"] == "auto_ordered"
    assert body["order_id"] != order_id

    orders = auth_client.get("/gift-orders").json()
    assert len(orders) == 2


def test_regift_same_opportunity_refire_skips(auth_client, stripe_stub, monkeypatch):
    me = auth_client.get("/auth/me").json()
    connection_id = _seed_crm(me["user_id"])
    _enable_auto_order(me["user_id"])
    monkeypatch.setattr(
        "app.stripe_payments.send_recipient_address_request",
        lambda **_kwargs: None,
    )

    first = _post_stage(auth_client, connection_id, "006SAMEOPP")
    assert first.json()["status"] == "auto_ordered"
    second = _post_stage(auth_client, connection_id, "006SAMEOPP")
    assert second.status_code == 200
    assert second.json()["status"] == "skipped_regift"
    assert len(auth_client.get("/gift-orders").json()) == 1


def test_regift_matches_manual_gift_same_email(auth_client, stripe_stub, monkeypatch):
    me = auth_client.get("/auth/me").json()
    connection_id = _seed_crm(me["user_id"])
    _enable_auto_order(me["user_id"])
    monkeypatch.setattr(
        "app.stripe_payments.send_recipient_address_request",
        lambda **_kwargs: None,
    )

    prospect = create_prospect(auth_client, name="Alex Buyer", email="alex@acme.com")
    order = create_order(auth_client, prospect["id"])
    mark_order_paid_db(order["id"])

    resp = _post_stage(auth_client, connection_id, "006MANUAL1")
    assert resp.status_code == 200, resp.text
    assert resp.json()["status"] == "skipped_regift"
    assert resp.json()["recent_order_id"] == order["id"]


def test_retry_error_event_creates_order(auth_client, stripe_stub, monkeypatch):
    me = auth_client.get("/auth/me").json()
    connection_id = _seed_crm(me["user_id"])
    _enable_auto_order(me["user_id"], monthly=False)
    monkeypatch.setattr("app.integrations.reminders.send_auto_order_checkout", lambda **_k: None)

    with patch(
        "app.integrations.reminders.create_checkout_session_for_order",
        side_effect=RuntimeError("stripe down"),
    ):
        failed = _post_stage(auth_client, connection_id, "006RETRYERR")
    assert failed.status_code == 200, failed.text
    assert failed.json()["status"] == "error"
    event_id = failed.json()["event_id"]
    assert auth_client.get("/gift-orders").json() == []

    listed = auth_client.get("/integrations/events?retryable=true")
    assert listed.status_code == 200
    assert any(row["id"] == event_id and row["retryable"] is True for row in listed.json())

    retried = auth_client.post(f"/integrations/events/{event_id}/retry")
    assert retried.status_code == 200, retried.text
    body = retried.json()
    assert body["status"] == "auto_ordered"
    assert body["order_id"]
    assert body["event_id"] == event_id
    assert len(auth_client.get("/gift-orders").json()) == 1


def test_retry_held_event_allowed(auth_client, stripe_stub, monkeypatch):
    me = auth_client.get("/auth/me").json()
    connection_id = _seed_crm(me["user_id"])
    _enable_auto_order(me["user_id"])
    monkeypatch.setattr(
        "app.stripe_payments.send_recipient_address_request",
        lambda **_kwargs: None,
    )

    prospect = create_prospect(auth_client, name="Alex Buyer", email="held@acme.com")
    db = SessionLocal()
    try:
        event = CrmReminderEventModel(
            connection_id=connection_id,
            owner_user_id=me["user_id"],
            prospect_id=prospect["id"],
            provider="salesforce",
            external_event_key="006HELD1",
            stage_name="Demo Completed",
            status="held",
        )
        db.add(event)
        db.commit()
        db.refresh(event)
        event_id = event.id
    finally:
        db.close()

    retried = auth_client.post(f"/integrations/events/{event_id}/retry")
    assert retried.status_code == 200, retried.text
    assert retried.json()["status"] == "auto_ordered"


def test_retry_success_event_rejected(auth_client, stripe_stub, monkeypatch):
    me = auth_client.get("/auth/me").json()
    connection_id = _seed_crm(me["user_id"])
    _enable_auto_order(me["user_id"])
    monkeypatch.setattr(
        "app.stripe_payments.send_recipient_address_request",
        lambda **_kwargs: None,
    )

    first = _post_stage(auth_client, connection_id, "006NOSUCCESSRETRY")
    assert first.json()["status"] == "auto_ordered"
    event_id = first.json()["event_id"]

    refused = auth_client.post(f"/integrations/events/{event_id}/retry")
    assert refused.status_code == 400
    assert "retried" in refused.json()["detail"].lower()
    assert len(auth_client.get("/gift-orders").json()) == 1


def test_retry_scoped_to_owner(auth_client, make_client, stripe_stub, monkeypatch):
    me = auth_client.get("/auth/me").json()
    connection_id = _seed_crm(me["user_id"])
    _enable_auto_order(me["user_id"], monthly=False)
    monkeypatch.setattr("app.integrations.reminders.send_auto_order_checkout", lambda **_k: None)

    with patch(
        "app.integrations.reminders.create_checkout_session_for_order",
        side_effect=RuntimeError("stripe down"),
    ):
        failed = _post_stage(auth_client, connection_id, "006OWNERRETRY")
    event_id = failed.json()["event_id"]

    other = signup(make_client(), "regift-other@example.com")
    assert other.get("/integrations/events").json() == []
    assert other.post(f"/integrations/events/{event_id}/retry").status_code == 404
