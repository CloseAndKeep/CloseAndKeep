"""Additional coverage for medium-severity hardening (CSV caps, amounts, auth expiry)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import stripe


def test_csv_import_rejects_oversized_upload(auth_client, monkeypatch):
    from app.config import settings

    monkeypatch.setattr(settings, "csv_import_max_bytes", 64)
    resp = auth_client.post(
        "/gift-orders/import",
        files={
            "file": (
                "orders.csv",
                b"Name,Email,Cookies,Address\n" + b"x" * 200,
                "text/csv",
            )
        },
    )
    assert resp.status_code == 400
    assert "too large" in resp.json()["detail"].lower()


def test_csv_import_rejects_too_many_rows(auth_client, monkeypatch, stripe_stub):
    from app.config import settings

    monkeypatch.setattr(settings, "csv_import_max_rows", 2)
    lines = ["Name,Email,Cookies,Address"]
    for i in range(3):
        lines.append(f"Person {i},p{i}@example.com,1,123 Main St")
    csv_text = "\n".join(lines) + "\n"
    resp = auth_client.post(
        "/gift-orders/import",
        files={"file": ("orders.csv", csv_text.encode("utf-8"), "text/csv")},
    )
    assert resp.status_code == 400
    detail = resp.json()["detail"]
    assert detail["message"]
    assert any("maximum of 2" in e["message"] for e in detail["errors"])


def test_webhook_rejects_amount_above_catalog(
    auth_client, prospect_id, stripe_stub, monkeypatch
):
    order = auth_client.post(
        "/gift-orders",
        json={
            "prospect_id": prospect_id,
            "gift_id": "cookies-4",
            "recipient_name": "Dana Buyer",
            "shipping_address": "123 Main St",
            "note": "Thanks!",
        },
    ).json()

    event = {
        "type": "checkout.session.completed",
        "data": {
            "object": {
                "id": "cs_test_created",
                "mode": "payment",
                "metadata": {"gift_order_id": str(order["id"])},
                "payment_status": "paid",
                "amount_total": 99999,
                "currency": "usd",
            }
        },
    }
    monkeypatch.setattr(
        stripe.Webhook,
        "construct_event",
        staticmethod(lambda payload, sig, secret: event),
    )
    resp = auth_client.post(
        "/billing/webhook",
        content=b"{}",
        headers={"Stripe-Signature": "t=1,v1=validsig"},
    )
    assert resp.status_code == 200
    fetched = auth_client.get(f"/gift-orders/{order['id']}").json()
    assert fetched["payment_status"] == "pending"


def test_admin_cancel_fails_closed_when_stripe_cancel_fails(
    auth_client, admin_client, prospect_id, stripe_stub, monkeypatch
):
    import app.stripe_payments as sp
    from app.db import SessionLocal
    from app.models import GiftOrderModel

    monkeypatch.setattr(sp, "send_recipient_address_request", lambda **kw: None)

    def _boom(*_a, **_k):
        raise stripe.error.StripeError("cancel failed")

    monkeypatch.setattr(stripe.PaymentIntent, "cancel", staticmethod(_boom))

    order = auth_client.post(
        "/gift-orders",
        json={
            "prospect_id": prospect_id,
            "gift_id": "cookies-4",
            "recipient_name": "Dana Buyer",
            "note": "Thanks!",
            "request_recipient_address": True,
            "recipient_email": "dana@example.com",
        },
    ).json()

    with SessionLocal() as db:
        row = db.get(GiftOrderModel, order["id"])
        session = {
            "id": row.stripe_checkout_session_id or "cs_test_created",
            "mode": "payment",
            "status": "complete",
            "payment_status": "unpaid",
            "payment_intent": "pi_test_123",
            "amount_total": 100,
            "currency": "usd",
            "metadata": {"gift_order_id": str(order["id"]), "defer_capture": "true"},
        }
        sp.fulfill_order_from_checkout_session(session, db)

    resp = admin_client.patch(
        f"/admin/gift-orders/{order['id']}",
        json={"status": "canceled"},
    )
    assert resp.status_code == 502

    refreshed = auth_client.get(f"/gift-orders/{order['id']}").json()
    assert refreshed["payment_status"] == "authorized"
    assert refreshed["status"] == "no_address"


def test_payment_intent_canceled_webhook_expires_authorization(
    auth_client, prospect_id, stripe_stub, monkeypatch
):
    import app.stripe_payments as sp
    from app.db import SessionLocal
    from app.models import GiftOrderModel

    monkeypatch.setattr(sp, "send_recipient_address_request", lambda **kw: None)
    order = auth_client.post(
        "/gift-orders",
        json={
            "prospect_id": prospect_id,
            "gift_id": "cookies-4",
            "recipient_name": "Dana Buyer",
            "note": "Thanks!",
            "request_recipient_address": True,
            "recipient_email": "dana@example.com",
        },
    ).json()

    with SessionLocal() as db:
        row = db.get(GiftOrderModel, order["id"])
        token = row.address_request_token
        session = {
            "id": row.stripe_checkout_session_id or "cs_test_created",
            "mode": "payment",
            "status": "complete",
            "payment_status": "unpaid",
            "payment_intent": "pi_test_123",
            "amount_total": 100,
            "currency": "usd",
            "metadata": {"gift_order_id": str(order["id"]), "defer_capture": "true"},
        }
        sp.fulfill_order_from_checkout_session(session, db)

    event = {
        "type": "payment_intent.canceled",
        "data": {"object": {"id": "pi_test_123", "status": "canceled"}},
    }
    monkeypatch.setattr(
        stripe.Webhook,
        "construct_event",
        staticmethod(lambda payload, sig, secret: event),
    )
    assert (
        auth_client.post(
            "/billing/webhook",
            content=b"{}",
            headers={"Stripe-Signature": "t=1,v1=validsig"},
        ).status_code
        == 200
    )

    refreshed = auth_client.get(f"/gift-orders/{order['id']}").json()
    assert refreshed["payment_status"] == "canceled"
    assert refreshed["status"] == "canceled"
    assert auth_client.get(f"/public/address-requests/{token}").status_code == 404


def test_address_token_expires(auth_client, prospect_id, stripe_stub, monkeypatch):
    import app.stripe_payments as sp
    from app.db import SessionLocal
    from app.models import GiftOrderModel

    monkeypatch.setattr(sp, "send_recipient_address_request", lambda **kw: None)
    order = auth_client.post(
        "/gift-orders",
        json={
            "prospect_id": prospect_id,
            "gift_id": "cookies-4",
            "recipient_name": "Dana Buyer",
            "note": "Thanks!",
            "request_recipient_address": True,
            "recipient_email": "dana@example.com",
        },
    ).json()

    with SessionLocal() as db:
        row = db.get(GiftOrderModel, order["id"])
        token = row.address_request_token
        row.address_request_expires_at = datetime.now(UTC) - timedelta(minutes=1)
        db.add(row)
        db.commit()
        session = {
            "id": row.stripe_checkout_session_id or "cs_test_created",
            "mode": "payment",
            "status": "complete",
            "payment_status": "unpaid",
            "payment_intent": "pi_test_123",
            "amount_total": 100,
            "currency": "usd",
            "metadata": {"gift_order_id": str(order["id"]), "defer_capture": "true"},
        }
        sp.fulfill_order_from_checkout_session(session, db)

    assert auth_client.get(f"/public/address-requests/{token}").status_code == 404


def test_session_cookie_secure_defaults_true_in_production(monkeypatch):
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.delenv("SESSION_COOKIE_SECURE", raising=False)
    # Re-evaluate default helper without reloading full Settings (pydantic already built).
    from app import config

    assert config._default_session_cookie_secure() == "true"
