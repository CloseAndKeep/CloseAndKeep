"""Recipient address-request flow: authorize → email link → capture on address."""

from __future__ import annotations

from conftest import create_prospect, make_order_payload


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


def _authorize_order(auth_client, order_id: int, stripe_stub, monkeypatch):
    """Simulate Stripe checkout.session.completed for a manual-capture order."""
    import app.stripe_payments as sp
    from app.db import SessionLocal
    from app.models import GiftOrderModel

    with SessionLocal() as db:
        order = db.get(GiftOrderModel, order_id)
        session = {
            "id": order.stripe_checkout_session_id or "cs_test_created",
            "mode": "payment",
            "status": "complete",
            "payment_status": "unpaid",
            "payment_intent": "pi_test_123",
            "metadata": {
                "gift_order_id": str(order_id),
                "defer_capture": "true",
            },
        }
        sp.fulfill_order_from_checkout_session(session, db)


def test_guest_cannot_request_recipient_address(client, stripe_stub):
    assert client.post("/auth/guest").status_code == 200
    prospect = create_prospect(client, email="guest-prospect@example.com")
    resp = client.post("/gift-orders", json=_request_payload(prospect["id"]))
    assert resp.status_code == 403
    assert "guest" in resp.json()["detail"].lower()


def test_request_address_starts_manual_capture_checkout(
    auth_client, prospect_id, stripe_stub, monkeypatch
):
    recipient_mail: dict = {}
    import app.stripe_payments as sp

    monkeypatch.setattr(
        sp, "send_recipient_address_request", lambda **kw: recipient_mail.update(kw)
    )

    resp = auth_client.post("/gift-orders", json=_request_payload(prospect_id))
    assert resp.status_code == 201, resp.text
    order = resp.json()

    assert order["status"] == "no_address"
    assert order["payment_status"] == "pending"
    assert order["shipping_address"] is None
    assert order["recipient_email"] == "dana@example.com"
    assert order["checkout_url"] == stripe_stub.created_session["url"]
    assert recipient_mail == {}  # email only after authorization

    params = stripe_stub.session_create_calls[0]
    assert params["payment_intent_data"] == {"capture_method": "manual"}
    assert params["metadata"]["defer_capture"] == "true"


def test_authorization_sends_recipient_email(
    auth_client, prospect_id, stripe_stub, monkeypatch
):
    recipient_mail: dict = {}
    import app.stripe_payments as sp

    monkeypatch.setattr(
        sp, "send_recipient_address_request", lambda **kw: recipient_mail.update(kw)
    )

    order = auth_client.post("/gift-orders", json=_request_payload(prospect_id)).json()
    _authorize_order(auth_client, order["id"], stripe_stub, monkeypatch)

    refreshed = auth_client.get(f"/gift-orders/{order['id']}").json()
    assert refreshed["payment_status"] == "authorized"
    assert refreshed["status"] == "no_address"
    assert recipient_mail["recipient_email"] == "dana@example.com"
    assert "/ship/" in recipient_mail["address_form_url"]


def test_cannot_checkout_again_after_authorization(
    auth_client, prospect_id, stripe_stub, monkeypatch
):
    import app.stripe_payments as sp

    monkeypatch.setattr(sp, "send_recipient_address_request", lambda **kw: None)

    order = auth_client.post("/gift-orders", json=_request_payload(prospect_id)).json()
    _authorize_order(auth_client, order["id"], stripe_stub, monkeypatch)

    resp = auth_client.post(f"/gift-orders/{order['id']}/checkout")
    assert resp.status_code == 400
    assert "authorized" in resp.json()["detail"].lower()


