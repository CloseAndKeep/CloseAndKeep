"""Monthly billing + CRM auto-order tests."""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import patch

from conftest import create_prospect, make_order_payload, signup
from app.db import SessionLocal
from app.integrations.crypto import encrypt_token
from app.jobs.monthly_billing import run_monthly_billing_job
from app.models import GiftOrderModel, IntegrationConnectionModel, UserModel


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


def _enable_monthly_with_pm(user_id: int, *, gift_id: str = "cookies-4") -> None:
    db = SessionLocal()
    try:
        user = db.get(UserModel, user_id)
        assert user is not None
        user.billing_mode = "monthly"
        user.stripe_customer_id = "cus_test_123"
        user.stripe_default_payment_method_id = "pm_test_card"
        user.auto_order_gift_id = gift_id
        db.add(user)
        db.commit()
    finally:
        db.close()


def test_billing_prefs_require_crm(auth_client):
    resp = auth_client.patch(
        "/auth/me/billing",
        json={"billing_mode": "monthly"},
    )
    assert resp.status_code == 400
    assert "API key" in resp.json()["detail"]


def test_billing_prefs_monthly_allowed_with_api_key(auth_client):
    me = auth_client.get("/auth/me").json()
    assert me["has_api_key"] is False
    created = auth_client.post("/api-keys", json={"name": "Zack CRM"})
    assert created.status_code == 201, created.text
    me2 = auth_client.get("/auth/me").json()
    assert me2["has_api_key"] is True
    assert me2["crm_connected"] is False

    resp = auth_client.patch(
        "/auth/me/billing",
        json={"billing_mode": "monthly"},
    )
    assert resp.status_code == 400
    assert "payment method" in resp.json()["detail"].lower()

    limit = auth_client.patch(
        "/auth/me/billing",
        json={"max_spending_cents": 5000},
    )
    assert limit.status_code == 200
    assert limit.json()["max_spending_cents"] == 5000

    auto = auth_client.patch(
        "/auth/me/billing",
        json={"auto_order_enabled": True, "auto_order_gift_id": "cookies-4"},
    )
    assert auto.status_code == 400
    assert "Salesforce or HubSpot" in auto.json()["detail"]


def test_api_key_monthly_order_skips_checkout(make_client, stripe_stub):
    browser = make_client()
    signup(browser, "custom-crm-monthly@example.com")
    created = browser.post("/api-keys", json={"name": "Zack CRM"})
    assert created.status_code == 201, created.text
    raw_key = created.json()["api_key"]
    me = browser.get("/auth/me").json()
    _enable_monthly_with_pm(me["user_id"])

    api = make_client()
    headers = {"Authorization": f"Bearer {raw_key}"}
    prospect = api.post(
        "/prospects",
        headers=headers,
        json={
            "name": "Dana Buyer",
            "email": "dana@example.com",
            "deal_status": "open",
        },
    )
    assert prospect.status_code == 201, prospect.text
    order = api.post(
        "/gift-orders",
        headers=headers,
        json=make_order_payload(prospect.json()["id"]),
    )
    assert order.status_code == 201, order.text
    body = order.json()
    assert body["checkout_url"] is None
    assert body["payment_status"] == "owed"
    assert not stripe_stub.session_create_calls


def test_billing_prefs_monthly_requires_payment_method(auth_client):
    me = auth_client.get("/auth/me").json()
    _seed_crm(me["user_id"])

    resp = auth_client.patch(
        "/auth/me/billing",
        json={"billing_mode": "monthly"},
    )
    assert resp.status_code == 400
    assert "payment method" in resp.json()["detail"].lower()


def test_setup_payment_method_creates_setup_session(auth_client, stripe_stub):
    me = auth_client.get("/auth/me").json()
    _seed_crm(me["user_id"])

    resp = auth_client.post("/auth/me/billing/setup-payment-method")
    assert resp.status_code == 200
    assert "setup_url" in resp.json()
    assert stripe_stub.session_create_calls
    assert stripe_stub.session_create_calls[-1]["mode"] == "setup"


