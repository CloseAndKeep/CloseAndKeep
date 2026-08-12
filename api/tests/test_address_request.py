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
            "amount_total": 100,
            "currency": "usd",
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
    assert order["redeem_code"]
    assert order["redeem_code"].startswith("CK-")
    _authorize_order(auth_client, order["id"], stripe_stub, monkeypatch)

    refreshed = auth_client.get(f"/gift-orders/{order['id']}").json()
    assert refreshed["payment_status"] == "authorized"
    assert refreshed["status"] == "no_address"
    assert recipient_mail["recipient_email"] == "dana@example.com"
    assert "/ship/" in recipient_mail["address_form_url"]
    assert recipient_mail["redeem_code"] == order["redeem_code"]
    assert "/redeem" in recipient_mail["redeem_url"]
    assert recipient_mail["sender_name"] == "Test Seller"
    assert recipient_mail["sender_company"] == "CloseAndKeep Test"
    assert recipient_mail["gift_label"]
    assert recipient_mail.get("sender_avatar_data") in (None, b"")


def test_authorization_includes_buyer_avatar_in_address_email(
    auth_client, prospect_id, stripe_stub, monkeypatch
):
    from app.db import SessionLocal
    from app.models import UserModel

    tiny_png = (
        b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01"
        b"\x08\x02\x00\x00\x00\x90wS\xde\x00\x00\x00\x0cIDATx\x9cc\xf8\x0f\x00"
        b"\x00\x01\x01\x00\x05\x18\xd8N\x00\x00\x00\x00IEND\xaeB`\x82"
    )
    me = auth_client.get("/auth/me").json()
    with SessionLocal() as db:
        user = db.get(UserModel, me["user_id"])
        user.avatar_data = tiny_png
        user.avatar_content_type = "image/png"
        db.add(user)
        db.commit()

    recipient_mail: dict = {}
    import app.stripe_payments as sp

    monkeypatch.setattr(
        sp, "send_recipient_address_request", lambda **kw: recipient_mail.update(kw)
    )

    order = auth_client.post("/gift-orders", json=_request_payload(prospect_id)).json()
    _authorize_order(auth_client, order["id"], stripe_stub, monkeypatch)

    assert recipient_mail["sender_avatar_data"] == tiny_png
    assert recipient_mail["sender_avatar_content_type"] == "image/png"


def test_request_address_without_email_skips_send_but_mints_redeem_code(
    auth_client, prospect_id, stripe_stub, monkeypatch
):
    recipient_mail: dict = {}
    import app.stripe_payments as sp

    monkeypatch.setattr(
        sp, "send_recipient_address_request", lambda **kw: recipient_mail.update(kw)
    )

    payload = _request_payload(prospect_id)
    del payload["recipient_email"]
    resp = auth_client.post("/gift-orders", json=payload)
    assert resp.status_code == 201, resp.text
    order = resp.json()
    assert order["recipient_email"] is None
    assert order["redeem_code"]
    assert order["status"] == "no_address"

    params = stripe_stub.session_create_calls[0]
    assert params["payment_intent_data"] == {"capture_method": "manual"}
    assert params["metadata"]["defer_capture"] == "true"

    _authorize_order(auth_client, order["id"], stripe_stub, monkeypatch)
    assert recipient_mail == {}
    refreshed = auth_client.get(f"/gift-orders/{order['id']}").json()
    assert refreshed["payment_status"] == "authorized"
    assert refreshed["redeem_code"] == order["redeem_code"]


def test_normal_order_still_requires_shipping_address(auth_client, prospect_id, stripe_stub):
    payload = make_order_payload(prospect_id)
    del payload["shipping_address"]
    resp = auth_client.post("/gift-orders", json=payload)
    assert resp.status_code == 422


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
    import app.fulfillment as fulfillment
    import app.stripe_payments as sp
    from app.db import SessionLocal
    from app.models import GiftOrderModel

    monkeypatch.setattr(sp, "send_recipient_address_request", lambda **kw: None)
    orderer_mail: dict = {}
    monkeypatch.setattr(
        sp, "send_orderer_receipt", lambda **kw: orderer_mail.update(kw)
    )
    ops_mail: dict = {}
    monkeypatch.setattr(
        fulfillment, "send_new_order_notification", lambda **kw: ops_mail.update(kw)
    )

    order = auth_client.post("/gift-orders", json=_request_payload(prospect_id)).json()
    _authorize_order(auth_client, order["id"], stripe_stub, monkeypatch)
    assert orderer_mail == {}  # no receipt on authorize-only

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
    assert "456 Oak Ave" in (orderer_mail.get("shipping_address") or "")
    assert orderer_mail["gift_label"]
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
    from app.db import SessionLocal
    from app.models import GiftOrderModel

    monkeypatch.setattr(sp, "send_recipient_address_request", lambda **kw: None)
    monkeypatch.setattr(sp, "send_orderer_receipt", lambda **kw: None)
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
    # Token is cleared after successful capture so the link cannot re-expose PII.
    assert second.status_code == 404
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