def test_recipient_submit_captures_payment_and_emails(
    auth_client, prospect_id, stripe_stub, monkeypatch
):
    import app.main as main
    import app.fulfillment as fulfillment
    import app.stripe_payments as sp
    from app.db import SessionLocal
    from app.models import GiftOrderModel

    monkeypatch.setattr(sp, "send_recipient_address_request", lambda **kw: None)
    orderer_mail: dict = {}
    monkeypatch.setattr(
        main, "send_orderer_address_received", lambda **kw: orderer_mail.update(kw)
    )
    ops_mail: dict = {}
    monkeypatch.setattr(
        fulfillment, "send_new_order_notification", lambda **kw: ops_mail.update(kw)
    )

    order = auth_client.post("/gift-orders", json=_request_payload(prospect_id)).json()
    _authorize_order(auth_client, order["id"], stripe_stub, monkeypatch)

    with SessionLocal() as db:
        token = db.get(GiftOrderModel, order["id"]).address_request_token
    assert token

    submit = auth_client.post(
        f"/public/address-requests/{token}",
        json={
            "shipping_address": "456 Oak Ave\nAustin, TX 78701",
            "recipient_name": "Dana Buyer",
        },
    )
    assert submit.status_code == 200, submit.text
    assert submit.json()["already_submitted"] is True

    assert len(stripe_stub.payment_intent_capture_calls) == 1
    assert stripe_stub.payment_intent_capture_calls[0]["id"] == "pi_test_123"

    refreshed = auth_client.get(f"/gift-orders/{order['id']}").json()
    assert refreshed["status"] == "queued"
    assert refreshed["shipping_address"] == "456 Oak Ave\nAustin, TX 78701"
    assert refreshed["payment_status"] == "paid"

    assert orderer_mail["order_id"] == order["id"]
    assert "456 Oak Ave" in orderer_mail["shipping_address"]
    assert ops_mail["order_id"] == order["id"]  # ops email after capture


def test_submit_before_authorization_rejected(
    auth_client, prospect_id, stripe_stub, monkeypatch
):
    import app.stripe_payments as sp
    from app.db import SessionLocal
    from app.models import GiftOrderModel

    monkeypatch.setattr(sp, "send_recipient_address_request", lambda **kw: None)

    order = auth_client.post("/gift-orders", json=_request_payload(prospect_id)).json()
    with SessionLocal() as db:
        token = db.get(GiftOrderModel, order["id"]).address_request_token

    resp = auth_client.post(
        f"/public/address-requests/{token}",
        json={"shipping_address": "123 Main"},
    )
    assert resp.status_code == 400
    assert len(stripe_stub.payment_intent_capture_calls) == 0


def test_request_address_requires_recipient_email(auth_client, prospect_id, stripe_stub):
    payload = _request_payload(prospect_id)
    del payload["recipient_email"]
    resp = auth_client.post("/gift-orders", json=payload)
    assert resp.status_code == 422


def test_normal_order_still_requires_shipping_address(auth_client, prospect_id, stripe_stub):
    payload = make_order_payload(prospect_id)
    del payload["shipping_address"]
    resp = auth_client.post("/gift-orders", json=payload)
    assert resp.status_code == 422


def test_normal_checkout_does_not_use_manual_capture(auth_client, prospect_id, stripe_stub):
    auth_client.post("/gift-orders", json=make_order_payload(prospect_id))
    params = stripe_stub.session_create_calls[0]
    assert "payment_intent_data" not in params
    assert params["metadata"]["defer_capture"] == "false"


def test_admin_can_filter_no_address_orders(
    auth_client, admin_client, prospect_id, stripe_stub, monkeypatch
):
    import app.stripe_payments as sp

    monkeypatch.setattr(sp, "send_recipient_address_request", lambda **kw: None)
    order = auth_client.post("/gift-orders", json=_request_payload(prospect_id)).json()

    listed = admin_client.get("/admin/gift-orders?status=no_address")
    assert listed.status_code == 200
    ids = [row["id"] for row in listed.json()]
    assert order["id"] in ids


def test_public_get_address_request(auth_client, prospect_id, stripe_stub, monkeypatch):
    import app.stripe_payments as sp
    from app.db import SessionLocal
    from app.models import GiftOrderModel

    monkeypatch.setattr(sp, "send_recipient_address_request", lambda **kw: None)
    order = auth_client.post("/gift-orders", json=_request_payload(prospect_id)).json()
    with SessionLocal() as db:
        token = db.get(GiftOrderModel, order["id"]).address_request_token

    # Public GET does not require auth.
    auth_client.post("/auth/logout")
    resp = auth_client.get(f"/public/address-requests/{token}")
    assert resp.status_code == 200
    body = resp.json()
    assert body["recipient_name"] == "Dana Buyer"
    assert body["gift_id"] == "cookies-4"
    assert body["already_submitted"] is False


def test_public_address_request_unknown_token_404(client):
    assert client.get("/public/address-requests/not-a-real-token").status_code == 404
    assert (
        client.post(
            "/public/address-requests/not-a-real-token",
            json={"shipping_address": "123 Main"},
        ).status_code
        == 404
    )