def test_monthly_create_skips_checkout_and_address_queues_ops(
    auth_client, stripe_stub, monkeypatch
):
    me = auth_client.get("/auth/me").json()
    _seed_crm(me["user_id"])
    _enable_monthly_with_pm(me["user_id"])

    prospect = create_prospect(auth_client)
    ops: list[dict] = []
    address_mails: list[dict] = []

    monkeypatch.setattr(
        "app.order_email.send_new_order_notification",
        lambda **kwargs: ops.append(kwargs),
    )
    monkeypatch.setattr(
        "app.stripe_payments.send_recipient_address_request",
        lambda **kwargs: address_mails.append(kwargs),
    )
    # Fulfillment imports order_email at call time via module attribute.
    monkeypatch.setattr(
        "app.fulfillment.send_new_order_notification",
        lambda **kwargs: ops.append(kwargs),
    )

    create = auth_client.post(
        "/gift-orders",
        json={
            "prospect_id": prospect["id"],
            "gift_id": "cookies-4",
            "recipient_name": "Dana Buyer",
            "note": "Thanks!",
            "request_recipient_address": True,
            "recipient_email": "dana@example.com",
        },
    )
    assert create.status_code == 201, create.text
    body = create.json()
    assert body["checkout_url"] is None
    assert body["payment_status"] == "owed"
    assert body["status"] == "no_address"
    assert not stripe_stub.session_create_calls
    assert len(address_mails) == 1

    db = SessionLocal()
    try:
        order = db.get(GiftOrderModel, body["id"])
        assert order is not None
        token = order.address_request_token
        assert token
    finally:
        db.close()

    submit = auth_client.post(
        f"/public/address-requests/{token}",
        json={"shipping_address": "123 Main St\nSpringfield, IL 62704"},
    )
    assert submit.status_code == 200, submit.text

    detail = auth_client.get(f"/gift-orders/{body['id']}").json()
    assert detail["payment_status"] == "owed"
    assert detail["status"] == "queued"
    assert len(ops) == 1
    assert ops[0]["payment_status"] == "owed"


def test_monthly_known_address_queues_immediately(auth_client, stripe_stub, monkeypatch):
    me = auth_client.get("/auth/me").json()
    _seed_crm(me["user_id"])
    _enable_monthly_with_pm(me["user_id"])
    prospect = create_prospect(auth_client)

    ops: list[dict] = []
    monkeypatch.setattr(
        "app.fulfillment.send_new_order_notification",
        lambda **kwargs: ops.append(kwargs),
    )

    create = auth_client.post(
        "/gift-orders",
        json=make_order_payload(prospect["id"]),
    )
    assert create.status_code == 201, create.text
    body = create.json()
    assert body["checkout_url"] is None
    assert body["payment_status"] == "owed"
    assert body["status"] == "queued"
    assert not stripe_stub.session_create_calls
    assert len(ops) == 1


def test_pay_balance_marks_orders_paid(auth_client, stripe_stub, monkeypatch):
    me = auth_client.get("/auth/me").json()
    _seed_crm(me["user_id"])
    _enable_monthly_with_pm(me["user_id"])
    prospect = create_prospect(auth_client)

    monkeypatch.setattr(
        "app.fulfillment.send_new_order_notification",
        lambda **_kwargs: None,
    )
    receipts: list[dict] = []
    monkeypatch.setattr(
        "app.stripe_payments.send_monthly_billing_receipt",
        lambda **kwargs: receipts.append(kwargs),
    )

    create = auth_client.post(
        "/gift-orders",
        json=make_order_payload(prospect["id"]),
    )
    assert create.status_code == 201
    order_id = create.json()["id"]

    pay = auth_client.post("/auth/me/billing/pay-balance")
    assert pay.status_code == 200, pay.text
    result = pay.json()
    assert result["status"] == "paid"
    assert result["order_count"] == 1
    assert stripe_stub.payment_intent_create_calls
    pi_call = stripe_stub.payment_intent_create_calls[-1]
    assert pi_call["off_session"] is True
    assert pi_call["confirm"] is True
    assert "payment_method_types" not in pi_call

    detail = auth_client.get(f"/gift-orders/{order_id}").json()
    assert detail["payment_status"] == "paid"
    assert len(receipts) == 1