def test_recipient_submit_accepts_structured_address(
    auth_client, prospect_id, stripe_stub, monkeypatch
):
    import app.fulfillment as fulfillment
    import app.stripe_payments as sp
    from app.db import SessionLocal
    from app.models import GiftOrderModel

    monkeypatch.setattr(sp, "send_recipient_address_request", lambda **kw: None)
    monkeypatch.setattr(sp, "send_orderer_receipt", lambda **kw: None)
    monkeypatch.setattr(fulfillment, "send_new_order_notification", lambda **kw: None)

    order = auth_client.post("/gift-orders", json=_request_payload(prospect_id)).json()
    _authorize_order(auth_client, order["id"], stripe_stub, monkeypatch)
    with SessionLocal() as db:
        token = db.get(GiftOrderModel, order["id"]).address_request_token
    assert token

    submit = auth_client.post(
        f"/public/address-requests/{token}",
        json={
            "shipping_street": "456 Oak Ave",
            "shipping_city": "Austin",
            "shipping_state": "TX",
            "shipping_postal_code": "78701",
            "recipient_name": "Dana Buyer",
        },
    )
    assert submit.status_code == 200, submit.text
    refreshed = auth_client.get(f"/gift-orders/{order['id']}").json()
    assert refreshed["shipping_street"] == "456 Oak Ave"
    assert refreshed["shipping_city"] == "Austin"
    assert refreshed["shipping_state"] == "TX"
    assert refreshed["shipping_postal_code"] == "78701"
    assert refreshed["shipping_address"] == "456 Oak Ave\nAustin, TX 78701"
    assert refreshed["status"] == "queued"