def test_resubmit_address_is_idempotent(
    auth_client, prospect_id, stripe_stub, monkeypatch
):
    import app.stripe_payments as sp
    import app.fulfillment as fulfillment
    import app.main as main
    from app.db import SessionLocal
    from app.models import GiftOrderModel

    monkeypatch.setattr(sp, "send_recipient_address_request", lambda **kw: None)
    monkeypatch.setattr(main, "send_orderer_address_received", lambda **kw: None)
    monkeypatch.setattr(fulfillment, "send_new_order_notification", lambda **kw: None)

    order = auth_client.post("/gift-orders", json=_request_payload(prospect_id)).json()
    _authorize_order(auth_client, order["id"], stripe_stub, monkeypatch)
    with SessionLocal() as db:
        token = db.get(GiftOrderModel, order["id"]).address_request_token

    first = auth_client.post(
        f"/public/address-requests/{token}",
        json={"shipping_address": "456 Oak Ave"},
    )
    assert first.status_code == 200
    assert first.json()["already_submitted"] is True
    assert len(stripe_stub.payment_intent_capture_calls) == 1

    second = auth_client.post(
        f"/public/address-requests/{token}",
        json={"shipping_address": "999 Different St"},
    )
    assert second.status_code == 200
    assert second.json()["already_submitted"] is True
    # No second capture; address stays the first one.
    assert len(stripe_stub.payment_intent_capture_calls) == 1
    refreshed = auth_client.get(f"/gift-orders/{order['id']}").json()
    assert refreshed["shipping_address"] == "456 Oak Ave"


def test_capture_failure_clears_address_so_link_stays_usable(
    auth_client, prospect_id, stripe_stub, monkeypatch
):
    import app.main as main
    import app.stripe_payments as sp
    from app.db import SessionLocal
    from app.models import GiftOrderModel
    from fastapi import HTTPException

    monkeypatch.setattr(sp, "send_recipient_address_request", lambda **kw: None)

    def _boom(order, db):
        raise HTTPException(status_code=502, detail="Unable to capture payment.")

    # main imports capture_authorized_order by name — patch the binding there.
    monkeypatch.setattr(main, "capture_authorized_order", _boom)

    order = auth_client.post("/gift-orders", json=_request_payload(prospect_id)).json()
    _authorize_order(auth_client, order["id"], stripe_stub, monkeypatch)
    with SessionLocal() as db:
        token = db.get(GiftOrderModel, order["id"]).address_request_token

    resp = auth_client.post(
        f"/public/address-requests/{token}",
        json={"shipping_address": "456 Oak Ave"},
    )
    assert resp.status_code == 502

    with SessionLocal() as db:
        refreshed = db.get(GiftOrderModel, order["id"])
        assert refreshed.shipping_address is None
        assert refreshed.status == "no_address"
        assert refreshed.payment_status == "authorized"


def test_admin_cancel_releases_authorized_payment(
    auth_client, admin_client, prospect_id, stripe_stub, monkeypatch
):
    import app.stripe_payments as sp
    from app.db import SessionLocal
    from app.models import GiftOrderModel

    monkeypatch.setattr(sp, "send_recipient_address_request", lambda **kw: None)
    order = auth_client.post("/gift-orders", json=_request_payload(prospect_id)).json()
    _authorize_order(auth_client, order["id"], stripe_stub, monkeypatch)

    with SessionLocal() as db:
        row = db.get(GiftOrderModel, order["id"])
        assert row.payment_status == "authorized"
        assert row.stripe_payment_intent_id == "pi_test_123"

    resp = admin_client.patch(
        f"/admin/gift-orders/{order['id']}",
        json={"status": "canceled"},
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["status"] == "canceled"
    assert body["payment_status"] == "canceled"
    assert len(stripe_stub.payment_intent_cancel_calls) == 1
    assert stripe_stub.payment_intent_cancel_calls[0]["id"] == "pi_test_123"


def test_blank_shipping_address_on_public_submit_rejected(
    auth_client, prospect_id, stripe_stub, monkeypatch
):
    import app.stripe_payments as sp
    from app.db import SessionLocal
    from app.models import GiftOrderModel

    monkeypatch.setattr(sp, "send_recipient_address_request", lambda **kw: None)
    order = auth_client.post("/gift-orders", json=_request_payload(prospect_id)).json()
    _authorize_order(auth_client, order["id"], stripe_stub, monkeypatch)
    with SessionLocal() as db:
        token = db.get(GiftOrderModel, order["id"]).address_request_token

    resp = auth_client.post(
        f"/public/address-requests/{token}",
        json={"shipping_address": "   "},
    )
    assert resp.status_code == 422
    assert len(stripe_stub.payment_intent_capture_calls) == 0