def test_auto_order_path_vs_reminder(auth_client, stripe_stub, monkeypatch):
    me = auth_client.get("/auth/me").json()
    connection_id = _seed_crm(me["user_id"])
    _enable_monthly_with_pm(me["user_id"], gift_id="cookies-12")

    db = SessionLocal()
    try:
        user = db.get(UserModel, me["user_id"])
        assert user is not None
        user.auto_order_enabled = True
        db.add(user)
        db.commit()
    finally:
        db.close()

    reminders: list[dict] = []
    address_mails: list[dict] = []
    monkeypatch.setattr(
        "app.integrations.reminders.send_cookie_reminder",
        lambda **kwargs: reminders.append(kwargs),
    )
    monkeypatch.setattr(
        "app.stripe_payments.send_recipient_address_request",
        lambda **kwargs: address_mails.append(kwargs),
    )

    with patch("app.main.sf.verify_webhook_secret", return_value=True):
        resp = auth_client.post(
            "/integrations/salesforce/events",
            json={
                "connection_id": connection_id,
                "opportunity_id": "006AUTOORDER1",
                "stage_name": "Demo Completed",
                "contact_name": "Alex Buyer",
                "contact_email": "alex@acme.com",
            },
            headers={"X-Webhook-Secret": "test-secret"},
        )

    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["status"] == "auto_ordered"
    assert body["order_id"]
    assert reminders == []
    assert len(address_mails) == 1

    orders = auth_client.get("/gift-orders").json()
    match = next(o for o in orders if o["id"] == body["order_id"])
    assert match["gift_id"] == "cookies-12"
    assert match["payment_status"] == "owed"
    assert match["status"] == "no_address"


def test_reminder_still_sent_when_auto_order_off(auth_client, monkeypatch):
    me = auth_client.get("/auth/me").json()
    connection_id = _seed_crm(me["user_id"])

    reminders: list[dict] = []
    monkeypatch.setattr(
        "app.integrations.reminders.send_cookie_reminder",
        lambda **kwargs: reminders.append(kwargs),
    )

    with patch("app.main.sf.verify_webhook_secret", return_value=True):
        resp = auth_client.post(
            "/integrations/salesforce/events",
            json={
                "connection_id": connection_id,
                "opportunity_id": "006REMINDER1",
                "stage_name": "Demo Completed",
                "contact_name": "Sam",
                "contact_email": "sam@example.com",
            },
        )

    assert resp.status_code == 200
    assert resp.json()["status"] == "sent"
    assert len(reminders) == 1


def test_auto_order_uses_crm_note_and_address(auth_client, stripe_stub, monkeypatch):
    me = auth_client.get("/auth/me").json()
    connection_id = _seed_crm(me["user_id"])
    _enable_monthly_with_pm(me["user_id"], gift_id="cookies-4")

    db = SessionLocal()
    try:
        user = db.get(UserModel, me["user_id"])
        assert user is not None
        user.auto_order_enabled = True
        db.add(user)
        db.commit()
    finally:
        db.close()

    address_mails: list[dict] = []
    monkeypatch.setattr(
        "app.stripe_payments.send_recipient_address_request",
        lambda **kwargs: address_mails.append(kwargs),
    )

    with patch("app.main.sf.verify_webhook_secret", return_value=True):
        resp = auth_client.post(
            "/integrations/salesforce/events",
            json={
                "connection_id": connection_id,
                "opportunity_id": "006CRMFIELDS1",
                "stage_name": "Demo Completed",
                "contact_name": "Alex Buyer",
                "contact_email": "alex@acme.com",
                "cookie_note": "Great demo — enjoy these!",
                "cookie_address": "123 Main St\nSpringfield, IL 62704",
            },
            headers={"X-Webhook-Secret": "test-secret"},
        )

    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["status"] == "auto_ordered"
    assert body.get("has_shipping_address") is True
    assert address_mails == []

    orders = auth_client.get("/gift-orders").json()
    match = next(o for o in orders if o["id"] == body["order_id"])
    assert match["note"] == "Great demo — enjoy these!"
    assert "123 Main St" in (match["shipping_address"] or "")
    assert match["status"] == "queued"
    assert match["payment_status"] == "owed"