def test_public_redeem_by_code_submits_address(
    auth_client, prospect_id, stripe_stub, monkeypatch
):
    import app.stripe_payments as sp
    import app.fulfillment as fulfillment

    monkeypatch.setattr(sp, "send_recipient_address_request", lambda **kw: None)
    monkeypatch.setattr(fulfillment, "send_new_order_notification", lambda **kw: None)
    orderer_mail: dict = {}
    monkeypatch.setattr(
        sp, "send_orderer_receipt", lambda **kw: orderer_mail.update(kw)
    )

    order = auth_client.post("/gift-orders", json=_request_payload(prospect_id)).json()
    code = order["redeem_code"]
    _authorize_order(auth_client, order["id"], stripe_stub, monkeypatch)
    assert orderer_mail == {}  # no receipt on authorize-only

    auth_client.post("/auth/logout")
    assert auth_client.get(f"/public/redeem/{code.lower()}").status_code == 200
    resp = auth_client.post(
        f"/public/redeem/{code}",
        json={"shipping_address": "99 Redeem Lane", "recipient_name": "Dana Buyer"},
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["already_submitted"] is True
    assert orderer_mail["order_id"] == order["id"]

    assert auth_client.get(f"/public/redeem/{code}").status_code == 404


def test_public_redeem_unknown_code_404(client):
    assert client.get("/public/redeem/CK-00000").status_code == 404


def test_decline_redeem_cancels_authorization(
    auth_client, prospect_id, stripe_stub, monkeypatch
):
    import app.stripe_payments as sp
    import app.main as main
    from app.db import SessionLocal
    from app.models import GiftOrderModel

    monkeypatch.setattr(sp, "send_recipient_address_request", lambda **kw: None)
    declined_mail: dict = {}
    monkeypatch.setattr(
        main, "send_orderer_gift_declined", lambda **kw: declined_mail.update(kw)
    )

    order = auth_client.post("/gift-orders", json=_request_payload(prospect_id)).json()
    code = order["redeem_code"]
    _authorize_order(auth_client, order["id"], stripe_stub, monkeypatch)

    resp = auth_client.post(f"/public/redeem/{code}/decline")
    assert resp.status_code == 200, resp.text
    assert declined_mail["order_id"] == order["id"]

    with SessionLocal() as db:
        row = db.get(GiftOrderModel, order["id"])
        assert row.status == "canceled"
        assert row.payment_status == "canceled"
        assert row.redeem_code is None
        assert row.address_request_token is None

    assert auth_client.get(f"/public/redeem/{code}").status_code == 404


def test_address_request_followup_after_72_hours(
    auth_client, prospect_id, stripe_stub, monkeypatch
):
    from datetime import UTC, datetime, timedelta

    import app.jobs.address_request_followups as followups
    import app.stripe_payments as sp
    from app.db import SessionLocal
    from app.models import GiftOrderModel

    monkeypatch.setattr(sp, "send_recipient_address_request", lambda **kw: None)
    followup_mail: dict = {}
    monkeypatch.setattr(
        followups, "send_recipient_address_followup", lambda **kw: followup_mail.update(kw)
    )

    order = auth_client.post("/gift-orders", json=_request_payload(prospect_id)).json()
    _authorize_order(auth_client, order["id"], stripe_stub, monkeypatch)

    with SessionLocal() as db:
        row = db.get(GiftOrderModel, order["id"])
        row.address_request_sent_at = datetime.now(UTC) - timedelta(hours=73)
        db.add(row)
        db.commit()

    result = auth_client.post("/internal/jobs/address-request-followups")
    assert result.status_code == 200, result.text
    assert result.json()["sent"] == 1
    assert followup_mail["recipient_email"] == "dana@example.com"
    assert "/ship/" in followup_mail["address_form_url"]
    assert followup_mail["redeem_code"] == order["redeem_code"]

    # Idempotent: second run must not re-send.
    followup_mail.clear()
    again = auth_client.post("/internal/jobs/address-request-followups")
    assert again.status_code == 200
    assert again.json()["sent"] == 0
    assert followup_mail == {}


def test_address_request_followup_skips_before_window(
    auth_client, prospect_id, stripe_stub, monkeypatch
):
    import app.jobs.address_request_followups as followups
    import app.stripe_payments as sp

    monkeypatch.setattr(sp, "send_recipient_address_request", lambda **kw: None)
    followup_mail: dict = {}
    monkeypatch.setattr(
        followups, "send_recipient_address_followup", lambda **kw: followup_mail.update(kw)
    )

    order = auth_client.post("/gift-orders", json=_request_payload(prospect_id)).json()
    _authorize_order(auth_client, order["id"], stripe_stub, monkeypatch)

    result = auth_client.post("/internal/jobs/address-request-followups")
    assert result.status_code == 200
    assert result.json()["sent"] == 0
    assert followup_mail == {}


def test_address_request_followup_skips_expired_link(
    auth_client, prospect_id, stripe_stub, monkeypatch
):
    from datetime import UTC, datetime, timedelta

    import app.jobs.address_request_followups as followups
    import app.stripe_payments as sp
    from app.db import SessionLocal
    from app.models import GiftOrderModel

    monkeypatch.setattr(sp, "send_recipient_address_request", lambda **kw: None)
    followup_mail: dict = {}
    monkeypatch.setattr(
        followups, "send_recipient_address_followup", lambda **kw: followup_mail.update(kw)
    )

    order = auth_client.post("/gift-orders", json=_request_payload(prospect_id)).json()
    _authorize_order(auth_client, order["id"], stripe_stub, monkeypatch)

    with SessionLocal() as db:
        row = db.get(GiftOrderModel, order["id"])
        row.address_request_sent_at = datetime.now(UTC) - timedelta(hours=73)
        row.address_request_expires_at = datetime.now(UTC) - timedelta(hours=1)
        db.add(row)
        db.commit()

    result = auth_client.post("/internal/jobs/address-request-followups")
    assert result.status_code == 200
    assert result.json()["sent"] == 0
    assert followup_mail == {}


def test_address_request_followup_requires_secret_in_production(client, monkeypatch):
    from app.config import settings

    monkeypatch.setattr(settings, "app_env", "production")
    monkeypatch.setattr(settings, "cron_secret", "expected-secret")

    denied = client.post("/internal/jobs/address-request-followups")
    assert denied.status_code == 401

    ok = client.post(
        "/internal/jobs/address-request-followups",
        headers={"X-Cron-Secret": "expected-secret"},
    )
    assert ok.status_code == 200
    assert ok.json()["sent"] == 0
