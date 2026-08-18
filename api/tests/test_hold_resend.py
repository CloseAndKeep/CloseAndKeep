"""Expired address-hold queue + one-click resend (in-app)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from conftest import create_prospect, signup

from app.db import SessionLocal
from app.models import GiftOrderModel, UserModel


def _request_payload(prospect_id: int, **overrides) -> dict:
    payload = {
        "prospect_id": prospect_id,
        "gift_id": "cookies-4",
        "recipient_name": "Dana Buyer",
        "note": "Thanks for the great meeting!",
        "request_recipient_address": True,
        "recipient_email": "dana@example.com",
    }
    payload.update(overrides)
    return payload


def _authorize_order(order_id: int) -> None:
    import app.stripe_payments as sp

    with SessionLocal() as db:
        order = db.get(GiftOrderModel, order_id)
        session = {
            "id": order.stripe_checkout_session_id or "cs_test_created",
            "mode": "payment",
            "status": "complete",
            "payment_status": "unpaid",
            "payment_intent": "pi_test_123",
            "amount_total": 100,
            "currency": "usd",
            "metadata": {
                "gift_order_id": str(order_id),
                "defer_capture": "true",
            },
        }
        sp.fulfill_order_from_checkout_session(session, db)


def _expire_hold(order_id: int, auth_client) -> None:
    with SessionLocal() as db:
        row = db.get(GiftOrderModel, order_id)
        token = row.address_request_token
        row.address_request_expires_at = datetime.now(UTC) - timedelta(minutes=1)
        db.add(row)
        db.commit()
    assert auth_client.get(f"/public/address-requests/{token}").status_code == 404


def _enable_monthly_with_pm(user_id: int) -> None:
    with SessionLocal() as db:
        user = db.get(UserModel, user_id)
        assert user is not None
        user.billing_mode = "monthly"
        user.stripe_customer_id = "cus_test_123"
        user.stripe_default_payment_method_id = "pm_test_card"
        db.add(user)
        db.commit()


def test_expired_holds_empty_for_fresh_seller(auth_client):
    resp = auth_client.get("/gift-orders/expired-holds")
    assert resp.status_code == 200
    assert resp.json() == []


def test_expired_holds_requires_auth(client):
    assert client.get("/gift-orders/expired-holds").status_code == 401


def test_list_includes_expired_hold_and_links_order(
    auth_client, prospect_id, stripe_stub, monkeypatch
):
    import app.stripe_payments as sp

    monkeypatch.setattr(sp, "send_recipient_address_request", lambda **kw: None)
    monkeypatch.setattr(sp, "send_seller_address_hold_expired", lambda **kw: None)

    order = auth_client.post("/gift-orders", json=_request_payload(prospect_id)).json()
    _authorize_order(order["id"])
    _expire_hold(order["id"], auth_client)

    listed = auth_client.get("/gift-orders")
    assert listed.status_code == 200
    assert any(row["id"] == order["id"] for row in listed.json())

    queue = auth_client.get("/gift-orders/expired-holds")
    assert queue.status_code == 200
    body = queue.json()
    assert len(body) == 1
    assert body[0]["id"] == order["id"]
    assert body[0]["recipient_name"] == "Dana Buyer"
    assert body[0]["status"] == "canceled"
    assert body[0]["payment_status"] == "canceled"


def test_list_excludes_canceled_order_that_had_an_address(
    auth_client, prospect_id, stripe_stub
):
    created = auth_client.post(
        "/gift-orders",
        json={
            "prospect_id": prospect_id,
            "gift_id": "cookies-4",
            "recipient_name": "Dana Buyer",
            "shipping_address": "123 Main St\nSpringfield, IL 62704",
            "note": "Thanks!",
        },
    )
    assert created.status_code == 201, created.text
    order_id = created.json()["id"]

    with SessionLocal() as db:
        row = db.get(GiftOrderModel, order_id)
        row.status = "canceled"
        row.payment_status = "canceled"
        db.add(row)
        db.commit()

    queue = auth_client.get("/gift-orders/expired-holds")
    assert queue.status_code == 200
    assert queue.json() == []


def test_list_is_owner_only(auth_client, prospect_id, stripe_stub, monkeypatch, make_client):
    import app.stripe_payments as sp

    monkeypatch.setattr(sp, "send_recipient_address_request", lambda **kw: None)
    monkeypatch.setattr(sp, "send_seller_address_hold_expired", lambda **kw: None)

    order = auth_client.post("/gift-orders", json=_request_payload(prospect_id)).json()
    _authorize_order(order["id"])
    _expire_hold(order["id"], auth_client)

    other = make_client()
    signup(other, "other-seller@example.com")
    other_queue = other.get("/gift-orders/expired-holds")
    assert other_queue.status_code == 200
    assert other_queue.json() == []

    resend = other.post(f"/gift-orders/{order['id']}/resend-address")
    assert resend.status_code == 404


def test_resend_creates_new_authorize_checkout(
    auth_client, prospect_id, stripe_stub, monkeypatch
):
    import app.stripe_payments as sp

    monkeypatch.setattr(sp, "send_recipient_address_request", lambda **kw: None)
    monkeypatch.setattr(sp, "send_seller_address_hold_expired", lambda **kw: None)

    order = auth_client.post("/gift-orders", json=_request_payload(prospect_id)).json()
    _authorize_order(order["id"])
    _expire_hold(order["id"], auth_client)

    with SessionLocal() as db:
        before = db.get(GiftOrderModel, order["id"])
        old_token = before.address_request_token
        assert old_token is None

    stripe_stub.session_create_calls.clear()
    stripe_stub.created_session = {
        "id": "cs_test_resend",
        "url": "https://checkout.stripe.test/pay/cs_test_resend",
    }

    resp = auth_client.post(f"/gift-orders/{order['id']}/resend-address")
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["id"] == order["id"]
    assert body["status"] == "no_address"
    assert body["payment_status"] == "pending"
    assert body["checkout_url"] == "https://checkout.stripe.test/pay/cs_test_resend"
    assert body["redeem_code"]

    assert len(stripe_stub.session_create_calls) == 1
    params = stripe_stub.session_create_calls[0]
    assert params["payment_intent_data"] == {"capture_method": "manual"}
    assert params["metadata"]["defer_capture"] == "true"
    assert params["metadata"]["gift_order_id"] == str(order["id"])

    with SessionLocal() as db:
        row = db.get(GiftOrderModel, order["id"])
        assert row.address_request_token
        assert row.address_request_token != old_token
        assert row.stripe_payment_intent_id is None
        assert row.stripe_checkout_session_id == "cs_test_resend"
        assert row.address_request_sent_at is None

    queue = auth_client.get("/gift-orders/expired-holds")
    assert queue.json() == []


def test_resend_monthly_owed_mints_token_without_checkout(
    auth_client, stripe_stub, monkeypatch
):
    import app.stripe_payments as sp

    recipient_mail: dict = {}
    monkeypatch.setattr(
        sp, "send_recipient_address_request", lambda **kw: recipient_mail.update(kw)
    )
    monkeypatch.setattr(sp, "send_seller_address_hold_expired", lambda **kw: None)

    me = auth_client.get("/auth/me").json()
    _enable_monthly_with_pm(me["user_id"])
    prospect = create_prospect(auth_client)

    created = auth_client.post(
        "/gift-orders",
        json=_request_payload(prospect["id"]),
    )
    assert created.status_code == 201, created.text
    assert created.json()["checkout_url"] is None
    assert created.json()["payment_status"] == "owed"
    order_id = created.json()["id"]
    assert not stripe_stub.session_create_calls

    _expire_hold(order_id, auth_client)
    recipient_mail.clear()
    stripe_stub.session_create_calls.clear()

    resp = auth_client.post(f"/gift-orders/{order_id}/resend-address")
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["checkout_url"] is None
    assert body["status"] == "no_address"
    assert body["payment_status"] == "owed"
    assert recipient_mail["recipient_email"] == "dana@example.com"
    assert "/ship/" in recipient_mail["address_form_url"]
    assert not stripe_stub.session_create_calls

    with SessionLocal() as db:
        row = db.get(GiftOrderModel, order_id)
        assert row.address_request_token
        assert row.stripe_payment_intent_id is None


def test_resend_rejects_active_hold(auth_client, prospect_id, stripe_stub, monkeypatch):
    import app.stripe_payments as sp

    monkeypatch.setattr(sp, "send_recipient_address_request", lambda **kw: None)

    order = auth_client.post("/gift-orders", json=_request_payload(prospect_id)).json()
    _authorize_order(order["id"])

    resp = auth_client.post(f"/gift-orders/{order['id']}/resend-address")
    assert resp.status_code == 400
    assert "expired" in resp.json()["detail"].lower()


def test_resend_unknown_order_404(auth_client):
    resp = auth_client.post("/gift-orders/999999/resend-address")
    assert resp.status_code == 404