def test_crm_auto_order_uses_structured_cookie_address(
    auth_client, stripe_stub, monkeypatch
):
    me = auth_client.get("/auth/me").json()
    connection_id = _seed_crm(me["user_id"])
    _enable_monthly_with_pm(me["user_id"])

    db = SessionLocal()
    try:
        user = db.get(UserModel, me["user_id"])
        assert user is not None
        user.auto_order_enabled = True
        db.add(user)
        db.commit()
    finally:
        db.close()

    with patch("app.main.sf.verify_webhook_secret", return_value=True):
        resp = auth_client.post(
            "/integrations/salesforce/events",
            json={
                "connection_id": connection_id,
                "opportunity_id": "006CRMSTREET1",
                "stage_name": "Demo Completed",
                "contact_name": "Alex Buyer",
                "contact_email": "alex@acme.com",
                "cookie_note": "Great demo — enjoy these!",
                "cookie_street": "123 Main St",
                "cookie_city": "Springfield",
                "cookie_state": "IL",
                "cookie_postal_code": "62704",
            },
            headers={"X-Webhook-Secret": "test-secret"},
        )

    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["status"] == "auto_ordered"
    assert body.get("has_shipping_address") is True

    orders = auth_client.get("/gift-orders").json()
    match = next(o for o in orders if o["id"] == body["order_id"])
    assert match["shipping_street"] == "123 Main St"
    assert match["shipping_city"] == "Springfield"
    assert match["shipping_state"] == "IL"
    assert match["shipping_postal_code"] == "62704"
    assert match["shipping_address"] == "123 Main St\nSpringfield, IL 62704"


def test_month_end_job_charges_owed(auth_client, stripe_stub, monkeypatch):
    me = auth_client.get("/auth/me").json()
    _seed_crm(me["user_id"])
    _enable_monthly_with_pm(me["user_id"])
    prospect = create_prospect(auth_client)

    monkeypatch.setattr(
        "app.fulfillment.send_new_order_notification",
        lambda **_kwargs: None,
    )
    monkeypatch.setattr(
        "app.stripe_payments.send_monthly_billing_receipt",
        lambda **_kwargs: None,
    )

    create = auth_client.post(
        "/gift-orders",
        json=make_order_payload(prospect["id"]),
    )
    assert create.status_code == 201

    with SessionLocal() as db:
        result = run_monthly_billing_job(
            db,
            now=datetime(2026, 8, 31, 15, 0, tzinfo=UTC),
            force_charge=True,
        )
    assert result["charged_users"] == 1
    assert stripe_stub.payment_intent_create_calls


def test_me_includes_billing_fields_when_crm_connected(auth_client):
    me = auth_client.get("/auth/me").json()
    assert me["crm_connected"] is False
    assert me["billing_mode"] == "per_order"
    assert me.get("max_spending_cents") is None

    _seed_crm(me["user_id"])
    _enable_monthly_with_pm(me["user_id"])
    me2 = auth_client.get("/auth/me").json()
    assert me2["crm_connected"] is True
    assert me2["billing_mode"] == "monthly"
    assert me2["has_payment_method"] is True


def test_spending_limit_requires_crm(auth_client):
    resp = auth_client.patch(
        "/auth/me/billing",
        json={"max_spending_cents": 5000},
    )
    assert resp.status_code == 400
    assert "API key" in resp.json()["detail"]


def test_spending_limit_can_be_set_and_cleared(auth_client):
    me = auth_client.get("/auth/me").json()
    _seed_crm(me["user_id"])

    set_resp = auth_client.patch(
        "/auth/me/billing",
        json={"max_spending_cents": 5000},
    )
    assert set_resp.status_code == 200
    assert set_resp.json()["max_spending_cents"] == 5000

    clear_resp = auth_client.patch(
        "/auth/me/billing",
        json={"max_spending_cents": None},
    )
    assert clear_resp.status_code == 200
    assert clear_resp.json()["max_spending_cents"] is None


def test_spending_limit_blocks_monthly_order_and_emails(
    auth_client, stripe_stub, monkeypatch
):
    me = auth_client.get("/auth/me").json()
    _seed_crm(me["user_id"])
    _enable_monthly_with_pm(me["user_id"])

    # Stub catalog prices are $1.00 (100 cents) — limit one open order.
    limit_resp = auth_client.patch(
        "/auth/me/billing",
        json={"max_spending_cents": 100},
    )
    assert limit_resp.status_code == 200

    prospect = create_prospect(auth_client)
    monkeypatch.setattr(
        "app.fulfillment.send_new_order_notification",
        lambda **_kwargs: None,
    )
    monkeypatch.setattr(
        "app.stripe_payments.send_recipient_address_request",
        lambda **_kwargs: None,
    )
    limit_mails: list[dict] = []
    monkeypatch.setattr(
        "app.stripe_payments.send_spending_limit_reached",
        lambda **kwargs: limit_mails.append(kwargs),
    )

    first = auth_client.post(
        "/gift-orders",
        json=make_order_payload(prospect["id"]),
    )
    assert first.status_code == 201, first.text
    assert limit_mails == []

    second_payload = make_order_payload(prospect["id"])
    second_payload["recipient_name"] = "Alex Still Waiting"
    second = auth_client.post("/gift-orders", json=second_payload)
    assert second.status_code == 402
    assert "spending limit" in second.json()["detail"].lower()
    assert len(limit_mails) == 1
    assert limit_mails[0]["limit_cents"] == 100
    assert limit_mails[0]["blocked_recipient_names"] == ["Alex Still Waiting"]

    # Do not re-email on every blocked attempt.
    third = auth_client.post(
        "/gift-orders",
        json=make_order_payload(prospect["id"]),
    )
    assert third.status_code == 402
    assert len(limit_mails) == 1


def test_raising_spending_limit_allows_orders_again(
    auth_client, stripe_stub, monkeypatch
):
    me = auth_client.get("/auth/me").json()
    _seed_crm(me["user_id"])
    _enable_monthly_with_pm(me["user_id"])
    auth_client.patch("/auth/me/billing", json={"max_spending_cents": 100})

    prospect = create_prospect(auth_client)
    monkeypatch.setattr(
        "app.fulfillment.send_new_order_notification",
        lambda **_kwargs: None,
    )
    monkeypatch.setattr(
        "app.stripe_payments.send_recipient_address_request",
        lambda **_kwargs: None,
    )
    monkeypatch.setattr(
        "app.stripe_payments.send_spending_limit_reached",
        lambda **_kwargs: None,
    )

    assert (
        auth_client.post(
            "/gift-orders",
            json=make_order_payload(prospect["id"]),
        ).status_code
        == 201
    )
    assert (
        auth_client.post(
            "/gift-orders",
            json=make_order_payload(prospect["id"]),
        ).status_code
        == 402
    )

    raised = auth_client.patch(
        "/auth/me/billing",
        json={"max_spending_cents": 500},
    )
    assert raised.status_code == 200

    again = auth_client.post(
        "/gift-orders",
        json=make_order_payload(prospect["id"]),
    )
    assert again.status_code == 201, again.text
